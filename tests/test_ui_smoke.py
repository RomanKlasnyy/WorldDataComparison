from __future__ import annotations

import os
from dataclasses import replace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_main_window_smoke(qtbot, project_paths, real_repo, tmp_path):
    pytest.importorskip("pytestqt")
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import QApplication

    from worlddata.config import load_config
    from worlddata.ui.context import AppContext
    from worlddata.ui.main_window import MainWindow
    from worlddata.ui.settings import Settings
    from worlddata.ui.theme import apply_qt_palette, palette, qss, set_current_theme

    app = QApplication.instance()
    set_current_theme("dark")
    app.setStyleSheet(qss("dark"))
    apply_qt_palette(app, "dark")

    config = load_config(project_paths)
    paths = replace(project_paths, settings=tmp_path / "settings.json")
    settings = Settings()
    ctx = AppContext(paths, config, real_repo, real_repo.manifest, settings)
    window = MainWindow(ctx)
    qtbot.addWidget(window)
    window.resize(1400, 900)
    window.show()
    app.processEvents()

    # The native Windows style paints the header tail and the gap after the
    # last column with the viewport palette, so both must be theme-aware.
    view = window._pages["countries"].profile_table.view
    assert view.viewport().objectName() == "DataTableViewport"
    assert view.viewport().palette().color(QPalette.Base).name() == palette("dark")["panel"]
    header_viewport = view.horizontalHeader().viewport()
    assert header_viewport.palette().color(QPalette.Base).name() == palette("dark")["panel_alt"]

    for key in ("dashboard", "countries", "rankings", "quality", "about"):
        window.navigate(key)
        app.processEvents()
        assert window.stack.currentWidget() is window._pages[key]

    # Country selection and indicator navigation work from the command surface.
    window.open_country("FRA")
    app.processEvents()
    assert window._pages["countries"]._iso3 == "FRA"
    window.open_indicator("hdi")
    app.processEvents()
    assert window._pages["rankings"]._indicator == "hdi"

    window.close()
