# Architecture

## Overview

Mimeo is a CLI tool that automates the full provisioning pipeline for static landing pages: GitHub repository creation from templates, GitHub Pages configuration, and DNS configuration at Porkbun. One command takes a domain from nothing to a live HTTPS site.

The tool is structured around a provider abstraction that separates the registrar (DNS) and host (deployment) concerns. The current implementation supports Porkbun as the registrar and GitHub Pages as the host. The abstractions allow adding other providers without changing the core orchestration logic.

Site content comes from GitHub template repositories in the `tepiton` org, generated via GitHub's template repo API (`POST /repos/{owner}/{repo}/generate`). There is no local content generation step.

The CLI surface is five verbs: `create`, `status`, `sync`, `doctor`, and (once DEC-024 lands) `template lint`. Each of `create`, `status`, and `sync` absorbed one or more single-purpose commands from an earlier design (DEC-025); the provider layer underneath was untouched by that collapse.

## Component Map

```
mimeo/
├── cli/                 Command-line interface (Click)
│   ├── __init__.py        main group, --log-format {text|json} global option
│   │                       registers: create, status, sync, doctor
│   ├── _processing.py     Shared concurrent processing, domain validation,
│   │                       error categorization, exit-on-failure helpers
│   │                       ThreadPoolExecutor for concurrent provisioning
│   ├── create.py          mimeo create -- provision, and optionally replace
│   │                       (--force), a site from a template
│   ├── status.py          mimeo status -- cross-provider fleet view;
│   │                       --source narrows to one provider
│   ├── sync.py            mimeo sync -- converge DNS + HTTPS enforcement
│   └── doctor.py          mimeo doctor -- prerequisite checks
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
│   │                     PorkbunDNSProvider: configure_dns, verify_dns, check_dns_drift,
│   │                       get_domain_records
│   │                     HTTP calls to api-ipv4.porkbun.com/api/json/v3
│   │                     configure_dns: delete conflicts, create records
│   │                     verify_dns: poll with dnspython
│   │
│   └── host/
│       ├── github.py   GitHub Pages provider
│       │                 gh CLI for API calls and git authentication
│       │                 GITHUB_PAGES_IPS constant (185.199.108-111.153)
│       │                 TEMPLATE_ORG = "tepiton", DEFAULT_TEMPLATE = "mimeo.lol"
│       │                 Repository creation from template via GitHub API
│       │                 Pages enable, custom domain, HTTPS enforcement
│       │                 health_status() classifier
│       │                 get_pages_health(), list_mimeo_repositories(),
│       │                 get_template_repository()
│       │                 _fetch_template_manifest / _apply_template_manifest:
│       │                 deploy-time manifest read + substitution (below)
│       └── template_manifest.py  DEC-024 manifest: parse_manifest(),
│                         apply_substitutions(), DEFAULT_DEV_PATHS
│                         Three format handlers: string-replace,
│                         js-key (loosey-goosey dotted-path to a unique
│                         string-literal leaf), yaml-frontmatter-key
│                         All failures loud (HostError); strip of dev-only
│                         paths stays best-effort
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
        │                           check_dns_drift(domain, expected)
        ▼                           get_domain_records(domain)
PorkbunRegistrar                              │
(porkbun.py)                                  ▼
                                    PorkbunDNSProvider
                                    (porkbun.py)

Host (ABC)
──────────────────────────────────────────
deploy_site(domain, template, force)
  -> DeployResult
required_dns_records(domain) -> list[DNSRecord]
enable_https_enforcement(repo_full_name) -> bool
get_pages_health(repo_full_name) -> dict
list_mimeo_repositories() -> list[dict]
get_template_repository(repo_full_name) -> str | None
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
mimeo create example.com [--template mimeo.lol] [--skip-dns] [--force] [--yes]
        │
        ▼
Validate domain format (_processing.validate_domains)
        │
        ▼
Load Config
(~/.config/mimeo/config.toml or env vars)
        │
        ▼
--force + not --yes? ──► confirm destructive replacement, abort if declined
        │
        ▼
Verify domain is registered in this Porkbun account
  not registered ──► abort, nothing else touched
        │
        ▼
Deploy to GitHub Pages (GitHubHost)
  ┌── repo exists? ─── yes, no --force ──► leave content unchanged
  │                    yes, --force ──► delete existing repo, recreate
  no                              │
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
                   suggest 'mimeo sync' once nameservers are correct
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
Report result: url, https_pending, dns_pending
  (no propagation poll -- run 'mimeo status' to confirm)
```

`--force` replaces an existing repository's content from the template; without it, an existing repo is left unchanged and DNS configuration is skipped (nothing new to point at). The domain-substitution manifest (DEC-024) reruns automatically on both plain `create` and `create --force`: a template shipping `mimeo.template.json` has its declared self-reference points rewritten to the deployed domain, with failures surfaced loudly rather than skipped.

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

Single domains, `--dry-run`, and `--sequential` always run with verbose per-step output. Concurrent mode suppresses per-step output to prevent garbled interleaving; each domain prints a single completion line.

## Status Workflow

`mimeo status` is a read-only cross-provider view: registration expiry, nameservers, DNS drift, and Pages health per domain, joining the Porkbun account against mimeo-managed repos. `--source` narrows it to a single provider.

```
mimeo status [domains ...] | --all [--source {github,porkbun,dns}] [--problems] [--with-dns] [--show-template]
        │
        ├── no --source ──► full cross-provider join
        │       │
        │       ▼
        │   PorkbunRegistrar.list_domains() + GitHubHost.list_mimeo_repositories()
        │       │
        │       ▼
        │   per domain (concurrent, default 5 workers):
        │     check_nameservers() -> ns_ok
        │     (--with-dns) get_domain_records()
        │     (has repo) get_pages_health() -> site_health, classify via health_status()
        │     (has repo, --show-template) get_template_repository()
        │     (has repo + registered) required_dns_records() + check_dns_drift() -> dns_status
        │       │
        │       ▼
        │   (--problems) filter to domains needing attention
        │
        ├── --source github ──► mimeo-managed repos only (former `list`)
        │       (--health) fetch Pages health concurrently
        │       (--show-template) fetch template per repo
        │
        ├── --source porkbun ──► registered domains only (former `registrar list`)
        │       per domain: check_nameservers()
        │       (--with-dns) get_domain_records()
        │
        └── --source dns ──► live DNS records or drift, no cross-provider join
                (no --problems) get_domain_records() -- raw records (former `dns show`)
                (--problems)    required_dns_records() + check_dns_drift() (former `dns check`)
                requires explicit domain names -- no fleet-wide mode
```

A bare `mimeo status` refuses to run: the fleet sweep is slow, so it requires the explicit `--all` (this restriction does not apply to `--source dns`, which always requires named domains instead). Registered domains with no site show `no repo`; sites whose domain is not in the Porkbun account show `-` on the registrar side. The DNS column is `-` when there is no repo (no desired state to compare against). Drift and unhealthy sites are findings (exit 0); API errors exit nonzero with partial results.

## Sync Workflow

`mimeo sync` converges domains on their desired state: applies missing DNS records and enables HTTPS enforcement when the certificate is ready. It absorbed the former `dns repair` and `fix https` commands (DEC-025).

```
mimeo sync [domains ...] | --all [--reset-nameservers] [--dry-run]
        │
        ▼
PorkbunRegistrar.list_domains() + GitHubHost.list_mimeo_repositories()
        │
        ▼
per domain (concurrent unless --dry-run):
  not in Porkbun account ──► skip: "not in Porkbun account"
  not a mimeo repo ──► skip: "no repo (use: mimeo create)"
        │
        ▼
  check_nameservers()
    ns_ok? ── no, no --reset-nameservers ──► skip: NS mismatch, suggest the flag
    ns_ok? ── no, --reset-nameservers ──► update_nameservers()
    ns_ok? ── yes
        │
        ▼
  required_dns_records() + check_dns_drift()
    missing records ──► configure_dns() -- apply them
    extra-only drift  ──► report dns_status="drift" (same term `status` uses);
                          sync does not delete records it does not manage
        │
        ▼
  get_pages_health()
    health_status() == "fixable" ──► enable_https_enforcement()
        │
        ▼
  report actions taken (or would-take, under --dry-run)
```

Sync will not create repositories (`mimeo create`), change site content (`mimeo create --force`), or delete DNS records it does not manage. It does not poll for DNS propagation -- run `mimeo status` afterwards to confirm. A bare `mimeo sync` refuses to run: fleet-wide convergence requires the explicit `--all`; naming domains is always allowed.

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
(for each domain) NS check via lookup_nameservers()
  ns_ok? ──► ok
  !ns_ok? ──► warn: nameservers point elsewhere
        │
        ▼
all ok? ──► exit 0
any fail? ──► print failures ──► exit EXIT_CONFIG
```

Each check returns `(ok: bool, detail: str, fix: str)`. The checks are implemented as standalone functions and are independently testable.

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
  ignore_domains    list of domains excluded from fleet-wide sweeps
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

`ignore_domains` only trims fleet-wide sweeps (`status --all`, `sync --all`); explicitly named domains are always processed regardless of the ignore list.

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

The `create` command attempts HTTPS enforcement at deploy time. If the certificate is not yet approved, it logs a warning and sets `https_pending = True`. `mimeo sync` later enables HTTPS for any repo in `fixable` state.

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

- Repository creation: checks for existing repo before creating; if it exists, skips creation (unless `--force`)
- Content generation: no local content push; template repo API handles everything server-side
- Pages configuration: `enable_github_pages` checks if Pages is already on
- DNS configuration: deletes existing records of matching type/name before creating new ones
- HTTPS enforcement: attempts to enable; swallows "certificate does not exist" error

`mimeo create --force` deletes and recreates the repository from the template. This is intentionally destructive and requires confirmation unless `--yes` is given.

Partial failure states (e.g., GitHub Pages deployed but DNS not configured) can be resolved by running `mimeo sync` or re-running `mimeo create`.
