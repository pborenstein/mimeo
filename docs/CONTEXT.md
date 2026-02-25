---
phase: 6
phase_name: Hardening
updated: 2026-02-25
last_commit: 73d0566
---

## Current Focus

Documentation sync: updated ARCHITECTURE.md and README.md to match the
current implementation (Phase 6 additions that were not yet documented).

## Active Tasks

- [x] Add `mimeo doctor` preflight command
- [x] Retry with jitter for transient failures
- [x] Improve failure taxonomy and exit codes
- [x] Add `--workers` option to `create`
- [x] Config schema versioning and deprecation warnings
- [x] Structured logging (`--log-format json`)
- [x] Reconciliation / DNS drift detection (`--dns-check` on `list`)
- [x] Registrar/DNS/Host three-layer separation
- [x] `mimeo doctor [domain...]` NS check
- [x] `--force-dns-update` flag on `create`
- [x] `mimeo registrar list` subcommand
- [x] ARCHITECTURE.md and README.md synced to current implementation
- [ ] E2E integration test lane

## Blockers

None.

## Context

- 258 tests passing; mypy and ruff clean
- ARCHITECTURE.md now documents: `utils/retry.py`, `DNSProvider` ABC, `PorkbunDNSProvider`,
  `NSMismatchError`, `NameserverCheckResult`, exit codes table, `--log-format` global,
  `registrar list` workflow, structured logging section, `--force-dns-update` in create workflow,
  `--dns-check` in list workflow, `doctor [domain...]` NS check
- README.md now documents: `--log-format` global option, `--force-dns-update`, `--dns-check`,
  `doctor [domain...]` NS check, `utils/retry.py` in project structure
- Registrar ABC: `check_nameservers`, `update_nameservers`, `list_domains`
- DNSProvider ABC (separate from Registrar): `configure_dns`, `verify_dns`, `check_nameservers`

## Next Session

Template/type system: --type flag on create (static, eleventy, astro), multiple
content generators, workflow variants (static.yml vs build workflows for SSGs).
