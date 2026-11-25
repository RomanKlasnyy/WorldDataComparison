"""About, methodology and attribution page."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from ... import SCHEMA_VERSION, __version__
from ..widgets import PageHeader, section_label
from .base import Page


class AboutPage(Page):
    def __init__(self, ctx, window, parent=None):
        super().__init__(ctx, window, parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 20, 26, 20)
        layout.setSpacing(12)
        layout.addWidget(
            PageHeader(
                "About & methodology",
                "What this app computes, how years are resolved, and what the numbers do not prove.",
            )
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 0, 10, 0)
        body.setSpacing(14)

        info = self.ctx.build_info()
        with_data = len(self.ctx.repo.indicators(include_hidden=False, with_data=True))
        configured = len(self.ctx.config.visible_indicators)
        body.addWidget(section_label("Build"))
        body.addWidget(
            self._paragraph(
                f"WorldDataComparison v{__version__} · schema {SCHEMA_VERSION} · build "
                f"<b>{info.get('build_id', '—')}</b>, generated {info.get('built_at', '—')}. "
                f"Database: {info.get('n_observations', '—')} observations, "
                f"{info.get('n_countries', '—')} countries, {configured} configured indicators "
                f"({with_data} with data), {info.get('db_size_mb', '—')} MB. Content hash "
                f"<code>{str(info.get('content_hash', ''))[:16]}…</code>."
            )
        )

        body.addWidget(section_label("How values are selected"))
        body.addWidget(
            self._paragraph(
                "For every country and indicator the app uses the <b>newest observation at or after the "
                f"recency cutoff</b> (default {self.ctx.settings.cutoff_year}, configurable in the app "
                "settings). Most series publish 2023–2025 values, but survey-based series such as Gini can be "
                "years older; every row carries its source year and the interface shows it. Historical "
                "observations from 2010 onward are stored so the correlation page can also run a "
                "<i>strict same-year</i> variant."
            )
        )

        body.addWidget(section_label("Correlation method"))
        body.addWidget(
            self._paragraph(
                "Headline correlations are Pearson r on pairwise-complete observations with at least 30 "
                "countries. Each pair reports N, a two-tailed p value, a 95% confidence interval (Fisher z), "
                "and Spearman rho as a monotonicity check. Benjamini–Hochberg FDR is applied across all pairs "
                "in a run. Optional variants: log10 transform for skewed indicators (GDP, population, "
                "military spending, patents, energy), exclusion of ±3σ outliers, restriction to years where "
                "both indicators share the same year, and partial correlation residualising both variables on "
                "a control (GDP per capita PPP by default)."
            )
        )

        body.addWidget(section_label("What correlations do not show"))
        caveat = QLabel(
            "Correlation is not causation. Country-level (“ecological”) correlations describe aggregates, "
            "not individuals. Composite indices (HDI, V-Dem, CPI, WGI, EPI, GPI, SPI, GII) are built from "
            "other indicators, so a composite-versus-component correlation is partly tautological — the UI "
            "marks such pairs. Different publication years and measurement definitions add noise. Always "
            "read N, the year gap, and the robustness columns before drawing a conclusion."
        )
        caveat.setObjectName("Caveat")
        caveat.setWordWrap(True)
        body.addWidget(caveat)

        body.addWidget(section_label("Sources and licences"))
        rows = []
        for source in self.ctx.repo.sources().itertuples(index=False):
            rows.append(
                f"<p><b>{source.name}</b><br>"
                f"Licence: {source.license or '—'}<br>"
                f"Attribution: {source.attribution or '—'}<br>"
                f"Redistributable in a public bundle: {'yes' if source.redistributable else 'no'}</p>"
            )
        body.addWidget(self._paragraph("".join(rows)))

        body.addWidget(section_label("Manual imports"))
        body.addWidget(
            self._paragraph(
                "Commercially licensed or irregular indices (EIU Democracy Index, OECD PISA, Freedom House, "
                "Yale EPI, ND-GAIN, IEP Global Peace Index, Social Progress Index) are never downloaded by "
                "the refresh script and are not redistributed. Import your own CSV or XLSX with:<br>"
                "<code>python scripts/import_manual.py --indicator pisa_math --file pisa.csv</code><br>"
                "Required columns: country (or ISO3 code), year, value. The importer resolves aliases, "
                "range-checks values, writes a snapshot and rebuilds the database."
            )
        )

        body.addWidget(section_label("Keyboard"))
        body.addWidget(
            self._paragraph(
                "Ctrl+K searches countries and indicators. Ctrl+1…7 switches pages. Tables support sorting, "
                "filtering, copy (Ctrl+C or right-click) and export."
            )
        )
        body.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

    def _paragraph(self, html: str) -> QLabel:
        label = QLabel(html)
        label.setWordWrap(True)
        label.setTextFormat(Qt.RichText)
        label.setOpenExternalLinks(True)
        label.setStyleSheet("line-height: 140%;")
        return label
