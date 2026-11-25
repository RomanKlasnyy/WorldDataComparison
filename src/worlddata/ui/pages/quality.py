"""Data & Quality page: build metadata, coverage, diagnostics and settings."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...core.export import export_dataframe
from ..widgets import DataTable, KpiCard, PageHeader, section_label, toolbar_row
from .base import Page


class QualityPage(Page):
    def __init__(self, ctx, window, parent=None):
        super().__init__(ctx, window, parent)
        self._coverage = pd.DataFrame()
        self._missing = pd.DataFrame()
        self._sources = pd.DataFrame()
        self._diagnostics: dict[str, pd.DataFrame] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 20, 26, 20)
        layout.setSpacing(12)
        layout.addWidget(
            PageHeader(
                "Data & Quality",
                "Build provenance, indicator coverage, quarantined values and analysis settings.",
            )
        )

        cards = QHBoxLayout()
        cards.setSpacing(10)
        self.card_obs = KpiCard("Observations")
        self.card_inds = KpiCard("Indicators with data")
        self.card_countries = KpiCard("Entities with data")
        self.card_manual = KpiCard("Manual imports missing")
        self.card_size = KpiCard("Database size")
        for card in (
            self.card_obs,
            self.card_inds,
            self.card_countries,
            self.card_manual,
            self.card_size,
        ):
            cards.addWidget(card)
        layout.addLayout(cards)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        self._build_coverage_tab()
        self._build_missing_tab()
        self._build_sources_tab()
        self._build_diagnostics_tab()
        self._build_settings_tab()

    # ------------------------------------------------------------------ tabs
    def _build_coverage_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.coverage_search = None
        self.coverage_table = DataTable(search=True, search_placeholder="Filter indicators…")
        export_csv = QPushButton("Export CSV")
        export_csv.clicked.connect(lambda: self._export(self._coverage, "indicator_coverage.csv"))
        export_xlsx = QPushButton("Export XLSX")
        export_xlsx.clicked.connect(lambda: self._export(self._coverage, "indicator_coverage.xlsx"))
        layout.addWidget(
            toolbar_row(
                section_label("Indicator coverage"),
                None,
                export_csv,
                export_xlsx,
            )
        )
        layout.addWidget(self.coverage_table, 1)
        note = QLabel(
            "Coverage is the share of the 197 tracked states with a value at or after the recency cutoff. "
            "Stale counts countries whose latest value predates the cutoff. Manual indicators stay at 0% "
            "until imported."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.tabs.addTab(page, "Coverage")

    def _build_missing_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        self.missing_table = DataTable(search=True, search_placeholder="Filter countries…")
        layout.addWidget(section_label("Missing indicators by country (latest selection)"))
        layout.addWidget(self.missing_table, 1)
        note = QLabel(
            "Missing counts indicators with no observation at or after the cutoff. Sparse indicators such "
            "as literacy, PISA and hospital beds explain most gaps; gaps are never imputed or zero-filled."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.tabs.addTab(page, "Missing by country")

    def _build_sources_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(section_label("Sources, licences and attribution"))
        self.sources_table = DataTable()
        layout.addWidget(self.sources_table, 1)
        note = QLabel(
            "Public bundles must exclude sources marked non-redistributable. Composite and perception "
            "indices keep their upstream terms; see the About page for full attribution."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.tabs.addTab(page, "Sources")

    def _build_diagnostics_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        buttons = QHBoxLayout()
        open_folder = QPushButton("Open data folder")
        open_folder.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.ctx.paths.data)))
        )
        buttons.addWidget(open_folder)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.diag_summary = QLabel()
        self.diag_summary.setWordWrap(True)
        layout.addWidget(self.diag_summary)

        self.diag_table = DataTable(search=True, search_placeholder="Filter diagnostics…")
        layout.addWidget(section_label("Unresolved or skipped source rows"))
        layout.addWidget(self.diag_table, 1)

        note = QLabel(
            "Quarantined values are written to data/rejected.csv, unresolved source names to "
            "data/unresolved.csv, and rejected non-country entities to data/skipped_entities.csv. "
            "Nothing is silently dropped."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.tabs.addTab(page, "Diagnostics")

    def _build_settings_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        layout.addWidget(section_label("Analysis settings"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        grid.addWidget(QLabel("Recency cutoff year"), 0, 0)
        self.cutoff = QSpinBox()
        self.cutoff.setRange(2010, datetime.now(UTC).year)
        self.cutoff.setValue(self.ctx.settings.cutoff_year)
        self.cutoff.setToolTip(
            "Only values published in this year or later are used. Raising it filters stale series such as Gini."
        )
        grid.addWidget(self.cutoff, 0, 1)

        grid.addWidget(QLabel("Minimum countries per correlation"), 1, 0)
        self.min_n = QSpinBox()
        self.min_n.setRange(10, 150)
        self.min_n.setValue(self.ctx.settings.min_n)
        grid.addWidget(self.min_n, 1, 1)

        grid.addWidget(QLabel("Include dependent territories"), 2, 0)
        self.territories = QCheckBox("Show Hong Kong, Puerto Rico, Greenland, etc. as entities")
        self.territories.setChecked(self.ctx.settings.include_territories)
        grid.addWidget(self.territories, 2, 1)
        grid.setColumnStretch(2, 1)
        layout.addLayout(grid)

        apply_button = QPushButton("Apply settings")
        apply_button.setObjectName("Primary")
        apply_button.clicked.connect(self._apply_settings)
        reset_button = QPushButton("Reset to defaults")
        reset_button.clicked.connect(self._reset_settings)
        layout.addWidget(toolbar_row(apply_button, reset_button))

        self.settings_note = QLabel()
        self.settings_note.setObjectName("Muted")
        self.settings_note.setWordWrap(True)
        layout.addWidget(self.settings_note)

        layout.addWidget(section_label("Swapping in new data"))
        swap = QLabel(
            "The app never needs the network. To update statistics, run "
            "<code>python scripts/refresh_data.py</code> and replace "
            "<code>data/worlddata.sqlite</code> plus <code>data/manifest.json</code>. On startup the app "
            "checks the manifest's schema version and SHA-256 of the database; mismatches are refused with "
            "an explanation instead of loading inconsistent data."
        )
        swap.setWordWrap(True)
        swap.setObjectName("Muted")
        layout.addWidget(swap)
        layout.addStretch(1)
        self.tabs.addTab(page, "Settings")

    # ------------------------------------------------------------------ data
    def on_show(self) -> None:
        info = self.ctx.build_info()
        self.card_obs.set_value(f"{int(info.get('n_observations', 0)):,}")
        self.card_inds.set_value(
            str(len(self.ctx.repo.indicators(include_hidden=False, with_data=True)))
        )
        self.card_countries.set_value(str(info.get("n_countries", "—")))
        self.card_size.set_value(f"{info.get('db_size_mb', 0)} MB", f"schema {info.get('schema_version')}")
        self._load_reports()
        self._refresh_settings_note()

    def _load_reports(self) -> None:
        paths = self.ctx.paths
        if paths.quality_report.exists():
            self._coverage = pd.read_csv(paths.quality_report)
        else:
            self._coverage = pd.DataFrame()
        if not self._coverage.empty:
            view = self._coverage.rename(
                columns={
                    "name": "Indicator",
                    "domain": "Domain",
                    "source_id": "Source",
                    "n_countries": "Countries",
                    "pct": "Coverage",
                    "latest_year": "Latest year",
                    "n_stale": "Stale countries",
                    "unit": "Unit",
                    "attribution": "Attribution",
                }
            )[
                [
                    "Indicator",
                    "Domain",
                    "Source",
                    "Countries",
                    "Coverage",
                    "Latest year",
                    "Stale countries",
                    "Unit",
                ]
            ].copy()
            source_labels = {
                "worldbank": "World Bank",
                "worldbank_wgi": "World Bank WGI",
                "owid": "OWID",
                "imf": "IMF",
                "derived": "Derived",
                "manual": "Manual import",
            }
            view["Source"] = view["Source"].map(source_labels).fillna(view["Source"])
            self.coverage_table.set_frame(
                view,
                {
                    "Countries": "int",
                    "Coverage": "pct",
                    "Latest year": "year",
                    "Stale countries": "int",
                },
            )
            self.coverage_table.set_widths(
                {
                    "Indicator": 235,
                    "Domain": 150,
                    "Source": 100,
                    "Countries": 68,
                    "Coverage": 90,
                    "Latest year": 72,
                    "Stale countries": 100,
                    "Unit": 140,
                }
            )
        manual = (
            self._coverage[
                (self._coverage["source_id"] == "manual") & (self._coverage["n_countries"] == 0)
            ]
            if not self._coverage.empty
            else self._coverage
        )
        self.card_manual.set_value(
            str(len(manual)) if not self._coverage.empty else "—",
            "PISA, Freedom House, EPI, ND-GAIN, GPI, SPI",
        )

        ds = self.ctx.dataset()
        missing = ds.values.isna().sum(axis=1).rename("Missing indicators").to_frame()
        missing["Country"] = [ds.name(c) for c in missing.index]
        missing["Region"] = [ds.countries.loc[c, "region"] for c in missing.index]
        missing["Indicators with data"] = len(ds.indicators) - missing["Missing indicators"]
        missing["Coverage"] = (
            (len(ds.indicators) - missing["Missing indicators"]) / max(len(ds.indicators), 1) * 100
        ).round(1)
        missing = missing.sort_values("Missing indicators", ascending=False)
        self._missing = missing[["Country", "Region", "Missing indicators", "Indicators with data", "Coverage"]]
        self.missing_table.set_frame(
            self._missing,
            {"Missing indicators": "int", "Indicators with data": "int", "Coverage": "pct"},
        )

        sources = self.ctx.repo.sources().rename(
            columns={
                "name": "Source",
                "license": "Licence",
                "attribution": "Attribution",
                "redistributable": "Redistributable",
                "homepage": "Homepage",
            }
        )
        sources["Redistributable"] = sources["Redistributable"].map({1: "yes", 0: "no"})
        self._sources = sources
        self.sources_table.set_frame(sources[["Source", "Licence", "Redistributable", "Attribution"]])

        diag_parts = []
        labels = {
            "unresolved.csv": "Unresolved names",
            "skipped_entities.csv": "Skipped aggregates",
            "rejected.csv": "Quarantined values",
        }
        for filename, label in labels.items():
            path = self.ctx.paths.data / filename
            if path.exists():
                try:
                    frame = pd.read_csv(path)
                except pd.errors.EmptyDataError:
                    continue
                if frame.empty:
                    continue
                frame.insert(0, "Kind", label)
                diag_parts.append(frame)
        self._diagnostics = {"all": pd.concat(diag_parts, ignore_index=True) if diag_parts else pd.DataFrame()}
        rejected_path = self.ctx.paths.rejected
        rejected_rows = 0
        if rejected_path.exists():
            try:
                rejected_rows = len(pd.read_csv(rejected_path))
            except pd.errors.EmptyDataError:
                rejected_rows = 0
        unresolved_rows = 0
        unresolved_path = self.ctx.paths.data / "unresolved.csv"
        if unresolved_path.exists():
            try:
                unresolved_rows = len(pd.read_csv(unresolved_path))
            except pd.errors.EmptyDataError:
                unresolved_rows = 0
        self.diag_summary.setText(
            f"Quarantined values: <b>{rejected_rows}</b> · unresolved country names: "
            f"<b>{unresolved_rows}</b> · source: <code>{self.ctx.paths.data}</code>"
        )
        diagnostics = self._diagnostics["all"]
        if diagnostics.empty:
            diagnostics = pd.DataFrame(
                columns=["Kind", "indicator_id", "name", "code", "n", "latest_year", "year", "value", "reason"]
            )
        self.diag_table.set_frame(diagnostics)

    # ------------------------------------------------------------------ actions
    def _refresh_settings_note(self) -> None:
        self.cutoff.setValue(self.ctx.settings.cutoff_year)
        self.min_n.setValue(self.ctx.settings.min_n)
        self.territories.setChecked(self.ctx.settings.include_territories)
        ds = self.ctx.dataset()
        self.settings_note.setText(
            f"Current dataset: {len(ds.values)} entities × {len(ds.indicators)} indicators, "
            f"cutoff {ds.cutoff}. Changing the cutoff rebuilds the in-memory view; the database itself "
            f"retains 2010→present history."
        )

    def _apply_settings(self) -> None:
        self.ctx.settings.cutoff_year = int(self.cutoff.value())
        self.ctx.settings.min_n = int(self.min_n.value())
        self.ctx.settings.include_territories = bool(self.territories.isChecked())
        self.ctx.settings.save(self.ctx.paths.settings)
        self.ctx.invalidate()
        self.window.refresh_all()

    def _reset_settings(self) -> None:
        self.cutoff.setValue(2015)
        self.min_n.setValue(30)
        self.territories.setChecked(False)
        self._apply_settings()

    def _export(self, frame: pd.DataFrame, default_name: str) -> None:
        if frame.empty:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export",
            default_name,
            "CSV (*.csv);;Excel (*.xlsx)",
        )
        if path:
            try:
                export_dataframe(frame, Path(path))
            except Exception as exc:  # noqa: BLE001
                self.window.statusBar().showMessage(f"Export failed: {exc}", 6000)
