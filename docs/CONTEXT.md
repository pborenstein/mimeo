---
phase: 8
phase_name: Consolidation
updated: 2026-09-29
last_commit: c7edfea
---

## Current Focus

Command-model reconsideration (user-driven). First build: the
`delete` verb (DEC-031, v1.2.0) — teardown as create's inverse,
for repurposing scratch domains; not yet live-tested.
`docs/SITE_ADDRESS.md` (proposed) is the standing design thread.

## Active Tasks

- [ ] **delete live test**: `--dry-run` then real on a scratch
      domain (002371.xyz & co.).
- [ ] **Command model**: `docs/SITE_ADDRESS.md` proposed,
      undecided; more command questions queued from the user.
- [ ] **Backlog**: rec #6 long-termers — Pages IPs from
      `api.github.com/meta`; D1 create-only-missing `sync` path.

## On Ice (2026-09-29, user call)

- **Template apply**: Entry 68 design; its open questions are
      preserved there (refresh vs migration; pandoc-resume's
      customizable index.md).
- **Subdomain sites**: `docs/SUBDOMAINS.md`; closed 2026-09-12,
      parked.

## Blockers

None.

## Context

- Templates: 11 repos in `tepiton` — 7 Eleventy starters, 3
  single-page, pandoc-resume (2026-09-28, user-tested). Canonical
  inventory: mimeo-sites TEMPLATES/CLAUDE.md. `--force` remains
  the only in-place replacement path.
- Org model: `github.template_org` (tepiton) holds templates;
  `github.default_org` receives site repos; `--template-org`/
  `--deploy-org` override per invocation.
- README style: user's documentation-principles gist (Entry 67) —
  Task|Command tables, no pseudo-headings.
- Exit codes (DEC-027/028): only confirmed-transient exits 5;
  already-existed create no-op keeps exit 0. Tests building
  404/422 `HostError`s must pass `status_code=` explicitly.
- Repo is public-as-visible; live usage is the real E2E hedge
  (`scripts/e2e_smoke.sh` on a junk domain). Version 1.2.0; bump
  pyproject + `__version__` + `uv lock` together.

## Next Session

Live-test `delete` on a scratch domain; `SITE_ADDRESS.md` awaits
the user's verdict, further command-model questions queued. Apply
and subdomains stay on ice; rec #6 long-termers open.
