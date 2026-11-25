from __future__ import annotations

import pandas as pd
import pytest

from worlddata.config import (
    Config,
    CountryConfig,
    FamilyConfig,
    GroupConfig,
    IndicatorConfig,
    SourceConfig,
)
from worlddata.countries import CountryRegistry
from worlddata.db import DataError, content_hash, open_repository, verify, write_db
from worlddata.normalize import normalize_frames
from worlddata.paths import Paths
from worlddata.quality import coverage_report, evaluate_gates


def _config() -> Config:
    sources = {
        "worldbank": SourceConfig(id="worldbank", name="World Bank", license="CC BY 4.0"),
        "owid": SourceConfig(id="owid", name="OWID", license="CC BY 4.0"),
        "derived": SourceConfig(id="derived", name="Derived"),
        "manual": SourceConfig(id="manual", name="Manual"),
    }
    indicators = [
        IndicatorConfig(
            id="a",
            name="Indicator A",
            domain="Test",
            unit="index",
            source="worldbank",
            series="A",
            aggregation="median",
            valid_min=0,
            valid_max=100,
        ),
        IndicatorConfig(
            id="b",
            name="Indicator B",
            domain="Test",
            unit="index",
            source="owid",
            series="b",
            value_column="B",
            aggregation="median",
        ),
        IndicatorConfig(
            id="ratio",
            name="Ratio B/A",
            domain="Test",
            unit="ratio",
            source="derived",
            derive={"op": "ratio", "numerator": "b", "denominator": "a", "multiplier": 1.0},
        ),
        IndicatorConfig(
            id="hidden_total",
            name="Hidden total",
            domain="Test",
            unit="people",
            source="worldbank",
            series="H",
            hidden=True,
            aggregation="sum",
        ),
    ]
    countries = [
        CountryConfig(iso3="USA", name="United States", entity_type="state", un_member=True),
        CountryConfig(iso3="FRA", name="France", entity_type="state", un_member=True),
        CountryConfig(iso3="KEN", name="Kenya", entity_type="state", un_member=True),
        CountryConfig(iso3="CIV", name="Côte d'Ivoire", entity_type="state", un_member=True),
        CountryConfig(
            iso3="HKG",
            name="Hong Kong",
            entity_type="territory",
            un_member=False,
            is_default=False,
        ),
    ]
    return Config(
        sources=sources,
        indicators=indicators,
        countries=countries,
        families=[FamilyConfig(id="f", name="Family")],
        groups=[GroupConfig(id="g", name="Group", family="f", members=["USA"])],
        aliases={"Ivory Coast": "CIV"},
        code_aliases={"OWID_KOS": "XKX"},
    )


def _paths(tmp_path) -> Paths:
    data = tmp_path / "data"
    return Paths(
        base=tmp_path,
        config=tmp_path / "config",
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


@pytest.fixture
def build_result(tmp_path):
    config = _config()
    registry = CountryRegistry(config)
    frames = {
        "a": pd.DataFrame(
            {
                "iso3": ["USA", "FRA", "KEN", "HKG", "USA"],
                "year": [2020, 2020, 2020, 2020, 2021],
                "value": [50.0, 150.0, 30.0, 70.0, 60.0],
                "name": ["United States", "France", "Kenya", "Hong Kong", "United States"],
            }
        ),
        "b": pd.DataFrame(
            {
                "code": ["", "", "", "OWID_WRL", ""],
                "name": ["United States", "Côte d'Ivoire", "France", "World", "Atlantis"],
                "year": [2020, 2020, 2020, 2020, 2020],
                "value": [10.0, 20.0, 30.0, 9999.0, 5.0],
            }
        ),
    }
    normalized = normalize_frames(
        config, registry, frames, {"worldbank": "t0", "owid": "t0"}, floor_year=2010, end_year=2027
    )
    groups = pd.DataFrame(
        [{"id": "g", "name": "Group", "family": "f", "description": "", "color": "#123456", "origin": "shipped"}]
    )
    members = pd.DataFrame([{"group_id": "g", "iso3": "USA"}])
    paths = _paths(tmp_path)
    manifest = write_db(
        paths,
        config=config,
        observations=normalized.observations,
        groups=groups,
        group_members=members,
        source_runs={"worldbank": {"files": {}}},
        history_floor_year=2010,
        recency_cutoff_year=2015,
        aliases=normalized.alias_hits,
        build_id="test",
    )
    return config, registry, normalized, paths, manifest


def test_normalization_contract(build_result):
    config, registry, normalized, _paths_obj, _manifest = build_result
    obs = normalized.observations
    assert len(obs) == 8
    assert obs.duplicated(subset=["iso3", "indicator_id", "year"]).sum() == 0
    assert set(obs["indicator_id"]) == {"a", "b", "ratio"}

    rejects = normalized.rejected
    assert len(rejects) == 1
    assert rejects.iloc[0]["iso3"] == "FRA"
    assert "above valid_max" in rejects.iloc[0]["reason"]

    assert len(normalized.unresolved) == 1
    assert normalized.unresolved.iloc[0]["name"] == "Atlantis"
    assert len(normalized.skipped) == 1
    assert normalized.skipped.iloc[0]["name"] == "World"

    aliases = {(name, iso3) for name, source, iso3 in normalized.alias_hits}
    assert ("United States", "USA") in aliases
    assert ("Côte d'Ivoire", "CIV") in aliases


def test_latest_and_derived(build_result):
    _config_obj, _registry, normalized, paths, _manifest = build_result
    latest = normalized.observations[
        (normalized.observations["iso3"] == "USA") & (normalized.observations["indicator_id"] == "a")
    ].set_index("year")["value"]
    assert latest.loc[2020] == 50.0
    assert latest.loc[2021] == 60.0

    ratio = normalized.observations[normalized.observations["indicator_id"] == "ratio"]
    assert list(ratio["iso3"]) == ["USA"]
    assert ratio["year"].iloc[0] == 2020
    assert ratio["value"].iloc[0] == pytest.approx(0.2)
    assert ratio["source_id"].iloc[0] == "derived"


def test_repository_roundtrip(build_result):
    _config_obj, _registry, _normalized, paths, manifest = build_result
    repo = open_repository(paths)
    try:
        countries = repo.countries(include_territories=True)
        assert len(countries) == 5
        assert len(repo.countries()) == 4
        assert repo.indicators(include_hidden=True, with_data=False).shape[0] == 4
        assert repo.observations().shape[0] == 8

        coverage = repo.indicators(include_hidden=False, with_data=True).set_index("id")
        assert coverage.loc["a", "n_countries"] == 2
        assert coverage.loc["a", "pct"] == 50.0
        assert coverage.loc["b", "pct"] == 75.0
        assert coverage.loc["ratio", "pct"] == 25.0

        latest = repo.latest(2015)
        usa_a = latest[(latest["iso3"] == "USA") & (latest["indicator_id"] == "a")]
        assert usa_a["year"].iloc[0] == 2021
        assert usa_a["value"].iloc[0] == 60.0

        assert repo.meta()["schema_version"] == "1"
        assert manifest["db_sha256"]
    finally:
        repo.close()


def test_manifest_verification_detects_corruption(build_result):
    _config_obj, _registry, normalized, paths, _manifest = build_result
    verify(paths)
    with paths.db.open("ab") as handle:
        handle.write(b"corruption")
    with pytest.raises(DataError, match="checksum"):
        verify(paths)


def test_content_hash_is_deterministic(build_result):
    _config_obj, _registry, normalized, paths, manifest = build_result
    first = content_hash(normalized.observations)
    second = content_hash(normalized.observations.sample(frac=1, random_state=1))
    assert first == second == manifest["content_hash"]


def test_quality_report_and_gates(build_result):
    config, registry, normalized, _paths_obj, _manifest = build_result
    report = coverage_report(
        config, normalized.observations, set(registry.default_codes()), cutoff_year=2015
    )
    gates = dict(
        (name, (ok, detail))
        for name, ok, detail in evaluate_gates(
            config,
            report,
            normalized.observations,
            normalized.unresolved,
            min_covered_indicators=1,
            min_pct=50.0,
        )
    )
    assert gates["unique observations"][0] is True
    assert gates["finite values"][0] is True
    assert gates["year sanity"][0] is True
    assert gates["country resolution"][0] is False  # 1 unresolved of 8 rows exceeds 1%


def test_missing_database_raises(tmp_path):
    paths = _paths(tmp_path)
    with pytest.raises(DataError, match="not found"):
        verify(paths)
