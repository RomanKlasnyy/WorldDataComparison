"""World Bank Indicators API fetcher (WDI source 2 and WGI source 3)."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd
import requests

from ..config import IndicatorConfig
from .base import FetchError, SnapshotStore, http_get

API = "https://api.worldbank.org/v2/country/all/indicator/{series}"
PER_PAGE = 20000


@dataclass
class FetchResult:
    frames: dict[str, pd.DataFrame]
    errors: dict[str, str]


def _safe_name(series: str) -> str:
    return series.replace("/", "_")


def fetch_indicator(
    session: requests.Session,
    store: SnapshotStore,
    indicator: IndicatorConfig,
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    name = _safe_name(indicator.series)
    if store.offline:
        payload = store.load_json(indicator.source, name)
    else:
        cached = None if store.force else store.today(indicator.source, name, "json")
        if cached is not None:
            payload = json.loads(cached.read_text(encoding="utf-8"))
        else:
            url = API.format(series=indicator.series) + (
                f"?format=json&per_page={PER_PAGE}&date={start_year}:{end_year}"
            )
            response = http_get(session, url)
            store.save(indicator.source, name, response.content, "json")
            try:
                payload = response.json()
            except ValueError as exc:
                raise FetchError(f"{indicator.series}: response is not JSON") from exc

    return _to_frame(payload, session, store, indicator, start_year, end_year)


def _to_frame(
    payload,
    session: requests.Session,
    store: SnapshotStore,
    indicator: IndicatorConfig,
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    if not isinstance(payload, list) or len(payload) < 2 or not payload[1]:
        message = payload[0].get("message") if isinstance(payload, list) and payload else payload
        raise FetchError(f"{indicator.series}: no data ({message})")

    rows: list[dict] = []
    pages = 1
    if isinstance(payload[0], dict):
        pages = int(payload[0].get("pages", 1) or 1)

    def collect(page_payload) -> None:
        for item in page_payload[1] or []:
            code = (item.get("countryiso3code") or "").strip().upper()
            if not code:
                continue
            value = item.get("value")
            if value is None:
                continue
            rows.append(
                {
                    "iso3": code,
                    "year": int(item["date"]),
                    "value": float(value),
                    "name": (item.get("country") or {}).get("value", ""),
                }
            )

    collect(payload)
    name = _safe_name(indicator.series)
    for page in range(2, pages + 1):
        if store.offline:
            raise FetchError(
                f"{indicator.series}: cached snapshot has {pages} pages; re-fetch online to page it"
            )
        url = API.format(series=indicator.series) + (
            f"?format=json&per_page={PER_PAGE}&date={start_year}:{end_year}&page={page}"
        )
        response = http_get(session, url)
        store.save(indicator.source, f"{name}_page{page}", response.content, "json")
        collect(response.json())
        time.sleep(0.1)

    frame = pd.DataFrame(rows, columns=["iso3", "year", "value", "name"])
    if not frame.empty:
        frame = frame[(frame["year"] >= start_year) & (frame["year"] <= end_year)]
        frame = frame.drop_duplicates(subset=["iso3", "year"], keep="last")
    return frame


def fetch_all(
    session: requests.Session,
    store: SnapshotStore,
    indicators: list[IndicatorConfig],
    start_year: int,
    end_year: int,
    delay: float = 0.5,
    progress: Callable[[str, bool, str], None] | None = None,
) -> FetchResult:
    frames: dict[str, pd.DataFrame] = {}
    errors: dict[str, str] = {}
    for index, indicator in enumerate(indicators, start=1):
        try:
            frame = fetch_indicator(session, store, indicator, start_year, end_year)
            if frame.empty:
                errors[indicator.id] = "no observations"
            else:
                frames[indicator.id] = frame
        except Exception as exc:  # noqa: BLE001 - one broken series must not kill the build
            errors[indicator.id] = str(exc)
        if progress:
            progress(indicator.id, indicator.id in frames, errors.get(indicator.id, f"{index} ok"))
        time.sleep(delay)
    return FetchResult(frames=frames, errors=errors)
