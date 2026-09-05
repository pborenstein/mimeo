---
phase: 8
phase_name: Consolidation
updated: 2026-09-05
last_commit: f02ca53
---

## Current Focus

Phase 8 Stages 1-3 done. Track A (fold `process_domains_concurrent` into
`map_items`) complete. Also fixed a latent inconsistency: `create` now
validates the template name upfront, matching `template apply`.

## Active Tasks

- [x] **Track A: Fold `process_domains_concurrent` into `map_items`**
      Done. Migrated dns repair, template apply, create. Deleted
      process_domains_concurrent, exit_on_failures, Lock from _processing.py.

- [ ] **Track B: Stage 4 E2E test lane**
      Gated (real APIs), covers `create`/`status`/`sync` flows. Blocked on
      having a test account/org to hit.

- [ ] **Backlog: `eleventy-*` template parameterization**
      `_customize_default_template` special-cases `mimeo.lol` by name. Not
      urgent — no eleventy templates in tepiton yet.

- [ ] **Backlog: Dead params in `HTTPClient`**
      `max_retries` and `backoff_factor` in `http.py` unused. Safe to remove.

## Blockers

None.

## Context

- All commands now use `map_items` + `render_results` + `exit_on_errors`;
  `_processing.py` has one fan-out system
- `create` and `template apply` both call `validate_template()` before the
  per-domain loop (was inconsistent; create had no upfront check)
- Two providers: `PorkbunRegistrar`/`PorkbunDNSProvider` and `GitHubHost`
- `_customize_default_template` special-cased by name (only `mimeo.lol`)
- `_rename_repository` uses numeric ID endpoint to avoid 307 redirects
- 297 tests passing; mypy and ruff clean

## Next Session

Choose from backlog items or start Stage 4 E2E tests when a test account
is available. Easiest backlog pick: remove dead `max_retries`/`backoff_factor`
params from `HTTPClient` in `http.py`.
