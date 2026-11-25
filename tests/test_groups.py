from __future__ import annotations

import types

import numpy as np
import pandas as pd
import pytest
import yaml

from worlddata.core.groups import (
    GroupSet,
    aggregate,
    compare,
    load_group_set,
    member_table,
    save_group_members,
    summarize,
)


def _group_set() -> GroupSet:
    groups = pd.DataFrame(
        [
            {"id": "A", "name": "Alpha", "family": "economic", "description": "", "color": "#111111", "origin": "shipped", "n_members": 5},
            {"id": "B", "name": "Beta", "family": "military", "description": "", "color": "#222222", "origin": "shipped", "n_members": 5},
            {"id": "C", "name": "Gamma", "family": "cultural", "description": "", "color": "#333333", "origin": "shipped", "n_members": 5},
        ]
    )
    members = {
        "A": [f"A{i}" for i in range(5)],
        "B": [f"B{i}" for i in range(5)],
        "C": [f"C{i}" for i in range(5)],
    }
    return GroupSet(groups=groups, members=members)


@pytest.fixture
def group_dataset(dataset_factory):
    values = {}
    for i in range(5):
        values[f"A{i}"] = {"val": float(i + 1), "rate": float(10 * (i + 1)), "population": 100.0}
        values[f"B{i}"] = {"val": float(10 + i), "rate": float(20 + i), "population": 1000.0}
        values[f"C{i}"] = {"val": float(100 + i), "rate": float(30 + i), "population": 10000.0}
    for i in range(3):
        values[f"R{i}"] = {"val": 50.0, "rate": 25.0, "population": 500.0}
    meta = {
        "val": {"aggregation": "median", "higher_is_better": True},
        "rate": {"aggregation": "weighted", "higher_is_better": True},
        "population": {"aggregation": "sum", "unit": "people", "higher_is_better": None},
    }
    return dataset_factory(values, indicator_meta=meta)


def test_aggregate_modes():
    values = np.array([1.0, 2.0, 3.0, 4.0])
    assert aggregate(values, "median") == 2.5
    assert aggregate(values, "mean") == 2.5
    assert aggregate(values, "sum") == 10.0
    assert aggregate(values, "weighted", np.array([1.0, 1.0, 1.0, 1.0])) == 2.5
    assert aggregate(values, "weighted", np.array([1.0, 0.0, 0.0, 3.0])) == 3.25
    assert np.isnan(aggregate(np.array([]), "median"))


def test_summarize_median_and_coverage(group_dataset):
    summary = summarize(group_dataset, _group_set(), "val", ["A", "B", "C"])
    table = summary.table.set_index("group_id")
    assert table.loc["A", "median"] == 3.0
    assert table.loc["B", "median"] == 12.0
    assert table.loc["C", "median"] == 102.0
    assert table.loc["A", "aggregate"] == 3.0
    assert table.loc["A", "coverage_pct"] == 100.0
    assert list(table.index) == ["C", "B", "A"]  # higher is better, descending


def test_summarize_weighted(dataset_factory):
    values = {
        "A0": {"rate": 10.0, "population": 900.0},
        "A1": {"rate": 10.0, "population": 100.0},
        "B0": {"rate": 50.0, "population": 100.0},
        "B1": {"rate": 50.0, "population": 100.0},
    }
    meta = {
        "rate": {"aggregation": "weighted"},
        "population": {"aggregation": "sum"},
    }
    ds = dataset_factory(values, indicator_meta=meta)
    summary = summarize(ds, _group_set(), "rate", ["A", "B"])
    table = summary.table.set_index("group_id")
    assert table.loc["A", "aggregate"] == pytest.approx(10.0)
    assert table.loc["B", "aggregate"] == pytest.approx(50.0)


def test_compare_tests(group_dataset):
    comparison = compare(group_dataset, _group_set(), "val", ["A", "B", "C"])
    assert len(comparison.summary) == 3
    assert len(comparison.pairwise) == 3
    assert comparison.kruskal_p < 0.05
    assert comparison.pairwise["q"].between(0, 1).all()
    assert len(comparison.vs_rest) == 3
    assert comparison.vs_rest["cliffs_delta"].iloc[0] < 0  # smallest group vs rest


def test_member_table(group_dataset):
    table = member_table(group_dataset, _group_set(), "A", "val")
    assert len(table) == 5
    assert table["value"].iloc[0] == 5.0


def test_overlay_roundtrip(tmp_path):
    shipped = pd.DataFrame(
        [
            {"id": "A", "name": "Alpha", "family": "economic", "description": "", "color": "#111", "origin": "shipped"},
            {"id": "B", "name": "Beta", "family": "military", "description": "", "color": "#222", "origin": "shipped"},
        ]
    )
    members = pd.DataFrame(
        [{"group_id": "A", "iso3": "USA"}, {"group_id": "A", "iso3": "FRA"}, {"group_id": "B", "iso3": "USA"}]
    )
    countries = pd.DataFrame([{"iso3": code} for code in ("USA", "FRA", "DEU", "KEN")])
    repo = types.SimpleNamespace(
        groups=lambda: shipped,
        group_members=lambda: members,
        countries=lambda include_territories=False: countries,
    )
    overlay = tmp_path / "groups.local.yaml"
    base = load_group_set(repo, overlay)
    assert base.members_of("A") == ["FRA", "USA"]

    save_group_members(overlay, "A", ["USA", "DEU", "NOT_A_COUNTRY"])
    updated = load_group_set(repo, overlay)
    assert updated.members_of("A") == ["DEU", "USA"]
    assert yaml.safe_load(overlay.read_text(encoding="utf-8"))["A"]["members"] == ["DEU", "NOT_A_COUNTRY", "USA"]
