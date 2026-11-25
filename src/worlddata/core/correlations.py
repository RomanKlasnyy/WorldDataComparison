"""Pairwise correlation engine with log, outlier, same-year and partial variants."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import leaves_list, linkage
from scipy.spatial.distance import squareform

from .dataset import Dataset
from .stats import (
    bh_fdr,
    fisher_ci,
    paired_pearson,
    residualize,
    spearman,
)


@dataclass(frozen=True)
class CorrOptions:
    log: bool = True
    same_year: bool = False
    exclude_outliers: bool = False
    min_n: int = 30
    control: str | None = None

    @property
    def key(self) -> tuple:
        return (self.log, self.same_year, self.exclude_outliers, self.min_n, self.control)


def prepare(dataset: Dataset, options: CorrOptions) -> tuple[np.ndarray, np.ndarray]:
    ids = dataset.indicator_ids
    values = dataset.values.to_numpy(dtype=float, copy=True)
    years = dataset.years.to_numpy(dtype=float, copy=True)
    if options.log:
        for j, indicator_id in enumerate(ids):
            if bool(dataset.indicators.loc[indicator_id, "default_log"]):
                column = values[:, j]
                with np.errstate(invalid="ignore", divide="ignore"):
                    values[:, j] = np.where(column > 0, np.log10(column), np.nan)
    return values, years


def correlation_pairs(
    dataset: Dataset,
    options: CorrOptions,
    indicator_ids: list[str] | None = None,
) -> pd.DataFrame:
    pair_ids = [
        i for i in (indicator_ids or dataset.indicator_ids) if i in dataset.values.columns
    ]
    if len(pair_ids) < 2:
        return _empty_pairs()
    work_ids = list(pair_ids)
    if options.control and options.control in dataset.values.columns and options.control not in work_ids:
        work_ids.append(options.control)
    sub = dataset.subset_indicators(work_ids)
    values, years = prepare(sub, options)
    control_index = work_ids.index(options.control) if options.control in work_ids else None
    index_of = {indicator_id: work_ids.index(indicator_id) for indicator_id in pair_ids}
    names = {i: sub.indicator_name(i) for i in work_ids}
    domains = {i: str(sub.indicators.loc[i, "domain"]) for i in work_ids}

    records: list[dict] = []
    for i in range(len(pair_ids)):
        xi = values[:, index_of[pair_ids[i]]]
        yi = years[:, index_of[pair_ids[i]]]
        for j in range(i + 1, len(pair_ids)):
            xj = values[:, index_of[pair_ids[j]]]
            yj = years[:, index_of[pair_ids[j]]]
            mask = np.isfinite(xi) & np.isfinite(xj)
            if options.same_year:
                mask &= yi == yj
            if control_index is not None:
                mask &= np.isfinite(values[:, control_index])
            n = int(mask.sum())
            n_outliers = 0

            if options.exclude_outliers and n >= 3:
                selected = np.flatnonzero(mask)
                keep = np.ones(selected.size, dtype=bool)
                for column in (xi, xj):
                    sample = column[selected]
                    sd = np.std(sample)
                    if sd > 0:
                        keep &= np.abs((sample - np.mean(sample)) / sd) <= 3
                n_outliers = int((~keep).sum())
                mask = np.zeros(len(yi), dtype=bool)
                mask[selected[keep]] = True
                n = int(mask.sum())

            row = {
                "a": pair_ids[i],
                "b": pair_ids[j],
                "a_name": names[pair_ids[i]],
                "b_name": names[pair_ids[j]],
                "a_domain": domains[pair_ids[i]],
                "b_domain": domains[pair_ids[j]],
                "n": n,
                "n_outliers": n_outliers,
                "insufficient": n < options.min_n,
                "r": np.nan,
                "p": np.nan,
                "ci_low": np.nan,
                "ci_high": np.nan,
                "rho": np.nan,
                "rho_p": np.nan,
                "partial_r": np.nan,
                "partial_p": np.nan,
                "year_gap_median": np.nan,
            }
            if n >= 3:
                xs = xi[mask]
                ys = xj[mask]
                r, p = paired_pearson(xs, ys)
                rho, rho_p = spearman(xs, ys)
                lo, hi = fisher_ci(r, n)
                row.update({"r": r, "p": p, "rho": rho, "rho_p": rho_p, "ci_low": lo, "ci_high": hi})
                row["year_gap_median"] = float(np.median(np.abs(yi[mask] - yj[mask])))
                if control_index is not None and options.control not in (pair_ids[i], pair_ids[j]):
                    controls = values[mask, control_index]
                    rx = residualize(xs, controls)
                    ry = residualize(ys, controls)
                    pr, pp = paired_pearson(rx, ry)
                    row["partial_r"] = pr
                    row["partial_p"] = pp
            records.append(row)

    frame = pd.DataFrame(records)
    if frame.empty:
        return _empty_pairs()
    frame["q"] = bh_fdr(frame["p"].to_numpy(dtype=float))
    frame["abs_r"] = frame["r"].abs()
    frame["effect"] = frame["r"].map(_band)
    return frame


def _band(r: float) -> str:
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


def _empty_pairs() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "a", "b", "a_name", "b_name", "a_domain", "b_domain", "n", "n_outliers",
            "insufficient", "r", "p", "ci_low", "ci_high", "rho", "rho_p", "partial_r",
            "partial_p", "year_gap_median", "q", "abs_r", "effect",
        ]
    )


def matrix_from_pairs(pairs: pd.DataFrame, ids: list[str], value: str = "r") -> pd.DataFrame:
    data = np.full((len(ids), len(ids)), np.nan, dtype=float)
    np.fill_diagonal(data, 1.0)
    matrix = pd.DataFrame(data, index=ids, columns=ids)
    for row in pairs.itertuples(index=False):
        if row.a not in matrix.index or row.b not in matrix.index:
            continue
        v = getattr(row, value)
        if v is None or (isinstance(v, float) and not np.isfinite(v)):
            continue
        matrix.loc[row.a, row.b] = v
        matrix.loc[row.b, row.a] = v
    return matrix


def cluster_order(matrix: pd.DataFrame) -> list[str]:
    ids = list(matrix.index)
    if len(ids) < 3:
        return ids
    data = matrix.to_numpy(dtype=float)
    distance = 1.0 - np.abs(np.nan_to_num(data, nan=0.0))
    np.fill_diagonal(distance, 0.0)
    distance = (distance + distance.T) / 2
    try:
        condensed = squareform(distance, checks=False)
        tree = linkage(condensed, method="average")
        order = leaves_list(tree)
        return [ids[i] for i in order]
    except Exception:  # noqa: BLE001 - ordering is cosmetic
        return ids


def pair_points(
    dataset: Dataset,
    a: str,
    b: str,
    options: CorrOptions,
) -> pd.DataFrame:
    ids = [i for i in (a, b) if i in dataset.values.columns]
    if len(ids) < 2:
        return pd.DataFrame()
    sub = dataset.subset_indicators(ids)
    values, years = prepare(sub, options)
    control = None
    if options.control and options.control in dataset.values.columns:
        control = prepare(dataset.subset_indicators([options.control]), CorrOptions(log=options.log))[0][:, 0]

    xi, xj = values[:, 0], values[:, 1]
    yi, yj = years[:, 0], years[:, 1]
    mask = np.isfinite(xi) & np.isfinite(xj)
    if options.same_year:
        mask &= yi == yj
    if control is not None:
        mask &= np.isfinite(control)

    raw_a = dataset.values[a].to_numpy(dtype=float)
    raw_b = dataset.values[b].to_numpy(dtype=float)
    frame = pd.DataFrame(
        {
            "iso3": sub.values.index,
            "country": [sub.name(c) for c in sub.values.index],
            "x": xi,
            "y": xj,
            "x_raw": raw_a,
            "y_raw": raw_b,
            "year_a": yi,
            "year_b": yj,
            "included": mask,
        }
    )
    if control is not None:
        frame["control"] = control
    if options.exclude_outliers:
        included = frame["included"].to_numpy()
        keep = np.ones(len(frame), dtype=bool)
        for column in ("x", "y"):
            sample = frame[column].to_numpy(dtype=float)
            valid = included & np.isfinite(sample)
            if valid.sum() >= 3 and np.std(sample[valid]) > 0:
                z = np.abs((sample - np.mean(sample[valid])) / np.std(sample[valid]))
                keep &= ~(valid & (z > 3))
        frame["included"] = included & keep
    return frame


def pairs_summary(pairs: pd.DataFrame, options: CorrOptions) -> dict:
    valid = pairs[~pairs["insufficient"] & np.isfinite(pairs["r"])]
    return {
        "n_pairs": int(len(pairs)),
        "n_tested": int(len(valid)),
        "n_insufficient": int(pairs["insufficient"].sum()),
        "median_n": float(valid["n"].median()) if not valid.empty else 0.0,
        "significant": int((valid["q"] < 0.05).sum()) if not valid.empty else 0,
        "strong": int((valid["abs_r"] >= 0.5).sum()) if not valid.empty else 0,
        "options": options,
    }
