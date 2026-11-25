"""Validate the built database and print quality gates."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from worlddata.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(["validate", *sys.argv[1:]]))
