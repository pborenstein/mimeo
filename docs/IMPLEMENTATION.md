# Mimeo Implementation Tracker

Living document tracking progress on the domain landing page provisioning tool.

**Last updated**: 2026-07-06

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
| Phase 7: CLI Redesign | Complete | Rethink command structure from first principles |
| Phase 8: Consolidation | Current | Collapse verb sprawl into status/sync, unify CLI plumbing |

---

## Current Phase

### Phase 8: Consolidation (2026-07-06 - Present)

**Goal**: Reverse barnacleization. Mimeo is a fleet manager for
domain-to-GitHub-Pages sites, not a "website generator." Collapse the
per-incident verb sprawl (`dns repair`, `fix https`, `template apply`) into
declarative `status`/`sync`, unify the duplicated CLI fan-out plumbing, and
add E2E coverage. The tool should end this phase smaller, with fewer
front-door verbs than it started with. See DEC-021.

**Tasks**:

- [x] Stage 1: Shared domain-operation engine (debt paydown, no behavior change)
  - [x] Extend `_processing.py` into one fan-out engine: `map_items` (ordered
        partial results, exceptions become error rows), `render_results`
        (text/json/csv dispatch), `exit_on_errors` (partial -> EXIT_PARTIAL,
        total -> category code)
  - [x] Migrate `registrar list`, `dns check`, `dns show`, `fix https`,
        and `list` onto it (four hand-rolled thread pools removed; three of
        them crashed entirely on one bad future.result())
  - [x] Measure: command files shrank ~65 lines but the engine added ~110,
        so cli/ net +51 lines; the payoff is structural (one pool, one
        dispatch) and compounds when status/sync build on it
  - [ ] Follow-up: fold `process_domains_concurrent` (create, dns repair,
        template apply) into `map_items` — the remaining duplicate pool
- [x] Stage 2: `mimeo status [DOMAINS...]` — the cross-provider join
  - [x] One table joining Porkbun domains x GitHub repos x DNS drift x
        Pages health (DOMAIN / EXPIRES / NS / DNS / SITE + summary line)
  - [x] Surface the diff: no-arg mode covers the union of both sides;
        domains without sites show "no repo", sites without domains show
        "-" on the registrar side; `--problems` filters to what needs
        attention
  - [x] Subsumes the `registrar list --with-dns` full-sweep use case
  - Note: DNS column is "-" when no repo exists (no desired state to
    compare); drift/unhealthy are findings (exit 0), API errors are
    failures (EXIT_PARTIAL)
- [ ] Stage 3: `mimeo sync [DOMAINS...]` — converge on desired state
  - [ ] One pass that applies whatever `status` flags: DNS repair + HTTPS
        enforcement (template apply stays manual — content is a choice,
        not drift)
  - [ ] `--dry-run` previews planned actions; partial-failure exit codes
  - [ ] Decide fate of `dns repair` / `fix https`: keep as plumbing,
        alias, or deprecate
- [ ] Stage 4: E2E integration test lane (separate from unit tests, gated,
      hits real APIs; `create`/`status`/`sync` are the flows worth covering)
- [ ] Identity fix: replace "A tool to generate websites quickly" with
      "Provision and manage custom-domain sites on GitHub Pages"
      (CLI help, README, pyproject description)
- [ ] Carried from Phase 7: template parameterization (substitute domain
      into template files post-creation)

---

### Phase 7: CLI Redesign (2026-03-19 - 2026-07-06)

**Delivered**:

- `mimeo/cli/` package with task-oriented command groups (DEC-018)
- `dns check` / `dns repair` / `dns show`, `template apply`, `fix https`,
  `registrar list`
- `create` and `list` stripped to single responsibilities
  (removed `--force`, `--force-dns-update`, `--fix`, `--dns-check`)
- Domain validation at CLI entry points (DEC-019); public provider methods
  for CLI-facing operations (DEC-020)
- 25 code-review findings fixed; full documentation realignment
- Race condition fix: `_wait_for_repo()` after template generate
- Partial results for `registrar list` (per-domain errors, EXIT_PARTIAL,
  shared HTTP clients)
- 243 tests passing; mypy and ruff clean

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
