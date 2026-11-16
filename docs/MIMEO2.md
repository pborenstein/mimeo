# mimeo 2.0: Design Notes

Status: **Input for a design session** -- nothing here is decided
except the version number: the redesign ships as 2.0 (DEC-038; the
current release is 1.3.0).
Gathered 2026-11-13 to 2026-11-15 (Entry 90). Decisions that come out
of the session go to `DECISIONS.md`.

## Why Now

DNS for the fleet is moving from Porkbun to Cloudflare. Today's code
assumes one fixed setup: Porkbun is both registrar and DNS provider,
GitHub Pages is the host, and every site repo is under one account
(`github_username`). Each part of that assumption broke during this
session:

- blueberryhill.fyi and xhosi.com have Cloudflare nameservers. Their
  Porkbun zones still hold GitHub Pages records that nothing serves,
  and `status` reported them as live until the Entry 90 fix (DEC-037).
- blueberryhill.fyi's repo is `pborenstein/blueberryhill.fyi`.
  `status` shows it as `no repo` because it only lists repos under
  the configured account. Sites can live in any account.
- xhosi.com's Cloudflare zone has MX and SPF records (Cloudflare
  Email Routing) that its Porkbun zone never had.

## Proposed Scope

mimeo connects a domain to the host serving its site, and keeps that
connection correct. It stops growing site creation: templates and
content are already tracked in the tepiton meta-repo (DEC-034 is the
only template rule mimeo keeps), and `gh repo create --template` does
the repo step.

What is given up: one command from domain name to running site. A
thin `create` wrapper can keep that (see Commands).

## Entities

| Entity | Lives at | Holds |
|---|---|---|
| Domain name | Registrar | Registration, expiry, auto-renew |
| Nameservers | Registrar | Which DNS provider is in charge of the zone |
| DNS records | DNS provider named by the nameservers | A/AAAA/CNAME/MX/TXT |
| Site | Host | Content; the host's custom-domain setting, certificate, HTTPS enforcement |

- The nameservers decide which provider's records are served.
- The host decides which records are needed (GitHub Pages: four A,
  optional four AAAA, `www` CNAME to `<owner>.github.io`).
- The host's custom-domain setting is what links a site to a domain.
  mimeo could find the link by scanning hosts and accounts listed in
  config instead of keeping its own registry.
- A template is input for making a site; it is not linked to the
  domain afterwards.

## Certificates

A certificate is issued for a hostname to whoever terminates TLS for
it. The DNS records decide who that is.

- Direct to GitHub Pages (mimeo.lol): one certificate, issued by
  GitHub through Let's Encrypt once the custom domain is set and the
  records point at GitHub. mimeo already tracks this as `cert_state`.
- Proxied through Cloudflare (blueberryhill.fyi, xhosi.com):
  browser to Cloudflare uses Cloudflare's edge certificate;
  Cloudflare to GitHub uses GitHub's. Whether Cloudflare checks
  GitHub's certificate depends on the zone's SSL mode.

## Commands (sketch)

| Command | What it does |
|---|---|
| `delegate DOMAIN --dns PROVIDER` | Makes sure the zone exists at the DNS provider, then sets the registrar's nameservers to it |
| `link DOMAIN SITE` | Sets the host's custom domain, writes the needed records at whichever provider serves the zone, enables HTTPS when the certificate is ready |
| `unlink DOMAIN` | Removes the custom domain and managed records; deletes the repo only with `--delete-repo` |
| `status` / `sync` | Check and fix that nameservers, records and host settings agree |
| `create DOMAIN` | `delegate` if needed, `gh repo create --template`, `link` |
| `doctor` | Today's checks plus DNS provider credentials |

`SITE` is written `github:owner/repo` or `netlify:site-name`; a bare
`link example.com` means `github:<default_org>/example.com`.

Provisioning a newly registered domain:

```
mimeo delegate example.com --dns cloudflare
gh repo create mimeo-sites/example.com --template mimeo-templates/mimeo --public
mimeo link example.com github:mimeo-sites/example.com
mimeo status example.com
```

## Observed 2026-11-14

| Domain | NS | Public A/AAAA | HTTP |
|---|---|---|---|
| blueberryhill.fyi | Cloudflare | Cloudflare IPs (proxied) | `server: cloudflare`, `x-github-request-id`; apex 200, `www` 301 to apex |
| xhosi.com | Cloudflare | Cloudflare IPs (proxied); MX/SPF for Cloudflare Email Routing | same as above |
| mimeo.lol | Porkbun | GitHub Pages IPs, v4 and v6; `www` CNAME `pborenstein.github.io` | matches the Porkbun zone |

All three serve Let's Encrypt certificates (YE1, YE2, YR2). For
proxied domains, public DNS shows only Cloudflare's IPs, so reading
the actual records takes the Cloudflare API (a token with
Zone:DNS:Read).

## Unverified Vendor Claims

Not checked against vendor docs (2026-11-15):

- GitHub Pages cannot issue or renew its certificate while records
  are proxied, because the validation request reaches Cloudflare.
  Usual workaround: link DNS-only, wait for the certificate, then
  turn proxying on.
- With proxying on, renewal of the GitHub certificate can fail
  without anyone noticing; it matters only in Full (strict) mode.

## Open Questions

1. Does `link` write proxied or DNS-only records, and is that a flag
   or a per-provider default?
2. When `delegate` creates a zone, does it copy all records or only
   the ones mimeo manages?
3. Netlify staging pass 1 (splitting "which repo" from "which host"
   in the code, `docs/NETLIFY.md`) is the refactor the `SITE`
   argument needs. Does it land first, on 1.x?
4. Which accounts and hosts does `status` scan, and where in config
   are they listed?
5. Is the registrar a separate interface from the DNS provider, given
   Porkbun stays the registrar and may stay a DNS provider for some
   zones?
6. Subdomain sites (`docs/SUBDOMAINS.md`, on ice since 2026-09-29):
   does a subdomain get its own records in the parent zone under
   `link`, or stay out of scope?

`docs/SITE_ADDRESS.md` (sites addressed as `org.github.io/x`, repo
always created) is stale and is not an input to this design (DEC-038).
