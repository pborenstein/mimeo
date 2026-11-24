---
phase: 8
phase_name: Consolidation
updated: 2026-11-23
last_commit: 8410c35
last_entry: 104
---

## Current Focus

mimeo 2.2.0 is the current release (tag `v2.2.0`, 2026-11-23). It reads
the six Netlify sites and makes no writes to Netlify (DEC-057). Next is
making Netlify a full host (`docs/IMPLEMENTATION.md`, Phase 9). The
create fix, the RENEW column, the HTTPS change and `mimeo proxy` are
committed but not released or pushed.

## Active Tasks

- [ ] **tequitl.dev is being left to expire** (2026-12-06, decided
      2026-11-17). Its site is `pborenstein/twohorses`; when `status`
      shows it as `no domain`, unlink it. Its repo also builds
      twohorses.lol on Netlify; `delete` now keeps the repo (DEC-057).

## Blockers: none

## Context

- mimeo reports a problem with its fix steps, and `sync` does the fix
      when it can write the zone (DEC-048).
- A fully proxied site uses Cloudflare's certificate (DEC-058). Only
      `mimeo proxy` turns a proxy on (DEC-059). 22 sites are proxied.
- Porkbun requests are spaced 0.25s; `status --all` takes a minute.
- 24 of 109 hostnames are on Cloudflare; 7 are on Netlify sites.
- Live config: three organizations, `defaults.dns = "cloudflare"`.
- 002370.xyz is the junk domain, on Cloudflare again since 2026-11-17.
- Porkbun can move a domain to Cloudflare itself (account connected
      2026-11-22); mimeo needs no change for it (DEC-053).

## Next Session

Move the 51 GitHub sites on Porkbun DNS to Cloudflare, leaving out
tequitl.dev, then run `mimeo proxy --all`. After that, the Netlify task
list in `docs/IMPLEMENTATION.md`, Phase 9.
