---
phase: 8
phase_name: Consolidation
updated: 2026-11-22
last_commit: f17589e
last_entry: 98
---

## Current Focus

mimeo 2.1.0 is the current release (tag `v2.1.0`, 2026-11-17; 2.0.0 was
released earlier the same day). It is in live use and every site reads `ok`.
On 2026-11-22 a batch of domains moved to Cloudflare; 24 of 109 hostnames
are on Cloudflare and all read `ok` (Entry 98).

## Active Tasks

- [ ] **blueberryhill.fyi** certificate renewal near 2026-12-23, proxied:
      on `cert error`, `mimeo sync blueberryhill.fyi` is the first run
      of DEC-050 on a real failure.
- [ ] **tequitl.dev is being left to expire** (2026-12-06, decided
      2026-11-17). Its site is `pborenstein/twohorses`; when `status`
      shows it as `no domain`, pick unlink, delete or move.

## Blockers: none

## Context

- mimeo reports a problem with its fix steps, and `sync` does the fix
      when it can write the zone (DEC-048, DEC-050).
- The proxy setting changes only during that certificate sequence.
- Porkbun requests are spaced 0.25s; `status --all` takes a minute.
- Live config: three organizations, `defaults.dns = "cloudflare"`.
- 002370.xyz is the junk domain, on Cloudflare again since 2026-11-17.
- Porkbun can move a domain to Cloudflare itself (account connected
      2026-11-22); mimeo needs no change for it (DEC-053).

## Next Session

Nothing is in progress. The one live path left is the proxy sequence
on a real failed certificate renewal (blueberryhill.fyi, near 2026-12-23).
