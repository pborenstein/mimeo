# Phase 6: Hardening Chronicles

## Entry 15: Documentation Refresh (2026-02-17)

**What**: Rewrote README and refreshed all planning docs to match current state. Moved PLAN.md to archive.

**Why**: CODEX-SPEAKS assessment scored documentation accuracy at 4/10. README still said "Phase 0 - Research & Design". PLAN.md (pre-implementation spec) was indistinguishable from current planning docs. IMPLEMENTATION.md had a 100-line checkbox log for Phase 5.

**How**:
- README rewritten from scratch: current commands, config format, prerequisites (including workflow scope requirement), known limitations, actual project structure
- IMPLEMENTATION.md: Phase 5 collapsed to ~15-line summary; Phase 6 task list added from CODEX-SPEAKS priorities
- PLAN.md moved to docs/archive/ (pre-implementation spec, kept for history)
- CONTEXT.md updated to Phase 6 with next session pointing at `mimeo doctor`

**Files**: README.md, docs/IMPLEMENTATION.md, docs/CONTEXT.md, docs/archive/PLAN.md (moved)

## Entry 16: mimeo doctor command (2026-02-17)

**What**: Added `mimeo doctor` preflight command that checks all prerequisites before running mimeo.

**Why**: CODEX-SPEAKS identified this as top Phase 6 priority. Users hitting silent failures from missing gh auth or wrong token scopes needed actionable diagnostics upfront.

**How**:
- Five checks: Python >=3.11, gh installed, gh authenticated, workflow scope, config valid
- Each check is a standalone `_check_*` helper returning `(ok, detail, fix)` — independently testable
- Command prints colored pass/fail rows with yellow remediation hints for failures
- Exits 0 only when all checks pass
- 17 new tests added (177 total); all passing

**Files**: mimeo/cli.py, tests/test_cli.py

## Entry 17: Repo cleanup and baseline documentation (2026-02-17)

**What**: Moved smoke test scripts from root into scripts/, then ran docs-artichoke to create a comprehensive documentation baseline.

**Why**: Two interactive smoke test scripts at the repo root belonged with other dev utilities in scripts/. docs-artichoke was used to fill gaps in user-facing docs that had grown stale.

**How**:
- `smoke_test.py` -> `scripts/smoke_test_porkbun.py` (renamed for clarity)
- `smoke_test_github.py` -> `scripts/smoke_test_github.py`
- Created: CONTRIBUTING.md, docs/ARCHITECTURE.md, docs/TROUBLESHOOTING.md, docs/README.md
- Updated: README.md (quick start, doctor command, architecture diagram, doc nav table)

**Files**: commit 7efa101; CONTRIBUTING.md, docs/ARCHITECTURE.md, docs/TROUBLESHOOTING.md, docs/README.md, README.md

## Entry 18: Retry with jitter for transient API failures (2026-02-17)

**What**: Replaced urllib3 Retry adapter with a provider-layer retry_with_jitter helper. Fixed pre-existing mypy and ruff issues in cli.py.

**Why**: Five concurrent workers in ThreadPoolExecutor could all fail simultaneously on rate-limit or transient errors, then retry at the same moment (thundering herd). urllib3 Retry used pure exponential backoff with no jitter; GitHub gh CLI had zero retry. Also cleaned up pre-existing lint issues caught by mypy/ruff while the files were open.

**How**:
- New `mimeo/utils/retry.py`: `retry_with_jitter(fn, retries, base, cap)` — `min(cap, base**attempt) + uniform(0,1)` sleep between attempts
- Retryable: `APIError` 429/5xx, `NetworkError` (all), `HostError` with transient keywords (502, 503, 500, rate limit, timeout)
- `HTTPClient`: removed `Retry`/`HTTPAdapter`; now a thin transport
- `PorkbunRegistrar._make_request`: wraps `client.post()` with retry_with_jitter
- `GitHubHost._run_gh_command`: wraps subprocess call via nested `_attempt` function
- cli.py: `cast(List, result["log"])` to fix mypy; removed spurious `f` prefixes on two strings
- 198 tests, mypy clean, ruff clean

**Files**: commit 094bf6d; mimeo/utils/retry.py (new), mimeo/utils/http.py, mimeo/providers/registrar/porkbun.py, mimeo/providers/host/github.py, mimeo/cli.py, tests/utils/test_retry.py (new)

## Entry 19: Failure taxonomy and exit codes (2026-02-17)

**What**: Replaced uniform exit-1 with categorized exit codes so callers can distinguish failure types without parsing error messages.

**Why**: Every failure — missing config, bad API key, rate limit, network timeout — exited 1 with "Aborted!". Scripting mimeo or diagnosing failures required reading prose output. Exit codes make failure type machine-readable.

**How**:
- EXIT_* constants in mimeo/exceptions.py: 2=config, 3=auth, 4=rate-limit, 5=transient, 6=partial
- _categorize_error(exc) in cli.py inspects exception type and message keywords
- Error messages prefixed [category] e.g. "[config] missing api key"
- create picks most specific exit code across all failed domains
- DNS-only failure (deploy succeeded) still exits 0; records error_category="partial" in result
- doctor exits EXIT_CONFIG on check failure
- 198 tests passing, mypy and ruff clean

**Files**: commit 7a3f2e2; mimeo/exceptions.py, mimeo/cli.py, tests/test_cli.py

## Entry 20: Hardening round 2 — workers, schema versioning, JSON logging, DNS drift (2026-02-18)

**What**: Four hardening tasks in one session: configurable concurrency, config
schema versioning, structured JSON logging, and DNS drift detection.

**Why**: Remaining Phase 6 tasks. All improve operability for scripts and CI:
`--workers` lets callers control load; schema versioning protects against silent
config drift as fields evolve; `--log-format json` makes output parseable; `--dns-check`
exposes DNS state without requiring manual Porkbun login.

**How**:
- `--workers N` on `create`: `click.IntRange(min=1)`, default 5, forwarded to ThreadPoolExecutor
- `schema_version = 1` in config TOML; missing → DeprecationWarning, future → UserWarning, invalid → ConfigurationError; `CURRENT_SCHEMA_VERSION` constant in config.py
- `--log-format text|json` on main group (global); JSON mode emits `{ts, level, message, domain?}` to stderr via `_emit()`; all text banners/tables suppressed in json mode
- `PorkbunRegistrar.check_dns_drift(domain, expected)`: compares live Porkbun records against expected set; returns `{status: ok|drift|missing, missing: [...], extra: [...]}`
- `mimeo list --dns-check`: fetches drift concurrently via ThreadPoolExecutor; text shows DNS column + drift details section; JSON includes full dns object; CSV adds dns_status column
- 18 new tests (216 total); mypy and ruff clean throughout

**Files**: mimeo/cli.py, mimeo/config.py, mimeo/providers/registrar/porkbun.py, tests/test_cli.py, tests/test_config.py, tests/providers/registrar/test_porkbun.py

## Entry 21: Registrar/DNS/Host three-layer separation + doctor NS check (2026-02-20)

**What**: Introduced `DNSProvider` ABC, split `PorkbunRegistrar` into separate registrar
and DNS provider classes, moved DNS record knowledge to `Host`, and added NS verification
to `mimeo doctor`.

**Why**: `PorkbunRegistrar` conflated registration, DNS management, and host knowledge.
When DNS is delegated elsewhere (Cloudflare, Netlify), mimeo would write records via the
Porkbun API, succeed, but the world would never see them. The fix: NS check gates DNS
config; warn-and-skip if NS doesn't point at Porkbun. See DEC-015, DEC-016.

**How**:
- `DNSProvider` ABC in `providers/base.py`: `configure_dns`, `verify_dns`, `check_nameservers`
- `Registrar` trimmed to `check_nameservers` only
- `Host` gains `required_dns_records(domain)` abstract method
- `porkbun.py` split: `_PorkbunClient` (shared auth), `PorkbunRegistrar` (NS check), `PorkbunDNSProvider` (all DNS ops + drift)
- `PORKBUN_NAMESERVERS` constant; `_lookup_nameservers()` module-level helper
- `GitHubHost.required_dns_records()` replaces static `PorkbunRegistrar.github_pages_records()`
- `create` flow: deploy → `host.required_dns_records()` → NS check → skip or configure DNS
- `list --dns-check` uses `PorkbunDNSProvider` + `host.required_dns_records()`
- `mimeo doctor [domain...]`: optional domain args; NS check row per domain; mismatch → exit non-zero
- `NameserverCheckResult` dataclass, `NSMismatchError` exception added
- 239 tests (up from 216); mypy and ruff clean

**Decisions**: DEC-015, DEC-016

**Files**: mimeo/providers/base.py, mimeo/providers/registrar/porkbun.py, mimeo/providers/host/github.py, mimeo/cli.py, mimeo/models.py, mimeo/exceptions.py, tests/

## Entry 22: --force-dns-update flag (2026-02-20)

**What**: Added `--force-dns-update` flag to `mimeo create`. When NS mismatch is detected,
resets the domain's nameservers to Porkbun via API then proceeds with full DNS config.

**Why**: Real-world use case — domain registered at Porkbun with NS delegated to Cloudflare.
Without the flag, mimeo warns and skips DNS. With it, ownership is asserted back to Porkbun.

**How**:
- `Registrar` ABC: added `update_nameservers(domain)` abstract method
- `PorkbunRegistrar.update_nameservers()`: calls `/domain/updateNs/{domain}` with `PORKBUN_NAMESERVERS`
- `_process_single_domain`: `force_dns_update` param; on mismatch calls `update_nameservers` then falls through to DNS config
- `create` command: `--force-dns-update` flag, threaded through sequential and concurrent paths
- 5 new tests (244 total); mypy and ruff clean

**Files**: mimeo/providers/base.py, mimeo/providers/registrar/porkbun.py, mimeo/cli.py,
tests/test_providers_base.py, tests/test_cli.py, tests/providers/registrar/test_porkbun.py

## Entry 23: mimeo registrar list subcommand (2026-02-20)

**What**: Added `mimeo registrar list` — lists all domains in the Porkbun account with
NS status, expiry, and optional DNS records. Concurrent enrichment, three output formats.
Also renamed `list` function to `list_sites` in cli.py to stop shadowing Python's builtin.

**Why**: `scripts/fetch_porkbun_domains.py` did this as a standalone script; moving it into
the CLI makes it discoverable and consistent. The `list` shadowing had caused two separate
bugs (`list(enumerate(...))` calling the Click command, `isinstance(data, list)` failing in tests).

**How**:
- `Registrar` ABC: `list_domains() -> list[dict[str, Any]]` abstract method
- `PorkbunRegistrar.list_domains()`: calls `/domain/listAll`, returns domain list
- `cli.py`: `registrar` group + `registrar_list` command; concurrent `_enrich()` closure
  per domain (NS via `check_nameservers()`, DNS via `_get_domain_records()`)
- `list` Click command renamed to `list_sites` (no CLI surface change)
- 81 new tests (258 total); mypy and ruff clean
- Docs: README, docs/LIST_COMMAND.md, docs/IMPLEMENTATION.md updated

**Files**: commit acb399b

## Entry 24: Documentation sync (2026-02-25)

**What**: Updated ARCHITECTURE.md and README.md to reflect all Phase 6 additions
that had been implemented but not yet documented.

**Why**: Docs lagged behind implementation. ARCHITECTURE.md still described the
old two-ABC design (`Registrar` + `Host`); README.md was missing several flags
and the global `--log-format` option entirely.

**How**:
- ARCHITECTURE.md: component map, provider abstractions, create/list/doctor/registrar-list
  workflows, exit codes table, structured logging section — all updated to match code
- README.md: global options section (`--log-format`), `--force-dns-update`, `--dns-check`,
  `doctor [domain...]` NS check, `utils/retry.py` in project structure
- CONTEXT.md: updated to 2026-02-25

**Files**: docs/ARCHITECTURE.md, README.md, docs/CONTEXT.md

## Entry 25: Docs cleanup (2026-03-06)

**What**: Removed dead-weight documentation files; updated docs/README.md.

**Why**: Files were historical artifacts with no ongoing reference value — a one-time AI code review (CODEX-SPEAKS.md), the original pre-implementation spec (archive/PLAN.md), raw API spec files (porkbun-OpenAPI/), the project abstract (ABSTRACT.md), and CONTRIBUTING.md (single-developer project).

**How**: Deleted 7 files, updated docs/README.md to remove dead links.

**Removed**:
- `docs/ABSTRACT.md`
- `docs/CODEX-SPEAKS.md`
- `docs/archive/PLAN.md`
- `docs/porkbun-OpenAPI/` (3 files)
- `CONTRIBUTING.md`

**Files**: docs/README.md
## Entry 26: Replace content generation with GitHub template repo API (2026-03-19)

**What**: Deleted `content.py` and the git-init/push flow. `mimeo create` now
instantiates repos via `POST /repos/tepiton/{template}/generate`. Added
`--template` flag (default: `mimeo.lol`). Set `is_template=true` on
`tepiton/mimeo.lol` via API.

**Why**: Simpler, fewer moving parts. No local content generation, no temp
dirs, no git operations. Template repos in `tepiton` org are the source of
truth for site content and GitHub Actions workflows.

**How**: Added `_create_from_template()` to `GitHubHost`, removed
`_create_repository()` and `_init_and_push_repository()`. Updated `deploy_site`
signature (no `content_path`). Deleted `test_content.py`. 242 tests passing.

**Decisions**: See DEC-017.

**Files**: `mimeo/providers/host/github.py`, `mimeo/cli.py`, `mimeo/providers/base.py`

