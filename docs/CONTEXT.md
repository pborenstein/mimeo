---
phase: 8
phase_name: Consolidation
updated: 2026-09-09
last_commit: f73e05d
---

## Current Focus

Subdomain-sites design written and committed (`e75fe6b`, see Entry 54).
Then repaired the chronicles: four phase files had out-of-order entries
and a duplicate Entry 53, fixed in `29192be` (Entry 55). The wrap-up
skill's numbering recipe hardened to max-across-all-matches.

## Active Tasks

- [ ] **Subdomain sites**: design complete; resolve the four open
      decisions in SUBDOMAINS.md (repo naming, zone-resolution source,
      `ignore_domains` semantics, apex freeze) before scheduling.
- [ ] **Stage 6**: `template lint`. Blocked on DEC-024 implementation.
- [ ] **Track B**: Stage 4 E2E test lane, blocked on test account/org.
- [ ] **Backlog**: BUG 4/6/7 and the error-semantics refactor
      (`docs/CODE_REVIEW.md` recommendation #2) — not started.
- [ ] **Backlog**: D2 (`default_registrar`/`default_host`) — decide
      factory vs. removal.

## Blockers

Stage 6 blocked on DEC-024 implementation. Everything else unblocked.

## Context

- Chronicles are now sorted ascending per file; next entry number is 55+1.
  Entries 49-52 are dated 09-09 but their commits are 09-08 evening —
  left alone, confirm intent before "fixing".
- Subdomain design core: "domain" means hostname + zone + join key at
  once; subdomains split them and make zones one-to-many with sites.
  Today `create` on a subdomain refuses cleanly at the ownership check.
- 289 tests passing, mypy clean, ruff unchanged from baseline (5
  pre-existing errors, untouched files). No code changed this session.

## Next Session

Either ratify SUBDOMAINS.md's open decisions and schedule the work, or
start BUG 4/6/7 + error-semantics refactor, or DEC-024 to unblock
Stage 6.
