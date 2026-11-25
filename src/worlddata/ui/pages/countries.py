"""Countries page: searchable profiles, sparklines, side-by-side comparison and radar."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...core.export import export_dataframe
from ...core.views import compare_percentiles, compare_table, country_profile
from ..theme import current_palette
from ..widgets import (
    ChartPanel,
    CheckListDialog,
    DataTable,
    PageHeader,
    SearchableList,
    section_label,
)
from .base import Page

RADAR_INDICATORS = [
    "gdp_per_capita_ppp",
    "life_expectancy",
    "hdi",
    "mean_years_schooling",
    "vdem_liberal_democracy",
    "cpi",
    "internet_users",
    "happiness",
]

RADAR_LABELS = {
    "gdp_per_capita_ppp": "GDP pc",
    "life_expectancy": "Life exp.",
    "hdi": "HDI",
    "mean_years_schooling": "Schooling",
    "vdem_liberal_democracy": "Democracy",
    "cpi": "CPI",
    "internet_users": "Internet",
    "happiness": "Happiness",
}


class CountriesPage(Page):
    def __init__(self, ctx, window, parent=None):
        super().__init__(ctx, window, parent)
        self._iso3 = self.ctx.settings.last_country or "USA"
        self._profile = pd.DataFrame()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 20, 26, 20)
        layout.setSpacing(10)
        layout.addWidget(
            PageHeader(
                "Countries",
                "Search a country, inspect every indicator with its source year and world rank, or compare "
                "up to six countries on a common percentile scale.",
            )
        )

        splitter = QSplitter(Qt.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        left_layout.addWidget(section_label("Countries"))
        self.country_list = SearchableList("Search countries…")
        self.country_list.item_selected.connect(self._country_selected)
        left_layout.addWidget(self.country_list, 1)
        left.setMinimumWidth(250)
        left.setMaximumWidth(320)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        header_row = QHBoxLayout()
        self.title = QLabel()
        self.title.setObjectName("PageTitle")
        self.meta = QLabel()
        self.meta.setObjectName("Muted")
        header_row.addWidget(self.title)
        header_row.addSpacing(10)
        header_row.addWidget(self.meta)
        header_row.addStretch(1)
        self.compare_button = QPushButton("Compare countries…")
        self.compare_button.clicked.connect(self._choose_compare)
        self.export_button = QPushButton("Export profile")
        self.export_button.clicked.connect(self._export_profile)
        header_row.addWidget(self.compare_button)
        header_row.addWidget(self.export_button)
        right_layout.addLayout(header_row)

        self.tabs = QTabWidget()
        right_layout.addWidget(self.tabs, 1)

        profile_tab = QWidget()
        profile_layout = QVBoxLayout(profile_tab)
        profile_layout.setContentsMargins(10, 10, 10, 10)
        profile_split = QSplitter(Qt.Vertical)
        self.profile_table = DataTable(search=True, search_placeholder="Filter indicators…")
        self.profile_table.view.selectionModel().selectionChanged.connect(self._row_selected)
        profile_split.addWidget(self.profile_table)
        history_container = QWidget()
        history_layout = QVBoxLayout(history_container)
        history_layout.setContentsMargins(0, 0, 0, 0)
        history_layout.addWidget(section_label("History (2010 → present)"))
        self.history_chart = ChartPanel(height=220)
        history_layout.addWidget(self.history_chart)
        profile_split.addWidget(history_container)
        profile_split.setSizes([480, 260])
        profile_layout.addWidget(profile_split)
        self.tabs.addTab(profile_tab, "Profile")

        compare_tab = QWidget()
        compare_layout = QVBoxLayout(compare_tab)
        compare_layout.setContentsMargins(10, 10, 10, 10)
        self.compare_caption = QLabel()
        self.compare_caption.setObjectName("Muted")
        self.compare_caption.setWordWrap(True)
        compare_layout.addWidget(self.compare_caption)
        compare_split = QSplitter(Qt.Horizontal)
        self.radar_chart = ChartPanel(height=340)
        compare_split.addWidget(self.radar_chart)
        self.compare_table = DataTable(search=True, search_placeholder="Filter indicators…")
        compare_split.addWidget(self.compare_table)
        compare_split.setSizes([470, 720])
        compare_layout.addWidget(compare_split, 1)
        self.tabs.addTab(compare_tab, "Compare")

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

    # ------------------------------------------------------------------ list
    def on_show(self) -> None:
        rows = self.ctx.country_rows()
        items = [
            (
                str(row.iso3),
                str(row.name),
                str(row.continent or row.region or "Other"),
            )
            for row in rows.itertuples(index=False)
        ]
        items.sort(key=lambda item: (item[2], item[1]))
        self.country_list.set_items(items)
        valid = {item[0] for item in items}
        preferred = self.ctx.settings.last_country
        if preferred not in valid and items:
            preferred = items[0][0]
        self._iso3 = preferred
        self.select_country(preferred)
        self._render_compare()

    def select_country(self, iso3: str) -> None:
        self._iso3 = iso3
        self.ctx.settings.last_country = iso3
        self.ctx.settings.save(self.ctx.paths.settings)
        self.country_list.search.clear()
        self.country_list.set_current(iso3)
        self._render_profile()

    def _country_selected(self, iso3: str) -> None:
        if iso3 and iso3 != self._iso3:
            self._iso3 = iso3
            self.ctx.settings.last_country = iso3
            self.ctx.settings.save(self.ctx.paths.settings)
            self._render_profile()

    # --------------------------------------------------------------- profile
    def _render_profile(self) -> None:
        ds = self.ctx.dataset()
        if self._iso3 not in ds.countries.index:
            self.title.setText(self._iso3)
            self.meta.setText("No data")
            self.profile_table.set_frame(pd.DataFrame())
            self.history_chart.message("No observations.")
            return
        row = ds.countries.loc[self._iso3]
        self.title.setText(str(row["name"]))
        details = [str(row["region"]), str(row["income_group"]), str(row["continent"])]
        details = list(dict.fromkeys(d for d in details if d and d != "nan"))
        if row["entity_type"] != "state":
            details.append(f"{row['entity_type']} entity")
        self.meta.setText(" · ".join(details))

        profile = country_profile(ds, self._iso3)
        self._profile = profile
        if profile.empty:
            self.profile_table.set_frame(pd.DataFrame())
            self.history_chart.message("No observations at the current cutoff.")
            return
        view = profile.rename(
            columns={
                "indicator": "Indicator",
                "domain": "Domain",
                "unit": "Unit",
                "value": "Value",
                "year": "Year",
                "rank": "Rank",
                "n": "Countries",
                "better_pct": "Percentile",
            }
        )[
            [
                "Indicator",
                "Domain",
                "Value",
                "Unit",
                "Year",
                "Rank",
                "Countries",
                "Percentile",
            ]
        ]
        self.profile_table.set_frame(
            view,
            {
                "Value": "num",
                "Year": "year",
                "Rank": "int",
                "Countries": "int",
                "Percentile": "pct",
            },
        )
        self.profile_table.set_widths(
            {
                "Indicator": 250,
                "Domain": 150,
                "Value": 95,
                "Unit": 125,
                "Year": 60,
                "Rank": 55,
                "Countries": 70,
                "Percentile": 105,
            }
        )
        if self.profile_table.view.selectionModel().selectedRows():
            pass
        else:
            self.profile_table.view.selectRow(0)
        self._render_history()

    def _row_selected(self, *_args) -> None:
        self._render_history()

    def _render_history(self) -> None:
        if self._profile.empty:
            return
        row = self.profile_table.selected_source_row()
        if row is None or row >= len(self._profile):
            row = 0
        indicator_id = str(self._profile.iloc[row]["indicator_id"])
        history = self.ctx.repo.country_history(self._iso3, indicator_id)
        meta = self.ctx.dataset().indicators.loc[indicator_id]
        if history.empty:
            self.history_chart.message("No history stored for this indicator.")
            return
        colors = current_palette()
        ax = self.history_chart.reset()
        ax.plot(
            history["year"],
            history["value"],
            color=colors["accent"],
            linewidth=1.8,
            marker="o",
            markersize=3.4,
        )
        ax.set_ylabel(str(meta["unit"]))
        ax.set_title(f"{meta['name']} — {self.ctx.dataset().name(self._iso3)}", loc="left")
        ax.grid(axis="x", visible=False)
        ax.spines[["top", "right"]].set_visible(False)
        if len(history) > 1:
            ax.set_xlim(history["year"].min() - 0.5, history["year"].max() + 0.5)
        self.history_chart.figure.subplots_adjust(left=0.10, right=0.99, top=0.80, bottom=0.18)
        self.history_chart.draw()

    # --------------------------------------------------------------- compare
    def _choose_compare(self) -> None:
        items = [
            (str(row.iso3), str(row.name), str(row.region))
            for row in self.ctx.country_rows().itertuples(index=False)
        ]
        dialog = CheckListDialog(
            "Compare countries",
            items,
            checked=self.ctx.settings.compare_countries,
            parent=self,
            max_checks=6,
        )
        if dialog.exec():
            selected = dialog.selected()
            if len(selected) >= 2:
                self.ctx.settings.compare_countries = selected
                self.ctx.settings.save(self.ctx.paths.settings)
                self._render_compare()

    def _render_compare(self) -> None:
        codes = [
            c
            for c in self.ctx.settings.compare_countries
            if c in self.ctx.dataset().countries.index
        ]
        if len(codes) < 2:
            self.compare_caption.setText("Select at least two countries.")
            self.compare_table.set_frame(pd.DataFrame())
            self.radar_chart.message("Choose two or more countries to compare.")
            return
        ds = self.ctx.dataset()
        self.compare_caption.setText(
            "Values are raw units (each row is one indicator). The radar uses direction-aware percentiles "
            "among the tracked states, 100 = best. Missing axes are treated as 0."
        )
        table = compare_table(ds, codes)
        value_columns = [f"{c}|value" for c in codes]
        view = table[["indicator", "domain", "unit", *value_columns]].rename(
            columns={
                "indicator": "Indicator",
                "domain": "Domain",
                "unit": "Unit",
                **{f"{c}|value": ds.name(c) for c in codes},
            }
        )
        self.compare_table.set_frame(view, {ds.name(c): "num" for c in codes})
        self.compare_table.set_widths(
            {
                "Indicator": 155,
                "Domain": 90,
                "Unit": 70,
                **{ds.name(code): 90 for code in codes},
            }
        )
        self._render_radar(codes)

    def _render_radar(self, codes: list[str]) -> None:
        ds = self.ctx.dataset()
        available = [i for i in RADAR_INDICATORS if i in ds.indicator_ids]
        if len(available) < 3:
            self.radar_chart.message("Not enough indicator coverage for a radar chart.")
            return
        pct = compare_percentiles(ds.subset_indicators(available), codes)
        labels = [RADAR_LABELS.get(indicator_id, ds.indicator_name(indicator_id)) for indicator_id in available]
        angles = np.linspace(0, 2 * np.pi, len(available), endpoint=False).tolist()
        angles += angles[:1]
        colors = current_palette()
        ax = self.radar_chart.reset(projection="polar")
        for index, code in enumerate(codes):
            values = pct[code].fillna(0).to_numpy(dtype=float).tolist()
            values += values[:1]
            color = colors["series"][index % len(colors["series"])]
            ax.plot(angles, values, color=color, linewidth=1.7, label=ds.name(code))
            ax.fill(angles, values, color=color, alpha=0.07)
        ax.set_xticks(angles[:-1], labels, fontsize=7.2)
        ax.tick_params(axis="x", pad=2)
        ax.set_ylim(0, 100)
        ax.set_yticks([25, 50, 75, 100], ["25", "50", "75", "100"], fontsize=6.5, color=colors["muted"])
        ax.grid(color=colors["grid"], alpha=0.7)
        ax.spines["polar"].set_color(colors["border"])
        handles, legend_labels = ax.get_legend_handles_labels()
        self.radar_chart.figure.legend(
            handles,
            legend_labels,
            loc="lower center",
            ncol=min(4, len(codes)),
            fontsize=7,
            frameon=False,
            labelcolor=colors["text"],
        )
        self.radar_chart.figure.subplots_adjust(left=0.17, right=0.83, top=0.94, bottom=0.20)
        self.radar_chart.draw()

    # --------------------------------------------------------------- actions
    def _export_profile(self) -> None:
        if self._profile.empty:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export profile", f"{self._iso3}_profile.csv", "CSV (*.csv);;Excel (*.xlsx)"
        )
        if path:
            try:
                export_dataframe(self._profile, Path(path))
                self.window.statusBar().showMessage(f"Exported {path}", 5000)
            except Exception as exc:  # noqa: BLE001
                self.window.statusBar().showMessage(f"Export failed: {exc}", 6000)

    def on_theme_changed(self) -> None:
        self.history_chart.apply_theme(self.ctx.settings.theme)
        self.radar_chart.apply_theme(self.ctx.settings.theme)
        self._render_history()
        self._render_compare()
