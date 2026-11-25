from __future__ import annotations

import numpy as np
import pytest

from worlddata.core.correlations import (
    CorrOptions,
    cluster_order,
    correlation_pairs,
    matrix_from_pairs,
    pair_points,
    pairs_summary,
    prepare,
)


def _dataset(factory, values, years=None, meta=None):
    return factory(values, years=years, indicator_meta=meta)


def test_strong_positive_relation(factory, rng):
    n = 80
    x = rng.normal(50, 10, n)
    y = 2.0 * x + rng.normal(0, 5, n)
    values = {
        f"C{i:03d}": {"x": float(x[i]), "y": float(y[i])} for i in range(n)
    }
    ds = _dataset(factory, values)
    pairs = correlation_pairs(ds, CorrOptions(log=False, min_n=30))
    row = pairs[(pairs["a"] == "x") & (pairs["b"] == "y")].iloc[0]
    assert row["n"] == n
    assert row["r"] > 0.9
    assert row["rho"] > 0.9
    assert row["q"] < 0.001
    assert row["ci_low"] < row["r"] < row["ci_high"]
    assert not row["insufficient"]


def test_partial_correlation_removes_confounder(factory, rng):
    n = 200
    confounder = rng.normal(0, 1, n)
    x = confounder + rng.normal(0, 0.7, n)
    y = confounder + rng.normal(0, 0.7, n)
    values = {
        f"C{i:03d}": {"x": float(x[i]), "y": float(y[i]), "conf": float(confounder[i])}
        for i in range(n)
    }
    ds = _dataset(factory, values)
    raw = correlation_pairs(ds, CorrOptions(log=False, control=None), ["x", "y"]).iloc[0]
    partial = correlation_pairs(ds, CorrOptions(log=False, control="conf"), ["x", "y"]).iloc[0]
    assert raw["r"] > 0.5
    assert abs(partial["partial_r"]) < 0.2
    assert partial["partial_r"] != partial["r"]


def test_partial_skips_self_control(factory, rng):
    n = 60
    x = rng.normal(size=n)
    y = x + rng.normal(size=n)
    values = {f"C{i:03d}": {"x": float(x[i]), "y": float(y[i])} for i in range(n)}
    ds = _dataset(factory, values)
    row = correlation_pairs(ds, CorrOptions(log=False, control="x"), ["x", "y"]).iloc[0]
    assert np.isnan(row["partial_r"])


def test_same_year_filter(factory):
    values = {"USA": {"x": 1.0, "y": 2.0}, "FRA": {"x": 2.0, "y": 4.0}, "KEN": {"x": 3.0, "y": 6.0}}
    years = {"USA": {"x": 2020, "y": 2021}, "FRA": {"x": 2020, "y": 2021}, "KEN": {"x": 2020, "y": 2021}}
    ds = _dataset(factory, values, years=years)
    same = correlation_pairs(ds, CorrOptions(log=False, same_year=True, min_n=2))
    assert same.iloc[0]["n"] == 0
    assert bool(same.iloc[0]["insufficient"])
    mixed = correlation_pairs(ds, CorrOptions(log=False, same_year=False, min_n=2))
    assert mixed.iloc[0]["n"] == 3
    assert mixed.iloc[0]["year_gap_median"] == 1


def test_log_transform(factory):
    values = {
        f"C{i}": {"x": 10.0 ** (i + 1), "y": 10.0 ** (2 * (i + 1))} for i in range(20)
    }
    ds = _dataset(
        factory,
        values,
        meta={"x": {"default_log": True, "unit": "US$"}, "y": {"default_log": True, "unit": "US$"}},
    )
    matrix, _ = prepare(ds, CorrOptions(log=True))
    assert np.allclose(matrix[:, 0], np.arange(1, 21))
    raw_matrix, _ = prepare(ds, CorrOptions(log=False))
    assert raw_matrix[0, 0] == pytest.approx(10.0)
    row = correlation_pairs(ds, CorrOptions(log=True, min_n=5)).iloc[0]
    assert row["r"] == pytest.approx(1.0, abs=1e-9)


def test_outlier_exclusion(factory, rng):
    n = 60
    x = rng.normal(0, 1, n)
    y = x + rng.normal(0, 0.2, n)
    values = {f"C{i:03d}": {"x": float(x[i]), "y": float(y[i])} for i in range(n)}
    values["OUT"] = {"x": 12.0, "y": -12.0}
    ds = _dataset(factory, values)
    raw = correlation_pairs(ds, CorrOptions(log=False, min_n=10)).iloc[0]
    clean = correlation_pairs(ds, CorrOptions(log=False, min_n=10, exclude_outliers=True)).iloc[0]
    assert raw["r"] < clean["r"]
    assert clean["n_outliers"] >= 1
    assert clean["n"] < raw["n"]


def test_insufficient_pairs_and_matrix(factory, rng):
    n = 12
    x = rng.normal(size=n)
    y = x + rng.normal(size=n)
    z = -x + rng.normal(size=n)
    values = {f"C{i:02d}": {"x": float(x[i]), "y": float(y[i]), "z": float(z[i])} for i in range(n)}
    ds = _dataset(factory, values)
    pairs = correlation_pairs(ds, CorrOptions(log=False, min_n=30))
    assert pairs["insufficient"].all()
    summary = pairs_summary(pairs, CorrOptions(log=False, min_n=30))
    assert summary["n_tested"] == 0
    matrix = matrix_from_pairs(pairs, ["x", "y", "z"])
    assert matrix.shape == (3, 3)
    assert np.allclose(np.diag(matrix), 1.0)
    assert list(matrix.index) == ["x", "y", "z"]


def test_matrix_symmetry_and_cluster_order(factory, rng):
    n = 40
    a = rng.normal(size=n)
    values = {
        f"C{i:02d}": {
            "a": float(a[i]),
            "b": float(a[i] + rng.normal(0, 0.1)),
            "c": float(-a[i] + rng.normal(0, 5)),
            "d": float(rng.normal()),
        }
        for i in range(n)
    }
    ds = _dataset(factory, values)
    pairs = correlation_pairs(ds, CorrOptions(log=False, min_n=10))
    matrix = matrix_from_pairs(pairs, ["a", "b", "c", "d"])
    assert np.allclose(matrix.to_numpy(), matrix.to_numpy().T)
    order = cluster_order(matrix)
    assert sorted(order) == sorted(["a", "b", "c", "d"])


def test_pair_points_marks_mask(factory):
    values = {"USA": {"x": 1.0, "y": 2.0}, "FRA": {"x": 2.0, "y": 4.0}, "KEN": {"x": np.nan, "y": 6.0}}
    ds = _dataset(factory, values)
    points = pair_points(ds, "x", "y", CorrOptions(log=False))
    assert set(points["country"]) == {"USA", "FRA", "KEN"}
    assert points.set_index("country").loc["KEN", "included"] == False  # noqa: E712
    assert points.set_index("country").loc["USA", "included"] == True  # noqa: E712
