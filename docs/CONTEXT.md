---
phase: 6
phase_name: Hardening
updated: 2026-02-17
last_commit: to-be-set
---

## Current Focus

Phase 6 Hardening underway. `mimeo doctor` preflight command implemented and tested (177 tests passing).

## Active Tasks

- [x] Refresh README to current state
- [x] Document workflow scope requirement
- [x] Document uv tool install for global CLI access
- [x] Archive PLAN.md with historical notice
- [x] Update IMPLEMENTATION.md with Phase 6 plan
- [x] Add `mimeo doctor` preflight command
- [ ] Improve failure taxonomy and exit codes
- [ ] Reconciliation / DNS drift detection
- [ ] Add `--workers` option to `create`
- [ ] Retry with jitter for transient failures

## Blockers

None.

## Context

- `mimeo doctor` checks: Python >=3.11, gh installed, gh authenticated, workflow scope, config valid
- Each check returns (ok, detail, fix) tuple — helper functions are independently testable
- 177 tests total (was 160, +17 for doctor)
- Pre-existing mypy warning in cli.py (heterogeneous dict) — known, not blocking

## Next Session

Continue Phase 6: improve failure taxonomy and exit codes (config / auth / rate-limit / transient / provider), or discuss template feature.
