---
phase: 6
phase_name: Hardening
updated: 2026-02-17
last_commit: 094bf6d
---

## Current Focus

Phase 6 Hardening. Retry with jitter for transient API failures completed this session.

## Active Tasks

- [x] Add `mimeo doctor` preflight command
- [x] Retry with jitter for transient failures
- [ ] Improve failure taxonomy and exit codes
- [ ] Reconciliation / DNS drift detection
- [ ] Add `--workers` option to `create`
- [ ] E2E integration test lane
- [ ] Config schema versioning
- [ ] Structured logging (`--log-format json`)

## Blockers

None.

## Context

- 198 tests passing; mypy and ruff clean (fixed pre-existing cli.py issues this session)
- retry_with_jitter in mimeo/utils/retry.py; retries at provider layer, not HTTP transport
- HTTPClient is now a thin transport; urllib3 Retry adapter removed
- Retryable: APIError 429/5xx, NetworkError, HostError with transient keywords

## Next Session

Continue Phase 6: improve failure taxonomy and exit codes, or add --workers option to create.
