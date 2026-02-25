# Architecture

## Overview

Mimeo is a CLI tool that automates the full provisioning pipeline for static landing pages: content generation, GitHub repository setup, GitHub Pages configuration, and DNS configuration at Porkbun. One command takes a domain from nothing to a live HTTPS site.

The tool is structured around a provider abstraction that separates the registrar (DNS) and host (deployment) concerns. The current implementation supports Porkbun as the registrar and GitHub Pages as the host. The abstractions allow adding other providers without changing the core orchestration logic.

## Component Map

```
mimeo/
├── cli.py              Command-line interface (Click)
│                         create, list, doctor subcommands
│                         registrar list subcommand
│                         ThreadPoolExecutor for concurrent provisioning
│                         --log-format {text|json} global option
│
├── config.py           Configuration loader
│                         TOML file: ~/.config/mimeo/config.toml
│                         Environment variable overrides: MIMEO_*
│
├── models.py           Data models
│                         Domain, DNSRecord, NameserverCheckResult
│
├── content.py          Content generator
│                         index.html (dark theme, domain name centered)
│                         .github/workflows/static.yml (GitHub Actions)
│                         README.md
│
├── exceptions.py       Exception hierarchy + exit codes
│                         EXIT_OK=0, EXIT_CONFIG=2, EXIT_AUTH=3
│                         EXIT_RATE_LIMIT=4, EXIT_TRANSIENT=5, EXIT_PARTIAL=6
│                         MimeoError
│                           ConfigurationError
│                           ProviderError
│                             RegistrarError
│                               NSMismatchError
│                             HostError
│                           DNSError
│                           NetworkError
│                           APIError (status_code attribute)
│
├── providers/
│   ├── base.py         Abstract base classes
│   │                     Registrar ABC: check_nameservers, update_nameservers, list_domains
│   │                     DNSProvider ABC: configure_dns, verify_dns, check_nameservers
│   │                     Host ABC: deploy_site -> DeployResult, required_dns_records
│   │                     DeployResult dataclass: url, repo_created, https_enabled
│   │
│   ├── registrar/
│   │   └── porkbun.py  Porkbun registrar + DNS provider
│   │                     PorkbunRegistrar: list_domains, check_nameservers, update_nameservers
│   │                     PorkbunDNSProvider: configure_dns, verify_dns, check_nameservers
│   │                     HTTP calls to api-ipv4.porkbun.com/api/json/v3
│   │                     configure_dns: delete conflicts, create records
│   │                     verify_dns: poll with dnspython
│   │
│   └── host/
│       └── github.py   GitHub Pages provider
│                         gh CLI for API calls and git authentication
│                         Repository creation, Pages enable, custom domain
│                         HTTPS enforcement (requires approved cert)
│
└── utils/
    ├── http.py         HTTP client
    │                     requests.Session with retry strategy
    │                     Retries on 429, 5xx with exponential backoff
    └── retry.py        Retry with exponential backoff and jitter
                          retry_with_jitter(): retries on transient errors
                          Retryable: APIError (429/5xx), NetworkError, transient HostError
```

## Provider Abstractions

`providers/base.py` defines three ABCs separating registrar, DNS, and host concerns:

```
Registrar (ABC)                    DNSProvider (ABC)
─────────────────────────          ──────────────────────────────
check_nameservers(domain)          configure_dns(domain, records)
  -> NameserverCheckResult         verify_dns(domain, records)
update_nameservers(domain)         check_nameservers(domain)
list_domains()                       -> NameserverCheckResult
        │                                      │
        ▼                                      ▼
PorkbunRegistrar              PorkbunDNSProvider
(porkbun.py)                  (porkbun.py)

Host (ABC)
──────────────────────────────────────
deploy_site(domain, path) -> DeployResult
  DeployResult: url, repo_created, https_enabled
required_dns_records(domain) -> list[DNSRecord]
        │
        ▼
GitHubHost
(github.py)
```

New providers implement these interfaces. The CLI orchestration in `cli.py` calls only the abstract methods, so new implementations slot in without touching the core flow.

`NameserverCheckResult` (in `models.py`) carries `ok: bool`, `actual: list[str]`, `expected: list[str]`.

## Create Workflow

The `mimeo create <domain>` command orchestrates stages in sequence per domain:

```
mimeo create example.com [--force-dns-update]
        │
        ▼
Load Config
(~/.config/mimeo/config.toml or env vars)
        │
        ▼
Generate Site Content (tempdir)
  index.html        dark theme, domain name centered
  static.yml        GitHub Actions Pages workflow
  README.md         minimal
        │
        ▼
Deploy to GitHub Pages (GitHubHost)
  ┌── repo exists? ─── yes ──► skip push
  │                              │
  no                             │
  │                              │
  ▼                              ▼
  create repo               enable Pages
  push content              set custom domain
  tag: mimeo                try HTTPS enforcement
  tag: landing-page               │
  tag: github-pages               │
        └──────────────────────────┘
                   │
                   ▼
         DeployResult
         url, repo_created, https_enabled
                   │
                   ▼
Check Nameservers (PorkbunRegistrar)
  ns_ok? ── no + --force-dns-update ──► update_nameservers()
  ns_ok? ── no (no flag) ──► warn, skip DNS config
                   │
                   ▼
Configure DNS (PorkbunDNSProvider)
  retrieve existing records
  delete conflicting records (by type + name)
  create 4 A records (185.199.108-111.153)
  create www CNAME (user.github.io)
                   │
                   ▼
Verify DNS propagation
  poll with dnspython
  up to 10 attempts, 5s delay
  returns True/False (does not block success)
                   │
                   ▼
Report result: url, https_pending, dns_pending
```

### Concurrency

Multiple domains use `ThreadPoolExecutor` with up to 5 workers:

```
mimeo create a.com b.com c.com
        │
        ├─► worker 1: a.com ────► complete
        ├─► worker 2: b.com ────► complete
        └─► worker 3: c.com ────► complete
                   │
        collect results in original order
                   │
        print summary
```

Single domains and `--dry-run` always run sequentially with verbose per-step output. Concurrent mode suppresses per-step output to prevent garbled interleaving; each domain prints a single completion line.

## List and Health Workflow

`mimeo list` enumerates repositories tagged with the `mimeo` topic:

```
mimeo list [--health] [--fix] [--dns-check]
        │
        ▼
gh search repos user:<owner> topic:mimeo
        │
        ▼
normalize: name, repository URL, site URL, updated date
        │
        ├── (no --health) ──► sort by name ──► display
        │
        ├── (--dns-check) ──► check DNS records against expected
        │                      PorkbunDNSProvider.check_nameservers()
        │                      compare live records vs required_dns_records()
        │
        └── (--health) ──► fetch Pages health concurrently (10 workers)
                                  │
                           get_pages_health(repo)
                           -> pages_configured
                              https_enforced
                              cert_state
                              pages_status
                                  │
                           classify: _health_status()
                           ┌──────────────────────────────┐
                           │ pages_error  Pages not set up │
                           │ no_cert      no certificate   │
                           │ cert_pending cert in progress │
                           │ fixable      cert approved    │
                           │              HTTPS not on yet │
                           │ healthy      HTTPS enforced   │
                           └──────────────────────────────┘
                                  │
                    ┌─────────────┴──────────────┐
                    │                            │
                (no --fix)                   (--fix)
                    │                            │
               sort by severity            fix "fixable" repos
               display table              enable HTTPS enforcement
                                          re-display updated status
```

## Doctor Workflow

`mimeo doctor` runs preflight checks before any API calls:

```
mimeo doctor [domain ...]
        │
        ▼
Python >= 3.11?     ok / fail + remediation
        │
        ▼
gh installed?       ok / fail + remediation
        │
        ▼
gh authenticated?   ok / fail + remediation
        │
        ▼
workflow scope?     ok / fail + remediation
        │
        ▼
config valid?       ok / fail + remediation
        │
        ▼
(for each domain) NS check via PorkbunRegistrar.check_nameservers()
  ns_ok? ──► ok
  !ns_ok? ──► warn: nameservers point elsewhere
        │
        ▼
all ok? ──► exit 0
any fail? ──► print failures ──► exit non-zero
```

Each check returns `(ok: bool, detail: str, fix: str)`. The checks are implemented as standalone functions and are independently testable.

## Data Flow: DNS Record Creation

The Porkbun registrar generates these records for a GitHub Pages deployment:

```
github_pages_records(domain, github_user)

Apex A records (4 records):
  A  @  185.199.108.153  TTL 600
  A  @  185.199.109.153  TTL 600
  A  @  185.199.110.153  TTL 600
  A  @  185.199.111.153  TTL 600

www CNAME:
  CNAME  www  github_user.github.io  TTL 600
```

The `configure_dns` method normalizes record names for idempotent operation. Porkbun can return apex records as `""`, `"@"`, or the full domain name — all are treated as equivalent.

## Configuration Loading

```
Config.load(path=None)
        │
        ▼
default path: ~/.config/mimeo/config.toml
        │
        ▼
parse TOML
  [porkbun]   api_key, secret_key
  [github]    default_org
  [defaults]  registrar, host
        │
        ▼
apply env var overrides (take precedence)
  MIMEO_PORKBUN_API_KEY
  MIMEO_PORKBUN_SECRET
  MIMEO_GITHUB_USERNAME
        │
        ▼
validate required fields
raise ConfigurationError if missing
        │
        ▼
return Config dataclass
```

## Exception Hierarchy

```
MimeoError
├── ConfigurationError     missing/invalid config file or required fields
├── ProviderError
│   ├── RegistrarError     Porkbun API failures
│   │   └── NSMismatchError  nameservers don't match expected provider
│   └── HostError          GitHub API / gh CLI failures
├── DNSError               DNS verification failures
├── NetworkError           network-level request failures
└── APIError               HTTP error responses (has status_code attribute)
```

The CLI catches `ConfigurationError` and `HostError` at the top level and prints a user-readable message before exiting. `RegistrarError` in the `create` command is caught and treated as a non-fatal DNS failure — the site is still accessible via `github.io` URL.

## Exit Codes

| Code | Constant | Meaning |
|:-----|:---------|:--------|
| 0 | EXIT_OK | All operations succeeded |
| 2 | EXIT_CONFIG | Configuration missing or invalid |
| 3 | EXIT_AUTH | Authentication failure (API key, gh token) |
| 4 | EXIT_RATE_LIMIT | Rate limit hit |
| 5 | EXIT_TRANSIENT | Transient network/server error |
| 6 | EXIT_PARTIAL | Some domains succeeded, some failed |

## Registrar List Workflow

`mimeo registrar list` enumerates all domains in the Porkbun account and enriches them concurrently:

```
mimeo registrar list [--with-dns] [--workers N]
        │
        ▼
PorkbunRegistrar.list_domains()
  GET /domain/listAll
        │
        ▼
concurrent enrichment (ThreadPoolExecutor, default 5 workers)
  per domain:
    check_nameservers() -> NameserverCheckResult (ns_ok)
    (--with-dns) fetch_dns_records() -> list[DNSRecord]
        │
        ▼
sort alphabetically by domain name
        │
        ▼
output: domain, tld, expires, auto_renew, ns_ok, nameservers
  (--format text|json|csv)
```

## Structured Logging

The `--log-format json` global option switches all diagnostic output to newline-delimited JSON on stderr:

```
mimeo --log-format json create example.com
```

Each log record has fields: `ts` (ISO 8601 UTC), `level`, `message`, and optionally `domain`. Normal result output (tables, JSON arrays) still goes to stdout.

## GitHub Pages SSL Certificate Lifecycle

HTTPS enforcement cannot be enabled immediately after Pages setup. The certificate goes through states:

```
new
  -> authorization_created
  -> issued
  -> approved        <-- HTTPS can be enforced here ("fixable")
```

The `create` command attempts HTTPS enforcement at deploy time. If the certificate is not yet approved, it logs a warning and sets `https_pending = True`. The `list --fix` command can later enable HTTPS for any repo in `fixable` state.

## Content Generation

`generate_minimal_site(domain, output_dir)` creates three files:

```
output_dir/
├── index.html                 landing page
│   body { background: #1a1a1a; color: #e0e0e0 }
│   <div class="domain">e x a m p l e . c o m</div>
│   (domain characters spaced with letter-spacing: 0.5rem)
│
├── .github/workflows/
│   └── static.yml             GitHub Actions Pages deployment workflow
│       triggers: push to main, workflow_dispatch
│       permissions: pages:write, id-token:write
│
└── README.md                  minimal placeholder
```

The content is generated with Python string substitution (no template engine). The domain name is displayed with `" ".join(domain)` — each character separated by a space, combined with CSS `letter-spacing`.

## Dependencies

| Package | Version | Role |
|:--------|:--------|:-----|
| click | >=8.0 | CLI framework, subcommands, options |
| requests | >=2.31 | HTTP client for Porkbun API |
| dnspython | >=2.4 | DNS record verification after propagation |
| pytest | dev | Test runner |
| mypy | dev | Static type checking |
| ruff | dev | Linting |
| pytest-mock | dev | Mock patching in tests |
| responses | dev | HTTP request mocking |

Python's `tomllib` (stdlib, 3.11+) handles TOML config parsing — no external TOML library needed.

## Idempotency

`mimeo create` is safe to re-run:

- Repository creation: checks for existing repo before creating
- Content push: skipped if repo already exists
- Pages configuration: `enable_github_pages` checks if Pages is already on
- DNS configuration: deletes existing records of matching type/name before creating new ones
- HTTPS enforcement: attempts to enable; swallows "certificate does not exist" error

Partial failure states (e.g., GitHub Pages deployed but DNS not configured) can be resolved by re-running the command.
