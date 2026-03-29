# Mimeo

Automates the provisioning of landing pages for registered domains. One command takes a domain from nothing to a live GitHub Pages site with custom DNS.

## Quick Start

```bash
# 1. Install
git clone https://github.com/pborenstein/mimeo
cd mimeo
uv sync

# 2. Configure
mkdir -p ~/.config/mimeo
cp config.toml.example ~/.config/mimeo/config.toml
# Edit ~/.config/mimeo/config.toml with your Porkbun API key and GitHub username

# 3. Authenticate GitHub CLI with workflow scope
gh auth login --scopes workflow

# 4. Verify setup
mimeo doctor

# 5. Provision a domain
mimeo create example.com
```

## What it does

`mimeo create example.com` orchestrates the full workflow:

1. Generates a minimal landing page (dark theme, domain name centered)
2. Creates a GitHub repository for the domain
3. Pushes content with a GitHub Actions Pages workflow
4. Configures DNS via Porkbun API (4 A records + CNAME)
5. Enables HTTPS enforcement when the cert is ready

Idempotent: safe to re-run against an existing deployment.

## Prerequisites

- Python >=3.11
- [uv](https://github.com/astral-sh/uv) — package manager
- [gh](https://cli.github.com/) — GitHub CLI, authenticated (`gh auth login`)
- Porkbun API key and secret
- GitHub account configured in `gh`

### GitHub token scope requirement

The `gh` token must have the `workflow` scope to push the GitHub Actions workflow file. Re-authenticate with the correct scope if needed:

```bash
gh auth login --scopes workflow
```

## Installation

### Development (from source)

```bash
git clone https://github.com/pborenstein/mimeo
cd mimeo
uv sync
uv run mimeo --help
```

### Global CLI install

```bash
uv tool install .
mimeo --help
```

## Configuration

Create `~/.config/mimeo/config.toml`:

```toml
[porkbun]
api_key = "pk1_..."
secret_key = "sk1_..."

[github]
default_org = "your-github-username"
```

See [config.toml.example](./config.toml.example) for the full annotated template including environment variable overrides.

### Environment variable overrides

All settings can be provided via environment variables (take precedence over the config file):

```bash
export MIMEO_PORKBUN_API_KEY="pk1_..."
export MIMEO_PORKBUN_SECRET="sk1_..."
export MIMEO_GITHUB_USERNAME="your-username"
```

## Global options

```bash
# Emit structured JSON log lines to stderr instead of human-readable text
mimeo --log-format json create example.com
```

`--log-format` accepts `text` (default) or `json`. In JSON mode each diagnostic line is a newline-delimited JSON object with `ts`, `level`, `message`, and optionally `domain`. Result output (tables, JSON arrays) still goes to stdout.

## Commands

### `mimeo doctor`

Check that all prerequisites are met before running any other command:

```bash
mimeo doctor
```

Verifies Python version, `gh` installation, `gh` authentication, `workflow` token scope, and config file validity. Prints a pass/fail result for each check with remediation instructions.

Optionally pass one or more domain names to also check that their nameservers point to Porkbun:

```bash
mimeo doctor example.com another.lol
```

### `mimeo create <domain> [<domain> ...]`

Provision one or more domains:

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

# Reset nameservers to Porkbun and configure DNS even if NS points elsewhere
mimeo dns repair example.com --reset-nameservers
```

Multiple domains are processed concurrently (up to 5 workers). Use `--sequential` for verbose per-step output or when debugging.

### `mimeo list`

Show all mimeo-managed sites (repos tagged with the `mimeo` topic):

```bash
# Human-readable table
mimeo list

# JSON output
mimeo list --format json

# CSV output
mimeo list --format csv

# Include GitHub Pages health status
mimeo list --health

# Fix HTTPS enforcement for sites with approved certs
mimeo list --fix

# Check DNS records for drift against expected configuration
mimeo list --dns-check
```

Health status values: `healthy`, `fixable`, `cert_pending`, `no_cert`, `pages_error`.
Output is sorted by severity (problems first).

See [docs/LIST_COMMAND.md](./docs/LIST_COMMAND.md) for detailed format reference and scripting examples.

### `mimeo registrar list`

List all domains in the Porkbun account — regardless of whether mimeo manages them:

```bash
# Human-readable table (domain, expiry, NS status)
mimeo registrar list

# JSON output — pipeable
mimeo registrar list --format json

# CSV output
mimeo registrar list --format csv

# Include DNS records per domain (doubles API calls)
mimeo registrar list --with-dns

# Adjust concurrency (default 5)
mimeo registrar list --workers 10
```

Output fields: `domain`, `tld`, `expires`, `auto_renew`, `ns_ok` (whether NS points to Porkbun), `nameservers`.

```bash
# Check which domains are not pointing to Porkbun
mimeo registrar list --format json | jq '.[] | select(.ns_ok == false) | .domain'

# Export full domain inventory to CSV
mimeo registrar list --format csv --with-dns > inventory.csv
```

## Architecture overview

```
mimeo create example.com
        |
        +--> Generate content (tempdir)
        |      index.html, static.yml, README.md
        |
        +--> GitHub Pages (gh CLI)
        |      create repo, push content
        |      enable Pages, set custom domain
        |      attempt HTTPS enforcement
        |
        +--> DNS (Porkbun API)
               4 A records (185.199.108-111.153)
               www CNAME (user.github.io)
               verify propagation
```

The tool uses provider abstractions (`Registrar`, `Host` ABCs) that allow adding new registrars and hosts without changing the core orchestration. See [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) for full component diagrams and data flows.

## Validation

```bash
uv sync --frozen && uv run pytest && uv run ruff check mimeo && uv run mypy mimeo
```

258 tests. Linting and type checking are expected to be clean.

## Project structure

```
mimeo/
├── mimeo/
│   ├── cli.py                          # CLI entry point (Click)
│   ├── cli/
│   │   ├── __init__.py                 # Command group registration
│   │   ├── _processing.py              # Shared concurrent processing + output helpers
│   │   ├── create.py                   # Create command
│   │   ├── list_cmd.py                 # List command
│   │   ├── doctor.py                   # Doctor command
│   │   ├── registrar.py                # Registrar list command
│   │   ├── dns.py                      # DNS check/repair commands
│   │   ├── fix.py                      # Fix https command
│   │   └── template.py                 # Template apply command
│   ├── config.py                       # Config loading (~/.config/mimeo/config.toml)
│   ├── exceptions.py                   # Exception hierarchy + exit codes
│   ├── models.py                       # Domain, DNSRecord, NameserverCheckResult
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
│   ├── ARCHITECTURE.md                 # Component map and workflow diagrams
│   ├── TROUBLESHOOTING.md              # Failure diagnosis by category
│   ├── LIST_COMMAND.md                 # list command reference
│   ├── IMPLEMENTATION.md               # Phase tracker
│   ├── DECISIONS.md                    # Architectural decisions
│   └── chronicles/                     # Session history
└── pyproject.toml
```

## Documentation

| Document | Purpose |
|:---------|:--------|
| [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) | Component map, data flows, workflow diagrams |
| [docs/TROUBLESHOOTING.md](./docs/TROUBLESHOOTING.md) | Failure diagnosis and remediation |
| [docs/LIST_COMMAND.md](./docs/LIST_COMMAND.md) | `list` command format reference and scripting |
| [docs/DECISIONS.md](./docs/DECISIONS.md) | Architectural decision registry |
| [docs/IMPLEMENTATION.md](./docs/IMPLEMENTATION.md) | Phase tracker and task status |
| [CONTRIBUTING.md](./CONTRIBUTING.md) | Development setup, code style, PR process |

## Known limitations

- Only supports Porkbun (registrar) and GitHub Pages (host). Provider abstraction is in place for future additions.
- DNS propagation is verified after configuration (up to 10 attempts, 50 seconds), but the site is marked successful regardless of propagation status.

## Development

See [CONTRIBUTING.md](./CONTRIBUTING.md) for development setup, coding standards, and PR process.

See [docs/DECISIONS.md](./docs/DECISIONS.md) for architectural decisions.

See [CLAUDE.md](./CLAUDE.md) for AI-assisted session workflow.
