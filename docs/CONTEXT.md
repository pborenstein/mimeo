---
phase: 8
phase_name: Consolidation
updated: 2026-11-18
last_commit: 274ae0b
last_entry: 96
---

## Current Focus

mimeo 2.0.0 was released from `main` on 2026-11-17 (tag `v2.0.0`, the
repository's first tag). It is in live use and every site reads `ok`.
README, TROUBLESHOOTING and the design's As Built match 2.0 (Entry 95).

## Active Tasks

- [ ] **blueberryhill.fyi** certificate renewal near 2026-12-23, proxied:
      on `cert error`, `mimeo sync blueberryhill.fyi` is the first run
      of DEC-050 on a real failure.
- [ ] **tequitl.dev is being left to expire** (2026-12-06, decided
      2026-11-17). Its site is `pborenstein/twohorses`; when `status`
      shows it as `no domain`, pick unlink, delete or move.
- [ ] **mimeo.lol** returns GitHub's 404: no repository has it as its
      custom domain since `pborenstein/mimeo.lol` became
      `mimeo-templates/mimeo`. Needs a decision on what it serves.

## Blockers: none

## Context

- mimeo reports a problem with its fix steps, and `sync` does the fix
      when it can write the zone (DEC-048, DEC-050).
- The proxy setting changes only during that certificate sequence.
- Porkbun requests are spaced 0.25s; `status --all` takes a minute.
- Live config: three organizations, `defaults.dns = "cloudflare"`.
- 002370.xyz is the junk domain, on Cloudflare again since 2026-11-17.

## Next Session

Nothing is in progress. The one live path left is the proxy sequence
on a real failed certificate renewal (blueberryhill.fyi, near 2026-12-23).
