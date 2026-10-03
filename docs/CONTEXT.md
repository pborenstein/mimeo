---
phase: 8
phase_name: Consolidation
updated: 2026-10-02
last_commit: 2835858
---

## Current Focus

Command-model work: `docs/SITE_ADDRESS.md` and `docs/NETLIFY.md`
(second host) both proposed; `delete` (DEC-031) + Website field
(DEC-032) shipped at v1.3.0.

## Active Tasks

- [ ] **Netlify second host**: `docs/NETLIFY.md` proposed,
      undecided; first decision is the DNS mode (OD #1).
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
- Netlify (Entries 72–75): host selection is recorded on the repo
      topic (`github-pages` today, unread; `netlify` for Netlify
      sites); mode A — Netlify writes the site records, DNSSEC is the
      only NS-switch refusal; `netlify.toml` carries repo-side config.
- Org model: `github.template_org` (tepiton) holds templates;
      `github.default_org` receives site repos; `--template-org`/
      `--deploy-org` override per invocation.
- Doc style: the Entry 67 gist governs all prose docs; explain the
      mechanism, do not coin a label for it (user, Entry 75);
      chronicles/DECISIONS/CODE_REVIEW are never rewritten.
- Exit codes (DEC-027/028): only confirmed-transient exits 5.
      Tests building 404/422 `HostError`s must pass `status_code=`.
- Repo is public-as-visible; live usage is the E2E hedge
      (`scripts/e2e_smoke.sh` on a junk domain). Version 1.3.0; bump
      pyproject + `__version__` + `uv lock` together.

## Next Session

User's decision on NETLIFY.md's DNS mode, or the queued command
questions (SITE_ADDRESS also pending); On Ice unchanged.
