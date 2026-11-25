# Frequently asked questions

### Is this a live data service?

No. The app is a reader for a validated local snapshot. Updates are explicit:
run `scripts/refresh_data.py`, then replace the database and manifest (or use
the packaged app's data folder). Nothing is fetched while the window is open.

### Why do some values differ from the World Bank / IMF / OWID website?

Upstream series are revised, the snapshot has a build date and a recency
cutoff, and some values are converted to the declared unit. This project does
not invent or adjust values; every row carries its source year. If a value is
wrong at the source, it is an upstream issue — please include the source URL in
a bug report.

### Why do correlations mix years?

Pairs use the newest available value per country, so GDP 2025 can be paired
with Gini 2021. This is standard cross-sectional practice but should be read
with care. The pair table reports the median year gap, and **Same year** mode
restricts a pair to identical years at the cost of a much smaller N.

### Why is Gini from 2015 while GDP is from 2025?

Gini comes from household surveys that are not run every year in every
country. The app shows the newest survey value at or after the cutoff and
flags the source year. The Data quality page counts countries whose latest
value predates the cutoff.

### Why 197 countries instead of 193?

The default set is the 193 UN members plus Vatican City and Palestine
(observers), Taiwan and Kosovo. Dependent territories are stored but hidden
behind “Include dependent territories” so they do not skew group averages.

### Why is country X missing a value?

Many series are sparse: Gini, literacy, hospital beds, PISA, working hours,
and some governance indices. Others do not publish Taiwan, Kosovo or Palestine.
Coverage is shown per indicator and per country; gaps are never filled with
zero or an average.

### Why is the EIU Democracy Index missing?

It is commercially licensed and cannot be redistributed. V-Dem, Freedom House
and the World Bank governance indicators are the free substitutes included
here. EIU can be imported privately after adding a manual indicator entry
(see [DATA](DATA.md)).

### How do I add an indicator or my own data?

- Automated source: add a `config/indicators.yaml` entry and refresh.
- Manual index: add an entry with `source: manual`, then
  `python scripts/import_manual.py --indicator <id> --file <csv>`.

The full contract is in [DATA](DATA.md) and [CONTRIBUTING](../CONTRIBUTING.md).

### Can I use this commercially?

The application code is MIT. The data is not: each source has its own terms,
and some OWID-delivered series (for example V-Dem) carry share-alike terms.
Check `NOTICE.txt` and `config/sources.yaml` before redistributing a bundle.

### Why is the download so large?

PySide6, SciPy, pandas and matplotlib are bundled for a fully offline,
install-free app. Unused Qt modules (Quick/QML/Pdf/OpenGL), translations and
pycountry are stripped. The uncompressed folder is ~283 MB; the zip is ~110 MB.

### Why does Windows SmartScreen warn me?

The executable is not code-signed. Use “More info → Run anyway”, or run from
source. Code signing can be added without changing the build.

### Can I run it on macOS or Linux?

The source is cross-platform (PySide6 and matplotlib), and tests run offscreen,
but only the Windows portable build is supported and released. On Linux you may
need the usual Qt/X11 libraries.

### Why is there no map or a full trend page?

Both are deliberately deferred. The database already retains 2010→present
history, so a trend view can be added without re-downloading data; a
choropleth needs an open-licence SVG map with ISO3 path mapping. See the
roadmap in `CHANGELOG.md`.

### What does “partial r” mean?

It is the Pearson correlation of the residuals after both variables are
regressed on a control (default GDP per capita PPP). It answers “is there still
a relationship after accounting for development level?”. It is not a causal
estimate and is omitted when the control is one of the pair variables.

### What is q, and how is it different from p?

`p` is the per-pair two-tailed p value. `q` is the Benjamini–Hochberg
false-discovery-rate adjusted value across all pairs in the run. Filtering the
visible table does not recompute `q`; the adjustment family is the full run.

### Why is HDI correlated with life expectancy?

HDI is a composite that includes life expectancy. Composite-versus-component
correlations are partly tautological; the app flags composites and offers an
“Exclude composites” toggle. The same applies to CPI/WGI, V-Dem indices and
similar constructs.

### How often is the data updated?

Whenever a maintainer runs the refresh and publishes a release. The cadence is
not tied to the app; the About/status bar and `manifest.json` show the exact
build id and snapshot date.

### How do I update the portable app without rebuilding it?

Close the app, replace `data/worlddata.sqlite` **and** `data/manifest.json`
from the same build, then relaunch. The manifest checksum is verified; a
mismatch is refused. Settings and local group edits are preserved.

### Where are settings stored?

`data/settings.json` (or `%APPDATA%\WorldDataComparison\settings.json` when the
folder is read-only) and group overrides in `data/groups.local.yaml`. Delete
them to reset the interface.

### Can I compare overlapping groups?

Yes. Groups are many-to-many, and the same country can appear in the EU, NATO
and a cultural family. Each aggregate reports its own coverage; “rest of world”
excludes all members of all selected groups to avoid double counting.

### Why do group medians differ from World Bank regional aggregates?

The app computes group statistics from member countries with its own
aggregation rules; World Bank regional aggregates use weighted methodologies
that are not directly comparable. The UI states whether a group value is a
median, sum, mean or population-weighted mean.

### Does the app send telemetry?

No. There is no network access at runtime and no analytics. The only outbound
traffic is from the refresh/import scripts when you explicitly run them.

### How do I report a wrong statistic?

Open an issue with the country, indicator, value, source year, the expected
value, and the upstream URL. For security issues, follow
[SECURITY](../SECURITY.md). For a missing alias, include the exact source name;
it is usually a one-line addition to `config/aliases.yaml`.
