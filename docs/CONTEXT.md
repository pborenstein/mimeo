---
phase: 8
phase_name: Consolidation
updated: 2026-09-10
last_commit: 272db0c
---

## Current Focus

DEC-024 is complete end to end: manifest implementation in mimeo
(`13583f7`, Entry 56), all ten tepiton templates shipping validated
manifests, live-verified by the user on fresh create and `--force`
(Entry 57). Every template repo and this repo are pushed.

## Active Tasks

- [ ] **Stage 6**: `template lint` — unblocked (all ten templates ship
      real manifests). pandoc-simple's remote-side frontmatter drift is
      the motivating example.
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

## Next Session

Stage 6 (`template lint`) is the natural pick — freshly unblocked with
real manifests to lint. Otherwise rec #2 (error semantics) or the
SUBDOMAINS.md decisions.
