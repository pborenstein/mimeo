---
phase: 8
phase_name: Consolidation
updated: 2026-10-04
last_commit: 9904ea8
last_entry: 81
---

## Current Focus

`docs/TEMPLATE_CONSOLIDATION.md` pass 1 executed 2026-10-04 (Entry
81): folio retired and archived, `dek` in chapbook, DEC-034 shipped
(`create` rejects unflagged template repos). Pass 2 — the content
contract and the tepiton fixture repo (OD 1–4) — is the next
consolidation work, unscheduled. Command-model work:
`docs/SITE_ADDRESS.md` and `docs/NETLIFY.md` (second host; DNS
decided, DEC-033) also proposed but unscheduled.

## Active Tasks

- [ ] **Template consolidation pass 2**: the `CONTENT-CONTRACT.md`
      + fixture-repo change — OD 1 (repo name, rec
      `tepiton/content-fixture`), OD 2 (corpus), OD 3 (Actions
      cadence), OD 4 (assertions) still open. The fixture's first run
      is the check for the four unverified contract claims in the
      plan's table.
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

- Templates: 10 repos in `tepiton` (6 eleventy starters, 3
      single-page, pandoc-resume) — folio retired 2026-10-04,
      archived; canonical inventory: mimeo-sites TEMPLATES/CLAUDE.md.
      `--force` is the only in-place replacement.
- Template offering is by repo flag: `is_template` unchecked = retired
      (DEC-034 — `create` rejects unflagged repos; the self-heal that
      re-flagged them is gone). The `mimeo-template` topic is for
      humans; nothing in mimeo enumerates templates.
- chapbook is the literary chaptered template (folio's `dek` ported;
      no image transform, images copy through unchanged — chapbook
      DEC-010/011; engines stays `>=22` across the six).
- Template fleet installs silent under npm 12 (2026-10-03 pass) —
      drop each `audit=false` when eleventy 4 ships.
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

Nothing queued for mimeo itself. When consolidation resumes: execute
`docs/TEMPLATE_CONSOLIDATION.md` pass 2 — settle OD 1–4, build the
tepiton fixture repo (`CONTENT-CONTRACT.md`, the corpus, the
four-template Actions matrix), and let its first run verify the
contract claims still marked unverified.
