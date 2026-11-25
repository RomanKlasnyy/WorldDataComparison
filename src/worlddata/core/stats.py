"""Statistical primitives used by the correlation and group engines."""

from __future__ import annotations

import math

import numpy as np
from scipy import stats

Z_95 = 1.959963984540054


def fisher_ci(r: float, n: int, z: float = Z_95) -> tuple[float, float]:
    if not np.isfinite(r) or n <= 3 or abs(r) >= 1:
        return (math.nan, math.nan)
    zr = math.atanh(r)
    se = 1.0 / math.sqrt(n - 3)
    return (math.tanh(zr - z * se), math.tanh(zr + z * se))


def r_pvalue(r: float, n: int) -> float:
    if not np.isfinite(r) or n < 3:
        return math.nan
    if abs(r) >= 1 - 1e-12:
        return 0.0
    denominator = 1 - r * r
    if denominator <= 0:
        return 0.0
    t = r * math.sqrt((n - 2) / denominator)
    p = float(2 * stats.t.sf(abs(t), n - 2))
    return 0.0 if not math.isfinite(p) else p


def bh_fdr(pvalues: np.ndarray) -> np.ndarray:
    p = np.asarray(pvalues, dtype=float)
    out = np.full(p.shape, np.nan)
    mask = np.isfinite(p)
    if not mask.any():
        return out
    values = p[mask]
    n = values.size
    order = np.argsort(values)
    ranked = values[order]
    q = ranked * n / np.arange(1, n + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    q = np.clip(q, 0, 1)
    restored = np.empty(n)
    restored[order] = q
    out[mask] = restored
    return out


def effect_band(r: float) -> str:
    if not np.isfinite(r):
        return "n/a"
    a = abs(r)
    if a < 0.1:
        return "negligible"
    if a < 0.3:
        return "small"
    if a < 0.5:
        return "moderate"
    return "strong"


def paired_pearson(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    if x.size < 3 or y.size < 3:
        return math.nan, math.nan
    if np.std(x) == 0 or np.std(y) == 0:
        return math.nan, math.nan
    r = float(np.corrcoef(x, y)[0, 1])
    return r, r_pvalue(r, x.size)


def spearman(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    if x.size < 3 or y.size < 3:
        return math.nan, math.nan
    res = stats.spearmanr(x, y)
    return float(res.statistic), float(res.pvalue)


def residualize(target: np.ndarray, controls: np.ndarray) -> np.ndarray:
    design = np.column_stack([np.ones(target.size), controls])
    beta, *_ = np.linalg.lstsq(design, target, rcond=None)
    return target - design @ beta


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    if a.size < 2 or b.size < 2:
        return math.nan
    pooled = math.sqrt(
        ((a.size - 1) * np.var(a, ddof=1) + (b.size - 1) * np.var(b, ddof=1))
        / (a.size + b.size - 2)
    )
    if pooled == 0:
        return math.nan
    return float((np.mean(a) - np.mean(b)) / pooled)


def cliffs_delta(a: np.ndarray, b: np.ndarray) -> float:
    if a.size == 0 or b.size == 0:
        return math.nan
    diff = a[:, None] - b[None, :]
    return float((np.sum(diff > 0) - np.sum(diff < 0)) / diff.size)


def mann_whitney(a: np.ndarray, b: np.ndarray) -> float:
    if a.size < 2 or b.size < 2:
        return math.nan
    try:
        return float(stats.mannwhitneyu(a, b, alternative="two-sided").pvalue)
    except ValueError:
        return math.nan


def kruskal(samples: list[np.ndarray]) -> float:
    clean = [s for s in samples if s.size >= 2]
    if len(clean) < 2:
        return math.nan
    try:
        return float(stats.kruskal(*clean).pvalue)
    except ValueError:
        return math.nan
