"""Build orchestrator: fetch (or reuse snapshots) -> normalize -> DB -> quality report."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pandas as pd

from .config import Config, load_config
from .countries import CountryRegistry
from .db import write_db
from .ingest import imf, manual, owid, worldbank
from .ingest.base import SnapshotStore, make_session
from .normalize import NormalizeResult, normalize_frames
from .paths import Paths
from .quality import coverage_report, evaluate_gates, write_artifacts


class BuildGateError(RuntimeError):
    pass


@dataclass
class BuildResult:
    manifest: dict
    report: pd.DataFrame
    gates: list[tuple[str, bool, str]]
    errors: dict[str, str] = field(default_factory=dict)
    normalized: NormalizeResult | None = None

    @property
    def failed_gates(self) -> list[tuple[str, bool, str]]:
        return [g for g in self.gates if not g[1]]


def _log(message: str, sink) -> None:
    print(message, file=sink)
    sink.flush()


def _retrieved_at(paths: Paths, online: bool) -> dict[str, str]:
    stamps: dict[str, str] = {}
    if paths.raw.exists():
        for source_dir in paths.raw.iterdir():
            if not source_dir.is_dir():
                continue
            dirs = sorted(d.name for d in source_dir.iterdir() if d.is_dir())
            if dirs:
                stamps[source_dir.name] = f"{dirs[-1]}T00:00:00+00:00"
    if online:
        now = datetime.now(UTC).isoformat(timespec="seconds")
        for source in ("worldbank", "worldbank_wgi", "owid", "imf"):
            stamps[source] = now
    return stamps


def resolve_groups(
    config: Config,
    registry: CountryRegistry,
    observations: pd.DataFrame,
    cutoff_year: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    latest = (
        observations[observations["year"] >= cutoff_year]
        .sort_values("year", kind="stable")
        .drop_duplicates(subset=["iso3", "indicator_id"], keep="last")
    )
    values = {
        (str(row.indicator_id), str(row.iso3)): float(row.value)
        for row in latest.itertuples(index=False)
    }
    countries = [c for c in config.countries if c.is_default]

    members: set[tuple[str, str]] = set()
    groups = []
    for group in config.groups:
        selected: set[str] = set()
        if group.selector:
            selector = group.selector
            if selector.field:
                field = selector.field
                expected = (selector.equals or "").casefold()
                for country in countries:
                    actual = str(getattr(country, field, "")).casefold()
                    if actual and actual == expected:
                        selected.add(country.iso3)
            elif selector.indicator:
                for country in countries:
                    value = values.get((selector.indicator, country.iso3))
                    if value is None:
                        continue
                    op = selector.op
                    target = float(selector.value or 0)
                    ok = (
                        (op == "ge" and value >= target)
                        or (op == "gt" and value > target)
                        or (op == "le" and value <= target)
                        or (op == "lt" and value < target)
                        or (op == "eq" and value == target)
                    )
                    if ok:
                        selected.add(country.iso3)
        for code in group.members:
            selected.add(code)
        selected = {c for c in selected if registry.get(c) is not None}
        members.update((group.id, code) for code in selected)
        groups.append(group)

    groups_frame = pd.DataFrame(
        [
            {
                "id": g.id,
                "name": g.name,
                "family": g.family,
                "description": g.description,
                "color": g.color,
                "origin": "shipped",
            }
            for g in groups
        ]
    )
    members_frame = pd.DataFrame(sorted(members), columns=["group_id", "iso3"])
    return groups_frame, members_frame


def build(
    paths: Paths,
    *,
    offline: bool = False,
    force: bool = False,
    only: list[str] | None = None,
    start_year: int = 2010,
    end_year: int | None = None,
    cutoff_year: int = 2015,
    strict: bool = False,
    min_covered_indicators: int = 50,
    min_pct: float = 60.0,
    log_sink=None,
) -> BuildResult:
    sink = log_sink or sys.stdout
    config = load_config(paths)
    registry = CountryRegistry(config)
    paths.ensure()
    end_year = end_year or (datetime.now(UTC).year + 1)
    _log(
        f"WorldDataComparison build: {len(config.countries)} entities, "
        f"{len(config.visible_indicators)} visible indicators, years {start_year}-{end_year}, "
        f"cutoff {cutoff_year}, {'offline' if offline else 'online'}",
        sink,
    )

    store = SnapshotStore(paths, offline=offline, force=force)
    session = None if offline else make_session()
    errors: dict[str, str] = {}

    progress_state = {"n": 0}

    def progress(label: str, ok: bool, detail: str) -> None:
        progress_state["n"] += 1
        if not ok:
            _log(f"  ! [{progress_state['n']}] {label}: {detail}", sink)
        else:
            _log(f"  [{progress_state['n']}] {label}", sink)

    selected = config.indicators
    if only:
        wanted = {s.strip() for s in only}
        selected = [i for i in selected if i.source in wanted or i.id in wanted]

    wb_indicators = [i for i in selected if i.source in {"worldbank", "worldbank_wgi"}]
    owid_indicators = [i for i in selected if i.source == "owid"]
    imf_indicators = [i for i in selected if i.source == "imf"]
    manual_indicators = [i for i in selected if i.source == "manual"]

    frames: dict[str, pd.DataFrame] = {}
    if wb_indicators:
        if session is None:
            _log("World Bank: reading cached snapshots", sink)
        result = worldbank.fetch_all(
            session or make_session(), store, wb_indicators, start_year, end_year, progress=progress
        )
        frames.update(result.frames)
        errors.update(result.errors)
        _log(
            f"World Bank: {len(result.frames)} series loaded, {len(result.errors)} failed",
            sink,
        )
        for indicator_id, message in result.errors.items():
            _log(f"  ! {indicator_id}: {message}", sink)

    if owid_indicators:
        result = owid.fetch_all(
            session or make_session(), store, owid_indicators, start_year, end_year, progress=progress
        )
        frames.update(result.frames)
        errors.update(result.errors)
        _log(
            f"Our World in Data: {len(result.frames)} series loaded, {len(result.errors)} failed",
            sink,
        )
        for indicator_id, message in result.errors.items():
            _log(f"  ! {indicator_id}: {message}", sink)

    if imf_indicators:
        result = imf.fetch_all(
            session or make_session(), store, imf_indicators, start_year, end_year, progress=progress
        )
        frames.update(result.frames)
        errors.update(result.errors)
        _log(f"IMF: {len(result.frames)} series loaded, {len(result.errors)} failed", sink)
        for indicator_id, message in result.errors.items():
            _log(f"  ! {indicator_id}: {message}", sink)

    if manual_indicators:
        manual_frames = manual.load_snapshots(
            store, config, manual_indicators, start_year, end_year
        )
        frames.update(manual_frames)
        _log(f"Manual imports: {len(manual_frames)} of {len(manual_indicators)} available", sink)

    if not frames:
        raise BuildGateError(
            "No series could be loaded. Run without --offline to download the source snapshots."
        )

    normalized = normalize_frames(
        config,
        registry,
        frames,
        _retrieved_at(paths, online=not offline),
        floor_year=start_year,
        end_year=end_year,
    )
    observations = normalized.observations
    if observations.empty:
        raise BuildGateError("Normalization produced no observations")

    groups_frame, members_frame = resolve_groups(config, registry, observations, cutoff_year)

    alias_rows = [
        (alias, source_id, iso3) for alias, source_id, iso3 in normalized.alias_hits
    ]
    manifest = write_db(
        paths,
        config=config,
        observations=observations[["iso3", "indicator_id", "year", "value", "source_id", "retrieved_at"]],
        groups=groups_frame,
        group_members=members_frame,
        source_runs=store.runs,
        history_floor_year=start_year,
        recency_cutoff_year=cutoff_year,
        aliases=alias_rows,
    )

    report = coverage_report(
        config, observations, set(registry.default_codes()), cutoff_year
    )
    write_artifacts(
        paths, report, normalized.rejected, normalized.unresolved, normalized.skipped
    )
    gates = evaluate_gates(
        config,
        report,
        observations,
        normalized.unresolved,
        min_covered_indicators=min_covered_indicators,
        min_pct=min_pct,
    )

    _log(
        f"Wrote {paths.db} ({manifest['db_bytes'] / 1e6:.1f} MB): "
        f"{len(observations):,} observations, {observations['iso3'].nunique()} entities with data",
        sink,
    )
    for name, ok, detail in gates:
        _log(f"  [{'ok' if ok else 'FAIL'}] {name}: {detail}", sink)

    result = BuildResult(
        manifest=manifest,
        report=report,
        gates=gates,
        errors=errors,
        normalized=normalized,
    )
    if strict and result.failed_gates:
        raise BuildGateError(
            "Quality gates failed: " + "; ".join(g[0] for g in result.failed_gates)
        )
    return result
