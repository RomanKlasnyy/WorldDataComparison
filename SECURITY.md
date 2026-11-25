# Security policy

## Supported versions

| Version | Supported |
| ------- | --------- |
| 0.1.x   | Yes       |

This is a local desktop application. It does not run a server, accept remote
connections, or send telemetry. The only network access happens when the user
explicitly runs the refresh scripts to download statistical snapshots.

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Use the
repository's **Security → Report a vulnerability** tab to open a private
advisory, or contact the maintainers listed on the repository profile.

Include:

- A description of the issue and its impact
- Steps to reproduce, with the app version and data build id
  (shown in the status bar and in `data/manifest.json`)
- The affected component (UI, database loader, importer, packaging)
- Any suggested mitigation

You can expect an initial acknowledgement within a reasonable timeframe. This
is a volunteer project, so timelines are best effort.

## Scope

In scope:

- Arbitrary code execution or path traversal through imported CSV/XLSX files
- SQL injection or unsafe database handling
- Crashes or data corruption caused by a maliciously crafted
  `worlddata.sqlite` / `manifest.json`
- Update or release-artifact integrity issues
- Leakage of local files through exports or logs

Out of scope:

- Statistical disagreements with the upstream sources
- Correlation-versus-causation misinterpretation
- Missing data for a country or indicator
- Windows SmartScreen warnings for an unsigned executable
- Vulnerabilities in third-party dependencies that have no exploitable path in
  this application (please report those upstream, and open an issue if the pin
  should change)

## Data integrity model

The application verifies `manifest.json` (schema version) and the SHA-256 of
`worlddata.sqlite` at startup. A mismatch is refused rather than silently
loaded. Do not trust a database copied from an untrusted source; rebuild it
from `data/raw` snapshots or from the upstream APIs.
