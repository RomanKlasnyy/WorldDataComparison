# Contributing to WorldDataComparison

Thanks for considering a contribution. This project combines a Python data
pipeline, a statistical analysis core, and a PySide6 desktop UI, so there are
several useful ways to help.

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

## Ways to contribute

- Report a bug or a wrong statistic (include the country, indicator, value,
  year, and the upstream source URL if possible).
- Suggest an indicator, a data source, or a country group.
- Improve the documentation (`README.md`, `docs/`).
- Improve the UI, charts, or accessibility.
- Add tests, especially for data-resolution edge cases.

Please search existing issues first. For data problems, state whether the value
is wrong in this project or also wrong at the upstream source — the latter is
usually an upstream report, not a bug here.

## Development setup

Requirements: Python 3.11+ (3.13 recommended), Windows 10/11 for the packaged
build. The source runs on other platforms with PySide6, but only the Windows
portable build is officially supported.

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,build]"
```

Build a dataset (needs internet; ~2–4 minutes on a warm cache):

```powershell
python scripts/refresh_data.py
```

Run the app:

```powershell
python -m worlddata.ui.app
```

## Tests

```powershell
python -m ruff check src scripts tests
python -m pytest -q
```

Test layers:

- `tests/test_config.py`, `test_stats.py`, `test_views.py`,
  `test_correlations.py`, `test_groups.py`, `test_manual_import.py`,
  `test_settings.py` — fast unit tests with synthetic data, no network.
- `tests/test_build.py` — end-to-end synthetic build: normalization,
  quarantine, derived indicators, SQLite, manifest checksums, quality gates.
- `tests/test_integration.py` — runs against the real built database and is
  skipped automatically when `data/worlddata.sqlite` is absent.
- `tests/test_ui_smoke.py` — creates the Qt window offscreen and navigates the
  pages; skipped when the database is absent.

CI runs lint and the full suite on Windows with Python 3.11 and 3.13.

## Code style

- Ruff configuration lives in `pyproject.toml`; run `python -m ruff check`.
- Type hints on public functions; keep the analysis core free of Qt imports.
- Prefer small, testable functions. Statistical formulas belong in
  `src/worlddata/core/stats.py`, not in UI pages.
- Docstrings explain *why* a rule exists (for example, why IMF projections are
  excluded). Avoid narrating obvious code.
- Keep the UI responsive: heavy work goes through `TaskRunner` (Qt thread pool),
  never the main thread.
- Do not add network calls to the app runtime. Only `scripts/refresh_data.py`
  and the fetch modules may use the network.

## Adding or changing an indicator

1. Add an entry to `config/indicators.yaml` (id, name, domain, unit, source,
   series, value column for OWID, direction, log flag, aggregation, valid range,
   attribution).
2. If the source is new, add it to `config/sources.yaml` and implement a
   fetcher under `src/worlddata/ingest/`.
3. Refresh and validate:

   ```powershell
   python scripts/refresh_data.py
   python scripts/validate_data.py --strict
   ```

4. Regenerate the catalogue and check the diff:

   ```powershell
   python tools/gen_docs.py
   ```

5. Add or update a test if the indicator has special resolution rules.

Derived indicators use a `derive: {op: ratio, numerator, denominator,
multiplier}` block and may reference hidden input indicators (`hidden: true`).
Manual indices use `source: manual` and are imported with
`scripts/import_manual.py`; they are never downloaded or redistributed.

### Choosing direction and aggregation

- `higher_is_better`: `true`, `false`, or `null` (neutral). This drives
  percentile bars and “best/worst” labels, not the correlation math.
- `aggregation`: `median` for rates and per-capita values, `sum` for totals,
  `weighted` for population-weighted shares. Never sum a per-capita value.
- `is_composite: true` for indices built from other indicators; the UI warns
  when such an index is correlated with a component.

## Adding a group

Edit `config/groups.yaml`:

- Explicit membership uses `members: [ISO3, ...]`.
- Derived membership uses `selector:` on a country field (`continent`,
  `income_group`, …) or on an indicator threshold (for example V-Dem ≥ 0.5).
- Groups may overlap; mixed countries may appear in several cultural groups.
  Write the operational definition in `description`.

Then rebuild (`python scripts/build_db.py`) so `group_member` is materialised,
and regenerate `docs/GROUPS.md` with `python tools/gen_docs.py`.

## Country names and aliases

Canonical entities live in `config/countries.yaml` (ISO 3166-1 alpha-3 keys,
197 default states plus 22 territories). Source-specific names belong in
`config/aliases.yaml`. Add an alias rather than renaming a country; the
resolver also normalises accents, punctuation and case. If a source starts
returning a new name, run the refresh and inspect `data/unresolved.csv`.

## Documentation

- `docs/INDICATORS.md` and `docs/GROUPS.md` are generated; do not edit them by
  hand. Run `python tools/gen_docs.py`.
- Update `docs/USAGE.md` for user-visible behaviour changes.
- Update `docs/DATA.md` for pipeline or data-source changes.
- Update `CHANGELOG.md` under “Unreleased”.
- UI changes should include a screenshot; put it in `docs/screenshots/` and
  reference it from the relevant doc.

## Pull requests

- One logical change per PR. Describe the motivation and the result.
- Include tests for behavioural changes. Data-only changes should include the
  coverage impact.
- Run `python -m ruff check src scripts tests && python -m pytest -q`.
- Do not commit generated data (`data/raw/`, `*.sqlite`, `manifest.json`,
  `quality_report.csv`, `rejected.csv`), virtual environments, `build/`,
  `dist/`, or local settings/logs.
- Confirm you have the right to contribute the code and that you agree it is
  licensed under the project's MIT licence.

## Commit messages

Conventional Commits are welcome but not mandatory, for example:

```
feat: add IMF general government debt indicator
fix: resolve “Congo, Dem. Rep.” aliases
docs: describe same-year correlation mode
```

## Questions

Open a discussion or an issue. For security reports, follow
[SECURITY.md](SECURITY.md).
