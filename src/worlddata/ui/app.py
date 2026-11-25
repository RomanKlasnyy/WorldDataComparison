"""Application entry point: database verification, context setup and main window."""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

import matplotlib

matplotlib.use("QtAgg")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from ..config import load_config  # noqa: E402
from ..db import DataError, open_repository  # noqa: E402
from ..paths import get_paths  # noqa: E402
from .context import AppContext  # noqa: E402
from .main_window import MainWindow  # noqa: E402
from .settings import Settings  # noqa: E402
from .theme import apply_qt_palette, qss, set_current_theme  # noqa: E402


def _write_debug(text: str) -> None:
    if "--selftest" not in sys.argv and not os.environ.get("WDC_DEBUG"):
        return
    targets = [Path(sys.executable).resolve().parent / "selftest.log"]
    targets.append(Path(os.environ.get("TEMP", ".")) / "WorldDataComparison-selftest.log")
    for target in targets:
        try:
            with target.open("a", encoding="utf-8") as handle:
                handle.write(text.rstrip() + "\n")
        except OSError:
            continue


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("WorldDataComparison")
    app.setOrganizationName("WorldDataComparison")

    paths = get_paths()
    _write_debug(f"frozen={getattr(sys, 'frozen', False)} base={paths.base} db={paths.db}")
    try:
        config = load_config(paths)
        _write_debug(f"config loaded: {len(config.indicators)} indicators")
        repo = open_repository(paths)
        manifest = repo.manifest
        _write_debug(f"repo loaded: {manifest.get('build_id')}")
    except DataError as exc:
        _write_debug(f"DataError: {exc}")
        box = QMessageBox()
        box.setWindowTitle("Data unavailable")
        box.setIcon(QMessageBox.Critical)
        box.setText(str(exc))
        box.setInformativeText(
            f"Expected database:\n{paths.db}\n\n"
            "Build it with:\n  python scripts/refresh_data.py\n"
            "or drop in a newer worlddata.sqlite + manifest.json."
        )
        box.exec()
        return 1
    except Exception as exc:  # noqa: BLE001 - configuration errors must be visible
        _write_debug(f"startup error: {exc}\n{traceback.format_exc()}")
        QMessageBox.critical(None, "Configuration error", f"{exc}\n\n{traceback.format_exc()}")
        return 1

    settings = Settings.load(paths.settings)
    set_current_theme(settings.theme)
    app.setStyleSheet(qss(settings.theme))
    apply_qt_palette(app, settings.theme)

    ctx = AppContext(paths, config, repo, manifest, settings)
    window = MainWindow(ctx)
    window.show()
    _write_debug("window shown")

    if "--selftest" in sys.argv:
        # Used by the packaging check: construct and render every page, then exit.
        try:
            for key in ("dashboard", "countries", "rankings", "correlations", "groups", "quality", "about"):
                window.navigate(key)
                app.processEvents()
                _write_debug(f"page ok: {key}")
            window.close()
            _write_debug("selftest ok")
            return 0
        except Exception:  # noqa: BLE001 - surface a non-zero exit code
            _write_debug(traceback.format_exc())
            return 2

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
