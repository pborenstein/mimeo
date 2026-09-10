---
phase: 8
phase_name: Consolidation
updated: 2026-09-10
last_commit: 272db0c
---

## Current Focus

DEC-024 is complete end to end (Entry 57, all repos pushed). The
follow-on Stage 6 (`template lint`) was evaluated this session and
dropped — deploy-time validation already fails loud, so a standalone
linter wasn't worth a new command (Entry 58, docs-only session).

## Active Tasks

- [ ] **Track B**: Stage 4 E2E test lane, blocked on test account/org.
- [ ] **Backlog**: BUG 4/6/7 and the error-semantics refactor
      (`docs/CODE_REVIEW.md` rec #2) — not started.
- [ ] **Backlog**: D2 (`default_registrar`/`default_host`) — decide
      factory vs. removal.
- [ ] **Subdomain sites**: four open decisions in SUBDOMAINS.md.

## Blockers

Track B blocked on a test account/org. Everything else unblocked.

## Context

- All eleventy manifests are one `js-key url` entry (plus about.md
  string-replace for chapbook/folio/pamphlet) — the template cleanup
  left `metadata.js`'s `url` as the single site-identity key.
- String-replace consumes its match, so it can't re-apply; safe because
  substitution only ever runs on a freshly generated tree (DEC-024
  addendum, `5b19189`).
- Template cleanup deleted author.email/url, feed.id, stale
  `notreally.config.js`; pamphlet's feed base derives from metadata.url.
  All ten templates build clean; nothing references the deleted keys.
- Known template nit, not fixed: double slash in tech-blog canonical
      URLs (`https://example.com//posts/...`) — pre-existing, mimeo-sites.
- Stage 6 (`template lint`) dropped 2026-09-10: deploy-time manifest
      validation already aborts loudly and names the failing entry, so
      lint only bought earlier drift discovery. Full rationale in
      IMPLEMENTATION.md's Stage 6 note.

## Next Session

The open picks are rec #2 (error-semantics refactor, CODE_REVIEW.md)
and the four SUBDOMAINS.md decisions; BUG 4/6/7 and D2 sit behind
them. Track B stays blocked on a test account/org.
