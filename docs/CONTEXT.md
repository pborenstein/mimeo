---
phase: 8
phase_name: Consolidation
updated: 2026-11-15
last_commit: 2f0c846
last_entry: 90
---

## Current Focus

Preparing the mimeo 2.0 design session (DEC-038). Proposed scope: mimeo connects
a domain to the host serving its site (domain, nameservers, DNS
records, site) and stops growing site creation. Notes, command
sketch and open questions: `docs/MIMEO2.md`.

## Active Tasks

- [ ] **2.0 design session**: work `docs/MIMEO2.md` open questions
      into DECISIONS.md entries.
- [ ] **Template org move** (Entry 89): config `template_org`, code
      default, README/ARCHITECTURE refs, 307 message. twohorses.org
      still uncreated.
- [ ] **Netlify second host**: staging pass 1 (repo/host split) is
      what 2.0's `SITE` argument needs; open: OD #2, #4, #5, #7, #8.
- [ ] **Backlog**: AAAA records, undecided.

## On Ice (2026-09-29, user call)

- **Template apply** (Entry 68). **Subdomain sites**:
      `docs/SUBDOMAINS.md` (revisit in 2.0, MIMEO2.md question 6).

## Blockers: none

## Context

- DNS is moving to Cloudflare; blueberryhill.fyi and xhosi.com are
      delegated and proxied to GitHub Pages. `status` now treats
      Porkbun records as live only on Porkbun nameservers (DEC-037).
- Sites can live in any GitHub account; `status`/`sync` only see the
      configured one (blueberryhill.fyi shows `no repo`).
- Stable facts: `CLAUDE.md` "Project Facts"; config and exit codes:
      `docs/ARCHITECTURE.md`; Netlify: `docs/NETLIFY.md`.
- Current release is 1.3.0; the redesign ships as 2.0.
- `docs/SITE_ADDRESS.md` is stale, not a 2.0 input (DEC-038).

## Next Session

Start the 2.0 design session from `docs/MIMEO2.md`: settle scope,
then open questions one at a time, recording each as a DEC entry.
