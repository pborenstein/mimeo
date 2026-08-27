---
phase: 8
phase_name: Consolidation
updated: 2026-08-27
last_commit: c3b1923
---

## Current Focus

Phase 8 Stages 1-3 done. This session: added `mimeo list --show-template` to
show which template each site was created from; improved `template apply` to
validate template name before touching anything; fixed `_rename_repository` to
use the repo's numeric ID (avoids GitHub's 307 redirect on previously-renamed
repos) with a 422 retry (GitHub serializes rapid renames).

## Active Tasks

- [ ] Stage 4: E2E test lane (gated, real APIs, covers create/status/sync)
- [ ] Fold `process_domains_concurrent` (create, dns repair, template apply)
      into `map_items` (Stage 1 follow-up)
- [ ] Template parameterization for `eleventy-*` templates (mimeo.lol done;
      full site generators need a different, template-aware approach)

## Blockers

None.

## Context

- `mimeo list --show-template` fetches `template_repository` via per-repo
  `gh api repos/<owner>/<repo>` calls (parallelized via `map_items`); GitHub
  search API doesn't expose this field
- `validate_template()` on `GitHubHost` checks `TEMPLATE_ORG/<name>` exists
  before `template apply` does any rename; gives a clear "not found" error
- `_rename_repository` now fetches repo ID first, PATCHes `repositories/<id>`
  to avoid 307 redirects from prior renames; retries once on 422 with 3s sleep
- DEC-023 covers the rename-by-ID decision
- 297 tests passing; mypy and ruff clean

## Next Session

Stage 4: E2E test lane, or eleventy-* template parameterization. Nothing
uncommitted.
