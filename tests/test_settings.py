from __future__ import annotations

from worlddata.ui.settings import Settings


def test_settings_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    settings = Settings(cutoff_year=2020, theme="light", min_n=40, compare_countries=["FRA", "DEU"])
    settings.save(path)
    loaded = Settings.load(path)
    assert loaded.cutoff_year == 2020
    assert loaded.theme == "light"
    assert loaded.min_n == 40
    assert loaded.compare_countries == ["FRA", "DEU"]


def test_settings_tolerate_unknown_keys(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"theme": "light", "future_option": 1}', encoding="utf-8")
    loaded = Settings.load(path)
    assert loaded.theme == "light"
    assert loaded.cutoff_year == 2015


def test_settings_defaults_when_missing(tmp_path):
    loaded = Settings.load(tmp_path / "missing.json")
    assert loaded.theme in {"dark", "light"}
    assert loaded.cutoff_year >= 2010
