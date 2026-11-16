# Mimeo

Connects a domain to the site that serves it, and keeps the connection correct. For a site to load at `example.com`, four things have to agree: the registration, the nameservers, the DNS records at whichever provider the nameservers name, and the host's custom-domain setting. mimeo reads all four, shows what disagrees, and fixes what it can.

Today that means Porkbun as the registrar, Porkbun or Cloudflare as the DNS provider, and GitHub Pages as the host.

## Quick Start

```bash
git clone https://github.com/pborenstein/mimeo
cd mimeo
uv sync
cp config.toml.example ~/.config/mimeo/config.toml
# edit ~/.config/mimeo/config.toml with your Porkbun API key and GitHub organization

uv run mimeo doctor              # verify setup
uv run mimeo create example.com  # new repo from a template, connected to the domain
uv run mimeo status example.com
```

Full setup details (prerequisites, `gh` token scope, global vs. dev install, environment variable overrides) are in [docs/INSTALLATION.md](./docs/INSTALLATION.md).

## How it works

Every command runs the same three steps.

1. **Read.** For a hostname, collect the zone it belongs to, the zone's nameservers (from the registrar), which configured DNS provider those nameservers belong to, the records at that provider, and the site whose custom domain is the hostname, with its certificate and HTTPS state.
2. **Compare.** Ask the host which records the site needs and compare them, and the host's settings, with what was read. The result is a list of changes.
3. **Apply** the changes, or print them.

`status` prints the list. `sync` applies it. The other commands do one thing before or after those steps.

| Command | What it does |
|:--------|:-------------|
| [`status`](#status) | Shows what was read, the changes `sync` would make, and the problems it cannot fix |
| [`sync`](#sync) | Applies the changes |
| [`link`](#link-and-unlink) | Sets a site's custom domain to a hostname, then syncs it |
| [`unlink`](#link-and-unlink) | Removes the site's records and its custom domain |
| [`delegate`](#delegate) | Moves a zone to another DNS provider |
| [`create`](#create) | `delegate` if needed, a new repository from a template, then `link` |
| [`delete`](#delete) | `unlink`, then deletes the repository |
| [`scan`](#scan) | Rebuilds the cache of which repository serves which hostname |
| [`doctor`](#doctor) | Checks tools, config and credentials |

### Which records mimeo touches

mimeo owns the address records (A, AAAA, CNAME, ALIAS) at a site's own names, and nothing else in the zone.

| Site | Names | Records GitHub Pages needs |
|:-----|:------|:---------------------------|
| Apex (`example.com`) | `example.com`, `www.example.com` | Four A and four AAAA at the apex; `www` CNAME to `<owner>.github.io` |
| Subdomain (`service.example.com`) | `service.example.com` | One CNAME to `<owner>.github.io` |

At those names a required record that is missing is added, and an address record that is not required is removed. MX and TXT records, records at any other name, and each record's Cloudflare proxy setting are left alone. `<owner>` is the owner of the repository serving the site.

### Which repository serves a hostname

The repository whose GitHub Pages custom domain is the hostname, in any organization or account listed under `github.organizations`. The repository's name does not matter. mimeo caches the pairs it finds in `~/.cache/mimeo/sites.json`; the custom-domain setting stays the authority, and a cached pair is confirmed against it before use. See [`scan`](#scan).

## After `create`

The site is an ordinary GitHub repository. To change it, clone the repo, edit, and push to `main`: the template's GitHub Actions workflow builds the site and deploys it to Pages. Content changes never go through mimeo.

To push without deploying, put `[skip ci]` (or `[no ci]`, `[skip actions]`) in the commit message. See GitHub's [Skipping workflow runs](https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-workflow-runs/skipping-workflow-runs).

## Global options

These options go before the subcommand and apply to every command.

| Option | Effect | Default |
|:-------|:-------|:--------|
| `--log-format text` <br> `--log-format json` | Log format for diagnostic output on stderr | `text` |
| `--template-org ORG` | Org holding template repositories | `github.template_org` (`mimeo-templates`) |
| `--deploy-org ORG` | GitHub user/org where site repositories are created | `github.default_org` (required) |

Precedence: CLI flags > `MIMEO_*` environment variables > config file.

## Commands

### status

| Task | Command |
|:-----|:--------|
| Check specific hostnames | `mimeo status example.com service.example.com` |
| Every registered domain and known site | `mimeo status --all` |
| Only hostnames that need attention | `mimeo status --all --problems` |
| Every record in the zone, from the provider serving it | `mimeo status example.com --records` |
| For scripting | `mimeo status --all --format json \| jq '.[] \| select(.fixable)'` |

| Column | Values |
|:-------|:-------|
| `EXPIRES` | Registration expiry; `-` for a subdomain or a hostname whose domain is not at the registrar |
| `DNS` | The provider serving the zone: `porkbun`, `cloudflare`, `external` (another provider, which mimeo cannot read), `none` (the registrar reports no nameservers). A trailing `*` means the site's records are proxied. |
| `RECORDS` | `ok`, `missing`, `extra`, `external` (not compared), `unknown` |
| `SITE` | `ok`, `fixable` (certificate ready, HTTPS not enforced), `pending`, `no cert`, `cert error`, `expiring` (14 days or less, so renewal is not happening), `no pages`, `no site` |
| `REPO` | The repository whose custom domain is the hostname |

When hostnames are named, each row is followed by the changes `sync` would make and the problems it cannot fix. A registered domain with no site, a zone at an external provider, and proxied records are not problems. A bare `mimeo status` refuses to run; a fleet sweep needs `--all`. Findings exit 0; API errors exit nonzero with partial results.

### sync

| Task | Command |
|:-----|:--------|
| Preview | `mimeo sync --all --dry-run` |
| Apply to every site | `mimeo sync --all` |
| Apply to specific hostnames | `mimeo sync example.com` |

Adds missing address records, removes extra ones at the site's own names, and enforces HTTPS when the certificate is ready. It does not change nameservers (`delegate`), does not link anything (`link`), does not change a proxy setting, and does not write to a zone at a provider that is not configured.

### link and unlink

| Task | Command |
|:-----|:--------|
| Link a hostname to the repo named after it in the default org | `mimeo link example.com` |
| Link to any repository | `mimeo link example.com github:someone/portfolio` |
| Link a subdomain | `mimeo link service.example.com github:mimeo-sites/service` |
| Preview | `mimeo link example.com --dry-run` |
| Wait up to 15 minutes for the certificate | `mimeo link example.com --wait` |
| Set the custom domain only | `mimeo link example.com --skip-dns` |
| Take a site off a hostname, keeping the repository | `mimeo unlink example.com` |

`link` works on a site that already exists; it creates nothing. Records are written DNS-only. When the zone is at a provider mimeo cannot write to, `link` sets the custom domain and prints the records to add by hand. Without `--wait`, a certificate that is not ready yet is reported and `mimeo sync` enforces HTTPS later. `link` refuses a hostname another site already serves.

`unlink` removes the address records at the site's names and the custom-domain setting, after a confirmation prompt (`--yes` skips it).

### delegate

| Task | Command |
|:-----|:--------|
| Preview a move to Cloudflare | `mimeo delegate example.com --dns cloudflare --dry-run` |
| Move | `mimeo delegate example.com --dns cloudflare` |
| Move back | `mimeo delegate example.com --dns porkbun` |

Copies every record except NS and SOA from the provider serving the zone now, reads the copies back to confirm them, and only then sets the nameservers at the registrar. Copies are DNS-only. The old provider's records are left in place. `--dns` defaults to `defaults.dns`.

`delegate` refuses when DNSSEC is enabled for the domain (the registry's DS records point at the current provider's keys), when given a subdomain, and when the current provider is one mimeo cannot read, unless `--empty` is passed to move the zone with no records. Record types the target cannot hold (ALIAS on Cloudflare) are listed and not copied.

### create

| Task | Command |
|:-----|:--------|
| One site | `mimeo create example.com` |
| Several, concurrently | `mimeo create example.com another.lol third.com` |
| A subdomain site | `mimeo create service.example.com --template eleventy-service` |
| A specific template | `mimeo create example.com --template pandoc-simple` |
| A specific repository | `mimeo create example.com --repo someone/portfolio` |
| Keep the zone at Porkbun for this one | `mimeo create example.com --dns porkbun` |
| Preview | `mimeo create example.com --dry-run` |
| Replace an existing repository from the template | `mimeo create example.com --force` |

For each hostname: when the zone sits at a configured DNS provider other than `defaults.dns`, it is moved there first (apex hostnames only; a subdomain never moves its parent zone). Then the repository is created from the template in the template org (which must have its `is_template` flag set), and linked. Nothing is created for a hostname no registered domain covers.

An existing repository is left unchanged and still linked. `--force` **deletes and recreates the repository**, so all content, issues and history are lost; it prompts unless `--yes` is passed. `--skip-dns` leaves nameservers and records alone.

### delete

| Task | Command |
|:-----|:--------|
| Tear down a site | `mimeo delete example.com` |
| Without the prompt | `mimeo delete example.com --yes` |
| Preview | `mimeo delete example.com --dry-run` |

Does what `unlink` does, then deletes the repository serving the hostname, whatever it is called and whichever listed organization it is in. The prompt names the repository. When nothing is linked, it falls back to the repository named after the hostname in the default org, after a full scan confirms no other repository serves the hostname. Needs the `delete_repo` token scope. The registration, nameservers and every other record are left alone.

### scan

`mimeo scan` reads the custom domain of every Pages repository in every organization listed under `github.organizations` and rewrites the cache. It runs by itself the first time a lookup misses. Run it by hand after linking a site outside mimeo, or after adding an organization to the config. It warns when two repositories claim one hostname.

### doctor

Checks Python version, `gh` installation, authentication and `workflow` scope, the config file, that GitHub still lists the eight Pages addresses mimeo writes (from `api.github.com/meta`), that the Porkbun keys are accepted, and that the Cloudflare token is active when one is configured. `mimeo doctor example.com` also checks that the domain's nameservers belong to a provider mimeo can write to.

## Upgrading from 1.x

A 1.x config file loads unchanged, and with no new keys mimeo behaves as before: one organization, Porkbun DNS, Cloudflare-delegated zones shown as `external`. To use what 2.0 adds, set `github.organizations`, add a `[cloudflare]` section, and set `defaults.dns` (see `config.toml.example`).

| 1.x | 2.0 |
|:----|:----|
| A site is the repo named after the domain in one account | A site is whichever repo's custom domain is the hostname, in any listed organization |
| Porkbun's zone is the DNS | The provider named by the nameservers is the DNS |
| `sync --reset-nameservers` | `mimeo delegate ZONE --dns porkbun` |
| `delete --keep-repo` | `mimeo unlink HOSTNAME` |
| `status --source ...`, `--with-dns`, `--health`, `--show-template` | One `status` view; `--records` shows the zone |
| `create` rewrites the zone's managed records | `create` changes only the site's address records |
| No AAAA records | Four AAAA at the apex; the first `sync` adds them |
| Subdomains refused | Subdomains supported |
| A registered domain with no repo is a problem | It is shown as `no site` and is not a problem |

## Development

```bash
uv sync --frozen && uv run pytest && uv run ruff check mimeo && uv run mypy mimeo
```

Linting and type checking are expected to be clean. The read, compare and apply steps are tested against in-memory providers (`tests/fakes.py`), with no HTTP mocking.

## Project structure

```
mimeo/
├── mimeo/
│   ├── connection.py         # Read: Fleet.read -> Connection
│   ├── plan.py               # Compare and apply: compare() -> Plan, apply()
│   ├── operations.py         # link, unlink, delegate
│   ├── cache.py              # Hostname-to-site cache
│   ├── cli/                  # One command per function; _fleet.py builds the providers
│   ├── providers/            # Registrar, DNSProvider, Host, RepoProvider; Porkbun, Cloudflare, GitHub
│   ├── utils/                # HTTP session with error handling, retry with jitter
│   ├── config.py             # Config loading (~/.config/mimeo/config.toml)
│   ├── models.py             # DNSRecord, Site, SiteState
│   └── exceptions.py         # Exception hierarchy + exit codes
├── tests/
├── scripts/
└── docs/
```

## Documentation

| Document | Purpose |
|:---------|:--------|
| [docs/INSTALLATION.md](./docs/INSTALLATION.md) | Prerequisites, install, configuration |
| [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) | Component map, data flows |
| [docs/MIMEO2_DESIGN.md](./docs/MIMEO2_DESIGN.md) | The 2.0 design and the reasons for it |
| [docs/TROUBLESHOOTING.md](./docs/TROUBLESHOOTING.md) | Failure diagnosis and remediation |
| [docs/DECISIONS.md](./docs/DECISIONS.md) | Architectural decision registry |
| [docs/IMPLEMENTATION.md](./docs/IMPLEMENTATION.md) | Phase tracker and task status |

## Known limitations

- One registrar (Porkbun), two DNS providers (Porkbun, Cloudflare), one host (GitHub Pages). The interfaces leave room for more.
- The Cloudflare provider and `delegate` are tested against in-memory providers and mocked HTTP only; they have not been run against a live Cloudflare account (as of 2026-11-15).
- mimeo does nothing about GitHub certificate renewal on proxied Cloudflare records. `status` shows a failed renewal as `cert error` (DEC-043).
- `scan` sees private repositories only in the authenticated account and in organizations it belongs to.
- DNS propagation is not polled; run `mimeo status` afterwards.
