# Phase 8: Consolidation Chronicles

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
