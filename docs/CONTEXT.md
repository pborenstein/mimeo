---
phase: 8
phase_name: Consolidation
updated: 2026-11-17
last_commit: c79ed04
last_entry: 93
---

## Current Focus

mimeo 2.0 (2.0.0b1, branch `mimeo-2.0-design`, not pushed, merged or
released) has now written live: `sync` on 61 sites, one `delegate` to
Cloudflare, five certificates requested. One site still has a problem.

## Active Tasks

- [ ] **xhosi.com certificate** expires 2026-12-12, renewal blocked by
      the Cloudflare proxy. `mimeo status xhosi.com` prints seven steps;
      doing them is their first test. blueberryhill.fyi follows near
      2026-12-23.
- [ ] **Not yet run live**: `delegate 002370.xyz --dns porkbun` (the
      move back); `sync` writing to a Cloudflare zone.
- [ ] **Registrations expiring** 2026-11-24 to 2026-12-06 (list in
      Entry 93); auto-renew not checked.
- [ ] **Small fixes**: `sync --dry-run` says "N changed"; `status`
      shows only dashes for spacemang.com and spacemang.org (registered
      in another Porkbun account).
- [ ] **Cache**: record the organizations it was built from; rescan
      when the config's list differs.
- [ ] **mimeo.lol** returns GitHub's 404 (repo has no custom domain).
- [ ] **Release** (1.4.0 is `62eeff7`); `docs/TROUBLESHOOTING.md` and
      `docs/MIMEO2_DESIGN.md` "As Built" predate Entry 93.

## Blockers: none

## Context

- A reported problem carries its fix steps, and `sync` requests a
      missing certificate when records are right and unproxied
      (DEC-048). mimeo still never changes a proxy setting (DEC-043).
- Porkbun requests are spaced 0.25s; `status --all` takes about a
      minute (DEC-049).
- Live config: three organizations, `[cloudflare]` set,
      `defaults.dns = "cloudflare"`.
- 002370.xyz is the junk domain, now on Cloudflare. History: Entry 93.

## Next Session

Do the seven steps for xhosi.com and correct them in `mimeo/plan.py` if
they are wrong. Then `delegate 002370.xyz --dns porkbun`.
