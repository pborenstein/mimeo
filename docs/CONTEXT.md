---
phase: 8
phase_name: Consolidation
updated: 2026-09-29
last_commit: c7edfea
---

## Current Focus

Quiet period (user call, 2026-09-29): template apply and subdomain
sites are on ice; nothing scheduled. Standing backlog: rec #6
long-termers.

## Active Tasks

- [ ] **Backlog**: rec #6 long-termers — Pages IPs from
      `api.github.com/meta` (cache + hardcoded fallback); D1
      create-only-missing `sync` path.

## On Ice (2026-09-29, user call)

- **Template apply**: Entry 68 design — overlay via template
      tarball + Git data API, `content_paths` field in
      mimeo.template.json, keep-content flag on `create --force`.
      Unresolved if revived: same-template refresh vs
      cross-template migration; whether content_paths covers
      pandoc-resume's customizable index.md.
- **Subdomain sites**: proposed design in `docs/SUBDOMAINS.md`;
      first closed 2026-09-12, now parked with no revive date.

## Blockers

None.

## Context

- Templates: 11 repos in `tepiton` (all is_template, all with
  mimeo.template.json; canonical inventory: mimeo-sites
  TEMPLATES/CLAUDE.md). Seven Eleventy starters (scaffold vs
  `content/`), three single-page (mimeo, pandoc-simple,
  laptopistan), plus pandoc-resume (added 2026-09-28, user-tested;
  resume.md is content, build.sh/templates/ are scaffold). Apply
  is conflated with repo creation (generate API); `--force`
  destroys repo + DNS. Entry 68's non-obliterating apply design is
  on ice; its two-family split predates pandoc-resume, which
  behaves like the scaffold/content family.
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

Nothing scheduled — apply and subdomains are on ice. Rec #6
long-termers remain open; otherwise wait for the user's next call.
