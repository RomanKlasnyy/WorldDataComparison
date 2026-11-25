"""Dashboard: headline coverage, top-country chart and quick navigation."""

from __future__ import annotations

import numpy as np
import pandas as pd
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ...core.views import domain_coverage, rank_table
from ..theme import current_palette
from ..widgets import ChartPanel, KpiCard, PageHeader, section_label
from .base import Page


class DashboardPage(Page):
    def __init__(self, ctx, window, parent=None):
        super().__init__(ctx, window, parent)
        self._indicator = self.ctx.settings.last_indicator

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 20, 26, 20)
        layout.setSpacing(12)
        layout.addWidget(
            PageHeader(
                "WorldData Comparison",
                "Compare the latest available statistics for 197 countries, test correlations and compare "
                "country groups — entirely offline.",
            )
        )

        cards = QHBoxLayout()
        cards.setSpacing(10)
        self.card_countries = KpiCard("Countries with data")
        self.card_indicators = KpiCard("Indicators in view")
        self.card_year = KpiCard("Newest observation")
        self.card_coverage = KpiCard("Median indicator coverage")
        self.card_groups = KpiCard("Country groups")
        for card in (
            self.card_countries,
            self.card_indicators,
            self.card_year,
            self.card_coverage,
            self.card_groups,
        ):
            cards.addWidget(card)
        layout.addLayout(cards)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(QLabel("Indicator"))
        self.indicator_combo = QComboBox()
        self.indicator_combo.setMinimumWidth(340)
        self.indicator_combo.currentIndexChanged.connect(self._combo_changed)
        controls.addWidget(self.indicator_combo)
        controls.addStretch(1)
        self.open_corr = QPushButton("Explore correlations →")
        self.open_corr.setObjectName("Primary")
        self.open_corr.clicked.connect(lambda: self.window.navigate("correlations"))
        self.open_groups = QPushButton("Compare groups")
        self.open_groups.clicked.connect(lambda: self.window.navigate("groups"))
        self.open_countries = QPushButton("Country profile")
        self.open_countries.clicked.connect(lambda: self.window.navigate("countries"))
        controls.addWidget(self.open_corr)
        controls.addWidget(self.open_groups)
        controls.addWidget(self.open_countries)
        layout.addLayout(controls)

        columns = QHBoxLayout()
        columns.setSpacing(12)
        left = QVBoxLayout()
        left.addWidget(section_label("Top 15 countries"))
        self.rank_chart = ChartPanel(height=360)
        left.addWidget(self.rank_chart, 1)
        columns.addLayout(left, 3)

        right = QVBoxLayout()
        right.addWidget(section_label("Coverage by domain"))
        self.domain_chart = ChartPanel(height=240)
        right.addWidget(self.domain_chart, 2)
        self.note = QLabel()
        self.note.setObjectName("Muted")
        self.note.setWordWrap(True)
        right.addWidget(self.note)
        columns.addLayout(right, 2)
        layout.addLayout(columns, 1)

        self.footnote = QLabel()
        self.footnote.setObjectName("Muted")
        self.footnote.setWordWrap(True)
        layout.addWidget(self.footnote)

    # ------------------------------------------------------------------ data
    def on_show(self) -> None:
        ds = self.ctx.dataset()
        info = self.ctx.build_info()
        with_data = ds.values.notna().any(axis=1).sum()
        self.card_countries.set_value(str(int(with_data)), "at or after cutoff")
        self.card_indicators.set_value(str(len(ds.indicators)), f"cutoff {ds.cutoff}")
        newest_values = ds.years.to_numpy(dtype=float, na_value=np.nan)
        newest = int(np.nanmax(newest_values)) if np.isfinite(newest_values).any() else None
        self.card_year.set_value(str(newest or "—"), "source year")
        coverage = ds.values.notna().mean().median() * 100 if len(ds.indicators) else 0
        self.card_coverage.set_value(f"{coverage:.0f}%", "share of 197 states")
        self.card_groups.set_value(str(len(self.ctx.group_set().groups)), "economic, military, cultural…")

        self.indicator_combo.blockSignals(True)
        self.indicator_combo.clear()
        for row in self.ctx.indicator_rows().itertuples(index=False):
            self.indicator_combo.addItem(f"{row.name}  ·  {row.domain}", row.id)
        if self._indicator not in ds.indicator_ids and ds.indicator_ids:
            self._indicator = ds.indicator_ids[0]
        index = self.indicator_combo.findData(self._indicator)
        if index >= 0:
            self.indicator_combo.setCurrentIndex(index)
        self.indicator_combo.blockSignals(False)

        self._render_rank()
        self._render_domains()

        stale = 0
        stale_text = ""
        if self.ctx.paths.quality_report.exists():
            report = pd.read_csv(self.ctx.paths.quality_report)
            stale = int((report["n_stale"] > 0).sum())
            stale_text = f" {stale} indicators still contain pre-cutoff values for some countries."
        self.note.setText(
            f"Values are the newest observation at or after {ds.cutoff}. "
            f"Six indices (PISA, Freedom House, EPI, ND-GAIN, GPI, SPI) require manual import.{stale_text}"
        )
        self.footnote.setText(
            f"Build {info.get('build_id', '—')} · {int(info.get('n_observations', 0)):,} observations · "
            "Use Ctrl+K to jump to a country or indicator."
        )

    def _combo_changed(self) -> None:
        value = self.indicator_combo.currentData()
        if value:
            self._indicator = str(value)
            self.ctx.settings.last_indicator = self._indicator
            self.ctx.settings.save(self.ctx.paths.settings)
            self._render_rank()

    def _render_rank(self) -> None:
        ds = self.ctx.dataset()
        if self._indicator not in ds.indicator_ids:
            self.rank_chart.message("No observations for this indicator at the current cutoff.")
            return
        table = rank_table(ds, self._indicator).head(15)
        if table.empty:
            self.rank_chart.message("No observations at the current cutoff.")
            return
        meta = ds.indicators.loc[self._indicator]
        colors = current_palette()
        ax = self.rank_chart.reset()
        names = table["country"].tolist()[::-1]
        values = table["value"].tolist()[::-1]
        y = np.arange(len(names))
        bars = ax.barh(y, values, color=colors["accent"], height=0.68)
        ax.set_yticks(y, names)
        ax.set_title(f"{meta['name']} — top 15 ({meta['unit']})", loc="left")
        ax.grid(axis="x", alpha=0.5)
        ax.grid(axis="y", visible=False)
        ax.spines[["top", "right", "left"]].set_visible(False)
        span = max(values) - min(min(values), 0)
        ax.set_xlim(min(min(values), 0), max(max(values) * 1.16, 1e-9))
        for bar, value in zip(bars, values, strict=False):
            ax.text(
                bar.get_width() + span * 0.01,
                bar.get_y() + bar.get_height() / 2,
                f"{value:,.2f}".rstrip("0").rstrip("."),
                va="center",
                fontsize=7.5,
                color=colors["muted"],
            )
        self.rank_chart.figure.subplots_adjust(left=0.24, right=0.98, top=0.9, bottom=0.08)
        self.rank_chart.draw()

    def _render_domains(self) -> None:
        ds = self.ctx.dataset()
        frame = domain_coverage(ds)
        if frame.empty:
            self.domain_chart.message("No coverage data.")
            return
        grouped = (
            frame.groupby("domain", sort=False)["coverage_pct"]
            .mean()
            .sort_values()
        )
        colors = current_palette()
        ax = self.domain_chart.reset()
        y = np.arange(len(grouped))
        ax.barh(y, grouped.values, color=colors["good"], height=0.62)
        ax.set_yticks(y, grouped.index)
        ax.set_xlim(0, 100)
        ax.set_xlabel("% of tracked states with data")
        ax.grid(axis="x", alpha=0.5)
        ax.grid(axis="y", visible=False)
        ax.spines[["top", "right", "left"]].set_visible(False)
        for yi, value in zip(y, grouped.values, strict=False):
            ax.text(value + 1.5, yi, f"{value:.0f}%", va="center", fontsize=7.5, color=colors["muted"])
        self.domain_chart.figure.subplots_adjust(left=0.42, right=0.97, top=0.95, bottom=0.16)
        self.domain_chart.draw()

    def on_theme_changed(self) -> None:
        self.rank_chart.apply_theme(self.ctx.settings.theme)
        self.domain_chart.apply_theme(self.ctx.settings.theme)
        self._render_rank()
        self._render_domains()
