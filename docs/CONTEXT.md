---
phase: 5
phase_name: CLI Integration
updated: 2026-02-16
last_commit: 75c27c1
---

## Current Focus

Made create command idempotent: handles existing repos by skipping content push, still configures GitHub Pages and DNS.

## Active Tasks

- [x] Fix create command for existing repositories (skip push, configure DNS)
- [ ] Document workflow scope requirement in setup docs
- [ ] Add configuration option for HTTPS enforcement
- [ ] Document uv tool install for global CLI access

## Blockers

None.

## Context

- create command now detects existing repos via _gh_api check before push
- New repos: creates repo + pushes content + configures Pages + DNS
- Existing repos: skips push, still configures Pages settings + DNS
- _repo_was_created flag on GitHubHost communicates this to CLI
- CLI shows "Repository exists / Skipped content push" for existing repos
- 152 tests passing (added 1 new test for existing repo case)

## Next Session

Document setup requirements (workflow scope, uv tool install). Consider adding config options for HTTPS enforcement behavior.
