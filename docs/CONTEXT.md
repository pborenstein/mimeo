---
phase: 7
phase_name: CLI Redesign
updated: 2026-04-03
last_commit: 90c5c7f
---

## Current Focus

Fixed race condition in `mimeo create`: GitHub template-generate API returns
before repo is accessible, causing 404s on all subsequent calls.

## Active Tasks

- [ ] E2E integration test lane (separate from unit tests, gated, hits real APIs)
- [ ] Template parameterization (substitute domain into template files)

## Blockers

None.

## Context

- `_wait_for_repo()` added to `GitHubHost` — polls up to 30s after generate before proceeding
- `_gh_api` now includes `METHOD endpoint` in error messages for easier diagnosis
- Race condition surfaced via improved error messages added earlier this session
- 233 tests passing; mypy and ruff clean

## Next Session

Consider E2E integration tests or template parameterization as next feature work.
