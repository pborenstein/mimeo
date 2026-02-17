---
phase: 5
phase_name: CLI Integration
updated: 2026-02-16
last_commit: a210f41
---

## Current Focus

Refactored dead abstractions: removed DeploymentConfig, workspace from Config, and configure_custom_domain. Replaced instance flag pattern on GitHubHost with structured DeployResult return value.

## Active Tasks

- [x] Remove DeploymentConfig (unused model)
- [x] Remove workspace field from Config (unused)
- [x] Remove configure_custom_domain from Host ABC and GitHubHost
- [x] Replace _repo_was_created/_https_enabled instance flags with DeployResult dataclass
- [ ] Document workflow scope requirement in setup docs
- [ ] Document uv tool install for global CLI access

## Blockers

None.

## Context

- DeployResult(url, repo_created, https_enabled) now returned from deploy_site()
- DeployResult lives in providers/base.py alongside Host ABC
- CLI reads result fields directly — no more hasattr() checks
- 145 tests passing (removed 7 tests for deleted code)
- Ruff linting clean, mypy pre-existing error in cli.py (heterogeneous dict)

## Next Session

Documentation: setup guide covering workflow scope token requirement and uv tool install for global CLI access. Consider Phase 6 polish work.
