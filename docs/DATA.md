# Data guide

WorldDataComparison is offline at runtime. A validated SQLite snapshot is
built ahead of time from public sources; the app only reads that file. This
document explains where the numbers come from, how they are normalised, how to
refresh them, and how to extend the catalogue.

## At a glance

| Item | Value |
| --- | --- |
| Indicators | 75 visible (69 automated + 6 manual) + 2 hidden inputs for derived ratios |
| Domains | 9 |
| Default entities | 197 (193 UN members + Vatican, Palestine, Taiwan, Kosovo) |
| Extra entities | 22 dependent territories, hidden by default |
| Observations | 180,460 in the shipped 0.1.0 snapshot |
| Years stored | 2010 → present (2025/2026 depending on source) |
| Default recency cutoff | 2015 |
| Database | ~25 MB SQLite + `manifest.json` |
| Automated sources | World Bank WDI, World Bank WGI, IMF WEO DataMapper, Our World in Data |
| Manual sources | OECD PISA, Freedom House, Yale EPI, ND-GAIN, IEP GPI, Social Progress Imperative |

The current snapshot is build `20261125T185349Z`, schema 1.

## Sources

| Source id | What it provides | Licence | Redistributable |
| --- | --- | --- | --- |
| `worldbank` | World Development Indicators, ~53 series | CC BY 4.0 | yes |
| `worldbank_wgi` | Worldwide Governance Indicators percentile ranks | CC BY 4.0 | yes |
| `imf` | WEO general government debt and fiscal balance | IMF terms, free with attribution | yes |
| `owid` | 13 indexed series (HDI, V-Dem, CPI, RSF, happiness, GII, turnout, homicide, median age, schooling, working hours) | CC BY 4.0 for OWID processing; upstream terms apply | yes |
| `derived` | Ratios computed from loaded indicators | inherits inputs | yes |
| `manual` | User-supplied indices | user-supplied | no |

Upstream producers behind the OWID series include UNDP, V-Dem, Transparency
International, Reporters Without Borders, WHO, UNODC, UN WPP, Gallup/WHR,
International IDEA and the Penn World Table. Full attribution is in
`NOTICE.txt`, in the app's About page, and in `config/indicators.yaml`
(per-indicator `attribution`).

The **EIU Democracy Index is not bundled** because it is commercially
licensed. V-Dem, Freedom House and the WGI governance indicators are the free
substitutes used here.

## Entity policy

- Canonical key: ISO 3166-1 alpha-3.
- Default set: 193 UN members + Vatican City, Palestine, Taiwan, Kosovo.
- Dependent territories (Hong Kong, Macao, Puerto Rico, Greenland, Bermuda, …)
  are stored with `entity_type=territory`, `is_default=0`, and are hidden
  unless “Include dependent territories” is enabled.
- World Bank aggregates (regions, income groups, “World”, “Euro area”) are
  never treated as countries. OWID pseudo-codes such as `OWID_WRL` and
  aggregate names are skipped and reported.
- Aliases live in `config/aliases.yaml`. Resolution order: ISO3 code →
  `code_aliases` → explicit alias → normalised display/official name. The
  normaliser strips accents, punctuation, apostrophes and case.

## Latest values, years and history

The database stores every observation from 2010 onward. Analysis selects the
**newest value per country × indicator at or after the recency cutoff**:

- Default cutoff: 2015.
- The cutoff is a UI setting; changing it does not rebuild the database.
- Each point's actual source year is stored and shown in profiles, tooltips,
  exports and the quality report.
- Correlation pairs use pairwise-complete observations; a pair can therefore
  combine years (for example GDP 2025 with Gini 2021). The median year gap is
  reported, and **Same year** mode restricts pairs to identical years.
- Missing values are never imputed, clamped or filled with zero.

History exists for three reasons: same-year robustness checks, country
sparklines, and future trend features. Per-indicator `min_year` can exclude
incompatible history (for example, CPI methodology changes before 2012).

## Automated sources and series codes

The exact source series for every indicator is in `config/indicators.yaml` and
in the generated [INDICATORS](INDICATORS.md) catalogue.

Examples:

- World Bank WDI: `NY.GDP.PCAP.PP.CD`, `SP.DYN.TFRT.IN`, `SI.POV.GINI`.
- World Bank WGI percentile ranks: `GOV_WGI_CC.SC`, `GOV_WGI_RL.SC`.
- IMF DataMapper: `GGXWDG_NGDP`, `GGXCNL_NGDP`.
- OWID grapher slugs with an explicit value column, e.g.
  `human-development-index` → “Human Development Index”.

IMF WEO includes projections; the fetcher caps those series at the previous
calendar year so a forecast is never presented as an observation.

## Pipeline

```
config/*.yaml
   │
   ├─ ingest → data/raw/<source>/<YYYY-MM-DD>/… + SHA-256
   │
   ├─ normalize → ISO3 resolution, unit/range checks, deduplication, derived ratios
   │
   ├─ validate → quarantine, coverage, quality gates
   │
   └─ write → data/worlddata.sqlite + manifest.json + quality_report.csv
              + rejected.csv + unresolved.csv / skipped_entities.csv
```

Commands:

```powershell
python scripts/refresh_data.py                 # fetch (or reuse today's cache) + rebuild
python scripts/refresh_data.py --force         # ignore today's cached snapshots
python scripts/refresh_data.py --only worldbank owid   # debugging subset
python scripts/build_db.py                     # offline rebuild from cached snapshots
python scripts/validate_data.py --strict       # checksum + quality gates
```

## Snapshot cache

- Online runs write into `data/raw/<source>/<date>/`.
- Within the same calendar day, an online run reuses existing snapshots unless
  `--force` is passed. This makes retries cheap and avoids hammering upstream
  APIs.
- `--offline` / `scripts/build_db.py` rebuilds from the newest snapshot per
  source.
- Each snapshot's SHA-256 is recorded in `manifest.json` for online runs.
- Raw snapshots are not committed and not bundled; they exist so the database
  can be rebuilt without re-downloading.

## Manual imports

Six indices have no stable, freely redistributable bulk feed. They appear in
the catalogue with `source: manual` and 0% coverage until imported.

Required columns (CSV or XLSX):

| Column | Accepted names | Notes |
| --- | --- | --- |
| Country | `country`, `country_name`, `name`, `entity`, `country name` | Names are resolved through the alias table |
| ISO3 (optional) | `code`, `iso3`, `iso_code`, `country_code` | Used first when present |
| Year | `year`, `date`, `period` | Integer |
| Value | `value`, `score`, `index`, `points` | Numeric |

```powershell
python scripts/import_manual.py --indicator pisa_math --file pisa.csv
```

The importer resolves countries, range-checks values, reports unresolved and
rejected rows, writes a snapshot to `data/raw/manual/<date>/<indicator>.csv`,
and rebuilds the database offline (use `--no-build` to skip the rebuild).

To add the EIU Democracy Index: append an indicator entry with `source: manual`
(0–100, `higher_is_better: true`, `is_composite: true`, aggregation median),
then import a CSV with `country, year, value`. The EIU file itself is not
redistributed by this project.

## Derived indicators

Three exposed indicators are ratios of loaded series:

| Indicator | Formula | Input |
| --- | --- | --- |
| Military expenditure per capita | total military spend ÷ population | `military_spend_total / population` |
| Armed forces personnel per 1,000 | total armed forces ÷ population × 1,000 | `armed_forces_total / population` |
| Patent applications per million | resident applications ÷ population × 1,000,000 | `patents_resident / population` |

`armed_forces_total` and `patents_resident` are hidden (`hidden: true`): they
are stored because the ratio needs them, but they do not appear in pickers or
correlations. Ratios only exist for country-years where both inputs exist.

## Coverage, quarantine and diagnostics

Generated files in `data/`:

| File | Contents |
| --- | --- |
| `quality_report.csv` | Per-indicator coverage, countries, latest/median year, stale count, observation count, attribution |
| `rejected.csv` | Values rejected by range checks or non-finite checks, with a reason |
| `unresolved.csv` | Source names that look like countries but could not be mapped |
| `skipped_entities.csv` | Source rows for aggregates and untracked territories |
| `manifest.json` | Schema version, build id, observations, content hash, DB SHA-256, source snapshot metadata |

Quality gates (`validate_data.py --strict`) fail on:

- fewer than 50 automated indicators with ≥60% country coverage (current:
  69/69 pass);
- duplicate `(iso3, indicator, year)` keys;
- non-finite values;
- more than 1% unresolved source rows (current: 0%);
- observations dated more than one year into the future.

## Manifest, schema and swapping data

The database carries `meta` rows with `schema_version`, `build_id`,
`content_hash`, `history_floor_year` and `recency_cutoff_year`.
`manifest.json` adds the DB SHA-256, row counts, a generated timestamp and
source snapshot metadata for online refreshes.

At startup the app:

1. refuses to load if `schema_version` does not match the app's schema;
2. verifies the SHA-256 of `worlddata.sqlite` against the manifest;
3. refuses a mismatch instead of loading inconsistent data.

To update a portable installation, close the app and replace
`data/worlddata.sqlite` **and** `data/manifest.json` together. Keep
`settings.json` and `groups.local.yaml` if you want to preserve preferences and
local group edits.

## Reproducibility

- Rebuilding from the same snapshots produces the same observation
  `content_hash` (covered by a test).
- Snapshot directories are date-stamped; `--offline` always uses the newest.
- The bag of upstream APIs changes over time, so a new fetch can legitimately
  change values. Record the build id when sharing results.

## Licensing and redistribution

The application code is MIT. Data is not covered by that licence. Before
publishing a bundle publicly:

- keep `NOTICE.txt` and the in-app attribution;
- check `redistributable` in `config/sources.yaml`;
- review upstream terms for OWID-delivered series (notably V-Dem CC BY-SA 4.0
  and Transparency International's CPI terms);
- do not add EIU or other commercially licensed data to a public bundle.

## Limits

- Some series are sparse by nature (Gini surveys, literacy, hospital beds,
  PISA, working hours); coverage is displayed rather than hidden.
- Publication years differ; use the same-year mode and read the year gap.
- Country definitions and disputed entities differ across sources; Taiwan,
  Kosovo and Palestine have gaps.
- The pipeline validates ranges and keys, not upstream methodology changes.
  A source revision can change a value without being an error here.
