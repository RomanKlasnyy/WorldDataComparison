"""Pandas-backed Qt table models with filtering, sorting and percent-bar painting."""

from __future__ import annotations

import math

import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QRectF, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from .theme import current_palette


def _is_missing(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def format_value(value, kind: str | None = None) -> str:
    if _is_missing(value):
        return "—"
    if kind == "pct":
        return f"{float(value):.1f}%"
    if kind == "pval":
        try:
            v = float(value)
        except (TypeError, ValueError):
            return str(value)
        return "<0.0001" if v < 0.0001 else f"{v:.4f}"
    if kind == "year":
        return f"{int(value)}"
    if kind == "int":
        try:
            return f"{int(round(float(value))):,}"
        except (TypeError, ValueError):
            return str(value)
    if kind == "num":
        try:
            v = float(value)
        except (TypeError, ValueError):
            return str(value)
        if v == 0:
            return "0"
        av = abs(v)
        if av >= 1e9:
            return f"{v / 1e9:,.2f}B"
        if av >= 1e6:
            return f"{v / 1e6:,.2f}M"
        if av >= 1e4:
            return f"{v:,.0f}"
        if av >= 100:
            return f"{v:,.1f}"
        if av >= 1:
            return f"{v:,.2f}"
        if av >= 0.01:
            return f"{v:.3f}"
        return f"{v:.4f}"
    if isinstance(value, float):
        return format_value(value, "num")
    if isinstance(value, (int,)) and not isinstance(value, bool):
        return f"{value:,}"
    return str(value)


def _sort_key(value):
    if _is_missing(value):
        return (2, 0.0)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return (0, float(value))
    return (1, str(value).casefold())


class DataFrameModel(QAbstractTableModel):
    def __init__(self, frame: pd.DataFrame | None = None, formats: dict | None = None):
        super().__init__()
        self._frame = pd.DataFrame()
        self._formats = formats or {}
        self._headers: list[str] = []
        self.set_frame(frame if frame is not None else pd.DataFrame())

    def set_frame(self, frame: pd.DataFrame, formats: dict | None = None) -> None:
        self.beginResetModel()
        self._frame = frame.reset_index(drop=True).copy()
        self._headers = [str(c) for c in self._frame.columns]
        if formats is not None:
            self._formats = formats
        self.endResetModel()

    def frame(self) -> pd.DataFrame:
        return self._frame.copy()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._frame)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._headers)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        value = self._frame.iat[index.row(), index.column()]
        if role == Qt.DisplayRole:
            column = self._headers[index.column()]
            return format_value(value, self._formats.get(column))
        if role == Qt.UserRole:
            if _is_missing(value):
                return None
            if isinstance(value, (int, float)):
                return float(value)
            return str(value)
        if role == Qt.TextAlignmentRole:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return int(Qt.AlignRight | Qt.AlignVCenter)
            return int(Qt.AlignLeft | Qt.AlignVCenter)
        if role == Qt.ToolTipRole:
            column = self._headers[index.column()]
            return f"{column}: {format_value(value, self._formats.get(column))}"
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return self._headers[section] if section < len(self._headers) else None
        return str(section + 1)

    def sort(self, column: int, order: Qt.SortOrder = Qt.AscendingOrder) -> None:
        if self._frame.empty or column >= len(self._headers):
            return
        name = self._headers[column]
        self.layoutAboutToBeChanged.emit()
        self._frame = self._frame.assign(
            __key=self._frame[name].map(_sort_key)
        ).sort_values("__key", ascending=order == Qt.AscendingOrder, kind="stable")
        self._frame = self._frame.drop(columns="__key").reset_index(drop=True)
        self.layoutChanged.emit()


class FrameProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._query = ""
        self.setDynamicSortFilter(True)
        self.setSortCaseSensitivity(Qt.CaseInsensitive)

    def set_query(self, text: str) -> None:
        self._query = (text or "").strip().casefold()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if not self._query:
            return True
        model = self.sourceModel()
        if model is None:
            return True
        for column in range(model.columnCount()):
            text = model.index(source_row, column).data(Qt.DisplayRole)
            if text and self._query in str(text).casefold():
                return True
        return False

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        lv = left.data(Qt.UserRole)
        rv = right.data(Qt.UserRole)
        lk, rk = _sort_key(lv), _sort_key(rv)
        if lk[0] != rk[0]:
            return lk[0] < rk[0]
        return lk[1] < rk[1]


class PercentBarDelegate(QStyledItemDelegate):
    def __init__(self, color: str | None = None, parent=None):
        super().__init__(parent)
        self._color = color

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        value = index.data(Qt.UserRole)
        if value is None:
            super().paint(painter, option, index)
            return
        try:
            pct = max(0.0, min(100.0, float(value)))
        except (TypeError, ValueError):
            super().paint(painter, option, index)
            return
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        style = option.widget.style() if option.widget else None
        if style:
            style.drawPrimitive(QStyle.PE_PanelItemViewItem, option, painter, option.widget)
        rect = QRectF(option.rect).adjusted(4, 5, -4, -5)
        radius = min(4.0, rect.height() / 2)
        base = QColor(self._color or current_palette()["accent"])
        base.setAlpha(110)
        painter.setPen(Qt.NoPen)
        painter.setBrush(base)
        painter.drawRoundedRect(rect, radius, radius)
        filled = QRectF(rect)
        filled.setWidth(max(rect.width() * pct / 100.0, 2.0))
        base.setAlpha(210)
        painter.setBrush(base)
        painter.drawRoundedRect(filled, radius, radius)
        painter.setPen(QPen(QColor(current_palette()["text"])))
        painter.drawText(
            option.rect.adjusted(8, 0, -6, 0),
            int(Qt.AlignLeft | Qt.AlignVCenter),
            f"{pct:.1f}%",
        )
        painter.restore()
