---
phase: 8
phase_name: Consolidation
updated: 2026-09-09
last_commit: 497f43f
---

## Current Focus

On branch `stage-5a-create-absorbs-template-apply` (not merged to main).
Stages 5A, 5B, and 5C of DEC-025's 9-verbs-to-5 collapse are implemented
and committed, plus two bugs found via live testing (`585e489`, `053ff52`,
`497f43f` — see DEC-025/IMPLEMENTATION.md). Next up is Stage 5D (cleanup).

## Active Tasks

- [ ] **Stage 5D**: registration cleanup, full test/mypy/ruff pass, then
      doc rewrite. README.md/TROUBLESHOOTING.md got minimal fixes during
      5C but still have older stale refs (`mimeo list --health`, etc.)
      from 5A/5B. `ARCHITECTURE.md` needs a structural rewrite (still
      names deleted `dns.py`/`fix.py` files). Full checklist in
      IMPLEMENTATION.md Stage 5D.
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

- DEC-026 explains `create`'s safety checks; DEC-025 covers the Stage 5
  verb collapse, including both bugs found this session.
- No provider-layer changes in Stage 5 outside DEC-026/bug fixes.
- Prefer live-testing provider-touching CLI changes — both bugs this
  session were invisible to mocks, same lesson as DEC-026.
- Real credentials configured at `~/.config/mimeo/config.toml` (github
  org `tepiton`) — don't assume no live testing is possible.

## Next Session

Start Stage 5D: registration cleanup, full test/mypy/ruff pass, then the
README/ARCHITECTURE.md doc rewrite (see IMPLEMENTATION.md for the full
list). Two QoL fixes are queued after that.
