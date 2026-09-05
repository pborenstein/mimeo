---
phase: 8
phase_name: Consolidation
updated: 2026-09-05
last_commit: 337b359
---

## Current Focus

Phase 8 Stages 1-3 done, Track A complete. `process_domains_concurrent`
deleted. All commands now use map_items + render_results + exit_on_errors.

## Active Tasks

- [x] **Track A: Fold `process_domains_concurrent` into `map_items`**
      Done. Migrated dns repair, template apply, create. Deleted
      process_domains_concurrent and exit_on_failures from _processing.py.

- [ ] **Track B: Stage 4 E2E test lane**
      Gated (real APIs), covers `create`/`status`/`sync` flows. Blocked on
      having a test account/org to hit.

- [ ] **Backlog: `eleventy-*` template parameterization**
      `_customize_default_template` special-cases `mimeo.lol` by name. Full
      site-generator templates need a different approach (template-aware, not
      hardcoded string substitution). Not urgent — no eleventy templates exist
      in tepiton yet.

- [ ] **Backlog: Dead params in `HTTPClient`**
      `max_retries` and `backoff_factor` in `http.py` are noted as unused,
      kept for API compatibility. No callers pass them. Safe to remove.

## Blockers

None.

## Context

### Architecture (from deep-dive)
- Two providers: `PorkbunRegistrar`/`PorkbunDNSProvider` (share `_PorkbunClient`)
  and `GitHubHost` (wraps `gh` CLI via subprocess, no direct HTTP)
- Templates always from `tepiton` GitHub org; default is `tepiton/mimeo.lol`
- "mimeo-managed" = repo has `mimeo` topic tag; no local state beyond config
- `_processing.py` has two parallel fan-out systems:
  - `process_domains_concurrent` (older, verbose, create/dns repair/template apply)
  - `map_items` + `render_results` + `exit_on_errors` (newer, cleaner, everything else)

### Key quirks to remember
- `_customize_default_template` is special-cased by name (only `mimeo.lol`)
- `_rename_repository` uses numeric ID endpoint to avoid 307 redirects
- `_delete_stale_pages_artifacts` runs after force-replace (multiple artifacts
  named `github-pages` break the Pages deploy action)
- `_ensure_is_template` auto-sets the flag before every generate call
- 297 tests passing; mypy and ruff clean

## Next Session

Track A done. Choose from backlog items or start Stage 4 E2E tests when
a test account is available.

Backlog candidates (either one is safe to tackle):
- **Dead params in `HTTPClient`**: remove `max_retries`/`backoff_factor`
  from `http.py` (no callers pass them, kept for API compat but there
  is no external API)
- **`eleventy-*` template parameterization**: not urgent, no eleventy
  templates in tepiton yet
