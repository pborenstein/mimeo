---
phase: 7
phase_name: CLI Redesign
updated: 2026-03-28
last_commit: 5b5d2fc
---

## Current Focus

Completed comprehensive code review with 25 findings and fixed all of them.
Branch `fix/code-review-findings` has all changes, uncommitted.

## Active Tasks

- [ ] E2E integration test lane (separate from unit tests, gated, hits real APIs)
- [ ] Template parameterization (substitute domain into template files)

## Blockers

None.

## Context

- 233 tests passing; mypy and ruff clean
- All 25 code review items addressed (see docs/CODE_REVIEW.md)
- Key changes: domain validation at CLI layer, ownership check via PorkbunRegistrar.domain_exists(), GITHUB_PAGES_IPS moved to github.py, removed dead code (Domain model, NSMismatchError), DNS progress indication, EXIT_GENERAL=1 added
- Provider ABCs now have public methods for CLI-facing operations (health_status, enable_https_enforcement)
- check_nameservers removed from DNSProvider ABC (registrar-only concern)
- "Loading configuration..." message removed from stdout (was polluting pipe output)
- config.toml.example had wrong env var name (MIMEO_PORKBUN_SECRET_KEY -> MIMEO_PORKBUN_SECRET)

## Next Session

Commit the code review fixes. Consider E2E integration tests or template parameterization as next feature work.
