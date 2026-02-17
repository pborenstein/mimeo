---
phase: 5
phase_name: CLI Integration
updated: 2026-02-16
last_commit: ebb9d67
---

## Current Focus

Added `--health` and `--fix` flags to `mimeo list`. Health check fetches Pages API data per repo concurrently; fix enables HTTPS enforcement for sites with approved certs. Tabular output replaces card format for readability at scale.

## Active Tasks

- [x] Add get_pages_health() to GitHubHost
- [x] Add _health_status() helper (pages_error/no_cert/cert_pending/fixable/healthy)
- [x] Add --health flag: concurrent Pages API fetch, adds status to all output formats
- [x] Add --fix flag: enables HTTPS for fixable repos, prints fix summary
- [x] Tabular text output sorted by severity then name
- [x] 160 tests passing
- [ ] Document workflow scope requirement in setup docs
- [ ] Document uv tool install for global CLI access

## Blockers

None.

## Context

- get_pages_health() returns pages_configured, https_enforced, cert_state, pages_status
- _health_status() is module-level (exported), used by CLI layer
- --fix implies --health; fix runs serially after concurrent health fetch
- Sort order: pages_error, no_cert, cert_pending, fixable, healthy (problems first)
- Text table: NAME / SITE / UPDATED / STATUS (status color-coded); repo URL dropped (redundant)
- JSON/CSV include health, https_enforced, cert_state fields when --health given
- Pre-existing mypy error in cli.py (heterogeneous dict, unrelated to this work)

## Next Session

Documentation: setup guide covering workflow scope token requirement and uv tool install. Consider Phase 6 polish (rollback, integration tests, README).
