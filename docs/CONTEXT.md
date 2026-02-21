---
phase: 6
phase_name: Hardening
updated: 2026-02-20
last_commit: acb399b
---

## Current Focus

Added `mimeo registrar list` subcommand: lists all domains in the Porkbun
account with NS enrichment, optional DNS records, and text/JSON/CSV output.
Also fixed `list` → `list_sites` function rename to stop shadowing the builtin.

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
- [ ] E2E integration test lane

## Blockers

None.

## Context

- 258 tests passing; mypy and ruff clean
- `list` Click command renamed to `list_sites` in cli.py — avoids shadowing builtin `list`
- `registrar list` enriches domains concurrently: NS via `check_nameservers()`, DNS via `_get_domain_records()`
- `list_domains()` added to `Registrar` ABC and implemented in `PorkbunRegistrar`
- `scripts/fetch_porkbun_domains.py` was the prototype; the CLI version shares no code with it

## Next Session

Template/type system: --type flag on create (static, eleventy, astro), multiple
content generators, workflow variants (static.yml vs build workflows for SSGs).
