"""Rankings page: pick an indicator and explore the full country distribution."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ...core.export import export_dataframe
from ...core.views import indicator_summary, rank_table
from ..theme import current_palette
from ..widgets import ChartPanel, DataTable, PageHeader, SearchableList, section_label
from .base import Page


class RankingsPage(Page):
    def __init__(self, ctx, window, parent=None):
        super().__init__(ctx, window, parent)
        self._indicator = self.ctx.settings.last_indicator
        self._table = pd.DataFrame()
        self._view = pd.DataFrame()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 20, 26, 20)
        layout.setSpacing(10)
        layout.addWidget(
            PageHeader(
                "Rankings",
                "Sort and filter every tracked state for one indicator. Bars show a direction-aware "
                "percentile (100 = best when the indicator has a direction, otherwise the highest value). "
                "Double-click a row for the country profile.",
            )
        )

        splitter = QSplitter(Qt.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(section_label("Indicators"))
        self.indicator_list = SearchableList("Search indicators…")
        self.indicator_list.item_selected.connect(self._indicator_selected)
        left_layout.addWidget(self.indicator_list, 1)
        left.setMinimumWidth(260)
        left.setMaximumWidth(340)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        self.title = QLabel()
        self.title.setObjectName("SectionTitle")
        self.meta = QLabel()
        self.meta.setObjectName("Muted")
        self.meta.setWordWrap(True)
        right_layout.addWidget(self.title)
        right_layout.addWidget(self.meta)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(QLabel("Region"))
        self.region = QComboBox()
        self.region.currentIndexChanged.connect(self._render_table)
        controls.addWidget(self.region)
        controls.addWidget(QLabel("Income"))
        self.income = QComboBox()
        self.income.currentIndexChanged.connect(self._render_table)
        controls.addWidget(self.income)
        controls.addStretch(1)
        self.csv_button = QPushButton("Export CSV")
        self.csv_button.clicked.connect(lambda: self._export("csv"))
        self.xlsx_button = QPushButton("Export XLSX")
        self.xlsx_button.clicked.connect(lambda: self._export("xlsx"))
        self.png_button = QPushButton("Save chart")
        self.png_button.clicked.connect(lambda: self.chart.save_dialog(self, f"{self._indicator}.png"))
        controls.addWidget(self.csv_button)
        controls.addWidget(self.xlsx_button)
        controls.addWidget(self.png_button)
        right_layout.addLayout(controls)

        self.dist_chart = ChartPanel(height=210)
        right_layout.addWidget(self.dist_chart)

        self.table = DataTable(search=True, search_placeholder="Filter countries…")
        self.table.view.doubleClicked.connect(self._open_country)
        right_layout.addWidget(self.table, 1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

    # ------------------------------------------------------------------ data
    def on_show(self) -> None:
        items = [
            (str(row.id), str(row.name), str(row.domain))
            for row in self.ctx.indicator_rows().itertuples(index=False)
        ]
        self.indicator_list.set_items(items)
        if self._indicator not in self.ctx.dataset().indicator_ids and items:
            self._indicator = items[0][0]
        self.select_indicator(self._indicator)

    def select_indicator(self, indicator_id: str) -> None:
        self._indicator = indicator_id
        self.ctx.settings.last_indicator = indicator_id
        self.ctx.settings.save(self.ctx.paths.settings)
        self.indicator_list.search.clear()
        self.indicator_list.set_current(indicator_id)
        self._render()

    def _indicator_selected(self, indicator_id: str) -> None:
        if indicator_id and indicator_id != self._indicator:
            self._indicator = indicator_id
            self.ctx.settings.last_indicator = indicator_id
            self.ctx.settings.save(self.ctx.paths.settings)
            self._render()

    def _render(self) -> None:
        ds = self.ctx.dataset()
        if self._indicator not in ds.indicator_ids:
            self.title.setText("Indicator unavailable")
            self.meta.setText("It has no observations at the current recency cutoff.")
            self.table.set_frame(pd.DataFrame())
            self.dist_chart.message("No data.")
            return
        table = rank_table(ds, self._indicator)
        self._table = table
        summary = indicator_summary(ds, self._indicator)
        self.title.setText(str(summary["name"]))
        direction = summary.get("higher_is_better")
        direction_text = "higher is better" if direction else ("lower is better" if direction is False else "neutral direction")
        composite = " · composite index" if summary.get("is_composite") else ""
        self.meta.setText(
            f"{summary['description']}\n"
            f"{summary['n']} countries · {summary['coverage_pct']}% coverage · median source year "
            f"{(summary['median_year'] or 0):.0f} · {direction_text}{composite} · {summary['unit']}"
        )
        self._populate_filters(table)
        self._render_chart(table, summary)
        self._render_table()

    def _populate_filters(self, table: pd.DataFrame) -> None:
        for box, column in ((self.region, "region"), (self.income, "income_group")):
            current = box.currentData()
            box.blockSignals(True)
            box.clear()
            box.addItem("All", None)
            for value in sorted({str(v) for v in table[column].dropna().unique()}):
                box.addItem(value, value)
            index = box.findData(current)
            box.setCurrentIndex(max(index, 0))
            box.blockSignals(False)

    def _filtered(self) -> pd.DataFrame:
        table = self._table
        if table.empty:
            return table
        region = self.region.currentData()
        income = self.income.currentData()
        if region:
            table = table[table["region"] == region]
        if income:
            table = table[table["income_group"] == income]
        return table

    def _render_chart(self, table: pd.DataFrame, summary: dict) -> None:
        values = table["value"].dropna()
        if values.empty:
            self.dist_chart.message("No values to plot.")
            return
        colors = current_palette()
        ax = self.dist_chart.reset()
        bins = min(24, max(8, int(np.sqrt(len(values)))))
        ax.hist(values, bins=bins, color=colors["accent"], alpha=0.85, edgecolor=colors["panel"])
        median = float(values.median())
        ax.axvline(median, color=colors["warn"], linewidth=1.4, linestyle="--", label=f"median {median:,.2f}")
        ax.set_xlabel(str(summary["unit"]))
        ax.set_ylabel("countries")
        ax.set_title(f"Distribution · {summary['name']}", loc="left")
        ax.legend(fontsize=7.5, loc="upper right")
        ax.spines[["top", "right"]].set_visible(False)
        self.dist_chart.figure.subplots_adjust(left=0.08, right=0.98, top=0.86, bottom=0.22)
        self.dist_chart.draw()

    def _render_table(self) -> None:
        table = self._filtered()
        if table.empty:
            self.table.set_frame(pd.DataFrame())
            return
        view = table[
            ["rank", "country", "value", "year", "better_pct", "region", "income_group", "iso3"]
        ].rename(
            columns={
                "rank": "Rank",
                "country": "Country",
                "value": "Value",
                "year": "Year",
                "better_pct": "Percentile",
                "region": "Region",
                "income_group": "Income",
                "iso3": "ISO3",
            }
        )
        self._view = view
        self.table.set_frame(
            view,
            {
                "Rank": "int",
                "Value": "num",
                "Year": "year",
                "Percentile": "pct",
            },
        )
        self.table.view.setColumnHidden(len(view.columns) - 1, True)

    # --------------------------------------------------------------- actions
    def _open_country(self, index) -> None:
        source_row = self.table.selected_source_row()
        if source_row is None or source_row >= len(self._view):
            return
        self.window.open_country(str(self._view.iloc[source_row]["ISO3"]))

    def _export(self, kind: str) -> None:
        if self._table.empty:
            return
        suffix = "xlsx" if kind == "xlsx" else "csv"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export ranking",
            f"{self._indicator}.{suffix}",
            "Excel (*.xlsx)" if kind == "xlsx" else "CSV (*.csv)",
        )
        if not path:
            return
        try:
            export_dataframe(self._table, Path(path))
            self.window.statusBar().showMessage(f"Exported {path}", 5000)
        except Exception as exc:  # noqa: BLE001
            self.window.statusBar().showMessage(f"Export failed: {exc}", 6000)

    def on_theme_changed(self) -> None:
        self.dist_chart.apply_theme(self.ctx.settings.theme)
        self._render()
