"""Groups page: compare alliances, blocs and cultural families on one indicator."""

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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...core.export import export_dataframe
from ...core.groups import (
    compare,
    member_table,
    reset_overlay,
    save_group_members,
    summarize,
)
from ..theme import current_palette
from ..widgets import (
    ChartPanel,
    CheckListDialog,
    DataTable,
    PageHeader,
    section_label,
)
from .base import Page


class GroupsPage(Page):
    def __init__(self, ctx, window, parent=None):
        super().__init__(ctx, window, parent)
        self._indicator = self.ctx.settings.group_indicator
        self._comparison = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 20, 26, 20)
        layout.setSpacing(8)
        layout.addWidget(
            PageHeader(
                "Groups",
                "Compare economic blocs, military alliances, continents, income tiers and cultural "
                "families. Groups may overlap; every aggregate shows its coverage.",
            )
        )

        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(QLabel("Indicator"))
        self.indicator_combo = QComboBox()
        self.indicator_combo.setMinimumWidth(340)
        self.indicator_combo.currentIndexChanged.connect(self._indicator_changed)
        controls.addWidget(self.indicator_combo)
        self.choose_button = QPushButton("Select groups…")
        self.choose_button.clicked.connect(self._choose_groups)
        controls.addWidget(self.choose_button)
        self.edit_button = QPushButton("Edit membership…")
        self.edit_button.clicked.connect(self._edit_membership)
        controls.addWidget(self.edit_button)
        self.reset_button = QPushButton("Reset local edits")
        self.reset_button.clicked.connect(self._reset_edits)
        controls.addWidget(self.reset_button)
        controls.addStretch(1)
        self.export_button = QPushButton("Export summary")
        self.export_button.clicked.connect(self._export_summary)
        controls.addWidget(self.export_button)
        layout.addLayout(controls)

        self.selection_label = QLabel()
        self.selection_label.setObjectName("Muted")
        self.selection_label.setWordWrap(True)
        layout.addWidget(self.selection_label)

        self.test_label = QLabel()
        self.test_label.setObjectName("Muted")
        self.test_label.setWordWrap(True)
        layout.addWidget(self.test_label)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        comparison_tab = QWidget()
        comparison_layout = QVBoxLayout(comparison_tab)
        comparison_layout.setContentsMargins(10, 10, 10, 10)
        split = QSplitter(Qt.Vertical)
        self.chart = ChartPanel(height=330)
        split.addWidget(self.chart)
        self.summary_table = DataTable()
        split.addWidget(self.summary_table)
        split.setSizes([340, 300])
        comparison_layout.addWidget(split)
        self.tabs.addTab(comparison_tab, "Comparison")

        tests_tab = QWidget()
        tests_layout = QVBoxLayout(tests_tab)
        tests_layout.setContentsMargins(10, 10, 10, 10)
        tests_layout.addWidget(section_label("Group vs rest of the world"))
        self.vs_rest_table = DataTable()
        tests_layout.addWidget(self.vs_rest_table, 1)
        tests_layout.addWidget(section_label("Pairwise group tests (Mann–Whitney U, BH FDR)"))
        self.pairwise_table = DataTable()
        tests_layout.addWidget(self.pairwise_table, 1)
        test_note = QLabel(
            "Cliff's delta above zero means the first group tends to have higher values; below zero means "
            "lower. Median differences are descriptive; q values control the false-discovery rate across "
            "the pairwise tests in this run."
        )
        test_note.setObjectName("Muted")
        test_note.setWordWrap(True)
        tests_layout.addWidget(test_note)
        self.tabs.addTab(tests_tab, "Statistical tests")

        members_tab = QWidget()
        members_layout = QVBoxLayout(members_tab)
        members_layout.setContentsMargins(10, 10, 10, 10)
        member_controls = QHBoxLayout()
        member_controls.addWidget(QLabel("Group"))
        self.member_group = QComboBox()
        self.member_group.currentIndexChanged.connect(self._render_members)
        member_controls.addWidget(self.member_group)
        member_controls.addStretch(1)
        members_layout.addLayout(member_controls)
        self.members_caption = QLabel()
        self.members_caption.setObjectName("Muted")
        self.members_caption.setWordWrap(True)
        members_layout.addWidget(self.members_caption)
        self.members_table = DataTable(search=True, search_placeholder="Filter members…")
        members_layout.addWidget(self.members_table, 1)
        self.tabs.addTab(members_tab, "Members")

    # ------------------------------------------------------------------ setup
    def on_show(self) -> None:
        ds = self.ctx.dataset()
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
        self._render()

    def _indicator_changed(self) -> None:
        value = self.indicator_combo.currentData()
        if value:
            self._indicator = str(value)
            self.ctx.settings.group_indicator = self._indicator
            self.ctx.settings.save(self.ctx.paths.settings)
            self._render()

    def _selected_group_ids(self) -> list[str]:
        group_set = self.ctx.group_set()
        valid = set(group_set.ids())
        ids = [g for g in self.ctx.settings.group_ids if g in valid]
        return ids or group_set.ids()[:4]

    def _choose_groups(self) -> None:
        group_set = self.ctx.group_set()
        family_names = {row.id: row.name for row in self.ctx.config.families}
        items = [
            (
                str(row.id),
                f"{row.name} · {int(row.n_members)} members",
                family_names.get(str(row.family), str(row.family)),
            )
            for row in group_set.groups.itertuples(index=False)
        ]
        dialog = CheckListDialog(
            "Select groups", items, checked=self._selected_group_ids(), parent=self
        )
        if dialog.exec():
            selected = dialog.selected()
            if selected:
                self.ctx.settings.group_ids = selected
                self.ctx.settings.save(self.ctx.paths.settings)
                self._render()

    # ------------------------------------------------------------------ render
    def _render(self) -> None:
        ds = self.ctx.dataset()
        group_set = self.ctx.group_set()
        ids = self._selected_group_ids()
        if self._indicator not in ds.indicator_ids:
            self.chart.message("No observations for this indicator.")
            self.summary_table.set_frame(pd.DataFrame())
            self.test_label.setText("")
            return
        self.selection_label.setText(
            "Selected: " + " · ".join(group_set.name(g) for g in ids)
        )
        summary = summarize(ds, group_set, self._indicator, ids)
        self._render_chart(summary.table)
        self._render_summary(summary.table)
        self._populate_member_groups(ids)
        if len(ids) >= 1:
            comparison = compare(ds, group_set, self._indicator, ids)
            self._comparison = comparison
            self._render_tests(comparison)
        else:
            self._comparison = None
            self.vs_rest_table.set_frame(pd.DataFrame())
            self.pairwise_table.set_frame(pd.DataFrame())

    def _render_chart(self, table: pd.DataFrame) -> None:
        ds = self.ctx.dataset()
        group_set = self.ctx.group_set()
        if table.empty:
            self.chart.message("No groups selected.")
            return
        colors = current_palette()
        ax = self.chart.reset()
        plotted = 0
        ticks: list[str] = []
        for row in table.itertuples(index=False):
            members = [m for m in group_set.members_of(row.group_id) if m in ds.values.index]
            values = ds.values.loc[members, self._indicator].dropna().to_numpy(dtype=float)
            if values.size == 0:
                continue
            position = plotted + 1
            color = str(row.color) if str(row.color).startswith("#") else colors["accent"]
            box = ax.boxplot(
                [values],
                positions=[position],
                orientation="horizontal",
                widths=0.55,
                patch_artist=True,
                showfliers=False,
                manage_ticks=False,
            )
            for patch in box["boxes"]:
                patch.set_facecolor(color)
                patch.set_alpha(0.22)
                patch.set_edgecolor(color)
                patch.set_linewidth(1.2)
            for key in ("whiskers", "caps"):
                for item in box[key]:
                    item.set_color(colors["muted"])
                    item.set_linewidth(0.9)
            for median in box["medians"]:
                median.set_color(colors["text"])
                median.set_linewidth(1.6)
            jitter = np.random.default_rng(7).uniform(-0.13, 0.13, size=values.size)
            ax.scatter(
                values,
                np.full(values.size, position) + jitter,
                s=15,
                color=color,
                alpha=0.75,
                linewidths=0,
                zorder=3,
            )
            if pd.notna(row.aggregate):
                ax.scatter(
                    [row.aggregate],
                    [position],
                    marker="D",
                    s=34,
                    color=colors["text"],
                    edgecolors=color,
                    linewidths=1.2,
                    zorder=4,
                )
            ticks.append(str(row.group))
            plotted += 1
        if plotted == 0:
            self.chart.message("Selected groups have no data for this indicator.")
            return
        ax.set_yticks(range(1, plotted + 1), ticks)
        ax.set_ylim(plotted + 0.55, 0.45)
        ax.set_xlabel(f"{ds.indicator_name(self._indicator)} [{ds.indicators.loc[self._indicator, 'unit']}]")
        ax.grid(axis="x", alpha=0.5)
        ax.grid(axis="y", visible=False)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.set_title("Distribution by group · boxes and jittered member values", loc="left")
        self.chart.figure.subplots_adjust(left=0.26, right=0.98, top=0.9, bottom=0.18)
        self.chart.draw()

    def _render_summary(self, table: pd.DataFrame) -> None:
        if table.empty:
            self.summary_table.set_frame(pd.DataFrame())
            return
        view = table[
            [
                "group",
                "family",
                "n_members",
                "n_data",
                "coverage_pct",
                "aggregate",
                "median",
                "mean",
                "sd",
                "best_country",
                "worst_country",
                "latest_year",
            ]
        ].rename(
            columns={
                "group": "Group",
                "family": "Family",
                "n_members": "Members",
                "n_data": "With data",
                "coverage_pct": "Coverage",
                "aggregate": "Aggregate",
                "median": "Median",
                "mean": "Mean",
                "sd": "SD",
                "best_country": "Best",
                "worst_country": "Worst",
                "latest_year": "Latest year",
            }
        ).copy()
        view["Family"] = view["Family"].astype(str).str.capitalize()
        self.summary_table.set_frame(
            view,
            {
                "Members": "int",
                "With data": "int",
                "Coverage": "pct",
                "Aggregate": "num",
                "Median": "num",
                "Mean": "num",
                "SD": "num",
                "Latest year": "year",
            },
        )

    def _render_tests(self, comparison) -> None:
        ds = self.ctx.dataset()
        mode = str(ds.indicators.loc[self._indicator, "aggregation"])
        parts: list[str] = []
        if not comparison.summary.empty and np.isfinite(comparison.kruskal_p):
            parts.append(
                f"Kruskal–Wallis p = {comparison.kruskal_p:.4f} across "
                f"{len(comparison.summary)} groups"
            )
        parts.append(f"group statistic: {mode} of latest values")
        parts.extend(comparison.notes)
        self.test_label.setText(" · ".join(parts))
        if comparison.vs_rest.empty:
            self.vs_rest_table.set_frame(pd.DataFrame())
        else:
            view = comparison.vs_rest.rename(
                columns={
                    "group": "Group",
                    "n_group": "N group",
                    "n_rest": "N rest",
                    "median_group": "Median group",
                    "median_rest": "Median rest",
                    "p": "p",
                    "q": "q (FDR)",
                    "cliffs_delta": "Cliff's δ",
                    "cohens_d": "Cohen's d",
                }
            )[["Group", "N group", "N rest", "Median group", "Median rest", "p", "q (FDR)", "Cliff's δ", "Cohen's d"]]
            self.vs_rest_table.set_frame(
                view,
                {
                    "N group": "int",
                    "N rest": "int",
                    "Median group": "num",
                    "Median rest": "num",
                    "p": "pval",
                    "q (FDR)": "pval",
                    "Cliff's δ": "num",
                    "Cohen's d": "num",
                },
            )
        if comparison.pairwise.empty:
            self.pairwise_table.set_frame(pd.DataFrame())
        else:
            view = comparison.pairwise.rename(
                columns={
                    "group_a": "Group A",
                    "group_b": "Group B",
                    "n_a": "N A",
                    "n_b": "N B",
                    "median_a": "Median A",
                    "median_b": "Median B",
                    "p": "p",
                    "q": "q (FDR)",
                    "cliffs_delta": "Cliff's δ",
                    "cohens_d": "Cohen's d",
                }
            )
            self.pairwise_table.set_frame(
                view,
                {
                    "N A": "int",
                    "N B": "int",
                    "Median A": "num",
                    "Median B": "num",
                    "p": "pval",
                    "q (FDR)": "pval",
                    "Cliff's δ": "num",
                    "Cohen's d": "num",
                },
            )

    def _populate_member_groups(self, ids: list[str]) -> None:
        group_set = self.ctx.group_set()
        current = self.member_group.currentData()
        self.member_group.blockSignals(True)
        self.member_group.clear()
        for group_id in ids:
            self.member_group.addItem(group_set.name(group_id), group_id)
        index = self.member_group.findData(current)
        self.member_group.setCurrentIndex(max(index, 0))
        self.member_group.blockSignals(False)
        self._render_members()

    def _render_members(self) -> None:
        group_id = self.member_group.currentData()
        if not group_id:
            self.members_table.set_frame(pd.DataFrame())
            return
        ds = self.ctx.dataset()
        group_set = self.ctx.group_set()
        table = member_table(ds, group_set, str(group_id), self._indicator)
        if table.empty:
            self.members_table.set_frame(pd.DataFrame())
            self.members_caption.setText("No member has data for this indicator at the current cutoff.")
            return
        meta = ds.indicators.loc[self._indicator]
        self.members_caption.setText(
            f"{meta['name']} [{meta['unit']}] · {len(table)} of "
            f"{len(group_set.members_of(str(group_id)))} members with data"
        )
        view = table[["country", "value", "year"]].rename(
            columns={"country": "Country", "value": "Value", "year": "Year"}
        )
        self.members_table.set_frame(view, {"Value": "num", "Year": "year"})

    # ---------------------------------------------------------------- actions
    def _edit_membership(self) -> None:
        group_id = self.member_group.currentData()
        if not group_id:
            self.window.statusBar().showMessage("Select a group first.", 4000)
            return
        group_set = self.ctx.group_set()
        items = [
            (str(row.iso3), str(row.name), str(row.region))
            for row in self.ctx.country_rows().itertuples(index=False)
        ]
        dialog = CheckListDialog(
            f"Membership — {group_set.name(str(group_id))}",
            items,
            checked=group_set.members_of(str(group_id)),
            parent=self,
        )
        if dialog.exec():
            try:
                save_group_members(self.ctx.paths.groups_local, str(group_id), dialog.selected())
                self.ctx.reload_groups()
            except OSError as exc:
                self.window.statusBar().showMessage(f"Could not save membership: {exc}", 8000)
                return
            self.window.statusBar().showMessage(
                f"Membership updated locally for {group_set.name(str(group_id))}.", 6000
            )
            self._render()

    def _reset_edits(self) -> None:
        try:
            reset_overlay(self.ctx.paths.groups_local)
            self.ctx.reload_groups()
        except OSError as exc:
            self.window.statusBar().showMessage(f"Could not reset local edits: {exc}", 8000)
            return
        self.window.statusBar().showMessage("Local group edits reset to the shipped definitions.", 6000)
        self._render()

    def _export_summary(self) -> None:
        if self._comparison is None or self._comparison.summary.empty:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export group summary", "group_summary.csv", "CSV (*.csv);;Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            export_dataframe(self._comparison.summary, Path(path))
            self.window.statusBar().showMessage(f"Exported {path}", 5000)
        except Exception as exc:  # noqa: BLE001
            self.window.statusBar().showMessage(f"Export failed: {exc}", 6000)

    def on_theme_changed(self) -> None:
        self.chart.apply_theme(self.ctx.settings.theme)
        self._render()
