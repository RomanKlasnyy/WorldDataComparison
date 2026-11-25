# Roadmap

The roadmap is indicative, not a commitment. Priorities are data integrity,
auditable statistics and a fast offline experience.

## v0.2 — analysis depth and maps

- [ ] Choropleth map view using an open-licence SVG world map and an ISO3 →
      path mapping (no GeoPandas dependency)
- [ ] Trend view over the retained 2010→present history (sparkline expansion,
      small multiples, year comparison)
- [ ] Re-evaluate selector-based group membership at the current recency cutoff
      instead of only at build time
- [ ] Multiple-control partial correlation and a guided “is this relationship
      confounded?” workflow
- [ ] Saved analysis presets (indicator set + correlation options) and a
      shareable report export (HTML/PDF)
- [ ] Rank-change and convergence views for groups

## v0.3 — distribution and reliability

- [ ] Windows installer (Inno Setup) with per-user install and data migration
- [ ] Code signing for the executable
- [ ] Linux/macOS packaging (at least an AppImage/zip) once the UI is tested
      there
- [ ] Differential data updates (fetch only changed series, verify against the
      previous snapshot)
- [ ] Automated upstream-change detection with a build diff report
- [ ] Optional SQLite/pandas-free analysis path for smaller builds

## Ideas under evaluation

- Regression workbench (standardised betas, VIF, model comparison)
- Time-series correlations with lag selection and rolling windows
- Subnational data (would require a separate entity model)
- Additional indices (subject to licensing): Fraser Economic Freedom, KOF
  Globalisation, UN E-Government, WIPO GII, environmental footprint
- Accessibility audit and screen-reader labelling
- Translations of the interface

## Explicit non-goals

- Live streaming statistics inside the app
- Cloud accounts, sync or telemetry
- Causal inference claims from cross-sectional correlations
- Bundling commercially licensed data in public releases
