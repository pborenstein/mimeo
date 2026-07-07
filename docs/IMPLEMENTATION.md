# Mimeo Implementation Tracker

Living document tracking progress on the domain landing page provisioning tool.

**Last updated**: 2026-03-28

---

## Phase Overview

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 0: Research & Design | Complete | Project setup, API exploration, architecture design |
| Phase 1: Core Infrastructure | Complete | Configuration management, data models, provider abstractions |
| Phase 2: Porkbun Integration | Complete | DNS configuration via Porkbun API |
| Phase 3: GitHub Pages Integration | Complete | Repository creation, Pages setup, custom domains |
| Phase 4: Content Generation | Complete | Simple HTML generator (no template engine) |
| Phase 5: CLI Integration | Complete | Full CLI with create, list, health, fix commands |
| Phase 6: Hardening | Complete | Operational robustness and documentation |
| Phase 7: CLI Redesign | Current | Rethink command structure from first principles |

---

## Current Phase

### Phase 7: CLI Redesign (2026-03-19 - Present)

**Goal**: Rethink `mimeo create` command structure. Current flag set (`--force`,
`--force-dns-update`, `--template`) suggests `create` is doing too much —
conflating provisioning with repair/maintenance.

**Tasks**:

- [x] `--force` flag on `create` to delete/recreate from template
- [x] Set `is_template=true` on all 5 tepiton template repos
- [x] Redesign command structure (provisioning vs repair)
  - [x] Convert `mimeo/cli.py` to `mimeo/cli/` package
  - [x] Extract shared processing utilities into `_processing.py`
  - [x] Add `mimeo dns check` and `mimeo dns repair`
  - [x] Add `mimeo template apply`
  - [x] Add `mimeo fix https`
  - [x] Clean up `create` (remove `--force`, `--force-dns-update`; add `--skip-dns`)
  - [x] Clean up `list` (remove `--fix`, `--dns-check`)
  - [x] Update tests for new module structure + new commands
- [x] Code review with 25 findings addressed (see docs/CODE_REVIEW.md)
  - [x] Fix wrong env var name in config.toml.example
  - [x] Remove phantom --force-dns-update from README
  - [x] Update README project structure to match actual files
  - [x] Add domain validation at CLI entry points
  - [x] Add ownership check via PorkbunRegistrar.domain_exists()
  - [x] Make _health_status and _enable_https_enforcement public API
  - [x] Move GITHUB_PAGES_IPS to github.py
  - [x] Remove check_nameservers from DNSProvider ABC
  - [x] Update Host ABC signature for deploy_site
  - [x] Add DNS propagation progress indication
  - [x] Remove "Loading configuration..." from stdout
  - [x] Remove dead code (NSMismatchError, Domain model)
  - [x] Fix --format shadowing Python builtin
  - [x] Add --workers to fix https command
  - [x] Add EXIT_GENERAL=1 exit code
- [x] Add `mimeo dns show` (raw live records for specific domains)
  - [x] Promote `PorkbunDNSProvider._get_domain_records` to public `get_domain_records`
- [x] Partial results for `registrar list` (per-domain errors, EXIT_PARTIAL, shared clients)
- [ ] Fix 3 failing tests in tests/providers/host/test_github.py (broken by e9830da `_wait_for_repo` change)
- [ ] E2E integration test lane (separate from unit tests, gated, hits real APIs)
- [ ] Template parameterization (substitute domain into template files post-creation)

---

### Phase 6: Hardening (2026-02-17 - 2026-03-19)

**Delivered**:

- `mimeo doctor` preflight command (Python, gh auth/scope, config, NS checks)
- Retry with jitter for transient API failures
- Failure taxonomy and exit codes (config / auth / rate-limit / transient / partial)
- `--workers N` configurable concurrency on `create`
- Config schema versioning and deprecation warnings
- Structured logging (`--log-format json`)
- DNS drift detection (`mimeo list --dns-check`)
- Registrar/DNS/Host three-layer separation
- `--force-dns-update` flag on `create`
- `mimeo registrar list` subcommand
- Replaced content generation with GitHub template repo API
- `--template` flag on `create`

---

## Completed Phases

### Phase 5: CLI Integration (2026-02-14 - 2026-02-16)

**Delivered**:

- `mimeo create <domain> [<domain>...]` — full end-to-end provisioning
  - Concurrent processing via ThreadPoolExecutor (up to 5 workers)
  - `--dry-run`, `--stop-on-error`, `--sequential` flags
  - Idempotent: handles existing repos, duplicate DNS records, HTTPS enforcement
- `mimeo list` — shows all repos tagged with `mimeo` topic
  - `--format text|json|csv` output formats
  - `--health` flag: concurrent Pages API health check per repo
  - `--fix` flag: enables HTTPS for repos with approved certs
  - Tabular text output sorted by severity (problems first)
- 160 tests passing
- Multiple successful E2E deployments: pepito.lol, mellowtimesphere.com, laminar.rodeo

**Key implementation details**:

- `_health_status()` is module-level (exported); used by CLI layer
- `--fix` implies `--health`; fix runs serially after concurrent health fetch
- Health status values: `pages_error`, `no_cert`, `cert_pending`, `fixable`, `healthy`
- Pre-existing mypy/ruff issues in cli.py fixed in Phase 6 (cast + f-string cleanup)

### Phase 4: Content Generation (Complete)

Simple HTML generator with string substitution. Minimal landing pages: dark theme (#1a1a1a / #e0e0e0), domain name with letter spacing, centered flexbox layout. No template engine.

### Phase 3: GitHub Pages Integration (Complete)

`GitHubHost` provider using `gh` CLI. Repository creation, GitHub Actions Pages workflow, custom domain CNAME, HTTPS enforcement. Uses `gh` credential helper for git push auth.

### Phase 2: Porkbun Integration (Complete)

`PorkbunRegistrar` provider. HTTP client with retry. DNS record creation/update (idempotent). Handles apex/subdomain normalization and ALIAS/A record conflicts.

### Phase 1: Core Infrastructure (Complete)

`Config` (TOML + env var loading), `DNSRecord`/`DeployResult` models, `Registrar`/`Host` ABCs, exception hierarchy.

### Phase 0: Research & Design (Complete)

Project scaffold, API research, architecture design, provider abstraction design. Reference implementation: mimeo.lol.

---

## Notes

**Design Principle**: Zero manual steps. `mimeo create domain.com` → live site, no intervention.

**Reference Site**: [mimeo.lol](https://mimeo.lol) / [pborenstein/mimeo.lol](https://github.com/pborenstein/mimeo.lol)

**Future Extensibility**: Provider ABCs support additional registrars (Namecheap, Cloudflare) and hosts (Netlify, Vercel). Template manifest design outlined in docs/CODEX-SPEAKS.md.
