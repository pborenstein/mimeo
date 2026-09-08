---
phase: 8
phase_name: Consolidation
updated: 2026-09-08
last_commit: b94685c
---

## Current Focus

On branch `stage-5a-create-absorbs-template-apply` (not merged to main).
Stage 5A (`create` absorbs `template apply`, DEC-026) is committed. Stage
5B (`status` absorbs `list`/`registrar list`/`dns show`/`dns check` via
`--source {github,porkbun,dns}`) is complete but **not yet committed** —
commit it before anything else. User chose to keep stacking sub-stages on
this one branch rather than PR-per-stage.

## Active Tasks

- [ ] **Commit Stage 5B** (uncommitted): `status.py`/`dns.py`/`__init__.py`
      rewritten, `list_cmd.py`/`registrar.py` deleted, tests relocated to
      `test_status.py` (296 passing, ruff/mypy clean).
- [ ] **Live-verify Stage 5B**: no provider credentials on this machine, so
      5B was only mock/CLI-help verified, never against a real account —
      do this before trusting it the way DEC-026 needed live testing to surface.
- [ ] **Stage 5C (start here)**: `sync` absorbs `dns repair`/`fix https`.
      Read DEC-025's "Open question" section first. Full steps in
      IMPLEMENTATION.md Stage 5C.
- [ ] **Stage 5D**: cleanup + full test/mypy/ruff pass + README update
      (README's `mimeo template apply` refs are stale from 5A too).
- [ ] **Stage 5E**: `template lint`. Blocked on DEC-024 implementation.
- [ ] **Track B**: Stage 4 E2E test lane, blocked on test account/org.
- [ ] **Backlog**: dead `max_retries`/`backoff_factor` params in `http.py`.

## Blockers

Stage 5E blocked on DEC-024 implementation. Everything else unblocked.

## Context

- DEC-026 explains `create`'s current safety checks (ownership check, DNS
  skip on pre-existing repo, no propagation poll) — read it before touching
  `create.py`/`github.py`'s template path.
- DEC-025 supersedes DEC-021's "keep dns repair/fix https as scalpels"
  call — don't re-litigate, just work the Stage 5 checklist.
- No provider-layer (`github.py`/`porkbun.py`) changes in Stage 5 outside
  DEC-026's fixes.
- Stage 5B: `--source dns` has no fleet-wide mode (domains must be named);
  `--problems` doubles as the dns-show-vs-dns-check switch when combined
  with `--source dns`; `--show-template` is new on `status` itself.
- Prefer testing provider-touching CLI changes (create/sync/status) against
  a real domain/repo, not mocks alone — DEC-026's bugs were invisible to
  mocks that didn't model the ownership/existing-repo distinction.

## Next Session

Commit Stage 5B, then either live-verify it or move to Stage 5C — read
DEC-025's "Open question" section before writing any 5C code.
