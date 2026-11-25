from __future__ import annotations

import pandas as pd
import pytest

from worlddata.config import load_config
from worlddata.countries import CountryRegistry
from worlddata.ingest.base import SnapshotStore
from worlddata.ingest.manual import canonicalize_import, import_file
from worlddata.paths import Paths


@pytest.fixture(scope="module")
def config(project_paths):
    return load_config(project_paths)


def test_canonicalize_import(config):
    registry = CountryRegistry(config)
    indicator = config.indicator("pisa_math")
    frame = pd.DataFrame(
        {
            "country": ["United States", "Côte d'Ivoire", "Atlantis", "France", "  "],
            "year": [2022, 2022, 2022, 2022, 2022],
            "value": [480.0, 300.0, 500.0, 1500.0, 400.0],
        }
    )
    clean, unresolved, rejected = canonicalize_import(frame, indicator, registry)
    assert set(clean["code"]) == {"USA", "CIV"}
    assert set(unresolved["name"]) == {"Atlantis", "  "}
    assert len(rejected) == 1
    assert rejected.iloc[0]["iso3"] == "FRA"
    assert "above valid_max" in rejected.iloc[0]["reason"]


def test_import_file_writes_snapshot(tmp_path, config):
    registry = CountryRegistry(config)
    data = tmp_path / "data"
    paths = Paths(
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
    paths.ensure()
    csv_path = tmp_path / "pisa.csv"
    pd.DataFrame(
        {"country": ["United States", "France"], "year": [2022, 2022], "value": [480, 490]}
    ).to_csv(csv_path, index=False)

    store = SnapshotStore(paths)
    clean, unresolved, rejected = import_file(store, config, registry, "pisa_math", csv_path)
    assert len(clean) == 2
    assert unresolved.empty
    assert rejected.empty
    snapshots = list((paths.raw / "manual").rglob("pisa_math.csv"))
    assert len(snapshots) == 1
    assert "USA" in snapshots[0].read_text(encoding="utf-8")


def test_import_rejects_unknown_indicator(tmp_path, config):
    store = SnapshotStore(
        Paths(
            base=tmp_path,
            config=tmp_path,
            data=tmp_path / "data",
            raw=tmp_path / "data" / "raw",
            db=tmp_path / "data" / "db.sqlite",
            manifest=tmp_path / "data" / "manifest.json",
            quality_report=tmp_path / "data" / "q.csv",
            rejected=tmp_path / "data" / "r.csv",
            settings=tmp_path / "data" / "s.json",
            groups_local=tmp_path / "data" / "g.yaml",
            cache=tmp_path / "data" / "cache",
        )
    )
    store.paths.ensure()
    csv_path = tmp_path / "x.csv"
    csv_path.write_text("country,year,value\nUSA,2022,1\n", encoding="utf-8")
    with pytest.raises(Exception, match="unknown indicator"):
        import_file(store, config, CountryRegistry(config), "does_not_exist", csv_path)
