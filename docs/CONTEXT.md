---
phase: 8
phase_name: Consolidation
updated: 2026-11-16
last_commit: 22f48c3
last_entry: 92
---

## Current Focus

mimeo 2.0 is built on branch `mimeo-2.0-design` (not pushed, merged or
released; version 2.0.0b1). The live config is on schema 2 and the
Cloudflare provider reads the live account. No command that writes has
run live yet.

## Active Tasks

- [ ] **`mimeo scan`**: the live cache holds only `mimeo-sites` sites
      (filled before `organizations` was set).
- [ ] **`mimeo status --all`**: read it against expectations.
- [ ] **First live writes**: `sync --dry-run` then `sync` on one
      Porkbun-served site (adds four AAAA); `delegate --dry-run` then
      `delegate` on a junk domain (first use of Zone Edit).
- [ ] **Cache**: record the organizations it was built from; rescan
      when the config's list differs.
- [ ] **xhosi.com certificate** expires 2026-12-12, renewal failing;
      manual steps in IMPLEMENTATION.md. blueberryhill.fyi is next,
      near 2026-12-23.
- [ ] **mimeo.lol** returns GitHub's 404 (its repo became
      `mimeo-templates/mimeo`, no custom domain). twohorses.org still
      uncreated.
- [ ] **Release**: 1.4.0 is commit `62eeff7`; 2.0.0 from the branch tip.
- [ ] **Stale docs**: TROUBLESHOOTING.md, SUBDOMAINS.md, NETLIFY.md.

## Blockers: none

## Context

- How 2.0 works: README "How it works". Design and where the code
      differs from it: `docs/MIMEO2_DESIGN.md` ("As Built"). Decisions:
      DEC-039 to DEC-047. History: Entries 91 and 92.
- Live config: three organizations, `[cloudflare]` set, `defaults.dns`
      unset (Porkbun). 1.x copy at `config.toml.v1.bak` beside it.
- Cloudflare token: account-owned, All Domains, DNS Edit + Zone Read +
      Zone Edit. Zone Edit and every write path are untested live.
- mimeo reports certificate trouble on proxied domains and does not
      act on it (DEC-043); a proxied name needs no AAAA (DEC-047).
- Tests run commands against in-memory providers (`tests/fakes.py`).

## Next Session

Run `mimeo scan`, then `mimeo status --all`, and go through the output
before any `sync`. Then the first live write on one Porkbun site.
