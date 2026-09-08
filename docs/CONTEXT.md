---
phase: 8
phase_name: Consolidation
updated: 2026-09-08
last_commit: bdddd22
---

## Current Focus

Template parameterization design shape is decided (DEC-024): a per-template
manifest declaring where each template's own self-reference (title,
metadata `url:`, frontmatter) lives, so `deploy_site` can stamp the target
domain in — scoped narrowly to that one fact, not general template
authoring. Not yet implemented.

## Active Tasks

- [ ] **Implement DEC-024**: `mimeo.template.json` manifest schema + three
      format handlers (`js-key`, `string-replace`, `yaml-frontmatter-key`)
      replacing `_customize_default_template`. Add manifests to templates in
      mimeo-sites, starting with `mimeo.lol` (already relied on).

- [ ] **Track B: Stage 4 E2E test lane**
      Gated (real APIs). Blocked on having a test account/org.

- [ ] **Backlog: Dead params in `HTTPClient`**
      `max_retries`/`backoff_factor` in `http.py` never read. Only
      `tests/utils/test_http.py:27-28` passes them.

## Blockers

None.

## Context

- Scope boundary (DEC-024): mimeo propagates the target domain into a
  template's declared self-reference point only — not bios, copy, or other
  branding. That kind of authoring work belongs in mimeo-sites (see Entry 43).
- 8 templates surveyed, 3 self-reference formats: hardcoded HTML string
  (mimeo.lol, laptopistan.com), JS object key `url:` in
  `content/_data/metadata.js` (5 eleventy-* templates), YAML frontmatter
  `title:` (pandoc-simple). Token-convention approach rejected — doesn't fit
  the JS-key case cleanly.
- Manifest absent on a template → substitution skipped, not an error (same
  as today's behavior for every template except mimeo.lol).
- `_customize_default_template` (`github.py:329-377`) is the code being
  replaced; preserve its 5x/2s retry against the "repo not populated yet"
  race.
- 297 tests passing; mypy and ruff clean (no code touched this session).

## Next Session

Implement the DEC-024 manifest schema and format handlers in
`github.py`/`create.py`, then add `mimeo.template.json` to `mimeo.lol` first
since `create` already depends on that substitution working.
