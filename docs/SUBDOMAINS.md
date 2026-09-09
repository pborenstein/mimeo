# Subdomain Sites

Status: **Proposed design** — not yet decided or scheduled. Open questions are
listed at the end; once settled they should be promoted to `DECISIONS.md`.

## Goal

Make this work the way the apex version already works:

```
mimeo create --template eleventy-service service.example.com
```

One command, from nothing to a live HTTPS site — on a hostname *below* the
registered domain, sharing that domain's DNS zone with the apex site and any
sibling subdomain sites.

## The Problem in One Paragraph

Every "domain" in mimeo is a single string playing three roles at once:

1. the **site hostname** — what the site is called: repository name, Pages
   custom domain, final URL;
2. the **DNS zone** — the unit Porkbun's API works in: ownership,
   nameservers, and every DNS record call;
3. the **join key** — how `status` and `sync` match GitHub repositories
   against Porkbun registrations.

For an apex domain (`example.com`) all three roles are the same string, and
that coincidence *is* the current design. A subdomain splits them:

```
site hostname:   service.example.com    repo name, Pages CNAME, URL
DNS zone:        example.com            ownership, NS checks, record API calls
record name:     service                the label inside the zone
```

It also introduces a relationship the code has never had to think about:
**one zone can contain many sites**. `example.com`, `service.example.com`,
and `blog.example.com` are three sites in one zone. Every piece of logic that
implicitly assumes "this zone belongs to this one site" has to learn to share.

## Behavior Today

The command fails cleanly. Argument validation already accepts subdomains
(the hostname grammar doesn't care how many labels there are), but the first
thing `create` does after that is verify ownership — and Porkbun's API is
zone-scoped, so asking about `service.example.com` comes back "not found".
Create refuses: *"not registered in this Porkbun account"*. Nothing is
created.

So the failure mode is safe. The reason this is a structural change rather
than a one-line fix is what would happen past that gate:

- Nameserver checks would query the subdomain, which has no NS records of
  its own — the answer lives at the zone.
- DNS record calls would go to a "zone" that is not a zone.
- Worst, the DNS desired state for an apex site (A records at the apex plus
  a `www` CNAME) would be applied as-is — a subdomain site trying to take
  over its parent's apex.

## What Needs to Happen

Six changes, in dependency order. The first three make subdomain creates
work; the next three are the correctness work that only matters once zones
are shared.

**1. Split the identity.** The full hostname and the zone it lives in must
be carried as separate values end to end. Everything user-facing keeps the
hostname (repo name, Pages custom domain, URL, template customization) —
unchanged. Everything registrar-facing switches to the zone (ownership,
nameservers, DNS record operations).

**2. Resolve hostname → zone, and treat that as the ownership check.**
Match the hostname against the account's registered domains and take the
longest suffix: `service.example.com` → `example.com`,
`a.b.example.com` → `example.com`. No match means the same refusal create
gives today. This makes ownership verification *stronger* than today's exact
string match, needs no new dependency, and gets multi-label suffixes
(`co.uk`) right for free because the account — not a suffix list — defines
where zones are cut.

**3. Give subdomain sites their own DNS desired state.** An apex site keeps
exactly today's records (four A at the apex, CNAME for `www`). A subdomain
site wants exactly one record: a CNAME on its label pointing at the Pages
host (`service` → `<owner>.github.io`). A subdomain site never touches the
parent's apex or `www`.

**4. Scope drift checks to records the site owns.** Once a zone holds
records for several sites, "extra record" judgments must only consider the
names this site manages. Otherwise a subdomain site's CNAME-only desired
state flags every sibling record in the zone (`www`, `blog`, …) as drift,
forever. (The current comparison filters by record *type* only, which
implies "whole zone belongs to this site".)

**5. Replace conflicting records at a managed name.** Taking over a label
that currently holds a different record type (an existing A record where a
CNAME is now wanted) must delete the old-type record, not just same-type
duplicates. The current replace logic only handles one such special case
(ALIAS vs A at the apex); the rule needs to generalize.

**6. Teach the fleet views both identities.** In `status` and `sync`,
repository names are hostnames while registrar data is zones, so the join
between them needs the hostname → zone mapping from change 2. Skip reasons
("not in Porkbun account" → "zone not in Porkbun account"), fleet
enumeration, and per-row registrar columns (expiry, NS) all resolve through
it. Nameserver checks can be deduplicated per zone when several sites share
one.

Minor and included: normalize hostnames (lowercase, strip trailing dot) on
input. Deeper subdomains (`a.b.example.com`) fall out naturally — the record
name is just `a.b`.

## What Does NOT Need to Change

Useful for scoping — most of the system already speaks the right language:

- **Hosting side entirely.** Repo creation, Pages enable, custom domain,
  HTTPS enforcement, and template customization all want the hostname,
  which is what they already receive. Repo names may contain dots, so
  `owner/service.example.com` is a valid repository name with no special
  handling.
- **Porkbun API plumbing.** The record-name normalization inside the DNS
  provider is already relative to whatever zone it is given; it understands
  `service` inside `example.com` today. The callers pass the wrong string —
  the layer itself is fine.
- **Argument validation.** Already accepts subdomains.
- **Error taxonomy, exit codes, concurrency model, output formats.**

## Open Decisions

| # | Question | Recommendation | Rationale |
|---|----------|----------------|-----------|
| 1 | Repository naming for subdomain sites | Keep the full hostname (`service.example.com`) | Preserves the repo ↔ site correspondence and the template-rename customization; dots are legal in repo names |
| 2 | Zone resolution source | Account's registered-domain list | Authoritative for what mimeo may touch, dependency-free, correct on multi-label suffixes. A Public Suffix List (`tldextract`) only matters if we ever manage zones *not* registered in the account |
| 3 | `ignore_domains` semantics | Match on hostname *or* zone | Lets users ignore one subdomain site or a whole zone, and is backward compatible |
| 4 | Does apex behavior change at all? | No | Apex sites are the common case; every branch above leaves their behavior identical |

## Suggested Staging

Two passes, each independently landable and testable:

1. **Create path** — changes 1–3. Subdomain creates work end to end; apex
   behavior byte-for-byte identical.
2. **Fleet correctness** — changes 4–6. Drift scoping, conflict
   replacement, and the `status`/`sync` joins, exercised against zones that
   hold several sites.

Independent of the queued DEC-024 / code-review work; no shared state.

## Appendix: Code Touch-Points

Where each change lands, for implementation planning only. Referenced
against `main` at `2e8580b`.

| Change | Where | Notes |
|--------|-------|-------|
| 1 — identity split | `mimeo/models.py` | New `SiteDomain` value object: `fqdn`, `zone`, `record_name`, `is_apex` |
| 2 — zone resolution | `mimeo/providers/registrar/porkbun.py` | `domain_exists()` becomes zone resolution: longest suffix match against `list_domains()` output |
| 3 — desired state | `mimeo/providers/host/github.py` | `required_dns_records()` branches: apex set unchanged; subdomain → single CNAME |
| 4 — drift scoping | `PorkbunDNSProvider.check_dns_drift()` | `extra` filtered by managed names, not just types |
| 5 — conflict replacement | `PorkbunDNSProvider.configure_dns()` | Generalize the ALIAS/@ special case to type conflicts at any managed name |
| 6 — fleet joins | `mimeo/cli/sync.py`, `mimeo/cli/status.py` | hostname → zone mapping in target enumeration, skip reasons, registrar columns; per-zone NS dedupe |
| plumbing | `mimeo/cli/create.py`, `mimeo/cli/_processing.py` | Thread `SiteDomain` through; hostname normalization in `validate_domains` |
| tests | `tests/` | Apex fixtures must show identical behavior (regression); new shared-zone fixtures: sibling records, type conflicts, deep subdomains |
