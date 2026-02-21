---
phase: 6
phase_name: Hardening
updated: 2026-02-20
last_commit: 2ff254e
---

## Current Focus

Registrar/DNS/Host separation landed: three-layer model with `Registrar`, `DNSProvider`,
`Host` ABCs. NS check gates DNS config on `create`. `mimeo doctor` now accepts domain
args for NS verification.

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
- [ ] E2E integration test lane

## Blockers

None.

## Context

- 239 tests passing; mypy and ruff clean
- `PorkbunRegistrar` — NS check only; `PorkbunDNSProvider` — all DNS ops
- `GitHubHost.required_dns_records(domain)` replaces static `github_pages_records()`
- NS mismatch on `create` → warning + skip DNS, site still deploys to .github.io
- `mimeo doctor site1.com site2.com` checks NS for each domain; mismatch → exit non-zero
- `NSMismatchError` and `NameserverCheckResult` added to exceptions/models

## Next Session

Template/type system: --type flag on create (static, eleventy, astro), multiple
content generators, workflow variants (static.yml vs build workflows for SSGs).
