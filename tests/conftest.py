"""Shared pytest fixtures and synthetic dataset builders."""

from __future__ import annotations

import os

import numpy as np
import pandas as pd
import pytest

from worlddata.paths import Paths, get_paths

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def make_dataset(
    values: dict[str, dict[str, float]],
    *,
    years: dict[str, dict[str, int]] | None = None,
    indicator_meta: dict[str, dict] | None = None,
    country_meta: dict[str, dict] | None = None,
    cutoff: int = 2015,
):
    from worlddata.core.dataset import Dataset

    iso = list(values)
    ids = list(next(iter(values.values())))
    frame = pd.DataFrame(values).T[ids].astype(float)
    frame.index.name = "iso3"

    if years is None:
        year_frame = pd.DataFrame(2020, index=iso, columns=ids, dtype="Int64")
    else:
        year_frame = pd.DataFrame(years).T[ids].astype("Int64")

    country_rows = []
    for code in iso:
        meta = (country_meta or {}).get(code, {})
        country_rows.append(
            {
                "iso3": code,
                "name": meta.get("name", code),
                "official_name": meta.get("official_name", code),
                "entity_type": meta.get("entity_type", "state"),
                "un_member": meta.get("un_member", True),
                "region": meta.get("region", "Test region"),
                "subregion": meta.get("subregion", "Test subregion"),
                "continent": meta.get("continent", "Test continent"),
                "income_group": meta.get("income_group", "High income"),
                "is_default": meta.get("is_default", 1),
            }
        )
    countries = pd.DataFrame(country_rows).set_index("iso3", drop=False)

    ind_rows = []
    for indicator_id in ids:
        meta = (indicator_meta or {}).get(indicator_id, {})
        ind_rows.append(
            {
                "id": indicator_id,
                "name": meta.get("name", indicator_id),
                "domain": meta.get("domain", "Test domain"),
                "description": meta.get("description", ""),
                "unit": meta.get("unit", "index"),
                "source_id": meta.get("source_id", "worldbank"),
                "source_name": meta.get("source_name", "World Bank"),
                "series": meta.get("series", indicator_id),
                "higher_is_better": meta.get("higher_is_better", True),
                "default_log": meta.get("default_log", False),
                "is_composite": meta.get("is_composite", False),
                "hidden": meta.get("hidden", 0),
                "aggregation": meta.get("aggregation", "median"),
                "valid_min": meta.get("valid_min", None),
                "valid_max": meta.get("valid_max", None),
                "attribution": meta.get("attribution", ""),
                "n_countries": meta.get("n_countries", len(iso)),
                "pct": meta.get("pct", 100.0),
                "min_year": meta.get("min_year", 2010),
                "max_year": meta.get("max_year", 2024),
                "latest_year": meta.get("latest_year", 2024),
            }
        )
    indicators = pd.DataFrame(ind_rows).set_index("id", drop=False)

    return Dataset(
        values=frame,
        years=year_frame,
        countries=countries,
        indicators=indicators,
        cutoff=cutoff,
    )


@pytest.fixture
def dataset_factory():
    return make_dataset


@pytest.fixture
def factory():
    return make_dataset


@pytest.fixture(scope="session")
def project_paths() -> Paths:
    return get_paths()


@pytest.fixture(scope="session")
def real_repo(project_paths):
    from worlddata.db import DataError, open_repository

    try:
        repo = open_repository(project_paths)
    except DataError as exc:
        pytest.skip(f"dataset not built: {exc}")
    yield repo
    repo.close()


@pytest.fixture
def rng():
    return np.random.default_rng(42)
