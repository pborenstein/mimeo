---
phase: 8
phase_name: Consolidation
updated: 2026-09-09
last_commit: e75fe6b
---

## Current Focus

Wrote `docs/SUBDOMAINS.md`: a proposed design for hosting sites on
subdomains (`mimeo create service.example.com`). Design only, no code.
Structured as "what needs to happen" — six changes, implementation detail
in an appendix table.

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

- Core design insight: "domain" currently means site hostname, DNS zone,
  and fleet join key at once — true only for apex domains. Subdomains
  split the three and make zones one-to-many with sites.
- Today `create` on a subdomain refuses cleanly at the ownership check
  (Porkbun's API is zone-scoped); nothing partial is created.
- Hosting side and Porkbun API plumbing already speak the right language;
  the work is the hostname/zone split, DNS desired state, drift scoping,
  and the status/sync joins. Two-pass staging in the doc.

## Next Session

Committed as `e75fe6b`. Either ratify SUBDOMAINS.md's open decisions and
schedule the work, or start BUG 4/6/7 + error-semantics refactor, or
DEC-024 to unblock Stage 6.
