---
phase: 8
phase_name: Consolidation
updated: 2026-10-02
last_commit: a943ebb
---

## Current Focus

Command-model work: `docs/SITE_ADDRESS.md` proposed and
`docs/NETLIFY.md` (second host; DNS decided, DEC-033) proposed but
unscheduled. `delete` (DEC-031) + Website field (DEC-032) shipped at
v1.3.0.

## Active Tasks

- [ ] **Netlify second host**: DNS decided (DEC-033 — Netlify
      nameservers); remaining open decisions #2–#8; staging pass 1
      (repo/host split) is a pure refactor, landable on its own.
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
- Netlify (Entries 72–76): DNS decided — Netlify nameservers
      (DEC-033); host selection recorded on the repo topic;
      `delete` restores Porkbun NS (DEC-031 amendment); DNSSEC is
      the only NS-switch refusal; `netlify.toml` carries repo-side
      config.
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

Build NETLIFY.md pass 1 (repo/host split — useful even if Netlify
stalls), or settle remaining open decisions #2–#8; SITE_ADDRESS and
the command questions still queued.
