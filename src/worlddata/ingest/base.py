"""Shared HTTP, snapshot-cache and error types for data fetchers."""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import requests

from ..paths import Paths

USER_AGENT = (
    "WorldDataComparison/0.1 (offline research tool; +https://github.com/) "
    "python-requests"
)

VERBOSE = bool(os.environ.get("WORLDDATA_VERBOSE"))


class FetchError(RuntimeError):
    pass


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})
    adapter = requests.adapters.HTTPAdapter(pool_connections=2, pool_maxsize=4)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def http_get(
    session: requests.Session,
    url: str,
    timeout: int = 40,
    attempts: int = 4,
) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(url, timeout=timeout)
        except Exception as exc:  # noqa: BLE001 - network layer is inherently broad
            last_error = exc
            if VERBOSE:
                print(f"    http attempt {attempt} failed: {exc}")
            time.sleep(2.0 * attempt)
            continue
        if response.status_code == 200 and response.content:
            return response
        last_error = FetchError(f"HTTP {response.status_code} for {url}")
        if VERBOSE:
            print(f"    http attempt {attempt}: status {response.status_code} ({len(response.content)} bytes)")
        if response.status_code in (400, 401, 403, 404):
            break
        time.sleep(3.0 * attempt)
    raise FetchError(f"failed to fetch {url}: {last_error}")


@dataclass
class SnapshotStore:
    paths: Paths
    offline: bool = False
    force: bool = False
    runs: dict[str, dict] = field(default_factory=dict)

    def _run_dir(self, source: str) -> Path:
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        return self.paths.raw / source / today

    def today(self, source: str, name: str, extension: str) -> Path | None:
        path = self._run_dir(source) / f"{name}.{extension}"
        if path.exists() and path.stat().st_size > 0:
            return path
        return None

    def save(self, source: str, name: str, payload: bytes, extension: str) -> Path:
        directory = self._run_dir(source)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{name}.{extension}"
        path.write_bytes(payload)
        checksum = hashlib.sha256(payload).hexdigest()
        self.runs.setdefault(source, {}).setdefault("files", {})[name] = {
            "file": str(path.relative_to(self.paths.data)),
            "sha256": checksum,
            "bytes": len(payload),
            "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        return path

    def latest(self, source: str, name: str, extension: str) -> Path:
        base = self.paths.raw / source
        if not base.exists():
            raise FetchError(
                f"no cached snapshot for {source}/{name}; run scripts/refresh_data.py without --offline"
            )
        candidates = sorted(
            (d / f"{name}.{extension}" for d in base.iterdir() if d.is_dir()),
            key=lambda p: p.parent.name,
        )
        existing = [p for p in candidates if p.exists()]
        if not existing:
            raise FetchError(f"no cached snapshot for {source}/{name} in {base}")
        return existing[-1]

    def load_json(self, source: str, name: str, extension: str = "json"):
        path = self.latest(source, name, extension)
        if extension == "json":
            return json.loads(path.read_text(encoding="utf-8"))
        return path.read_text(encoding="utf-8")

    def mark_source(self, source: str, **fields) -> None:
        run = self.runs.setdefault(source, {})
        run.update(fields)
