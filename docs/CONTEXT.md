---
phase: 8
phase_name: Consolidation
updated: 2026-09-09
last_commit: fa0c02e
---

## Current Focus

DEC-024 implemented and committed (`13583f7`, Entry 56): manifest-driven
template substitution replaces the mimeo.lol hardcode. Schema ratified in
DEC-024's addendum. mimeo-side work is done; the templates' own manifests
are the remaining piece, and they live in mimeo-sites, not here.

## Active Tasks

- [ ] **mimeo-sites follow-up**: add `mimeo.template.json` to each of the
      10 templates. mimeo.lol first: one `string-replace` entry
      (`match: "mimeo.lol"`), enabled by its CSS letter-spacing fix.
- [ ] **Stage 6**: `template lint` — now gated only on a real manifest
      existing on a template (schema/handlers are done).
- [ ] **Track B**: Stage 4 E2E test lane, blocked on test account/org.
- [ ] **Backlog**: BUG 4/6/7 and the error-semantics refactor
      (`docs/CODE_REVIEW.md` rec #2) — not started.
- [ ] **Backlog**: D2 (`default_registrar`/`default_host`) — decide
      factory vs. removal.
- [ ] **Subdomain sites**: four open decisions in SUBDOMAINS.md.

## Blockers

Stage 6 blocked on the first real manifest landing (mimeo-sites). The rest
unblocked.

## Context

- Manifest schema (DEC-024 addendum): `version` (=1), optional `dev_paths`
  (replaces defaults `README.md`/`docs/`/`CLAUDE.md` wholesale), non-empty
  `substitutions`, `{domain}`-only templating, all failures loud.
- `js-key` is loosey-goosey: dotted path to a unique string-literal leaf
  through any object literal; set-by-key, indifferent to placeholders.
- mimeo.lol deploys are uncustomized until its manifest lands (accepted
  window); verification is mock-based — live-`create` once a manifest exists.
- 333 tests passing, mypy clean, ruff at the pre-existing 5-error baseline.

## Next Session

Either write mimeo.lol's manifest in mimeo-sites and live-smoke-test
`create`, or start CODE_REVIEW rec #2 (error-semantics refactor), or
tackle the SUBDOMAINS.md decisions.
