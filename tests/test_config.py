from __future__ import annotations

import pytest

from worlddata.config import load_config
from worlddata.countries import CountryRegistry, norm_name


@pytest.fixture(scope="module")
def config(project_paths):
    return load_config(project_paths)


def test_config_counts(config):
    assert len(config.sources) == 6
    assert len(config.countries) == 219
    assert sum(1 for c in config.countries if c.is_default) == 197
    assert len(config.visible_indicators) == 75
    assert len(config.indicators) == 77  # plus two hidden inputs for derived ratios
    assert len(config.groups) >= 25
    assert len(config.families) == 6


def test_indicator_contract(config):
    ids = [i.id for i in config.indicators]
    assert len(ids) == len(set(ids))
    for indicator in config.indicators:
        assert indicator.source in config.sources
        assert indicator.unit
        if indicator.valid_min is not None and indicator.valid_max is not None:
            assert indicator.valid_min < indicator.valid_max
        if indicator.source == "derived":
            assert indicator.derive is not None
            assert indicator.derive.numerator in ids
            assert indicator.derive.denominator in ids
        if indicator.source != "derived":
            assert indicator.series


def test_groups_have_valid_members(config):
    iso3 = {c.iso3 for c in config.countries}
    for group in config.groups:
        assert set(group.members) <= iso3
        assert group.members or group.selector is not None


def test_group_membership_sizes(config):
    groups = {group.id: group for group in config.groups}
    assert len(groups["eu"].members) == 27
    assert len(groups["eurozone"].members) == 20
    assert len(groups["nato"].members) == 32
    assert "SWE" in groups["nato"].members
    assert len(groups["arab_league"].members) == 22
    assert len(groups["nuclear_powers"].members) == 9
    assert len(groups["asean"].members) == 10
    assert len(groups["mercosur"].members) == 4


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Turkey", "TUR"),
        ("Türkiye", "TUR"),
        ("Côte d'Ivoire", "CIV"),
        ("Cote d Ivoire", "CIV"),
        ("Korea, Rep.", "KOR"),
        ("South Korea", "KOR"),
        ("Korea, Dem. People's Rep.", "PRK"),
        ("Congo, Dem. Rep.", "COD"),
        ("Democratic Republic of the Congo", "COD"),
        ("Congo, Rep.", "COG"),
        ("Congo", "COG"),
        ("Czech Republic", "CZE"),
        ("Swaziland", "SWZ"),
        ("Macedonia", "MKD"),
        ("Holy See", "VAT"),
        ("Palestine", "PSE"),
        ("Kosovo", "XKX"),
        ("United States of America", "USA"),
        ("UK", "GBR"),
        ("UAE", "ARE"),
        ("Burma", "MMR"),
        ("East Timor", "TLS"),
        ("Cape Verde", "CPV"),
        ("Ivory Coast", "CIV"),
        ("São Tomé and Príncipe", "STP"),
        ("Curacao", "CUW"),
        ("Moldova", "MDA"),
        ("Laos", "LAO"),
        ("Viet Nam", "VNM"),
        ("Russia", "RUS"),
    ],
)
def test_alias_resolution(config, value, expected):
    assert CountryRegistry(config).resolve_name(value) == expected


def test_code_resolution(config):
    registry = CountryRegistry(config)
    assert registry.resolve_code("USA") == "USA"
    assert registry.resolve_code("OWID_KOS") == "XKX"
    assert registry.resolve_code("OWID_WRL") is None
    assert registry.resolve("OWID_TWN", "Taiwan") == "TWN"
    assert registry.resolve("", "Not a country") is None


def test_normalization_is_stable():
    assert norm_name("Côte d'Ivoire") == norm_name("Cote d Ivoire")
    assert norm_name("Antigua & Barbuda") == norm_name("Antigua and Barbuda")
    assert norm_name("  United   States  ") == "united states"
