# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Versions before 2.0.0 were not tagged. Their history is in
[docs/chronicles](docs/chronicles/) and in the git log; 1.4.0 is commit
[62eeff7](https://github.com/pborenstein/mimeo/commit/62eeff7).

## [Unreleased]

## [2.2.0] - 2026-11-23

mimeo now reads Netlify sites. It makes no changes to them.

### Added

- If the `netlify` command-line tool is installed and logged in, `status` reports that account's sites: DNS, certificate state, and the repository each builds from, marked `(netlify)`. A domain on Netlify DNS shows `netlify` under `DNS`. JSON and CSV output gain `host` and `source_repo` fields ([4240717](https://github.com/pborenstein/mimeo/commit/4240717)).
- `doctor` checks that the Netlify account can be read.
- `MIMEO_SKIP_NETLIFY=1` turns the Netlify checks off.

### Changed

- `create` and `link` refuse a hostname a Netlify site serves.
- `delete` refuses a hostname a Netlify site serves. For a GitHub Pages site whose repository also builds a Netlify site, it removes the link and DNS records and keeps the repository.
- `sync` skips a Netlify site and says why.
- If the Netlify account cannot be read, `status` warns and continues, and `create`, `link` and `delete` stop.

### Known limitations

- The Netlify problem reports (expiring certificate, missing record) have run only against test data, because every live site is healthy (as of 2026-11-23).

## [2.1.0] - 2026-11-17

### Added

- `scripts/e2e_smoke.sh DOMAIN`: moves a junk domain's zone to the other DNS provider and back, checking that `status` reads `ok` at each step. Not run by pytest ([a54a1a5](https://github.com/pborenstein/mimeo/commit/a54a1a5)).

### Changed

- `delegate` no longer warns that Porkbun mail forwarding may stop. Porkbun's guide says forwarding works with DNS hosted elsewhere when the MX records point at Porkbun, and `delegate` copies them. The Cloudflare Email Routing warning now cites Cloudflare's documentation.
- The site cache records the organizations it was built from. When `github.organizations` changes, the next lookup that misses rescans.
- `status` shows a hostname registered outside this Porkbun account as `elsewhere` under `EXPIRES` and `external` under `DNS` and `RECORDS`, with a `note:` naming its nameservers, instead of dashes. JSON and CSV output gain a `notes` field ([a54a1a5](https://github.com/pborenstein/mimeo/commit/a54a1a5)).
- The README is reorganized, and `docs/TROUBLESHOOTING.md` says which vendor facts were checked and when ([0e48ab8](https://github.com/pborenstein/mimeo/commit/0e48ab8)).

### Fixed

- `sync --dry-run` ends with "N would change" instead of "N changed" ([a54a1a5](https://github.com/pborenstein/mimeo/commit/a54a1a5)).
- `delegate --dry-run` lists only the records the target provider lacks, as the real run copies; it listed every record ([ab8085d](https://github.com/pborenstein/mimeo/commit/ab8085d)).
- `doctor DOMAIN` no longer says a Cloudflare-served domain "needs [cloudflare] api_token in config" when the token is configured, and fails when it is not.

## [2.0.0] - 2026-11-17

mimeo 2.0 connects a hostname to the site that serves it and keeps the
connection correct. Every command reads the same four things (the
registration, the nameservers, the DNS records at whichever provider the
nameservers name, and the host's custom-domain setting), compares them
with what the site needs, and applies or prints the difference. The
README's [How it works](README.md#how-it-works) describes it, and
[Upgrading from 1.x](README.md#upgrading-from-1x) lists what moved.

### Breaking changes

- A site is the repository whose GitHub Pages custom domain is the
  hostname, in any organization listed under `github.organizations`.
  In 1.x it was the repository named after the domain in one account
  ([7685699](https://github.com/pborenstein/mimeo/commit/7685699)).
- The DNS provider is whichever one the registrar's nameservers name.
  In 1.x Porkbun's zone was always treated as the DNS.
- `sync --reset-nameservers` is replaced by
  `mimeo delegate ZONE --dns porkbun`.
- `delete --keep-repo` is replaced by `mimeo unlink HOSTNAME`.
- `status --source`, `--with-dns`, `--health` and `--show-template` are
  removed. `status` has one view, and `--records` shows the zone.
- `create` changes only the site's address records. In 1.x it rewrote
  the zone's managed records.
- A registered domain with no repository is shown as `no site` and is no
  longer counted as a problem.

A 1.x config file loads unchanged, and with no new keys mimeo behaves as
before: one organization, Porkbun DNS.

### Added

- Cloudflare as a DNS provider, chosen per zone by its nameservers.
  Needs a `[cloudflare]` section in the config
  ([648f1eb](https://github.com/pborenstein/mimeo/commit/648f1eb)).
- `mimeo delegate`: moves a zone to another DNS provider. Copies every
  record except NS and SOA, reads the copies back, then sets the
  nameservers at the registrar
  ([d67b97a](https://github.com/pborenstein/mimeo/commit/d67b97a)).
- `mimeo link` and `mimeo unlink`: connect a hostname to a repository
  that already exists, or take it off, without creating or deleting
  anything
  ([d67b97a](https://github.com/pborenstein/mimeo/commit/d67b97a)).
- `mimeo scan`: rebuilds the cache of which repository serves which
  hostname across every listed organization
  ([7685699](https://github.com/pborenstein/mimeo/commit/7685699)).
- Subdomain sites (`service.example.com`), served by one CNAME.
- Four AAAA records at the apex of every site. The first `sync` after
  upgrading adds them.
- `github.organizations` and `defaults.dns` in the config, with config
  schema 2.
- Every problem `status` and `sync` report is a sentence followed by the
  steps that fix it, with the hostname, commands and page to open filled
  in. In JSON and CSV output the steps are the `fixes` field
  ([c79ed04](https://github.com/pborenstein/mimeo/commit/c79ed04)).
- `sync` gets a certificate issued when a site has none, when a renewal
  failed, or when the certificate is within 14 days of expiry, by
  removing the custom domain and setting it again
  ([c79ed04](https://github.com/pborenstein/mimeo/commit/c79ed04),
  [f853a58](https://github.com/pborenstein/mimeo/commit/f853a58)).
- When the site's records are proxied through Cloudflare, `sync`
  switches them to DNS-only for that, waits for the certificate, and
  switches them back
  ([f853a58](https://github.com/pborenstein/mimeo/commit/f853a58)).
- `status` shows `no domain` for a site whose hostname is not at the
  registrar and has no nameservers in public DNS, and offers the choices
  for its repository
  ([c79ed04](https://github.com/pborenstein/mimeo/commit/c79ed04)).
- `delegate` lists the services a move would stop (Cloudflare Email
  Routing, Cloudflare's proxy, Porkbun mail) and asks before changing
  anything. `--yes` skips the question. `create` leaves such a zone
  where it is
  ([f853a58](https://github.com/pborenstein/mimeo/commit/f853a58)).
- `doctor` checks the Porkbun keys and the Cloudflare token, including
  tokens owned by an account
  ([678b3b7](https://github.com/pborenstein/mimeo/commit/678b3b7)).

### Changed

- Requests to Porkbun start at least 0.25 seconds apart and are retried
  five times. `status --all` over about 100 domains takes about a minute
  ([c79ed04](https://github.com/pborenstein/mimeo/commit/c79ed04)).
- Templates are looked up in the `mimeo-templates` organization by
  default
  ([62eeff7](https://github.com/pborenstein/mimeo/commit/62eeff7)).
- `docs/TROUBLESHOOTING.md` is rewritten for 2.0.

### Fixed

- A name proxied through Cloudflare is no longer asked for more A or
  AAAA records once it has some of the required ones
  ([22f48c3](https://github.com/pborenstein/mimeo/commit/22f48c3)).

### Known limitations

- `sync` removing a record on Cloudflare, `sync` adding a record at a
  name that is already proxied, and the proxy sequence against a renewal
  that has actually failed have not been run against live services (as
  of 2026-11-17). They are covered by tests against in-memory providers.
- `delegate` warns only about the three services listed above.

[Unreleased]: https://github.com/pborenstein/mimeo/compare/v2.2.0...HEAD
[2.2.0]: https://github.com/pborenstein/mimeo/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/pborenstein/mimeo/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/pborenstein/mimeo/releases/tag/v2.0.0
