from __future__ import annotations

import pandas as pd
import pytest

from worlddata.core.views import (
    compare_percentiles,
    compare_table,
    country_profile,
    domain_coverage,
    indicator_summary,
    percentiles,
    rank_table,
)


def _dataset(factory):
    values = {
        "USA": {"good": 10.0, "bad": 10.0, "neutral": 10.0},
        "FRA": {"good": 20.0, "bad": 20.0, "neutral": 20.0},
        "KEN": {"good": 30.0, "bad": 30.0, "neutral": 25.0},
    }
    meta = {
        "good": {"higher_is_better": True, "domain": "D1", "unit": "pts"},
        "bad": {"higher_is_better": False, "domain": "D1", "unit": "pts"},
        "neutral": {"higher_is_better": None, "domain": "D2", "unit": "pts"},
    }
    return factory(values, indicator_meta=meta)


def test_rank_table_direction(factory):
    ds = _dataset(factory)
    good = rank_table(ds, "good").set_index("country")
    assert good.loc["KEN", "rank"] == 1
    assert good.loc["KEN", "better_pct"] == pytest.approx(100.0)
    assert good.loc["USA", "better_pct"] == pytest.approx(0.0)

    bad = rank_table(ds, "bad").set_index("country")
    assert bad.loc["USA", "rank"] == 1
    assert bad.loc["USA", "better_pct"] == pytest.approx(100.0)

    neutral = rank_table(ds, "neutral").set_index("country")
    assert neutral.loc["FRA", "better_pct"] == pytest.approx(50.0)


def test_percentiles_guard():
    series = pd.Series({"A": 1.0})
    assert percentiles(series, True).iloc[0] == 100.0
    assert percentiles(pd.Series(dtype=float), True).empty


def test_indicator_summary(factory):
    ds = _dataset(factory)
    summary = indicator_summary(ds, "good")
    assert summary["n"] == 3
    assert summary["max"] == 30.0
    assert summary["median"] == 20.0
    assert summary["coverage_pct"] == 100.0


def test_country_profile(factory):
    ds = _dataset(factory)
    profile = country_profile(ds, "USA")
    assert set(profile["indicator"]) == {"good", "bad", "neutral"}
    row = profile.set_index("indicator").loc["good"]
    assert row["rank"] == 3
    assert row["better_pct"] == 0.0
    assert country_profile(ds, "XXX").empty


def test_compare_tables(factory):
    ds = _dataset(factory)
    table = compare_table(ds, ["USA", "FRA"])
    assert len(table) == 3
    assert "USA|value" in table.columns
    pct = compare_percentiles(ds, ["USA", "FRA"])
    assert pct.shape[0] == 3
    assert set(pct.columns) >= {"USA", "FRA"}


def test_domain_coverage(factory):
    ds = _dataset(factory)
    coverage = domain_coverage(ds)
    d1 = coverage[coverage["domain"] == "D1"]
    assert len(d1) == 2
    assert d1["coverage_pct"].tolist() == [100.0, 100.0]
    d2 = coverage[coverage["domain"] == "D2"]
    assert d2["n"].iloc[0] == 3
