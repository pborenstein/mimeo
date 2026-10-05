---
phase: 8
phase_name: Consolidation
updated: 2026-10-04
last_commit: c5cba66
last_entry: 82
---

## Current Focus

`docs/TEMPLATE_CONSOLIDATION.md` is fully executed (Entries 81–82):
folio retired, `dek` in chapbook, DEC-034 shipped, and pass 2's
tepiton/content-fixture live with the content contract and a green
four-template CI matrix. Nothing is queued for consolidation.
Command-model work: `docs/SITE_ADDRESS.md` and `docs/NETLIFY.md`
(second host; DNS decided, DEC-033) proposed but unscheduled.

## Active Tasks

- [ ] **Netlify second host**: DNS decided (DEC-033); OD #1, #3, #6
      decided — open: #2, #4, #5, #7, #8; staging pass 1 (repo/host
      split) is a pure refactor, landable on its own.
- [ ] **Command model**: `docs/SITE_ADDRESS.md` proposed,
      undecided; more command questions queued from the user.
- [ ] **Backlog**: rec #6 long-termers — Pages IPs from
      `api.github.com/meta`; D1 create-only-missing `sync` path.
- [ ] **Watch item**: content-fixture's weekly Actions run is the
      drift alarm for template changes that break portability.

## On Ice (2026-09-29, user call)

- **Template apply**: Entry 68 design (open questions preserved
      there). **Subdomain sites**: `docs/SUBDOMAINS.md`; parked.

## Blockers

None.

## Context

- Templates: 10 repos in `tepiton` (6 eleventy starters, 3
      single-page, pandoc-resume); canonical inventory: mimeo-sites
      TEMPLATES/CLAUDE.md. `--force` is the only in-place
      replacement.
- The content contract lives in tepiton/content-fixture
      (`CONTENT-CONTRACT.md`): portable fields (title, draft, order,
      date, tags, dek), `content/chapters|posts|img/` directories,
      and what portable content must not rely on. Its Actions matrix
      builds the corpus against the four document templates — push,
      weekly (Mon 06:17 UTC), dispatch.
- Template offering is by repo flag: `is_template` unchecked = retired
      (DEC-034 — `create` rejects unflagged repos; the self-heal that
      re-flagged them is gone). The `mimeo-template` topic is for
      humans; nothing in mimeo enumerates templates.
- chapbook: `dek` ported, no image transform, `content/img`
      passthrough (sub-repo DEC-010/011/012); pamphlet: drafts
      preprocessor (sub-repo DEC-010). Engines `>=22` across the six.
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

Consolidation has no queue. The open threads are the Netlify second
host (staging pass 1 is self-contained) and the command-model
question in `docs/SITE_ADDRESS.md` — whichever the user picks up.
