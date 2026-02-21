---
phase: 6
phase_name: Hardening
updated: 2026-02-20
last_commit: a3f1805
---

## Current Focus

Polishing `mimeo registrar list`: fixed CLI command name regression (`list-sites` →
`list`) and added alpha sort by domain. Both were post-merge fixups.

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
- `list_sites` function name + `name="list"` on decorator — avoids builtin shadow, preserves CLI name
- `registrar list` output sorted alpha by domain; concurrent enrichment preserves dict order via `enriched.values()`
- Click command name comes from function name by default; use `name=` param to override
- `list_domains()` on `Registrar` ABC + `PorkbunRegistrar`; enrichment in cli.py `_enrich()` closure

## Next Session

Template/type system: --type flag on create (static, eleventy, astro), multiple
content generators, workflow variants (static.yml vs build workflows for SSGs).
