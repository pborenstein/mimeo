---
phase: 8
phase_name: Consolidation
updated: 2026-09-12
last_commit: 74f438a
---

## Current Focus

Error-path QoL session (Entry 61, DEC-027/028): structured gh status
codes end to end (rec #2 + BUG 4 + BUG 7 closed), create output honest
(created / already-existed / failed) and narrated in parallel runs.
Branding work declared complete at Entry 59 — no port to the remaining
five templates. Subdomain sites closed: the eleventy templates working
was the answer.

## Active Tasks

- [ ] **BUG 6**: missing-`schema_version` warning invisible to CLI users
      (`DeprecationWarning` hidden outside `__main__`) — print to stderr
      or drop the check. Small.
- [ ] **D2**: `default_registrar`/`default_host` — provider factory vs.
      config-field removal.
- [ ] **Track B**: Stage 4 E2E test lane, blocked on test account/org.
- [ ] **Backlog**: rec #6 long-termers — Pages IPs from
      `api.github.com/meta`, gentler create-only-missing `sync` path (D1).

## Blockers

Track B blocked on a test account/org. Everything else unblocked.

## Context

- Exit-code contract (DEC-027): only confirmed-transient exits 5;
  definitive provider failures and unexpected exceptions exit 1.
- Tests constructing 404/422-meaning `HostError`s must pass
  `status_code=` explicitly — parsing lives in `_run_gh_command`.
- Already-existed create no-op keeps exit 0 with a warn recap (DEC-028);
  user accepted honest text over a nonzero code.
- mimeo-sites (separate repo): user updated the templates' pages.yml so
  URLs work with or without a custom domain; not chronicled here.

## Next Session

BUG 6 is the quick win; otherwise the D2 factory-vs-removal decision or
the rec #6 long-termers.
