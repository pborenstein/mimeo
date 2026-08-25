---
phase: 8
phase_name: Consolidation
updated: 2026-08-25
last_commit: 3663e8f
---

## Current Focus

Phase 8 Stages 1-3 done (engine, status, sync, identity fix; see DEC-021).
Since then: `status --with-dns`, `defaults.ignore_domains`, and (this
session) default-template customization -- `mimeo.lol`'s hardcoded name is
now rewritten to the target domain after `create`/`template apply`.

## Active Tasks

- [ ] Stage 4: E2E test lane (gated, real APIs, covers create/status/sync)
- [ ] Fold `process_domains_concurrent` (create, dns repair, template apply)
      into `map_items` (Stage 1 follow-up)
- [ ] Template parameterization for `eleventy-*` templates (mimeo.lol done;
      full site generators need a different, template-aware approach)

## Blockers

None.

## Context

- Engine: `map_items` (ordered, exceptions -> error rows), `render_results`
  (json/csv uniform, text via callback), `exit_on_errors` (partial ->
  EXIT_PARTIAL 6, total failure -> category code)
- `status` and `sync` both require --all for fleet-wide; DNS column "-" when
  no repo; `sync` acts on missing records only, never deletes extras
- Template-generate race, 2nd instance: `generate`-from-template returns
  before GitHub populates the file tree, so an immediate contents-API read
  can 404 "repository is empty" (same class as Entry 30's `_wait_for_repo`,
  different endpoint). `_customize_default_template` retries 5x/2s; a first
  attempt that swallowed the error instead shipped silently broken
- 293 tests passing; mypy and ruff clean; template apply live-verified
  against tepiton/tantamount.rodeo

## Next Session

Stage 4: E2E test lane, or eleventy-* template parameterization if that's
the priority instead.
