"""Table and figure export helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def export_dataframe(frame: pd.DataFrame, path: Path) -> Path:
    path = Path(path)
    suffix = path.suffix.casefold()
    if suffix in {".xlsx", ".xlsm"}:
        frame.to_excel(path, index=False)
    else:
        frame.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def export_figure(figure, path: Path, dpi: int = 200) -> Path:
    path = Path(path)
    figure.savefig(path, dpi=dpi, bbox_inches="tight", facecolor=figure.get_facecolor())
    return path
