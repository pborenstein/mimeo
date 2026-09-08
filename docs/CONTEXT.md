---
phase: 8
phase_name: Consolidation
updated: 2026-09-08
last_commit: 868aca9
---

## Current Focus

On branch `stage-5a-create-absorbs-template-apply` (not merged to main).
Stage 5A is complete and committed: `create` absorbs `template apply` via
`--force`/`--yes`. Three unplanned safety bugs were also found and fixed
in the same session (DEC-026) while manually verifying `create` against
real domains — read DEC-026 in DECISIONS.md before touching `create.py`
or `github.py`'s template-generation path again, the reasoning there
explains why the current behavior looks the way it does.

Next up is Stage 5B (`status` absorbs `list`/`registrar list`/`dns show`/
`dns check`). DEC-024 (template domain-substitution manifest) is still
fully unimplemented, unrelated to this branch.

## Active Tasks

- [ ] **Merge/PR the `stage-5a-create-absorbs-template-apply` branch**
      before starting 5B, or continue 5B on the same branch — not yet
      decided. Branch is two commits (`d4debf2`, `868aca9`) ahead of `main`.
- [ ] **Stage 5B (start here)**: `status` absorbs `list`/`registrar list`/
      `dns show`/`dns check` via `--source {github,porkbun,dns}`. Largest
      test-relocation surface — full steps in IMPLEMENTATION.md Stage 5B.
- [ ] **Stage 5C**: `sync` absorbs `dns repair`/`fix https`. Read DEC-025's
      "Open question" section FIRST — may already be a non-issue, needs
      checking before writing code.
- [ ] **Stage 5D**: registration cleanup + full test/mypy/ruff pass + README
      update. Do last among 5A-5D. Note: README.md's `mimeo template apply`
      references (lines ~191, ~235-241) are now stale from 5A and need
      updating here too, not just the 9-verb-surface rewrite.
- [ ] **Stage 5E**: new `template lint` command. BLOCKED on DEC-024 landing
      first (validates the manifest schema DEC-024 defines).
- [ ] **DEC-024 implementation**: manifest schema + 3 format handlers
      (`js-key`, `string-replace`, `yaml-frontmatter-key`), replacing
      `_customize_default_template`. Needed before Stage 5E.
- [ ] **Track B: Stage 4 E2E test lane** — blocked on test account/org.
- [ ] **Backlog**: dead `max_retries`/`backoff_factor` params in `http.py`.

## Blockers

Stage 5E blocked on DEC-024 implementation. Everything else unblocked.

## Context

- **DEC-026 (new this session)**: `create` now (1) refuses to run at all
  if the domain isn't registered in the configured Porkbun account
  (`PorkbunRegistrar.domain_exists()`, checked before any GitHub call),
  (2) skips DNS configuration entirely when `deploy.repo_created` is
  `False` (repo pre-existed, no `--force` — DNS is only touched on first
  creation or explicit `--force` replace), and (3) no longer polls
  `verify_dns` for propagation (dropped the ~50s 10x5s poll; points users
  to `mimeo status` instead). Also: `GitHubHost._strip_template_dev_files`
  now deletes a generated repo's `README.md`/`docs/` right after every
  fresh template generation — those are template-authoring files, not
  site content, and were being published live. All four fixes were found
  by running `create --force`/`create` against real domains/repos during
  Stage 5A verification, not by the test suite — the test suite was
  extended afterward to cover them (303 tests passing).
- If you're asked why `create` behaves this way and only have DEC-025 open,
  you're missing half the picture — DEC-026 is the one that explains the
  current safety checks in `create.py`.
- DEC-025 is a plan document, not a decision to re-litigate — read it once,
  then work the IMPLEMENTATION.md Stage 5 checklist directly.
- DEC-025 explicitly supersedes DEC-021 Stage 3's "keep dns repair/fix
  https as scalpels" call — say so if touching that area, don't re-debate it.
- No provider-layer code changes in Stage 5 at all *except* DEC-026's fixes
  (which were pre-existing bugs surfaced during 5A, not new Stage-5 scope).
  `github.py`/`porkbun.py` are otherwise untouched by the consolidation.
- Every Stage 5 sub-stage ends with relocating the old command's tests onto
  the merged command's new flags, not just deleting coverage.
- When verifying CLI changes that touch live provider calls (create, sync,
  status), prefer testing against a real domain/repo via `gh api`/`curl`
  in addition to the mocked test suite — this session's real bugs (DEC-026)
  were invisible to the existing mocks precisely because the mocks didn't
  model the ownership/existing-repo distinction. Don't declare a `create`-
  path change verified on green tests alone.

## Next Session

Decide branch strategy for `stage-5a-create-absorbs-template-apply`
(merge now vs. continue 5B on it), then start Stage 5B (`status --source`).
