# Phase 7: CLI Redesign Chronicles

## Entry 30: Race condition fix — wait for repo after generate (2026-04-03)

**What**: Fixed a race condition where `mimeo create` failed with 404 on topics,
pages, and custom domain calls immediately after `repos/.../generate` returned.

**Why**: GitHub's template-generate API returns before the repo is actually
accessible. Every subsequent API call (topics, pages, domain) hit a repo that
didn't exist yet. Diagnosed via a bug report from a real `mimeo create` run on
`tantamount.rodeo` — improved error messages (endpoint included) made the
failing call visible for the first time.

**How**: Added `_wait_for_repo()` to `GitHubHost` — polls `repos/{owner}/{name}`
up to 30s with 2s intervals before proceeding. Also improved `_gh_api` to
include `METHOD endpoint` in error messages so future failures are identifiable.

**Files**: `mimeo/providers/host/github.py`

---


## Entry 28: Comprehensive code review -- 25 findings fixed (2026-03-28)

**What**: Performed a critical user-perspective code review, documented 25 findings
in `docs/CODE_REVIEW.md`, and fixed all of them on branch `fix/code-review-findings`.

**Why**: Pre-1.0 polish. Several issues would bite new users immediately (wrong env
var name in config example, phantom flag in README, no domain validation, noisy stdout
breaking pipes).

**How**: Changes span 19 files, +585/-384 lines. Key fixes:
- Domain validation regex added to `_processing.py`, called from all domain-accepting commands
- `PorkbunRegistrar.domain_exists()` added for ownership verification before GitHub deploy
- `GITHUB_PAGES_IPS` moved from porkbun.py to github.py (host owns its own config data)
- Private methods made public: `health_status`, `enable_https_enforcement` (added to Host ABC)
- `check_nameservers` removed from DNSProvider ABC (registrar-only concern)
- DNS verification now shows progress via callback
- Dead code removed: `NSMismatchError`, unused `Domain` model
- `EXIT_GENERAL = 1` added for non-ConfigurationError failures
- `load_config` no longer prints to stdout

**Decisions**: DEC-019 (domain validation at CLI layer), DEC-020 (public provider API for CLI)

**Files**: 19 files changed. See `docs/CODE_REVIEW.md` for full finding list.

---

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

---

## Entry 29: Documentation audit and alignment (2026-03-28)

**What**: Audited all user-facing documentation (README, ARCHITECTURE, TROUBLESHOOTING,
docs/README, LIST_COMMAND) and fixed every reference that was stale after the CLI
redesign and code review.

**Why**: After Phase 7 CLI redesign and 25 code review fixes, docs still described the
old command structure (`list --fix`, `list --dns-check`, `content.py`), referenced
removed classes (`Domain`, `NSMismatchError`), and had wrong test counts and exit codes.

**How**: README.md updated with new command sections (dns check/repair, template apply,
fix https), removed stale flags, corrected architecture diagram. ARCHITECTURE.md fully
rewritten (532 lines) to reflect cli/ package, template repo API, updated ABC signatures.
TROUBLESHOOTING.md updated to point users at `mimeo fix https` and `mimeo dns repair`
instead of removed flags.

**Files**: `README.md`, `docs/ARCHITECTURE.md`, `docs/TROUBLESHOOTING.md`, `docs/README.md`
