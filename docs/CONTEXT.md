---
phase: 8
phase_name: Consolidation
updated: 2026-10-26
last_commit: a5045ae
last_entry: 85
---

## Current Focus

Template consolidation is done (Entries 81–82). Open code work is
the two Entry 83 `create` defects; Entry 84 was an ops pass (Porkbun
parking CNAMEs removed from 54 domains).

## Active Tasks

- [ ] **Entry 83 fixes**: `_gh_api` drops the response `errors`
      array; `required_dns_records` uses `default_org` for `www`,
      ignoring `--deploy-org` (github.py:994). Test-first.
- [ ] **Netlify second host**: DNS decided (DEC-033); OD #1, #3, #6
      decided — open: #2, #4, #5, #7, #8; staging pass 1 (repo/host
      split) is a pure refactor, landable on its own.
- [ ] **Command model**: `docs/SITE_ADDRESS.md` proposed,
      undecided; more command questions queued from the user.
- [ ] **Backlog**: D1 -- `sync` adds only what's missing (CODE_REVIEW
      rec #6). Pages IPs item closed by the doctor check (Entry 85).

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

Fix the two Entry 83 defects test-first. After that: Netlify staging
pass 1 or the `docs/SITE_ADDRESS.md` command-model question.
