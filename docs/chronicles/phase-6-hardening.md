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
