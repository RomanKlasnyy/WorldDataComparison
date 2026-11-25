"""Import a CSV/XLSX for an indicator whose source is `manual`."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from worlddata.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(["import-manual", *sys.argv[1:]]))
