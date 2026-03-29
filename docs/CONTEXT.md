---
phase: 7
phase_name: CLI Redesign
updated: 2026-03-28
last_commit: 908ffa0
---

## Current Focus

All documentation (README, ARCHITECTURE, TROUBLESHOOTING, docs/README) aligned
with current codebase after CLI redesign and code review fixes.

## Active Tasks

- [ ] E2E integration test lane (separate from unit tests, gated, hits real APIs)
- [ ] Template parameterization (substitute domain into template files)

## Blockers

None.

## Context

- 233 tests passing; mypy and ruff clean
- All user-facing docs audited and updated to match code
- Key stale references fixed: --fix/--dns-check removed from list, content.py references removed, NSMismatchError removed, exit codes updated, Domain model removed
- ARCHITECTURE.md fully rewritten to reflect cli/ package structure and new commands

## Next Session

Consider E2E integration tests or template parameterization as next feature work.
