"""IMF DataMapper fetcher (World Economic Outlook series)."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import pandas as pd
import requests

from ..config import IndicatorConfig
from .base import FetchError, SnapshotStore, http_get

API = "https://www.imf.org/external/datamapper/api/v1/{series}"


@dataclass
class FetchResult:
    frames: dict[str, pd.DataFrame]
    errors: dict[str, str]


def fetch_indicator(
    session: requests.Session,
    store: SnapshotStore,
    indicator: IndicatorConfig,
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    series = indicator.series
    if store.offline:
        payload = store.load_json("imf", series)
    else:
        cached = None if store.force else store.today("imf", series, "json")
        if cached is not None:
            payload = json.loads(cached.read_text(encoding="utf-8"))
        else:
            response = http_get(session, API.format(series=series))
            store.save("imf", series, response.content, "json")
            try:
                payload = response.json()
            except ValueError as exc:
                raise FetchError(f"{series}: response is not JSON") from exc

    values = (payload or {}).get("values", {}).get(series)
    if not values:
        raise FetchError(f"{series}: no IMF values in response")

    # WEO publishes forecasts; never treat a projection as an observed statistic.
    cap = min(end_year, datetime.now(UTC).year - 1)
    rows = []
    for iso3, by_year in values.items():
        if not isinstance(by_year, dict):
            continue
        for year, value in by_year.items():
            try:
                year_int = int(year)
            except (TypeError, ValueError):
                continue
            if value is None or year_int < start_year or year_int > cap:
                continue
            rows.append({"iso3": str(iso3).upper(), "year": year_int, "value": float(value), "name": ""})
    frame = pd.DataFrame(rows, columns=["iso3", "year", "value", "name"])
    return frame.drop_duplicates(subset=["iso3", "year"], keep="last")


def fetch_all(
    session: requests.Session,
    store: SnapshotStore,
    indicators: list[IndicatorConfig],
    start_year: int,
    end_year: int,
    progress: Callable[[str, bool, str], None] | None = None,
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
        except Exception as exc:  # noqa: BLE001
            errors[indicator.id] = str(exc)
        if progress:
            progress(indicator.id, indicator.id in frames, errors.get(indicator.id, "ok"))
        time.sleep(0.2)
    return FetchResult(frames=frames, errors=errors)
