"""Command-line interface for data refresh, builds, validation and imports."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from .build import BuildGateError, build
from .config import load_config
from .countries import CountryRegistry
from .db import DataError, Repository, open_repository, read_manifest
from .ingest.base import SnapshotStore
from .ingest.manual import import_file
from .paths import get_paths
from .quality import evaluate_gates


def _configure_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _add_build_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--start-year", type=int, default=2010, help="first year to store (default 2010)")
    parser.add_argument("--end-year", type=int, default=None, help="last year to store (default current+1)")
    parser.add_argument("--cutoff", type=int, default=2015, help="recency cutoff for latest-value analysis")
    parser.add_argument("--only", nargs="*", default=None, help="restrict to these source or indicator ids")
    parser.add_argument("--force", action="store_true", help="re-download snapshots even if today's cache exists")
    parser.add_argument("--strict", action="store_true", help="exit non-zero when quality gates fail")
    parser.add_argument("--min-covered", type=int, default=50, help="gate: indicators with >=60%% coverage")
    parser.add_argument("--min-pct", type=float, default=60.0, help="coverage threshold for the gate")


def cmd_refresh(args: argparse.Namespace) -> int:
    paths = get_paths()
    result = build(
        paths,
        offline=False,
        force=args.force,
        only=args.only,
        start_year=args.start_year,
        end_year=args.end_year,
        cutoff_year=args.cutoff,
        strict=args.strict,
        min_covered_indicators=args.min_covered,
        min_pct=args.min_pct,
    )
    print(f"\nBuild complete: {result.manifest['build_id']}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    paths = get_paths()
    result = build(
        paths,
        offline=True,
        only=args.only,
        start_year=args.start_year,
        end_year=args.end_year,
        cutoff_year=args.cutoff,
        strict=args.strict,
        min_covered_indicators=args.min_covered,
        min_pct=args.min_pct,
    )
    print(f"\nOffline rebuild complete: {result.manifest['build_id']}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    paths = get_paths()
    config = load_config(paths)
    repo = open_repository(paths)
    try:
        observations = repo.observations()
        unresolved_path = paths.data / "unresolved.csv"
        unresolved = (
            pd.read_csv(unresolved_path) if unresolved_path.exists() else pd.DataFrame(columns=["n"])
        )
        gates = evaluate_gates(
            config,
            pd.read_csv(paths.quality_report),
            observations,
            unresolved,
            min_covered_indicators=args.min_covered,
            min_pct=args.min_pct,
        )
        for name, ok, detail in gates:
            print(f"[{'ok' if ok else 'FAIL'}] {name}: {detail}")
        failed = [g for g in gates if not g[1] and g[0] != "manual imports"]
        if failed and args.strict:
            return 1
    finally:
        repo.close()
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    paths = get_paths()
    config = load_config(paths)
    registry = CountryRegistry(config)
    store = SnapshotStore(paths, offline=False)
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"File not found: {file_path}", file=sys.stderr)
        return 2
    clean, unresolved, rejected = import_file(store, config, registry, args.indicator, file_path)
    print(
        f"Imported {len(clean)} rows for {args.indicator}; "
        f"{len(unresolved)} unresolved and {len(rejected)} out-of-range rows skipped."
    )
    if not unresolved.empty:
        print("\nUnresolved names:")
        print(unresolved.groupby("name").size().sort_values(ascending=False).head(15).to_string())
    if not rejected.empty:
        print("\nRejected values:")
        print(rejected.head(15).to_string(index=False))
    if args.no_build:
        print("Skipped rebuild (--no-build). The dataset will not include these rows until you rebuild.")
        return 0
    result = build(paths, offline=True, cutoff_year=args.cutoff, strict=args.strict)
    print(f"Rebuilt dataset: {result.manifest['build_id']}")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    paths = get_paths()
    manifest = read_manifest(paths)
    print(f"Database : {paths.db} ({manifest.get('db_bytes', 0) / 1e6:.1f} MB)")
    print(f"Schema   : {manifest.get('schema_version')}   Build: {manifest.get('build_id')}")
    print(f"Built at : {manifest.get('built_at')}")
    print(f"Rows     : {manifest.get('n_observations')}   Countries: {manifest.get('n_countries')}")
    print(f"Cutoff   : {manifest.get('recency_cutoff_year')}   History floor: {manifest.get('history_floor_year')}")
    repo = Repository(paths.db, manifest)
    try:
        print("\nIndicators with data:")
        print(repo.indicators().to_string(index=False, max_colwidth=40))
    finally:
        repo.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="worlddata", description="WorldDataComparison data pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    p_refresh = sub.add_parser("refresh", help="download snapshots and rebuild the database")
    _add_build_args(p_refresh)
    p_refresh.set_defaults(func=cmd_refresh)

    p_build = sub.add_parser("build", help="rebuild the database from cached snapshots (no network)")
    _add_build_args(p_build)
    p_build.set_defaults(func=cmd_build)

    p_validate = sub.add_parser("validate", help="verify the database and print quality gates")
    p_validate.add_argument("--strict", action="store_true")
    p_validate.add_argument("--min-covered", type=int, default=50)
    p_validate.add_argument("--min-pct", type=float, default=60.0)
    p_validate.set_defaults(func=cmd_validate)

    p_import = sub.add_parser("import-manual", help="import a CSV/XLSX for a manual indicator")
    p_import.add_argument("--indicator", required=True, help="indicator id from config/indicators.yaml")
    p_import.add_argument("--file", required=True, help="CSV or XLSX with country, year, value columns")
    p_import.add_argument("--cutoff", type=int, default=2015)
    p_import.add_argument("--strict", action="store_true")
    p_import.add_argument("--no-build", action="store_true")
    p_import.set_defaults(func=cmd_import)

    p_info = sub.add_parser("info", help="show manifest and indicator coverage")
    p_info.set_defaults(func=cmd_info)
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_stdout()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (BuildGateError, DataError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
