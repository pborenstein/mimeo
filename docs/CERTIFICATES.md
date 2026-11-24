# HTTPS Certificates

Status: **Built 2026-11-23** (DEC-058). The Cloudflare settings are
applied to the fleet and mimeo keeps them right. Replaces the certificate
handling for proxied sites in DEC-050. Cloudflare facts were
read from its docs on 2026-11-23; fleet facts were measured the same day.

## The Rule

Whoever answers the visitor provides the certificate.

| A site's records | Who answers visitors | Certificate that matters | What mimeo does |
|---|---|---|---|
| DNS-only | GitHub Pages | GitHub's | What it does today: request it, watch it, enforce HTTPS |
| Proxied at all of the site's names | Cloudflare | Cloudflare's, which it issues and renews itself | Make sure the zone's two Cloudflare settings below are right. Ignore GitHub's certificate |
| Proxied at some names, DNS-only at others | Both | Both | Treat it as DNS-only, because GitHub answers for at least one name |

mimeo never switches a proxy on or off to get a certificate. The
`mimeo proxy` command turns it on when asked (DEC-059).

## The Two Cloudflare Settings

A proxied zone needs these, and `sync` sets them:

| Setting | Value | Why |
|---|---|---|
| SSL/TLS encryption mode (`ssl`) | `full`, fixed | Cloudflare connects to GitHub over HTTPS and does not check GitHub's certificate |
| Always Use HTTPS (`always_use_https`) | on | Cloudflare redirects `http://` to `https://`, whether or not GitHub has a certificate |

Why `full` and not the others:

- **Flexible** sends traffic from Cloudflare to GitHub unencrypted. It
  also causes a redirect loop on any site where GitHub enforces HTTPS
  ([Cloudflare](https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/flexible/)).
- **Full (strict)** requires a valid GitHub certificate. GitHub cannot
  renew one behind the proxy, so when it expires visitors get an error
  ([Cloudflare](https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full-strict/)).
- **Full** accepts a certificate that is "expired, self-signed, or not
  even [has] a matching CN/SAN entry"
  ([Cloudflare](https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full/)).
  The cost is that Cloudflare does not verify it is talking to GitHub.
- **Automatic** must be turned off. It can raise a zone to Full (strict)
  on its own, about once a month, when it sees a valid GitHub certificate
  ([Cloudflare](https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/)).
  That would break the site when the certificate later expires.

## What the Fleet Looks Like Now

Read through the Cloudflare API on 2026-11-23, before and after the
change.

| Setting | Before | After |
|---|---|---|
| SSL/TLS mode | `full` on all 24 zones | Unchanged |
| Automatic | On for blueberryhill.fyi, mimeo.lol and xhosi.com; off for the other 21 zones | Off on all 24 zones |
| Always Use HTTPS | Off on all 24 zones | On for the 16 zones with proxied sites, then the 6 proxied with `mimeo proxy`; off for tantamount.party and xhosi.org, which have no site |

The 16 zones are 002370.xyz, blueberryhill.fyi, ekranoplan.org,
mellowtimesphere.com, mellowtimesphere.org, mezuzah.lol, mimeo.fyi,
mimeo.lol, mrzeitgeist.net, mrzeitgeist.org, orobia.dev, orobia.lol,
orobia.net, xhosi.com, xhosi.net and xocoyotl.dev. After the change, each
read back the settings above, answered 200 on `https://`, and redirected
`http://` to `https://`.

No zone is on Full (strict), so no proxied site depends on its GitHub
certificate. When a zone gets
proxied later, `status` shows its site as `fixable` and `sync` sets both
settings.

## What mimeo Does

| Command | Behavior |
|---|---|
| `status` | A fully proxied site reads `ok` when the two settings are right, whatever GitHub's certificate says. It reads `fixable` when a setting is wrong, and `unknown` when they cannot be read |
| `sync` | Sets the two settings. Turns Automatic off first, and writes only what is wrong |
| `doctor` | Checks that the token can read zone settings. It cannot check for write access without writing |
| `link`, `create` | Do not report HTTPS as pending for a fully proxied site |
| `proxy` | Sets the two settings, then turns on the proxy for a site's address records (DEC-059) |

The proxy-off sequence from DEC-050 is removed. `sync` does not change a
record's proxy setting.

## Verified on 2026-11-23

| Claim | Result |
|---|---|
| `PATCH /zones/{id}/settings/ssl_automatic_mode` with `{"value":"custom"}` turns Automatic off | Yes, on three zones; `ssl` stayed `full` |
| `PATCH /zones/{id}/settings/always_use_https` takes `{"value":"on"}` | Yes, on 16 zones |
| A proxied site works under Full with no GitHub certificate for its hostname | Yes: mimeo.fyi, mrzeitgeist.net and mrzeitgeist.org |
| `mimeo sync` corrects a wrong setting | Yes: Always Use HTTPS was turned off on 002370.xyz, `status` read `fixable`, `sync` turned it back on |
