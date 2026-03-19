---
phase: 6
phase_name: Hardening
updated: 2026-03-19
last_commit: 5e23155
---

## Current Focus

Replaced hardcoded content generation with GitHub template repo instantiation.
`mimeo create example.com` now creates repos from `tepiton/mimeo.lol` via the
GitHub "Use this template" API. Next: parameterization (substituting domain
into template content like metadata.js / index.md frontmatter).

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
- [x] Replace content generation with GitHub template repo API
- [ ] E2E integration test lane
- [ ] Template parameterization (substitute domain into template files)

## Blockers

None.

## Context

- 242 tests passing; mypy and ruff clean
- `tepiton/mimeo.lol` is_template=true (set this session)
- All 5 templates in tepiton org: mimeo.lol, pandoc-simple, eleventy-pamphlet, eleventy-chapbook, eleventy-folio
- `--template` flag wired up on `create`, defaults to `mimeo.lol`
- content.py deleted; `_init_and_push_repository` deleted; `_create_from_template` added

## Next Session

Discuss and implement template parameterization: substituting the domain name
into template files (e.g. `metadata.js` url field for Eleventy templates,
`index.md` frontmatter title for pandoc-simple).
