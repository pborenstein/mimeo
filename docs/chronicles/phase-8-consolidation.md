# Phase 8: Consolidation Chronicles

## Entry 39: list --show-template; validate template name; rename-by-ID fix (2026-08-27)

**What**: Three improvements in one session.

**list --show-template**: New flag on `mimeo list` fetches `template_repository`
per repo via parallelized `gh api repos/<owner>/<repo>` calls and adds a TEMPLATE
column. GitHub's search API doesn't expose this field, so a per-repo call is
unavoidable; the flag makes it opt-in so the default list stays fast.

**template apply early validation**: `validate_template()` on `GitHubHost`
checks that `TEMPLATE_ORG/<name>` exists before the confirmation prompt runs.
A typo now fails immediately with "Template 'x' not found in tepiton. Check the
spelling and try again." instead of renaming repos and then 422ing mid-flow.

**rename-by-ID fix**: `_rename_repository` was using `PATCH repos/<owner>/<name>`,
which GitHub 307-redirects when the repo was previously renamed. Switched to
fetching the repo ID first, then PATCHing `repositories/<id>` (stable across
renames). Added one 422 retry with 3s sleep for rapid successive renames. See
DEC-023.

**Decisions**: DEC-023

**Files**: `mimeo/providers/host/github.py`, `mimeo/cli/list_cmd.py`,
`mimeo/cli/template.py`

---

## Entry 38: template apply --force deleted a live repo -- rename-not-delete fix (2026-08-25)

**What**: Live `template apply --template mellowtimesphere.com laptopistan.com` deleted
`tepiton/laptopistan.com` and then failed with a 404 on the template-generate call, because
`mellowtimesphere.com` wasn't flagged `is_template` on GitHub. `_create_from_template` deleted
the target repo *before* attempting generate, with no rollback on failure. Restored via GitHub
org deleted-repo restore (works because `tepiton` is an Organization; would not have worked for
a personal-owned repo). See DEC-022.

**Why**: `is_template: false` on the source repo makes GitHub's `generate` endpoint return a
bare 404 indistinguishable from "repo doesn't exist" -- no error message pointed at the real
cause. Root cause confirmed via `gh api repos/tepiton/mellowtimesphere.com --jq .is_template`.
Separately, delete-before-generate meant *any* generate failure -- not just this one -- would
have destroyed the target repo permanently.

**How**: Added `_ensure_is_template` (reads `is_template`, PATCHes to `true` if unset) called
right before `generate`. Changed force-replace to rename the target repo out of the way
(`{name}-mimeo-replaced-{timestamp}`) instead of deleting it; only deletes the renamed-old repo
after `generate` succeeds; renames it back on any `HostError` from `_ensure_is_template` or
`generate`. Also set `is_template: true` on `tepiton/mellowtimesphere.com` directly via `gh api`.
293 -> 297 tests (rename/rollback paths + `_ensure_is_template` unit tests); mypy and ruff clean.

**Files**: `mimeo/providers/host/github.py`, `tests/providers/host/test_github.py`, DEC-022

## Entry 37: Default template customization -- fix hardcoded "mimeo.lol" (2026-08-25)

**What**: `mimeo.lol` (the default template) is itself a live site, so its
`index.html` hardcodes "mimeo.lol" in `<title>` and letter-spaced
("m i m e o . l o l") in `<h1>`. Every site generated from it -- via `create`
or `template apply` -- shipped that literal text instead of its own domain.
Added `_customize_default_template` to rewrite both forms post-generation.

**Why**: Reported live: `template apply --template mimeo.lol
tantamount.rodeo` produced a page still reading "m i m e o . l o l". First
fix attempt swallowed a real error (`except HostError: pass`) and shipped
untested against the actual template content, so it silently did nothing.
Second attempt traced the live call path end-to-end and found the real
cause: `generate`-from-template returns before GitHub populates the file
tree, so the immediate `index.html` read 404s with "repository is empty" --
the same failure class as Entry 30's `_wait_for_repo` fix, but on the
contents API rather than repo metadata, and previously undetected because
nothing polled it.

**How**: `_customize_default_template` reads `index.html` (retrying up to
5x/2s on the empty-repo 404), substitutes `DEFAULT_TEMPLATE` and its
letter-spaced form for the real domain in memory, writes back only if
something changed. Raises on persistent failure instead of swallowing.
Scoped to `mimeo.lol` only -- `eleventy-*` templates are full site
generators where a blind string-replace would be unsafe; that's the
remaining open part of the carried-over "template parameterization" task.
Live-verified: ran `template apply` against `tepiton/tantamount.rodeo` for
real and confirmed the deployed `index.html` and commit history.

**Files**: `mimeo/providers/host/github.py`, `tests/providers/host/test_github.py`

## Entry 36: status also requires --all for fleet-wide (2026-07-06)

**What**: A bare `mimeo status` now refuses to run; fleet-wide sweeps
require explicit `--all`, matching sync.

**Why**: User ran the fleet sweep and gave up waiting — several API calls
per domain across 105 domains takes minutes. Unlike sync's guard (safety),
this one is about cost; recorded as such in DEC-021 Stage 3 resolutions.

**Files**: `mimeo/cli/status.py`, `tests/test_status.py`, commit d5b7723

## Entry 35: Stage 3 — mimeo sync, converge on desired state (2026-07-06)

**What**: Added `mimeo sync [DOMAINS... | --all]`: applies missing DNS
records and enables HTTPS enforcement when the certificate is ready, in one
pass, with `--dry-run` and `--reset-nameservers`.

**Why**: The remediation half of DEC-021's status/sync pair — replaces
running `dns repair` and `fix https` separately across the fleet.

**How**: Same union-of-inventories targeting as status, built on map_items.
Safety decisions (user-confirmed): fleet-wide requires explicit `--all`
(no-arg refuses, exit 2); acts on missing records only, never deletes
extras (the Porkbun wildcard parking CNAME survives); nameservers touched
only with `--reset-nameservers`; no propagation wait at fleet scale.
`dns repair` / `fix https` kept as targeted scalpels. Live-verified:
guard refuses correctly; `--dry-run` on two real domains reported both ok
(wildcard drift correctly triggers no action).

**Decisions**: DEC-021 (Stage 3 resolutions)

**Files**: `mimeo/cli/sync.py`, `mimeo/cli/__init__.py`, `tests/test_sync.py`

## Entry 34: Stage 2 — mimeo status, the cross-provider join (2026-07-06)

**What**: Added `mimeo status [DOMAINS...]` — one view joining the Porkbun
account against mimeo-managed GitHub repos: EXPIRES / NS / DNS drift / SITE
health per domain, `--problems` filter, text/json/csv.

**Why**: The two inventories (`list`, `registrar list`) never joined, so the
fleet questions (domains without sites, sites without domains, drift) had no
command. This is the diagnostic half of DEC-021's status/sync pair.

**How**: Built on Stage 1's `map_items`; shares one registrar, DNS provider,
and host across workers. No-arg mode targets the union of both inventories.
DNS column is "-" when no repo exists (no desired state to compare). Drift
and unhealthy sites are findings (exit 0); API errors are failures
(EXIT_PARTIAL). Live-verified: correctly surfaced the Porkbun wildcard
parking CNAME as drift, matching `dns check`.

**Decisions**: DEC-021 (Stage 2)

**Files**: `mimeo/cli/status.py`, `mimeo/cli/__init__.py`, `tests/test_status.py`

## Entry 33: Stage 1 — shared domain-operation engine (2026-07-06)

**What**: Built `map_items` / `render_results` / `exit_on_errors` in
`_processing.py` and migrated `registrar list`, `dns check`, `dns show`,
`fix https`, and `list` onto them. Removed four hand-rolled thread pools.

**Why**: Three of the four pools crashed the whole command on one bad
`future.result()` (the zero-results bug class); every command duplicated the
text/json/csv dispatch. DEC-021 Stage 1.

**How**: `map_items` returns results in input order and converts escaped
exceptions to error rows via an `on_error` callback. `render_results` keeps
text rendering as a per-command callback (layouts genuinely differ) but owns
json/csv. Exit codes unified: some-failed -> EXIT_PARTIAL, all-failed ->
category code (dns show partial changed from transient to EXIT_PARTIAL).
Command files shrank ~65 lines, engine added ~110 (net +51); the payoff is
structural. Follow-up added: fold `process_domains_concurrent` into
`map_items`. Live-verified against real Porkbun and GitHub APIs.

**Decisions**: DEC-021 (Stage 1)

**Files**: `mimeo/cli/_processing.py`, `mimeo/cli/{registrar,dns,fix,list_cmd}.py`,
`tests/test_processing.py`

## Entry 32: Phase 8 planned — consolidation to status/sync (2026-07-06)

**What**: Closed Phase 7 and planned Phase 8 after a whole-codebase design
review. Reframed mimeo as a fleet manager for domain-to-GitHub-Pages sites.

**Why**: The CLI grew by accretion — one verb per operational incident
(dns repair, fix https, template apply) — and the two inventories (`list`,
`registrar list`) never join, so fleet-level questions across 105 domains
have no command. Half the codebase is per-command copies of the same
fan-out/render plumbing, where the zero-results bug lived.

**How**: Four staged tasks in IMPLEMENTATION.md: (1) shared domain-operation
engine, (2) `mimeo status` cross-provider join, (3) `mimeo sync` convergence
with --dry-run, (4) gated E2E lane. Plus identity fix and carried-over
template parameterization. Full rationale and alternatives in DEC-021.

**Decisions**: DEC-021

**Files**: `docs/IMPLEMENTATION.md`, `docs/DECISIONS.md`, `docs/CONTEXT.md`
