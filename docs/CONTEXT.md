---
phase: 6
phase_name: Hardening
updated: 2026-02-18
last_commit: 8af228c
---

## Current Focus

Phase 6 Hardening — four more tasks landed this session: --workers, config schema
versioning, --log-format json, and DNS drift detection via --dns-check.

## Active Tasks

- [x] Add `mimeo doctor` preflight command
- [x] Retry with jitter for transient failures
- [x] Improve failure taxonomy and exit codes
- [x] Add `--workers` option to `create`
- [x] Config schema versioning and deprecation warnings
- [x] Structured logging (`--log-format json`)
- [x] Reconciliation / DNS drift detection (`--dns-check` on `list`)
- [ ] E2E integration test lane

## Blockers

None.

## Context

- 216 tests passing; mypy and ruff clean
- `--workers N` on create; defaults 5, capped to domain count
- `schema_version = 1` in config; missing version → DeprecationWarning
- `--log-format json` on main group; JSON lines to stderr, suppresses text output
- `mimeo list --dns-check`: calls Porkbun API, compares live vs expected records
- check_dns_drift() added to PorkbunRegistrar; returns ok/drift/missing

## Next Session

Template/type system: --type flag on create (static, eleventy, astro), multiple
content generators, workflow variants (static.yml vs build workflows for SSGs).
