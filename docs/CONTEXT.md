---
phase: 8
phase_name: Consolidation
updated: 2026-09-05
last_commit: 2277111
---

## Current Focus

Phase 8 Stages 1-3 done. Code review session: deep dive into the full
codebase to understand organic structure. Two main cleanup tracks identified
for next session (see Active Tasks).

## Active Tasks

- [ ] **Track A: Fold `process_domains_concurrent` into `map_items`**
      Affects `create`, `dns repair`, `template apply`. These three commands
      still use the older fan-out function with a baked-in progress printer
      and a `{domain, success, error, log}` result schema. `map_items` +
      `render_results` + `exit_on_errors` is the current idiom. Within `dns`,
      `check` and `show` already use the new path while `repair` uses the old
      one — same command group, two different patterns.

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

**Start with Track A** (fold `process_domains_concurrent` into `map_items`):

1. Migrate `dns repair` first — it's the easiest case and fixes the
   inconsistency within the `dns` command group
2. Then `template apply` — similar verbosity pattern to `dns repair`
3. Then `create` — most complex (has dry-run log closures and a detailed
   summary section), leave for last

For each: the `log` closure and `{success, error_category, log}` schema
go away; commands own their text rendering via a `_text` function passed
to `render_results`. The per-domain progress printing in the concurrent
branch of `process_domains_concurrent` moves to `map_items` or is dropped
(the new pattern doesn't print mid-run progress in concurrent mode).

After the migration, `process_domains_concurrent` can be deleted entirely.
