---
phase: 6
phase_name: Hardening
updated: 2026-03-06
last_commit: a65448f
---

## Current Focus

Docs cleanup: removed dead-weight files (ABSTRACT.md, CODEX-SPEAKS.md,
CONTRIBUTING.md, archive/PLAN.md, porkbun-OpenAPI/). Updated docs/README.md.
Beginning to explore template/type system for `mimeo create`.

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
- [x] docs/ cleanup (dead files removed)
- [ ] E2E integration test lane
- [ ] Template/type system (`--template` flag on `create`)

## Blockers

None.

## Context

- 258 tests passing; mypy and ruff clean
- tantamount.rodeo is the working sandbox for template exploration
- Template family exists in mimeo-sites/TEMPLATES/: eleventy-pamphlet, eleventy-chapbook, eleventy-folio
- orobia.{lol,dev,net} repos in tepiton org are plain placeholders; the Eleventy template repos point custom domains there
- Pandoc-based single-page markdown template is the first new template target

## Next Session

Build a pandoc-based `simple-markdown` template: index.md + stylesheet +
GitHub Actions workflow (pandoc build → Pages deploy). Wire up `--template`
flag on `mimeo create`. Start in tantamount.rodeo as sandbox.
