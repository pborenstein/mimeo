---
phase: 8
phase_name: Consolidation
updated: 2026-07-06
last_commit: b56ff0c
---

## Current Focus

Phase 8 Stages 1-3 done: shared domain-operation engine, `mimeo status`
(cross-provider join), `mimeo sync` (converge, --all required for fleet),
identity fix. See DEC-021 incl. Stage 3 resolutions.

## Active Tasks

- [ ] Stage 4: E2E test lane (gated, real APIs, covers create/status/sync)
- [ ] Fold `process_domains_concurrent` (create, dns repair, template apply)
      into `map_items` (Stage 1 follow-up)
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
- `sync` acts on missing records only; never deletes extras; NS only with
  --reset-nameservers; no propagation wait; dns repair / fix https kept
  as targeted scalpels
- 275 tests passing; mypy and ruff clean; status and sync --dry-run
  live-verified

## Next Session

Stage 4: E2E test lane. Decide gating (env var vs pytest marker), which
flows to cover (create/status/sync --dry-run), and teardown strategy.
