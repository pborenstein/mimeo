# Mimeo

Automates the provisioning of landing pages for registered domains. One command takes a domain from nothing to a live GitHub Pages site with custom DNS.

## Quick Start

```bash
git clone https://github.com/pborenstein/mimeo
cd mimeo
uv sync
cp config.toml.example ~/.config/mimeo/config.toml
# edit ~/.config/mimeo/config.toml with your Porkbun API key and GitHub username

uv run mimeo doctor     # verify setup
uv run mimeo create example.com
```

Full setup details (prerequisites, `gh` token scope, global vs. dev install, environment variable overrides) are in [docs/INSTALLATION.md](./docs/INSTALLATION.md).

## What it does

`mimeo create example.com` orchestrates the full workflow:

1. Creates a GitHub repository from a template (default: `mimeo`)
2. Enables GitHub Pages with a custom domain
3. Configures DNS via Porkbun API (4 A records + CNAME)
4. Enables HTTPS enforcement when the cert is ready

Idempotent: safe to re-run against an existing deployment.

## Global options

These options go before the subcommand and apply to every command.

| Option | Effect | Default |
|:-------|:-------|:--------|
| `--log-format text` <br> `--log-format json` | Log format for diagnostic output on stderr | `text` |
| `--template-org ORG` | Org holding template repositories | `github.template_org` (`tepiton`) |
| `--deploy-org ORG` | GitHub user/org where site repositories are created | `github.default_org` (required) |

Templates and sites live in different places: the template org holds the repositories `create` copies from, while the deploy org — usually your username — is where new site repositories land. The two need not match; pass `--template-org` or `--deploy-org` to override either for a single invocation:

```bash
mimeo --log-format json create example.com
mimeo --template-org mytemplates --deploy-org myorg create example.com
```

Precedence: CLI flags > `MIMEO_*` environment variables > config file.

In JSON log mode each diagnostic line is a newline-delimited JSON object with `ts`, `level`, `message`, and optionally `domain`. Result output (tables, JSON arrays) still goes to stdout.

## Commands

### doctor

Checks that all prerequisites are met before running any other command: Python version, `gh` installation, `gh` authentication, `workflow` token scope, and config file validity. Each check prints a pass/fail result with remediation instructions. Passing domain names also checks that their nameservers point to Porkbun.

| Task | Command |
|:-----|:--------|
| Run all checks | `mimeo doctor` |
| Also check nameservers for specific domains | `mimeo doctor example.com another.lol` |

### create

Provisions one or more domains end to end. Templates are looked up in the template org (see [Global options](#global-options)); the default template is `mimeo`. Multiple domains are processed concurrently (up to 5 workers); use `--sequential` for verbose per-step output or when debugging.

| Task | Command |
|:-----|:--------|
| Provision a single domain | `mimeo create example.com` |
| Provision several domains concurrently | `mimeo create example.com another.lol third.com` |
| Preview without executing | `mimeo create example.com --dry-run` |
| Run sequentially with per-step output | `mimeo create example.com another.lol --sequential` |
| Use a specific template | `mimeo create example.com --template pandoc-simple` |
| Create repo and Pages only; configure DNS separately | `mimeo create example.com --skip-dns` |
| Replace an existing site with a different template | `mimeo create example.com --template new-theme --force` |
| Same, without the confirmation prompt | `mimeo create example.com --template new-theme --force --yes` |

If a repository already exists, `create` leaves it unchanged (safe to re-run). `--force` instead replaces an existing repository's content with the template: it **deletes and recreates the repo**, so all existing content, issues, and history are lost, and managed DNS records are deleted and recreated as well. Pass `--skip-dns` alongside `--force` to leave DNS untouched. `--force` prompts for confirmation unless `--yes` is passed.

### status

One view of the fleet: registration expiry, nameservers, DNS drift, and Pages health per domain, joining the Porkbun account against mimeo-managed repos.

| Task | Command |
|:-----|:--------|
| Check specific domains (quick) | `mimeo status example.com another.lol` |
| Whole fleet: union of registered domains and mimeo repos | `mimeo status --all` |
| Only domains that need attention | `mimeo status --all --problems` |
| Full detail for scripting | `mimeo status --all --format json \| jq '.[] \| select(.dns_status == "drift")'` |
| Include the full live DNS records | `mimeo status example.com --with-dns` |

A bare `mimeo status` refuses to run: the fleet sweep makes several API calls per domain and is slow on large accounts, so it requires the explicit `--all`.

Registered domains with no site show `no repo`; sites whose domain is not in the Porkbun account show `-` on the registrar side. The DNS column is `-` when there is no repo (no desired state to compare against). Drift and unhealthy sites are findings (exit 0); API errors exit nonzero with partial results.

`--source` narrows the report to a single provider instead of the cross-provider join.

#### --source github

Site inventory: all mimeo-managed sites, i.e. repos tagged with the `mimeo` topic.

| Task | Command |
|:-----|:--------|
| Human-readable table | `mimeo status --all --source github` |
| JSON output | `mimeo status --all --source github --format json` |
| CSV output | `mimeo status --all --source github --format csv` |
| Include Pages health | `mimeo status --all --source github --health` |
| Include the template each site was created from | `mimeo status --all --source github --show-template` |

With `--health`, each site is classified as `healthy`, `fixable`, `cert_pending`, `no_cert`, or `pages_error`, and output is sorted by severity (problems first).

#### --source porkbun

Registrar inventory: all domains in the Porkbun account, regardless of whether mimeo manages them. Output fields: `domain`, `tld`, `expires`, `auto_renew`, `ns_ok` (whether NS points to Porkbun), `nameservers`. `--with-dns` includes each domain's live DNS records (doubles the API calls).

| Task | Command |
|:-----|:--------|
| Human-readable table | `mimeo status --all --source porkbun` |
| JSON output | `mimeo status --all --source porkbun --format json` |
| Full inventory to CSV | `mimeo status --all --source porkbun --format csv --with-dns > inventory.csv` |
| Which domains do not point at Porkbun | `mimeo status --all --source porkbun --format json \| jq '.[] \| select(.ns_ok == false) \| .domain'` |
| Adjust concurrency | `mimeo status --all --source porkbun --workers 10` (default 5) |

#### --source dns

Live DNS records for named domains, or the drift against what GitHub Pages expects. Unlike the other sources, `--source dns` has no fleet-wide mode; it always takes explicit domain names. Repairing missing records and enabling HTTPS enforcement are both part of `mimeo sync`; replacing repository content with a different template is `mimeo create --force`.

| Task | Command |
|:-----|:--------|
| Raw live records | `mimeo status example.com --source dns` |
| Drift only (missing/extra vs. expected) | `mimeo status example.com --source dns --problems` |

### sync

Converges domains on their desired state: applies missing DNS records and enables HTTPS enforcement when the certificate is ready. It will not create repositories (`mimeo create`), change content (`mimeo create --force`), or delete DNS records it does not manage, and it only touches nameservers with `--reset-nameservers`.

| Task | Command |
|:-----|:--------|
| Preview fleet-wide changes first | `mimeo sync --all --dry-run` |
| Converge the whole fleet | `mimeo sync --all` |
| Converge specific domains | `mimeo sync example.com another.lol` |
| Also reset nameservers that point elsewhere | `mimeo sync example.com --reset-nameservers` |

A bare `mimeo sync` refuses to run: fleet-wide convergence requires the explicit `--all`.

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

## Development

```bash
uv sync --frozen && uv run pytest && uv run ruff check mimeo && uv run mypy mimeo
```

361 tests. Linting and type checking are expected to be clean. See [docs/INSTALLATION.md](./docs/INSTALLATION.md) for development setup.

## Project structure

```
mimeo/
├── mimeo/
│   ├── cli/                  # doctor, create, status, sync commands
│   ├── providers/            # Registrar / DNSProvider / Host abstractions; Porkbun, GitHub Pages
│   ├── utils/                # HTTP session with error handling, retry with jitter
│   ├── config.py             # Config loading (~/.config/mimeo/config.toml)
│   ├── models.py             # DNSRecord, NameserverCheckResult
│   └── exceptions.py         # Exception hierarchy + exit codes
├── tests/
├── scripts/                  # Smoke tests and utilities
└── docs/
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
