---
phase: 8
phase_name: Consolidation
updated: 2026-11-17
last_commit: acf24f8
last_entry: 94
---

## Current Focus

mimeo 2.0.0 was released from `main` on 2026-11-17 (tag `v2.0.0`, the
repository's first tag). It is in live use and every site reads `ok`.

## Active Tasks

- [ ] **blueberryhill.fyi** renewal near 2026-12-23, behind the proxy:
      on `cert error`, `mimeo sync blueberryhill.fyi` is the first run
      of DEC-050 on a real failure.
- [ ] **Not yet run live**: `sync` writing records to a Cloudflare
      zone. (The move back to Porkbun ran 2026-11-17.)
- [ ] **tequitl.dev is being left to expire** (2026-12-06, decided
      2026-11-17). Its site is `pborenstein/twohorses`; when `status`
      shows it as `no domain`, pick unlink, delete or move.
- [ ] **Unverified vendor facts** behind `delegate`'s warnings: Email
      Routing and Porkbun mail forwarding (DEC-051).
- [ ] **Small fixes**: `sync --dry-run` says "N changed"; `status`
      shows only dashes for spacemang.com and spacemang.org.
- [ ] **Cache**: record the organizations it was built from.
- [ ] **mimeo.lol** returns GitHub's 404 (repo has no custom domain).

## Blockers: none

## Context

- mimeo reports a problem with its fix steps, and `sync` does the fix
      when it can write the zone (DEC-048, DEC-050).
- The proxy setting changes only during that certificate sequence.
- Porkbun requests are spaced 0.25s; `status --all` takes a minute.
- Live config: three organizations, `defaults.dns = "cloudflare"`.
- 002370.xyz is the junk domain, back on Porkbun since 2026-11-17.

## Next Session

Nothing is in progress. Next live test: move 002370.xyz to Cloudflare,
break a record by hand, and run `mimeo sync 002370.xyz`.
