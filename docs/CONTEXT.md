---
phase: 8
phase_name: Consolidation
updated: 2026-09-14
last_commit: a821659
---

## Current Focus

Template-side session wrapped (Entry 62): laptopistan follows the OS
color scheme (no toggle), and the template catalog now lives on the org
site at tepiton.com (user folded list.md into index.md, deployed). No
mimeo code this round; repo is clean at the Entry 61 code commit.

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
- Already-existed create no-op keeps exit 0 with a warn recap (DEC-028).
- mimeo-sites: TEMPLATES/CLAUDE.md is stale on the mimeo.lol template's
  repo (says tepiton/mimeo.lol; the repo is `tepiton/mimeo`).
- Template demos: project Pages redirect under tepiton.com/<repo>; the
  mimeo.lol template's demo serves at mimeo.lol.

## Next Session

BUG 6 is the quick win; otherwise the D2 factory-vs-removal decision or
the rec #6 long-termers.
