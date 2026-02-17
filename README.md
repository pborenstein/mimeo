# Mimeo

Automates the provisioning of landing pages for registered domains. One command takes a domain from nothing to a live GitHub Pages site with custom DNS.

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
[providers.porkbun]
api_key = "pk1_..."
api_secret = "sk1_..."

[providers.github]
username = "your-github-username"
```

## Commands

### `mimeo create <domain> [<domain> ...]`

Provision one or more domains:

```bash
# Single domain
mimeo create example.com

# Multiple domains
mimeo create example.com another.lol third.com

# Preview without executing
mimeo create example.com --dry-run

# Stop on first failure (default: continue)
mimeo create example.com --stop-on-error

# Run sequentially instead of concurrently
mimeo create example.com another.lol --sequential
```

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
```

Health status values: `healthy`, `fixable`, `cert_pending`, `no_cert`, `pages_error`.
Output is sorted by severity (problems first).

See [docs/LIST_COMMAND.md](./docs/LIST_COMMAND.md) for detailed format reference and scripting examples.

## Validation

```bash
uv sync --frozen && uv run pytest && uv run ruff check mimeo && uv run mypy mimeo
```

160 tests. Linting and type checking are expected to be clean (one pre-existing mypy warning in cli.py for a heterogeneous dict).

## Project structure

```
mimeo/
├── mimeo/
│   ├── cli.py                          # CLI entry point (Click)
│   ├── config.py                       # Config loading (~/.config/mimeo/config.toml)
│   ├── content.py                      # Landing page HTML generation
│   ├── exceptions.py                   # Exception hierarchy
│   ├── models.py                       # Domain, DNSRecord, DeployResult
│   └── providers/
│       ├── base.py                     # Registrar / Host ABCs
│       ├── registrar/porkbun.py        # Porkbun DNS API
│       └── host/github.py             # GitHub Pages automation (via gh CLI)
├── tests/
├── docs/
│   ├── CONTEXT.md                      # Current session state
│   ├── IMPLEMENTATION.md               # Phase tracker
│   ├── DECISIONS.md                    # Architectural decisions
│   ├── LIST_COMMAND.md                 # list command reference
│   └── chronicles/                     # Session history
└── pyproject.toml
```

## Known limitations

- Only supports Porkbun (registrar) and GitHub Pages (host). Provider abstraction is in place for future additions.
- No reconciliation command yet — partial failures (e.g., DNS configured but Pages not ready) require manual inspection or re-running `create`.
- DNS propagation is not verified after configuration; the tool configures records and moves on.
- No preflight check (`mimeo doctor`) — misconfigured `gh` auth or missing config surfaces at runtime.

## Development

See [CLAUDE.md](./CLAUDE.md) for session workflow and coding standards.

See [docs/DECISIONS.md](./docs/DECISIONS.md) for architectural decisions.
