"""Filesystem layout resolution for source runs and frozen (PyInstaller) builds."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates = [exe_dir, exe_dir / "_internal"]
        for candidate in candidates:
            if (candidate / "config").is_dir() and (candidate / "data").is_dir():
                return candidate
        return exe_dir
    return _project_root()


@dataclass(frozen=True)
class Paths:
    base: Path
    config: Path
    data: Path
    raw: Path
    db: Path
    manifest: Path
    quality_report: Path
    rejected: Path
    settings: Path
    groups_local: Path
    cache: Path

    def ensure(self) -> Paths:
        self.data.mkdir(parents=True, exist_ok=True)
        self.raw.mkdir(parents=True, exist_ok=True)
        self.cache.mkdir(parents=True, exist_ok=True)
        return self


def get_paths() -> Paths:
    base = Path(os.environ.get("WORLDDATA_BASE_DIR", _base_dir())).resolve()
    config = Path(os.environ.get("WORLDDATA_CONFIG_DIR", base / "config")).resolve()
    data = Path(os.environ.get("WORLDDATA_DATA_DIR", base / "data")).resolve()
    return Paths(
        base=base,
        config=config,
        data=data,
        raw=data / "raw",
        db=data / "worlddata.sqlite",
        manifest=data / "manifest.json",
        quality_report=data / "quality_report.csv",
        rejected=data / "rejected.csv",
        settings=data / "settings.json",
        groups_local=data / "groups.local.yaml",
        cache=data / "cache",
    )
