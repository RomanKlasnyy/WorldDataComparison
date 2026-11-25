"""Integration checks against the real built database (skipped when absent)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from worlddata.config import load_config
from worlddata.core.correlations import CorrOptions, correlation_pairs
from worlddata.core.dataset import load_dataset
from worlddata.core.groups import load_group_set, summarize
from worlddata.db import verify


@pytest.fixture(scope="module")
def dataset(real_repo, project_paths):
    config = load_config(project_paths)
    return load_dataset(real_repo, cutoff=2015, domain_order=config.domain_order)


def test_manifest_and_coverage(project_paths, real_repo):
    manifest = verify(project_paths)
    assert int(manifest["schema_version"]) == 1
    assert int(manifest["n_observations"]) > 150_000
    assert int(manifest["n_countries"]) == 197

    indicators = real_repo.indicators(include_hidden=False, with_data=True)
    assert len(indicators) >= 69
    assert (indicators["pct"] >= 60).sum() >= 60
    debt = indicators.set_index("id").loc["govt_debt"]
    assert debt["pct"] > 85
    assert debt["source_id"] == "imf"

    observations = real_repo.observations()
    assert int(observations.duplicated(subset=["iso3", "indicator_id", "year"]).sum()) == 0
    assert observations["year"].min() >= 2010


def test_no_unresolved_country_names(project_paths):
    path = project_paths.data / "unresolved.csv"
    if path.exists():
        unresolved = pd.read_csv(path)
        assert unresolved.empty, unresolved.head(10).to_string()


def test_dataset_shape(dataset):
    assert dataset.values.shape[0] == 197
    assert len(dataset.indicators) >= 69
    assert dataset.values.notna().any(axis=1).sum() > 190
    assert int(np.nanmax(dataset.years.to_numpy(dtype=float, na_value=np.nan))) >= 2024


def _value(dataset, iso3, indicator):
    return float(dataset.values.at[iso3, indicator])


def test_golden_values(dataset):
    assert _value(dataset, "USA", "gdp_nominal") > 20e12
    assert _value(dataset, "USA", "gdp_per_capita_ppp") > 70_000
    assert _value(dataset, "IRL", "gdp_per_capita_ppp") > 100_000
    assert _value(dataset, "NOR", "hdi") > 0.9
    assert _value(dataset, "JPN", "life_expectancy") > 80
    assert _value(dataset, "DEU", "population") > 80e6
    assert _value(dataset, "KOR", "fertility_rate") < 1.5
    assert _value(dataset, "DNK", "cpi") > 80
    assert _value(dataset, "CHE", "gdp_per_capita") > 80_000
    assert _value(dataset, "SGP", "gdp_per_capita_ppp") > 100_000


def test_statistical_sign_sanity(dataset):
    units = [i for i in ("gdp_per_capita_ppp", "life_expectancy", "fertility_rate", "cpi", "wgi_control_corruption") if i in dataset.indicator_ids]
    pairs = correlation_pairs(dataset, CorrOptions(log=True, min_n=30, control=None), units)
    lookup = {
        frozenset((row.a, row.b)): row
        for row in pairs.itertuples(index=False)
    }

    gdp_life = lookup[frozenset(("gdp_per_capita_ppp", "life_expectancy"))]
    assert 0.5 < gdp_life.r < 0.9
    assert gdp_life.q < 0.001

    gdp_fertility = lookup[frozenset(("gdp_per_capita_ppp", "fertility_rate"))]
    assert gdp_fertility.r < -0.3

    cpi_wgi = lookup[frozenset(("cpi", "wgi_control_corruption"))]
    assert cpi_wgi.r > 0.8  # same construct, expected to agree


def test_partial_correlation_control(dataset):
    units = ["gdp_per_capita_ppp", "fertility_rate", "cpi"]
    pairs = correlation_pairs(dataset, CorrOptions(log=True, min_n=30, control="gdp_per_capita_ppp"), units)
    row = pairs[(pairs["a"] == "fertility_rate") & (pairs["b"] == "cpi")].iloc[0]
    assert np.isfinite(row["partial_r"])
    assert abs(row["partial_r"]) < 1
    assert row["n"] >= 30


def test_same_year_mode_is_sparser(dataset):
    units = ["gdp_per_capita_ppp", "gini"]
    mixed = correlation_pairs(dataset, CorrOptions(log=True, min_n=10, same_year=False), units).iloc[0]
    strict = correlation_pairs(dataset, CorrOptions(log=True, min_n=10, same_year=True), units).iloc[0]
    assert strict["n"] < mixed["n"]


def test_group_comparison(real_repo, project_paths, dataset):
    group_set = load_group_set(real_repo, project_paths.groups_local)
    assert "eu" in group_set.ids()
    summary = summarize(dataset, group_set, "gdp_per_capita_ppp", ["eu", "asean", "nato", "mercosur"])
    table = summary.table.set_index("group_id")
    assert table.loc["eu", "aggregate"] > table.loc["asean", "aggregate"]
    assert table.loc["eu", "coverage_pct"] > 90
    assert table.loc["eu", "n_members"] >= 27
    for group_id in ("eu", "nato", "asean", "mercosur"):
        assert table.loc[group_id, "n_data"] > 0
