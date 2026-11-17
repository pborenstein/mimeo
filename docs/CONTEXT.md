---
phase: 8
phase_name: Consolidation
updated: 2026-11-17
last_commit: f853a58
last_entry: 94
---

## Current Focus

mimeo 2.0 (2.0.0b1, branch `mimeo-2.0-design`, not pushed, merged or
released) is in live use. Every site reads `ok`. `sync` now fixes certificate
trouble itself and `delegate` asks before stopping a service.

## Active Tasks

- [ ] **blueberryhill.fyi** renewal near 2026-12-23, behind the proxy:
      on `cert error`, `mimeo sync blueberryhill.fyi` is the first run
      of DEC-050 on a real failure.
- [ ] **Not yet run live**: `delegate 002370.xyz --dns porkbun` (the
      move back); `sync` writing records to a Cloudflare zone.
- [ ] **Auto-renew is off** for tequitl.dev (has a live site) and
      tequitl.agency, expiring 2026-12-06, and for ayeye.dev and
      ayeye.rodeo, expiring 2026-11-27. Read 2026-11-17.
- [ ] **Unverified vendor facts** behind `delegate`'s warnings: Email
      Routing and Porkbun mail forwarding (DEC-051).
- [ ] **Small fixes**: `sync --dry-run` says "N changed"; `status`
      shows only dashes for spacemang.com and spacemang.org.
- [ ] **Cache**: record the organizations it was built from.
- [ ] **mimeo.lol** returns GitHub's 404 (repo has no custom domain).
- [ ] **Release** (1.4.0 is `62eeff7`); `docs/TROUBLESHOOTING.md` and
      `docs/MIMEO2_DESIGN.md` "As Built" predate Entry 93.

## Blockers: none

## Context

- mimeo reports a problem with its fix steps, and `sync` does the fix
      when it can write the zone (DEC-048, DEC-050).
- The proxy setting changes only during that certificate sequence.
- Porkbun requests are spaced 0.25s; `status --all` takes a minute.
- Live config: three organizations, `defaults.dns = "cloudflare"`.
- 002370.xyz is the junk domain, on Cloudflare, DNS-only.

## Next Session

Run `delegate 002370.xyz --dns porkbun`, then `sync` on a Cloudflare
zone with a record removed. Check auto-renew on the expiring domains.
