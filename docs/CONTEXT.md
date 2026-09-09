---
phase: 8
phase_name: Consolidation
updated: 2026-09-09
last_commit: 56d75bd
---

## Current Focus

Stage 5 (DEC-025's 9-verbs-to-5 collapse: 5A-5D) is merged to `main` and
pushed (merge commit `56d75bd`, real merge not a fast-forward, per user
request). `template lint` was split out of Stage 5 (was "5E") into its
own Stage 6, since it validates DEC-024's manifest schema rather than
collapsing existing verbs.

## Active Tasks

- [ ] **Stage 6**: `template lint`. Blocked on DEC-024 implementation.
- [ ] **Track B**: Stage 4 E2E test lane, blocked on test account/org.
- [ ] **Backlog**: dead `max_retries`/`backoff_factor` params in `http.py`.

## Blockers

Stage 6 blocked on DEC-024 implementation. Everything else unblocked.

## Context

- DEC-025 status updated to Complete and merged; DEC-026 covers
  `create`'s safety fixes found during 5A.
- 296 tests passing, mypy/ruff clean on `main` post-merge (re-verified).
- `mimeo/cli/dns.py`, `fix.py`, `list_cmd.py`, `registrar.py`,
  `template.py`, and `docs/LIST_COMMAND.md` are gone from `main` now.
  `create`, `status`, `sync`, `doctor` are the full CLI surface until
  Stage 6 adds `template lint`.
- Real credentials configured at `~/.config/mimeo/config.toml` (github
  org `tepiton`) — live testing is possible.

## Next Session

No active work queued except Stage 6 (blocked) and the one backlog
item above. Check in with the user for direction, or start on DEC-024
if ready to unblock Stage 6.
