---
phase: 6
phase_name: Hardening
updated: 2026-02-17
last_commit: 7a3f2e2
---

## Current Focus

Phase 6 Hardening complete. Failure taxonomy and exit codes landed this session.

## Active Tasks

- [x] Add `mimeo doctor` preflight command
- [x] Retry with jitter for transient failures
- [x] Improve failure taxonomy and exit codes
- [ ] Reconciliation / DNS drift detection
- [ ] Add `--workers` option to `create`
- [ ] E2E integration test lane
- [ ] Config schema versioning
- [ ] Structured logging (`--log-format json`)

## Blockers

None.

## Context

- 198 tests passing; mypy and ruff clean
- Exit codes: 2=config, 3=auth, 4=rate-limit, 5=transient, 6=partial
- EXIT_* constants in mimeo/exceptions.py; _categorize_error() in cli.py
- Error messages prefixed [category] e.g. "[config] missing api key"
- Next big direction: --type / template system (eleventy, astro, landing)

## Next Session

Start template/type system: --type flag on create, multiple content generators,
workflow variants (static.yml vs build workflows for SSGs).
