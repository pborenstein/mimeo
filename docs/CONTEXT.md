---
phase: 7
phase_name: CLI Redesign
updated: 2026-03-19
last_commit: 928c6aa
---

## Current Focus

Added `--force` flag to `mimeo create` for replacing existing repos with a new
template. Set `is_template=true` on all 5 tepiton template repos. Identified
that `create` is overloaded -- doing both provisioning and repair. CLI options
are becoming a hodgepodge. Need to rethink the command structure from first
principles before adding more flags.

## Active Tasks

- [ ] Rethink `create` command structure (provisioning vs repair)
- [ ] E2E integration test lane
- [ ] Template parameterization (substitute domain into template files)

## Blockers

None.

## Context

- 242 tests passing; mypy and ruff clean
- All 5 templates in tepiton org have is_template=true
- `--force` implemented but uncommitted -- deletes and recreates repo from template
- Warning shown when repo exists and template not applied
- DNS always runs even when repo already exists -- wasteful
- `--force` vs `--force-dns-update` naming is confusing
- User wants to rethink CLI design from first principles (switching to opus)

## Next Session

Redesign `mimeo create` command structure. The current flag set (`--force`,
`--force-dns-update`, `--template`) suggests `create` is doing too much.
Consider separating provisioning from repair/maintenance commands.
