---
phase: 8
phase_name: Consolidation
updated: 2026-09-09
last_commit: 237c35a
---

## Current Focus

On branch `stage-5a-create-absorbs-template-apply` (not merged to main).
Stage 5D and both queued QoL fixes are done — all of Stage 5 (DEC-025's
9-verbs-to-5 collapse) plus its follow-up polish is complete. Ready to
merge, or move to Stage 5E.

## Active Tasks

- [ ] Merge `stage-5a-create-absorbs-template-apply` to `main`.
- [ ] **Stage 5E**: `template lint`. Blocked on DEC-024 implementation.
- [ ] **Track B**: Stage 4 E2E test lane, blocked on test account/org.
- [ ] **Backlog**: dead `max_retries`/`backoff_factor` params in `http.py`.

## Blockers

Stage 5E blocked on DEC-024 implementation. Everything else unblocked.

## Context

- DEC-025 covers the full Stage 5 verb collapse (5A/5B/5C/5D); DEC-026
  covers `create`'s safety checks found during 5A.
- 296 tests passing, mypy/ruff clean as of this session.
- `create` with no domain args now prints full `--help` (exit 2) instead
  of Click's terse "Missing argument" error — dropped `required=True` on
  the argument, check moved into the command body via `ctx.get_help()`.
- `status`'s text summary now appends "(N fixable with: mimeo sync)" when
  any reported problem is something sync can actually converge (NS
  mismatch, DNS drift/missing, HTTPS-fixable cert) — verified live
  against the real 113-domain fleet (86 issues, 42 sync-fixable).
- Real credentials configured at `~/.config/mimeo/config.toml` (github
  org `tepiton`) — live testing is possible.

## Next Session

Decide whether to merge the branch now or start Stage 5E once DEC-024
lands.
