---
phase: 8
phase_name: Consolidation
updated: 2026-09-21
last_commit: 8a52f08
---

## Current Focus

Config work wrapped (Entry 63, DEC-029): template org and default
template are config settings (`github.template_org`, `defaults.template`),
independent of the destination org (`github.default_org`);
`DEFAULT_TEMPLATE` renamed to "mimeo". README accuracy pass landed with
it, and `uv.lock` is now committed.

## Active Tasks

- [ ] **BUG 6**: missing-`schema_version` warning invisible to CLI users
      (`DeprecationWarning` hidden outside `__main__`) — print to stderr
      or drop the check. Small.
- [ ] **D2 remainder**: `default_registrar`/`default_host` — provider
      factory vs. config-field removal (DEC-029 extended the
      config-field side for templates only).
- [ ] **Track B**: Stage 4 E2E test lane, blocked on test account/org.
- [ ] **Backlog**: rec #6 long-termers — Pages IPs from
      `api.github.com/meta`, gentler create-only-missing `sync` path (D1).

## Blockers

Track B blocked on a test account/org. Everything else unblocked.

## Context

- Template org vs destination org: `github.template_org` (tepiton) is
  where templates live; `github.default_org` is where site repos land.
  Default template is `defaults.template` (mimeo).
- Repo verified clean to go public (no tokens in history; config lives
  outside the repo); stance is public-as-visible, not advertised use.
- Exit-code contract (DEC-027): only confirmed-transient exits 5;
  definitive provider failures and unexpected exceptions exit 1.
- Already-existed create no-op keeps exit 0 with a warn recap (DEC-028).
- Tests constructing 404/422-meaning `HostError`s must pass
  `status_code=` explicitly — parsing lives in `_run_gh_command`.

## Next Session

BUG 6 is the quick win; otherwise the D2 factory-vs-removal decision or
the rec #6 long-termers.
