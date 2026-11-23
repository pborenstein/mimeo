---
phase: 8
phase_name: Consolidation
updated: 2026-11-23
last_commit: 4240717
last_entry: 101
---

## Current Focus

mimeo 2.2.0 is the current release (tag `v2.2.0`, 2026-11-23). It reads
the six Netlify sites and makes no writes to Netlify (DEC-057). Next is
making Netlify a full host (`docs/IMPLEMENTATION.md`, Phase 9).

## Active Tasks

- [ ] **blueberryhill.fyi** certificate renewal near 2026-12-23, proxied:
      on `cert error`, `mimeo sync blueberryhill.fyi` is the first run
      of DEC-050 on a real failure.
- [ ] **tequitl.dev is being left to expire** (2026-12-06, decided
      2026-11-17). Its site is `pborenstein/twohorses`; when `status`
      shows it as `no domain`, unlink it. Its repo also builds
      twohorses.lol on Netlify; `delete` now keeps the repo (DEC-057).

## Blockers: none

## Context

- mimeo reports a problem with its fix steps, and `sync` does the fix
      when it can write the zone (DEC-048, DEC-050).
- The proxy setting changes only during that certificate sequence.
- Porkbun requests are spaced 0.25s; `status --all` takes a minute.
- 24 of 109 hostnames are on Cloudflare; 7 are on Netlify sites.
- Live config: three organizations, `defaults.dns = "cloudflare"`.
- 002370.xyz is the junk domain, on Cloudflare again since 2026-11-17.
- Porkbun can move a domain to Cloudflare itself (account connected
      2026-11-22); mimeo needs no change for it (DEC-053).

## Next Session

Start the Netlify task list in `docs/IMPLEMENTATION.md`, Phase 9: check
the three Netlify facts, then let `Fleet` hold a list of hosts.
Separately: blueberryhill.fyi renewal near 2026-12-23.
