---
phase: 8
phase_name: Consolidation
updated: 2026-10-26
last_commit: 794abb7
last_entry: 88
---

## Current Focus

Entry 83's two defects are closed (Entry 86: one fixed, one was not a
bug), D1 shipped, and doctor checks the Pages IPs (Entry 85). No code
work is in flight.

## Active Tasks

- [ ] **Netlify second host**: DNS decided (DEC-033); OD #1, #3, #6
      decided — open: #2, #4, #5, #7, #8; staging pass 1 (repo/host
      split) is a pure refactor, landable on its own.
- [ ] **Command model**: `docs/SITE_ADDRESS.md` proposed,
      undecided; more command questions queued from the user.
- [ ] **Backlog**: none from CODE_REVIEW rec #6 (Pages IPs: doctor
      check, Entry 85; D1: Entry 86). Open: AAAA records undecided.

## On Ice (2026-09-29, user call)

- **Template apply**: Entry 68 design (open questions preserved
      there). **Subdomain sites**: `docs/SUBDOMAINS.md`; parked.

## Blockers

None.

## Context

- Stable project facts (templates, org model, disk layout, doc
      style, releases, tests) live in `CLAUDE.md` "Project Facts";
      config and exit codes in `docs/ARCHITECTURE.md`.
- Netlify design and its unverified-claims table:
      `docs/NETLIFY.md` (Entries 72–77).
- Template sub-repo decisions (chapbook `dek`/`content/img`,
      pamphlet drafts) live in their own repos' DECISIONS.md.
- `pborenstein.ooo` expired 2026-10-05 with API access off; its
      parking CNAME stays (user call, Entry 84).

## Next Session

The fleet is converged (`sync --all --dry-run` plans nothing). Next:
the command-model question (`docs/SITE_ADDRESS.md`), walked through one decision at a
time, or Netlify staging pass 1.
