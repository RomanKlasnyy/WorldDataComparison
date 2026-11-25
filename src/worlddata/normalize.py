"""Normalize source frames into canonical (iso3, indicator, year, value) observations."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import Config
from .countries import CountryRegistry, resolve_row


@dataclass
class NormalizeResult:
    observations: pd.DataFrame
    rejected: pd.DataFrame
    unresolved: pd.DataFrame
    skipped: pd.DataFrame
    alias_hits: list[tuple[str, str, str]] = field(default_factory=list)


def _empty_obs() -> pd.DataFrame:
    return pd.DataFrame(
        columns=["iso3", "indicator_id", "year", "value", "source_id", "retrieved_at"]
    )


def _empty_rejects() -> pd.DataFrame:
    return pd.DataFrame(
        columns=["source_id", "indicator_id", "iso3", "name", "year", "value", "reason"]
    )


_AGGREGATE_EXACT = {
    "World", "Africa", "Asia", "Europe", "North America", "South America", "Oceania",
    "Antarctica", "European Union (27)", "European Union", "Euro area", "OECD",
}
_AGGREGATE_TOKENS = (
    "(UNDP)", "(UN)", "(WHO)", "(WB)", "(OECD)", "income countries", "human development",
    "Arab States", "Sub-Saharan Africa", "Latin America", "Caribbean", "Pacific",
    "South Asia", "East Asia", "Central Asia", "Middle East", "Least developed",
    "Small states", "Fragile", "World", "ASEAN", "BRICS", "G7", "G20",
    "population-weighted", "Less developed", "More developed", "excluding",
    "England", "Scotland", "Wales", "Northern Ireland", "Palestine/",
)


def is_aggregate_label(code: str, name: str, registry: CountryRegistry) -> bool:
    text = str(name or "").strip()
    if text in _AGGREGATE_EXACT:
        return True
    if any(token in text for token in _AGGREGATE_TOKENS):
        return True
    code = str(code or "").strip().upper()
    if code.startswith("OWID_") and registry.resolve_code(code) is None:
        return True
    if code and registry.resolve_code(code) is None:
        try:
            import pycountry

            if pycountry.countries.get(alpha_3=code) is not None:
                return True
        except Exception:  # noqa: BLE001 - classification is best-effort
            pass
    return False


def _group_gaps(rows: list[dict]) -> pd.DataFrame:
    columns = ["source_id", "indicator_id", "name", "code", "n", "latest_year"]
    if not rows:
        return pd.DataFrame(columns=columns)
    return (
        pd.DataFrame(rows)
        .groupby(["source_id", "indicator_id", "name", "code"], dropna=False)
        .agg(n=("year", "size"), latest_year=("year", "max"))
        .reset_index()
    )


def normalize_frames(
    config: Config,
    registry: CountryRegistry,
    frames: dict[str, pd.DataFrame],
    retrieved_at: dict[str, str],
    floor_year: int,
    end_year: int,
) -> NormalizeResult:
    obs_parts: list[pd.DataFrame] = []
    rejects: list[dict] = []
    unresolved_rows: list[dict] = []
    skipped_rows: list[dict] = []
    alias_hits: set[tuple[str, str, str]] = set()

    for indicator in config.indicators:
        if indicator.source == "derived":
            continue
        frame = frames.get(indicator.id)
        if frame is None or frame.empty:
            continue
        source_id = indicator.source
        stamp = retrieved_at.get(source_id, "")
        min_year = max(floor_year, indicator.min_year or floor_year)

        work = frame.copy()
        if "iso3" in work.columns:
            work["raw_code"] = work["iso3"].astype(str).str.strip().str.upper()
            work["name"] = work["name"].astype(str) if "name" in work.columns else ""
            work["iso3"] = work["raw_code"].map(registry.resolve_code)
            work["matched_by"] = "code"
        else:
            work["raw_code"] = (
                work["code"].astype(str) if "code" in work.columns else ""
            )
            work["name"] = work["name"].astype(str) if "name" in work.columns else ""
            pairs = [
                resolve_row(registry, code, name)
                for code, name in zip(work["raw_code"], work["name"], strict=False)
            ]
            work["iso3"] = [p.iso3 for p in pairs]
            work["matched_by"] = [p.matched_by for p in pairs]

        work["year"] = pd.to_numeric(work["year"], errors="coerce")
        work["value"] = pd.to_numeric(work["value"], errors="coerce")
        work = work[work["year"].notna()]
        work["year"] = work["year"].astype(int)

        missing = work["iso3"].isna()
        if missing.any():
            for row in work[missing].itertuples(index=False):
                record = {
                    "source_id": source_id,
                    "indicator_id": indicator.id,
                    "name": str(row.name),
                    "code": str(row.raw_code),
                    "year": int(row.year),
                    "value": row.value,
                }
                if source_id in {"owid", "manual"} and not is_aggregate_label(
                    record["code"], record["name"], registry
                ):
                    unresolved_rows.append(record)
                else:
                    skipped_rows.append(record)
            work = work[~missing]

        work = work[work["value"].notna()]
        work = work[(work["year"] >= min_year) & (work["year"] <= end_year)]

        non_finite = ~np.isfinite(work["value"].to_numpy(dtype=float))
        if non_finite.any():
            for row in work[non_finite].itertuples(index=False):
                rejects.append(
                    {
                        "source_id": source_id,
                        "indicator_id": indicator.id,
                        "iso3": row.iso3,
                        "name": str(row.name),
                        "year": int(row.year),
                        "value": row.value,
                        "reason": "non-finite value",
                    }
                )
            work = work[~non_finite]

        reason = pd.Series("", index=work.index)
        out_of_range = pd.Series(False, index=work.index)
        if indicator.valid_min is not None:
            mask = work["value"] < indicator.valid_min
            out_of_range |= mask
            reason[mask] = f"below valid_min {indicator.valid_min}"
        if indicator.valid_max is not None:
            mask = work["value"] > indicator.valid_max
            out_of_range |= mask
            reason[mask] = f"above valid_max {indicator.valid_max}"
        if out_of_range.any():
            for idx, row in work[out_of_range].iterrows():
                rejects.append(
                    {
                        "source_id": source_id,
                        "indicator_id": indicator.id,
                        "iso3": row["iso3"],
                        "name": str(row["name"]),
                        "year": int(row["year"]),
                        "value": row["value"],
                        "reason": str(reason.loc[idx]),
                    }
                )
            work = work[~out_of_range]

        for row in work[work["matched_by"] == "name"].itertuples(index=False):
            alias_hits.add((str(row.name), source_id, str(row.iso3)))

        part = work[["iso3", "year", "value"]].copy()
        part.insert(0, "indicator_id", indicator.id)
        part["source_id"] = source_id
        part["retrieved_at"] = stamp
        part = part.drop_duplicates(subset=["iso3", "indicator_id", "year"], keep="last")
        obs_parts.append(part)

    observations = (
        pd.concat(obs_parts, ignore_index=True) if obs_parts else _empty_obs()
    ).sort_values(["indicator_id", "iso3", "year"], kind="stable")

    observations = pd.concat(
        [observations, _derive(config, observations)], ignore_index=True
    )
    observations = (
        observations.drop_duplicates(subset=["iso3", "indicator_id", "year"], keep="last")
        .sort_values(["indicator_id", "iso3", "year"], kind="stable")
        .reset_index(drop=True)
    )

    return NormalizeResult(
        observations=observations,
        rejected=pd.DataFrame(rejects) if rejects else _empty_rejects(),
        unresolved=_group_gaps(unresolved_rows),
        skipped=_group_gaps(skipped_rows),
        alias_hits=sorted(alias_hits),
    )


def _derive(config: Config, observations: pd.DataFrame) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for indicator in config.indicators:
        if indicator.source != "derived" or not indicator.derive:
            continue
        spec = indicator.derive
        numerator = observations.loc[
            observations["indicator_id"] == spec.numerator, ["iso3", "year", "value"]
        ].rename(columns={"value": "numerator"})
        denominator = observations.loc[
            observations["indicator_id"] == spec.denominator, ["iso3", "year", "value"]
        ].rename(columns={"value": "denominator"})
        if numerator.empty or denominator.empty:
            continue
        merged = numerator.merge(denominator, on=["iso3", "year"], how="inner")
        merged = merged[merged["denominator"].notna() & (merged["denominator"] != 0)]
        merged["value"] = (
            merged["numerator"] / merged["denominator"] * float(spec.multiplier)
        )
        merged = merged.replace([np.inf, -np.inf], np.nan).dropna(subset=["value"])
        if indicator.valid_min is not None:
            merged = merged[merged["value"] >= indicator.valid_min]
        if indicator.valid_max is not None:
            merged = merged[merged["value"] <= indicator.valid_max]
        if merged.empty:
            continue
        out = merged[["iso3", "year", "value"]].copy()
        out.insert(0, "indicator_id", indicator.id)
        out["source_id"] = "derived"
        out["retrieved_at"] = ""
        parts.append(out)
    return pd.concat(parts, ignore_index=True) if parts else _empty_obs()
