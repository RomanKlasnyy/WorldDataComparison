from __future__ import annotations

import numpy as np
import pytest
from scipy import stats

from worlddata.core.stats import (
    bh_fdr,
    cliffs_delta,
    cohens_d,
    effect_band,
    fisher_ci,
    mann_whitney,
    paired_pearson,
    r_pvalue,
    residualize,
)


def test_fisher_ci_matches_reference():
    low, high = fisher_ci(0.5, 100)
    se = 1 / np.sqrt(97)
    assert low == pytest.approx(np.tanh(np.arctanh(0.5) - 1.959963984540054 * se))
    assert high == pytest.approx(np.tanh(np.arctanh(0.5) + 1.959963984540054 * se))
    assert np.isnan(fisher_ci(float("nan"), 100)[0])
    assert np.isnan(fisher_ci(0.5, 3)[0])


def test_r_pvalue_matches_scipy():
    rng = np.random.default_rng(1)
    x = rng.normal(size=50)
    y = 0.4 * x + rng.normal(size=50)
    r = np.corrcoef(x, y)[0, 1]
    expected = stats.pearsonr(x, y).pvalue
    assert r_pvalue(float(r), 50) == pytest.approx(expected, rel=1e-9)


def test_bh_fdr_reference():
    p = np.array([0.01, 0.04, 0.03, 0.002])
    q = bh_fdr(p)
    assert q == pytest.approx([0.02, 0.04, 0.04, 0.008])
    assert np.isnan(bh_fdr(np.array([np.nan, 0.01]))[0])


def test_effect_bands():
    assert effect_band(0.05) == "negligible"
    assert effect_band(0.2) == "small"
    assert effect_band(-0.4) == "moderate"
    assert effect_band(0.7) == "strong"
    assert effect_band(float("nan")) == "n/a"


def test_pearson_guards():
    r, p = paired_pearson(np.array([1.0, 2.0, 3.0]), np.array([2.0, 4.0, 6.0]))
    assert r == pytest.approx(1.0)
    assert p == pytest.approx(0.0)
    assert np.isnan(paired_pearson(np.array([1.0, 1.0, 1.0]), np.array([2.0, 3.0, 4.0]))[0])
    assert np.isnan(paired_pearson(np.array([1.0, 2.0]), np.array([1.0, 2.0]))[0])


def test_residualize_removes_linear_signal(rng):
    control = rng.normal(size=200)
    target = 3.0 * control + rng.normal(scale=0.1, size=200)
    residuals = residualize(target, control)
    assert abs(np.corrcoef(residuals, control)[0, 1]) < 1e-8
    assert abs(residuals.mean()) < 1e-9


def test_group_effect_sizes():
    a = np.array([10.0, 11.0, 12.0, 13.0])
    b = np.array([1.0, 2.0, 3.0, 4.0])
    assert cliffs_delta(a, b) == pytest.approx(1.0)
    assert cliffs_delta(b, a) == pytest.approx(-1.0)
    assert cohens_d(a, b) > 2.0
    assert 0.0 <= mann_whitney(a, b) <= 1.0
