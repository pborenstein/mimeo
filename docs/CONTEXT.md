---
phase: 8
phase_name: Consolidation
updated: 2026-08-27
last_commit: 65e7be7
---

## Current Focus

Phase 8 Stages 1-3 done. This session: `list --show-template`, early template
validation, rename-by-ID fix, and stale Pages artifact cleanup after
force-replace.

## Active Tasks

- [ ] Stage 4: E2E test lane (gated, real APIs, covers create/status/sync)
- [ ] Fold `process_domains_concurrent` (create, dns repair, template apply)
      into `map_items` (Stage 1 follow-up)
- [ ] Template parameterization for `eleventy-*` templates (mimeo.lol done;
      full site generators need a different, template-aware approach)

## Blockers

None.

## Context

- `mimeo list --show-template`: per-repo `gh api` calls parallelized via
  `map_items`; GitHub search API doesn't expose `template_repository`
- `validate_template()` checks template exists before confirmation prompt
- `_rename_repository` uses `repositories/<id>` (avoids 307 redirects);
  retries once on 422 with 3s sleep (DEC-023)
- `_delete_stale_pages_artifacts` runs after force-replace; GitHub's
  deploy-pages action fails with >1 artifact named `github-pages`
- 297 tests passing; mypy and ruff clean

## Next Session

Stage 4: E2E test lane, or eleventy-* template parameterization. Nothing
uncommitted.
