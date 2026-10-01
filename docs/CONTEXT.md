---
phase: 8
phase_name: Consolidation
updated: 2026-10-01
last_commit: ff6c2ea
---

## Current Focus

Command-model reconsideration (user-driven): two proposed designs
standing -- `docs/SITE_ADDRESS.md` and `docs/NETLIFY.md` (second
host, revised after user review). `delete` (DEC-031) and
Website-field deploy (DEC-032) landed at v1.3.0.

## Active Tasks

- [ ] **Netlify second host**: `docs/NETLIFY.md` proposed,
      undecided; first decision is the DNS mode (Open Decision #1);
      DEC-030's factory-revisit trigger.
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
- Netlify (Entries 72–73): `netlify api` works like `gh api`; repo
      link needs the one-time browser-only GitHub App install; in
      mode A Netlify writes the site records and DNSSEC is the only
      refusal-worthy NS-switch condition; `netlify.toml` carries the
      repo-side configuration.
- Org model: `github.template_org` (tepiton) holds templates;
      `github.default_org` receives site repos; `--template-org`/
      `--deploy-org` override per invocation.
- Exit codes (DEC-027/028): only confirmed-transient exits 5.
      Tests building 404/422 `HostError`s must pass `status_code=`.
- Repo is public-as-visible; live usage is the real E2E hedge
      (`scripts/e2e_smoke.sh` on a junk domain). Version 1.3.0; bump
      pyproject + `__version__` + `uv lock` together.

## Next Session

User's decision on NETLIFY.md's DNS mode, or the queued command
questions (SITE_ADDRESS also pending); On Ice unchanged.
