---
phase: 8
phase_name: Consolidation
updated: 2026-09-21
last_commit: e3b3332
---

## Current Focus

Org configurability fully landed (Entries 63-65): `github.template_org`
/ `defaults.template` in config, and global `--template-org`/
`--deploy-org` CLI flags over them (CLI > env > file). v1.1.0.
Code-review bugs all closed (BUG 6 was the last), D2 resolved by
removal (DEC-030).

## Active Tasks

- [ ] **Track B**: Stage 4 E2E test lane, blocked on test account/org.
- [ ] **Backlog**: rec #6 long-termers — Pages IPs from
      `api.github.com/meta` (cache + hardcoded fallback), gentler
      create-only-missing `sync` path (D1).

## Blockers

Track B blocked on a test account/org. Everything else unblocked.

## Context

- Org model: `github.template_org` (tepiton) holds templates;
  `github.default_org` is where site repos land. Overridable per
  invocation with `--template-org`/`--deploy-org` (applied in
  `_processing.load_config`, the shared wrapper).
- Repo verified clean to go public (no tokens in history; config lives
  outside the repo); stance is public-as-visible, not advertised use.
- Exit-code contract (DEC-027): only confirmed-transient exits 5;
  definitive provider failures and unexpected exceptions exit 1.
- Already-existed create no-op keeps exit 0 with a warn recap (DEC-028).
- Tests constructing 404/422-meaning `HostError`s must pass
  `status_code=` explicitly — parsing lives in `_run_gh_command`.
- Version is 1.1.0 (`mimeo --version`); uv.lock is committed, so bump
  pyproject + `__version__` then `uv lock`.

## Next Session

The rec #6 long-termers (Pages IPs from the meta API, D1 surgical DNS
apply), or Track B once a test account/org exists.

