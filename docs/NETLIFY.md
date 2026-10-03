# Netlify as a Second Host

Status: **Proposed design** — not yet decided or scheduled. Open questions
are listed at the end; once settled they should be promoted to
`DECISIONS.md`. This is the second host that DEC-030 anticipated ("revisit
the factory if a second registrar or host lands"). Sibling of
`docs/SITE_ADDRESS.md` (proposed); the two share the repo-provisioning
work but do not depend on each other. Decide the DNS mode first (Open
Decision #1) — it determines whether the registrar changes are in scope
at all.

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
| Link site to repo | `PUT /sites/{site_id}/repo` | `{repo_id, branch}`; `cmd`/`dir` optional when the repo has a `netlify.toml` (change 7) |
| Add custom domain | `POST /sites/{site_id}/domains` | apex and www separately |
| Create DNS zone | `POST /dns_zones` | response includes the assigned nameservers (NS1: `dns1.pXX.nsone.net` ...) |
| Ensure site records exist | `GET`/`POST /dns_zones/{zone_id}/dns_records` | Netlify writes the apex/www records itself when the domain is attached; this is the fallback if the API path does not (verify during implementation) |
| Check / provision cert | `GET`/`POST /sites/{site_id}/ssl` | empty POST body = Let's Encrypt |
| Force HTTPS | `PATCH /sites/{site_id}` | `{"force_ssl": true}` |

Repo association has no non-interactive CLI command (`netlify init` is
an interactive wizard); the API `PUT` is the automation path.

### The DNS mode choice

**Mode A — move the nameservers to Netlify.** This is Netlify's
recommended path and the original motivation. Mimeo creates the zone,
attaches the domain to the site, then updates the domain's NS at
Porkbun (`POST /domain/updateNameServers/{domain}`; the request
replaces the whole list). Netlify writes the site records (apex and
www) itself when the domain is attached, so mimeo does not write them,
and the certificate is issued automatically once the zone answers. Any
other records in the Porkbun zone are left in place but stop being
served; switching NS back restores them. The failure mode is a quiet
outage. Porkbun email forwarding, for example, stops working with no
error until someone notices. `delete` should restore Porkbun's
nameservers; otherwise the domain stops resolving entirely.

**Mode B — keep DNS at Porkbun.** The existing DNS code is reused
unchanged; only the record values change (apex A → `104.198.14.52`,
www CNAME → `{site}.netlify.app`). No nameserver move, no email risk,
`delete` unchanged. The certificate is issued only after the records
propagate, so `create` ends `https_pending` and `sync` finishes the
job — the same loop as today's Pages certificate handling, with more
waiting.

## Prerequisites and Constraints

| Constraint | What it means |
|------------|---------------|
| Netlify GitHub App installed on the site-repos org | One-time, in the browser, per org — the one step that cannot be scripted. Without it the repos do not appear in `GET /{account_slug}/repos` and linking fails |
| DNS zones are unique across all Netlify accounts | One NS1 namespace. If the domain's zone exists under any account, `POST /dns_zones` fails and the fix is a Netlify support ticket |
| Site subdomains are globally unique | The domain with dots as dashes can collide; take the suffix Netlify assigns |
| Mode A order: zone and domain attachment, then NS switch, then certificate | An NS switch before the zone exists stops the whole domain resolving; each partial state must be fixable by `sync`, as with today's deploy ordering |
| DNSSEC enabled at Porkbun blocks the NS switch | The registry's DS records point at Porkbun's keys; switching NS without updating them stops the whole domain resolving for validating resolvers, and this breaks the site as well as the leftover records |
| Free-tier build minutes are shared — 300/month across all sites | Pages builds are unmetered. Not an issue for landing pages; a ceiling for a large fleet |
| Netlify tokens are account-wide | No per-operation scopes like `gh`'s `repo`/`workflow` |

## What Needs to Happen

Seven changes, in dependency order. Changes 1–3 plus mode B deliver a
working second host; 4–5 are the mode A work and the fleet updates;
6–7 are the config and template work both modes need.

**1. Split `GitHubHost` into a repo provider and a Pages host.** Move
the repository half — `_create_from_template` (`github.py:275`) with
its force and rename-recovery handling, manifest fetch and apply,
dev-file strip, topics, Website field, repo delete/rename — into a repo
provider (e.g. `providers/repo/github.py`). `GitHubHost` keeps Pages
enable, custom domain, HTTPS, and health. `NetlifyHost` uses the same
repo provider: a Netlify deploy still creates a GitHub repository from
the same tepiton template. `SITE_ADDRESS.md` change 2 needs the same
split, so doing it first means that design lands on it instead of
doing it over again.

**2. Add `NetlifyHost`** (`providers/host/netlify.py`). A subprocess
wrapper around `netlify api`, built like `_run_gh_command`/`_gh_api`
(`github.py:107,158`) — including pulling the HTTP status out of error
output into `HostError.status_code`, so the DEC-027/028 exit-code
mapping works unchanged. `deploy_site`: create the repo with the
`netlify` host topic (changes 1 and 3), create the site, link the repo,
add the custom domain, attempt force-HTTPS. `teardown_site`: delete the
site; the custom domain is deleted with it. Health: `GET /sites/{id}/ssl`
plus deploy state behind a classifier like `health_status`.
`required_dns_records`: mode B returns the two load-balancer records;
mode A returns none, because the zone records are Netlify-internal.

**3. Host selection, recorded on the repo.** `--host {github,netlify}`
on `create`, default github. The choice is written where later
commands can read it: the repository topics. Every site already
carries its host as a topic — `create` tags repos `mimeo,
landing-page, github-pages` — and a Netlify site gets `netlify` in
place of `github-pages`. The record exists today and nothing reads it.
`status`/`sync`/`delete` keep their single-source enumeration (repos
tagged `mimeo`, one API call they already make), read the host from
the topic list, and talk to exactly one host provider;
`list_mimeo_repositories` adds `topics` to the fields it requests. No
second provider sweep, no domain matching across providers, and a
domain cannot be claimed by both hosts — the topic is the record.
Switching hosts is `create --force --host <other>`, which recreates
the repo and rewrites the topics. No local state file.

**4. Registrar nameserver update + Netlify zone (mode A only).**
`PorkbunRegistrar.set_nameservers(domain, ns)` wrapping
`POST /domain/updateNameServers/{domain}`; `check_nameservers` takes
the expected nameservers as a parameter (Porkbun defaults for
github-hosted domains, the zone's assigned NS for netlify-hosted
ones). A Netlify DNS provider creates the zone, attaches the domain,
and verifies the site records are present, creating the two only if
Netlify did not (see the flow table). Record-level drift checking does
not apply on this host: Netlify owns the records it serves, so drift
becomes "NS still Netlify's, domain still attached."

**5. Update the fleet commands for two hosts.** Each command reads the
host from the repo topic and then applies that host's answers.
`status`: host column and a health classifier per host. `sync`: NS
check against the serving host's expectation; record drift for
github-hosted domains, NS-and-attachment for netlify-hosted ones;
`force_ssl` when the certificate is ready. `delete`:
amend DEC-031's "nameservers are never touched" to "restored to
registrar defaults for hosts that own the zone" — restore the Porkbun
NS and delete the site; the leftover Netlify zone is harmless, and
deleting it goes behind a flag because it may carry email. `doctor`:
check that `netlify` is installed and authenticated when that host is
selected, plus remediation text for the GitHub App prerequisite.

**6. Config and auth.** `[netlify]` section (`account_slug`; token
from `MIMEO_NETLIFY_AUTH_TOKEN`/`NETLIFY_AUTH_TOKEN` or
`netlify login`), schema_version 2. `config.py:12` imports template
defaults from the GitHub provider; those constants move to a neutral
module as part of change 1.

**7. Give templates a `netlify.toml`.** Netlify ignores the Pages
workflow files; per-repository configuration lives in a
`netlify.toml` at the repo root, which Netlify reads from the linked
repo at build time. Besides the build command and publish directory it
carries the build environment (`NODE_VERSION`), build plugins,
redirects (e.g. www to apex), and custom headers — most of the
per-template configuration the host needs, with no mimeo code: the
generate copies the file into every site repo. When the repo has a
`netlify.toml`, the repo-link call can omit `cmd`/`dir` (change 2).
Keep `mimeo.template.json` for domain substitution only (DEC-024).
`--host netlify` rejects templates with no `netlify.toml`, naming
them.

## What Does NOT Need to Change

- **The content pipeline.** Template generate, manifest substitution,
  and dev-file strip run the same way for both hosts; that is the
  result of change 1.
- **Error handling and exit codes.** `HostError.status_code` carries
  Netlify API failures through the existing mapping.
- **The registrar ABC** — `set_nameservers` is additive.
- **Porkbun DNS for github-hosted sites**, unchanged.
- **Concurrency, output formats, `--log-format json`.**

## Open Decisions

| # | Question | Recommendation | Rationale |
|---|----------|----------------|-----------|
| 1 | DNS mode: A (delegate NS), B (external), or B then A | A is the stated destination; do B first only if the registrar work would delay the first Netlify site | B reuses the existing DNS code and is easy to undo; A is Netlify's recommended path with automatic certificates, but it moves the zone, brings the email risk, and changes delete semantics and NS checks. Decide before scheduling change 4 |
| 2 | Unmanaged records at the NS switch (mode A) | Print the Porkbun-zone records the switch will stop serving, then proceed (skippable with `--yes`); refuse only when DNSSEC is enabled at Porkbun | The records are not deleted — switching NS back restores them — so the failure is a quiet outage, not a loss, and a warning is enough. DNSSEC is the only case where the switch breaks the site as well (the registry's DS records point at Porkbun's keys) |
| 3 | `delete` on a Netlify-DNS domain | Restore Porkbun NS and delete the site by default; zone deletion behind a flag | Leaving NS at a deleted zone breaks resolution; a leftover zone is only clutter, and may carry email someone still wants |
| 4 | Netlify site naming | Domain with dots as dashes; accept Netlify's suffix on collision | The site name is an implementation detail (same reasoning as SITE_ADDRESS #7's `--repo`); the domain is the identity and join key |
| 5 | Where build configuration lives | `netlify.toml` in templates | Netlify reads it from the repository after generate; keeps the manifest single-purpose |
| 6 | pandoc-resume on Netlify | Out of scope initially; covered by the change-7 rejection gate | Netlify's build image has no pandoc, but `netlify.toml` build plugins are the documented way to add one; validating a pandoc plugin is its own investigation. 10 of 11 templates are npm-build or static |
| 7 | Certificate convergence | Copy the Pages lifecycle: `create` attempts force-HTTPS and reports `https_pending`; `sync` finishes when the certificate state says ready | The `https_pending`/`fixable` handling already exists; only the state names differ |
| 8 | Where the host choice lives | On the repository topic, written by `create`: `github-pages` today, `netlify` for Netlify sites; `[defaults] host` returns together with the factory | The record is already on every repo, unread; fleet commands keep one enumeration source and no local state file is needed. The config field waits for the factory per DEC-030's rule — no config option until it works |

## Suggested Staging

Two passes, each independently landable and testable:

1. **Second host, familiar DNS** — changes 1, 2, 3 (create side), 6,
   7, with mode B records. `create --host netlify` works end to end on
   external DNS; the GitHub path is unchanged; change 1 lands as a pure
   refactor with the existing tests as the check.
2. **Netlify DNS (mode A) and fleet correctness** — changes 4, 5: the
   NS move, the Netlify zone, the MX gate, host-aware
   `status`/`sync`/`delete`, and the DEC-031 amendment.

Smallest slice worth shipping: change 1 + `NetlifyHost` + `--host` on
`create`, for one static template.

Change 1 is worth landing even if the Netlify work stops:
`SITE_ADDRESS.md` needs the same split, and it turns `github.py` — the
project's largest module — into two smaller ones.

## Appendix: Code Touch-Points

Where each change lands, for implementation planning only. Referenced
against `main` at `4f6c03b`.

| Change | Where | Notes |
|--------|-------|-------|
| 1 — repo/host split | `providers/host/github.py` → `providers/repo/github.py` (new) + `github.py` | move `_create_from_template` (:275) plus manifest/dev-strip/topics/homepage/rename/delete; `deploy_site` (:753) composes them; template constants leave the host module (`config.py:12` import) |
| 2 — `NetlifyHost` | `providers/host/netlify.py` (new) + `tests/providers/host/test_netlify.py` | wrapper built like `_run_gh_command`/`_gh_api` (:107, :158); health classifier like `health_status` (:38); teardown like `teardown_site` (:830) |
| 3 — host selection | `cli/create.py:130,303`; factory in `cli/_processing.py` | `--host` flag; repo topics gain the host tag; `list_mimeo_repositories` requests `topics`; `status.py:480,631,879`, `sync.py:167`, `delete.py:112` read the host from the repo data |
| 4 — NS update + zone | `providers/registrar/porkbun.py`; `providers/dns/netlify.py` (new) | `set_nameservers` → `POST /domain/updateNameServers/{domain}`; expected-NS parameter on `check_nameservers` |
| 5 — fleet commands | `cli/status.py`, `cli/sync.py`, `cli/delete.py`, `cli/doctor.py` | host read from the topic; host column, per-host NS expectation, DEC-031 amendment, netlify doctor checks |
| 6 — config | `mimeo/config.py`, `config.toml.example` | `[netlify]` section, schema_version 2, env overrides |
| 7 — templates | tepiton template repos + TEMPLATES/CLAUDE.md inventory | `netlify.toml` per template; rejection gate list |
| tests | `tests/` | Regression: github-hosted fixtures unchanged. New: netlify deploy/teardown against mocked `netlify api` output, NS switch ordering, MX gate |
