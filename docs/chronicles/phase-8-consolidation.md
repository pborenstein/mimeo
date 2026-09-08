# Phase 8: Consolidation Chronicles

## Entry 43: Scrub leaked identity from eleventy-tech-blog / eleventy-prose-blog (2026-09-05)

**What**: Removed real personal identity from both templates in mimeo-sites
(not this repo) — the Entry 42 prerequisite. `content/_data/metadata.js`,
`package.json`, `CLAUDE.md`, `base.njk` (tech-blog's hardcoded `@pborenstein`
twitter tag), and `docs/*.md`/chronicles now use placeholder identity
(`Author Name`, `example.com`) matching chapbook/folio/pamphlet. Also
replaced all personal demo content — 10 posts (tech-blog) and 26 posts plus
a stray page (prose-blog), all real personal essays/bio with no generic
equivalent — with one purpose-built `welcome.md` per template exercising the
template's actual features (footnotes, code blocks, mermaid for tech-blog;
intentional linebreaks for prose-blog). Kept 4 already-generic git/eleventy
tutorial posts in tech-blog.

**Why**: Both templates were forks of the user's real personal blogs
(`pborenstein.dev`, `pborenstein.com`) shipping real name/email/domain/social
handles in config that ends up in every generated site, plus dozens of real
personal essays as "demo content" — confusing for anyone forking the
template and not something to keep re-publishing per site.

**How**: Decided against scrubbing-in-place for the essays (many are book
reviews/personal reflections with no generic version) in favor of full
replacement with small purpose-built posts. `package-lock.json` regenerated
via `npm install --package-lock-only` rather than hand-edited. Both
templates verified building clean (`npm run build`) after the pass. Peer
Claude sessions on eleventy-tech-blog and eleventy-prose-blog notified
directly since the changes touch files they may have open; nothing
committed there yet.

**Files**: mimeo-sites/TEMPLATES/eleventy-tech-blog/*, mimeo-sites/TEMPLATES/eleventy-prose-blog/*
(outside this repo)

## Entry 42: Template parameterization survey — no code changes (2026-09-05)

**What**: Investigation only. Surveyed all seven tepiton templates in
`~/projects/mimeo-sites/TEMPLATES` and traced mimeo's template path to scope
the carried-over parameterization item. No code written; design shape is a
decision still owed.

**Why**: `_customize_default_template` (`github.py:329-377`) only knows how to
un-brand `mimeo.lol` — two literal `str.replace` calls on `index.html`, gated
at `github.py:324-325` on `template_repo == DEFAULT_TEMPLATE`. Every other
template ships its own branding into the generated site. Generalizing needs to
stay platform-agnostic: not every site is an eleventy site.

**How**: Site identity turns out to live in a different file and format per
family — `content/_data/metadata.js` plus `package.json` (tech-blog,
prose-blog, chapbook, folio), an inline object in `eleventy.config.js:45-48`
(pamphlet), YAML frontmatter in `index.md:1-7` (pandoc-simple), hardcoded
`<title>`/`<h1>` (mimeo.lol). So a single hardcoded file path cannot generalize.
Three candidate shapes: (1) a manifest in each template repo declaring its
substitutable files/tokens — self-describing, no mimeo release per new
template, costs a one-time edit to seven repos plus a 404-tolerant fetch;
(2) a token convention (`{{MIMEO_SITE_URL}}`) with a repo-wide walk — simplest
mimeo-side, no declared intent; (3) a mimeo-side registry — no template repo
changes, but every new template needs a code change, cutting against
platform-agnosticism. Leaning (1).

Also found: `eleventy-tech-blog` and `eleventy-prose-blog` contain real
live-site identity rather than placeholders — `pborenstein.dev`/`.com`, real
email, and a `pborenstein.2025` git URL in `package.json`. Anyone generating
from those inherits it. The other three eleventy templates already use
`example.com`, so the convention exists; those two diverge. Fix lives in
mimeo-sites.

Two properties of the current implementation worth preserving in any redesign:
the 5x/2s empty-repo read retry, and the `updated == content` no-op guard that
makes re-runs safe.

**Decisions**: none yet — design shape open

**Files**: none (investigation); `docs/IMPLEMENTATION.md` backlog expanded

## Entry 41: Fold process_domains_concurrent into map_items; template validation fix (2026-09-05)

**What**: Completed Track A from Entry 40's plan. Migrated `dns repair`,
`template apply`, and `create` from `process_domains_concurrent` to
`map_items` + `render_results` + `exit_on_errors`. Deleted the old function,
`exit_on_failures`, and the unused `Lock`/`_console_lock` from `_processing.py`.
Also found and fixed a latent inconsistency: `create` had no upfront template
validation while `template apply` called `validate_template()` before its loop.

**Why**: One fan-out system instead of two; consistent result schema across all
commands; `create` with a bad template name now fails fast with a clear message
rather than surfacing per-domain errors mid-run.

**How**: Each command's `process_fn` now lets exceptions propagate to
`map_items`'s `on_error` handler. The `log` closure drops its result-list
accumulation; the `success` and `log` result fields are gone. Text output moves
into a `_text` callback passed to `render_results`. Two test assertions updated:
mid-run progress banners (`"site1.com started"`) were artifacts of the old
function, not meaningful behavior.

**Files**: `mimeo/cli/_processing.py`, `mimeo/cli/dns.py`,
`mimeo/cli/template.py`, `mimeo/cli/create.py`, `tests/test_cli.py`
**Commits**: `337b359`, `f02ca53`

## Entry 40: Code review deep-dive; plan for process_domains_concurrent removal (2026-09-05)

**What**: Full read-through of all source files. No code changes.

**Why**: Repo was organically grown across 8 phases. Wanted a clear mental
model before the next round of cleanup, and to assess whether it could go public.

**Findings**:
- Privacy: clean for public release. Two `*.nogit.json` files (full domain
  inventory) are blocked by global gitignore `*.nogit*`, not committed.
  Only personal identifiers in git are two README clone URLs and one
  IMPLEMENTATION.md reference link.
- Two parallel fan-out systems in `_processing.py`: `process_domains_concurrent`
  (older, used by `create`/`dns repair`/`template apply`) and `map_items` +
  `render_results` + `exit_on_errors` (newer, used by everything else).
  Within the `dns` group, `check`/`show` use the new path, `repair` uses the old.
- `HTTPClient` has two dead constructor params noted as "kept for API compat".
- `_customize_default_template` is special-cased by template name; `eleventy-*`
  parameterization is a separate, harder problem.

**Plan for next session**: Migrate `dns repair`, `template apply`, `create`
(in that order) from `process_domains_concurrent` to `map_items`. Then delete
`process_domains_concurrent`. See CONTEXT.md Next Session section.

**Files**: docs/CONTEXT.md (updated with plan)

## Entry 39: list --show-template; validate template name; rename-by-ID fix (2026-08-27)

**What**: Three improvements in one session.

**list --show-template**: New flag on `mimeo list` fetches `template_repository`
per repo via parallelized `gh api repos/<owner>/<repo>` calls and adds a TEMPLATE
column. GitHub's search API doesn't expose this field, so a per-repo call is
unavoidable; the flag makes it opt-in so the default list stays fast.

**template apply early validation**: `validate_template()` on `GitHubHost`
checks that `TEMPLATE_ORG/<name>` exists before the confirmation prompt runs.
A typo now fails immediately with "Template 'x' not found in tepiton. Check the
spelling and try again." instead of renaming repos and then 422ing mid-flow.

**rename-by-ID fix**: `_rename_repository` was using `PATCH repos/<owner>/<name>`,
which GitHub 307-redirects when the repo was previously renamed. Switched to
fetching the repo ID first, then PATCHing `repositories/<id>` (stable across
renames). Added one 422 retry with 3s sleep for rapid successive renames. See
DEC-023.

**Stale artifacts fix**: `template apply --force` left old `github-pages`
artifacts on the repo after recreate; GitHub's deploy-pages action fails with
"Multiple artifacts named 'github-pages' were unexpectedly found." Added
`_delete_stale_pages_artifacts` — called after a successful force-replace —
which keeps only the newest artifact and deletes the rest.

**Decisions**: DEC-023

**Files**: `mimeo/providers/host/github.py`, `mimeo/cli/list_cmd.py`,
`mimeo/cli/template.py`; commits `c3b1923`, `65e7be7`

---

## Entry 38: template apply --force deleted a live repo -- rename-not-delete fix (2026-08-25)

**What**: Live `template apply --template mellowtimesphere.com laptopistan.com` deleted
`tepiton/laptopistan.com` and then failed with a 404 on the template-generate call, because
`mellowtimesphere.com` wasn't flagged `is_template` on GitHub. `_create_from_template` deleted
the target repo *before* attempting generate, with no rollback on failure. Restored via GitHub
org deleted-repo restore (works because `tepiton` is an Organization; would not have worked for
a personal-owned repo). See DEC-022.

**Why**: `is_template: false` on the source repo makes GitHub's `generate` endpoint return a
bare 404 indistinguishable from "repo doesn't exist" -- no error message pointed at the real
cause. Root cause confirmed via `gh api repos/tepiton/mellowtimesphere.com --jq .is_template`.
Separately, delete-before-generate meant *any* generate failure -- not just this one -- would
have destroyed the target repo permanently.

**How**: Added `_ensure_is_template` (reads `is_template`, PATCHes to `true` if unset) called
right before `generate`. Changed force-replace to rename the target repo out of the way
(`{name}-mimeo-replaced-{timestamp}`) instead of deleting it; only deletes the renamed-old repo
after `generate` succeeds; renames it back on any `HostError` from `_ensure_is_template` or
`generate`. Also set `is_template: true` on `tepiton/mellowtimesphere.com` directly via `gh api`.
293 -> 297 tests (rename/rollback paths + `_ensure_is_template` unit tests); mypy and ruff clean.

**Files**: `mimeo/providers/host/github.py`, `tests/providers/host/test_github.py`, DEC-022

## Entry 37: Default template customization -- fix hardcoded "mimeo.lol" (2026-08-25)

**What**: `mimeo.lol` (the default template) is itself a live site, so its
`index.html` hardcodes "mimeo.lol" in `<title>` and letter-spaced
("m i m e o . l o l") in `<h1>`. Every site generated from it -- via `create`
or `template apply` -- shipped that literal text instead of its own domain.
Added `_customize_default_template` to rewrite both forms post-generation.

**Why**: Reported live: `template apply --template mimeo.lol
tantamount.rodeo` produced a page still reading "m i m e o . l o l". First
fix attempt swallowed a real error (`except HostError: pass`) and shipped
untested against the actual template content, so it silently did nothing.
Second attempt traced the live call path end-to-end and found the real
cause: `generate`-from-template returns before GitHub populates the file
tree, so the immediate `index.html` read 404s with "repository is empty" --
the same failure class as Entry 30's `_wait_for_repo` fix, but on the
contents API rather than repo metadata, and previously undetected because
nothing polled it.

**How**: `_customize_default_template` reads `index.html` (retrying up to
5x/2s on the empty-repo 404), substitutes `DEFAULT_TEMPLATE` and its
letter-spaced form for the real domain in memory, writes back only if
something changed. Raises on persistent failure instead of swallowing.
Scoped to `mimeo.lol` only -- `eleventy-*` templates are full site
generators where a blind string-replace would be unsafe; that's the
remaining open part of the carried-over "template parameterization" task.
Live-verified: ran `template apply` against `tepiton/tantamount.rodeo` for
real and confirmed the deployed `index.html` and commit history.

**Files**: `mimeo/providers/host/github.py`, `tests/providers/host/test_github.py`

## Entry 36: status also requires --all for fleet-wide (2026-07-06)

**What**: A bare `mimeo status` now refuses to run; fleet-wide sweeps
require explicit `--all`, matching sync.

**Why**: User ran the fleet sweep and gave up waiting — several API calls
per domain across 105 domains takes minutes. Unlike sync's guard (safety),
this one is about cost; recorded as such in DEC-021 Stage 3 resolutions.

**Files**: `mimeo/cli/status.py`, `tests/test_status.py`, commit d5b7723

## Entry 35: Stage 3 — mimeo sync, converge on desired state (2026-07-06)

**What**: Added `mimeo sync [DOMAINS... | --all]`: applies missing DNS
records and enables HTTPS enforcement when the certificate is ready, in one
pass, with `--dry-run` and `--reset-nameservers`.

**Why**: The remediation half of DEC-021's status/sync pair — replaces
running `dns repair` and `fix https` separately across the fleet.

**How**: Same union-of-inventories targeting as status, built on map_items.
Safety decisions (user-confirmed): fleet-wide requires explicit `--all`
(no-arg refuses, exit 2); acts on missing records only, never deletes
extras (the Porkbun wildcard parking CNAME survives); nameservers touched
only with `--reset-nameservers`; no propagation wait at fleet scale.
`dns repair` / `fix https` kept as targeted scalpels. Live-verified:
guard refuses correctly; `--dry-run` on two real domains reported both ok
(wildcard drift correctly triggers no action).

**Decisions**: DEC-021 (Stage 3 resolutions)

**Files**: `mimeo/cli/sync.py`, `mimeo/cli/__init__.py`, `tests/test_sync.py`

## Entry 34: Stage 2 — mimeo status, the cross-provider join (2026-07-06)

**What**: Added `mimeo status [DOMAINS...]` — one view joining the Porkbun
account against mimeo-managed GitHub repos: EXPIRES / NS / DNS drift / SITE
health per domain, `--problems` filter, text/json/csv.

**Why**: The two inventories (`list`, `registrar list`) never joined, so the
fleet questions (domains without sites, sites without domains, drift) had no
command. This is the diagnostic half of DEC-021's status/sync pair.

**How**: Built on Stage 1's `map_items`; shares one registrar, DNS provider,
and host across workers. No-arg mode targets the union of both inventories.
DNS column is "-" when no repo exists (no desired state to compare). Drift
and unhealthy sites are findings (exit 0); API errors are failures
(EXIT_PARTIAL). Live-verified: correctly surfaced the Porkbun wildcard
parking CNAME as drift, matching `dns check`.

**Decisions**: DEC-021 (Stage 2)

**Files**: `mimeo/cli/status.py`, `mimeo/cli/__init__.py`, `tests/test_status.py`

## Entry 33: Stage 1 — shared domain-operation engine (2026-07-06)

**What**: Built `map_items` / `render_results` / `exit_on_errors` in
`_processing.py` and migrated `registrar list`, `dns check`, `dns show`,
`fix https`, and `list` onto them. Removed four hand-rolled thread pools.

**Why**: Three of the four pools crashed the whole command on one bad
`future.result()` (the zero-results bug class); every command duplicated the
text/json/csv dispatch. DEC-021 Stage 1.

**How**: `map_items` returns results in input order and converts escaped
exceptions to error rows via an `on_error` callback. `render_results` keeps
text rendering as a per-command callback (layouts genuinely differ) but owns
json/csv. Exit codes unified: some-failed -> EXIT_PARTIAL, all-failed ->
category code (dns show partial changed from transient to EXIT_PARTIAL).
Command files shrank ~65 lines, engine added ~110 (net +51); the payoff is
structural. Follow-up added: fold `process_domains_concurrent` into
`map_items`. Live-verified against real Porkbun and GitHub APIs.

**Decisions**: DEC-021 (Stage 1)

**Files**: `mimeo/cli/_processing.py`, `mimeo/cli/{registrar,dns,fix,list_cmd}.py`,
`tests/test_processing.py`

## Entry 32: Phase 8 planned — consolidation to status/sync (2026-07-06)

**What**: Closed Phase 7 and planned Phase 8 after a whole-codebase design
review. Reframed mimeo as a fleet manager for domain-to-GitHub-Pages sites.

**Why**: The CLI grew by accretion — one verb per operational incident
(dns repair, fix https, template apply) — and the two inventories (`list`,
`registrar list`) never join, so fleet-level questions across 105 domains
have no command. Half the codebase is per-command copies of the same
fan-out/render plumbing, where the zero-results bug lived.

**How**: Four staged tasks in IMPLEMENTATION.md: (1) shared domain-operation
engine, (2) `mimeo status` cross-provider join, (3) `mimeo sync` convergence
with --dry-run, (4) gated E2E lane. Plus identity fix and carried-over
template parameterization. Full rationale and alternatives in DEC-021.

**Decisions**: DEC-021

**Files**: `docs/IMPLEMENTATION.md`, `docs/DECISIONS.md`, `docs/CONTEXT.md`

## Entry 44: Scoped template parameterization to domain self-reference; manifest design (2026-09-08)

**What**: Design-only session (no code changed). Built two Artifact pages
mapping the CLI's command/provider structure, then used the discussion to
correct course on the open "template parameterization" task and settle its
design shape.

**Why**: The command-map artifact revealed the atoms/composites/commands
breakdown was a map of the *implementation* (provider method boundaries),
not an independent decomposition of the *problem* — worth naming since it
looked more authoritative than it was. Revisiting what mimeo is *for* (per
DEC-021, a fleet manager, not a site generator) surfaced that the open
parameterization task had drifted toward general template authoring — the
same kind of work as Entry 43's mimeo-sites identity scrub, which is out of
mimeo's scope. The real, narrower requirement: a deployed site's boilerplate
should say its own domain, not the template's name.

**How**: Surveyed all 8 tepiton templates' self-reference storage (extending
Entry 42): hardcoded HTML (mimeo.lol, laptopistan.com), `metadata.js` `url:`
key (5 eleventy-* templates), YAML frontmatter `title:` (pandoc-simple).
Three incompatible formats ruled out a single token-replace convention.
Settled on a per-template manifest (`mimeo.template.json`) declaring
`{file, format, key/match, value}` substitutions across three format
handlers (`js-key`, `string-replace`, `yaml-frontmatter-key`), replacing
`_customize_default_template`'s mimeo.lol-only hardcoding. Full rationale
and rejected alternatives in DEC-024.

**Decisions**: DEC-024

**Files**: `docs/IMPLEMENTATION.md`, `docs/DECISIONS.md` (no source changes —
manifest schema and handlers not yet implemented)
