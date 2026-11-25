"""Our World in Data grapher CSV fetcher."""

from __future__ import annotations

import io
import time
from dataclasses import dataclass

import pandas as pd
import requests

from ..config import IndicatorConfig
from .base import FetchError, SnapshotStore, http_get

BASE = "https://ourworldindata.org/grapher/{slug}.csv"


@dataclass
class FetchResult:
    frames: dict[str, pd.DataFrame]
    errors: dict[str, str]


def _read_csv(content: bytes) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(content), encoding="utf-8-sig", low_memory=False)


def fetch_indicator(
    session: requests.Session,
    store: SnapshotStore,
    indicator: IndicatorConfig,
    start_year: int,
    end_year: int,
    delay: float = 0.25,
) -> pd.DataFrame:
    slug = indicator.series
    if store.offline:
        path = store.latest("owid", slug, "csv")
        frame = _read_csv(path.read_bytes())
    else:
        cached = None if store.force else store.today("owid", slug, "csv")
        if cached is not None:
            frame = _read_csv(cached.read_bytes())
        else:
            url = BASE.format(slug=slug)
            response = http_get(session, url)
            store.save("owid", slug, response.content, "csv")
            frame = _read_csv(response.content)
            time.sleep(delay)

    if indicator.value_column and indicator.value_column in frame.columns:
        column = indicator.value_column
    else:
        candidates = [
            c for c in frame.columns if c not in {"Entity", "Code", "Year", "World region according to OWID"}
        ]
        if len(candidates) != 1:
            raise FetchError(
                f"{slug}: cannot identify value column {indicator.value_column!r}; "
                f"candidates={candidates}"
            )
        column = candidates[0]

    out = frame.rename(columns={column: "value"})[["Entity", "Code", "Year", "value"]].copy()
    out = out.rename(columns={"Entity": "name", "Code": "code", "Year": "year"})
    out["code"] = out["code"].astype("string").fillna("")
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    out["year"] = pd.to_numeric(out["year"], errors="coerce")
    out = out.dropna(subset=["year", "value"])
    out["year"] = out["year"].astype(int)
    out = out[(out["year"] >= start_year) & (out["year"] <= end_year)]
    out = out.drop_duplicates(subset=["code", "name", "year"], keep="last")
    return out.reset_index(drop=True)


def fetch_all(
    session: requests.Session,
    store: SnapshotStore,
    indicators: list[IndicatorConfig],
    start_year: int,
    end_year: int,
    progress=None,
) -> FetchResult:
    frames: dict[str, pd.DataFrame] = {}
    errors: dict[str, str] = {}
    for indicator in indicators:
        try:
            frame = fetch_indicator(session, store, indicator, start_year, end_year)
            if frame.empty:
                errors[indicator.id] = "no observations"
            else:
                frames[indicator.id] = frame
        except Exception as exc:  # noqa: BLE001 - isolate per-series failures
            errors[indicator.id] = str(exc)
        if progress:
            progress(indicator.id, indicator.id in frames, errors.get(indicator.id, "ok"))
    return FetchResult(frames=frames, errors=errors)
