# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Planned

- Choropleth map view (open-licence SVG world map, ISO3 → path mapping)
- Optional trend view over the retained 2010→present history
- Historical group membership evaluation for selector-based groups at the
  current recency cutoff

## [0.1.0] — 2026-11-25

First public release.

### Added

- PySide6 desktop application with seven pages: Dashboard, Countries,
  Rankings, Correlations, Groups, Data & Quality, About.
- 75 visible indicators across 9 domains; 69 automated (World Bank WDI/WGI,
  IMF WEO DataMapper, Our World in Data) and 6 manual-import indices
  (PISA, Freedom House, Yale EPI, ND-GAIN, GPI, SPI).
- Canonical ISO3 country registry: 193 UN members + Vatican, Palestine,
  Taiwan, Kosovo (197 default states), plus 22 dependent territories hidden by
  default. Alias resolution for source-specific names.
- Latest-available-value selection with a configurable recency cutoff
  (default 2015), per-point source years, and withheld/imputed values never
  filled.
- 2010→present observation history in SQLite, enabling strict same-year
  correlation checks and country sparklines.
- All-pairs correlation engine: Pearson r, N, two-tailed p, 95% Fisher-z CI,
  Spearman rho, Benjamini–Hochberg FDR, log10 transform for skewed series,
  ±3σ outlier exclusion, same-year mode, and partial correlation with a
  selectable confounder (GDP per capita PPP by default). Clustered heatmap,
  ranked pair table, scatter drill-down with hover tooltips, CSV/XLSX/PNG
  export.
- 28 country groups in 6 families (economic blocs, military alliances,
  continents, World Bank income tiers, V-Dem regime split, cultural and
  linguistic families), with per-indicator aggregation rules, coverage
  disclosure, Kruskal–Wallis and pairwise Mann–Whitney tests with BH
  correction, Cliff's delta and Cohen's d, member drill-down, and local
  membership editing.
- Data pipeline: snapshot cache with SHA-256, offline rebuilds, range
  validation and quarantine, unresolved-name and skipped-aggregate reports,
  derived indicators, generated coverage reports, quality gates, and
  `manifest.json` with schema version and database checksum.
- Portable Windows build (PyInstaller onedir) with `data/` and `config/`
  beside the executable, checksum validation at startup, a `--selftest` mode,
  and a zipped release artifact.
- 86 automated tests: unit statistics, synthetic end-to-end build, real-data
  integration, golden values, and an offscreen Qt smoke test.
- Documentation: README, usage guide, data guide, architecture notes,
  generated indicator and group catalogues, FAQ, release checklist,
  contributing/security/conduct policies, and CI/release workflows.
- Repository release readiness: MIT licence, issue and pull-request templates,
  Dependabot configuration, editor/line-ending conventions, screenshots, a
  citation file, and a GitHub release workflow with checksums.

### Fixed

- The dark theme no longer shows a white strip in a table's header tail, the
  gap after the last column, or the scrollbar track on Windows. The table and
  header viewport palettes are now applied explicitly, because the native
  Windows style paints those areas from the palette rather than the stylesheet.

### Data snapshot

- Build `20261125T185349Z`, schema 1, 180,460 observations, 197 default
  countries, 25.3 MB SQLite.
- Coverage: 69 of 69 automated indicators have ≥60% country coverage; zero
  unresolved source names, zero duplicate keys, zero out-of-range rows.

### Known limitations

- Correlations are country-level and do not describe individuals; the UI and
  documentation state this explicitly.
- Different indicators publish in different years; same-year mode mitigates
  but does not eliminate this.
- Some series are sparse by nature (Gini surveys, literacy, hospital beds,
  PISA, working hours). Coverage is always displayed.
- Taiwan, Kosovo and Palestine have gaps because not every upstream source
  publishes them.
- The packaged bundle is ~283 MB uncompressed (~110 MB zipped) due to
  PySide6, SciPy and pandas; the executable is unsigned.
- The EIU Democracy Index is commercially licensed and is not bundled; it can
  be added through a manual import after adding a manual indicator entry.
