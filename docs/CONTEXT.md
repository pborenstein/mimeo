---
phase: 8
phase_name: Consolidation
updated: 2026-10-04
last_commit: ccf0cf4
---

## Current Focus

`docs/TEMPLATE_CONSOLIDATION.md` (template fleet: retire folio,
shared content base, fixture CI) approved in outline with four
decisions settled, unscheduled — the next session starts with its
pass 1. Command-model work: `docs/SITE_ADDRESS.md` and
`docs/NETLIFY.md` (second host; DNS decided, DEC-033) also proposed
but unscheduled. `delete` (DEC-031) + Website field (DEC-032)
shipped at v1.3.0.

## Active Tasks

- [ ] **Template consolidation**: decisions settled 2026-10-04 —
      retire folio; extended portable field set (title, draft, order,
      date, tags, dek); tepiton fixture repo; chapbook drops its
      unused image transform (Entry 80). Pass 1 (dek port + transform
      drop + folio retirement) needs no new repos. Open: OD 1–6 in
      the plan.
- [ ] **Netlify second host**: DNS decided (DEC-033); OD #1, #3, #6
      decided — open: #2, #4, #5, #7, #8; staging pass 1 (repo/host
      split) is a pure refactor, landable on its own.
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
      single-page, pandoc-resume); canonical inventory: mimeo-sites
      TEMPLATES/CLAUDE.md. `--force` is the only in-place replacement.
      Template fleet now installs silent under npm 12 (2026-10-03
      pass; per-repo DECs + TEMPLATES meta DEC-004) — drop each
      `audit=false` when eleventy 4 ships.
- Template consolidation (Entries 79–80): folio retires after `dek`
      ports to chapbook (repo flags only — mimeo hardcodes no
      template list); chapbook's image transform goes with it
      (processes nothing — demo has no images); image optimization
      remains in the blogs and product/service icon/OG generation.
- Netlify (Entries 72–77): delete = delete the project + restore
      Porkbun NS (project deletion removes site, domains, and zone —
      user-verified); `gh api search/repositories` returns topics
      (`gh search --json` does not); pandoc ships in the build image;
      "To Verify at Implementation" table holds the three unverified
      claims — vendor facts are verified-with-date or in that table.
- Org model: `github.template_org` (tepiton) holds templates;
      `github.default_org` receives site repos; `--template-org`/
      `--deploy-org` override per invocation.
- Doc style: the Entry 67 gist governs all prose docs; explain the
      mechanism, do not coin a label; answer the question asked —
      yes/no gets yes/no; link to what you reference; chronicles/
      DECISIONS/CODE_REVIEW are never rewritten.
- Exit codes (DEC-027/028): only confirmed-transient exits 5.
      Tests building 404/422 `HostError`s must pass `status_code=`.
- Repo is public-as-visible; live usage is the E2E hedge
      (`scripts/e2e_smoke.sh` on a junk domain). Version 1.3.0; bump
      pyproject + `__version__` + `uv lock` together.

## Next Session

Execute `docs/TEMPLATE_CONSOLIDATION.md` pass 1: port `dek` to
chapbook and drop its unused image transform (change 1), then retire
folio — feed-dir cleanup, README pointer, is_template/topic flags,
archive, inventory updates (change 2). Settle OD 6 (chapbook engines
floor) when change 1 lands.
