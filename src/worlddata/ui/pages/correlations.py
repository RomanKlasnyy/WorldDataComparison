"""Correlations page: all-pairs matrix, ranked table, scatter drill-down and variants."""

from __future__ import annotations

import textwrap
from pathlib import Path

import numpy as np
import pandas as pd
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from ...core.correlations import (
    CorrOptions,
    cluster_order,
    correlation_pairs,
    matrix_from_pairs,
    pair_points,
    pairs_summary,
)
from ...core.export import export_dataframe
from ..models import format_value
from ..theme import current_palette
from ..widgets import ChartPanel, DataTable, PageHeader, check, section_label, spin, toolbar_row
from .base import Page


class CorrelationsPage(Page):
    def __init__(self, ctx, window, parent=None):
        super().__init__(ctx, window, parent)
        self._pairs = pd.DataFrame()
        self._visible = pd.DataFrame()
        self._matrix = pd.DataFrame()
        self._ids: list[str] = []
        self._heat_ids: list[str] = []
        self._generation = 0
        self._selected: tuple[str, str] | None = None
        self._scatter_frame = pd.DataFrame()
        self._scatter_ax = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 20, 26, 20)
        layout.setSpacing(8)
        layout.addWidget(
            PageHeader(
                "Correlations",
                "Every indicator against every other indicator, with significance control, robustness "
                "variants and a scatter drill-down that shows each country's source year.",
            )
        )

        caveat = QLabel(
            "Correlation is not causation. Values are country-level and may come from different source "
            "years; use the same-year variant and the partial correlation control to test robustness. "
            "Composite indices correlated with their own components are partly tautological."
        )
        caveat.setObjectName("Caveat")
        caveat.setWordWrap(True)
        layout.addWidget(caveat)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(QLabel("Scope"))
        self.scope = QComboBox()
        self.scope.currentIndexChanged.connect(lambda: self._schedule())
        controls.addWidget(self.scope)
        self.log_box = check("Log skewed", self.ctx.settings.log_transform)
        self.log_box.toggled.connect(lambda: self._schedule())
        controls.addWidget(self.log_box)
        self.same_year = check("Same year", self.ctx.settings.same_year)
        self.same_year.toggled.connect(lambda: self._schedule())
        controls.addWidget(self.same_year)
        self.outliers = check("Exclude ±3σ", self.ctx.settings.exclude_outliers)
        self.outliers.toggled.connect(lambda: self._schedule())
        controls.addWidget(self.outliers)
        self.no_composite = check("Exclude composites", False)
        self.no_composite.toggled.connect(lambda: self._schedule())
        controls.addWidget(self.no_composite)
        controls.addWidget(QLabel("Control"))
        self.control = QComboBox()
        self.control.currentIndexChanged.connect(lambda: self._schedule())
        controls.addWidget(self.control)
        controls.addWidget(QLabel("Min N"))
        self.min_n = spin(10, 150, self.ctx.settings.min_n)
        self.min_n.valueChanged.connect(lambda: self._schedule())
        controls.addWidget(self.min_n)
        controls.addStretch(1)
        self.computing = QLabel("")
        self.computing.setObjectName("Muted")
        controls.addWidget(self.computing)
        layout.addLayout(controls)

        self.summary = QLabel()
        self.summary.setObjectName("Muted")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        top_split = QSplitter(Qt.Horizontal)
        heat_container = QWidget()
        heat_layout = QVBoxLayout(heat_container)
        heat_layout.setContentsMargins(0, 0, 0, 0)
        self.order = QComboBox()
        self.order.addItem("Clustered", "cluster")
        self.order.addItem("By domain", "domain")
        self.order.addItem("Alphabetical", "alpha")
        self.order.currentIndexChanged.connect(lambda: self._render_heatmap())
        save_matrix_button = QPushButton("Save matrix")
        save_matrix_button.clicked.connect(
            lambda: self.heatmap.save_dialog(self, "correlations.png")
        )
        heat_layout.addWidget(
            toolbar_row(
                section_label("Correlation matrix"),
                None,
                QLabel("Order"),
                self.order,
                save_matrix_button,
            )
        )
        self.heatmap = ChartPanel(height=340)
        heat_layout.addWidget(self.heatmap, 1)
        self.hover = QLabel("Hover a cell to inspect a pair.")
        self.hover.setObjectName("Muted")
        heat_layout.addWidget(self.hover)
        top_split.addWidget(heat_container)

        pairs_container = QWidget()
        pairs_layout = QVBoxLayout(pairs_container)
        pairs_layout.setContentsMargins(0, 0, 0, 0)
        self.min_r = spin(0, 100, 0, step=5)
        self.significant = check("q < 0.05", True)
        self.show_insufficient = check("show insufficient", False)
        export_pairs_button = QPushButton("Export")
        export_pairs_button.clicked.connect(self._export_pairs)
        pairs_layout.addWidget(
            toolbar_row(
                section_label("Ranked pairs"),
                None,
                QLabel("|r| ≥"),
                self.min_r,
                self.significant,
                self.show_insufficient,
                export_pairs_button,
            )
        )
        self.min_r.valueChanged.connect(lambda: self._render_pairs())
        self.significant.toggled.connect(lambda: self._render_pairs())
        self.show_insufficient.toggled.connect(lambda: self._render_pairs())
        self.pairs_table = DataTable(search=True, search_placeholder="Filter pairs…")
        self.pairs_table.view.selectionModel().selectionChanged.connect(self._pair_selected)
        pairs_layout.addWidget(self.pairs_table, 1)
        top_split.addWidget(pairs_container)
        top_split.setSizes([640, 740])
        layout.addWidget(top_split, 3)

        self.scatter = ChartPanel(height=260)
        self.scatter_title = QLabel("Select a pair to see the scatter")
        self.scatter_title.setObjectName("SectionTitle")
        self.scatter_note = QLabel("")
        self.scatter_note.setObjectName("Muted")
        self.scatter_note.setWordWrap(True)
        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.addWidget(self.scatter_title)
        bottom_layout.addWidget(self.scatter_note)
        bottom_layout.addWidget(self.scatter, 1)
        layout.addWidget(bottom, 2)

        self._connect_heatmap()
        self._connect_scatter()
        self._sync_settings()

    # ------------------------------------------------------------------ setup
    def _sync_settings(self) -> None:
        self.log_box.setChecked(self.ctx.settings.log_transform)
        self.same_year.setChecked(self.ctx.settings.same_year)
        self.outliers.setChecked(self.ctx.settings.exclude_outliers)
        self.min_n.setValue(self.ctx.settings.min_n)

    def on_show(self) -> None:
        domains = ["All domains", *self.ctx.config.domain_order]
        current = self.scope.currentText()
        self.scope.blockSignals(True)
        self.scope.clear()
        self.scope.addItems(domains)
        if current in domains:
            self.scope.setCurrentText(current)
        self.scope.blockSignals(False)

        controls = [("", "None")]
        for indicator_id in ("gdp_per_capita_ppp", "population", "gdp_per_capita"):
            if indicator_id in self.ctx.dataset().indicator_ids:
                controls.append((indicator_id, self.ctx.indicator_label(indicator_id)))
        current_control = self.control.currentData() or self.ctx.settings.control
        self.control.blockSignals(True)
        self.control.clear()
        for key, label in controls:
            self.control.addItem(label, key)
        index = self.control.findData(current_control)
        self.control.setCurrentIndex(max(index, 0))
        self.control.blockSignals(False)

        self._schedule()

    # --------------------------------------------------------------- compute
    def _scope_ids(self) -> list[str]:
        ds = self.ctx.dataset()
        ids = ds.indicator_ids
        domain = self.scope.currentText()
        if domain and domain != "All domains":
            ids = [i for i in ids if str(ds.indicators.loc[i, "domain"]) == domain]
        if self.no_composite.isChecked():
            ids = [i for i in ids if not bool(ds.indicators.loc[i, "is_composite"])]
        control = self.control.currentData() or None
        if control and control not in ids:
            ids = [*ids, control]
        return ids

    def _options(self) -> CorrOptions:
        return CorrOptions(
            log=self.log_box.isChecked(),
            same_year=self.same_year.isChecked(),
            exclude_outliers=self.outliers.isChecked(),
            min_n=int(self.min_n.value()),
            control=self.control.currentData() or None,
        )

    def _schedule(self) -> None:
        ds = self.ctx.dataset()
        ids = self._scope_ids()
        if len(ids) < 2:
            self._pairs = pd.DataFrame()
            self._ids = ids
            self.summary.setText("Select at least two indicators.")
            self.heatmap.message("Not enough indicators in scope.")
            self.pairs_table.set_frame(pd.DataFrame())
            return
        options = self._options()
        self.ctx.settings.log_transform = options.log
        self.ctx.settings.same_year = options.same_year
        self.ctx.settings.exclude_outliers = options.exclude_outliers
        self.ctx.settings.min_n = options.min_n
        self.ctx.settings.control = options.control
        self.ctx.settings.save(self.ctx.paths.settings)

        key = (tuple(ids), options.key)
        self._generation += 1
        generation = self._generation
        cached = self.ctx.cached(key)
        if cached is not None:
            self._finish(cached, ids, options, generation)
            return
        self.computing.setText(f"Computing {len(ids) * (len(ids) - 1) // 2:,} pairs…")
        self.pairs_table.setEnabled(False)

        def compute():
            return correlation_pairs(ds, options, ids)

        def done(result):
            self.ctx.remember(key, result)
            self._finish(result, ids, options, generation)

        def failed(message):
            if generation != self._generation:
                return
            self.computing.setText("")
            self.pairs_table.setEnabled(True)
            self.window.statusBar().showMessage(f"Correlation failed: {message}", 8000)

        self.window.task_runner.run(compute, done, failed)

    def _finish(self, pairs: pd.DataFrame, ids: list[str], options: CorrOptions, generation: int) -> None:
        if generation != self._generation:
            return
        self.computing.setText("")
        self.pairs_table.setEnabled(True)
        self._pairs = pairs
        self._ids = ids
        summary = pairs_summary(pairs, options)
        variant = "log" if options.log else "raw"
        extras = []
        if options.same_year:
            extras.append("same-year only")
        if options.exclude_outliers:
            extras.append("±3σ excluded")
        if options.control:
            extras.append(f"partial r controls {self.ctx.indicator_label(options.control)}")
        note = f" · {', '.join(extras)}" if extras else ""
        self.summary.setText(
            f"{summary['n_tested']:,} testable pairs ({summary['n_insufficient']:,} below N="
            f"{options.min_n}) · {summary['significant']:,} significant at q<0.05 · "
            f"{summary['strong']:,} strong (|r|>=0.5) · median N={summary['median_n']:.0f} · "
            f"{variant}{note}"
        )
        self._render_heatmap()
        self._render_pairs()

    # ---------------------------------------------------------------- render
    def _ordered_ids(self) -> list[str]:
        if not self._ids:
            return []
        mode = self.order.currentData()
        ds = self.ctx.dataset()
        if mode == "alpha":
            return sorted(self._ids, key=lambda i: ds.indicator_name(i).casefold())
        if mode == "domain":
            order = {d: n for n, d in enumerate(self.ctx.config.domain_order)}
            return sorted(
                self._ids,
                key=lambda i: (order.get(str(ds.indicators.loc[i, "domain"]), 999), ds.indicator_name(i)),
            )
        return cluster_order(self._matrix) if not self._matrix.empty else self._ids

    def _render_heatmap(self) -> None:
        if self._pairs.empty or len(self._ids) < 2:
            self.heatmap.message("No testable pairs.")
            return
        matrix = matrix_from_pairs(self._pairs, self._ids)
        self._matrix = matrix
        ids = self._ordered_ids()
        self._heat_ids = ids
        matrix = matrix.loc[ids, ids]
        colors = current_palette()
        ax = self.heatmap.reset()
        data = matrix.to_numpy(dtype=float)
        image = ax.imshow(data, cmap="RdBu_r", vmin=-1, vmax=1, interpolation="nearest", aspect="auto")
        n = len(ids)
        if n <= 30:
            labels = [self._short_label(i) for i in ids]
            ax.set_xticks(range(n), labels, rotation=90, fontsize=6.5)
            ax.set_yticks(range(n), labels, fontsize=6.5)
        else:
            ax.set_xticks([])
            ax.set_yticks([])
        ax.grid(False)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_title("Pearson r", loc="left")
        colorbar = self.heatmap.figure.colorbar(image, ax=ax, fraction=0.025, pad=0.01)
        colorbar.ax.tick_params(labelsize=6.5, colors=colors["muted"])
        colorbar.outline.set_visible(False)
        self.heatmap.figure.subplots_adjust(left=0.22, right=0.97, top=0.94, bottom=0.22)
        self.heatmap.draw()

    def _short_label(self, indicator_id: str) -> str:
        name = self.ctx.dataset().indicator_name(indicator_id)
        return name if len(name) <= 26 else name[:24] + "…"

    def _render_pairs(self) -> None:
        pairs = self._pairs
        if pairs.empty:
            self._visible = pairs
            self.pairs_table.set_frame(pd.DataFrame())
            return
        pairs = pairs.copy()
        if not self.show_insufficient.isChecked():
            pairs = pairs[~pairs["insufficient"]]
        if self.significant.isChecked():
            pairs = pairs[pairs["q"] < 0.05]
        threshold = self.min_r.value() / 100.0
        if threshold > 0:
            pairs = pairs[pairs["abs_r"] >= threshold]
        pairs = pairs.sort_values("abs_r", ascending=False, na_position="last")
        self._visible = pairs.head(2000)
        ds = self.ctx.dataset()
        view = pd.DataFrame(
            {
                "Indicator A": [ds.indicator_name(i) for i in self._visible["a"]],
                "Indicator B": [ds.indicator_name(i) for i in self._visible["b"]],
                "r": self._visible["r"],
                "N": self._visible["n"],
                "q": self._visible["q"],
                "Spearman": self._visible["rho"],
                "Partial r": self._visible["partial_r"],
                "Effect": self._visible["effect"],
                "A": self._visible["a"],
                "B": self._visible["b"],
            }
        )
        self.pairs_table.set_frame(
            view,
            {
                "r": "num",
                "N": "int",
                "q": "pval",
                "Spearman": "num",
                "Partial r": "num",
            },
        )
        self.pairs_table.set_widths(
            {
                "Indicator A": 145,
                "Indicator B": 145,
                "r": 52,
                "N": 42,
                "q": 70,
                "Spearman": 72,
                "Partial r": 66,
                "Effect": 66,
            }
        )
        self.pairs_table.view.setColumnHidden(len(view.columns) - 2, True)
        self.pairs_table.view.setColumnHidden(len(view.columns) - 1, True)
        if len(view) and not self.pairs_table.view.selectionModel().selectedRows():
            self.pairs_table.view.selectRow(0)
            self._pair_selected()
        elif len(view):
            self._pair_selected()

    # ---------------------------------------------------------------- scatter
    def _pair_selected(self, *_args) -> None:
        row = self.pairs_table.selected_source_row()
        if row is None or row >= len(self._visible):
            return
        record = self._visible.iloc[row]
        self._selected = (str(record["a"]), str(record["b"]))
        self._render_scatter()

    def _render_scatter(self) -> None:
        if not self._selected:
            return
        a, b = self._selected
        ds = self.ctx.dataset()
        options = self._options()
        points = pair_points(ds, a, b, options)
        self._scatter_frame = points
        if points.empty:
            self.scatter.message("No points.")
            return
        included = points[points["included"]]
        excluded = points[~points["included"]]
        colors = current_palette()
        ax = self.scatter.reset()
        self._scatter_ax = ax
        if not excluded.empty:
            ax.scatter(
                excluded["x"], excluded["y"], s=16, color=colors["muted"], alpha=0.35,
                label="excluded / mismatched year", linewidths=0,
            )
        ax.scatter(
            included["x"], included["y"], s=22, color=colors["accent"], alpha=0.8,
            label="included", linewidths=0,
        )
        if len(included) >= 3:
            coefficient = np.polyfit(included["x"], included["y"], 1)
            xs = np.linspace(included["x"].min(), included["x"].max(), 50)
            ax.plot(xs, np.polyval(coefficient, xs), color=colors["warn"], linewidth=1.4)
            residual = included["y"] - np.polyval(coefficient, included["x"])
            for index in residual.abs().sort_values(ascending=False).head(6).index:
                point = points.loc[index]
                ax.annotate(
                    point["country"],
                    (point["x"], point["y"]),
                    fontsize=6.2,
                    color=colors["muted"],
                    xytext=(3, 3),
                    textcoords="offset points",
                )
        meta_a = ds.indicators.loc[a]
        meta_b = ds.indicators.loc[b]
        log_a = options.log and bool(meta_a["default_log"])
        log_b = options.log and bool(meta_b["default_log"])
        ax.set_xlabel(self._axis_label(meta_a, log_a))
        ax.set_ylabel(self._axis_label(meta_b, log_b))
        ax.legend(fontsize=7, loc="best")
        ax.spines[["top", "right"]].set_visible(False)

        record = self._visible[
            (self._visible["a"] == a) & (self._visible["b"] == b)
        ]
        if record.empty:
            record = self._visible[(self._visible["a"] == b) & (self._visible["b"] == a)]
        detail = ""
        if not record.empty:
            row = record.iloc[0]
            detail = (
                f"r = {row['r']:.3f} [{row['ci_low']:.3f}, {row['ci_high']:.3f}] · "
                f"N = {int(row['n'])} · q = {row['q']:.4f} · Spearman = {row['rho']:.3f}"
            )
            if np.isfinite(row["partial_r"]):
                detail += f" · partial r = {row['partial_r']:.3f}"
            detail += f" · median |year gap| = {row['year_gap_median']:.0f}"
        composite = []
        if bool(meta_a["is_composite"]):
            composite.append(str(meta_a["name"]))
        if bool(meta_b["is_composite"]):
            composite.append(str(meta_b["name"]))
        if composite:
            detail += " · composite index involved: " + ", ".join(composite)
        self.scatter_title.setText(f"{meta_a['name']}  ×  {meta_b['name']}")
        self.scatter_note.setText(detail)
        self.scatter.figure.subplots_adjust(left=0.14, right=0.98, top=0.95, bottom=0.22)
        self.scatter.draw()

    def _axis_label(self, meta: pd.Series, log: bool) -> str:
        name = textwrap.fill(str(meta["name"]), 32)
        suffix = f"\n[{meta['unit']}]"
        if log:
            suffix += " · log10"
        return name + suffix

    # ------------------------------------------------------------------ hover
    def _connect_heatmap(self) -> None:
        self.heatmap.canvas.mpl_connect("motion_notify_event", self._hover_heatmap)

    def _hover_heatmap(self, event) -> None:
        if event.inaxes is None or self._matrix.empty or not self._ids:
            return
        ordered = self._heat_ids or self._ordered_ids()
        if not ordered:
            return
        x = int(round(event.xdata or 0))
        y = int(round(event.ydata or 0))
        if 0 <= x < len(ordered) and 0 <= y < len(ordered):
            a, b = ordered[x], ordered[y]
            value = self._matrix.loc[a, b]
            if np.isfinite(value):
                self.hover.setText(
                    f"{self._short_label(a)} × {self._short_label(b)}: r = {value:.3f}"
                )

    def _connect_scatter(self) -> None:
        self.scatter.canvas.mpl_connect("motion_notify_event", self._hover_scatter)

    def _hover_scatter(self, event) -> None:
        if event.inaxes is None or self._scatter_frame.empty:
            return
        frame = self._scatter_frame
        x, y = event.xdata, event.ydata
        if x is None or y is None:
            return
        distance = (frame["x"] - x) ** 2 + (frame["y"] - y) ** 2
        index = distance.idxmin()
        point = frame.loc[index]
        if distance.loc[index] > 0.002:
            return
        text = (
            f"{point['country']}\n"
            f"x: {format_value(point['x_raw'], 'num')} ({int(point['year_a']) if pd.notna(point['year_a']) else '—'})\n"
            f"y: {format_value(point['y_raw'], 'num')} ({int(point['year_b']) if pd.notna(point['year_b']) else '—'})"
        )
        QToolTip.showText(
            self.scatter.canvas.mapToGlobal(QPoint(int(event.x), int(event.y))), text, self.scatter
        )

    # ---------------------------------------------------------------- actions
    def _export_pairs(self) -> None:
        if self._visible.empty:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export pairs", "correlation_pairs.csv", "CSV (*.csv);;Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            export_dataframe(self._visible.drop(columns=["abs_r"], errors="ignore"), Path(path))
            self.window.statusBar().showMessage(f"Exported {path}", 5000)
        except Exception as exc:  # noqa: BLE001
            self.window.statusBar().showMessage(f"Export failed: {exc}", 6000)

    def on_theme_changed(self) -> None:
        self.heatmap.apply_theme(self.ctx.settings.theme)
        self.scatter.apply_theme(self.ctx.settings.theme)
        self._render_heatmap()
        self._render_scatter()
