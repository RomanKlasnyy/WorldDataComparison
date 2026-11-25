"""CSV/XLSX imports for indicators without a stable free bulk feed."""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

from ..config import Config, IndicatorConfig
from ..countries import CountryRegistry
from .base import FetchError, SnapshotStore

_COUNTRY_COLUMNS = ("country", "country_name", "name", "entity", "country name")
_CODE_COLUMNS = ("code", "iso3", "iso_code", "country_code")
_YEAR_COLUMNS = ("year", "date", "period")
_VALUE_COLUMNS = ("value", "score", "index", "points")


def _find(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    lowered = {c.strip().casefold(): c for c in columns}
    for candidate in candidates:
        if candidate in lowered:
            return lowered[candidate]
    return None


def read_import_file(path: Path) -> pd.DataFrame:
    suffix = path.suffix.casefold()
    if suffix in {".xlsx", ".xls", ".xlsm"}:
        return pd.read_excel(path)
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise FetchError(f"could not decode {path}")


def canonicalize_import(
    frame: pd.DataFrame, indicator: IndicatorConfig, registry: CountryRegistry
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    country_col = _find(list(frame.columns), _COUNTRY_COLUMNS)
    year_col = _find(list(frame.columns), _YEAR_COLUMNS)
    value_col = _find(list(frame.columns), _VALUE_COLUMNS)
    code_col = _find(list(frame.columns), _CODE_COLUMNS)

    if year_col is None or value_col is None or (country_col is None and code_col is None):
        raise FetchError(
            "import file needs columns for country (or code), year and value; "
            f"found {list(frame.columns)}"
        )

    out = pd.DataFrame(
        {
            "code": frame[code_col].astype(str) if code_col else "",
            "name": frame[country_col].astype(str) if country_col else "",
            "year": pd.to_numeric(frame[year_col], errors="coerce"),
            "value": pd.to_numeric(frame[value_col], errors="coerce"),
        }
    )
    out["reason"] = ""
    missing = out["year"].isna() | out["value"].isna()
    out.loc[missing, "reason"] = "missing year or value"
    out = out[~missing]
    out["year"] = out["year"].astype(int)
    out["iso3"] = [
        registry.resolve(code, name) for code, name in zip(out["code"], out["name"], strict=False)
    ]

    unresolved = out[out["iso3"].isna()].copy()
    unresolved["reason"] = "unresolved country"
    out = out[out["iso3"].notna()].copy()

    range_bad = pd.Series(False, index=out.index)
    reason = pd.Series("", index=out.index)
    if indicator.valid_min is not None:
        mask = out["value"] < indicator.valid_min
        range_bad |= mask
        reason[mask] = f"below valid_min {indicator.valid_min}"
    if indicator.valid_max is not None:
        mask = out["value"] > indicator.valid_max
        range_bad |= mask
        reason[mask] = f"above valid_max {indicator.valid_max}"
    rejected = out[range_bad].copy()
    rejected["reason"] = reason[range_bad]
    out = out[~range_bad]

    out = out.drop_duplicates(subset=["iso3", "year"], keep="last")
    clean = out[["iso3", "name", "year", "value"]].rename(columns={"iso3": "code"})
    return clean, unresolved, rejected


def import_file(
    store: SnapshotStore,
    config: Config,
    registry: CountryRegistry,
    indicator_id: str,
    path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    indicator = config.indicator_map.get(indicator_id)
    if indicator is None:
        raise FetchError(f"unknown indicator {indicator_id!r}; add it to config/indicators.yaml first")

    frame = read_import_file(path)
    clean, unresolved, rejected = canonicalize_import(frame, indicator, registry)
    if clean.empty:
        raise FetchError("no usable rows after country resolution and range checks")

    buffer = io.StringIO()
    clean.to_csv(buffer, index=False)
    store.save("manual", indicator_id, buffer.getvalue().encode("utf-8"), "csv")
    return clean, unresolved, rejected


def load_snapshots(
    store: SnapshotStore,
    config: Config,
    indicators: list[IndicatorConfig],
    start_year: int,
    end_year: int,
) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for indicator in indicators:
        try:
            path = store.latest("manual", indicator.id, "csv")
        except FetchError:
            continue
        frame = pd.read_csv(path)
        if frame.empty:
            continue
        frame["year"] = pd.to_numeric(frame["year"], errors="coerce")
        frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
        frame = frame.dropna(subset=["year", "value"])
        frame["year"] = frame["year"].astype(int)
        if "code" not in frame.columns:
            frame["code"] = ""
        if "name" not in frame.columns:
            frame["name"] = ""
        frame = frame[(frame["year"] >= start_year) & (frame["year"] <= end_year)]
        if not frame.empty:
            frames[indicator.id] = frame[["code", "name", "year", "value"]]
    return frames
