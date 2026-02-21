---
phase: 6
phase_name: Hardening
updated: 2026-02-20
last_commit: pending
---

## Current Focus

Added `--force-dns-update` flag to `mimeo create`: when NS mismatch is detected, resets
nameservers to Porkbun via `/domain/updateNs` API then proceeds with DNS config as normal.

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
- [ ] E2E integration test lane

## Blockers

None.

## Context

- 244 tests passing; mypy and ruff clean
- `--force-dns-update`: NS mismatch → calls `PorkbunRegistrar.update_nameservers()` → DNS config proceeds
- When NS already correct, `--force-dns-update` is a no-op
- `Registrar` ABC now has `update_nameservers(domain)` as abstract method
- Verified end-to-end: documentation.rodeo reset from Cloudflare NS to Porkbun successfully

## Next Session

Template/type system: --type flag on create (static, eleventy, astro), multiple
content generators, workflow variants (static.yml vs build workflows for SSGs).
