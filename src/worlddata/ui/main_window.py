"""Main window shell, navigation sidebar and Ctrl+K command palette."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from .theme import apply_qt_palette, apply_table_palettes, current_theme, qss, set_current_theme
from .widgets import TaskRunner

PAGE_ORDER = [
    ("dashboard", "Dashboard"),
    ("countries", "Countries"),
    ("rankings", "Rankings"),
    ("correlations", "Correlations"),
    ("groups", "Groups"),
    ("quality", "Data quality"),
    ("about", "About"),
]


class CommandPalette(QDialog):
    chosen = Signal(str, str)

    def __init__(self, window):
        super().__init__(window)
        self.setWindowTitle("Search countries and indicators")
        self.setModal(True)
        self.resize(620, 520)
        self._window = window
        self._entries: list[tuple[str, str, str, str]] = []
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type a country or indicator…")
        self.input.textChanged.connect(self._filter)
        self.results = QListWidget()
        self.results.itemActivated.connect(self._activate)
        self.results.itemClicked.connect(self._activate)
        layout = QVBoxLayout(self)
        layout.addWidget(self.input)
        layout.addWidget(self.results, 1)
        self._load()
        self._filter("")
        self.input.setFocus()

    def _load(self) -> None:
        ctx = self._window.ctx
        for row in ctx.country_rows().itertuples(index=False):
            self._entries.append(
                ("country", str(row.iso3), f"{row.name}", f"Country · {row.region}")
            )
        for row in ctx.indicator_rows().itertuples(index=False):
            self._entries.append(
                ("indicator", str(row.id), f"{row.name}", f"Indicator · {row.domain}")
            )

    def _filter(self, text: str) -> None:
        query = (text or "").strip().casefold()
        self.results.clear()
        shown = 0
        for kind, key, label, group in self._entries:
            if query and query not in label.casefold() and query not in group.casefold():
                continue
            item = QListWidgetItem(f"{label}    —    {group}")
            item.setData(Qt.UserRole, (kind, key))
            self.results.addItem(item)
            shown += 1
            if shown >= 60:
                break
        if self.results.count():
            self.results.setCurrentRow(0)

    def _activate(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.UserRole)
        if data:
            self.chosen.emit(data[0], data[1])
            self.accept()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and self.results.currentItem():
            self._activate(self.results.currentItem())
            return
        super().keyPressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle("WorldDataComparison — country statistics explorer")
        self.resize(1460, 940)
        self.setMinimumSize(1120, 720)
        self._pages: dict[str, QWidget] = {}
        self._nav: dict[str, QPushButton] = {}
        self.task_runner = TaskRunner(self)

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(218)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(14, 18, 14, 14)
        side.setSpacing(4)

        title = QLabel("WorldData Comparison")
        title.setObjectName("AppTitle")
        title.setWordWrap(True)
        subtitle = QLabel("Latest country statistics · correlations · groups")
        subtitle.setObjectName("AppSubtitle")
        subtitle.setWordWrap(True)
        side.addWidget(title)
        side.addWidget(subtitle)
        side.addSpacing(16)

        for index, (key, label) in enumerate(PAGE_ORDER, start=1):
            button = QPushButton(f"{label}")
            button.setObjectName("Nav")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda checked=False, k=key: self.navigate(k))
            button.setToolTip(f"Ctrl+{index}")
            side.addWidget(button)
            self._nav[key] = button

        side.addStretch(1)
        info = self.ctx.build_info()
        self.build_label = QLabel(self._build_caption(info))
        self.build_label.setObjectName("Muted")
        self.build_label.setWordWrap(True)
        side.addWidget(self.build_label)
        side.addSpacing(8)

        self.theme_button = QPushButton()
        self.theme_button.clicked.connect(self.toggle_theme)
        side.addWidget(self.theme_button)
        self._update_theme_button()

        self.stack = QStackedWidget()
        root.addWidget(sidebar)
        root.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        from .pages.about import AboutPage
        from .pages.correlations import CorrelationsPage
        from .pages.countries import CountriesPage
        from .pages.dashboard import DashboardPage
        from .pages.groups import GroupsPage
        from .pages.quality import QualityPage
        from .pages.rankings import RankingsPage

        classes = {
            "dashboard": DashboardPage,
            "countries": CountriesPage,
            "rankings": RankingsPage,
            "correlations": CorrelationsPage,
            "groups": GroupsPage,
            "quality": QualityPage,
            "about": AboutPage,
        }
        for key, _label in PAGE_ORDER:
            page = classes[key](self.ctx, self)
            self._pages[key] = page
            self.stack.addWidget(page)

        self.status_label = QLabel()
        self.statusBar().addWidget(self.status_label, 1)
        self.statusBar().addPermanentWidget(
            QLabel(f"Schema {info.get('schema_version', '?')} · v{__version__}")
        )
        self._update_status(info)

        for index, (key, _label) in enumerate(PAGE_ORDER, start=1):
            action = QAction(self)
            action.setShortcut(QKeySequence(f"Ctrl+{index}"))
            action.triggered.connect(lambda checked=False, k=key: self.navigate(k))
            self.addAction(action)
        search_action = QAction(self)
        search_action.setShortcut(QKeySequence("Ctrl+K"))
        search_action.triggered.connect(self.open_palette)
        self.addAction(search_action)

        start = self.ctx.settings.last_page
        self.navigate(start if start in self._pages else "dashboard")
        apply_table_palettes(QApplication.instance(), self.ctx.settings.theme)

    # --------------------------------------------------------------- navigation
    def navigate(self, key: str) -> None:
        if key not in self._pages:
            key = "dashboard"
        page = self._pages[key]
        self.stack.setCurrentWidget(page)
        for nav_key, button in self._nav.items():
            button.setChecked(nav_key == key)
        self.ctx.settings.last_page = key
        page.on_show()

    def refresh_all(self) -> None:
        info = self.ctx.build_info()
        self.build_label.setText(self._build_caption(info))
        self._update_status(info)
        current = self.stack.currentWidget()
        hook = getattr(current, "on_show", None)
        if hook:
            hook()

    def open_country(self, iso3: str) -> None:
        self.navigate("countries")
        page = self._pages["countries"]
        if hasattr(page, "select_country"):
            page.select_country(iso3)

    def open_indicator(self, indicator_id: str) -> None:
        self.navigate("rankings")
        page = self._pages["rankings"]
        if hasattr(page, "select_indicator"):
            page.select_indicator(indicator_id)

    def open_palette(self) -> None:
        dialog = CommandPalette(self)
        dialog.chosen.connect(self._handle_palette_choice)
        dialog.exec()

    def _handle_palette_choice(self, kind: str, key: str) -> None:
        if kind == "country":
            self.open_country(key)
        else:
            self.open_indicator(key)

    # ------------------------------------------------------------------- theme
    def toggle_theme(self) -> None:
        theme = "light" if current_theme() == "dark" else "dark"
        set_current_theme(theme)
        QApplication.instance().setStyleSheet(qss(theme))
        apply_qt_palette(QApplication.instance(), theme)
        apply_table_palettes(QApplication.instance(), theme)
        self.ctx.settings.theme = theme
        self.ctx.settings.save(self.ctx.paths.settings)
        self._update_theme_button()
        for page in self._pages.values():
            hook = getattr(page, "on_theme_changed", None)
            if hook:
                hook()

    def _update_theme_button(self) -> None:
        self.theme_button.setText(
            "Switch to light theme" if current_theme() == "dark" else "Switch to dark theme"
        )

    # ------------------------------------------------------------------ status
    def _build_caption(self, info: dict) -> str:
        built = str(info.get("built_at", ""))[:10]
        with_data = len(self.ctx.repo.indicators(with_data=True))
        return (
            f"Data build {built}\n"
            f"{with_data} indicators · {info.get('n_countries', '?')} countries\n"
            f"Latest-value cutoff {info.get('recency_cutoff_year', self.ctx.settings.cutoff_year)}"
        )

    def _update_status(self, info: dict) -> None:
        self.status_label.setText(
            f"Build {info.get('build_id', '—')} · "
            f"{int(info.get('n_observations', 0)):,} observations · "
            f"{info.get('db_size_mb', 0)} MB · Ctrl+K to search · Ctrl+1…7 to switch pages"
        )

    def closeEvent(self, event) -> None:
        try:
            self.ctx.settings.save(self.ctx.paths.settings)
        except Exception:  # noqa: BLE001 - never block closing
            pass
        super().closeEvent(event)
