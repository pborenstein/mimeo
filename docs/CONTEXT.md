---
phase: 8
phase_name: Consolidation
updated: 2026-09-29
last_commit: 4c38e5c
---

## Current Focus

Command-model reconsideration (user-driven): `delete` (DEC-031,
user-tested live) and the Website-field deploy step (DEC-032)
landed at v1.3.0. `SITE_ADDRESS.md` (proposed) is the standing
design thread.

## Active Tasks

- [ ] **Command model**: `docs/SITE_ADDRESS.md` proposed,
      undecided; more command questions queued from the user.
- [ ] **Backlog**: rec #6 long-termers — Pages IPs from
      `api.github.com/meta`; D1 create-only-missing `sync` path.

## On Ice (2026-09-29, user call)

- **Template apply**: Entry 68 design (open questions preserved
      there). **Subdomain sites**: `docs/SUBDOMAINS.md`; parked.

## Blockers

None.

## Context

- Templates: 11 repos in `tepiton` (7 Eleventy starters, 3
  single-page, pandoc-resume). Canonical inventory: mimeo-sites
  TEMPLATES/CLAUDE.md. `--force` is the only in-place replacement.
- Org model: `github.template_org` (tepiton) holds templates;
  `github.default_org` receives site repos; `--template-org`/
  `--deploy-org` override per invocation.
- README style: documentation-principles gist (Entry 67) —
  Task|Command tables.
- Exit codes (DEC-027/028): only confirmed-transient exits 5.
  Tests building 404/422 `HostError`s must pass `status_code=`.
- Repo is public-as-visible; live usage is the real E2E hedge
  (`scripts/e2e_smoke.sh` on a junk domain). Version 1.3.0; bump
  pyproject + `__version__` + `uv lock` together.

## Next Session

`SITE_ADDRESS.md` awaits the user's verdict (more command
questions queued). Apply and subdomains on ice; rec #6
long-termers open.
