# Phase 7: CLI Redesign Chronicles

## Entry 27: --force flag and CLI design rethink (2026-03-19)

**What**: Added `--force` flag to `create` that deletes and recreates an existing
repo from the specified template. Set `is_template=true` on all 5 tepiton
template repos (only mimeo.lol had it). Added warning when repo exists and
template is not applied. Identified that the `create` command is overloaded --
doing both provisioning and repair with a confusing flag set.

**Why**: User tested `--template eleventy-folio` and got a cryptic 404 because
the repo wasn't marked as a template. Then re-running with a different template
on an existing domain silently skipped the template. DNS also ran unnecessarily.

**How**: `_create_from_template` returns 3-tuple `(name, created, existed)`.
`_delete_repository` added. `DeployResult` gained `repo_existed` field. CLI
warns when template not applied, suggests `--force`.

**Files**: `mimeo/providers/host/github.py`, `mimeo/cli.py`, `mimeo/providers/base.py`
