"""Reusable Qt widgets: cards, charts, tables, searchable lists and background tasks."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QAction, QColor, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QSpinBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from .models import DataFrameModel, FrameProxy, PercentBarDelegate
from .theme import current_palette, palette

BAR_COLUMNS = {
    "better_pct": "Percentile",
    "Percentile": "Percentile",
    "coverage_pct": "Coverage",
    "pct": "Coverage",
}


class Card(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setFrameShape(QFrame.NoFrame)


class KpiCard(Card):
    def __init__(self, label: str, value: str = "—", hint: str = "", parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 12, 14, 12)
        self._layout.setSpacing(2)
        self.value_label = QLabel(value)
        self.value_label.setObjectName("CardValue")
        caption = QLabel(label)
        caption.setObjectName("CardLabel")
        self.hint_label = QLabel(hint)
        self.hint_label.setObjectName("Muted")
        self.hint_label.setWordWrap(True)
        self._layout.addWidget(caption)
        self._layout.addWidget(self.value_label)
        self._layout.addWidget(self.hint_label)
        self.setMinimumWidth(150)

    def set_value(self, value: str, hint: str | None = None) -> None:
        self.value_label.setText(value)
        if hint is not None:
            self.hint_label.setText(hint)


class PageHeader(QWidget):
    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 6)
        layout.setSpacing(2)
        self.title = QLabel(title)
        self.title.setObjectName("PageTitle")
        self.subtitle = QLabel(subtitle)
        self.subtitle.setObjectName("PageSubtitle")
        self.subtitle.setWordWrap(True)
        layout.addWidget(self.title)
        if subtitle:
            layout.addWidget(self.subtitle)

    def set_subtitle(self, text: str) -> None:
        self.subtitle.setText(text)


def section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("SectionTitle")
    return label


class ChartPanel(QWidget):
    def __init__(self, height: int = 300, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(height)
        self._figure = Figure(figsize=(6, 3.4), dpi=100)
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)
        self._axes = None

    @property
    def figure(self) -> Figure:
        return self._figure

    @property
    def canvas(self) -> FigureCanvasQTAgg:
        return self._canvas

    def reset(self, projection: str | None = None):
        self._figure.clear()
        self._figure.set_facecolor(current_palette()["panel"])
        if projection:
            self._axes = self._figure.add_subplot(111, projection=projection)
        else:
            self._axes = self._figure.add_subplot(111)
        return self._axes

    def apply_theme(self, theme: str) -> None:
        colors = palette(theme)
        self._figure.set_facecolor(colors["panel"])
        if self._axes is not None:
            self._axes.set_facecolor(colors["panel"])

    def message(self, text: str) -> None:
        self._figure.clear()
        self._figure.set_facecolor(current_palette()["panel"])
        self._figure.text(
            0.5,
            0.5,
            text,
            ha="center",
            va="center",
            color=current_palette()["muted"],
            fontsize=10,
        )
        self._canvas.draw_idle()

    def draw(self) -> None:
        self._canvas.draw_idle()

    def save_dialog(self, parent=None, default_name: str = "chart.png") -> Path | None:
        path, _ = QFileDialog.getSaveFileName(
            parent or self, "Save chart", default_name, "PNG image (*.png);;SVG (*.svg);;PDF (*.pdf)"
        )
        if not path:
            return None
        target = Path(path)
        self._figure.savefig(
            target, dpi=200, bbox_inches="tight", facecolor=self._figure.get_facecolor()
        )
        return target


class DataTable(QWidget):
    def __init__(self, search: bool = False, search_placeholder: str = "Filter…", parent=None):
        super().__init__(parent)
        self._model = DataFrameModel()
        self._proxy = FrameProxy(self)
        self._proxy.setSourceModel(self._model)
        self.search = QLineEdit()
        self.search.setPlaceholderText(search_placeholder)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._proxy.set_query)
        self.search.setVisible(search)
        self.view = QTableView()
        self.view.setModel(self._proxy)
        self.view.setSortingEnabled(True)
        self.view.setAlternatingRowColors(True)
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.view.verticalHeader().setVisible(False)
        self.view.verticalHeader().setDefaultSectionSize(26)
        self.view.horizontalHeader().setStretchLastSection(False)
        self.view.horizontalHeader().setMinimumSectionSize(40)
        # QTableView paints the gap after the last column and the header's
        # empty tail with the viewport palette, which the native Windows style
        # leaves light. Give both viewports an explicit QSS colour so they
        # follow the active theme.
        self.view.viewport().setObjectName("DataTableViewport")
        self.view.horizontalHeader().viewport().setObjectName("DataTableHeaderViewport")
        self.view.setWordWrap(False)
        self.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._context_menu)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        if search:
            layout.addWidget(self.search)
        layout.addWidget(self.view)

    def set_frame(self, frame, formats: dict | None = None) -> None:
        self._model.set_frame(frame, formats)
        self._proxy.sort(-1)
        self.view.horizontalHeader().setSortIndicator(-1, Qt.AscendingOrder)
        self._apply_delegates()

    def _apply_delegates(self) -> None:
        headers = [self._model.headerData(i, Qt.Horizontal) for i in range(self._model.columnCount())]
        for index, header in enumerate(headers):
            if header in BAR_COLUMNS:
                self.view.setItemDelegateForColumn(index, PercentBarDelegate(parent=self.view))
                self.view.setColumnWidth(index, 120)
        self.view.resizeColumnsToContents()
        for index in range(self._model.columnCount()):
            self.view.setColumnWidth(index, min(max(self.view.columnWidth(index), 64), 220))

    def frame(self):
        return self._model.frame()

    def set_widths(self, widths: dict[str, int]) -> None:
        headers = [
            self._model.headerData(i, Qt.Horizontal) for i in range(self._model.columnCount())
        ]
        for index, header in enumerate(headers):
            if header in widths:
                self.view.setColumnWidth(index, widths[header])

    def proxy(self) -> FrameProxy:
        return self._proxy

    def selected_source_row(self) -> int | None:
        indexes = self.view.selectionModel().selectedRows()
        if not indexes:
            return None
        return self._proxy.mapToSource(indexes[0]).row()

    def selected_value(self, column: str):
        row = self.selected_source_row()
        if row is None:
            return None
        frame = self._model.frame()
        if column not in frame.columns or row >= len(frame):
            return None
        return frame.iloc[row][column]

    def _context_menu(self, point) -> None:
        menu = QMenu(self)
        copy_cell = QAction("Copy cell", menu)
        copy_cell.triggered.connect(lambda: self._copy(False))
        copy_row = QAction("Copy row", menu)
        copy_row.triggered.connect(lambda: self._copy(True))
        copy_all = QAction("Copy all (TSV)", menu)
        copy_all.triggered.connect(self._copy_all)
        menu.addAction(copy_cell)
        menu.addAction(copy_row)
        menu.addSeparator()
        menu.addAction(copy_all)
        menu.exec(self.view.viewport().mapToGlobal(point))

    def _copy(self, whole_row: bool) -> None:
        index = self.view.currentIndex()
        if not index.isValid():
            return
        if whole_row:
            values = [
                str(self._proxy.index(index.row(), c).data(Qt.DisplayRole) or "")
                for c in range(self._proxy.columnCount())
            ]
            QGuiApplication.clipboard().setText("\t".join(values))
        else:
            QGuiApplication.clipboard().setText(str(index.data(Qt.DisplayRole) or ""))

    def _copy_all(self) -> None:
        frame = self._model.frame()
        QGuiApplication.clipboard().setText(frame.to_csv(sep="\t", index=False))


class SearchableList(QWidget):
    item_selected = Signal(str)

    def __init__(self, placeholder: str = "Search…", parent=None):
        super().__init__(parent)
        self._items: list[tuple[str, str, str | None]] = []
        self.search = QLineEdit()
        self.search.setPlaceholderText(placeholder)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._rebuild)
        self.list = QListWidget()
        self.list.setUniformItemSizes(True)
        self.list.currentItemChanged.connect(self._emit)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.search)
        layout.addWidget(self.list, 1)

    def set_items(self, items: list[tuple[str, str, str | None]]) -> None:
        self._items = items
        self._rebuild()

    def _rebuild(self) -> None:
        query = self.search.text().strip().casefold()
        current = self.current_key()
        self.list.blockSignals(True)
        self.list.clear()
        last_group = None
        first_selectable = None
        for key, label, group in self._items:
            if query and query not in label.casefold() and query not in (group or "").casefold():
                continue
            if group and group != last_group:
                header = QListWidgetItem(group.upper())
                header.setFlags(Qt.NoItemFlags)
                header.setForeground(QColor(current_palette()["muted"]))
                self.list.addItem(header)
                last_group = group
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, key)
            self.list.addItem(item)
            if first_selectable is None:
                first_selectable = item
            if key == current:
                self.list.setCurrentItem(item)
        if self.list.currentItem() is None and first_selectable is not None:
            self.list.setCurrentItem(first_selectable)
        self.list.blockSignals(False)

    def _emit(self, current, previous) -> None:
        if current is None:
            return
        key = current.data(Qt.UserRole)
        if key:
            self.item_selected.emit(str(key))

    def current_key(self) -> str | None:
        item = self.list.currentItem()
        return str(item.data(Qt.UserRole)) if item and item.data(Qt.UserRole) else None

    def set_current(self, key: str) -> None:
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item.data(Qt.UserRole) == key:
                self.list.setCurrentItem(item)
                return

    def select_first(self) -> None:
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item.data(Qt.UserRole):
                self.list.setCurrentItem(item)
                return


class CheckListDialog(QDialog):
    """A modal searchable checkbox picker used for compare sets and group membership."""

    def __init__(
        self,
        title: str,
        items: list[tuple[str, str, str | None]],
        checked: list[str] | None = None,
        parent=None,
        max_checks: int | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(520, 620)
        self._max = max_checks
        self._all: list[tuple[str, str, str | None]] = items
        self._checked = set(checked or [])

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search…")
        self.search.textChanged.connect(self._rebuild)
        self.list = QListWidget()
        self.list.setMinimumSize(380, 440)
        self._rebuild()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Apply")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.search)
        layout.addWidget(self.list, 1)
        if self._max:
            hint = QLabel(f"Select up to {self._max}.")
            hint.setObjectName("Muted")
            layout.addWidget(hint)
        layout.addWidget(buttons)

    def _rebuild(self) -> None:
        query = self.search.text().strip().casefold()
        self.list.clear()
        last_group = None
        for key, label, group in self._all:
            if query and query not in label.casefold() and query not in (group or "").casefold():
                continue
            if group and group != last_group:
                header = QListWidgetItem(group.upper())
                header.setFlags(Qt.NoItemFlags)
                header.setForeground(QColor(current_palette()["muted"]))
                self.list.addItem(header)
                last_group = group
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, key)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if key in self._checked else Qt.Unchecked)
            self.list.addItem(item)

    def selected(self) -> list[str]:
        keys = []
        for row in range(self.list.count()):
            item = self.list.item(row)
            key = item.data(Qt.UserRole)
            if key and item.checkState() == Qt.Checked:
                keys.append(str(key))
        if self._max:
            keys = keys[: self._max]
        return keys


class TaskSignals(QObject):
    done = Signal(object)
    failed = Signal(str)


class _Task(QRunnable):
    def __init__(self, fn: Callable, signals: TaskSignals):
        super().__init__()
        self.fn = fn
        self.signals = signals

    def run(self) -> None:
        try:
            result = self.fn()
        except Exception as exc:  # noqa: BLE001 - reported to the UI
            self.signals.failed.emit(str(exc))
        else:
            self.signals.done.emit(result)


class TaskRunner(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pool = QThreadPool.globalInstance()
        self._tasks: list[_Task] = []

    def run(self, fn: Callable, on_done: Callable, on_error: Callable[[str], None] | None = None):
        signals = TaskSignals(self)
        task = _Task(fn, signals)
        self._tasks.append(task)
        signals.done.connect(on_done)
        signals.done.connect(lambda _: self._cleanup(task))
        if on_error:
            signals.failed.connect(on_error)
        signals.failed.connect(lambda _: self._cleanup(task))
        self.pool.start(task)

    def _cleanup(self, task: _Task) -> None:
        if task in self._tasks:
            self._tasks.remove(task)


def toolbar_row(*widgets, stretch_end: bool = True) -> QWidget:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    for widget in widgets:
        if widget is None:
            layout.addStretch(1)
        else:
            layout.addWidget(widget)
    if stretch_end:
        layout.addStretch(1)
    return container


def combo(items: list[tuple[str, str]], current: str | None = None) -> QComboBox:
    box = QComboBox()
    for key, label in items:
        box.addItem(label, key)
    if current:
        index = box.findData(current)
        if index >= 0:
            box.setCurrentIndex(index)
    box.setMinimumWidth(180)
    return box


def spin(minimum: int, maximum: int, value: int, suffix: str = "", step: int = 1) -> QSpinBox:
    box = QSpinBox()
    box.setRange(minimum, maximum)
    box.setValue(value)
    box.setSingleStep(step)
    if suffix:
        box.setSuffix(suffix)
    return box


def check(text: str, checked: bool = False) -> QCheckBox:
    box = QCheckBox(text)
    box.setChecked(checked)
    return box


def empty_state(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Muted")
    label.setAlignment(Qt.AlignCenter)
    label.setWordWrap(True)
    label.setMinimumHeight(120)
    return label


def error_box(parent, title: str, message: str) -> None:
    QMessageBox.critical(parent, title, message)
