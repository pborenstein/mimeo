# Architecture

Describes mimeo 2.0. The reasons behind the design are in
[MIMEO2_DESIGN.md](MIMEO2_DESIGN.md) and DEC-039 to DEC-046 in
[DECISIONS.md](DECISIONS.md).

## Overview

mimeo connects a hostname to the site that serves it. Four things have to agree for a site to load at `example.com`:

| Thing | Held by | Read from |
|:------|:--------|:----------|
| The registration | Registrar (Porkbun) | Porkbun API |
| The nameservers | Registrar | Porkbun API |
| The DNS records | Whichever DNS provider the nameservers name | That provider's API (Porkbun or Cloudflare) |
| The site and its custom-domain setting | Host (GitHub Pages) | GitHub API, through the `gh` CLI |

Every command runs the same three steps:

```
hostname
   │
   ▼
READ      connection.py   Fleet.read(hostname) -> Connection
   │                        zone, nameservers, DNS provider, records, site, site state
   ▼
COMPARE   plan.py         compare(Connection, Host) -> Plan
   │                        changes (each: where, what, why) + problems no change fixes
   ▼
APPLY     plan.py         apply(Connection, Plan, Host)
                            or print the changes (status, --dry-run)
```

`status` prints the Plan. `sync` applies it. `link`, `unlink` and `delegate` (`operations.py`) change one thing and then run the same steps; `create` and `delete` add repository creation and deletion around `link` and `unlink`.

Site content comes from GitHub template repositories (`POST /repos/{owner}/{repo}/generate`). Templates are tracked in the tepiton meta-repo; mimeo only requires that a template has its `is_template` flag set (DEC-034).

## Component Map

```
mimeo/
├── connection.py        READ
│                          Connection: what was read about one hostname
│                          Fleet: the providers for a run, plus per-run memory of
│                            the registrar's domain list, each zone's nameservers
│                            and each zone's records
│                          Fleet.zone_for: longest registered suffix of a hostname
│                          Fleet.provider_for: the DNS provider the nameservers
│                            belong to (DEC-041)
│                          Fleet.site_for: cache, confirmed against the host; then
│                            the default places; then a scan (DEC-040)
│
├── plan.py              COMPARE and APPLY
│                          Change, Plan
│                          compare(): address records at the site's names against
│                            Host.required_records; certificate and HTTPS state
│                          apply(): carries out changes in order (removals first)
│
├── operations.py        link, unlink, delegate
│                          Functions over the provider interfaces. Each returns an
│                          Outcome (what it did, as sentences) and honors dry_run.
│                          OperationError: a refusal, with the reason
│
├── cache.py             SiteCache: hostname -> site, ~/.cache/mimeo/sites.json
│                          Never the authority; safe to delete
│
├── models.py            DNSRecord (zone-relative name; priority, proxied, id),
│                          Site (`github:owner/repo`), SiteState, ADDRESS_TYPES
│
├── config.py            Config, schema version 2
├── exceptions.py        Exception hierarchy + exit codes
│
├── cli/
│   ├── __init__.py        main group and global options
│   ├── _fleet.py          open_fleet(): builds the providers from config
│   │                       targets_for(): which hostnames a run covers
│   │                       result_row(): Connection + Plan -> one output row
│   ├── _processing.py     concurrency, hostname validation, error categories,
│   │                       exit codes, output formats
│   ├── status.py          prints Plans
│   ├── sync.py            applies Plans
│   ├── connect.py         link, unlink, delegate, scan
│   ├── create.py          delegate if needed, create the repo, link
│   ├── delete.py          unlink, delete the repo
│   └── doctor.py          prerequisite and credential checks
│
├── providers/
│   ├── base.py            Registrar, DNSProvider, Host, RepoProvider
│   ├── gh.py              GhCli: the gh CLI as an API client; recovers the HTTP
│   │                       status from gh's error text into HostError.status_code
│   ├── registrar/
│   │   └── porkbun.py     PorkbunRegistrar (Registrar)
│   │                       PorkbunDNSProvider (DNSProvider)
│   ├── dns/
│   │   └── cloudflare.py  CloudflareDNS (DNSProvider), v4 API, bearer token
│   ├── host/
│   │   ├── github.py      GitHubHost (Host): Pages, custom domain, HTTPS,
│   │   │                   certificate state, scan
│   │   └── template_manifest.py   DEC-024 manifest parsing and substitution
│   └── repo/
│       └── github.py      GitHubRepoProvider (RepoProvider): create from template
│                           (force, rename recovery), manifest, dev-file strip,
│                           topics, Website field, delete
│
└── utils/
    ├── http.py            requests.Session wrapper; raises APIError / NetworkError
    └── retry.py           retry_with_jitter(): 429/5xx, network errors
```

`plan.py`, `connection.py` and `operations.py` hold no vendor knowledge. They are tested against the in-memory providers in `tests/fakes.py`.

## Provider Interfaces

| Interface | Methods | Implementations |
|:----------|:--------|:----------------|
| `Registrar` | `list_domains`, `get_nameservers`, `set_nameservers`, `dnssec_enabled` | `PorkbunRegistrar` |
| `DNSProvider` | `serves(nameservers)`, `zone_exists`, `create_zone`, `zone_nameservers`, `list_records`, `add_record`, `delete_record`; `unsupported_types` | `PorkbunDNSProvider`, `CloudflareDNS` |
| `Host` | `find_site`, `scan`, `state`, `set_custom_domain`, `required_records(site, label)`, `enforce_https` | `GitHubHost` |
| `RepoProvider` | `validate_template`, `create_from_template`, `delete_repository_if_exists` | `GitHubRepoProvider` |

- A DNS provider is chosen per zone by asking each configured provider whether the zone's nameservers are its own (`serves`). Records at a provider the nameservers do not name are never read.
- Nameservers come from the registrar's API, not a public lookup, so they are current the moment `delegate` sets them.
- `required_records` takes the hostname's label within its zone: `""` for an apex (four A, four AAAA, `www` CNAME), anything else for a subdomain (one CNAME). The CNAME target is the repository owner's `github.io` name.

## What `compare` Decides

Records, only when a configured provider serves the zone:

- The site's names are the names of its required records. Only address records (A, AAAA, CNAME, ALIAS) at those names are considered.
- A required record with no live match is added. A live address record that is not required is removed. Removals are ordered first, since a name holds one CNAME and an ALIAS at the apex blocks A records.
- Records are matched on type, name and content. TTL, priority and proxy setting are ignored.
- A record being added takes the proxy setting already in use at its name (DEC-043).

Site:

| Certificate | HTTPS enforced | Result |
|:------------|:---------------|:-------|
| `approved`, more than 14 days left | yes | `ok` |
| `approved`, more than 14 days left | no | `fixable`: change "enforce HTTPS" |
| `approved`, 14 days or less left | either | `expiring`: problem |
| `new`, `authorization_created`, `authorization_pending`, `issued` | either | `pending`: problem |
| none | either | `no cert`: problem |
| anything else (`bad_authz`, ...) | either | `cert error`: problem |
| Pages not enabled | | `no pages`: problem |

## delegate

```
zone registered?  target provider configured?  already served by target? -> done
        │
DNSSEC enabled at the registrar? -> refuse
        │
read every record from the provider serving the zone now (minus NS, SOA)
  current provider not configured -> refuse, unless --empty
        │
create the zone at the target if it is not there
add each record the target does not already have (DNS-only)
        │
read the target zone back; any record missing -> refuse, nameservers unchanged
        │
set the nameservers at the registrar to the target's
```

## Concurrency

`status`, `sync` and `create` process hostnames on a thread pool (`--workers`, default 5); dry runs are sequential. `Fleet` guards its per-run memory with a lock, and sites sharing a zone share one read of its records. An exception for one hostname becomes that hostname's error row; the others are still reported (`map_items`).

## Configuration Loading

```
Config.load(path=None)
        │
        ▼
default path: ~/.config/mimeo/config.toml
        │
        ▼
parse TOML (tomllib, stdlib 3.11+)
  schema_version    integer (currently 2; a version 1 file loads unchanged)
  [porkbun]         api_key, secret_key
  [cloudflare]      api_token, account_id (optional section)
  [github]          default_org, organizations, template_org
  [defaults]        template, dns, ignore_domains
        │
        ▼
apply env var overrides (take precedence)
  MIMEO_PORKBUN_API_KEY
  MIMEO_PORKBUN_SECRET
  MIMEO_GITHUB_USERNAME
  MIMEO_GITHUB_ORGANIZATIONS (comma-separated)
  MIMEO_GITHUB_TEMPLATE_ORG, MIMEO_DEFAULT_TEMPLATE
  MIMEO_CLOUDFLARE_API_TOKEN, MIMEO_CLOUDFLARE_ACCOUNT_ID
  MIMEO_DEFAULT_DNS
        │
        ▼
validate required fields
raise ConfigurationError if missing
        │
        ▼
return Config dataclass
```

`github.template_org` (default `mimeo-templates`) is the org templates are read from; `github.default_org` is the org new site repos are created in. `--template-org` and `--deploy-org` override them for one invocation.

`github.organizations` lists every organization and user account searched for sites; it defaults to `[default_org]`. `defaults.dns` (`porkbun` or `cloudflare`, default `porkbun`) is where `create` and `delegate` put a zone; `cloudflare` requires `cloudflare.api_token`.

`ignore_domains` only trims fleet-wide sweeps (`status --all`, `sync --all`); explicitly named domains are always processed regardless of the ignore list.

## Exception Hierarchy

```
MimeoError
├── ConfigurationError     missing/invalid config file or required fields
├── ProviderError
│   ├── RegistrarError     Porkbun API failures
│   └── HostError          GitHub API / gh CLI failures
├── OperationError         link, unlink or delegate refused; the message says why
├── DNSError               DNS verification failures
├── NetworkError           network-level request failures
└── APIError               HTTP error responses (has status_code attribute)
```

Each command catches exceptions at the top level, prints `[category] message`, and exits by category. Cloudflare failures are `APIError`. In a multi-hostname run an exception becomes that hostname's error row.

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

Only confirmed-transient failures exit 5 (DEC-027): 429 exits 4, 5xx exits 5, 401/403 exit 3, and definitive provider failures (400/404/422, gh not installed) exit 1. A script that retries on 5 does not retry a failure that will repeat.

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

`link` (and so `create`) enforces HTTPS if the certificate is already approved, or waits up to 15 minutes for it with `--wait`. Otherwise it reports HTTPS as pending, and `mimeo sync` enforces it later for any site in `fixable` state.

GitHub issues and renews the certificate only while the records resolve to GitHub's addresses. A site proxied at all its names uses Cloudflare's certificate instead, so mimeo does not judge GitHub's. It checks that the zone is on SSL/TLS mode Full with Automatic off and Always Use HTTPS on, and `sync` sets those (DEC-058).

## Dependencies

| Package | Version | Role |
|:--------|:--------|:-----|
| click | >=8.0 | CLI framework, subcommands, options |
| requests | >=2.31 | HTTP client for the Porkbun and Cloudflare APIs |
| dnspython | >=2.4 | Public NS lookup in `doctor` |
| pytest | dev | Test runner |
| mypy | dev | Static type checking |
| ruff | dev | Linting |
| pytest-mock | dev | Mock patching in tests |
| responses | dev | HTTP request mocking |

Python's `tomllib` (stdlib, 3.11+) handles TOML config parsing -- no external TOML library needed.

## Idempotency

Every command can be re-run:

- `sync` and `link` change only what `compare` finds different; a second run finds nothing.
- `create` leaves an existing repository unchanged (unless `--force`) and still links it.
- `delegate` skips records the target already has, and does nothing when the target already serves the zone.
- `unlink` and `delete` refuse or report when there is nothing to remove.

`mimeo create --force` deletes and recreates the repository from the template. It requires confirmation unless `--yes` is given.

A run that stops partway (repository created, records not written) is finished by `mimeo link` or `mimeo sync`.
