---
phase: 8
phase_name: Consolidation
updated: 2026-07-06
last_commit: b53a591
---

## Current Focus

Phase 8 planned: reverse barnacleization. Mimeo reframed as a fleet manager
for domain-to-GitHub-Pages sites. Collapse per-incident verbs into
declarative `status`/`sync`; unify CLI fan-out plumbing first. See DEC-021.

## Active Tasks

- [ ] Stage 1: shared domain-operation engine in `_processing.py`; migrate
      registrar list, dns check/show, fix https, list onto it
- [ ] Stage 2: `mimeo status` (cross-provider join: registrar x DNS x Pages)
- [ ] Stage 3: `mimeo sync` (converge: DNS repair + HTTPS enforcement)
- [ ] Stage 4: E2E test lane (gated, real APIs, covers create/status/sync)
- [ ] Identity fix ("Provision and manage custom-domain sites on GitHub Pages")
- [ ] Template parameterization (carried from Phase 7)

## Blockers

None.

## Context

- Phase 7 closed 2026-07-06; 243 tests passing, mypy and ruff clean
- Stages are ordered: engine first (pure debt paydown), then status, then sync
- Template apply stays manual — content is a choice, not drift (DEC-021)
- Fate of dns repair / fix https (alias vs deprecate) decided during Stage 3
- cli/ is ~1,850 lines; Stage 1 should shrink it measurably

## Next Session

Start Stage 1: design the shared domain-operation engine API in
`_processing.py`, then migrate `registrar list` onto it as the first consumer.
