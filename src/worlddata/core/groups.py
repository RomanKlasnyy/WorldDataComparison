"""Country-group resolution, aggregation and statistical comparison."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from ..db import Repository
from .dataset import Dataset
from .stats import bh_fdr, cliffs_delta, cohens_d, kruskal, mann_whitney


@dataclass
class GroupSet:
    groups: pd.DataFrame
    members: dict[str, list[str]]
    overlay: dict = field(default_factory=dict)

    def ids(self) -> list[str]:
        return list(self.groups["id"])

    def name(self, group_id: str) -> str:
        row = self.groups[self.groups["id"] == group_id]
        return str(row["name"].iloc[0]) if not row.empty else group_id

    def members_of(self, group_id: str) -> list[str]:
        return list(self.members.get(group_id, []))


def load_group_set(repo: Repository, overlay_path: Path | None = None) -> GroupSet:
    groups = repo.groups()
    member_frame = repo.group_members()
    valid = set(repo.countries(include_territories=True)["iso3"])
    members: dict[str, list[str]] = {
        group_id: sorted(set(group["iso3"].tolist()) & valid)
        for group_id, group in member_frame.groupby("group_id")
    }
    overlay = {}
    if overlay_path and overlay_path.exists():
        try:
            raw = yaml.safe_load(overlay_path.read_text(encoding="utf-8")) or {}
            for group_id, changes in raw.items():
                if group_id not in set(groups["id"]) or not isinstance(changes, dict):
                    continue
                if "members" in changes:
                    current = {str(code) for code in (changes.get("members") or [])} & valid
                else:
                    current = set(members.get(group_id, []))
                    for code in changes.get("add", []) or []:
                        current.add(str(code))
                    for code in changes.get("remove", []) or []:
                        current.discard(str(code))
                    current &= valid
                members[group_id] = sorted(current)
                overlay[group_id] = changes
        except (yaml.YAMLError, AttributeError):
            overlay = {}

    groups = groups.copy()
    groups["n_members"] = groups["id"].map(lambda g: len(members.get(g, [])))
    return GroupSet(groups=groups, members=members, overlay=overlay)


def save_group_members(path: Path, group_id: str, members: list[str]) -> None:
    data = {}
    if path.exists():
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            data = {}
    data[group_id] = {"members": sorted(set(members))}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=True), encoding="utf-8")


def save_overlay(path: Path, group_id: str, add: list[str], remove: list[str]) -> None:
    data = {}
    if path.exists():
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            data = {}
    entry = data.get(group_id, {}) or {}
    entry["add"] = sorted(set(entry.get("add", []) or []) | set(add))
    entry["remove"] = sorted(set(entry.get("remove", []) or []) | set(remove))
    if not entry["add"]:
        entry.pop("add")
    if not entry["remove"]:
        entry.pop("remove")
    if entry:
        data[group_id] = entry
    else:
        data.pop(group_id, None)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=True), encoding="utf-8")


def reset_overlay(path: Path) -> None:
    if path.exists():
        path.unlink()


def aggregate(values: np.ndarray, mode: str, weights: np.ndarray | None = None) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return float("nan")
    if mode == "sum":
        return float(np.sum(values))
    if mode == "mean":
        return float(np.mean(values))
    if mode == "weighted" and weights is not None and values.size == weights.size:
        weights = np.asarray(weights, dtype=float)
        valid = np.isfinite(weights) & (weights > 0)
        if valid.sum() >= 2:
            return float(np.average(values[valid], weights=weights[valid]))
        return float(np.mean(values))
    return float(np.median(values))


@dataclass
class GroupSummary:
    table: pd.DataFrame
    notes: list[str] = field(default_factory=list)


def summarize(
    dataset: Dataset,
    group_set: GroupSet,
    indicator_id: str,
    group_ids: list[str] | None = None,
) -> GroupSummary:
    if indicator_id not in dataset.values.columns:
        return GroupSummary(pd.DataFrame(), [f"indicator {indicator_id} is not loaded"])
    meta = dataset.indicators.loc[indicator_id]
    mode = str(meta["aggregation"])
    hib = meta["higher_is_better"]
    direction = None if pd.isna(hib) else bool(hib)
    population = (
        dataset.values["population"]
        if "population" in dataset.values.columns
        else pd.Series(np.nan, index=dataset.values.index)
    )
    notes: list[str] = []
    if mode == "weighted" and "population" not in dataset.values.columns:
        notes.append("Population weights are not loaded; weighted aggregation falls back to the unweighted mean.")
    elif mode == "weighted":
        notes.append("Group values are population-weighted means.")

    selected = group_ids or group_set.ids()
    rows = []
    for group_id in selected:
        group_row = group_set.groups[group_set.groups["id"] == group_id]
        if group_row.empty:
            continue
        members = [m for m in group_set.members_of(group_id) if m in dataset.values.index]
        values = dataset.values.loc[members, indicator_id].dropna()
        years = dataset.years.loc[values.index, indicator_id].dropna()
        weights = population.reindex(values.index).to_numpy(dtype=float)
        aggregated = aggregate(values.to_numpy(dtype=float), mode, weights)
        ordered = values.sort_values(ascending=False)
        best = None
        worst = None
        if not ordered.empty:
            if direction is False:
                best, worst = ordered.index[-1], ordered.index[0]
            else:
                best, worst = ordered.index[0], ordered.index[-1]
        rows.append(
            {
                "group_id": group_id,
                "group": group_row["name"].iloc[0],
                "family": group_row["family"].iloc[0],
                "color": group_row["color"].iloc[0],
                "n_members": len(group_set.members_of(group_id)),
                "n_data": int(values.size),
                "coverage_pct": round(values.size / max(len(group_set.members_of(group_id)), 1) * 100, 1),
                "aggregate": aggregated,
                "mean": float(values.mean()) if values.size else np.nan,
                "median": float(values.median()) if values.size else np.nan,
                "sd": float(values.std(ddof=1)) if values.size > 1 else np.nan,
                "q1": float(values.quantile(0.25)) if values.size else np.nan,
                "q3": float(values.quantile(0.75)) if values.size else np.nan,
                "min": float(values.min()) if values.size else np.nan,
                "max": float(values.max()) if values.size else np.nan,
                "latest_year": int(years.max()) if not years.empty else None,
                "best_country": dataset.name(best) if best else "",
                "worst_country": dataset.name(worst) if worst else "",
            }
        )
    table = pd.DataFrame(rows)
    if not table.empty:
        table = table.sort_values("aggregate", ascending=direction is not True, na_position="last")
    return GroupSummary(table=table, notes=notes)


@dataclass
class GroupComparison:
    summary: pd.DataFrame
    pairwise: pd.DataFrame
    kruskal_p: float
    vs_rest: pd.DataFrame
    notes: list[str] = field(default_factory=list)


def compare(
    dataset: Dataset,
    group_set: GroupSet,
    indicator_id: str,
    group_ids: list[str],
) -> GroupComparison:
    summary = summarize(dataset, group_set, indicator_id, group_ids)
    samples: dict[str, np.ndarray] = {}
    for group_id in group_ids:
        members = [m for m in group_set.members_of(group_id) if m in dataset.values.index]
        values = dataset.values.loc[members, indicator_id].dropna().to_numpy(dtype=float)
        if values.size:
            samples[group_id] = values

    pair_rows = []
    ids = list(samples)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = samples[ids[i]], samples[ids[j]]
            if a.size < 2 or b.size < 2:
                continue
            pair_rows.append(
                {
                    "group_a": group_set.name(ids[i]),
                    "group_b": group_set.name(ids[j]),
                    "n_a": int(a.size),
                    "n_b": int(b.size),
                    "median_a": float(np.median(a)),
                    "median_b": float(np.median(b)),
                    "p": mann_whitney(a, b),
                    "cliffs_delta": cliffs_delta(a, b),
                    "cohens_d": cohens_d(a, b),
                }
            )
    pairwise = pd.DataFrame(pair_rows)
    if not pairwise.empty:
        pairwise["q"] = bh_fdr(pairwise["p"].to_numpy(dtype=float))

    all_members: set[str] = set()
    for group_id in group_ids:
        all_members.update(group_set.members_of(group_id))
    rest_values = dataset.values.drop(index=[m for m in all_members if m in dataset.values.index])[
        indicator_id
    ].dropna()

    rest_rows = []
    for group_id, values in samples.items():
        rest = rest_values.to_numpy(dtype=float)
        if rest.size < 2:
            continue
        rest_rows.append(
            {
                "group_id": group_id,
                "group": group_set.name(group_id),
                "n_group": int(values.size),
                "n_rest": int(rest.size),
                "median_group": float(np.median(values)),
                "median_rest": float(np.median(rest)),
                "p": mann_whitney(values, rest),
                "cliffs_delta": cliffs_delta(values, rest),
                "cohens_d": cohens_d(values, rest),
            }
        )
    vs_rest = pd.DataFrame(rest_rows)
    if not vs_rest.empty:
        vs_rest["q"] = bh_fdr(vs_rest["p"].to_numpy(dtype=float))

    return GroupComparison(
        summary=summary.table,
        pairwise=pairwise,
        kruskal_p=kruskal(list(samples.values())),
        vs_rest=vs_rest,
        notes=summary.notes,
    )


def member_table(
    dataset: Dataset, group_set: GroupSet, group_id: str, indicator_id: str
) -> pd.DataFrame:
    members = [m for m in group_set.members_of(group_id) if m in dataset.values.index]
    values = dataset.values.loc[members, indicator_id]
    years = dataset.years.loc[members, indicator_id]
    frame = pd.DataFrame(
        {
            "iso3": members,
            "country": [dataset.name(m) for m in members],
            "value": values.to_numpy(dtype=float),
            "year": years.to_numpy(),
        }
    )
    return frame.dropna(subset=["value"]).sort_values("value", ascending=False)
