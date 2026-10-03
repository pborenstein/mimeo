# Netlify as a Second Host

Status: **Proposed design** — not yet decided or scheduled. Open questions
are listed at the end; once settled they should be promoted to
`DECISIONS.md`. This is the second host that DEC-030 anticipated ("revisit
the factory if a second registrar or host lands"). Sibling of
`docs/SITE_ADDRESS.md` (proposed); the two share the repo-provisioning
work but do not depend on each other. The DNS mode is decided (DEC-033):
Netlify's nameservers. The remaining open questions are listed at the end.

## Goal

The same promise as today on a second host: one command takes a domain
from nothing to a live HTTPS site, and Netlify builds the site from the
same tepiton template repos.

| Task | Command |
|------|---------|
| Deploy a Netlify-hosted site | `mimeo create example.com --host netlify` |
| View the fleet across both hosts | `mimeo status --all` |
| Converge a site on either host | `mimeo sync example.com` |
| Tear down a site on either host | `mimeo delete example.com` |

## The Problem in One Paragraph

The `Host` ABC (`providers/base.py`) allows a second host, but nothing
else does. The CLI constructs `GitHubHost` by name in five commands
(`create.py:130,303`, `status.py:480,631,879`, `sync.py:167`,
`delete.py:112`), and DEC-030 removed the `defaults.host` config fields
because no factory existed. `GitHubHost.deploy_site` (`github.py:753`)
also combines two jobs that Netlify splits apart: it creates the source
repository (template generate, manifest substitution, dev-file strip,
topics, Website field) and it serves the site (Pages enable, custom
domain, HTTPS). A Netlify deploy still needs the first job — Netlify
builds from the GitHub repository — and replaces the second. Netlify's
recommended DNS setup adds a third change: the domain's nameservers move
to Netlify, so Porkbun stops serving DNS. That affects
`check_nameservers`, `sync --reset-nameservers`, and DEC-031's
"nameservers are never touched" rule.

## Behavior Today

There is nothing to change yet: no `--host` flag and no Netlify code.
`[defaults] host` was removed from config (DEC-030); a leftover key in
an existing config is ignored, so reintroducing it breaks nothing. A
user who wants Netlify today configures the site by hand in the web UI.

## What the Netlify Flow Is

Netlify's CLI works like `gh`: `netlify login` (browser) or
`NETLIFY_AUTH_TOKEN` for non-interactive use, and
`netlify api <operation> --data '{...}'` for raw JSON API calls
(operation names from open-api.netlify.com). Every step mimeo needs can
be done through the API:

| Step | Endpoint | Notes |
|------|----------|-------|
| Verify auth | `netlify status` | the `gh auth status` equivalent |
| Create site | `POST /sites` | in the team's account slug |
| List linkable repos | `GET /{account_slug}/repos` | only repos the Netlify GitHub App can see |
| Link site to repo | `PUT /sites/{site_id}/repo` | `{repo_id, branch}`; `cmd`/`dir` optional when the repo has a `netlify.toml` |
| Add custom domain | `POST /sites/{site_id}/domains` | apex and www separately |
| Create DNS zone | `POST /dns_zones` | response includes the assigned nameservers (NS1: `dns1.pXX.nsone.net` ...) |
| Ensure site records exist | `GET`/`POST /dns_zones/{zone_id}/dns_records` | Netlify writes the apex/www records itself when the domain is attached; this is the fallback if the API path does not (verify during implementation) |
| Check / provision cert | `GET`/`POST /sites/{site_id}/ssl` | empty POST body = Let's Encrypt |
| Force HTTPS | `PATCH /sites/{site_id}` | `{"force_ssl": true}` |

The CLI documents no command for repo association — `netlify init` is
an interactive wizard — so the API `PUT` is the automation path.

### The DNS setup

**The design: move the nameservers to Netlify (decided, DEC-033).**
Mimeo creates the zone, attaches the domain to the site, then updates
the domain's NS at Porkbun (`POST /domain/updateNameServers/{domain}`;
the request replaces the whole list). Netlify writes the site records
(apex and www) itself when the domain is attached, so mimeo does not
write them, and the certificate is issued automatically once the zone
answers. Any other records in the Porkbun zone are left in place but
stop being served; switching NS back restores them. The failure mode
is a quiet outage. Porkbun email forwarding, for example, stops
working with no error until someone notices. `delete` should restore
Porkbun's nameservers; otherwise the domain stops resolving entirely.

**Rejected: keep DNS at Porkbun (mode B).** The existing DNS code
would be reused unchanged, with only the record values changed (apex
A → `104.198.14.52`, www CNAME → `{site}.netlify.app`), and the
nameserver move and its risks would not exist. Rejected because it
leaves mimeo writing and checking DNS records, and because the
certificate is issued only after the records propagate — `create`
would end `https_pending` and `sync` would finish the job, the same
loop as today's Pages certificate handling with more waiting. The
point of moving to Netlify is that Netlify manages the DNS.

## Prerequisites and Constraints

| Constraint | What it means |
|------------|---------------|
| Netlify GitHub App installed on the site-repos org | One-time, in the browser, per org — the one step that cannot be scripted. Without it the repos do not appear in `GET /{account_slug}/repos` and linking fails |
| DNS zones are unique across all Netlify accounts | One NS1 namespace. If the domain's zone exists under any Netlify account, `POST /dns_zones` fails |
| Site subdomains are globally unique | The domain with dots as dashes can collide; on collision, use another name |
| Deploy order: zone and domain attachment, then NS switch, then certificate | An NS switch before the zone exists stops the whole domain resolving; each partial state must be fixable by `sync`, as with today's deploy ordering |
| DNSSEC enabled at Porkbun blocks the NS switch | The registry's DS records point at Porkbun's keys; switching NS without updating them stops the whole domain resolving for validating resolvers, and this breaks the site as well as the leftover records |
| Free-tier build minutes are a shared monthly pool | Pages builds are unmetered. Not an issue for landing pages; a ceiling for a large fleet |
| Netlify tokens are account-wide | No per-operation scopes like `gh`'s `repo`/`workflow` |

## To Verify at Implementation

Claims this design uses but has not verified. Verified vendor behavior
cited in the text says so; anything below is still an assumption.

| Claim | How to check |
|-------|--------------|
| Attaching a domain to a site creates the apex/www zone records through the API, with no browser step (the UI flow does this; the user confirmed the end state 2026-10-02) | Add a domain to a scratch site via `netlify api`, then read the zone's records |
| A way exists to detect DNSSEC state before refusing the NS switch — the Porkbun API may not expose it | Check the Porkbun API docs; fallback is a DNS query for the domain's DS records |
| The build image's pandoc version runs pandoc-resume's build | Deploy pandoc-resume to a scratch site |

## What Needs to Happen

Seven changes, in dependency order: the [repo/host split](#change-1),
[`NetlifyHost`](#change-2), and [host selection](#change-3) deliver a
working second host; the [registrar nameserver work](#change-4) and the
[fleet-command updates](#change-5) follow; [config](#change-6) and
[templates](#change-7) support both.

<a id="change-1"></a>

**1. Split `GitHubHost` into a repo provider and a Pages host.**

`GitHubHost` currently does two jobs; separate them.

Moves to a repo provider (`providers/repo/github.py`):

- `_create_from_template` (`github.py:275`), including force and
  rename-recovery handling
- manifest fetch and apply
- dev-file strip
- topics and the Website field
- repo delete and rename

Stays in `GitHubHost`:

- Pages enable
- custom domain
- HTTPS enforcement
- health

`NetlifyHost` uses the same repo provider: a Netlify deploy still
creates a GitHub repository from the same tepiton template. The
pipeline-branch change in `SITE_ADDRESS.md` needs the same split, so
doing it first means that design lands on it instead of doing it over
again.

<a id="change-2"></a>

**2. Add `NetlifyHost`** (`providers/host/netlify.py`).

A subprocess wrapper around `netlify api`, built like
`_run_gh_command`/`_gh_api` (`github.py:107,158`), including pulling
the HTTP status out of error output into `HostError.status_code` — the
DEC-027/028 exit-code mapping then works unchanged.

- `deploy_site`: create the repo with the `netlify` host topic (repo
  provider from [change 1](#change-1), topic from [change 3](#change-3)),
  create the site, link the repo, add the custom domain, attempt
  force-HTTPS
- `teardown_site`: delete the site; the custom domain goes with it
- health: `GET /sites/{id}/ssl` plus deploy state, behind a classifier
  like `health_status`
- `required_dns_records`: none — the zone records are Netlify-internal

<a id="change-3"></a>

**3. Host selection, recorded on the repo.**

`--host {github,netlify}` on `create`, default github. The choice is
written where later commands can read it: the repository topics.
`create` already tags repos `mimeo, landing-page, github-pages`; a
Netlify site gets `netlify` in place of `github-pages`. The record
exists today and nothing reads it.

To read it, `status`/`sync`/`delete` keep their single-source
enumeration (repos tagged `mimeo`, one API call they already make),
take the host from the topic list, and talk to exactly one host
provider. `list_mimeo_repositories` moves from `gh search repos --json`,
which has no `topics` field (checked against gh 2.102), to
`gh api search/repositories`, which returns `topics` per repo
(verified against tepiton 2026-10-02).

There is no second provider sweep and no domain matching across
providers, and a domain cannot be claimed by both hosts — the topic is
the record. Switching hosts is `create --force --host <other>`, which
recreates the repo and rewrites the topics. No local state file.

<a id="change-4"></a>

**4. Registrar nameserver update + Netlify zone.**

- `PorkbunRegistrar.set_nameservers(domain, ns)` — wraps
  `POST /domain/updateNameServers/{domain}`
- `check_nameservers` takes the expected nameservers as a parameter —
  Porkbun defaults for github-hosted domains, the zone's assigned NS
  for netlify-hosted ones
- a Netlify DNS provider — creates the zone, attaches the domain, and
  verifies the site records are present, creating the two only if
  Netlify did not (see the flow table)

Record-level drift checking does not apply on this host: Netlify owns
the records it serves, so drift becomes "NS still Netlify's, domain
still attached."

<a id="change-5"></a>

**5. Update the fleet commands for two hosts.**

Each command reads the host from the repo topic and then applies that
host's answers.

- `status`: host column; a health classifier per host
- `sync`: NS check against the serving host's expectation; record
  drift for github-hosted domains, NS-and-attachment for netlify-hosted
  ones; `force_ssl` when the certificate is ready
- `delete`: restore the Porkbun NS and delete the Netlify project —
  amends DEC-031's "nameservers are never touched" to "restored to
  registrar defaults for hosts that own the zone." Deleting the project
  removes the site, its custom domains, and the DNS zone; there is
  nothing else to clean up on the Netlify side
- `doctor`: `netlify` installed and authenticated when that host is
  selected; remediation text for the GitHub App prerequisite

<a id="change-6"></a>

**6. Config and auth.** `[netlify]` section (`account_slug`; token
from `MIMEO_NETLIFY_AUTH_TOKEN`/`NETLIFY_AUTH_TOKEN` or
`netlify login`), schema_version 2. `config.py:12` imports template
defaults from the GitHub provider; those constants move to a neutral
module as part of the [repo/host split](#change-1).

<a id="change-7"></a>

**7. Give templates a `netlify.toml`.**

Netlify ignores the Pages workflow files. Per-repository configuration
lives in a `netlify.toml` at the repo root, which Netlify reads from
the linked repo at build time. It carries:

- the build command and publish directory
- the build environment (`NODE_VERSION`)
- build plugins
- redirects (e.g. www to apex)
- custom headers

That is most of the per-template configuration the host needs, with no
mimeo code — the generate copies the file into every site repo. When
the repo has a `netlify.toml`, the repo-link call can omit
`cmd`/`dir`. Keep `mimeo.template.json` for domain substitution only
(DEC-024). `--host netlify` rejects templates with no `netlify.toml`,
naming them.

## What Does NOT Need to Change

- **The content pipeline.** Template generate, manifest substitution,
  and dev-file strip run the same way for both hosts; that is the
  result of the [repo/host split](#change-1).
- **Error handling and exit codes.** `HostError.status_code` carries
  Netlify API failures through the existing mapping.
- **The registrar ABC** — `set_nameservers` is additive.
- **Porkbun DNS for github-hosted sites**, unchanged.
- **Concurrency, output formats, `--log-format json`.**

## Open Decisions

| # | Question | Recommendation | Rationale |
|---|----------|----------------|-----------|
| 1 | DNS mode | **Decided (2026-10-02)**: A — delegate the nameservers to Netlify (DEC-033) | Netlify owns the records and the certificate; mode B rejected — see "The DNS setup" |
| 2 | Unmanaged records at the NS switch | Print the Porkbun-zone records the switch will stop serving, then proceed (skippable with `--yes`); refuse only when DNSSEC is enabled at Porkbun | The records are not deleted — switching NS back restores them — so the failure is a quiet outage, not a loss, and a warning is enough. DNSSEC is the only case where the switch breaks the site as well (the registry's DS records point at Porkbun's keys) |
| 3 | `delete` on a Netlify-DNS domain | **Decided (2026-10-02)**: delete the Netlify project, restore the Porkbun NS | Deleting the project removes the site, its custom domains, and the DNS zone together (user-verified 2026-10-02) — nothing else to clean up on the Netlify side. The NS restore is required: once the zone is deleted, nameservers still pointing at Netlify stop the domain resolving |
| 4 | Netlify site naming | Domain with dots as dashes; accept Netlify's suffix on collision | The site name is an implementation detail (same reasoning as SITE_ADDRESS #7's `--repo`); the domain is the identity and join key |
| 5 | Where build configuration lives | `netlify.toml` in templates | Netlify reads it from the repository after generate; keeps the manifest single-purpose |
| 6 | pandoc-resume on Netlify | **Decided (2026-10-02)**: build it like the others — a `netlify.toml` with the build command, no plugin | The build image ships pandoc (verified against Netlify's build-image docs 2026-10-02; an earlier draft of this row claimed the opposite). Check at implementation that the installed version runs pandoc-resume's build |
| 7 | Certificate convergence | Copy the Pages lifecycle: `create` attempts force-HTTPS and reports `https_pending`; `sync` finishes when the certificate state says ready | The `https_pending`/`fixable` handling already exists; only the state names differ |
| 8 | Where the host choice lives | On the repository topic, written by `create`: `github-pages` today, `netlify` for Netlify sites; `[defaults] host` returns together with the factory | The record is already on every repo, unread; fleet commands keep one enumeration source and no local state file is needed. The config field waits for the factory per DEC-030's rule — no config option until it works |

## Suggested Staging

Three passes, each independently landable and testable:

1. **[Repo/host split](#change-1)**: a pure refactor with no behavior
   change; the existing tests are the check.
2. **Netlify create path** — [`NetlifyHost`](#change-2), the [host
   topic](#change-3), [config](#change-6), the templates'
   [`netlify.toml`](#change-7), and the zone and nameserver steps of
   the [registrar work](#change-4). `create --host netlify` works end
   to end: site, repo link, custom domain, zone, NS switch with the
   record warning and the DNSSEC refusal, certificate attempt.
3. **Fleet correctness** — the rest of the [registrar work](#change-4)
   (expected NS in checks) and the [fleet commands](#change-5):
   host-aware `status`/`sync`/`delete` and the DEC-031 amendment.

Smallest slice worth shipping: passes 1 and 2, for one static
template — everything `create` needs.

Change 1 is worth landing even if the Netlify work stops:
`SITE_ADDRESS.md` needs the same split, and it turns `github.py` — the
project's largest module — into two smaller ones.

## Appendix: Code Touch-Points

Where each change lands, for implementation planning only. Referenced
against `main` at `4f6c03b`.

| Change | Where | Notes |
|--------|-------|-------|
| [1 — repo/host split](#change-1) | `providers/host/github.py` → `providers/repo/github.py` (new) + `github.py` | move `_create_from_template` (:275) plus manifest/dev-strip/topics/homepage/rename/delete; `deploy_site` (:753) composes them; template constants leave the host module (`config.py:12` import) |
| [2 — `NetlifyHost`](#change-2) | `providers/host/netlify.py` (new) + `tests/providers/host/test_netlify.py` | wrapper built like `_run_gh_command`/`_gh_api` (:107, :158); health classifier like `health_status` (:38); teardown like `teardown_site` (:830) |
| [3 — host selection](#change-3) | `cli/create.py:130,303`; factory in `cli/_processing.py` | `--host` flag; repo topics gain the host tag; `list_mimeo_repositories` switches to `gh api search/repositories` for topics; `status.py:480,631,879`, `sync.py:167`, `delete.py:112` read the host from the repo data |
| [4 — NS update + zone](#change-4) | `providers/registrar/porkbun.py`; `providers/dns/netlify.py` (new) | `set_nameservers` → `POST /domain/updateNameServers/{domain}`; expected-NS parameter on `check_nameservers` |
| [5 — fleet commands](#change-5) | `cli/status.py`, `cli/sync.py`, `cli/delete.py`, `cli/doctor.py` | host read from the topic; host column, per-host NS expectation, DEC-031 amendment, netlify doctor checks |
| [6 — config](#change-6) | `mimeo/config.py`, `config.toml.example` | `[netlify]` section, schema_version 2, env overrides |
| [7 — templates](#change-7) | tepiton template repos + TEMPLATES/CLAUDE.md inventory | `netlify.toml` per template; rejection gate list |
| tests | `tests/` | Regression: github-hosted fixtures unchanged. New: netlify deploy/teardown against mocked `netlify api` output, NS switch ordering, record warning, DNSSEC refusal |
