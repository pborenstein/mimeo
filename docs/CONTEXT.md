---
phase: 8
phase_name: Consolidation
updated: 2026-09-09
last_commit: 237c35a
---

## Current Focus

On branch `stage-5a-create-absorbs-template-apply` (not merged to main).
Stage 5D (registration cleanup, validation pass, doc rewrite) is now
complete — all of Stage 5 (DEC-025's 9-verbs-to-5 collapse) is done.
Ready to merge, or move to the queued QoL fixes / Stage 5E.

## Active Tasks

- [ ] Merge `stage-5a-create-absorbs-template-apply` to `main`.
- [ ] **QoL**: `mimeo create` with no domain args should print full help,
      not Click's terse "Missing argument" error.
- [ ] **QoL**: `status`'s summary line should point at `sync` for fixable
      problems, not just count them.
- [ ] **Stage 5E**: `template lint`. Blocked on DEC-024 implementation.
- [ ] **Track B**: Stage 4 E2E test lane, blocked on test account/org.
- [ ] **Backlog**: dead `max_retries`/`backoff_factor` params in `http.py`.

## Blockers

Stage 5E blocked on DEC-024 implementation. Everything else unblocked.

## Context

- DEC-025 covers the full Stage 5 verb collapse (5A/5B/5C/5D); DEC-026
  covers `create`'s safety checks found during 5A.
- 294 tests passing, mypy/ruff clean as of this session.
- docs/LIST_COMMAND.md was deleted this session (documented the deleted
  `list` command); README.md and ARCHITECTURE.md were rewritten to match
  the 5-verb surface — no more stale refs to `dns.py`/`fix.py`/`list_cmd.py`
  in live docs.
- Real credentials configured at `~/.config/mimeo/config.toml` (github
  org `tepiton`) — live testing is possible.

## Next Session

Decide whether to merge the branch now or continue with the queued QoL
fixes first. CONTRIBUTING.md and .github/ were checked this session —
no stale references to deleted files.
