"""Qt stylesheet and chart palette."""

from __future__ import annotations

PALETTE = {
    "bg": "#12161b",
    "panel": "#1a2027",
    "panel_alt": "#212a33",
    "border": "#2c3742",
    "text": "#dfe6ee",
    "muted": "#96a3b3",
    "accent": "#4ea1ff",
    "accent_dim": "#2f6fb3",
    "good": "#4ec9a0",
    "bad": "#e06c75",
    "warn": "#e5c07b",
    "grid": "#2a333d",
    "series": [
        "#4ea1ff", "#f2a65a", "#4ec9a0", "#c678dd", "#e06c75",
        "#56b6c2", "#e5c07b", "#98c379", "#d19a66", "#abb2bf",
    ],
}

LIGHT_PALETTE = {
    **PALETTE,
    "bg": "#f4f6f9",
    "panel": "#ffffff",
    "panel_alt": "#eef2f7",
    "border": "#d4dce6",
    "text": "#1d2733",
    "muted": "#5d6b7c",
    "grid": "#dfe5ec",
}

DARK_QSS = """
* { font-family: "Segoe UI", "Inter", sans-serif; font-size: 10pt; }
QLabel { color: #dfe6ee; }
QMainWindow, QDialog { background: #12161b; }
QWidget#Sidebar { background: #0e1216; border-right: 1px solid #232c35; }
QLabel#AppTitle { color: #eef4fb; font-size: 15pt; font-weight: 700; }
QLabel#AppSubtitle { color: #7f8d9c; font-size: 8.5pt; }
QLabel#PageTitle { color: #eef4fb; font-size: 18pt; font-weight: 700; }
QLabel#PageSubtitle { color: #93a1b1; font-size: 9.5pt; }
QLabel#SectionTitle { color: #cfdae6; font-size: 11pt; font-weight: 600; }
QLabel#Muted { color: #8b99a8; }
QLabel#Caveat { color: #d8c48b; background: #241f14; border: 1px solid #4a3f22; border-radius: 6px; padding: 8px 10px; }
QLabel#CardValue { color: #eef4fb; font-size: 20pt; font-weight: 700; }
QLabel#CardLabel { color: #8b99a8; font-size: 8.5pt; text-transform: uppercase; }
QFrame#Card, QWidget#Card { background: #1a2027; border: 1px solid #2c3742; border-radius: 10px; }
QPushButton {
    background: #232d38; color: #dfe6ee; border: 1px solid #33414f;
    border-radius: 6px; padding: 6px 12px;
}
QPushButton:hover { background: #2b3947; border-color: #43607d; }
QPushButton:pressed { background: #1c252e; }
QPushButton:checked { background: #1e3a5c; border-color: #4ea1ff; color: #eaf3ff; }
QPushButton#Primary { background: #2f6fb3; border-color: #4ea1ff; color: #ffffff; font-weight: 600; }
QPushButton#Primary:hover { background: #3a83cf; }
QPushButton#Nav {
    text-align: left; padding: 9px 14px; border: none; border-left: 3px solid transparent;
    background: transparent; color: #a7b4c2; border-radius: 0;
}
QPushButton#Nav:hover { background: #161d24; color: #e6eef7; }
QPushButton#Nav:checked { background: #17212b; border-left: 3px solid #4ea1ff; color: #ffffff; font-weight: 600; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #1a222b; border: 1px solid #33414f; border-radius: 6px;
    padding: 6px 8px; color: #dfe6ee; selection-background-color: #2f6fb3;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: #4ea1ff; }
QComboBox QAbstractItemView {
    background: #1a222b; border: 1px solid #33414f; selection-background-color: #2b4a6b;
    color: #dfe6ee; outline: 0;
}
QCheckBox { color: #cfdae6; spacing: 6px; }
QCheckBox::indicator { width: 15px; height: 15px; border-radius: 3px; border: 1px solid #4a5b6d; background: #1a222b; }
QCheckBox::indicator:checked { background: #4ea1ff; border-color: #4ea1ff; }
QTableView {
    background: #161c23; alternate-background-color: #1a2129; gridline-color: #25303a;
    border: 1px solid #29343f; border-radius: 6px; color: #dfe6ee;
    selection-background-color: #24486e; selection-color: #ffffff;
}
QTableView::item { padding: 4px 6px; }
QHeaderView { background: #1e2731; border: none; }
QHeaderView::section {
    background: #1e2731; color: #9fadbc; border: none; border-bottom: 1px solid #33414f;
    border-right: 1px solid #29343f; padding: 6px; font-weight: 600;
}
QTableView QTableCornerButton::section { background: #1e2731; border: none; }
QAbstractScrollArea::corner { background: #161c23; }
QWidget#DataTableViewport { background: #161c23; }
QWidget#DataTableHeaderViewport { background: #1e2731; }
QListWidget {
    background: #161c23; border: 1px solid #29343f; border-radius: 6px; color: #cdd8e4;
    outline: 0;
}
QListWidget::item { padding: 5px 8px; border-radius: 4px; }
QListWidget::item:selected { background: #24486e; color: #ffffff; }
QListWidget::item:hover { background: #1e2933; }
QScrollBar:vertical { background: #141a20; width: 11px; margin: 0; }
QScrollBar::handle:vertical { background: #33414f; min-height: 28px; border-radius: 5px; }
QScrollBar::handle:vertical:hover { background: #44566a; }
QScrollBar:horizontal { background: #141a20; height: 11px; }
QScrollBar::handle:horizontal { background: #33414f; min-width: 28px; border-radius: 5px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: #141a20; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: #141a20; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; background: none; border: none; }
QTabWidget::pane { border: 1px solid #29343f; border-radius: 6px; background: #161c23; }
QTabBar::tab {
    background: #1a222b; color: #9fadbc; padding: 7px 14px; margin-right: 2px;
    border-top-left-radius: 6px; border-top-right-radius: 6px;
}
QTabBar::tab:selected { background: #24486e; color: #ffffff; }
QGroupBox { color: #cfdae6; font-weight: 600; border: 1px solid #29343f; border-radius: 8px; margin-top: 10px; padding-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QToolTip { background: #1f2933; color: #e6eef7; border: 1px solid #3b4a5a; padding: 4px; }
QStatusBar { background: #0e1216; color: #8b99a8; border-top: 1px solid #232c35; }
QSplitter::handle { background: #232c35; }
QProgressBar { background: #1a222b; border: 1px solid #33414f; border-radius: 5px; text-align: center; color: #dfe6ee; }
QProgressBar::chunk { background: #2f6fb3; border-radius: 4px; }
"""

LIGHT_QSS = """
* { font-family: "Segoe UI", "Inter", sans-serif; font-size: 10pt; }
QLabel { color: #1d2733; }
QMainWindow, QDialog { background: #f4f6f9; }
QWidget#Sidebar { background: #e8edf3; border-right: 1px solid #d4dce6; }
QLabel#AppTitle { color: #14202c; font-size: 15pt; font-weight: 700; }
QLabel#AppSubtitle { color: #5d6b7c; font-size: 8.5pt; }
QLabel#PageTitle { color: #14202c; font-size: 18pt; font-weight: 700; }
QLabel#PageSubtitle { color: #5d6b7c; font-size: 9.5pt; }
QLabel#SectionTitle { color: #24313f; font-size: 11pt; font-weight: 600; }
QLabel#Muted { color: #5d6b7c; }
QLabel#Caveat { color: #6b5313; background: #fff7e0; border: 1px solid #e6d49a; border-radius: 6px; padding: 8px 10px; }
QLabel#CardValue { color: #14202c; font-size: 20pt; font-weight: 700; }
QLabel#CardLabel { color: #5d6b7c; font-size: 8.5pt; }
QFrame#Card, QWidget#Card { background: #ffffff; border: 1px solid #d4dce6; border-radius: 10px; }
QPushButton { background: #ffffff; color: #1d2733; border: 1px solid #c7d2de; border-radius: 6px; padding: 6px 12px; }
QPushButton:hover { background: #eef3f9; border-color: #9fb3c8; }
QPushButton:checked { background: #dceafa; border-color: #3c7fc4; }
QPushButton#Primary { background: #2f6fb3; border-color: #2f6fb3; color: #ffffff; font-weight: 600; }
QPushButton#Nav { text-align: left; padding: 9px 14px; border: none; border-left: 3px solid transparent; background: transparent; color: #3d4b5a; border-radius: 0; }
QPushButton#Nav:hover { background: #dde5ee; color: #14202c; }
QPushButton#Nav:checked { background: #d5e3f2; border-left: 3px solid #2f6fb3; color: #10202f; font-weight: 600; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: #ffffff; border: 1px solid #c7d2de; border-radius: 6px; padding: 6px 8px; color: #1d2733; }
QLineEdit:focus, QComboBox:focus { border-color: #2f6fb3; }
QTableView { background: #ffffff; alternate-background-color: #f6f8fb; gridline-color: #e2e8f0; border: 1px solid #d4dce6; border-radius: 6px; color: #1d2733; selection-background-color: #d5e3f2; selection-color: #10202f; }
QHeaderView { background: #eef2f7; border: none; }
QHeaderView::section { background: #eef2f7; color: #46566a; border: none; border-bottom: 1px solid #d4dce6; border-right: 1px solid #e2e8f0; padding: 6px; font-weight: 600; }
QTableView QTableCornerButton::section { background: #eef2f7; border: none; }
QAbstractScrollArea::corner { background: #ffffff; }
QWidget#DataTableViewport { background: #ffffff; }
QWidget#DataTableHeaderViewport { background: #eef2f7; }
QListWidget { background: #ffffff; border: 1px solid #d4dce6; border-radius: 6px; color: #1d2733; }
QListWidget::item { padding: 5px 8px; border-radius: 4px; }
QListWidget::item:selected { background: #d5e3f2; color: #10202f; }
QTextEdit, QPlainTextEdit { background: #ffffff; border: 1px solid #d4dce6; border-radius: 6px; color: #1d2733; }
QScrollBar:vertical { background: #eef2f7; width: 11px; }
QScrollBar::handle:vertical { background: #c3cfdc; min-height: 28px; border-radius: 5px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: #eef2f7; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: #eef2f7; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; background: none; border: none; }
QTabWidget::pane { border: 1px solid #d4dce6; border-radius: 6px; background: #ffffff; }
QTabBar::tab { background: #eef2f7; color: #46566a; padding: 7px 14px; margin-right: 2px; border-top-left-radius: 6px; border-top-right-radius: 6px; }
QTabBar::tab:selected { background: #d5e3f2; color: #10202f; }
QGroupBox { color: #24313f; font-weight: 600; border: 1px solid #d4dce6; border-radius: 8px; margin-top: 10px; padding-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QStatusBar { background: #e8edf3; color: #5d6b7c; border-top: 1px solid #d4dce6; }
QSplitter::handle { background: #d4dce6; }
QToolTip { background: #ffffff; color: #1d2733; border: 1px solid #c7d2de; padding: 4px; }
"""


def qss(theme: str) -> str:
    return LIGHT_QSS if theme == "light" else DARK_QSS


def palette(theme: str) -> dict:
    return LIGHT_PALETTE if theme == "light" else PALETTE


_CURRENT = {"theme": "dark"}


def set_current_theme(theme: str) -> None:
    _CURRENT["theme"] = theme
    apply_matplotlib_style(theme)


def current_theme() -> str:
    return _CURRENT["theme"]


def current_palette() -> dict:
    return palette(_CURRENT["theme"])


def apply_qt_palette(app, theme: str) -> None:
    from PySide6.QtGui import QColor, QPalette

    colors = palette(theme)
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(colors["bg"]))
    pal.setColor(QPalette.WindowText, QColor(colors["text"]))
    pal.setColor(QPalette.Base, QColor(colors["panel"]))
    pal.setColor(QPalette.AlternateBase, QColor(colors["panel_alt"]))
    pal.setColor(QPalette.Text, QColor(colors["text"]))
    pal.setColor(QPalette.Button, QColor(colors["panel_alt"]))
    pal.setColor(QPalette.ButtonText, QColor(colors["text"]))
    pal.setColor(QPalette.BrightText, QColor("#ffffff"))
    pal.setColor(QPalette.Highlight, QColor(colors["accent_dim"]))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ToolTipBase, QColor(colors["panel_alt"]))
    pal.setColor(QPalette.ToolTipText, QColor(colors["text"]))
    pal.setColor(QPalette.PlaceholderText, QColor(colors["muted"]))
    pal.setColor(QPalette.Link, QColor(colors["accent"]))
    pal.setColor(QPalette.Disabled, QPalette.Text, QColor(colors["muted"]))
    pal.setColor(QPalette.Disabled, QPalette.WindowText, QColor(colors["muted"]))
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(colors["muted"]))
    app.setPalette(pal)


def apply_table_palettes(app, theme: str) -> None:
    """Theme the parts of a QTableView that the native Windows style paints itself.

    The area after the last column and the empty header tail are filled with the
    viewport's QPalette::Base, not with the QSS background, so they stay white in
    dark mode unless the viewport palette is set explicitly.
    """
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QTableView

    colors = palette(theme)
    for widget in app.allWidgets():
        if not isinstance(widget, QTableView):
            continue
        viewport = widget.viewport()
        viewport.setAutoFillBackground(True)
        vp = viewport.palette()
        vp.setColor(QPalette.Base, QColor(colors["panel"]))
        vp.setColor(QPalette.Window, QColor(colors["panel"]))
        vp.setColor(QPalette.AlternateBase, QColor(colors["panel_alt"]))
        viewport.setPalette(vp)

        header = widget.horizontalHeader().viewport()
        header.setAutoFillBackground(True)
        hp = header.palette()
        hp.setColor(QPalette.Base, QColor(colors["panel_alt"]))
        hp.setColor(QPalette.Window, QColor(colors["panel_alt"]))
        header.setPalette(hp)


def apply_matplotlib_style(theme: str) -> None:
    import matplotlib as mpl

    colors = palette(theme)
    mpl.rcParams.update(
        {
            "figure.facecolor": colors["panel"],
            "figure.edgecolor": colors["panel"],
            "axes.facecolor": colors["panel"],
            "axes.edgecolor": colors["border"],
            "axes.labelcolor": colors["muted"],
            "axes.titlecolor": colors["text"],
            "axes.grid": True,
            "axes.grid.axis": "both",
            "grid.color": colors["grid"],
            "grid.linewidth": 0.7,
            "grid.alpha": 0.7,
            "text.color": colors["text"],
            "xtick.color": colors["muted"],
            "ytick.color": colors["muted"],
            "font.size": 9,
            "axes.titlesize": 10.5,
            "axes.titleweight": "bold",
            "legend.frameon": False,
            "legend.labelcolor": colors["text"],
            "figure.autolayout": False,
        }
    )
