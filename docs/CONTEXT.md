---
phase: 8
phase_name: Consolidation
updated: 2026-09-11
last_commit: ce40b44
---

## Current Focus

Two template-side rounds this session, no mimeo code: branding
centralization in product/service with `email` parameterized (Entry 59),
then package.json identity fixes in the literary three (Entry 60).
All seven eleventy templates now carry honest, consistent package
metadata, verified through the deploy steps.

## Active Tasks

- [ ] **Port the branding pattern to the other five eleventy
      templates** (prose-blog, tech-blog, chapbook, folio, pamphlet)
      — user deferred; literary three carry the about.md
      string-replace wrinkle; decide whether blogs/chapbooks want a
      site-wide email at all.
- [ ] **Track B**: Stage 4 E2E test lane, blocked on test account/org.
- [ ] **Backlog**: BUG 4/6/7 and the error-semantics refactor
      (`docs/CODE_REVIEW.md` rec #2) — not started.
- [ ] **Backlog**: D2 (`default_registrar`/`default_host`) — decide
      factory vs. removal.
- [ ] **Subdomain sites**: four open decisions in SUBDOMAINS.md.

## Blockers

Track B blocked on a test account/org. Everything else unblocked.

## Context

- Design stance (Entry 60): template package.json ships as-is; its
      identity fields are inert in a site, so sites do nothing.
      Stopping rule for parameterization creep: only what the site's
      build or visitors consume (url/email pass; package identity
      fails).
- package-lock.json mirrors the root package name/version — keep in
      sync when renaming, or `npm ci` can fail on the Pages deploy.
- Instance tepiton/002370.xyz predates the prose fix: hand-edit its
      about.md or `--force` + re-apply metadata.
- Prose trick: `markdownTemplateEngine: "njk"` lets `{{ metadata.title
      }}` rebrand .md bodies; frontmatter can't interpolate.

## Next Session

Port the branding pattern to the remaining five eleventy templates,
or pick up rec #2 (error semantics) / the SUBDOMAINS.md decisions.
