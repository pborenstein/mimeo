# Mimeo Implementation Tracker

Living document tracking progress on the domain landing page provisioning tool.

**Last updated**: 2026-02-18

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
| Phase 6: Hardening | Current | Operational robustness and documentation |

---

## Current Phase

### Phase 6: Hardening (2026-02-17 - Present)

**Goal**: Make the tool dependable and maintainable. Any operator can run one command and know what happened, what failed, and how to fix it.

**Tasks**:

- [x] Add `mimeo doctor` preflight command (Python version, gh auth/scope, config validity)
- [x] Add retry with jitter for transient API failures
- [x] Improve failure taxonomy and exit codes (config / auth / rate-limit / transient / partial)
- [x] Add `--workers N` option to `create` for configurable concurrency
- [x] Config schema versioning and deprecation warnings (`schema_version = 1`)
- [x] Structured logging option (`--log-format json`) on main group
- [x] DNS drift detection (`mimeo list --dns-check` via Porkbun API)
- [x] Registrar/DNS/Host three-layer separation (`DNSProvider` ABC, `PorkbunDNSProvider`, NS check gate)
- [x] `mimeo doctor [domain...]` NS verification for domains
- [ ] E2E integration test lane (separate from unit tests, gated, hits real APIs)
- [x] Refresh README to current state
- [x] Document workflow scope requirement
- [x] Document `uv tool install` for global CLI access

**Success Criteria**:

- `mimeo doctor` catches misconfiguration before any API calls
- Partial failure leaves a clear repair path
- All error messages include actionable remediation

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

`Config` (TOML + env var loading), `Domain`/`DNSRecord`/`DeployResult` models, `Registrar`/`Host` ABCs, exception hierarchy.

### Phase 0: Research & Design (Complete)

Project scaffold, API research, architecture design, provider abstraction design. Reference implementation: mimeo.lol.

---

## Notes

**Design Principle**: Zero manual steps. `mimeo create domain.com` → live site, no intervention.

**Reference Site**: [mimeo.lol](https://mimeo.lol) / [pborenstein/mimeo.lol](https://github.com/pborenstein/mimeo.lol)

**Future Extensibility**: Provider ABCs support additional registrars (Namecheap, Cloudflare) and hosts (Netlify, Vercel). Template manifest design outlined in docs/CODEX-SPEAKS.md.
