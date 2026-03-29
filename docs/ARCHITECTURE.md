# Architecture

## Overview

Mimeo is a CLI tool that automates the full provisioning pipeline for static landing pages: GitHub repository creation from templates, GitHub Pages configuration, and DNS configuration at Porkbun. One command takes a domain from nothing to a live HTTPS site.

The tool is structured around a provider abstraction that separates the registrar (DNS) and host (deployment) concerns. The current implementation supports Porkbun as the registrar and GitHub Pages as the host. The abstractions allow adding other providers without changing the core orchestration logic.

Site content comes from GitHub template repositories in the `tepiton` org, generated via GitHub's template repo API (`POST /repos/{owner}/{repo}/generate`). There is no local content generation step.

## Component Map

```
mimeo/
├── cli/                 Command-line interface (Click)
│   ├── __init__.py        main group, --log-format {text|json} global option
│   ├── _processing.py     Shared concurrent processing, domain validation,
│   │                       error categorization, exit-on-failure helpers
│   │                       ThreadPoolExecutor for concurrent provisioning
│   ├── create.py          mimeo create -- template-based provisioning
│   ├── list_cmd.py        mimeo list -- read-only site enumeration
│   ├── dns.py             mimeo dns check / mimeo dns repair
│   ├── fix.py             mimeo fix https -- enable HTTPS enforcement
│   ├── doctor.py          mimeo doctor -- prerequisite checks
│   ├── template.py        mimeo template apply -- replace repo from template
│   └── registrar.py       mimeo registrar list -- Porkbun domain inventory
│
├── config.py           Configuration loader
│                         TOML file: ~/.config/mimeo/config.toml
│                         Environment variable overrides: MIMEO_*
│
├── models.py           Data models
│                         DNSRecord, DNSRecordType, NameserverCheckResult
│
├── exceptions.py       Exception hierarchy + exit codes
│                         EXIT_OK=0, EXIT_GENERAL=1, EXIT_CONFIG=2, EXIT_AUTH=3
│                         EXIT_RATE_LIMIT=4, EXIT_TRANSIENT=5, EXIT_PARTIAL=6
│                         MimeoError
│                           ConfigurationError
│                           ProviderError
│                             RegistrarError
│                             HostError
│                           DNSError
│                           NetworkError
│                           APIError (status_code attribute)
│
├── providers/
│   ├── base.py         Abstract base classes
│   │                     Registrar ABC: check_nameservers, update_nameservers, list_domains
│   │                     DNSProvider ABC: configure_dns, verify_dns
│   │                     Host ABC: deploy_site -> DeployResult, required_dns_records,
│   │                               enable_https_enforcement -> bool
│   │                     DeployResult dataclass: url, repo_created, https_enabled, repo_existed
│   │
│   ├── registrar/
│   │   └── porkbun.py  Porkbun registrar + DNS provider
│   │                     _PorkbunClient: shared API plumbing
│   │                     PorkbunRegistrar: list_domains, check_nameservers,
│   │                       update_nameservers, domain_exists
│   │                     PorkbunDNSProvider: configure_dns, verify_dns, check_dns_drift
│   │                     HTTP calls to api-ipv4.porkbun.com/api/json/v3
│   │                     configure_dns: delete conflicts, create records
│   │                     verify_dns: poll with dnspython
│   │
│   └── host/
│       └── github.py   GitHub Pages provider
│                         gh CLI for API calls and git authentication
│                         GITHUB_PAGES_IPS constant (185.199.108-111.153)
│                         TEMPLATE_ORG = "tepiton", DEFAULT_TEMPLATE = "mimeo.lol"
│                         Repository creation from template via GitHub API
│                         Pages enable, custom domain, HTTPS enforcement
│                         health_status() classifier
│                         get_pages_health(), list_mimeo_repositories()
│
└── utils/
    ├── http.py         HTTP client
    │                     requests.Session, no built-in retry
    │                     Retry handled at provider layer via retry_with_jitter()
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
update_nameservers(domain)           max_attempts, delay
list_domains()                       progress_callback -> bool
        │                                      │
        ▼                                      ▼
PorkbunRegistrar                  PorkbunDNSProvider
(porkbun.py)                      (porkbun.py)

Host (ABC)
──────────────────────────────────────────
deploy_site(domain, template, force)
  -> DeployResult
required_dns_records(domain) -> list[DNSRecord]
enable_https_enforcement(repo_full_name) -> bool
        │
        ▼
GitHubHost
(github.py)
```

New providers implement these interfaces. The CLI orchestration in `cli/` calls only the abstract methods, so new implementations slot in without touching the core flow.

`NameserverCheckResult` (in `models.py`) carries `ok: bool`, `actual: list[str]`, `expected: list[str]`.

`DeployResult` (in `providers/base.py`) carries `url: str`, `repo_created: bool`, `https_enabled: bool`, `repo_existed: bool`.

## Create Workflow

The `mimeo create <domain>` command orchestrates stages in sequence per domain:

```
mimeo create example.com [--template mimeo.lol] [--skip-dns] [--force]
        │
        ▼
Validate domain format (_processing.validate_domains)
        │
        ▼
Load Config
(~/.config/mimeo/config.toml or env vars)
        │
        ▼
Deploy to GitHub Pages (GitHubHost)
  ┌── repo exists? ─── yes ──► skip creation
  │                              │
  no                             │
  │                              │
  ▼                              ▼
  create from template       enable Pages
  POST /repos/{tepiton}/     set custom domain
    {template}/generate      try HTTPS enforcement
  set topics: mimeo,               │
    landing-page, github-pages     │
        └──────────────────────────┘
                   │
                   ▼
         DeployResult
         url, repo_created, https_enabled, repo_existed
                   │
                   ▼
Check Nameservers (PorkbunRegistrar)
  ns_ok? ── no ──► warn, skip DNS config
                   suggest 'mimeo dns repair'
                   │
  ns_ok? ── yes
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
  progress_callback for status output
  returns True/False (does not block success)
                   │
                   ▼
Report result: url, https_pending, dns_pending
```

### Concurrency

Multiple domains use `ThreadPoolExecutor` via `_processing.process_domains_concurrent` with up to 5 workers:

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

`mimeo list` enumerates repositories tagged with the `mimeo` topic. This is a read-only command with no side effects.

```
mimeo list [--health]
        │
        ▼
gh search repos user:<owner> topic:mimeo
        │
        ▼
normalize: name, repository URL, site URL, updated date
        │
        ├── (no --health) ──► sort by name ──► display
        │
        └── (--health) ──► fetch Pages health concurrently (10 workers)
                                  │
                           get_pages_health(repo)
                           -> pages_configured
                              https_enforced
                              cert_state
                              pages_status
                                  │
                           classify: health_status()
                           ┌──────────────────────────────┐
                           │ pages_error  Pages not set up │
                           │ no_cert      no certificate   │
                           │ cert_pending cert in progress │
                           │ fixable      cert approved    │
                           │              HTTPS not on yet │
                           │ healthy      HTTPS enforced   │
                           └──────────────────────────────┘
                                  │
                        sort by severity
                        display table
```

Use `mimeo fix https` to fix sites in `fixable` state.

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
(for each domain) NS check via _lookup_nameservers()
  ns_ok? ──► ok
  !ns_ok? ──► warn: nameservers point elsewhere
        │
        ▼
all ok? ──► exit 0
any fail? ──► print failures ──► exit EXIT_CONFIG
```

Each check returns `(ok: bool, detail: str, fix: str)`. The checks are implemented as standalone functions and are independently testable.

## DNS Check/Repair Workflow

`mimeo dns check` inspects DNS configuration for drift:

```
mimeo dns check example.com [--format text|json|csv]
        │
        ▼
GitHubHost.required_dns_records(domain) -> expected
PorkbunRegistrar.check_nameservers(domain) -> ns_ok
PorkbunDNSProvider.check_dns_drift(domain, expected) -> status
        │
        ▼
┌─────────────────────────────────────────────┐
│ status: ok      all expected records match   │
│ status: drift   extra records found          │
│ status: missing expected records absent      │
│ status: error   API failure                  │
└─────────────────────────────────────────────┘
        │
        ▼
display: domain, ns_ok, nameservers, dns_status, missing, extra
```

`mimeo dns repair` re-applies expected DNS records:

```
mimeo dns repair example.com [--reset-nameservers] [--dry-run]
        │
        ▼
PorkbunRegistrar.check_nameservers(domain)
        │
        ├── ns_ok ──► proceed
        │
        └── !ns_ok + --reset-nameservers ──► update_nameservers(domain)
                                                        │
            !ns_ok (no flag) ──► error, abort      ns_ok now
                                        │
                                        ▼
                               GitHubHost.required_dns_records(domain)
                                        │
                                        ▼
                               PorkbunDNSProvider.configure_dns(domain, records)
                                        │
                                        ▼
                               PorkbunDNSProvider.verify_dns(domain, records)
                                  max_attempts=10, delay=5
                                  progress_callback for status
                                        │
                                        ▼
                               report result
```

## Template Apply Workflow

`mimeo template apply` replaces repository content with a different template:

```
mimeo template apply example.com --template new-theme [--yes] [--dry-run]
        │
        ▼
Validate domain format
        │
        ▼
Confirm destructive operation (skip with --yes)
        │
        ▼
GitHubHost.deploy_site(domain, template, force=True)
  ┌── repo exists? ── yes ──► delete existing repo
  │                              │
  └──────────────────────────────┘
                 │
                 ▼
  create from template (POST /repos/{tepiton}/{template}/generate)
  set topics: mimeo, landing-page, github-pages
  enable GitHub Pages
  set custom domain
  try HTTPS enforcement
                 │
                 ▼
  DeployResult(repo_existed=True, repo_created=True)
                 │
                 ▼
report result
```

DNS records are not modified by this command.

## Fix HTTPS Workflow

`mimeo fix https` enables HTTPS enforcement on sites with approved SSL certificates:

```
mimeo fix https [domains ...] [--dry-run]
        │
        ├── domains provided ──► fix those repos
        │
        └── no domains ──► discover fixable repos
                │
                ▼
        GitHubHost.list_mimeo_repositories()
                │
                ▼
        fetch Pages health concurrently (10 workers)
        filter for health_status == "fixable"
                │
                ▼
        GitHubHost.enable_https_enforcement(repo_full_name)
          returns True  -> success
          returns False -> certificate not ready (swallowed)
          raises HostError -> failure
                │
                ▼
        display summary: fixed N/M
```

## Data Flow: DNS Record Creation

The GitHub Pages host defines required records; Porkbun creates them:

```
GitHubHost.required_dns_records(domain)

Apex A records (4 records):
  A  @  185.199.108.153  TTL 600
  A  @  185.199.109.153  TTL 600
  A  @  185.199.110.153  TTL 600
  A  @  185.199.111.153  TTL 600

www CNAME:
  CNAME  www  github_user.github.io  TTL 600
```

The `configure_dns` method normalizes record names for idempotent operation. Porkbun can return apex records as `""`, `"@"`, or the full domain name -- all are treated as equivalent.

## Configuration Loading

```
Config.load(path=None)
        │
        ▼
default path: ~/.config/mimeo/config.toml
        │
        ▼
parse TOML (tomllib, stdlib 3.11+)
  schema_version    integer (currently 1)
  [porkbun]         api_key, secret_key
  [github]          default_org
  [defaults]        registrar, host
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
│   └── HostError          GitHub API / gh CLI failures
├── DNSError               DNS verification failures
├── NetworkError           network-level request failures
└── APIError               HTTP error responses (has status_code attribute)
```

The CLI catches `ConfigurationError` and `HostError` at the top level and prints a user-readable message before exiting. `RegistrarError` in the `create` command is caught and treated as a non-fatal DNS failure -- the site is still accessible via `github.io` URL.

## Exit Codes

| Code | Constant | Meaning |
|:-----|:---------|:--------|
| 0 | EXIT_OK | All operations succeeded |
| 1 | EXIT_GENERAL | General/unexpected error |
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
  POST /domain/listAll
        │
        ▼
concurrent enrichment (ThreadPoolExecutor, default 5 workers)
  per domain:
    check_nameservers() -> NameserverCheckResult (ns_ok)
    (--with-dns) _get_domain_records() -> list[DNSRecord]
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

The `create` command attempts HTTPS enforcement at deploy time. If the certificate is not yet approved, it logs a warning and sets `https_pending = True`. The `fix https` command can later enable HTTPS for any repo in `fixable` state.

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

Python's `tomllib` (stdlib, 3.11+) handles TOML config parsing -- no external TOML library needed.

## Idempotency

`mimeo create` is safe to re-run:

- Repository creation: checks for existing repo before creating; if it exists, skips creation
- Content generation: no local content push; template repo API handles everything server-side
- Pages configuration: `enable_github_pages` checks if Pages is already on
- DNS configuration: deletes existing records of matching type/name before creating new ones
- HTTPS enforcement: attempts to enable; swallows "certificate does not exist" error

`mimeo template apply` uses `force=True` which deletes and recreates the repository from the template. This is intentionally destructive.

Partial failure states (e.g., GitHub Pages deployed but DNS not configured) can be resolved by running `mimeo dns repair` or re-running `mimeo create`.
