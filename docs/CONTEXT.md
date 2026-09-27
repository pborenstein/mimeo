---
phase: 8
phase_name: Consolidation
updated: 2026-09-27
last_commit: c7edfea
---

## Current Focus

Non-obliterating template apply designed but not built (Entry 68).
Next up: more template-related work per the user's plan.

## Active Tasks

- [ ] **Template apply**: Entry 68 design awaiting go/no-go -- overlay
      via template tarball + Git data API, `content_paths` field in
      mimeo.template.json, keep-content flag on `create --force`. Open
      question: same-template refresh vs cross-template migration.
- [ ] **Backlog**: rec #6 long-termers — Pages IPs from
      `api.github.com/meta` (cache + hardcoded fallback); D1
      create-only-missing `sync` path.

## Blockers

None.

## Context

- Templates: 10 repos in `tepiton` (all is_template, all with
  mimeo.template.json). Two families: single-page vs Eleventy starters
  (scaffold vs `content/`). Apply is conflated with repo creation
  (generate API); `--force` destroys repo + DNS. Entry 68 has the
  non-obliterating design.
- README style: user's documentation-principles gist (link in Entry
  67) -- Task|Command tables, no pseudo-headings, no LLM-config refs.
- Org model: `github.template_org` (tepiton) holds templates;
  `github.default_org` is where site repos land. Overridable per
  invocation with `--template-org`/`--deploy-org` (applied in
  `_processing.load_config`, the shared wrapper).
- Repo verified clean to go public (no tokens; config lives outside
  the repo); public-as-visible, not advertised. Live usage is the real
  E2E coverage -- hedge if dormant: `scripts/e2e_smoke.sh` on a junk
  domain.
- Exit codes (DEC-027/028): only confirmed-transient exits 5; the
  already-existed create no-op keeps exit 0 with a warn recap.
- Tests constructing 404/422-meaning `HostError`s must pass
  `status_code=` explicitly — parsing lives in `_run_gh_command`.
- Version is 1.1.0 (`mimeo --version`); uv.lock is committed, so bump
  pyproject + `__version__` then `uv lock`.

## Next Session

The user's next template-related task; Entry 68 holds the apply
design if that task is the build. Rec #6 long-termers remain open.
