"""Typed configuration contracts loaded from the YAML files in config/."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from .paths import Paths


class SourceConfig(BaseModel):
    id: str
    name: str
    homepage: str = ""
    license: str = ""
    attribution: str = ""
    redistributable: bool = True


class DeriveSpec(BaseModel):
    op: Literal["ratio"] = "ratio"
    numerator: str
    denominator: str
    multiplier: float = 1.0


class IndicatorConfig(BaseModel):
    id: str
    name: str
    domain: str
    description: str = ""
    unit: str
    source: str
    series: str = ""
    value_column: str | None = None
    higher_is_better: bool | None = None
    default_log: bool = False
    is_composite: bool = False
    hidden: bool = False
    aggregation: Literal["median", "mean", "sum", "weighted"] = "median"
    valid_min: float | None = None
    valid_max: float | None = None
    attribution: str = ""
    min_year: int | None = None
    derive: DeriveSpec | None = None

    @model_validator(mode="after")
    def _derive_consistency(self) -> IndicatorConfig:
        if not self.series:
            self.series = self.id
        if self.source == "derived" and self.derive is None:
            raise ValueError(f"indicator {self.id}: source=derived requires a derive block")
        if self.source != "derived" and self.derive is not None:
            raise ValueError(f"indicator {self.id}: derive block only allowed for source=derived")
        return self


class CountryConfig(BaseModel):
    iso3: str = Field(min_length=3, max_length=3)
    name: str
    official_name: str = ""
    entity_type: Literal["state", "territory", "observer", "disputed"] = "state"
    un_member: bool = False
    region: str = ""
    subregion: str = ""
    continent: str = ""
    income_group: str = ""
    is_default: bool = True

    @property
    def is_country(self) -> bool:
        return self.is_default


class Selector(BaseModel):
    field: str | None = None
    equals: str | None = None
    indicator: str | None = None
    op: Literal["ge", "gt", "le", "lt", "eq"] | None = None
    value: float | None = None

    @model_validator(mode="after")
    def _one_kind(self) -> Selector:
        if bool(self.field) == bool(self.indicator):
            raise ValueError("selector must have exactly one of `field` or `indicator`")
        if self.field and self.equals is None:
            raise ValueError("field selector requires `equals`")
        if self.indicator and (self.op is None or self.value is None):
            raise ValueError("indicator selector requires `op` and `value`")
        return self


class GroupConfig(BaseModel):
    id: str
    name: str
    family: str
    description: str = ""
    color: str = "#4C78A8"
    members: list[str] = Field(default_factory=list)
    selector: Selector | None = None


class FamilyConfig(BaseModel):
    id: str
    name: str


class Config(BaseModel):
    sources: dict[str, SourceConfig]
    indicators: list[IndicatorConfig]
    countries: list[CountryConfig]
    families: list[FamilyConfig]
    groups: list[GroupConfig]
    code_aliases: dict[str, str] = Field(default_factory=dict)
    aliases: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _cross_validate(self) -> Config:
        errors: list[str] = []
        iso3 = {c.iso3 for c in self.countries}
        if len(iso3) != len(self.countries):
            errors.append("duplicate ISO3 codes in countries.yaml")
        ind_ids = [i.id for i in self.indicators]
        if len(set(ind_ids)) != len(ind_ids):
            errors.append("duplicate indicator ids")
        group_ids = [g.id for g in self.groups]
        if len(set(group_ids)) != len(group_ids):
            errors.append("duplicate group ids")
        for ind in self.indicators:
            if ind.source not in self.sources:
                errors.append(f"indicator {ind.id}: unknown source {ind.source}")
            if ind.valid_min is not None and ind.valid_max is not None and ind.valid_min >= ind.valid_max:
                errors.append(f"indicator {ind.id}: valid_min >= valid_max")
            if ind.derive:
                for ref in (ind.derive.numerator, ind.derive.denominator):
                    if ref not in ind_ids:
                        errors.append(f"indicator {ind.id}: derive references unknown indicator {ref}")
        families = {f.id for f in self.families}
        for group in self.groups:
            if group.family not in families:
                errors.append(f"group {group.id}: unknown family {group.family}")
            for m in group.members:
                if m not in iso3:
                    errors.append(f"group {group.id}: unknown member {m}")
            if not group.members and group.selector is None:
                errors.append(f"group {group.id}: no members and no selector")
        for alias, target in self.aliases.items():
            if target not in iso3:
                errors.append(f"alias {alias!r} points to unknown ISO3 {target}")
        if errors:
            raise ValueError("configuration errors:\n  " + "\n  ".join(errors))
        return self

    @property
    def indicator_map(self) -> dict[str, IndicatorConfig]:
        return {i.id: i for i in self.indicators}

    @property
    def visible_indicators(self) -> list[IndicatorConfig]:
        return [i for i in self.indicators if not i.hidden]

    @property
    def domain_order(self) -> list[str]:
        seen: list[str] = []
        for ind in self.indicators:
            if ind.domain not in seen:
                seen.append(ind.domain)
        return seen

    def indicator(self, indicator_id: str) -> IndicatorConfig:
        return self.indicator_map[indicator_id]


def _read_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def load_config(paths: Paths) -> Config:
    cfg_dir = paths.config
    sources_raw = _read_yaml(cfg_dir / "sources.yaml")["sources"]
    indicators_raw = _read_yaml(cfg_dir / "indicators.yaml")["indicators"]
    countries_raw = _read_yaml(cfg_dir / "countries.yaml")["countries"]
    groups_raw = _read_yaml(cfg_dir / "groups.yaml")
    aliases_raw = _read_yaml(cfg_dir / "aliases.yaml")

    flat_aliases: dict[str, str] = {}
    for iso3, names in (aliases_raw.get("aliases") or {}).items():
        for name in names or []:
            flat_aliases[str(name)] = iso3

    return Config(
        sources={s["id"]: SourceConfig(**s) for s in sources_raw},
        indicators=[IndicatorConfig(**i) for i in indicators_raw],
        countries=[CountryConfig(**c) for c in countries_raw],
        families=[FamilyConfig(**f) for f in groups_raw["families"]],
        groups=[GroupConfig(**g) for g in groups_raw["groups"]],
        code_aliases={str(k): str(v) for k, v in (aliases_raw.get("code_aliases") or {}).items()},
        aliases=flat_aliases,
    )
