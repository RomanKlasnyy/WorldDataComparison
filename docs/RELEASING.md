# Release checklist

This is the procedure for publishing a GitHub release of
WorldDataComparison. It assumes Windows, Python 3.13, and a checkout with data
build access.

## 0. First-time repository setup

If the project is not yet a git repository:

```powershell
git init
git add .
git commit -m "chore: initial import"
git branch -M main
git remote add origin <repository-url>
git push -u origin main
```

The `.gitignore` excludes generated data (`data/raw`, `*.sqlite`,
`manifest.json`, reports), `build/`, `dist/` and local settings. The release
asset carries the validated data snapshot; the repository does not.

Then complete the one-time GitHub settings in step 7 (description, topics,
branch protection, security reporting, Discussions).

## 1. Pre-flight

- [ ] `git status` is clean (or only the intended release changes are present).
- [ ] CI is green on `main`.
- [ ] Open issues/PRs are triaged; no known data-integrity bug is unreleased.
- [ ] `NOTICE.txt`, `config/sources.yaml` and the About page reflect the
      current sources and licences.
- [ ] The README still matches the UI (features, screenshots, shortcuts).

## 2. Version bump

Update the same version in:

- [ ] `pyproject.toml` → `[project] version`
- [ ] `src/worlddata/__init__.py` → `__version__`
- [ ] `CITATION.cff` → `version` and `date-released`
- [ ] `CHANGELOG.md` → move “Unreleased” items under the new version with the
      date and a data-snapshot section
- [ ] README static version badge, test count and snapshot numbers
- [ ] Any version shown in docs

Schema version changes require `SCHEMA_VERSION` in
`src/worlddata/__init__.py` to be bumped and a rebuild.

## 3. Refresh and validate the data

```powershell
python scripts/refresh_data.py --force
python scripts/validate_data.py --strict
python tools/gen_docs.py
```

- [ ] All gates pass (69/69 automated indicators ≥60% coverage, zero
      duplicates, zero unresolved names, zero out-of-range rows).
- [ ] `docs/INDICATORS.md` and `docs/GROUPS.md` are regenerated and reviewed.
- [ ] The new `data/manifest.json` build id is recorded in the changelog.
- [ ] A spot check of 5–10 golden values against the upstream source is done.

## 4. Build and test

```powershell
python -m ruff check src scripts tests
python -m pytest -q
powershell -ExecutionPolicy Bypass -File build.ps1
```

`build.ps1` runs lint and tests, builds with PyInstaller, runs the packaged
`--selftest`, assembles the portable layout, and creates
`dist\WorldDataComparison-<version>.zip`.

- [ ] The packaged self-test exits 0.
- [ ] The zip contains `WorldDataComparison.exe`, `_internal/`, `config/`,
      `data/` (DB, manifest, coverage, rejected), `docs/`, `NOTICE.txt`,
      `LICENSE`, `README.md`, `CHANGELOG.md` and `CITATION.cff`.
- [ ] No `settings.json`, `groups.local.yaml`, `*.sqlite-wal`/`-shm` or
      `selftest.log` are in the zip.
- [ ] Extract the zip to a **fresh** folder outside the repo and run
      `WorldDataComparison.exe --selftest`; then launch it normally and check
      all seven pages.
- [ ] Extract to a path with a space and a non-ASCII character; verify startup.

## 5. Checksums

```powershell
Get-FileHash dist\WorldDataComparison-<version>.zip -Algorithm SHA256
```

Publish the SHA-256 next to the zip in the release notes. Do not reuse a hash
from a previous build.

## 6. Git tag and GitHub release

```powershell
git add -A
git commit -m "release: v<version>"
git tag -a v<version> -m "WorldDataComparison v<version>"
git push origin main
git push origin v<version>
```

The `Release` workflow (`.github/workflows/release.yml`) runs on a `v*` tag:
it refreshes data, validates, builds the zip, computes a checksum, uploads the
artifact, and creates a GitHub release. You can also trigger it manually with
**Actions → Release → Run workflow** (a manual run uploads the artifact but
does not create a tag/release).

If releasing manually:

```powershell
gh release create v<version> dist\WorldDataComparison-<version>.zip `
  --title "WorldDataComparison v<version>" --generate-notes
```

Release notes should include:

- One-paragraph summary
- Added / Changed / Fixed sections (mirroring CHANGELOG)
- Data snapshot build id, observation count, coverage summary
- Artifact filename and SHA-256
- Upgrade notes (replace `worlddata.sqlite` + `manifest.json` together)
- Known limitations

## 7. Repository settings (one-time)

- [ ] Description: “Offline desktop comparison of the latest country statistics
      with all-pairs correlation analysis and country-group comparisons.”
- [ ] Topics: `country-statistics`, `data-visualization`, `correlation`,
      `pyside6`, `world-bank`, `imf`, `our-world-in-data`, `open-data`,
      `desktop-app`, `python`.
- [ ] Enable Discussions (optional) and Issues.
- [ ] Enable the **Security** tab / private vulnerability reporting so
      `SECURITY.md` has a reporting channel.
- [ ] Protect `main`: require CI, require a pull request, no force pushes.
- [ ] Enable Dependabot alerts and version updates (`.github/dependabot.yml`).
- [ ] Add the CI badge to the README after the first workflow run by removing
      the comment markers and replacing `OWNER/REPO`:

      ```md
      [![CI](https://github.com/OWNER/REPO/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/ci.yml)
      ```

- [ ] Set a social preview image (the dashboard screenshot works).
- [ ] Add repository URLs to `pyproject.toml` `[project.urls]` and optionally
      `CITATION.cff` once the final URL exists.
- [ ] Confirm the MIT licence is detected and `NOTICE.txt` is linked from the
      README.
- [ ] Community profile is complete: README, LICENSE, CONTRIBUTING,
      CODE_OF_CONDUCT, SECURITY, SUPPORT, issue forms, PR template.
- [ ] Release-note categories are defined in `.github/release.yml`.
- [ ] `ROADMAP.md` reflects the next milestone.

## 8. Post-release

- [ ] Download the release asset on a clean Windows account and run it.
- [ ] Verify the published SHA-256.
- [ ] Announce with the data build id and a screenshot.
- [ ] Open a “next milestone” issue with the planned items from CHANGELOG.

## Notes

- The executable is unsigned. SmartScreen warnings are expected; document them
  in the release notes. Code signing can be added later without changing the
  build process.
- The zip is ~110 MB; GitHub's per-asset limit is well above that.
- Data is not committed to git. The release asset is the only place a bundled
  snapshot is distributed, together with its manifest and licences.
