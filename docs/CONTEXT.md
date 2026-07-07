---
phase: 7
phase_name: CLI Redesign
updated: 2026-07-06
last_commit: e9830da
---

## Current Focus

Added `mimeo dns show` (raw live records for specific domains) and made
`registrar list` return partial results instead of discarding everything
when one domain's enrichment fails.

## Active Tasks

- [ ] Fix 3 failing tests in tests/providers/host/test_github.py (broken by e9830da, pre-existing)
- [ ] E2E integration test lane (separate from unit tests, gated, hits real APIs)
- [ ] Template parameterization (substitute domain into template files)

## Blockers

None.

## Context

- `mimeo dns show DOMAIN...` fetches live Porkbun records; text/json/csv; sequential; per-domain errors
- `registrar list` now shares one registrar + one DNS client across workers (was 2 fresh sessions per domain)
- Enrichment failures carry `error`/`error_category` per row; command exits EXIT_PARTIAL (6) if any failed
- `_get_domain_records` renamed to public `get_domain_records`
- Verified live: 105 domains enriched with --with-dns, 0 failures
- 238 tests passing (3 pre-existing github template test failures remain); mypy and ruff clean

## Next Session

Fix the 3 broken test_github.py tests, then E2E integration tests or
template parameterization.
