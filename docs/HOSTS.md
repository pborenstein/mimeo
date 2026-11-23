# Hosts Beyond GitHub Pages

Status: **Proposed 2026-11-22, revised 2026-11-23** (DEC-054, DEC-055,
DEC-056). Not scheduled.
Supersedes [NETLIFY.md](NETLIFY.md), which predates 2.0 and assumed
Netlify must take over the domain's DNS. Vendor facts below were read
from the vendors' docs on 2026-11-22 unless a row says otherwise;
anything not confirmed there is listed under
[To Verify](#to-verify).

## Goal

Put pages on the web efficiently: any set of files, at a custom domain,
with HTTPS, using free hosting, with no manual steps after one-time
account setup. GitHub Pages stays. Other hosts are added where they do
something GitHub Pages does not, or do it with less work.

Today mimeo can serve only one kind of thing: a GitHub repository
created from a template, built by GitHub Actions, served by GitHub
Pages. The plan widens both ends:

- **What goes up**: a template, an existing repository, a directory on
  disk, or an archive (`.tar.gz`, `.zip`).
- **Where it goes**: GitHub Pages, Cloudflare (Workers static assets),
  and Netlify. The evaluation below covers six more hosts and says
  why they are left out.

## The Two Ways Files Reach a Host

| Way | What happens | Hosts |
|---|---|---|
| The host builds from a repository | A push to the repo starts a build on the host (or in GitHub Actions), and the output is served | GitHub Pages; Cloudflare Pages and Netlify when linked to a repo |
| mimeo uploads files | mimeo sends a set of already-built files through the host's API, and the host serves them | Cloudflare Workers static assets, Netlify, Vercel, Firebase, Surge, Neocities |

mimeo does not build sites (DEC-054). A directory or archive given to
mimeo is published as it is. A repository that needs a build (every
Eleventy template does) is built where it is built today, in the
repo's GitHub Actions workflow, and the workflow's last step changes
from "deploy to GitHub Pages" to `mimeo publish`. The upload code then
runs in one place, whether it is called from a laptop or from Actions.

## How an Upload Sends Only What Changed

Four of the upload APIs work the same way: the client sends a list of
every file's path and hash, the host answers with the hashes it does not
already have, and the client uploads only those. Then the client marks
the new version live.

| Host | Hash | Ask | Upload | Make live |
|---|---|---|---|---|
| Cloudflare Workers | 32 hex chars of a hash of the file ([direct upload](https://developers.cloudflare.com/workers/static-assets/direct-upload/)) | `POST .../workers/scripts/{name}/assets-upload-session` with a manifest of path, hash and size; answers `buckets` of hashes and a JWT | `POST .../workers/assets/upload` per bucket, multipart, with that JWT; the last answers a completion JWT | `PUT .../workers/scripts/{name}` with `assets.jwt` set to the completion JWT |
| Netlify | SHA1 | `POST /sites/{id}/deploys` with `files: {path: sha1}`; answers `required` | `PUT /deploys/{id}/files/{path}` | Live when the deploy reaches `ready` |
| Vercel | SHA1 | none; upload first | `POST /v2/files` with `x-vercel-digest` | `POST /v13/deployments` with `files: [{file, sha, size}]` |
| Firebase | SHA256 of the gzipped file | `:populateFiles`, at most 1000 hashes per call; answers `uploadRequiredHashes` | `POST {uploadUrl}/{hash}` with the gzipped file | finalize the version, then create a release |

So republishing a site where one page changed uploads one file. mimeo
keeps no record of what it uploaded before; the host's answer is the
record. The manifest must still list every file, including unchanged
ones (Cloudflare and Firebase say so in their docs).

One module, `mimeo/bundle.py`, reads a directory or archive into a list
of paths, sizes and file locations, and computes whichever hash a host
asks for, once per file. It skips `.git/` and `.DS_Store`, and it
checks the host's file-count and file-size limits before anything is
sent.

GitHub Pages has no upload API usable from outside Actions:
`POST /repos/{owner}/{repo}/pages/deployments` requires an
`oidc_token` "issued by GitHub Actions" and an artifact that belongs to
the repository ([Pages REST API](https://docs.github.com/en/rest/pages/pages)).
For a directory, mimeo pushes the files to the repo's `gh-pages` branch
with `git`, after a depth-1 fetch of that branch, so git sends only the
files that changed. The site is served from that branch with
`build_type: legacy` and a `.nojekyll` file.

## Hosts Evaluated

| Host | Upload API | Repo builds | Custom domain + HTTPS, free | DNS it needs | Free limits that matter | Verdict |
|---|---|---|---|---|---|---|
| GitHub Pages | No (Actions only) | Yes | Yes | A/AAAA at apex, CNAME at `www` | 1 GB per site, 100 GB/month soft, 10 builds/hour soft (not for Actions builds); no online business ([limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)) | Keep. Add directory publishing by branch push |
| Cloudflare Workers static assets | Yes, hash-based | Not used here | Yes; Cloudflare creates the DNS records and certificate | Zone must be on the same Cloudflare account | 20,000 files, 25 MiB per file; requests to static assets "free and unlimited" ([limits](https://developers.cloudflare.com/workers/platform/limits/), [billing](https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/)) | **Add after Netlify**, for uploaded files |
| Cloudflare Pages | Only through Wrangler in the docs; REST endpoints exist but the upload flow is not documented ([direct upload](https://developers.cloudflare.com/pages/get-started/direct-upload/)) | Yes; `source` on project create, GitHub app setup unclear | Yes | Apex: zone on the account; subdomain: CNAME to `<project>.pages.dev` | 100 projects, 500 builds/month | Not used. Workers does uploads with a documented API, and Cloudflare says "Start new projects with Workers" |
| Netlify | Yes, hash-based; also zip | Yes; `repo` on the site | Yes | Apex A `75.2.60.5`, or ALIAS to `apex-loadbalancer.netlify.com`; subdomain CNAME to `<site>.netlify.app` ([custom domains](https://docs.netlify.com/domains-https/custom-domains/)). Netlify DNS is optional | This account is on a legacy plan, so the [credit limits](https://docs.netlify.com/manage/accounts-and-billing/billing/billing-for-credit-based-plans/how-credits-work/) for newer free accounts do not apply. API deploys: 3 per minute, 100 per day | **Already in use: six sites.** First host to add, starting with reading them |
| Vercel | Yes, hash-based | Yes | Yes; records come from `GET /v6/domains/{domain}/config` | Read at run time from that endpoint | 100 deployments/day, 200 projects; Hobby is "personal or non-commercial use" only ([terms](https://vercel.com/legal/terms) §4) | Not planned. Works, but adds nothing Workers and Netlify lack, and the terms restrict use |
| Firebase Hosting | Yes, hash-based | No | Yes; `requiredDnsUpdates` lists records | Read at run time | 10 GB stored, 360 MB/day transfer on Spark ([pricing](https://firebase.google.com/pricing)); API is `v1beta1`; Google service-account auth | Not planned. Daily transfer cap and heavier auth |
| Surge | Yes, whole site as a gzipped tar per deploy ([API](https://surge.sh/docs/api/)) | No | Yes, free ([platform](https://surge.sh/docs/platform/)) | Not confirmed | Size limits not read | Not planned. Re-sends every file each deploy; DNS target unverified |
| Neocities | Yes; `upload_hash` skips unchanged files ([API](https://neocities.org/api)) | No | Paid only ($5/month Supporter) | n/a | 1 GB free | Out: custom domains cost money |
| Codeberg Pages | No; webhook or Forgejo Action ([docs](https://docs.codeberg.org/codeberg-pages/)) | Yes | Yes | CNAME/ALIAS to `codeberg.page` plus a TXT record | Pages v2 "disabled for new users"; [Terms of Use](https://codeberg.org/Codeberg/org/src/branch/main/TermsOfUse.md) §2(1)7 bar projects mostly written by AI tools | Out |
| Render | Not for static sites | Yes | Yes | CNAME | Hobby includes 2 custom domains | Out: repo-only, two domains |

### Why Cloudflare Workers is the host for uploaded files

- 24 of the fleet's 109 hostnames are on Cloudflare (2026-11-22,
  Entry 98), and `defaults.dns` is `cloudflare`. Workers needs the
  zone on the account, which is already true for every new site.
- The certificate is Cloudflare's own. The sequence in DEC-050 exists
  because GitHub cannot renew a certificate behind Cloudflare's proxy.
  A site served by Workers never needs it.
- Finding sites is one call: `GET /accounts/{id}/workers/domains`
  lists every hostname with the Worker (`service`) serving it. GitHub
  needs one call per repository.
- Static requests are not counted against anything on the free plan.
- The upload is documented end to end as REST calls, with no CLI.

### The Netlify sites that already exist

Read from the Netlify API and public DNS on 2026-11-23. All six build
from GitHub repos on push, with HTTPS forced.

| Netlify site | Hostnames | Repo (branch) | Build, output | DNS |
|---|---|---|---|---|
| `plywood-violin` | plywoodviolin.com | `pborenstein/plywood-violin` (main) | `npm run build`, `_site` | Netlify |
| `estherlol` | esther.lol | `pborenstein/esther.lol` (main) | `npm run build`, `dist` | Netlify |
| `twohorses` | twohorses.lol, twohorses.net (alias) | `pborenstein/twohorses` (main) | `npm run build`, `dist` | .lol on Netlify; .net on Porkbun, A `75.2.60.5` |
| `tania-project` | www.tania-project.com | `pborenstein/tania-project` (master) | `eleventy`, `dist` | Netlify |
| `dev-pborenstein` | pborenstein.dev | `pborenstein/pborenstein.2025.dev` (main) | `npm run build`, `_site` | Netlify |
| `pborenstein` | pborenstein.com | `pborenstein/pborenstein.2025` (main) | `npm run build`, `_site` | Netlify |

Before 2.2.0 mimeo could not see any of them. `status` showed all seven
hostnames as `no site`, six with DNS `external` and twohorses.net with
DNS `porkbun`. That had three consequences, which 2.2.0 addresses:

- **`create` can take a live site's domain.** `no site` reads as free.
  `mimeo create twohorses.net` would treat it as unused and replace the
  record that points it at Netlify.
- **One repo can serve two hosts.** `pborenstein/twohorses` builds
  twohorses.lol on Netlify and tequitl.dev on GitHub Pages. `mimeo
  delete tequitl.dev` deletes the repo, which is the source of
  twohorses.lol. The deployed site would stay up, but it could no
  longer be rebuilt.
- **The fleet view is incomplete.** Certificate and DNS problems on
  these sites do not appear in `status`.

Netlify therefore comes before Cloudflare Workers in the order of work,
and its first job is reading what exists (DEC-056).

### Netlify DNS and outside DNS

Both are in use, and mimeo supports both. Existing domains stay where
they are; nothing moves them.

- **On Netlify DNS** (plywoodviolin.com, esther.lol, twohorses.lol,
  tania-project.com, pborenstein.dev, pborenstein.com): a new `NetlifyDNS` provider reads and writes the zone through
  `/dns_zones`. Netlify's nameservers are NS1's (`dns1.p01.nsone.net`,
  and `p02` for pborenstein.dev), which other NS1 customers also use, so
  the provider confirms the zone is in the account instead of matching
  on the nameserver names alone.
- **On outside DNS** (twohorses.net today): Netlify is a host like
  GitHub Pages. It asks for an apex A `75.2.60.5` or a CNAME to
  `<site>.netlify.app`, and mimeo writes them at Porkbun or Cloudflare.
  New Netlify sites default to this, following `defaults.dns`. DEC-033's
  nameserver move is no longer required, but it remains a valid state.

## What Changes in mimeo

### A site is whatever the host calls a site

DEC-040 says a site is the repository whose Pages custom domain is the
hostname. That becomes: a site is the object at a host whose
custom-domain setting names the hostname. `Site` already carries the
host (`github:owner/repo`).

| Host | `Site` | Where the hostname is recorded | Full scan |
|---|---|---|---|
| `github` | `github:owner/repo` | Pages `cname` | one call per Pages repo in each organization |
| `cloudflare` | `cloudflare:<worker name>` | Workers custom domain | `GET .../workers/domains`, one call |
| `netlify` | `netlify:<site name>` | `custom_domain` and `domain_aliases` | `GET /sites`, paged |

Two hosts claiming one hostname is a problem `status` reports, like
two repos claiming one today.

Netlify differs from GitHub Pages in three ways the shared code has to
handle:

- **One site can have several hostnames** (`custom_domain` plus
  `domain_aliases`). `set_custom_domain(site, hostname)` assumes one, so
  it becomes `add_hostname` and `remove_hostname`, and `SiteState`
  reports a list.
- **The primary name can be `www`** (tania-project.com). The scan files
  `www.example.com` under the `example.com` row.
- **A site records its repo** (`build_settings.repo_path`). Every host
  reports its source repo, if any, so `delete` can tell when a repo
  also feeds another site. `delete` then removes only the site and
  keeps the repo, and says which other site uses it.

### Interfaces

`Host` gains:

| Method | What it does | GitHub Pages | Cloudflare | Netlify |
|---|---|---|---|---|
| `accepts_files` | Whether `publish` works | Only for a branch-served repo | Yes | Yes |
| `create_site(name)` | Makes an empty site | Repo provider does it, as today | Upload a Worker with no files yet | `POST /sites` |
| `delete_site(site)` | Removes it | Repo provider, as today | Delete the Worker | `DELETE /sites/{id}` |
| `publish(site, bundle)` | Uploads only missing files, makes the new set live | `git` push to `gh-pages` | The three Workers calls above | Netlify deploy |
| `records_owned_by_host(label)` | True when the host writes the records at a name itself | No | Yes | Yes on Netlify DNS; no on outside DNS |
| `source_repo(site)` | The repo the site builds from, if any | The repo itself | None, or the repo set at create | `build_settings.repo_path` |

`required_records` stays. For Cloudflare it returns nothing and
`records_owned_by_host` returns true, and `plan.py` does not add or
remove address records at those names. It checks the custom domain's
state instead. That is the change to DEC-045's "mimeo owns the address
records at a site's own names" rule: it owns them unless the host
does.

`Fleet` takes a list of hosts instead of one. `Fleet.host_for(site)`
picks by the `Site.host` prefix; `scan` asks every host and merges.
The cache already stores `host:ref` strings.
`operations.py`'s "No host named ..." check stays, against the list.

### Config

```toml
[defaults]
host = "github"            # where `create` puts a new site

[cloudflare]
api_token = "..."          # gains Workers Scripts: Edit
account_id = "..."

[netlify]
api_token = "..."
team = "..."               # account slug
```

`defaults.host` comes back, as DEC-030 said it would once a second
host exists. A host with no config section is not configured, as with
DNS providers today.

### Commands

| Command | Change |
|---|---|
| `create HOSTNAME` | Takes `--host NAME`, and `--from PATH` as an alternative to `--template`. `--from` makes an empty site and publishes the directory or archive. `--template` with an upload host makes the repo, sets the secrets its workflow needs, and lets the first workflow run publish |
| `publish HOSTNAME PATH` | New. Finds the site, reads PATH, uploads what is missing. Refuses a GitHub Pages site built by a workflow, and prints how to change it to branch serving |
| `status` | A `HOST` column |
| `sync` | Per host: records for GitHub and Netlify, custom-domain state for Cloudflare |
| `delete` | Deletes the host's site. Deletes the repo too when there is one, with today's confirmation |
| `doctor` | Checks each configured host's credentials |

### Templates (in the tepiton meta-repo, not mimeo)

Each template's `pages.yml` builds to `_site/` and then deploys to
GitHub Pages. It gains a branch on a repository variable: when
`MIMEO_HOST` is set, the last step runs `mimeo publish` with the
host's token from repository secrets, instead of the Pages deploy
steps. `create --template X --host cloudflare` sets the variable and
the secrets through the GitHub API. The path-prefix step that reads the
Pages `cname` reads a `MIMEO_HOSTNAME` variable in that case.

## Walk-Throughs

**A directory to a new domain on Cloudflare.**
`mimeo create example.com --host cloudflare --from ./site`.
The zone is moved to Cloudflare if it is not there (`delegate`). mimeo
uploads a Worker `example-com` with the files, attaches `example.com`
and `www.example.com` as custom domains, and waits for the domain state
to be active. No records are written by mimeo.

**Updating it.** `mimeo publish example.com ./site`. mimeo hashes the
files; Cloudflare answers with the ones it lacks; only those go up.

**A template site on Cloudflare.**
`mimeo create example.com --host cloudflare --template eleventy-folio`.
mimeo creates the repo, sets `MIMEO_HOST`, `MIMEO_HOSTNAME` and the
token secret, creates the empty Worker, and attaches the domain. The
first push's workflow builds and runs `mimeo publish`.

**A directory on GitHub Pages.**
`mimeo create example.com --from ./site` (default host). mimeo creates
an empty repo, pushes the files to `gh-pages` with `.nojekyll`, turns
Pages on with `build_type: legacy` from that branch, and continues as
`link` does today.

**Moving an existing GitHub Pages site to Cloudflare.** Not in the first
passes. It needs: create the Worker, publish the site's built output,
remove the GitHub records at the site's names (Cloudflare refuses a
custom domain where a CNAME exists), attach the domain, then remove the
GitHub custom domain. The site is unreachable between removing the
records and the domain becoming active.

## Order of Work

Each step can ship on its own.

1. **Several hosts in one fleet.** `Fleet` with a list of hosts, routing
   by `Site.host`, `defaults.host`, the `HOST` column. Tested with two
   fake hosts in `tests/fakes.py`. No new vendor code.
2. **See and protect the Netlify sites.** Done in 2.2.0, ahead of step
   1, with a read-only class, `NetlifyReader` (DEC-057). All seven
   hostnames have real rows in `status`; `create` and `link` refuse a
   hostname a Netlify site holds; `delete` keeps a repo Netlify builds
   from. `NetlifyHost` and `NetlifyDNS` replace that class in step 3.
3. **Manage and create Netlify sites.** `sync` for Netlify sites, then
   `create --host netlify`, linking a repo so Netlify builds on push.
   This is how those sites already work, and templates need only a
   `netlify.toml`.
4. **Files to GitHub Pages and Netlify.** `bundle.py`, `publish`,
   `create --from`: branch push for GitHub, hash-checked deploy for
   Netlify.
5. **Cloudflare host.** `providers/host/cloudflare.py`: create, publish,
   custom domains, scan, state, delete; `records_owned_by_host` in
   `plan.py`. Then `create --host cloudflare --from`.
6. **Template sites on Cloudflare.** The workflow change in the
   templates, and `create --template --host cloudflare` setting the
   variable and secrets.
7. **Moving a site between hosts.** The sequence in the last
   walk-through, as a command.

The task list for this work is in
[IMPLEMENTATION.md](IMPLEMENTATION.md), Phase 9.

## To Verify

| Claim | How to check |
|---|---|
| A Worker can be uploaded with static assets and no script code | Upload one with only `assets` metadata to a scratch name; the [static assets docs](https://developers.cloudflare.com/workers/static-assets/) describe assets-only Workers through Wrangler |
| The endpoint that creates a Workers custom domain (the create page returned 404 on 2026-11-22; list is `GET /accounts/{id}/workers/domains`) | Read the Workers domains section of the API reference again |
| What the DNS record Cloudflare makes for a Workers custom domain looks like through the DNS records API, so `plan.py` can leave it alone | Attach a domain on 002370.xyz and list the zone |
| `www` behavior: whether both names are attached and serve the same files, or `www` redirects. GitHub Pages redirects `www` to the apex | Try both on the scratch domain; a redirect needs a Cloudflare redirect rule or a few lines of Worker script |
| Which hash Workers wants: the docs say only "a 32 hexadecimal character hash"; their example truncates SHA-256 | Upload with truncated SHA-256 and see it accepted |
| The legacy plan's actual limits (the user reports generous limits; the numbers were not read) | The account's billing page |
| Netlify certificate state values from `GET /sites/{id}/ssl` | Read them from an existing site; this is a read-only call |
| How Netlify DNS represents site records through `/dns_zones/{id}/dns_records` (Netlify's own record types may appear) | Read the zone for esther.lol |
| Linking a repo through the API on this account (the `repo` object takes `installation_id`) | Read the values from an existing site's `build_settings`, then link a scratch site |
| Worker name limits (length, characters) for `example-com` style names | API reference for script upload |

## Calls Made Here

| Call | Reason |
|---|---|
| mimeo does not build | Builds already run in each template's Actions workflow; running npm locally would make mimeo depend on every template's toolchain |
| Workers static assets, not Cloudflare Pages | Workers' upload is documented as REST; Pages' is documented only through Wrangler. Cloudflare recommends Workers for new projects. Pages' one advantage, subdomains on outside DNS, is covered by GitHub Pages and Netlify |
| Uploads use each host's hash check, with no local record | The host already knows what it has; a local record can go stale |
| GitHub directory publishing pushes a branch | The Pages deployments API needs an Actions OIDC token |
| Netlify comes before Cloudflare Workers | Six live sites are invisible to mimeo, and two of its commands can damage them |
| Existing Netlify domains stay on their current DNS; new ones follow `defaults.dns` | Moving working DNS gains nothing. Netlify documents outside-DNS records, and 2.0 keeps DNS providers separate from hosts |
| The workflow calls `mimeo publish` instead of host-specific deploy actions | One upload implementation; host-specific logic stays in mimeo, not in every template |
| Vercel, Firebase, Surge, Neocities, Codeberg, Render are not planned | See the evaluation table; each fails on cost, terms, efficiency, or API |
