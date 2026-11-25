## Summary

<!-- What does this PR change and why? Link the issue if one exists. -->

Fixes #

## Type

- [ ] Bug fix
- [ ] New indicator / data source
- [ ] New group / membership change
- [ ] Analysis or statistics change
- [ ] UI change
- [ ] Documentation
- [ ] Build / CI / packaging
- [ ] Refactor (no behaviour change)

## Testing

<!-- Commands run and results. -->

- [ ] `python -m ruff check src scripts tests`
- [ ] `python -m pytest -q`
- [ ] `python scripts/validate_data.py --strict` (for data changes)
- [ ] Packaged `--selftest` (for packaging/UI changes)

## Checklist

- [ ] One logical change; no unrelated reformatting.
- [ ] Tests added/updated for behavioural changes.
- [ ] Data changes include the coverage impact and a source/licence check.
- [ ] `docs/INDICATORS.md` / `docs/GROUPS.md` regenerated if the catalogue changed.
- [ ] `docs/USAGE.md` updated for user-visible behaviour.
- [ ] `CHANGELOG.md` updated under “Unreleased”.
- [ ] No generated data (`data/raw`, `*.sqlite`, manifest, reports), `build/`, `dist/` or local settings committed.
- [ ] Screenshots attached for UI changes.

## Screenshots / notes

<!-- Before/after, coverage tables, or anything reviewers should know. -->
