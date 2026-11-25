"""SQLite schema, build-time writers, manifest handling and read-side repository."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from . import SCHEMA_VERSION, __version__
from .paths import Paths

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE source (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    homepage TEXT,
    license TEXT,
    attribution TEXT,
    redistributable INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE country (
    iso3 TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    official_name TEXT,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('state','territory','observer','disputed')),
    un_member INTEGER NOT NULL DEFAULT 0,
    region TEXT,
    subregion TEXT,
    continent TEXT,
    income_group TEXT,
    is_default INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE country_alias (
    alias TEXT NOT NULL,
    source_id TEXT NOT NULL,
    iso3 TEXT NOT NULL REFERENCES country(iso3),
    PRIMARY KEY (alias, source_id)
);

CREATE TABLE indicator (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    domain TEXT NOT NULL,
    description TEXT,
    unit TEXT,
    source_id TEXT NOT NULL REFERENCES source(id),
    series TEXT,
    higher_is_better INTEGER,
    default_log INTEGER NOT NULL DEFAULT 0,
    is_composite INTEGER NOT NULL DEFAULT 0,
    hidden INTEGER NOT NULL DEFAULT 0,
    aggregation TEXT NOT NULL DEFAULT 'median',
    valid_min REAL,
    valid_max REAL,
    attribution TEXT
);

CREATE TABLE observation (
    iso3 TEXT NOT NULL REFERENCES country(iso3),
    indicator_id TEXT NOT NULL REFERENCES indicator(id),
    year INTEGER NOT NULL,
    value REAL NOT NULL,
    source_id TEXT NOT NULL REFERENCES source(id),
    retrieved_at TEXT,
    PRIMARY KEY (iso3, indicator_id, year)
) WITHOUT ROWID;

CREATE INDEX idx_observation_indicator ON observation(indicator_id, year);
CREATE INDEX idx_observation_country ON observation(iso3, year);

CREATE TABLE coverage (
    indicator_id TEXT PRIMARY KEY REFERENCES indicator(id),
    n_countries INTEGER NOT NULL,
    pct REAL NOT NULL,
    min_year INTEGER,
    max_year INTEGER,
    latest_year INTEGER
);

CREATE TABLE "group" (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    family TEXT NOT NULL,
    description TEXT,
    color TEXT,
    origin TEXT NOT NULL DEFAULT 'shipped'
);

CREATE TABLE group_member (
    group_id TEXT NOT NULL REFERENCES "group"(id) ON DELETE CASCADE,
    iso3 TEXT NOT NULL REFERENCES country(iso3),
    PRIMARY KEY (group_id, iso3)
);
"""


class DataError(RuntimeError):
    """Raised when the database or manifest is missing, stale or inconsistent."""


def connect(path: Path, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        uri = f"file:{path.as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if not readonly:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def content_hash(observations: pd.DataFrame) -> str:
    ordered = observations.sort_values(
        ["iso3", "indicator_id", "year"], kind="stable"
    )[["iso3", "indicator_id", "year", "value"]]
    digest = hashlib.sha256()
    for iso3, indicator_id, year, value in ordered.itertuples(index=False, name=None):
        digest.update(f"{iso3}|{indicator_id}|{int(year)}|{float(value):.10g}\n".encode())
    return digest.hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_db(
    paths: Paths,
    *,
    config,
    observations: pd.DataFrame,
    groups: pd.DataFrame,
    group_members: pd.DataFrame,
    source_runs: dict[str, dict],
    history_floor_year: int,
    recency_cutoff_year: int,
    aliases: list[tuple[str, str, str]] | None = None,
    build_id: str | None = None,
) -> dict:
    paths.ensure()
    tmp = paths.db.with_suffix(".sqlite.tmp")
    if tmp.exists():
        tmp.unlink()
    conn = connect(tmp)
    try:
        create_schema(conn)
        iso_default = {c.iso3 for c in config.countries if c.is_default}
        default_set = sorted(iso_default)
        conn.executemany(
            "INSERT INTO country VALUES (?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    c.iso3,
                    c.name,
                    c.official_name,
                    c.entity_type,
                    int(c.un_member),
                    c.region,
                    c.subregion,
                    c.continent,
                    c.income_group,
                    int(c.is_default),
                )
                for c in config.countries
            ],
        )
        conn.executemany(
            "INSERT INTO source VALUES (?,?,?,?,?,?)",
            [
                (s.id, s.name, s.homepage, s.license, s.attribution, int(s.redistributable))
                for s in config.sources.values()
            ],
        )
        conn.executemany(
            "INSERT INTO indicator VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    i.id,
                    i.name,
                    i.domain,
                    i.description,
                    i.unit,
                    i.source,
                    i.series,
                    None if i.higher_is_better is None else int(i.higher_is_better),
                    int(i.default_log),
                    int(i.is_composite),
                    int(i.hidden),
                    i.aggregation,
                    i.valid_min,
                    i.valid_max,
                    i.attribution,
                )
                for i in config.indicators
            ],
        )
        if aliases:
            conn.executemany(
                "INSERT OR REPLACE INTO country_alias VALUES (?,?,?)", aliases
            )

        payload = [
            (
                str(row.iso3),
                str(row.indicator_id),
                int(row.year),
                float(row.value),
                str(row.source_id),
                str(row.retrieved_at),
            )
            for row in observations.itertuples(index=False)
        ]
        conn.executemany("INSERT OR REPLACE INTO observation VALUES (?,?,?,?,?,?)", payload)

        conn.executemany(
            'INSERT INTO "group" VALUES (?,?,?,?,?,?)',
            [
                (g.id, g.name, g.family, g.description, g.color, "shipped")
                for g in config.groups
            ],
        )
        conn.executemany(
            "INSERT INTO group_member VALUES (?,?)",
            [(str(r.group_id), str(r.iso3)) for r in group_members.itertuples(index=False)],
        )

        n_countries = len(default_set)
        cov_source = observations[observations["iso3"].isin(iso_default)]
        cov = (
            cov_source.groupby("indicator_id", sort=False)
            .agg(
                n_countries=("iso3", "nunique"),
                min_year=("year", "min"),
                max_year=("year", "max"),
                latest_year=("year", "max"),
            )
            .reset_index()
        )
        cov["pct"] = (cov["n_countries"] / max(n_countries, 1) * 100).round(2)
        conn.executemany(
            "INSERT INTO coverage VALUES (?,?,?,?,?,?)",
            [
                (
                    str(r.indicator_id),
                    int(r.n_countries),
                    float(r.pct),
                    int(r.min_year),
                    int(r.max_year),
                    int(r.latest_year),
                )
                for r in cov.itertuples(index=False)
            ],
        )

        meta = {
            "schema_version": str(SCHEMA_VERSION),
            "app_version": __version__,
            "build_id": build_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
            "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "history_floor_year": str(history_floor_year),
            "recency_cutoff_year": str(recency_cutoff_year),
            "content_hash": content_hash(observations),
            "n_observations": str(len(observations)),
            "n_countries": str(n_countries),
            "n_indicators": str(len(config.indicators)),
        }
        conn.executemany("INSERT INTO meta VALUES (?,?)", list(meta.items()))
        conn.commit()
        # Compact the WAL into the main file so the shipped DB is a single artifact.
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()

    if paths.db.exists():
        paths.db.unlink()
    tmp.replace(paths.db)

    manifest = {
        **meta,
        "db_sha256": file_sha256(paths.db),
        "db_bytes": paths.db.stat().st_size,
        "sources": source_runs,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    paths.manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def read_manifest(paths: Paths) -> dict:
    if not paths.manifest.exists():
        raise DataError(
            f"Data manifest not found at {paths.manifest}. "
            "Run `python scripts/refresh_data.py` to build the dataset."
        )
    return json.loads(paths.manifest.read_text(encoding="utf-8"))


def verify(paths: Paths, check_hash: bool = True) -> dict:
    if not paths.db.exists():
        raise DataError(
            f"Database not found at {paths.db}. "
            "Run `python scripts/refresh_data.py` to build the dataset."
        )
    manifest = read_manifest(paths)
    version = int(manifest.get("schema_version", -1))
    if version != SCHEMA_VERSION:
        raise DataError(
            f"Data schema version {version} does not match this app (expected {SCHEMA_VERSION}). "
            "Rebuild the database with scripts/build_db.py or update the application."
        )
    if check_hash:
        expected = manifest.get("db_sha256")
        actual = file_sha256(paths.db)
        if expected and expected != actual:
            raise DataError(
                "The database checksum does not match manifest.json. "
                "Replace both files from the same build, or rebuild the dataset."
            )
    return manifest


class Repository:
    """Read-only access used by the analysis core and the UI."""

    def __init__(self, path: Path, manifest: dict | None = None):
        self.path = Path(path)
        self._manifest = manifest
        self._conn = connect(self.path, readonly=True)

    def close(self) -> None:
        self._conn.close()

    @property
    def manifest(self) -> dict:
        if self._manifest is None:
            from .db import read_manifest as _rm
            from .paths import get_paths

            self._manifest = _rm(get_paths())
        return self._manifest

    def meta(self) -> dict[str, str]:
        return {r["key"]: r["value"] for r in self._conn.execute("SELECT key, value FROM meta")}

    def countries(self, include_territories: bool = False) -> pd.DataFrame:
        sql = "SELECT * FROM country"
        params: tuple = ()
        if not include_territories:
            sql += " WHERE is_default = 1"
        sql += " ORDER BY name"
        return pd.read_sql_query(sql, self._conn, params=params)

    def indicators(self, include_hidden: bool = False, with_data: bool = True) -> pd.DataFrame:
        sql = """
            SELECT i.*, c.n_countries, c.pct, c.min_year, c.max_year, c.latest_year,
                   s.name AS source_name, s.license AS source_license
            FROM indicator i
            JOIN source s ON s.id = i.source_id
            LEFT JOIN coverage c ON c.indicator_id = i.id
        """
        clauses = []
        if not include_hidden:
            clauses.append("i.hidden = 0")
        if with_data:
            clauses.append("c.n_countries > 0")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        return pd.read_sql_query(sql, self._conn)

    def sources(self) -> pd.DataFrame:
        return pd.read_sql_query("SELECT * FROM source ORDER BY name", self._conn)

    def groups(self) -> pd.DataFrame:
        return pd.read_sql_query(
            """
            SELECT g.*, COUNT(gm.iso3) AS n_members
            FROM "group" g LEFT JOIN group_member gm ON gm.group_id = g.id
            GROUP BY g.id ORDER BY g.family, g.name
            """,
            self._conn,
        )

    def group_members(self) -> pd.DataFrame:
        return pd.read_sql_query("SELECT * FROM group_member", self._conn)

    def observations(self, indicators: list[str] | None = None) -> pd.DataFrame:
        sql = "SELECT iso3, indicator_id, year, value, source_id, retrieved_at FROM observation"
        params: tuple = ()
        if indicators:
            placeholders = ",".join("?" for _ in indicators)
            sql += f" WHERE indicator_id IN ({placeholders})"
            params = tuple(indicators)
        return pd.read_sql_query(sql, self._conn, params=params)

    def latest(self, cutoff_year: int, indicators: list[str] | None = None) -> pd.DataFrame:
        """Latest observation per country x indicator at or after cutoff_year."""
        sql = """
            SELECT iso3, indicator_id, year, value
            FROM (
                SELECT iso3, indicator_id, year, value,
                       ROW_NUMBER() OVER (
                           PARTITION BY iso3, indicator_id ORDER BY year DESC
                       ) AS rn
                FROM observation
                WHERE year >= ?
        """
        params: list = [cutoff_year]
        if indicators:
            placeholders = ",".join("?" for _ in indicators)
            sql += f" AND indicator_id IN ({placeholders})"
            params.extend(indicators)
        sql += ") WHERE rn = 1"
        return pd.read_sql_query(sql, self._conn, params=tuple(params))

    def country_history(self, iso3: str, indicator_id: str) -> pd.DataFrame:
        return pd.read_sql_query(
            "SELECT year, value FROM observation WHERE iso3 = ? AND indicator_id = ? ORDER BY year",
            self._conn,
            params=(iso3, indicator_id),
        )

    def year_coverage(self, indicator_id: str) -> pd.DataFrame:
        return pd.read_sql_query(
            "SELECT year, COUNT(*) AS n FROM observation WHERE indicator_id = ? GROUP BY year ORDER BY year",
            self._conn,
            params=(indicator_id,),
        )


def open_repository(paths: Paths) -> Repository:
    manifest = verify(paths)
    return Repository(paths.db, manifest)
