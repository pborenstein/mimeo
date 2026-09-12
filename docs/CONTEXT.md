---
phase: 8
phase_name: Consolidation
updated: 2026-09-11
last_commit: ab61bcf
---

## Current Focus

Template-branding session (Entry 59): eleventy-product and
eleventy-service centralize branding in metadata.js, and their
manifests substitute `email` (`hello@{domain}`) alongside `url`.
No mimeo code changed; DEC-024 addendum records the email scope call.

## Active Tasks

- [ ] **Port the branding pattern to the other five eleventy
      templates** (prose-blog, tech-blog, chapbook, folio, pamphlet)
      — user deferred; the literary three carry the about.md
      string-replace wrinkle.
- [ ] **Track B**: Stage 4 E2E test lane, blocked on test account/org.
- [ ] **Backlog**: BUG 4/6/7 and the error-semantics refactor
      (`docs/CODE_REVIEW.md` rec #2) — not started.
- [ ] **Backlog**: D2 (`default_registrar`/`default_host`) — decide
      factory vs. removal.
- [ ] **Subdomain sites**: four open decisions in SUBDOMAINS.md.

## Blockers

Track B blocked on a test account/org. Everything else unblocked.

## Context

- Instance tepiton/002370.xyz (from eleventy-service, metadata edited
      to Talking Dog Studio) predates the prose fix: its about.md
      needs a hand edit or `--force` + metadata re-apply.
- Prose trick: `markdownTemplateEngine: "njk"` lets `{{ metadata.title
      }}` rebrand .md bodies; frontmatter data can't interpolate —
      neutralize instead.
- Stage 6 (`template lint`) dropped 2026-09-10 (Entry 58):
      deploy-time validation already fails loud; DEC-025's lint
      references corrected.

## Next Session

Port the branding pattern to the remaining five eleventy templates,
or pick up rec #2 (error semantics) / the SUBDOMAINS.md decisions.
