# Development guide

See [CONTRIBUTING](../CONTRIBUTING.md) for the contribution workflow and
[ARCHITECTURE](ARCHITECTURE.md) for the design. This page is the hands-on
reference for working on the code.

## Environment

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,build]"
```

Extras:

| Extra | Contents |
| --- | --- |
| `dev` | pytest, pytest-qt, ruff, mypy |
| `build` | PyInstaller |

Runtime dependencies: pandas, NumPy, SciPy, matplotlib, PySide6, pydantic,
PyYAML, requests, tenacity, openpyxl, pycountry.

## Everyday commands

| Task | Command |
| --- | --- |
| Run the app | `python -m worlddata.ui.app` |
| Run the app and log startup | `$env:WDC_DEBUG="1"; python -m worlddata.ui.app` (log in `%TEMP%\WorldDataComparison-selftest.log`) |
| Fetch + build data | `python scripts/refresh_data.py` |
| Offline rebuild | `python scripts/build_db.py` |
| Validate data | `python scripts/validate_data.py --strict` |
| Import a manual index | `python scripts/import_manual.py --indicator pisa_math --file pisa.csv` |
| Show dataset info | `python -m worlddata.cli info` |
| Lint | `python -m ruff check src scripts tests` |
| Type-check (best effort) | `python -m mypy src` |
| Test | `python -m pytest -q` |
| Single test | `python -m pytest tests/test_stats.py -q` |
| Build the portable app | `powershell -ExecutionPolicy Bypass -File build.ps1` |
| Regenerate indicator/group docs | `python tools/gen_docs.py` |
| Check documentation links | `python tools/check_links.py` |
| Regenerate the country registry | `python tools/gen_countries.py` |

`build.ps1` performs lint, tests, PyInstaller, the packaged `--selftest`, the
portable layout assembly, and the zip.

## Test architecture

```
tests/
  conftest.py              synthetic dataset factory, real-repo fixture, offscreen Qt
  test_config.py           contracts, alias resolution (35 cases)
  test_stats.py            scipy references, BH-FDR, effect sizes, guards
  test_correlations.py     synthetic relations, log/outliers/same-year/partial
  test_groups.py           aggregation modes, tests, overlays
  test_views.py            rankings, profiles, percentiles, coverage
  test_build.py            end-to-end synthetic build, manifest, gates
  test_manual_import.py    CSV canonicalisation and snapshot writing
  test_settings.py         settings round-trip and fallbacks
  test_integration.py      real DB, golden values, statistical sign checks (skips if absent)
  test_ui_smoke.py         Qt window, page navigation (skips if DB absent)
```

Fixtures:

- `factory` / `dataset_factory` builds an in-memory `Dataset` from nested
  dictionaries. Use it for statistical tests; do not hit SQLite.
- `real_repo` opens `data/worlddata.sqlite` and skips the test when the data is
  missing, so a fresh clone can run CI without a snapshot.
- `qtbot` comes from pytest-qt. `conftest.py` sets `QT_QPA_PLATFORM=offscreen`
  before Qt is imported.

Guidelines:

- Unit tests must not use the network.
- Synthetic tests should exercise edge cases explicitly: missing values,
  zero variance, perfect correlation, outliers, equal years, self-control.
- When fixing a data-resolution bug, add the exact failing name to
  `test_config.py`.
- When changing correlation math, keep a reference comparison (SciPy or a
  hand-computed constant) in the test.

## Adding an indicator

1. Add a config entry to `config/indicators.yaml`.
2. If the source already exists, map the series in the fetcher config
   (`series`, `value_column`, or a `derive` block). No Python change is needed
   for World Bank, IMF or OWID series.
3. Refresh and validate.
4. Run `python tools/gen_docs.py` to update the catalogue.
5. If the indicator is sparse (<60% coverage), the quality gate still passes as
   long as at least 50 automated indicators are above the threshold; the
   coverage is visible in the UI.

### New source checklist

- Add to `config/sources.yaml` with licence, attribution, redistributable flag.
- Implement `src/worlddata/ingest/<source>.py` exposing `fetch_all(...)`
  returning `{indicator_id: DataFrame}` with `iso3`/`code`, `name`, `year`,
  `value` columns.
- Register the dispatch in `build.py`.
- Add it to `_retrieved_at` source stamps.
- Add a test with a cached fixture frame if the source has unusual shapes.
- Update `NOTICE.txt`, `docs/DATA.md`, the About page source list, and
  `docs/INDICATORS.md`.

## Schema changes

The schema lives in `db.SCHEMA` and `worlddata.SCHEMA_VERSION`.

- Bump `SCHEMA_VERSION` for any change that existing databases cannot satisfy.
- Rebuild the shipped database.
- Add or update a test in `test_build.py`.
- The app refuses mismatched schemas; document the migration/rebuild in
  `docs/DATA.md` and `CHANGELOG.md`.
- There is no in-place migration script yet; rebuilding from snapshots is the
  supported path.

## Adding a page

1. Create `src/worlddata/ui/pages/<name>.py` subclassing `Page`.
2. Implement `on_show()` (build/recompute) and `on_theme_changed()` (re-render
   charts).
3. Use `AppContext` for data; never open SQLite directly.
4. Add the page to `PAGE_ORDER` and the page-class map in `main_window.py`.
5. Give shortcuts a slot; `Ctrl+1…7` are assigned in order.
6. Add an offscreen smoke assertion in `test_ui_smoke.py`.
7. Add a screenshot to `docs/screenshots/` and update `docs/USAGE.md`.

## UI conventions

- Object names used by the QSS: `Card`, `PageTitle`, `PageSubtitle`,
  `SectionTitle`, `Muted`, `Caveat`, `CardValue`, `CardLabel`, `Nav`, `Primary`.
- Charts go through `ChartPanel`; call `reset()` then `draw()`. The figure
  background follows the active theme.
- Tables go through `DataTable`, which supplies sorting, filtering, copy and
  export-friendly data.
- Long-running work goes through `MainWindow.task_runner.run(...)` and a
  generation counter if the user can change options concurrently.
- Never block the main thread on a correlation or data load.

## Packaging and frozen-app debugging

```powershell
python -m PyInstaller --noconfirm --clean WorldDataComparison.spec
python -c "import subprocess; print(subprocess.run([r'dist\WorldDataComparison\WorldDataComparison.exe','--selftest']).returncode)"
```

- `--selftest` renders every page and exits 0/2; it writes `selftest.log` beside
  the executable.
- Raw PyInstaller output keeps `config/` and `data/` in `_internal/`; `paths`
  falls back there. `build.ps1` copies them beside the exe for the portable
  layout and removes the duplicates.
- The Qt runtime excludes Quick/QML/Pdf/OpenGL/translations to trim the bundle.
  If a future feature needs those modules, remove the corresponding entries
  from `QT_SKIP` / `excludes` in the spec.
- `pycountry` is a build-time dependency only; it is excluded from the frozen
  app.

## Performance

Targets: visible window in ≤5 s packaged, dataset load <1 s, default
correlation run <3 s, table render <200 ms.

- Profile with `python -X importtime -m worlddata.ui.app` (source) or the
  packaged `selftest.log` timestamps.
- Correlations are O(pairs × countries); avoid adding per-pair Python loops
  beyond the current structure.
- Cache options results in `AppContext`; clear the cache when the dataset
  changes.

## Common issues

| Symptom | Cause / fix |
| --- | --- |
| `No module named worlddata` | Run from the repo root or `pip install -e .` |
| Tests skip integration/UI | `data/worlddata.sqlite` is absent; run `refresh_data.py` |
| `DataError: checksum` | Replace DB and manifest from the same build |
| Qt platform plugin error in CI | Set `QT_QPA_PLATFORM=offscreen` |
| PyInstaller cannot find `theme.qss` | The QSS lives in `theme.py`; do not add a file data entry |
| Fetch jobs look stalled | Increase verbosity with `WDC_DEBUG=1` only for app startup; fetchers print failures per series |
| A source returns a renamed country | Add an alias; inspect `data/unresolved.csv` |
