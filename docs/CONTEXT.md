---
phase: 8
phase_name: Consolidation
updated: 2026-08-26
last_commit: 28a2cf5
---

## Current Focus

Phase 8 Stages 1-3 done (engine, status, sync, identity fix; see DEC-021).
Previous session: fixed a live incident where `template apply --force`
deleted `tepiton/laptopistan.com` with no rollback after a generate
failure. See DEC-022. This session: investigated a suspected `create
--template` bug (multi-domain runs appeared to ignore `--template`) --
verified against GitHub's API that the flag was honored correctly in
every case (single- and multi-domain); no bug found.

## Active Tasks

- [ ] Stage 4: E2E test lane (gated, real APIs, covers create/status/sync)
- [ ] Fold `process_domains_concurrent` (create, dns repair, template apply)
      into `map_items` (Stage 1 follow-up)
- [ ] Template parameterization for `eleventy-*` templates (mimeo.lol done;
      full site generators need a different, template-aware approach)

## Blockers

None.

## Context

- `_create_from_template` (`github.py`) now: renames target repo out of the
  way (not delete) on force-replace, calls `_ensure_is_template` (auto-sets
  `is_template` on the source repo if unset -- generate 404s silently
  otherwise) then `generate`, deletes the renamed-old repo only on success,
  renames it back on any failure. DEC-022.
- `laptopistan.com` was destroyed live, then restored via GitHub org
  deleted-repo restore (works because `tepiton` is an Org, ~90-day window;
  would NOT have worked for a personal-owned repo)
- `mellowtimesphere.com` template repo had `is_template: false` -- fixed
  both by hand (`gh api PATCH`) and now automatically by the code above
- `status` and `sync` both require --all for fleet-wide; DNS column "-" when
  no repo; `sync` acts on missing records only, never deletes extras
- 297 tests passing; mypy and ruff clean
- `create --template <name>` confirmed working end-to-end (CLI parsing,
  `deploy_site`, `_create_from_template`, GitHub `generate` call) --
  checked via `gh api repos/<owner>/<repo> --jq .template_repository`

## Next Session

Stage 4: E2E test lane, or eleventy-* template parameterization if that's
the priority instead. Nothing uncommitted.
