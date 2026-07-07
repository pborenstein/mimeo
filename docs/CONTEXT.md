---
phase: 8
phase_name: Consolidation
updated: 2026-07-06
last_commit: b53a591
---

## Current Focus

Phase 8 Stages 1-2 done: shared domain-operation engine in `_processing.py`
(five commands migrated), and `mimeo status` — the cross-provider join
(registrar x DNS drift x Pages health) with `--problems` filter. See DEC-021.

## Active Tasks
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
- `status`: no-arg = union of Porkbun domains and mimeo repos; DNS column
  "-" when no repo (no desired state); drift/unhealthy exit 0, API errors
  EXIT_PARTIAL
- Live drift finding on real domains: Porkbun wildcard parking CNAME
  (`* -> pixie.porkbun.com`) reported as extra — consistent with dns check
- `process_domains_concurrent` (create, dns repair, template apply) still
  duplicates the pool — folding it in is a Stage 1 follow-up task
- 264 tests passing; mypy and ruff clean; status live-verified

## Next Session

Stage 3: `mimeo sync` — converge on desired state (DNS repair + HTTPS
enforcement), driven by the same per-domain assessment status uses.
