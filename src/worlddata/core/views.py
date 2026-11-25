"""Reusable table builders for the dashboard, rankings, profile and compare pages."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .dataset import Dataset


def _direction(meta: pd.Series) -> bool | None:
    value = meta.get("higher_is_better")
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    return bool(value)


def percentiles(values: pd.Series, direction: bool | None) -> pd.Series:
    """Share of countries the value is better than, 0-100 (100 = best)."""
    values = values.dropna()
    n = len(values)
    if n <= 1:
        return pd.Series(100.0, index=values.index)
    if direction is True:
        return values.map(lambda v: float((values < v).sum()) / (n - 1) * 100.0)
    if direction is False:
        return values.map(lambda v: float((values > v).sum()) / (n - 1) * 100.0)
    return values.map(lambda v: float((values < v).sum()) / (n - 1) * 100.0)


def rank_table(dataset: Dataset, indicator_id: str) -> pd.DataFrame:
    if indicator_id not in dataset.values.columns:
        return pd.DataFrame()
    meta = dataset.indicators.loc[indicator_id]
    direction = _direction(meta)
    values = dataset.values[indicator_id].dropna()
    years = dataset.years[indicator_id].reindex(values.index)
    if values.empty:
        return pd.DataFrame()
    frame = pd.DataFrame(
        {
            "iso3": values.index,
            "country": [dataset.name(c) for c in values.index],
            "value": values.to_numpy(dtype=float),
            "year": years.to_numpy(),
            "rank_high": values.rank(ascending=False, method="min").to_numpy(),
            "rank_low": values.rank(ascending=True, method="min").to_numpy(),
            "n": len(values),
            "better_pct": percentiles(values, direction).to_numpy(),
            "region": [dataset.countries.loc[c, "region"] for c in values.index],
            "income_group": [dataset.countries.loc[c, "income_group"] for c in values.index],
        }
    )
    if direction is False:
        frame = frame.sort_values("value", ascending=True, kind="stable")
    else:
        frame = frame.sort_values("value", ascending=False, kind="stable")
    frame["rank"] = np.arange(1, len(frame) + 1)
    return frame.reset_index(drop=True)


def indicator_summary(dataset: Dataset, indicator_id: str) -> dict:
    if indicator_id not in dataset.values.columns:
        return {}
    meta = dataset.indicators.loc[indicator_id]
    values = dataset.values[indicator_id].dropna()
    years = dataset.years[indicator_id].dropna()
    n_countries = len(dataset.values)
    return {
        "indicator_id": indicator_id,
        "name": str(meta["name"]),
        "domain": str(meta["domain"]),
        "unit": str(meta["unit"]),
        "description": str(meta.get("description") or ""),
        "attribution": str(meta.get("attribution") or ""),
        "source": str(meta.get("source_name") or meta.get("source_id") or ""),
        "n": int(values.size),
        "coverage_pct": round(values.size / max(n_countries, 1) * 100, 1),
        "mean": float(values.mean()) if values.size else np.nan,
        "median": float(values.median()) if values.size else np.nan,
        "min": float(values.min()) if values.size else np.nan,
        "max": float(values.max()) if values.size else np.nan,
        "latest_year": int(years.max()) if years.size else None,
        "median_year": float(years.median()) if years.size else None,
        "is_composite": bool(meta.get("is_composite")),
        "higher_is_better": _direction(meta),
    }


def country_profile(dataset: Dataset, iso3: str) -> pd.DataFrame:
    if iso3 not in dataset.values.index:
        return pd.DataFrame()
    rows = []
    for indicator_id in dataset.indicator_ids:
        meta = dataset.indicators.loc[indicator_id]
        direction = _direction(meta)
        column = dataset.values[indicator_id]
        value = column.get(iso3, np.nan)
        if value is None or (isinstance(value, float) and np.isnan(value)):
            continue
        clean = column.dropna()
        if direction is True:
            pct = float((clean < value).sum()) / max(len(clean) - 1, 1) * 100
            rank = int((clean > value).sum()) + 1
        elif direction is False:
            pct = float((clean > value).sum()) / max(len(clean) - 1, 1) * 100
            rank = int((clean < value).sum()) + 1
        else:
            rank = int((clean > value).sum()) + 1
            pct = float((clean < value).sum()) / max(len(clean) - 1, 1) * 100
        rows.append(
            {
                "indicator_id": indicator_id,
                "indicator": str(meta["name"]),
                "domain": str(meta["domain"]),
                "unit": str(meta["unit"]),
                "value": float(value),
                "year": dataset.years.at[iso3, indicator_id],
                "rank": rank,
                "n": len(clean),
                "better_pct": pct,
                "higher_is_better": direction,
                "is_composite": bool(meta.get("is_composite")),
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    order = {d: i for i, d in enumerate(dict.fromkeys(dataset.indicators["domain"]))}
    frame["_order"] = frame["domain"].map(lambda d: order.get(d, 999))
    return frame.sort_values(["_order", "better_pct"], ascending=[True, False]).drop(
        columns="_order"
    ).reset_index(drop=True)


def compare_table(dataset: Dataset, iso3_codes: list[str]) -> pd.DataFrame:
    codes = [c for c in iso3_codes if c in dataset.values.index]
    rows = []
    for indicator_id in dataset.indicator_ids:
        meta = dataset.indicators.loc[indicator_id]
        row = {
            "indicator_id": indicator_id,
            "indicator": str(meta["name"]),
            "domain": str(meta["domain"]),
            "unit": str(meta["unit"]),
        }
        for code in codes:
            value = dataset.values.at[code, indicator_id]
            row[f"{code}|value"] = value
            row[f"{code}|year"] = dataset.years.at[code, indicator_id]
        rows.append(row)
    return pd.DataFrame(rows)


def compare_percentiles(dataset: Dataset, iso3_codes: list[str]) -> pd.DataFrame:
    codes = [c for c in iso3_codes if c in dataset.values.index]
    rows = []
    for indicator_id in dataset.indicator_ids:
        meta = dataset.indicators.loc[indicator_id]
        direction = _direction(meta)
        column = dataset.values[indicator_id]
        row = {"indicator_id": indicator_id, "indicator": str(meta["name"]), "domain": str(meta["domain"])}
        for code in codes:
            value = column.get(code)
            if value is None or (isinstance(value, float) and np.isnan(value)):
                row[code] = np.nan
                continue
            clean = column.dropna()
            if direction is True:
                row[code] = float((clean < value).sum()) / max(len(clean) - 1, 1) * 100
            elif direction is False:
                row[code] = float((clean > value).sum()) / max(len(clean) - 1, 1) * 100
            else:
                row[code] = float((clean < value).sum()) / max(len(clean) - 1, 1) * 100
        rows.append(row)
    return pd.DataFrame(rows)


def domain_coverage(dataset: Dataset) -> pd.DataFrame:
    total = max(len(dataset.values), 1)
    frame = (
        dataset.values.notna()
        .sum()
        .rename("n")
        .to_frame()
        .join(dataset.indicators[["domain", "name"]])
    )
    frame["coverage_pct"] = (frame["n"] / total * 100).round(1)
    return frame.reset_index(names="indicator_id")


def search_countries(dataset: Dataset, query: str) -> pd.DataFrame:
    frame = dataset.countries[["iso3", "name", "region", "income_group"]]
    if not query.strip():
        return frame
    mask = frame["name"].str.contains(query.strip(), case=False, regex=False, na=False)
    return frame[mask]
