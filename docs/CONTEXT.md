---
phase: 8
phase_name: Consolidation
updated: 2026-11-15
last_commit: c7a4753
last_entry: 91
---

## Current Focus

mimeo 2.0 is designed and built on branch `mimeo-2.0-design` (DEC-039
to DEC-046, Entry 91). Not merged, not released, and not yet run
against live APIs for anything that writes. Design:
`docs/MIMEO2_DESIGN.md`; what differs from it: its "As Built" section.

## Active Tasks

- [ ] **Live config**: add `github.organizations =
      ["mimeo-sites", "tepiton", "pborenstein"]`; run `mimeo scan`.
- [ ] **Cloudflare, read-only first**: add `[cloudflare]` (token with
      Zone:Read and DNS:Edit; `account_id` for zone creation); run
      `mimeo doctor`, then `mimeo status blueberryhill.fyi xhosi.com
      --records`.
- [ ] **First live writes**: `mimeo sync` one Porkbun-served site (adds
      four AAAA); `delegate --dry-run` then `delegate` on a junk domain.
- [ ] **Verify vendor facts** in MIMEO2_DESIGN.md "To Verify at
      Implementation" (Cloudflare zone creation and record import,
      Porkbun DNSSEC lookup, AAAA and certificates).
- [ ] **Release**: 1.4.0 is commit `62eeff7`; branch tip is 2.0.0b1.
- [ ] **Leftovers**: `docs/TROUBLESHOOTING.md` describes 1.x; smoke
      script needs `delegate`; `docs/SUBDOMAINS.md` and
      `docs/NETLIFY.md` predate 2.0.

## Found This Session

- xhosi.com: GitHub certificate renewal failing (`bad_authz`), expires
      2026-12-12; records proxied through Cloudflare (DEC-043).
- mimeo.lol returns GitHub's 404: its repo is now
      `mimeo-templates/mimeo`, with no custom domain.
- twohorses.org still uncreated (Entry 89); the template org default
      is fixed, so `create` should work once the config key is too.

## Blockers: none

## Context

- 2.0 in one paragraph: every command reads the registration,
      nameservers, records (at the provider the nameservers name) and
      site for a hostname, compares them with what the host needs, and
      applies or prints the changes. README "How it works".
- A site is the repo whose Pages custom domain is the hostname, in any
      organization in `github.organizations`; cached in
      `~/.cache/mimeo/sites.json`.
- A 1.x config loads unchanged and behaves as 1.x did.
- Stable facts: `CLAUDE.md` "Project Facts"; config and exit codes:
      `docs/ARCHITECTURE.md`.

## Next Session

Update the live config, run `mimeo scan` and `mimeo status --all`, and
compare against what 1.3.0 reports before any command that writes.
