# Netlify as a Second Host

Status: **Proposed design** — not yet decided or scheduled. Open questions are
listed at the end; once settled they should be promoted to `DECISIONS.md`.
This is the "second host" DEC-030 named as its own revisit trigger ("revisit
the factory if a second registrar or host lands"). Sibling of
`docs/SITE_ADDRESS.md` (proposed); the two share the repo-provisioning seam
but do not depend on each other. The load-bearing decision here is the DNS
mode fork (Open Decision #1) — it determines whether the registrar-layer
work is in scope at all.

## Goal

```
mimeo create example.com --host netlify   # repo from template (unchanged) +
                                          #   Netlify site linked to that repo,
                                          #   custom domain, DNS, HTTPS
mimeo status --all                        # mixed fleet: github + netlify sites
mimeo sync example.com                    # converges either host
mimeo delete example.com                  # undoes either host
```

One command, from nothing to a live HTTPS site — the same promise on a
second host. Netlify builds the site from the same tepiton template repos
(continuous deployment from GitHub), so the repo half of the pipeline is
shared and only the serving half changes.

## The Problem in One Paragraph

The `Host` ABC (`providers/base.py`) anticipates a second host, but nothing
else does. The CLI instantiates `GitHubHost` by name in five commands
(`create.py:130,303`, `status.py:480,631,879`, `sync.py:167`,
`delete.py:112`) — DEC-030 removed the `defaults.host` config fields
precisely because no factory existed. Worse, `GitHubHost` welds two roles
together in `deploy_site` (`github.py:753`): *make the source repo*
(template generate, manifest substitution, dev-strip, topics, Website
field) and *serve it via Pages* (Pages enable, custom domain, HTTPS). A
Netlify host needs the first role in full and replaces the second. And
Netlify's recommended DNS path — delegate the nameservers — inverts the
registrar's part: Porkbun goes from DNS provider to inert bystander, which
touches `check_nameservers`, `sync --reset-nameservers`, and DEC-031's
"registration and nameservers are never touched" scope limit.

## Behavior Today

Greenfield — there is no `--host` flag and no Netlify code. `[defaults]
host` was removed from config (DEC-030); a stale key in an existing config
is silently ignored, so reintroducing it later breaks nothing. The failure
mode for "user wants Netlify" is manual: create the site in the web UI by
hand, exactly the toil mimeo exists to remove.

## What the Netlify Flow Is

Netlify's CLI mirrors the `gh` pattern: `netlify login` (browser) or
`NETLIFY_AUTH_TOKEN` for headless use, and `netlify api <operation> --data
'{...}'` as the raw-JSON escape hatch (operation names from
open-api.netlify.com). Everything mimeo needs is API-addressable:

| Step | Endpoint | Notes |
|------|----------|-------|
| Verify auth | `netlify status` | analog of `gh auth status` |
| Create site | `POST /sites` | in the team/account slug |
| List linkable repos | `GET /{account_slug}/repos` | only repos the Netlify GitHub App can see |
| Link site to repo | `PUT /sites/{site_id}/repo` | `{repo_id, branch, cmd, dir}` |
| Add custom domain | `POST /sites/{site_id}/domains` | apex and www separately |
| Create DNS zone | `POST /dns_zones` | response carries the assigned nameservers (NS1: `dns1.pXX.nsone.net` ...) |
| Create zone records | `POST /dns_zones/{zone_id}/dns_records` | apex A `104.198.14.52`, www CNAME `{site}.netlify.app` |
| Cert state / provision | `GET`/`POST /sites/{site_id}/ssl` | empty POST body = Let's Encrypt |
| Force HTTPS | `PATCH /sites/{site_id}` | `{"force_ssl": true}` |
| Fleet domains | `GET /domains` | all domains the account serves — the `list_mimeo_repositories` analog |

Repo association is *not* a first-class non-interactive CLI command
(`netlify init` is a wizard); the API `PUT` is the automation path.

### The DNS mode fork

**Mode A — delegate nameservers to Netlify** (Netlify's recommended path,
and the original motivation): create the zone, copy records in, then flip
the domain's NS at Porkbun (`POST /domain/updateNameServers/{domain}`,
atomic full-list replacement). Certs provision automatically once the
zone answers. Cost: Porkbun stops serving DNS — anything it served that
was not copied (email MX above all) dies silently — and `delete` must
learn to restore Porkbun NS or leave the domain SERVFAIL-ing.

**Mode B — external DNS (keep Porkbun)**: mimeo's whole existing DNS
machinery is reused unchanged; only the record values change (apex A →
`104.198.14.52`, www CNAME → `{site}.netlify.app`). No nameserver move, no
email risk, `delete` unchanged. Cost: the cert provisions only after
records propagate, so `create` ends `https_pending` and `sync` converges
— the exact shape of today's Pages cert loop, with more waiting.

## Prerequisites and Hard Facts

- **Netlify GitHub App** must be installed on the org holding site repos
  (one-time, browser, per-org — the Netlify equivalent of `gh auth login`,
  and the one step that cannot be scripted). Without it, the repos do not
  appear in `GET /{account_slug}/repos` and linking fails.
- DNS zones are **globally unique across all Netlify accounts** (one NS1
  namespace). If the domain's zone exists under any account ever,
  `POST /dns_zones` fails; resolution is a Netlify support ticket.
- Netlify site subdomains are globally unique — `{domain}` with dots as
  dashes can collide; take the suffix Netlify assigns.
- Mode A ordering invariant: zone exists → records in zone → NS switch →
  cert. Every partial state along that chain must be convergable by
  `sync` (same philosophy as today's deploy ordering).
- Free-tier build minutes are a **shared pool** (300/month across all
  sites) where Pages builds are unmetered — a non-issue for landing
  pages, a real ceiling for a large fleet.
- Netlify personal access tokens are coarse (account-wide by default);
  there is no per-operation scope like `gh`'s `repo`/`workflow`.

## What Needs to Happen

Seven changes, in dependency order. Changes 1–3 plus mode B deliver a
working second host; changes 4–5 are the mode A and fleet-correctness
work; 6–7 are plumbing the whole thing stands on.

**1. Split `GitHubHost` into repo-provider and Pages-host.** Extract the
source-repo half — `_create_from_template` (`github.py:275`) with its
force/rename-recovery dance, manifest fetch/apply, dev-strip, topics,
Website field, repo delete/rename — into a repo provider (e.g.
`providers/repo/github.py`). `GitHubHost` keeps Pages enable, custom
domain, HTTPS, health. `NetlifyHost` composes the same repo provider: a
Netlify deploy still creates a GitHub repository from the same tepiton
template. This is also the seam `SITE_ADDRESS.md` change 2 wants; doing
it first means that design lands on the split instead of forcing it.

**2. Add `NetlifyHost`** (`providers/host/netlify.py`). A subprocess
wrapper around `netlify api` mirroring `_run_gh_command`/`_gh_api`
(`github.py:107,158`) — including HTTP-status extraction out of error
output into `HostError.status_code`, so the DEC-027/028 exit-code mapping
works unchanged. `deploy_site`: repo (via change 1) → create site → link
repo → add custom domain → attempt force-HTTPS. `teardown_site`: delete
the site (custom domain dies with it). Health: `GET /sites/{id}/ssl` +
deploy state behind a `health_status`-style classifier. Fleet listing:
`GET /domains`. `required_dns_records`: mode-dependent (mode B: the two
load-balancer records; mode A: empty — zone records live inside Netlify).

**3. Host selection and fleet resolution.** `--host {github,netlify}` on
`create` (default github). `status`/`sync`/`delete` resolve which host
serves a domain by asking both providers and joining on the domain —
GitHub via the `mimeo` topic, Netlify via `GET /domains`. No local state
file (Open Decision #8). A domain claimed by both (mid-migration) is
reported, not guessed at.

**4. Registrar NS handoff + Netlify zone (mode A only).**
`PorkbunRegistrar.set_nameservers(domain, ns)` wrapping
`POST /domain/updateNameServers/{domain}`; `check_nameservers` gains an
expected-NS parameter (Porkbun defaults for github-hosted domains, the
zone's assigned NS for netlify-hosted ones). A Netlify DNS provider
creates the zone, writes records, and drift-checks within it — the
`PorkbunDNSProvider` role against different endpoints.

**5. Make the fleet commands host-aware.** `status`: host column,
per-host health classifiers, host-correct NS expectations. `sync`: NS
check against the serving host's expectation; drift against that host's
records; `force_ssl` when the cert is ready. `delete`: amend DEC-031's
"nameservers are never touched" to "restored to registrar defaults for
hosts that own the zone" — restore Porkbun NS, delete the site; the
leftover Netlify zone is inert (deleting it behind a flag, since it may
carry email). `doctor`: `netlify` installed + authenticated when that
host is selected, plus a remediation pointer for the GitHub App
prerequisite.

**6. Config and auth.** `[netlify]` section (`account_slug`; token from
`MIMEO_NETLIFY_AUTH_TOKEN`/`NETLIFY_AUTH_TOKEN` or `netlify login`),
schema_version 2. Note `config.py:12` imports template defaults from the
GitHub provider — those constants move to a neutral module as part of the
split (change 1).

**7. Give templates a Netlify build story.** Netlify ignores the Pages
workflow files; it needs a build command and publish directory. Carrier:
a `netlify.toml` in each template repo (rides along on generate, read by
Netlify from the repo — zero mimeo code) rather than growing
`mimeo.template.json` beyond domain substitution (DEC-024's shape).
`--host netlify` rejects templates with no build story, naming them.

## What Does NOT Need to Change

- **The content pipeline.** Template generate, manifest substitution,
  dev-strip run identically for both hosts — that is the point of
  change 1.
- **Error taxonomy and exit codes.** `HostError.status_code` carries
  Netlify API failures through the existing mapping.
- **The registrar ABC shape** — `set_nameservers` is additive.
- **Porkbun as DNS provider for github-hosted sites**, byte-for-byte.
- **Concurrency model, output formats, `--log-format json`.**

## Open Decisions

| # | Question | Recommendation | Rationale |
|---|----------|----------------|-----------|
| 1 | DNS mode: A (delegate NS) vs B (external) vs B-then-A | A is the stated destination; land B first only if the registrar work would otherwise delay the first Netlify site | B reuses all existing DNS machinery and is reversible scaffolding; A is Netlify's recommended path with automatic certs but moves the zone — email risk, delete-semantics change, host-aware NS checks. Decide before change 4 is scheduled |
| 2 | MX/uncopied records at NS switch (mode A) | Hard gate: refuse the switch while the Porkbun zone holds records absent from the Netlify zone, MX first; a copy step can come later | A silent email outage is the worst failure this design can cause; mimeo does not manage MX, so it must not silently destroy it |
| 3 | `delete` on a Netlify-DNS domain | Restore Porkbun NS + delete site by default; zone deletion behind a flag | Leaving NS at a deleted zone is SERVFAIL; an inert leftover zone is only hygiene — and may carry email someone still wants |
| 4 | Netlify site naming | Domain with dots as dashes; accept Netlify's suffix on collision | The site name is an implementation detail (same logic as SITE_ADDRESS #7's `--repo`); the domain is the identity and join key |
| 5 | Build-config carrier | `netlify.toml` in templates | Canonical — Netlify reads it from the repo after generate; keeps the manifest single-purpose |
| 6 | pandoc-resume on Netlify | Out of scope initially; covered by the change-7 rejection gate | No pandoc in Netlify's build image; a plugin/Docker workaround is its own investigation. 10 of 11 templates are npm-build or static |
| 7 | Cert convergence | Mirror the Pages lifecycle: `create` attempts force-HTTPS and reports `https_pending`; `sync` converges when the cert state says ready | The `https_pending`/`fixable` machinery already exists; only the state names differ |
| 8 | Host-selection state: config field vs flag-only vs live resolution | `--host` flag now; `[defaults] host` returns only together with the factory; per-domain host always resolved live by joining both providers | DEC-030 discipline — no config field until it works; mimeo's philosophy is live discovery, not local state |

## Suggested Staging

Two passes, each independently landable and testable:

1. **Second host, familiar DNS** — changes 1, 2, 3 (create side), 6, 7,
   with mode B records. `create --host netlify` works end to end on
   external DNS; the GitHub path is byte-for-byte unchanged; change 1
   lands as a pure refactor with existing tests as the harness.
2. **Netlify DNS (mode A) and fleet correctness** — changes 4, 5: NS
   handoff, Netlify zone, the MX gate, host-aware `status`/`sync`/
   `delete`, and the DEC-031 amendment.

Smallest shippable slice: change 1 + `NetlifyHost` + `--host` on `create`
for one static template.

Sequencing note: change 1 is worth landing even if Netlify stalls —
`SITE_ADDRESS.md` needs the same seam, and it converts `github.py` from
the project's largest module into two focused ones.

## Appendix: Code Touch-Points

Where each change lands, for implementation planning only. Referenced
against `main` at `4f6c03b`.

| Change | Where | Notes |
|--------|-------|-------|
| 1 — repo/host split | `providers/host/github.py` → `providers/repo/github.py` (new) + `github.py` | move `_create_from_template` (:275) + manifest/dev-strip/topics/homepage/rename/delete; `deploy_site` (:753) composes; template constants leave the host module (`config.py:12` import) |
| 2 — `NetlifyHost` | `providers/host/netlify.py` (new) + `tests/providers/host/test_netlify.py` | wrapper mirrors `_run_gh_command`/`_gh_api` (:107, :158); health classifier mirrors `health_status` (:38); teardown mirrors `teardown_site` (:830) |
| 3 — host selection | `cli/create.py:130,303`; factory in `cli/_processing.py` | `--host` flag; `status.py:480,631,879`, `sync.py:167`, `delete.py:112` resolve per-domain host |
| 4 — NS handoff + zone | `providers/registrar/porkbun.py`; `providers/dns/netlify.py` (new) | `set_nameservers` → `POST /domain/updateNameServers/{domain}`; expected-NS injection into `check_nameservers` |
| 5 — fleet commands | `cli/status.py`, `cli/sync.py`, `cli/delete.py`, `cli/doctor.py` | host column, per-host NS expectation, DEC-031 amendment, netlify doctor checks |
| 6 — config | `mimeo/config.py`, `config.toml.example` | `[netlify]` section, schema_version 2, env overrides |
| 7 — templates | tepiton template repos + TEMPLATES/CLAUDE.md inventory | `netlify.toml` per template; rejection gate list |
| tests | `tests/` | Regression: github-hosted fixtures byte-identical. New: netlify deploy/teardown against mocked `netlify api` output, NS handoff ordering, MX gate |
