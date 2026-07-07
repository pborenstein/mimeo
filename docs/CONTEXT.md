---
phase: 8
phase_name: Consolidation
updated: 2026-07-06
last_commit: b53a591
---

## Current Focus

Phase 8 Stage 1 done: shared domain-operation engine (`map_items`,
`render_results`, `exit_on_errors`) in `_processing.py`; five commands
migrated off hand-rolled thread pools and format dispatch. See DEC-021.

## Active Tasks

- [ ] Stage 2: `mimeo status` (cross-provider join: registrar x DNS x Pages)
- [ ] Stage 3: `mimeo sync` (converge: DNS repair + HTTPS enforcement)
- [ ] Stage 4: E2E test lane (gated, real APIs, covers create/status/sync)
- [ ] Identity fix ("Provision and manage custom-domain sites on GitHub Pages")
- [ ] Template parameterization (carried from Phase 7)

## Blockers

None.

## Context

- Engine: `map_items` (ordered, exceptions -> error rows), `render_results`
  (json/csv uniform, text via callback), `exit_on_errors` (partial ->
  EXIT_PARTIAL 6, total failure -> category code)
- Exit codes unified: dns show partial failure now EXIT_PARTIAL (was transient)
- `process_domains_concurrent` (create, dns repair, template apply) still
  duplicates the pool — folding it in is a Stage 1 follow-up task
- Template apply stays manual — content is a choice, not drift (DEC-021)
- 257 tests passing; mypy and ruff clean; live-verified dns show,
  registrar list, list against real APIs

## Next Session

Stage 2: `mimeo status` — cross-provider join built on map_items
(Porkbun domains x GitHub repos x DNS drift x Pages health).
