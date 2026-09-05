---
phase: 8
phase_name: Consolidation
updated: 2026-09-05
last_commit: 6c72003
---

## Current Focus

Surveyed the template parameterization backlog item (Entry 42). Investigation
only, no code changes. The design shape is an open decision.

## Active Tasks

- [ ] **Template parameterization: pick a design shape**
      Three candidates: (1) manifest in each template repo declaring
      substitutable files/tokens, (2) token convention (`{{MIMEO_SITE_URL}}`)
      with a repo-wide walk, (3) mimeo-side per-template registry. Leaning (1)
      — it's the only one where a non-eleventy template costs nothing.
      Tradeoffs in Entry 42.

- [ ] **Prerequisite: scrub leaked identity from two templates**
      `eleventy-tech-blog` and `eleventy-prose-blog` ship `pborenstein.dev`/
      `.com`, real email, and a `pborenstein.2025` git URL. Lives in
      mimeo-sites, not this repo.

- [ ] **Track B: Stage 4 E2E test lane**
      Gated (real APIs). Blocked on having a test account/org.

- [ ] **Backlog: Dead params in `HTTPClient`**
      `max_retries`/`backoff_factor` in `http.py` never read. Only
      `tests/utils/test_http.py:27-28` passes them.

## Blockers

None. Template parameterization needs a design decision, not unblocking.

## Context

- Site identity lives in a different file/format per template family:
  `content/_data/metadata.js` + `package.json`, inline object in
  `eleventy.config.js`, YAML frontmatter in `index.md`, hardcoded HTML
- `_customize_default_template` (`github.py:329-377`) handles only `mimeo.lol`;
  gated at `github.py:324-325`. Preserve its 5x/2s retry and `updated ==
  content` no-op guard in any redesign
- Templates are discovered live from the `tepiton` org — no local list, so
  `validate_template` is a GitHub API existence check
- 297 tests passing; mypy and ruff clean

## Next Session

Decide the parameterization design shape, then plan against it. Unrelated
easy pick if you'd rather: remove the dead `HTTPClient` params.
