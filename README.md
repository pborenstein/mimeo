# Mimeo

Connects a domain to the site that serves it, and keeps the connection correct. For a site to load at `example.com`, four things have to agree. Mimeo reads all four, shows what disagrees, and fixes what it can.

| What has to agree | Where it lives |
|:------------------|:---------------|
| The registration | [Porkbun](https://porkbun.com) |
| The nameservers | Porkbun, set to Porkbun's or [Cloudflare](https://cloudflare.com)'s |
| The DNS records | Whichever of Porkbun or Cloudflare the nameservers name |
| The custom-domain setting | The GitHub repository that serves the site, or a [Netlify site](#netlify-sites), which mimeo reads and does not change |

## Quick start

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

Prerequisites, the `gh` token scopes, global versus development install, and environment variable overrides are in [docs/INSTALLATION.md](./docs/INSTALLATION.md).

## How it works

Every command runs the same three steps on each hostname.

1. Read the four things above, plus the site's certificate and HTTPS state.
2. Compare them with what the site needs. The result is a list of changes.
3. Print the changes (`status`) or apply them (`sync`).

The other commands do one thing before or after those steps: `link` sets the custom domain first, `delegate` moves the zone first, `create` makes the repository first.

### Which repository serves a hostname

The repository whose GitHub Pages custom domain is the hostname, in any organization or account listed under `github.organizations`. The repository's name does not matter.

mimeo caches the pairs it finds in `~/.cache/mimeo/sites.json`. The custom-domain setting stays the authority, and a cached pair is confirmed against it before use. See [`scan`](#scan).

### Netlify sites

If the `netlify` command-line tool is installed and logged in, mimeo reads that account's sites and never changes them. `status` shows each one with `(netlify)` after its repository, and `sync` skips it. `create` and `link` refuse a hostname a Netlify site serves. `delete` refuses such a hostname, and keeps a repository a Netlify site builds from.

### Which records mimeo touches

mimeo owns the address records (A, AAAA, CNAME, ALIAS) at a site's own names, and nothing else in the zone. `<owner>` is the owner of the repository serving the site.

| Site | Names | Records GitHub Pages needs |
|:-----|:------|:---------------------------|
| Apex (`example.com`) | `example.com`, `www.example.com` | Four A and four AAAA at the apex; `www` CNAME to `<owner>.github.io` |
| Subdomain (`service.example.com`) | `service.example.com` | One CNAME to `<owner>.github.io` |

At those names a missing record is added, and an address record that is not needed is removed. MX and TXT records and records at any other name are left alone. A record's Cloudflare proxy setting is left alone too. Only [`mimeo proxy`](#proxy) changes it.

## Commands

| Command | What it does |
|:--------|:-------------|
| [`status`](#status) | Shows what was read, the changes `sync` would make, and each problem `sync` cannot fix with the steps that fix it |
| [`sync`](#sync) | Applies the changes |
| [`link`](#link-and-unlink) | Sets a site's custom domain to a hostname, then syncs it |
| [`unlink`](#link-and-unlink) | Removes the site's records and its custom domain |
| [`delegate`](#delegate) | Moves a zone to another DNS provider, asking first when that would stop a service |
| [`proxy`](#proxy) | Turns on Cloudflare's proxy for sites, with the HTTPS settings they need |
| [`create`](#create) | `delegate` if needed, a new repository from a template, then `link` |
| [`delete`](#delete) | `unlink`, then deletes the repository |
| [`scan`](#scan) | Rebuilds the cache of which repository serves which hostname |
| [`doctor`](#doctor) | Checks tools, config and credentials |

### status

| Task | Command |
|:-----|:--------|
| Check specific hostnames | `mimeo status example.com service.example.com` |
| Every registered domain and known site | `mimeo status --all` |
| Only hostnames that need attention, with details | `mimeo status --all --problems` |
| Every record in the zone, from the provider serving it | `mimeo status example.com --records` |
| For scripting | `mimeo status --all --format json \| jq '.[] \| select(.fixable)'` |

A bare `mimeo status` refuses to run; a fleet sweep needs `--all`. Findings exit 0. API errors exit nonzero with partial results.

#### Columns

| Column | Values |
|:-------|:-------|
| `EXPIRES` | Registration expiry; `elsewhere` for a hostname registered outside this Porkbun account that DNS answers for; `-` for a subdomain, or a hostname not at the registrar that nothing answers for |
| `RENEW` | `off` when the registration will not renew automatically; blank when it will, or when it does not apply |
| `DNS` | `porkbun`, `cloudflare`, `netlify`, `external` (a provider or account mimeo cannot read), `none` (no nameservers); a trailing `*` when the site's records are proxied |
| `RECORDS` | `ok`, `missing`, `extra`, `external` (not compared), `netlify` (managed by Netlify), `unknown` |
| `SITE` | `ok`, `fixable`, `pending`, `no cert`, `cert error`, `expiring`, `no pages`, `no domain`, `unknown` (a proxied zone's HTTPS settings could not be read), `no site` |
| `REPO` | The repository whose custom domain is the hostname, or the one a Netlify site builds from, marked `(netlify)` |

What each value means and what to do about it is in [docs/TROUBLESHOOTING.md](./docs/TROUBLESHOOTING.md#reading-a-status-row). A registered domain with no site, a zone at an external provider, and proxied records are not problems.

#### Detail lines

When hostnames are named, or with `--problems`, detail lines follow each row. The steps name the hostname, the commands and the page to open.

| Line | Meaning |
|:-----|:--------|
| `sync would:` | A change `mimeo sync` makes |
| `problem:` | Something `sync` cannot change, stated in a sentence |
| `to fix:` | Numbered steps for that problem, done in order |
| `do one of:` | Alternatives for that problem; pick one |
| `note:` | Something worth knowing that is not a problem, such as a hostname registered outside this account |

```
  example.com      2027-08-31         cloudflare*  ok   fixable     mimeo-sites/example.com
      sync would: set Cloudflare SSL/TLS for example.com to a fixed Full mode with Always Use HTTPS on
  operation.rodeo  -                  -            -    no domain   mimeo-sites/operation.rodeo
      problem: operation.rodeo is not in the registrar account and nothing answers for it in DNS, so the registration has most likely lapsed. The repository mimeo-sites/operation.rodeo is still set up to serve it.
      do one of:
        - Keep the repository and take the domain off it: mimeo unlink operation.rodeo
        - Delete the repository: mimeo delete operation.rodeo
        - Move the repository to another account: open https://github.com/mimeo-sites/operation.rodeo/settings, scroll to Danger Zone, click Transfer ownership
        - Get the domain back: register operation.rodeo again, then run: mimeo sync operation.rodeo
```

In JSON and CSV output the steps are the `fixes` field, and `fixes_are_choices` says whether they are alternatives.

### sync

| Task | Command |
|:-----|:--------|
| Preview | `mimeo sync --all --dry-run` |
| Apply to every site | `mimeo sync --all` |
| Apply to specific hostnames | `mimeo sync example.com` |

| Finding | What `sync` does |
|:--------|:-----------------|
| A needed address record is missing | Adds it |
| An address record at the site's names is not needed | Removes it |
| Site not fully proxied: no certificate, a failed renewal, or a certificate within 14 days of expiry | Removes the custom domain and sets it again |
| Site not fully proxied: certificate approved, HTTPS not enforced | Enforces HTTPS |
| Site fully proxied: the zone's Cloudflare HTTPS settings are wrong | Sets them |
| A Netlify site | Skips it |

Problems `sync` cannot fix are printed with the same steps `status` prints.

#### Certificates

This section is about sites that are not fully proxied. GitHub requests a certificate at the moment the custom domain is saved, and issues it only if it can reach the site directly. That is why setting the domain again works. Verified 2026-11-16 on five sites with no certificate; GitHub approved the first within 20 seconds.

`sync` requests a certificate only when the records are already right. A site with wrong records takes two runs a few minutes apart: records, then the request. A further run enforces HTTPS once the certificate is approved.

If the domain cannot be set again, the error gives the `mimeo link` command that puts it back.

#### Proxied records

When every name of a site is proxied, Cloudflare answers visitors with its own certificate, which it issues and renews itself. mimeo then ignores GitHub's certificate for that site and checks two settings on the zone. `sync` sets them if they are wrong:

| Cloudflare setting | Value |
|:-------------------|:------|
| SSL/TLS encryption mode | Full, with Automatic off |
| Always Use HTTPS | On |

`sync` never turns the proxy on or off; [`mimeo proxy`](#proxy) turns it on. The token needs the Zone Settings: Edit permission. The reasons are in [docs/CERTIFICATES.md](./docs/CERTIFICATES.md).

#### What sync leaves alone

| Not changed | Changed by |
|:------------|:-----------|
| Nameservers | `mimeo delegate` |
| Which repository serves a hostname | `mimeo link` |
| Whether a record is proxied | `mimeo proxy` to turn it on; Cloudflare's dashboard to turn it off |
| A zone at a provider that is not configured | That provider |

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

`link` works on a site that already exists; it creates nothing. It refuses a hostname another site already serves. Records are written DNS-only.

When the zone is at a provider mimeo cannot write to, `link` sets the custom domain and prints the records to add by hand. Without `--wait`, a certificate that is not ready yet is reported, and `mimeo sync` enforces HTTPS later.

`unlink` removes the address records at the site's names and the custom-domain setting, after a confirmation prompt (`--yes` skips it).

### delegate

| Task | Command |
|:-----|:--------|
| Preview a move to Cloudflare | `mimeo delegate example.com --dns cloudflare --dry-run` |
| Move | `mimeo delegate example.com --dns cloudflare` |
| Move back | `mimeo delegate example.com --dns porkbun` |

To move many domains from Porkbun to Cloudflare at once, Porkbun's own [move to Cloudflare](https://porkbun.com/llms/guides/move-domains-to-cloudflare) also works, and mimeo picks each domain up from its nameservers. `delegate` is the one that reads the records back before changing the nameservers (DEC-053).

`delegate` copies every record except NS and SOA from the provider serving the zone now, reads the copies back, and only then sets the nameservers at the registrar. Copies are DNS-only. The old provider's records are left in place. `--dns` defaults to `defaults.dns`.

#### Services a move would stop

Some records point at a service the current provider runs only for zones it serves. Copying the record does not move the service. When a move would stop one, `delegate` says which and asks before changing anything. `--yes` skips the question, and `--dry-run` lists each as `would stop:`.

| Leaving | Records | What stops |
|:--------|:--------|:-----------|
| Cloudflare | MX pointing at `mx.cloudflare.net` | Cloudflare Email Routing: incoming mail |
| Cloudflare | Any proxied record | Cloudflare's proxy for those names, with whatever is set up on it |

Cloudflare's docs say Email Routing "is available to all Cloudflare customers using Cloudflare as an authoritative nameserver" ([Email Routing](https://developers.cloudflare.com/email-routing/), checked 2026-11-17). Porkbun's mail forwarding is not on the list: Porkbun's guide says it works with DNS hosted elsewhere as long as the MX records point at `fwd1.porkbun.com` and `fwd2.porkbun.com` ([kb.porkbun.com/article/47](https://kb.porkbun.com/article/47-how-to-use-porkbun-email-when-your-dns-is-hosted-elsewhere), checked 2026-11-17), and `delegate` copies them.

#### Refusals

| `delegate` refuses when | Why |
|:------------------------|:----|
| DNSSEC is enabled for the domain | The registry's DS records point at the current provider's keys |
| Given a subdomain | It moves whole zones |
| The current provider is one mimeo cannot read | There is nothing to copy; `--empty` moves the zone with no records |

Record types the target cannot hold (ALIAS on Cloudflare) are listed and not copied.

### proxy

```bash
mimeo proxy example.com --dry-run
mimeo proxy site1.com site2.com
mimeo proxy --all --dry-run
mimeo proxy --all
```

For each site, `proxy` sets the zone to SSL/TLS mode Full with Always Use HTTPS on, turns on the proxy for the site's own address records, and checks that `https://` still answers. If it does not, the proxy is switched back off and the run stops. Mail, TXT and other records are left alone.

It skips, and says why, a hostname with no site, a Netlify site, and a domain whose DNS is not on Cloudflare. `--all` asks first; `--yes` skips the question.

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

For each hostname, `create` runs these steps. Nothing is created for a hostname no registered domain covers.

1. Move the zone to `defaults.dns` if it is at another configured provider. Apex hostnames only; a subdomain never moves its parent zone. When the move would stop a service, the zone stays where it is and the `delegate` command is printed.
2. Create the repository from the template in the template org. The template must have its `is_template` flag set. GitHub copies the files after creating the repository, so `create` waits up to 5 minutes and reports progress. An existing repository is left unchanged.
3. Link the repository to the hostname.

`create` refuses a hostname a Netlify site serves. If a `create` fails partway, rerun it with `--force`: without it, the half-made repository is left unchanged and gets linked.

`--force` deletes and recreates the repository, so all content, issues and history are lost. It prompts unless `--yes` is passed. `--skip-dns` leaves nameservers and records alone.

#### After create

The site is an ordinary GitHub repository. To change it, clone the repo, edit, and push to `main`. The template's GitHub Actions workflow builds the site and deploys it to Pages. Content changes never go through mimeo.

To push without deploying, put `[skip ci]` (or `[no ci]`, `[skip actions]`) in the commit message. See GitHub's [Skipping workflow runs](https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-workflow-runs/skipping-workflow-runs).

### delete

| Task | Command |
|:-----|:--------|
| Tear down a site | `mimeo delete example.com` |
| Without the prompt | `mimeo delete example.com --yes` |
| Preview | `mimeo delete example.com --dry-run` |

`delete` does what `unlink` does, then deletes the repository serving the hostname, whatever it is called and whichever listed organization it is in. The prompt names the repository. It needs the `delete_repo` token scope. The registration, nameservers and every other record are left alone.

It refuses a hostname a Netlify site serves. If a Netlify site builds from the repository, it unlinks the hostname and keeps the repository.

When nothing is linked, it falls back to the repository named after the hostname in the default org, after a full scan confirms no other repository serves the hostname.

### scan

`mimeo scan` reads the custom domain of every Pages repository in every organization listed under `github.organizations` and rewrites the cache. It warns when two repositories claim one hostname.

It runs by itself when a lookup misses and the cache was never filled, or was filled from a different `github.organizations` list. The cache records the list it was built from. Run it by hand after linking a site outside mimeo.

### doctor

| Check | Passes when |
|:------|:------------|
| Python | Version 3.11 or later |
| `gh` | Installed, logged in, token has the `workflow` scope |
| Config file | Present and valid |
| Pages IPs | GitHub still lists the eight Pages addresses mimeo writes (from `api.github.com/meta`) |
| Porkbun keys | Accepted by Porkbun |
| Cloudflare token | Active, when a `[cloudflare]` section is configured |
| Cloudflare settings | The token can read zone settings. Write access is not tested |
| Netlify | The account can be read, when the `netlify` tool is installed |
| Nameservers | `mimeo doctor example.com` only: the domain's nameservers belong to a provider mimeo can write to |

### Global options

These options go before the subcommand and apply to every command. Precedence: CLI flags, then `MIMEO_*` environment variables, then the config file.

| Option | Effect | Default |
|:-------|:-------|:--------|
| `--log-format text` <br> `--log-format json` | Log format for diagnostic output on stderr | `text` |
| `--template-org ORG` | Org holding template repositories | `github.template_org` (`mimeo-templates`) |
| `--deploy-org ORG` | GitHub user or org where site repositories are created | `github.default_org` (required) |

## Upgrading from 1.x

A 1.x config file loads unchanged. With no new keys mimeo behaves as before: one organization, Porkbun DNS, Cloudflare-delegated zones shown as `external`. To use what 2.0 adds, set `github.organizations`, add a `[cloudflare]` section, and set `defaults.dns` (see `config.toml.example`).

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

## Known limitations

- One registrar (Porkbun), two DNS providers (Porkbun, Cloudflare), one host mimeo can change (GitHub Pages). Netlify sites are read only. The plan for more hosts is in [docs/HOSTS.md](./docs/HOSTS.md).
- `delegate` warns only about the two services in [its table](#services-a-move-would-stop). Anything else that depends on the old provider moves without a question.
- Requests to Porkbun start 0.25 seconds apart, so `status --all` over about 100 domains takes about a minute. Whether Porkbun publishes a request limit is unverified; the interval was chosen on 2026-11-16 after unspaced sweeps lost a domain to a 503.
- `scan` sees private repositories only in the authenticated account and in organizations it belongs to.
- DNS propagation is not polled; run `mimeo status` afterwards.

| Path | Run against live services |
|:-----|:--------------------------|
| Reading Cloudflare zones | Yes, 2026-11-16 |
| `delegate` from Porkbun to Cloudflare | Once, 2026-11-16 |
| `delegate` back to Porkbun | Once, 2026-11-17 |
| `sync` removing and adding records in a Cloudflare zone | Once each, 2026-11-17 |
| `sync` setting Cloudflare's HTTPS settings on a proxied zone | Once, on 002370.xyz, 2026-11-23 |
| `proxy` turning on the proxy | Six sites, 2026-11-23 |
| Reading Netlify sites, zones and certificates | Yes, 2026-11-23 |
| Netlify problem reports (expiring certificate, missing record) | No; every live site is healthy |

## Development

```bash
uv sync --frozen && uv run pytest && uv run ruff check mimeo && uv run mypy mimeo
```

Linting and type checking are expected to be clean. The read, compare and apply steps are tested against in-memory providers (`tests/fakes.py`), with no HTTP mocking.

```
mimeo/
├── mimeo/
│   ├── connection.py         # Read: Fleet.read -> Connection
│   ├── plan.py               # Compare and apply: compare() -> Plan, apply()
│   ├── operations.py         # link, unlink, delegate, proxy
│   ├── cache.py              # Hostname-to-site cache
│   ├── cli/                  # One command per function; _fleet.py builds the providers
│   ├── providers/            # Registrar, DNSProvider, Host, RepoProvider; Porkbun, Cloudflare, GitHub, Netlify (read-only)
│   ├── utils/                # HTTP session with error handling, retry with jitter
│   ├── config.py             # Config loading (~/.config/mimeo/config.toml)
│   ├── models.py             # DNSRecord, Site, SiteState, ProxyTLS
│   └── exceptions.py         # Exception hierarchy + exit codes
├── tests/
├── scripts/
└── docs/
```

## Documentation

| Document | Purpose |
|:---------|:--------|
| [docs/INSTALLATION.md](./docs/INSTALLATION.md) | Prerequisites, install, configuration |
| [docs/TROUBLESHOOTING.md](./docs/TROUBLESHOOTING.md) | What each status value means, refusals and errors, and what to do |
| [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) | Component map, data flows |
| [docs/CERTIFICATES.md](./docs/CERTIFICATES.md) | Which certificate a site uses, and the Cloudflare settings for proxied sites |
| [docs/HOSTS.md](./docs/HOSTS.md) | Evaluation of other hosts and the plan for adding them |
| [docs/MIMEO2_DESIGN.md](./docs/MIMEO2_DESIGN.md) | The 2.0 design and the reasons for it |
| [docs/DECISIONS.md](./docs/DECISIONS.md) | Architectural decision registry |
| [docs/IMPLEMENTATION.md](./docs/IMPLEMENTATION.md) | Phase tracker and task status |
| [CHANGELOG.md](./CHANGELOG.md) | Changes by release |
