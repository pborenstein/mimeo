---
phase: 8
phase_name: Consolidation
updated: 2026-11-02
last_commit: 189c75b
last_entry: 89
---

## Current Focus

`create` fails with `gh: HTTP 307` because the templates moved from
`tepiton` to `mimeo-templates` and `template_org` still says
`tepiton` (Entry 89). Diagnosed, not yet fixed.

## Active Tasks

- [ ] **Template org move**: set config `template_org`, change the
      code default and README/ARCHITECTURE refs, report 307s as
      "moved to X". twohorses.org is still uncreated.
- [ ] **Netlify second host**: DNS decided (DEC-033); OD #1, #3, #6
      decided — open: #2, #4, #5, #7, #8; staging pass 1 (repo/host
      split) is a pure refactor, landable on its own.
- [ ] **Command model**: `docs/SITE_ADDRESS.md` proposed,
      undecided; more command questions queued from the user.
- [ ] **Backlog**: CODE_REVIEW rec #6 done (DEC-035, DEC-036). Open:
      AAAA records, undecided.

## On Ice (2026-09-29, user call)

- **Template apply**: Entry 68 design (open questions preserved
      there). **Subdomain sites**: `docs/SUBDOMAINS.md`; parked.

## Blockers: none

## Context

- Stable project facts (templates, org model, disk layout, doc
      style, releases, tests) live in `CLAUDE.md` "Project Facts";
      config and exit codes in `docs/ARCHITECTURE.md`.
- Netlify design and its unverified-claims table:
      `docs/NETLIFY.md` (Entries 72–77).
- Template docs (incl. sub-repo decisions) live in the tepiton
      meta-repo (`~/projects/tepiton/`), not here.
- `pborenstein.ooo` expired 2026-10-05; parking CNAME stays (Entry 84).

## Next Session

Finish the template-org move, then retry `mimeo create twohorses.org`.
After that: `docs/SITE_ADDRESS.md` one decision at a time, or Netlify
staging pass 1.
