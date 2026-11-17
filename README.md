# Mimeo

Connects a domain to the site that serves it, and keeps the connection correct. For a site to load at `example.com`, four things have to agree. Mimeo reads all four, shows what disagrees, and fixes what it can.

- registration ([Porkbun](https://porkbun.com))
- nameservers (Porkbun or [Cloudflare](https://cloudflare.com))
- DNS records the provider the nameservers name (Porkbun or Cloudflare)
- the host's custom-domain setting (GitHub)

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

1. Read
   -  For a hostname, collect the zone it belongs to
   -  the zone's nameservers (from the registrar)
   -  which configured DNS provider those nameservers belong to
   -  the records at that provider
   -  and the site whose custom domain is the hostname, with its certificate and HTTPS state
2. Compare
   - Ask the host which records the site needs
   - compare them  and the host's settings with what was read.
   - The result is a list of changes.
3. Print (`status`) or apply (`sync`) the changes

`status` prints the list. `sync` applies it. The other commands do one thing before or after those steps.

| Command | What it does |
|:--------|:-------------|
| [`status`](#status) | Shows what was read, the changes `sync` would make, and each problem it cannot fix with the steps that fix it |
| [`sync`](#sync) | Applies the changes |
| [`link`](#link-and-unlink) | Sets a site's custom domain to a hostname, then syncs it |
| [`unlink`](#link-and-unlink) | Removes the site's records and its custom domain |
| [`delegate`](#delegate) | Moves a zone to another DNS provider, asking first when that would stop a service |
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

At those names a required record that is missing is added, and an address record that is not required is removed. MX and TXT records and records at any other name are left alone. A record's Cloudflare proxy setting is left alone too, except while `sync` gets a certificate issued (see [sync](#sync)). `<owner>` is the owner of the repository serving the site.

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
| `SITE` | `ok`, `fixable` (certificate ready, HTTPS not enforced), `pending`, `no cert`, `cert error`, `expiring` (14 days or less, so renewal is not happening), `no pages`, `no domain` (the hostname is not at the registrar and has no DNS), `no site` |
| `REPO` | The repository whose custom domain is the hostname |

When hostnames are named, or with `--problems`, each row is followed by the changes `sync` would make and by each problem it cannot fix. A problem is stated in a sentence and followed by what to do about it, with the hostname, the commands and the page to open filled in:

```
  xhosi.com  2027-08-31  cloudflare*  ok        cert error  mimeo-sites/xhosi.com
      problem: The HTTPS certificate could not be renewed. It expires 2026-12-12; after that date browsers refuse to open https://xhosi.com.
      to fix:
        1. In the Cloudflare dashboard, open xhosi.com > DNS > Records
        2. Edit each of these and switch Proxy status to DNS only: A @, CNAME www. The proxy is what blocks the certificate.
        3. Open https://github.com/mimeo-sites/xhosi.com/settings/pages
        4. Under Custom domain, click Remove
        5. Type xhosi.com back into Custom domain and click Save
        6. Wait 15 minutes, then run: mimeo status xhosi.com. Repeat until SITE says ok or fixable; it can take an hour.
        7. Switch the same records back to Proxied
```

`to fix:` lists steps to do in order. `do one of:` lists alternatives. A site shown as `no domain` gets alternatives, because the registration has most likely lapsed and the decision is about the repository: `mimeo unlink` to keep it, `mimeo delete` to remove it, GitHub's transfer page to move it, or registering the domain again. mimeo reaches `no domain` only when public DNS says the name has no nameservers; when that lookup cannot be made, it concludes nothing. In JSON and CSV output the steps are the `fixes` field, and `fixes_are_choices` says which kind they are.

A registered domain with no site, a zone at an external provider, and proxied records are not problems. A bare `mimeo status` refuses to run; a fleet sweep needs `--all`. Findings exit 0; API errors exit nonzero with partial results.

### sync

| Task | Command |
|:-----|:--------|
| Preview | `mimeo sync --all --dry-run` |
| Apply to every site | `mimeo sync --all` |
| Apply to specific hostnames | `mimeo sync example.com` |

Adds missing address records, removes extra ones at the site's own names, requests the HTTPS certificate when the site has none, and enforces HTTPS when the certificate is ready.

GitHub requests a certificate at the moment the custom domain is saved, and issues it only if it can reach the site directly. So for a site with no certificate, a failed renewal, or a certificate within 14 days of expiry, `sync` removes the custom domain and sets it again. It does that only when the records are already right: a site with wrong records takes two runs a few minutes apart (records, then the request), and a further run enforces HTTPS once the certificate is approved. Verified 2026-11-16 on five sites with no certificate; GitHub approved the first within 20 seconds. If the domain cannot be set again, the error gives the `mimeo link` command that puts it back.

When the site's records are proxied through Cloudflare, the proxy is what blocks the certificate. `sync` then switches those records to DNS-only, sets the custom domain again, waits up to 15 minutes for the certificate (asking again if a request fails), and switches the records back to proxied. This is the one case in which mimeo changes a proxy setting (DEC-050). If a step fails, the records are switched back before the error is reported. If the certificate does not arrive in 15 minutes, the records are left DNS-only so it still can, and the error says how to switch them back. `status` shows this as `sync would: renew the HTTPS certificate ... (switches A @, AAAA @, CNAME www to DNS-only, ...)`.

Problems `sync` cannot fix are printed with the same steps `status` prints. It does not change nameservers (`delegate`), does not link anything (`link`), does not change a proxy setting, and does not write to a zone at a provider that is not configured.

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

Some records point at a service the current provider runs only for zones it serves. Copying the record does not move the service. When a move would stop one, `delegate` says which and asks before changing anything; `--yes` skips the question, and `--dry-run` lists each as `would stop:`. It knows three cases:

| Leaving | Records | What stops |
|:--------|:--------|:-----------|
| Cloudflare | MX pointing at `mx.cloudflare.net` | Cloudflare Email Routing: incoming mail |
| Cloudflare | Any proxied record | Cloudflare's proxy for those names, with whatever is set up on it |
| Porkbun | MX pointing at `porkbun.com` | Porkbun's mail forwarding or hosting may stop (unverified) |

`create` runs unattended, so when moving the zone would stop a service it leaves the zone where it is, creates the site there, and prints the `delegate` command.

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
- Against a live Cloudflare account, mimeo has read zones and run one `delegate` from Porkbun to Cloudflare (as of 2026-11-16). It has run one `delegate` back to Porkbun (2026-11-17). `sync` writing records to a Cloudflare zone has not been run live.
- `sync` renewing a certificate behind Cloudflare's proxy has run live only on a site whose certificate was still valid (2026-11-17): the proxy was switched off and on and the custom domain set again, in 22 seconds. The same steps done by hand fixed xhosi.com's failed renewal the same day. `sync` has not yet met a failed renewal itself.
- `delegate` warns only about the three services listed under [delegate](#delegate). That Cloudflare Email Routing stops when the zone leaves Cloudflare is from how the service is set up, not checked against Cloudflare's documentation (as of 2026-11-17).
- Requests to Porkbun are spaced 0.25 seconds apart, so `status --all` over about 100 domains takes about a minute. Whether Porkbun publishes a request limit is unverified; the 0.25 seconds is mimeo's choice. The spacing was added on 2026-11-16 after sweeps with five unspaced workers lost a domain to a 503.
- `scan` sees private repositories only in the authenticated account and in organizations it belongs to.
- DNS propagation is not polled; run `mimeo status` afterwards.
