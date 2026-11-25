"""Persisted UI settings (portable, with a %APPDATA% fallback)."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path


@dataclass
class Settings:
    cutoff_year: int = 2015
    include_territories: bool = False
    theme: str = "dark"
    min_n: int = 30
    log_transform: bool = True
    same_year: bool = False
    exclude_outliers: bool = False
    control: str | None = "gdp_per_capita_ppp"
    last_indicator: str = "gdp_per_capita_ppp"
    last_country: str = "USA"
    compare_countries: list[str] = field(
        default_factory=lambda: ["USA", "CHN", "DEU", "BRA"]
    )
    last_page: str = "dashboard"
    group_ids: list[str] = field(default_factory=lambda: ["eu", "nato", "asean", "mercosur"])
    group_indicator: str = "gdp_per_capita_ppp"
    correlation_limit: int = 15

    @classmethod
    def load(cls, path: Path) -> Settings:
        for candidate in (path, _fallback_path()):
            if candidate and candidate.exists():
                try:
                    raw = json.loads(candidate.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                known = {f.name for f in fields(cls)}
                return cls(**{k: v for k, v in raw.items() if k in known})
        return cls()

    def save(self, path: Path) -> None:
        target = path
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(".tmp")
            tmp.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
            tmp.replace(target)
        except OSError:
            fallback = _fallback_path()
            fallback.parent.mkdir(parents=True, exist_ok=True)
            fallback.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


def _fallback_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "WorldDataComparison" / "settings.json"
