# mimeo 2.0: Design

Status: **Implemented 2026-11-15** on branch `mimeo-2.0-design`
(Entry 91, DEC-046). Written in one pass at the user's request, so
that the design could be read whole instead of decided question by
question. It builds on DEC-039 to DEC-045 in
[DECISIONS.md](DECISIONS.md) and on the notes in
[MIMEO2.md](MIMEO2.md). Where the code ended up different from this
document, [As Built](#as-built) says how; the rest of the text is
left as it was designed.

## What 2.0 Does

mimeo connects a hostname to the site that serves it and keeps the
connection correct (DEC-039). Four things have to agree for a site to
load at `example.com`:

| Thing | Held by | 2.0 reads it from |
|---|---|---|
| The registration | Registrar (Porkbun) | Porkbun API |
| The nameservers | Registrar | Porkbun API |
| The DNS records | Whichever DNS provider the nameservers name | That provider's API (Porkbun or Cloudflare) |
| The site and its custom-domain setting | Host (GitHub Pages) | GitHub API |

1.x reads these in different places in different commands, and each
command has its own idea of what is wrong and what to do about it.
2.0 does it once.

## How Every Command Works

Every command runs the same three steps.

1. **Read.** For a hostname, collect the four things above into one
   record: the zone it belongs to, the zone's nameservers, which
   configured DNS provider those nameservers belong to (DEC-041), the
   records at that provider, and the site whose custom-domain setting
   names the hostname (DEC-040), with its certificate and HTTPS state.
2. **Compare.** Ask the host which records the site needs. Compare
   them, and the host's settings, with what was read. The result is a
   list of changes; each change says where it applies (registrar, DNS
   provider, host), what it does, and why.
3. **Apply.** Carry out the changes, or print them.

The commands differ only in what they do before and after:

| Command | Before the three steps | After |
|---|---|---|
| `status [HOSTNAME...]` | nothing | Prints what was read and the list of changes. Applies nothing. |
| `sync [HOSTNAME...]` | nothing | Applies the changes. |
| `link HOSTNAME [SITE]` | Sets the host's custom domain to HOSTNAME | Applies the changes, then waits for the certificate and enforces HTTPS |
| `unlink HOSTNAME` | nothing | Removes the site's records and the host's custom domain |
| `delegate ZONE --dns PROVIDER` | Copies the zone to PROVIDER (DEC-042) | Sets the nameservers. Applies nothing else. |
| `create HOSTNAME` | `delegate` if the zone is not at the default DNS provider; creates the repo from a template | `link` |
| `delete HOSTNAME` | `unlink` | Deletes the repo, with the confirmation 1.x has |
| `scan` | nothing | Rebuilds the cache of hostname-to-site pairs (DEC-040) |
| `doctor` | nothing | Checks tools, config, and credentials for every configured provider |

Every command that changes something takes `--dry-run`, which prints
the list of changes and stops. `status` and `sync` cannot disagree
about what is wrong, because `sync` applies the list `status` prints.

`SITE` is `github:owner/repo`. Left out, it is
`github:<default_org>/<hostname>`.

## What Counts as a Site's Records

mimeo owns the address records at a site's own names and nothing
else in the zone (DEC-045).

| Site | Names | Records the GitHub Pages host asks for |
|---|---|---|
| Apex (`example.com`) | `example.com`, `www.example.com` | Four A and four AAAA at the apex; `www` CNAME to `<owner>.github.io` |
| Subdomain (`service.example.com`) | `service.example.com` | One CNAME to `<owner>.github.io` |

"Address records" means A, AAAA, CNAME and ALIAS. At a site's names:

- a required record that is missing gets added;
- an address record that is not required gets removed. [GitHub's
  docs](https://docs.github.com/en/pages/getting-started-with-github-pages/securing-your-github-pages-site-with-https)
  (read 2026-11-15) say extra records at these names can stop the
  certificate from being issued.

Everything else is left alone: MX and TXT records at the apex, every
record at any other name, and each record's Cloudflare proxy setting
(DEC-043). This rule is what lets several sites share a zone and
keeps mail records safe.

`<owner>` is the owner of the linked repo, so the `www` record for
gilborenstein.com points to `tepiton.github.io` and the one for
blueberryhill.fyi to `pborenstein.github.io`.

## What `status` Reports

One row per hostname. The rows are the registrar's domains plus every
hostname in the cache.

| Finding | Counted as a problem | Fixed by `sync` |
|---|---|---|
| Required record missing or wrong | yes | yes |
| Extra address record at a site's name | yes | yes |
| Certificate ready, HTTPS not enforced | yes | yes |
| Certificate not issued, in an error state, or expiring within 30 days | yes | no |
| Nameserver lookup returns nothing | yes | no |
| Two repos claim the same hostname | yes | no |
| Nameservers belong to no configured provider | no (shown as `external`, DEC-037) | no |
| Registered domain with no site | no (shown as `no site`) | no |
| Records proxied | no (shown in a column) | no |

The certificate row is how a failed renewal on a proxied domain
becomes visible. mimeo does not act on it (DEC-043).

## Config

Schema version 2. The file stays at `~/.config/mimeo/config.toml`.

```toml
schema_version = 2

[defaults]
template = "mimeo"
dns = "cloudflare"          # where `create` and `delegate` put a zone
ignore_domains = []

[porkbun]
api_key = "..."
secret_key = "..."

[cloudflare]
api_token = "..."
account_id = "..."

[github]
default_org = "mimeo-sites"
organizations = ["mimeo-sites", "tepiton", "pborenstein"]
template_org = "mimeo-templates"
```

A version 1 file still loads. `organizations` defaults to
`[default_org]`, `defaults.dns` defaults to `porkbun`, and with no
`[cloudflare]` section Cloudflare is not a configured provider. A 1.x
setup upgraded to 2.0 with no config change behaves as it did on 1.x,
including treating Cloudflare-delegated domains as `external`.

## Code Layout

```
mimeo/
  connection.py      step 1: read everything about a hostname
  plan.py            step 2: compare, produce the list of changes
  cache.py           hostname-to-site pairs (DEC-040)
  providers/
    base.py          Registrar, DNSProvider, Host, RepoProvider
    registrar/porkbun.py
    dns/porkbun.py
    dns/cloudflare.py
    host/github_pages.py
    repo/github.py   repo work split out of GitHubHost (DEC-044)
  cli/               one module per command
```

The interfaces:

| Interface | Methods |
|---|---|
| `Registrar` | list domains; get nameservers; set nameservers (takes the list); DNSSEC enabled? |
| `DNSProvider` | its nameservers for a zone; zone exists?; create zone; list records; add record; delete record |
| `Host` | find the site for a hostname within given organizations; get and set custom domain; required records for a hostname; certificate state; enforce HTTPS; health |
| `RepoProvider` | create from template (with the `is_template` check, DEC-034); delete; rename |

- `plan.py` talks only to these interfaces and holds no vendor
  knowledge. It is tested against in-memory fakes of the four
  interfaces, with no HTTP mocking.
- `dns/cloudflare.py` calls the Cloudflare API with the HTTP client
  the Porkbun code already uses. No new dependency.
- `DNSRecord` gains an optional `proxied` field, which only the
  Cloudflare provider fills in.
- `cli/status.py` (991 lines, with a separate code path per
  `--source` view) shrinks to formatting what steps 1 and 2 return.
- Exit codes do not change (DEC-027, DEC-028).

## Walk-Throughs

**A newly registered domain.**

```
mimeo create example.com
```

The zone is on Porkbun's nameservers and `defaults.dns` is
`cloudflare`, so `create` copies the zone to Cloudflare, sets the
nameservers, creates `mimeo-sites/example.com` from the default
template, sets its custom domain, writes the A, AAAA and `www`
records at Cloudflare, waits for the certificate, and enforces HTTPS.

**Moving an existing Porkbun-served site to Cloudflare.**

```
mimeo delegate example.com --dns cloudflare --dry-run
mimeo delegate example.com --dns cloudflare
mimeo status example.com
```

Every record is copied and compared before the nameservers change.
The site's records come across with the rest, so `status` has nothing
to report once the new nameservers are visible.

**Moving back.** `mimeo delegate example.com --dns porkbun`. This
replaces `sync --reset-nameservers`.

**A site that already exists in another account.**

```
mimeo scan
mimeo status blueberryhill.fyi
```

`scan` finds `pborenstein/blueberryhill.fyi` by its custom domain.
No `link` is needed; the link already exists at the host.

**A subdomain site.**

```
mimeo create service.example.com
```

The zone is `example.com`. One CNAME named `service` is added; the
apex site's records are not touched.

## Changes From 1.x

| 1.x | 2.0 |
|---|---|
| A site is the repo named after the domain under `github_username` | A site is whichever repo's custom domain names the hostname, in any listed organization |
| Porkbun's zone is the DNS | The provider named by the nameservers is the DNS |
| `sync --reset-nameservers` | `delegate ZONE --dns porkbun` |
| `status --source porkbun` | `status --source registrar` |
| `create` clears and rewrites the zone's records (DEC-035) | `create` changes only the site's address records |
| No AAAA records | Four AAAA at the apex |
| Subdomains refused | Subdomains supported |

## Order of Work

Each step leaves the tests passing and can be released or stopped at.

| Step | Work | Ships as |
|---|---|---|
| 1 | Repo/host split (DEC-044). Template org default changed from `tepiton` to `mimeo-templates`. | 1.4.0 |
| 2 | The four interfaces; Porkbun DNS code reshaped to list/add/delete; `connection.py` and `plan.py`; `status` and `sync` moved onto them with unchanged behavior on Porkbun-served domains | 2.0 branch |
| 3 | `github.organizations`, the cache, `scan`; site found by custom domain | 2.0 branch |
| 4 | Cloudflare DNS provider; provider chosen by nameservers; `doctor` checks | 2.0 branch |
| 5 | `link`, `unlink`; `create` and `delete` rebuilt on them | 2.0 branch |
| 6 | `delegate` | 2.0 branch |
| 7 | Subdomains; AAAA records | 2.0 branch |
| 8 | README, ARCHITECTURE, `scripts/e2e_smoke.sh` extended to delegate a junk domain to Cloudflare and back | 2.0.0 |

After step 4, `status` reads the real records for blueberryhill.fyi
and xhosi.com. That is the first point where 2.0 does something 1.x
cannot, and it involves no writes to Cloudflare.

## Calls Made Here

Choices no DEC entry covers yet, each with its reason.

- **One read, one comparison, shared by every command.** The Entry 90
  bug (DEC-037) came from `status` and `sync` each having their own
  notion of what was fixable. With one list of changes there is one
  notion.
- **`delete` stays, as `unlink` plus repo deletion.** `create` and
  `delete` are the pair that makes and removes a repo; `link` and
  `unlink` are the pair that never touches one. `unlink` has no
  `--delete-repo` flag, which changes the sketch in MIMEO2.md.
- **`defaults.dns` in config.** `create` needs to know where a new
  zone goes without a flag on every run. `create --dns` and
  `delegate --dns` override it.
- **AAAA records are written.** This closes the backlog item. GitHub's
  docs list them alongside the A records, mimeo.lol already has them,
  and `doctor` already sees the IPv6 addresses in GitHub's list
  (DEC-036). The hardcoded list gains the four IPv6 addresses under
  the same `doctor` check. First `sync` on 2.0 adds four records to
  every apex site on a configured provider.
- **mimeo owns address records at a site's names and removes extras
  there.** Narrower than 1.x's clear-and-recreate, wide enough to
  remove a leftover record that blocks a certificate.
- **Netlify is not in 2.0.** The `Host` interface and the `SITE`
  prefix leave room for `netlify:`. Two open decisions in
  [NETLIFY.md](NETLIFY.md) are overtaken and get redone when Netlify
  is picked up: "unmanaged records at the NS switch" (DEC-042 now
  copies every record) and "where the host choice lives" (the site
  reference in the cache now carries it, found by asking each
  configured host).
- **A version 1 config loads and behaves as 1.x did.** Upgrading does
  not change what mimeo does until `organizations`, `[cloudflare]` or
  `defaults.dns` is set.
- **No Cloudflare SDK.** The provider needs six calls.

## To Verify at Implementation

Not checked against vendor docs as of 2026-11-15:

- Whether creating a Cloudflare zone through the API needs the
  account ID (assumed above), and which token permissions cover zone
  creation, record reads and record writes.
- Whether Cloudflare imports records on its own when a zone is
  created through the API (DEC-042).
- How Porkbun's API reports that DNSSEC is enabled for a domain.
- How long GitHub takes to issue a certificate after AAAA records
  are added to a domain that had only A records, and whether adding
  them disturbs an issued certificate.

## As Built

Differences between the text above and the code (2026-11-15):

- **Certificate expiry warning is 14 days, not 30.** xhosi.com's
  renewal was already failing with 27 days left, so GitHub starts
  renewing at about 30 days. A 30-day threshold would flag every
  healthy site for a while on each renewal.
- **Two repos claiming one hostname is reported by `scan`**, as a
  warning, not as a `status` row. Only a scan sees both claims; the
  cache keeps the first.
- **Site lookup scans less often than DEC-040 says.** A lookup that
  misses the cache tries `<organization>/<hostname>` in each listed
  organization. It then runs a full scan only when the cache has
  never been filled by one, or when the caller is `delete`. After the
  first scan, a site in a differently named repo that was linked
  outside mimeo is found by running `mimeo scan`. A scan costs one
  API call per Pages repository, which is too much for every
  `status` of a domain that has no site.
- **`link` does not wait for the certificate unless given `--wait`**
  (up to 15 minutes). Without it, a pending certificate is reported
  and `sync` enforces HTTPS later, as `create` did in 1.x.
- **`link` has `--skip-dns`**, and `create` keeps it.
- **A record being added takes the proxy setting in use at its
  name.** This keeps DEC-043's rule that mimeo never changes how a
  name is served.
- **A proxied name is not asked for more A or AAAA records** once
  it has some of the required ones. Cloudflare answers for a proxied
  name over IPv4 and IPv6 itself, so the four AAAA records would add
  nothing. Found on the first live Cloudflare read (2026-11-16):
  blueberryhill.fyi and xhosi.com have proxied A records only and
  were shown as `missing`.
- **`status` has one view.** `--source`, `--with-dns`, `--health` and
  `--show-template` are gone; `--records` shows the zone. There is no
  `--source registrar`.
- **A registered domain with no site is not a problem.** In 1.x it
  was.
- **Nameservers are read from the registrar's API**, not public DNS,
  so they are current as soon as `delegate` sets them.
- **Layout.** `link`, `unlink` and `delegate` are functions in
  `mimeo/operations.py`; their commands and `scan` are in
  `cli/connect.py`; `cli/_fleet.py` builds the providers. The Porkbun
  DNS provider stayed in `providers/registrar/porkbun.py` next to the
  registrar, since they share one API client.
- **`scan` sees private repositories** in the authenticated account
  and in organizations it belongs to, by using the endpoints that
  list them; other accounts are listed publicly.
- **Step 1 did not ship separately.** It is commit `62eeff7` on the
  same branch, with version 1.4.0, and can be released from there.

Checked against live APIs (read-only, 2026-11-15): Porkbun's
`getNs` response, the GitHub Pages certificate fields, and the scan
across `mimeo-sites`, `tepiton` and `pborenstein` (72 sites found,
including tequitl.dev served by `pborenstein/twohorses`). Not run
live: anything that writes, the Cloudflare provider, `delegate`, and
Porkbun's DNSSEC lookup. The items under "To Verify at
Implementation" are still unverified.
