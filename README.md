# Mimeo

Automates the provisioning of landing pages for registered domains. One command takes a domain from nothing to a live GitHub Pages site with custom DNS.

## Quick Start

```bash
git clone https://github.com/pborenstein/mimeo
cd mimeo
uv sync
cp config.toml.example ~/.config/mimeo/config.toml
# edit ~/.config/mimeo/config.toml with your Porkbun API key and GitHub username

mimeo doctor           # verify setup
mimeo create example.com
```

Full setup details (prerequisites, `gh` token scope, global vs. dev install, environment variable overrides) are in [docs/INSTALLATION.md](./docs/INSTALLATION.md).

## What it does

`mimeo create example.com` orchestrates the full workflow:

1. Creates a GitHub repository from a template (default: mimeo.lol)
2. Enables GitHub Pages with a custom domain
3. Configures DNS via Porkbun API (4 A records + CNAME)
4. Enables HTTPS enforcement when the cert is ready

Idempotent: safe to re-run against an existing deployment.

## Global options

```bash
# Emit structured JSON log lines to stderr instead of human-readable text
mimeo --log-format json create example.com
```

`--log-format` accepts `text` (default) or `json`. In JSON mode each diagnostic line is a newline-delimited JSON object with `ts`, `level`, `message`, and optionally `domain`. Result output (tables, JSON arrays) still goes to stdout.

## Commands

**`mimeo doctor`** — check that all prerequisites are met before running any other command:

```bash
mimeo doctor
```

Verifies Python version, `gh` installation, `gh` authentication, `workflow` token scope, and config file validity. Prints a pass/fail result for each check with remediation instructions.

Optionally pass one or more domain names to also check that their nameservers point to Porkbun:

```bash
mimeo doctor example.com another.lol
```

**`mimeo create <domain> [<domain> ...]`** — provision one or more domains:

```bash
# Single domain
mimeo create example.com

# Multiple domains (concurrent by default)
mimeo create example.com another.lol third.com

# Preview without executing
mimeo create example.com --dry-run

# Stop on first failure (default: continue)
mimeo create example.com --stop-on-error

# Run sequentially instead of concurrently
mimeo create example.com another.lol --sequential
```

Multiple domains are processed concurrently (up to 5 workers). Use `--sequential` for verbose per-step output or when debugging.

**`mimeo status <domain> [<domain> ...] | --all`** — one view of the fleet: registration expiry, nameservers, DNS drift, and Pages health per domain, joining the Porkbun account against mimeo-managed repos.

```bash
# Specific domains (quick)
mimeo status example.com another.lol

# Whole fleet: union of registered domains and mimeo repos
# (several API calls per domain -- takes a while on large accounts)
mimeo status --all

# Only domains that need attention
mimeo status --all --problems

# Full detail for scripting
mimeo status --all --format json | jq '.[] | select(.dns_status == "drift")'

# Include the full live DNS records (one extra API call per domain)
mimeo status example.com --with-dns
mimeo status --all --with-dns --format json > fleet.json
```

A bare `mimeo status` refuses to run: the fleet sweep is slow, so it requires the explicit `--all`. Registered domains with no site show `no repo`; sites whose domain is not in the Porkbun account show `-` on the registrar side. The DNS column is `-` when there is no repo (no desired state to compare against). Drift and unhealthy sites are findings (exit 0); API errors exit nonzero with partial results.

**`mimeo sync <domain> [<domain> ...] | --all`** — converge domains on their desired state: apply missing DNS records and enable HTTPS enforcement when the certificate is ready.

```bash
# Preview fleet-wide changes first
mimeo sync --all --dry-run

# Converge the whole fleet (explicit --all required)
mimeo sync --all

# Specific domains
mimeo sync example.com another.lol

# Also reset nameservers that point elsewhere
mimeo sync example.com --reset-nameservers
```

Sync will not create repositories (`mimeo create`), change content (`mimeo create --force`), or delete DNS records it does not manage, and it only touches nameservers with `--reset-nameservers`. A bare `mimeo sync` refuses to run: fleet-wide convergence requires the explicit `--all`.

**`mimeo status --source github`** (site inventory) — show all mimeo-managed sites (repos tagged with the `mimeo` topic):

```bash
# Human-readable table
mimeo status --all --source github

# JSON output
mimeo status --all --source github --format json

# CSV output
mimeo status --all --source github --format csv

# Include GitHub Pages health status
mimeo status --all --source github --health

# Include the template each site was created from
mimeo status --all --source github --show-template
```

Health status values: `healthy`, `fixable`, `cert_pending`, `no_cert`, `pages_error`.
Output is sorted by severity (problems first) when `--health` is given.

**`mimeo status --source porkbun`** (registrar inventory) — list all domains in the Porkbun account, regardless of whether mimeo manages them:

```bash
# Human-readable table (domain, expiry, NS status)
mimeo status --all --source porkbun

# JSON output — pipeable
mimeo status --all --source porkbun --format json

# CSV output
mimeo status --all --source porkbun --format csv

# Include DNS records per domain (doubles API calls)
mimeo status --all --source porkbun --with-dns

# Adjust concurrency (default 5)
mimeo status --all --source porkbun --workers 10
```

Output fields: `domain`, `tld`, `expires`, `auto_renew`, `ns_ok` (whether NS points to Porkbun), `nameservers`.

```bash
# Check which domains are not pointing to Porkbun
mimeo status --all --source porkbun --format json | jq '.[] | select(.ns_ok == false) | .domain'

# Export full domain inventory to CSV
mimeo status --all --source porkbun --format csv --with-dns > inventory.csv
```

**`mimeo status --source dns`** (raw records / drift) — show live DNS records for named domains, or drift against what GitHub Pages expects:

```bash
# Raw live records
mimeo status example.com --source dns

# Drift only (missing/extra vs. expected)
mimeo status example.com --source dns --problems
```

`--source dns` has no fleet-wide mode; it always takes explicit domain names. Repairing missing records and enabling HTTPS enforcement are both part of `mimeo sync` (see above). Replacing repository content with a different template is `mimeo create --force` (see above).

## Architecture overview

```
mimeo create example.com
        |
        +--> GitHub Pages (gh CLI)
        |      create repo from template
        |      enable Pages, set custom domain
        |      attempt HTTPS enforcement
        |
        +--> DNS (Porkbun API)
               4 A records (185.199.108-111.153)
               www CNAME (user.github.io)
```

The tool uses provider abstractions (`Registrar`, `Host` ABCs) that allow adding new registrars and hosts without changing the core orchestration. See [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) for full component diagrams and data flows.

## Validation

```bash
uv sync --frozen && uv run pytest && uv run ruff check mimeo && uv run mypy mimeo
```

294 tests. Linting and type checking are expected to be clean.

## Project structure

```
mimeo/
├── mimeo/
│   ├── cli/
│   │   ├── __init__.py                 # Command group registration
│   │   ├── _processing.py              # Shared concurrent processing + output helpers
│   │   ├── create.py                   # Create command (absorbs template apply)
│   │   ├── status.py                   # Status command (absorbs list, registrar list,
│   │   │                                  dns show, dns check)
│   │   ├── sync.py                     # Sync command (absorbs dns repair, fix https)
│   │   └── doctor.py                   # Doctor command
│   ├── config.py                       # Config loading (~/.config/mimeo/config.toml)
│   ├── exceptions.py                   # Exception hierarchy + exit codes
│   ├── models.py                       # DNSRecord, NameserverCheckResult
│   ├── providers/
│   │   ├── base.py                     # Registrar / DNSProvider / Host ABCs
│   │   ├── registrar/porkbun.py        # Porkbun registrar + DNS provider
│   │   └── host/github.py             # GitHub Pages automation (via gh CLI)
│   └── utils/
│       ├── http.py                     # requests.Session with error handling
│       └── retry.py                    # retry_with_jitter() for transient errors
├── tests/
├── scripts/                            # Smoke tests and utilities
├── docs/
│   ├── README.md                       # Documentation index
│   ├── INSTALLATION.md                 # Prerequisites, install, configuration
│   ├── ARCHITECTURE.md                 # Component map and workflow diagrams
│   ├── TROUBLESHOOTING.md              # Failure diagnosis by category
│   ├── IMPLEMENTATION.md               # Phase tracker
│   ├── DECISIONS.md                    # Architectural decisions
│   └── chronicles/                     # Session history
└── pyproject.toml
```

## Documentation

| Document | Purpose |
|:---------|:--------|
| [docs/INSTALLATION.md](./docs/INSTALLATION.md) | Prerequisites, install, configuration |
| [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) | Component map, data flows, workflow diagrams |
| [docs/TROUBLESHOOTING.md](./docs/TROUBLESHOOTING.md) | Failure diagnosis and remediation |
| [docs/DECISIONS.md](./docs/DECISIONS.md) | Architectural decision registry |
| [docs/IMPLEMENTATION.md](./docs/IMPLEMENTATION.md) | Phase tracker and task status |

## Known limitations

- Only supports Porkbun (registrar) and GitHub Pages (host). Provider abstraction is in place for future additions.
- DNS propagation is not polled after configuration -- run `mimeo status` afterwards to confirm records have propagated.

## Development

See [docs/INSTALLATION.md](./docs/INSTALLATION.md) for dev setup, and [CLAUDE.md](./CLAUDE.md) for coding standards, testing, and git workflow.

See [docs/DECISIONS.md](./docs/DECISIONS.md) for architectural decisions.
