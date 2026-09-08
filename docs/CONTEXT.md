---
phase: 8
phase_name: Consolidation
updated: 2026-09-08
last_commit: 4568fe9
---

## Current Focus

Two design decisions landed this session, neither implemented yet:
DEC-024 (template domain-substitution manifest) and DEC-025 (collapse 9 CLI
verbs to 5: create/status/sync/doctor/template-lint). DEC-025 has a full
sub-stage checklist in IMPLEMENTATION.md Phase 8 Stage 5 — start there.

## Active Tasks

- [ ] **Stage 5A (start here)**: `create` absorbs `template apply` via
      `--force`/`--yes` flags. Self-contained, no dependency on DEC-024.
      Full steps in IMPLEMENTATION.md Stage 5A.
- [ ] **Stage 5B**: `status` absorbs `list`/`registrar list`/`dns show`/
      `dns check` via `--source {github,porkbun,dns}`. Largest test-
      relocation surface — do after 5A.
- [ ] **Stage 5C**: `sync` absorbs `dns repair`/`fix https`. Read DEC-025's
      "Open question" section FIRST — may already be a non-issue, needs
      checking before writing code.
- [ ] **Stage 5D**: registration cleanup + full test/mypy/ruff pass + README
      update. Do last among 5A-5D.
- [ ] **Stage 5E**: new `template lint` command. BLOCKED on DEC-024 landing
      first (validates the manifest schema DEC-024 defines).
- [ ] **DEC-024 implementation**: manifest schema + 3 format handlers
      (`js-key`, `string-replace`, `yaml-frontmatter-key`), replacing
      `_customize_default_template`. Needed before Stage 5E.
- [ ] **Track B: Stage 4 E2E test lane** — blocked on test account/org.
- [ ] **Backlog**: dead `max_retries`/`backoff_factor` params in `http.py`.

## Blockers

Stage 5E blocked on DEC-024 implementation. Everything else unblocked.

## Context

- DEC-025 is a plan document, not a decision to re-litigate — read it once,
  then work the IMPLEMENTATION.md Stage 5 checklist directly.
- DEC-025 explicitly supersedes DEC-021 Stage 3's "keep dns repair/fix
  https as scalpels" call — say so if touching that area, don't re-debate it.
- No provider-layer code changes in Stage 5 at all — `github.py`/
  `porkbun.py` untouched, this is CLI-layer flag consolidation only.
- Every Stage 5 sub-stage ends with relocating the old command's tests onto
  the merged command's new flags, not just deleting coverage.

## Next Session

Start Stage 5A (`create --force`/`--yes`) — it's independent of the other
sub-stages and has no open questions to resolve first.
