"""Base page class shared by all sections."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget


class Page(QWidget):
    def __init__(self, ctx, window, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.window = window

    def on_show(self) -> None:  # pragma: no cover - UI hook
        pass

    def on_theme_changed(self) -> None:  # pragma: no cover - UI hook
        pass
