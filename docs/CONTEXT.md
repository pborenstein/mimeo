---
phase: 8
phase_name: Consolidation
updated: 2026-09-21
last_commit: 51a0409
---

## Current Focus

Code-review close-out wrapped (Entry 64, DEC-030): BUG 6 fixed
(schema notices now visible on stderr), D2 resolved by removal
(`default_registrar`/`default_host` gone), version bumped to 1.1.0.
With DEC-029 (configurable template org/default template) this
closes out the config surface: every `[defaults]`/`[github]` key now
does real work.

## Active Tasks

- [ ] **Track B**: Stage 4 E2E test lane, blocked on test account/org.
- [ ] **Backlog**: rec #6 long-termers — Pages IPs from
      `api.github.com/meta` (cache + hardcoded fallback), gentler
      create-only-missing `sync` path (D1).

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
- Version is 1.1.0 (`mimeo --version`); uv.lock is committed, so bump
  the version in pyproject + `__version__` then `uv lock`.

## Next Session

The rec #6 long-termers (Pages IPs from the meta API, D1 surgical DNS
apply), or Track B once a test account/org exists.

