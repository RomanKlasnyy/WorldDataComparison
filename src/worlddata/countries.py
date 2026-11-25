"""Canonical country registry and source-name resolution."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

import pandas as pd

from .config import Config, CountryConfig


def norm_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().replace("&", " and ")
    text = text.replace("'", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class CountryRegistry:
    def __init__(self, config: Config):
        self.config = config
        self._by_iso3: dict[str, CountryConfig] = {c.iso3: c for c in config.countries}
        self._alias: dict[str, str] = {}
        self._code_alias: dict[str, str] = {
            k.upper(): v for k, v in config.code_aliases.items()
        }

        for country in config.countries:
            self._alias[norm_name(country.name)] = country.iso3
            if country.official_name:
                self._alias.setdefault(norm_name(country.official_name), country.iso3)
        for alias, iso3 in config.aliases.items():
            if iso3 in self._by_iso3:
                self._alias[norm_name(alias)] = iso3

    # ------------------------------------------------------------------ lookups
    def get(self, iso3: str) -> CountryConfig | None:
        return self._by_iso3.get(str(iso3).upper())

    def resolve_code(self, code: str | None) -> str | None:
        if not code:
            return None
        code = str(code).strip().upper()
        if code in self._by_iso3:
            return code
        return self._code_alias.get(code)

    def resolve_name(self, name: str | None) -> str | None:
        if not name:
            return None
        key = norm_name(name)
        if key in self._alias:
            return self._alias[key]
        # Retry after stripping a trailing parenthetical ("Bolivia (Plurinational State of)").
        stripped = re.sub(r"\([^)]*\)", " ", str(name))
        key = norm_name(stripped)
        return self._alias.get(key)

    def resolve(self, code: str | None, name: str | None = None) -> str | None:
        return self.resolve_code(code) or self.resolve_name(name)

    def name(self, iso3: str) -> str:
        country = self.get(iso3)
        return country.name if country else str(iso3)

    # ------------------------------------------------------------------ frames
    def countries_frame(self, include_territories: bool = False) -> pd.DataFrame:
        rows = [
            c.model_dump()
            for c in self.config.countries
            if include_territories or c.is_default
        ]
        frame = pd.DataFrame(rows)
        return frame.sort_values("name", kind="stable").reset_index(drop=True)

    def codes(self, include_territories: bool = True) -> list[str]:
        return [
            c.iso3 for c in self.config.countries if include_territories or c.is_default
        ]

    def default_codes(self) -> list[str]:
        return [c.iso3 for c in self.config.countries if c.is_default]


@dataclass(frozen=True)
class Resolution:
    iso3: str | None
    matched_by: str


def resolve_row(
    registry: CountryRegistry, code: str | None, name: str | None
) -> Resolution:
    iso3 = registry.resolve_code(code)
    if iso3:
        return Resolution(iso3, "code")
    iso3 = registry.resolve_name(name)
    if iso3:
        return Resolution(iso3, "name")
    return Resolution(None, "unresolved")
