---
phase: 8
phase_name: Consolidation
updated: 2026-09-22
last_commit: 2926bfc
---

## Current Focus

Track B closed as empirically served (Entry 66) -- the board reduces
to the rec #6 long-termers, with no blockers. Org configurability
(Entries 63-65: config keys + global CLI flags) and v1.1.0 are landed;
all code-review bugs are closed and D2 is resolved (DEC-030).

## Active Tasks

- [ ] **Backlog**: rec #6 long-termers — Pages IPs from
      `api.github.com/meta` (cache + hardcoded fallback), gentler
      create-only-missing `sync` path (D1).

## Blockers

None.

## Context

- Org model: `github.template_org` (tepiton) holds templates;
  `github.default_org` is where site repos land. Overridable per
  invocation with `--template-org`/`--deploy-org` (applied in
  `_processing.load_config`, the shared wrapper).
- Track B (E2E lane) closed 2026-09-22 without being built -- live
  usage has been the real coverage; hedge if the fleet goes dormant:
  `scripts/e2e_smoke.sh` against a junk domain.
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

The rec #6 long-termers: Pages IPs from the meta API, and D1's
surgical create-only-missing DNS apply.

