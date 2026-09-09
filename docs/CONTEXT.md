---
phase: 8
phase_name: Consolidation
updated: 2026-09-08
last_commit: b94685c
---

## Current Focus

On branch `stage-5a-create-absorbs-template-apply` (not merged to main).
Stages 5A (`create` absorbs `template apply`, DEC-026), 5B (`status`
absorbs `list`/`registrar list`/`dns show`/`dns check`), and 5C (`sync`
absorbs `dns repair`/`fix https`) are all implemented. **5C is not yet
committed** — commit it before anything else. User chose to keep stacking
sub-stages on this one branch rather than PR-per-stage.

## Active Tasks

- [x] **Commit Stage 5B**: done, `7925af9`.
- [x] **Live-verify Stage 5B**: real credentials ARE configured at
      `~/.config/mimeo/config.toml` (github org `tepiton`) — the "no
      credentials" note from the 5B session was wrong, don't repeat it.
      Ran `status --source dns`/full-join against `002373.xyz` live;
      found real drift (see below), confirming the command works.
- [x] **Stage 5C**: `sync` absorbs `dns repair`/`fix https`. Resolved
      DEC-025's open question — `sync --all`'s existing HTTPS-fixable
      check already covered `fix https`'s auto-discovery, confirmed by
      reading source, no new flag needed. Deleted `mimeo/cli/dns.py` and
      `mimeo/cli/fix.py` outright; no test relocation needed since
      `tests/test_sync.py` already covered every case. Deliberately
      dropped the `--wait`/propagation-poll flag the original plan called
      for (see DEC-025/IMPLEMENTATION.md Stage 5C for why). Fixed direct
      breakage in README.md/TROUBLESHOOTING.md only — not committed yet.
      Not live-tested against `002373.xyz`'s real drift (mock-tested only,
      same caveat 5B carried for `create`-adjacent paths).
- [x] **Stage 5C follow-up**: live-verified `sync` against `002373.xyz`'s
      real extra-CNAME drift — found a real bug, not just a confirmation:
      `sync --dry-run` reported `ok` for a domain `status` reports as
      `DNS: drift`. Root cause: `_sync_domain` only ever inspected
      `drift["missing"]`, so an extra-only result (Porkbun's
      `check_dns_drift` returns `status: "drift"` when there's no missing
      but some extra) fell through to "ok" silently. Fixed: `sync` now
      surfaces the same `dns_status`/`extra` vocabulary `status` uses
      (literally "drift", not new sync-specific wording) instead of
      collapsing it into "ok". New test:
      `test_extra_only_reports_drift_not_ok` in `tests/test_sync.py`.
      293 tests passing. Verified live against `002373.xyz` again after
      the fix — now correctly shows `drift` with the extra CNAME listed.
      Not yet committed.
- [ ] **QoL: `mimeo create` with no domain args prints Click's terse
      "Missing argument" error instead of full help.** User: "If you're
      going to tell me to run --help, just run help. IOW if you're just
      printing a short usage message, don't." Click's `no_args_is_help`
      doesn't apply automatically to a required `nargs=-1` argument; needs
      an explicit check in `create.py` (e.g. detect empty `domains` before
      Click's own argument validation fires, or invoke the help callback).
- [ ] **QoL: `status`'s problem-count summary line should say how to fix,
      not just count.** User: do this after 5C, don't forget. Once 5C
      lands, the summary (currently just "N domain(s), M with issues")
      should point at the merged repair command (`sync`?) for domains
      with fixable problems.
- [ ] **Stage 5D**: cleanup + full test/mypy/ruff pass + README update
      (README's `mimeo template apply` refs are stale from 5A too).
- [ ] **Stage 5E**: `template lint`. Blocked on DEC-024 implementation.
- [ ] **Track B**: Stage 4 E2E test lane, blocked on test account/org.
- [ ] **Backlog**: dead `max_retries`/`backoff_factor` params in `http.py`.

## Blockers

Stage 5E blocked on DEC-024 implementation. Everything else unblocked.

## Context

- DEC-026 explains `create`'s current safety checks (ownership check, DNS
  skip on pre-existing repo, no propagation poll) — read it before touching
  `create.py`/`github.py`'s template path.
- DEC-025 supersedes DEC-021's "keep dns repair/fix https as scalpels"
  call — don't re-litigate, just work the Stage 5 checklist.
- No provider-layer (`github.py`/`porkbun.py`) changes in Stage 5 outside
  DEC-026's fixes.
- Stage 5B: `--source dns` has no fleet-wide mode (domains must be named);
  `--problems` doubles as the dns-show-vs-dns-check switch when combined
  with `--source dns`; `--show-template` is new on `status` itself.
- Prefer testing provider-touching CLI changes (create/sync/status) against
  a real domain/repo, not mocks alone — DEC-026's bugs were invisible to
  mocks that didn't model the ownership/existing-repo distinction.
- **Real drift found live**: `002373.xyz` has an extra `CNAME * ->
  pixie.porkbun.com` (Porkbun's default parking wildcard) that GitHub
  Pages never expected. `dns repair --dry-run` only re-asserts the
  expected A/CNAME records — it does NOT delete extras, so it will not
  clear this drift. Left as-is deliberately to be a real 5C test case for
  "extra record" handling; don't delete it out of band.

## Next Session

Commit Stage 5C, then live-verify `sync` against `002373.xyz`'s real
extra-CNAME drift. After that, Stage 5D (cleanup + full test/mypy/ruff +
README/ARCHITECTURE.md doc rewrite — see IMPLEMENTATION.md for the full
list of stale doc references 5C deliberately left for 5D). Two QoL fixes
are also queued (see Active Tasks): `create`'s no-args help behavior, and
`status`'s summary line.
