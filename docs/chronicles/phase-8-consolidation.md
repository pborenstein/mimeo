# Phase 8: Consolidation Chronicles

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

## Entry 36: status also requires --all for fleet-wide (2026-07-06)

**What**: A bare `mimeo status` now refuses to run; fleet-wide sweeps
require explicit `--all`, matching sync.

**Why**: User ran the fleet sweep and gave up waiting — several API calls
per domain across 105 domains takes minutes. Unlike sync's guard (safety),
this one is about cost; recorded as such in DEC-021 Stage 3 resolutions.

**Files**: `mimeo/cli/status.py`, `tests/test_status.py`, commit d5b7723

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

## Entry 45: Planned collapsing 9 CLI verbs to 5 (2026-09-08)

**What**: Continued the same session into command-surface redesign. Applied
one test across every command pair — "is this a different action, or the
same action with a flag" — starting from the user's own call that `create`
and `template apply` are the same operation (create is reset, forced).
Extended the same test to the rest of the surface and wrote a full,
self-contained implementation plan.

**Why**: DEC-021 (Stage 3) had already left this exact question open
("alias vs deprecate — decided during Stage 3") and only partially answered
it, keeping `dns repair`/`fix https` split from `sync` for stated reasons
(propagation-wait gap, auto-discovery gap). Re-examining whether those gaps
still justify a split, post the atoms/composites mapping from Entry 44,
found they're closable with flags, not separate verbs.

**How**: DEC-025 records the merge and, explicitly, that it supersedes
DEC-021 Stage 3's scalpel decision rather than being a fresh call —
important since DEC-021 made that split for a specific, checkable reason
that needed to be named, not silently overridden. Five-command target
surface: `create` (+ `--force`/`--yes`, absorbing `template apply`),
`status` (+ `--source github|porkbun|dns`, absorbing `list`/
`registrar list`/`dns show`/`dns check`), `sync` (+ `--wait`, absorbing
`dns repair`/`fix https`), `doctor` (unchanged), `template lint` (new,
gated on DEC-024 landing first). One open question flagged rather than
guessed past: whether `sync --all`'s existing HTTPS pass already subsumes
`fix https`'s auto-discovery mode, or a real gap remains — Stage 5C must
check the actual code before merging, not assume. Full sub-stage checklist
in IMPLEMENTATION.md Phase 8 Stage 5, written for a fresh session to
execute without re-deriving this reasoning.

**Decisions**: DEC-025 (supersedes DEC-021 Stage 3's dns-repair/fix-https
scalpel decision)

**Files**: `docs/IMPLEMENTATION.md` (Stage 5, full checklist),
`docs/DECISIONS.md`, `docs/CONTEXT.md` (no source changes)

## Entry 46: Implemented Stage 5A; found and fixed two live safety bugs
against real domains (2026-09-08)

**What**: New branch `stage-5a-create-absorbs-template-apply`. Implemented
Stage 5A per the IMPLEMENTATION.md checklist: `create` gained `--force`/
`--yes`, wired to the existing `deploy_site(force=...)` path; ported
`template apply`'s delete-and-recreate confirmation prompt, gated on
`--force`; deleted `mimeo/cli/template.py` and its registration; relocated
its two CLI-layer tests onto `create --force` (DEC-022's rollback-on-failure
coverage already lived at the provider layer and needed no move). All Stage
5A checkboxes now `[x]`.

While manually verifying the merged command against real domains (not just
mocks), found two live bugs neither the plan nor the existing test suite
had caught, both discovered by actually running `create` against domains
in GitHub/Porkbun rather than trusting green tests:

1. `mimeo create <domain>` for a domain not registered in this Porkbun
   account ran end-to-end anyway — created a public repo, configured
   Pages, wrote a CNAME — before any ownership check. `validate_domains`
   only checks string format; the only ownership-adjacent signal
   (`check_nameservers`) fires after the repo already exists, as a warning.
   Caught by the user directly ("I don't own that domain") after a session
   in which the model first misdiagnosed an unrelated repo as evidence of
   a bug (see below) before checking the actual one.
2. `mimeo create <domain>` on a domain with an *already-existing* repo
   (correctly left unchanged, no `--force`) still ran DNS configuration —
   `configure_dns` deletes and recreates every matching record
   unconditionally, so a plain re-run silently rewrote a live site's DNS.
   `deploy.repo_created` was available but unchecked before the DNS block.

**Why**: Both are severity-inverted relative to how `create` treated them:
ownership was a late warning instead of an early hard stop; DNS rewrite on
an unchanged repo was invisible instead of skipped. Neither was Stage 5A's
original scope, but both were exposed *by* Stage 5A's live testing and are
squarely "create must not have side effects it doesn't own" — the same
category the ownership fix belongs to. Separately, the DNS-propagation poll
(10x5s, ~50s) added in Phase 5/6 almost never observes real propagation and
changes nothing `create` does on either outcome — dead weight now that
`mimeo status` exists to report drift.

**How**: See DEC-026 for full rationale. Summary: `create` now calls the
already-existing (but previously unused by `create`) `PorkbunRegistrar
.domain_exists()` before touching GitHub at all, raising `RegistrarError`
(exit 5, no side effects) if the domain isn't in this account; checks
`deploy.repo_created` before running DNS config, skipping it entirely
(same as `--skip-dns`) when the repo was left unchanged; and drops the
`verify_dns` poll, pointing to `mimeo status` instead. A fourth, unrelated
fix landed in the same session: generated repos were publishing the
template's own `README.md` and `docs/` (authoring documentation, not site
content) as live site files — found while inspecting a real deployed repo's
contents during the branding investigation below. Added
`_strip_template_dev_files` (+`_delete_file`/`_delete_directory`) to
`GitHubHost`, best-effort, run right after every fresh template generation.

A branding report ("the page still says the template's name") during this
session turned out to be pure DNS/CDN propagation lag, not a code bug —
confirmed by `curl`ing the live site directly and finding it already
correct. Worth recording because the model's first response speculated a
historical-artifact explanation instead of checking the live page first;
the user's pushback on that speculation is why the ownership and DNS bugs
above got the scrutiny they did rather than being taken on faith from a
green test suite. Every fix in this entry was verified against real
domains/repos via `gh api`/`curl`, not just the mocked test suite.

**Decisions**: DEC-026

**Files**: `mimeo/cli/create.py`, `mimeo/providers/host/github.py`,
`mimeo/cli/__init__.py`, `mimeo/cli/sync.py` (stale doc reference),
`mimeo/cli/template.py` (deleted), `tests/test_cli.py`,
`tests/providers/host/test_github.py`, `docs/IMPLEMENTATION.md`,
`docs/DECISIONS.md`. Not yet committed.

## Entry 47: Implemented Stage 5B — `status --source` absorbs `list`,
`registrar list`, `dns show`, `dns check` (2026-09-08)

**What**: On the same `stage-5a-create-absorbs-template-apply` branch
(user's call: keep stacking sub-stages rather than PR-per-stage). Added
`--source {github,porkbun,dns}` to `status`; no `--source` keeps the
existing full-join behavior unchanged. `--source github`/`porkbun`
reproduce `list`/`registrar list` output exactly, including their
`--health`/`--with-template`/`--with-dns` flags. `--source dns` reproduces
`dns show` (raw records) alone, or `dns check` (drift) when combined with
the existing `--problems` flag — chosen over a new flag to keep the
surface smaller, per user's pick when asked. Deleted `list_cmd.py` and
`registrar.py` (nothing survived in the latter once `list` moved) and
`dns.py`'s `show`/`check` (kept `repair` for 5C). Relocated all four
commands' tests into three new `test_status.py` classes.

**Why**: Per DEC-025's Stage 5 plan — one output-shape gap was found as
anticipated (`list --show-template`'s TEMPLATE column had no `status`
equivalent), closed by adding `--show-template` to `status` itself rather
than keeping `list` alive, backed by the same `get_template_repository()`
call.

**How**: No provider-layer changes. 296 tests passing (up from 270),
ruff/mypy clean. Verification is mock-based only — no Porkbun/GitHub
credentials configured on this machine, so unlike 5A's DEC-026 bugs (only
found by live testing), this stage has not yet been run against a real
account.

**Decisions**: none new; implements DEC-025's Stage 5B as planned.

**Files**: `mimeo/cli/status.py` (rewritten), `mimeo/cli/dns.py`,
`mimeo/cli/__init__.py`, `mimeo/cli/list_cmd.py` (deleted),
`mimeo/cli/registrar.py` (deleted), `tests/test_cli.py`,
`tests/test_status.py`, `docs/IMPLEMENTATION.md`, `docs/CONTEXT.md`.
Not yet committed.

## Entry 48: Implemented Stage 5C; live testing found two more bugs
(sync's drift reporting, template dev-file strip race) (2026-09-09)

**What**: Implemented Stage 5C — `sync` absorbs `dns repair`/`fix https`.
Resolved DEC-025's open question by reading source before writing any
code: `sync --all`'s existing HTTPS-fixable check (`get_pages_health()` +
`health_status() == "fixable"`) already duplicated `fix https`'s
auto-discovery exactly, so no new flag was needed. Deleted
`mimeo/cli/dns.py` and `mimeo/cli/fix.py` outright. Deliberately did not
add the `--wait` flag the original plan called for — dropped `dns
repair`'s propagation poll entirely instead, same reasoning DEC-026 used
for `create`. No test relocation needed: `tests/test_sync.py` already
covered every case the deleted test classes did. (Commit `b96d493`.)

Live-verifying 5C against `002373.xyz` (real extra-CNAME drift left over
from Entry 46/47) surfaced a genuine bug, not just a confirmation:
`sync --dry-run` reported `ok` for a domain `status` correctly reports as
`DNS: drift`. `_sync_domain` only ever inspected `drift["missing"]`,
never `drift["status"]`/`drift["extra"]` — an extra-only result fell
through to "ok" silently. User asked "why does status think this is
drift but sync doesn't" then "can we make status and sync use the same
terms" — fixed by having `sync` surface the same `dns_status`/`extra`
fields and literal `"drift"` term `status` already uses, rather than
inventing sync-specific wording. First fix included a "-- see mimeo
status" pointer in the message; user correctly called it useless (you're
already looking at the fact status would report) and it was dropped in
favor of stating *why* sync leaves it alone. (Commits `585e489`,
`053ff52`.)

Live-testing `create --template laptopistan.com` (a non-default template,
first real test of Entry 46's `_strip_template_dev_files` outside
mimeo.lol) found the generated repo still had the template's `README.md`.
Root cause: `_delete_file`/`_delete_directory` treated any `HostError`
from the existence-check read as "file doesn't exist" — including a
fresh repo's transient "repository is empty" 404 before
generate-from-template finishes populating the tree. That's the identical
race `_customize_default_template` already retries around (5x/2s); the
strip helpers had no equivalent, so a real file could silently survive.

**Why**: Both bugs were invisible to the mocked test suite because mocks
don't model the specific failure mode (an HTTP 404 that's actually "not
ready yet" vs. "genuinely absent"; a `status` field with three states
collapsed into a boolean check) — same lesson as Entry 46's DEC-026 bugs.
Live-testing against real domains/repos keeps finding real bugs; mocks
alone would not have caught either.

**How**: `sync` now sets `dns_status`/`extra` on its result row and
reports literal `"drift"` instead of falling through to `"ok"`; no change
to what `sync` acts on (still never deletes extras). `_delete_file`/
`_delete_directory` now retry their existence-check call up to 5x/2s
before concluding a path is genuinely absent, matching
`_customize_default_template`'s pattern. Manually deleted the stray
`README.md` from the live `tepiton/002372.xyz` repo. 294 tests passing,
mypy/ruff clean throughout.

**Decisions**: DEC-025 updated with the resolved open question and both
bugs' root causes.

**Files**: `mimeo/cli/dns.py`/`mimeo/cli/fix.py` (deleted),
`mimeo/cli/__init__.py`, `mimeo/cli/create.py`, `mimeo/cli/sync.py`,
`mimeo/providers/host/github.py`, `tests/test_cli.py`,
`tests/test_sync.py`, `tests/providers/host/test_github.py`,
`README.md`, `docs/TROUBLESHOOTING.md`, `docs/DECISIONS.md`,
`docs/IMPLEMENTATION.md`, `docs/CONTEXT.md`. Commits `b96d493`,
`585e489`, `053ff52`, `497f43f`.

## Entry 49: Stage 5D — registration cleanup, full validation pass, doc rewrite (2026-09-09)

**What**: Closed out Stage 5D of DEC-025's verb collapse. Verified `mimeo/cli/__init__.py` already registers exactly the 4 target commands (no change needed — 5A/5B/5C left it correct). Ran the full test/mypy/ruff pass clean: 294 tests, mypy clean (19 files), ruff clean. Rewrote README.md's command reference (the `mimeo list`/`mimeo registrar list` sections became `mimeo status --source github`/`--source porkbun`, added a missing `--source dns` section) and did a structural rewrite of docs/ARCHITECTURE.md — replaced the five separate per-command workflow diagrams (list, dns check, dns repair, template apply, fix https) with Create/Status/Sync workflow sections matching current behavior, including --source, --problems, --with-dns, --show-template, --reset-nameservers, the extra-only-drift fix, and the dropped propagation poll.

**Why**: 5A/5B/5C left docs pointing at deleted commands and files (`dns.py`, `fix.py`, `mimeo list --health`) — 5D was scoped specifically to close that gap before the branch merges.

**How**: Read every current CLI module (create.py, status.py, sync.py, doctor.py) directly rather than trusting the old docs, to make sure the rewrite matched actual flag behavior. Doc sweep also found docs/LIST_COMMAND.md fully documenting the deleted `list` command and three stale `mimeo list --health`/`mimeo dns repair` refs in TROUBLESHOOTING.md, none of which were in the original 5D checklist — confirmed with user before deleting LIST_COMMAND.md (its content is superseded by `status --source github`) rather than silently expanding scope. Swept docs/DECISIONS.md too; left its historical entries alone since a decision log correctly describes the surface as it existed at the time.

**Decisions**: None new — this was cleanup, no architectural change.

**Files**: `README.md`, `docs/ARCHITECTURE.md`, `docs/TROUBLESHOOTING.md`, `docs/IMPLEMENTATION.md`, `docs/CONTEXT.md`. Deleted `docs/LIST_COMMAND.md`.

## Entry 50: Two QoL fixes -- create prints full help with no args, status points at sync (2026-09-09)

**What**: Implemented the two QoL items queued after Stage 5D. `mimeo create` with no domain arguments now prints full `--help` output (exit 2) instead of Click's terse `Error: Missing argument 'DOMAINS...'.` -- dropped `required=True` from the `domains` argument, added `@click.pass_context`, and check emptiness explicitly at the top of the command body via `ctx.get_help()`. `mimeo status`'s text summary line now appends `(N fixable with: mimeo sync)` when the fleet has problems sync can actually converge.

**Why**: Click's built-in missing-argument error is unhelpful for a command with this many flags; the fix keeps the same exit code but gives the user something actionable. The status summary previously just counted problems with no pointer to the fix, echoing the same gap Entry 48 found in sync's drift message (a bare count with no next step).

**How**: Added `_fixable_by_sync()` in status.py, deliberately narrower than `_has_problem()` -- it returns true only for NS mismatch, DNS drift/missing, and HTTPS-fixable cert state, not for "no repo"/"not registered"/other site-health states/API errors, since sync has nothing to do for those. Live-verified both fixes: `mimeo create` (no args) against the real CLI, and `mimeo status --all` against the real 113-domain fleet (86 issues, 42 correctly counted as sync-fixable). Updated `test_create_requires_domain` (was asserting the old undesirable behavior) and added two new status tests for the sync-hint present/absent cases. 296 tests passing, mypy/ruff clean.

**Decisions**: None new -- both were pre-scoped backlog items from CONTEXT.md, no new tradeoffs surfaced.

**Files**: `mimeo/cli/create.py`, `mimeo/cli/status.py`, `tests/test_cli.py`, `tests/test_status.py`, `docs/CONTEXT.md`.

## Entry 51: Fixed create's mangled Examples block; merged Stage 5 to main (2026-09-09)

**What**: Cleaned up `create`'s `--help` docstring -- the Examples block was missing Click's `\b` no-rewrap marker, so all seven example lines were getting mashed into one run-on paragraph (surfaced by the previous session's new no-args-prints-help behavior, which made the mangled text visible in a new place). Also dropped an internal DEC-024 citation from the user-facing docstring -- decision-doc references have no place in --help text. Then merged `stage-5a-create-absorbs-template-apply` into `main` as an explicit merge commit (`--no-ff`, not a fast-forward) per user request, completing all of Stage 5 (5A-5D).

**Why**: User caught the formatting bug by inspection of the rendered help output. The merge needed `--no-ff` specifically because the branch was a clean fast-forward of main (0 behind) -- a plain `git merge` would have fast-forwarded silently with no merge commit, which the user explicitly did not want.

**How**: Added the missing `\b` marker (same pattern already used correctly in status.py and sync.py). Verified `--help` output line-by-line after the fix. Confirmed the DEC-024 reference existed nowhere else (README, tests). Full validation pass (296 tests, mypy, ruff) re-run on `main` post-merge to confirm the merge itself introduced no regressions.

**Decisions**: DEC-025 status updated to Complete and merged (`56d75bd`); Stage 5E remains open, blocked on DEC-024.

**Files**: `mimeo/cli/create.py`. Merge commit `56d75bd` on `main` (12 commits: d4debf2..be515b0).

## Entry 52: Split 'template lint' out of Stage 5 into its own Stage 6 (2026-09-09)

**What**: Renamed what IMPLEMENTATION.md called "Stage 5E" (`template lint TEMPLATE`) to its own top-level Stage 6. Updated the Stage 5 intro line, DEC-025's status line, and CONTEXT.md accordingly.

**Why**: User pointed out `template lint` is a different kind of work than Stages 5A-5D -- those collapsed nine existing verbs into four by merging shared write/read paths (DEC-025's actual scope); `template lint` is new functionality that validates DEC-024's manifest schema, unrelated to the verb-collapse. Filing it as "5E" implied it was part of the same effort when it isn't.

**How**: Pure renumbering, no code change. Stage 5's own checklist (5A-5D) is now marked `[x]` complete as a whole, since nothing in Stage 6 blocks calling Stage 5 done.

**Decisions**: DEC-025's status line updated to note `template lint` moved to Stage 6.

**Files**: `docs/IMPLEMENTATION.md`, `docs/DECISIONS.md`, `docs/CONTEXT.md`.

## Entry 53: Code review fix pass — BUG 1/2/3/5 and dead-code sweep (2026-09-08)

**What**: Worked through GLM 5.3's `docs/CODE_REVIEW.md` (dated 2026-09-08,
pinned to `0c3c6ba`). Fixed the four small user-facing bugs it flagged as
independent of any design decision (BUG 1, 2, 3, 5), then most of its
dead-code table: removed `verify_dns` entirely (ABC slot, Porkbun impl, and
all its test coverage), collapsed `HTTPClient`'s four HTTP verbs onto one
`_request` helper and dropped its two dead constructor params, and fixed a
stale comment in `config.py`.

**Why**: The review's own priority order put these first — "small, all
user-facing, none need design decisions" — and pre-1.0 was called out as the
cheap time to cut dead surface before it taxes a future provider
implementation (`verify_dns`'s ABC slot was the one flagged as taxing the
future most).

**How**: Verified each bug against the actual code and, for BUG 1, against
this repo's own Porkbun test fixtures (`"Domain not found"` is the real
error-message text Porkbun returns, confirmed via `tests/providers/registrar/
test_porkbun.py`'s mocked responses across other endpoints — no live-API
call was made). Checked in with the user before touching `default_registrar`/
`default_host` (D2) and the `HTTPClient.get/put/delete` scope, since both
carried real design-decision or test-surface weight beyond mechanical
cleanup; D2 was deliberately left, `HTTPClient` was done but kept its public
`get`/`put`/`delete` methods (real tests exercise them, not just dead
surface). Full suite re-run after: 289 passed (296 - 7, all `verify_dns`-only
tests), mypy clean, ruff unchanged from baseline (5 pre-existing errors, none
in touched files). `docs/CODE_REVIEW.md` updated in place with
FIXED/REMOVED/left-open markers per finding, instead of a separate tracking
checklist.

**Decisions**: None new. No DEC entry — this was bug fixes and dead-code
removal, not an architectural choice.

**Files**: `mimeo/providers/registrar/porkbun.py`, `mimeo/providers/base.py`,
`mimeo/cli/create.py`, `mimeo/cli/status.py`, `mimeo/config.py`,
`mimeo/utils/http.py`, `tests/providers/registrar/test_porkbun.py`,
`tests/test_cli.py`, `tests/test_providers_base.py`,
`tests/utils/test_http.py`, `README.md`, `docs/TROUBLESHOOTING.md`,
`docs/CODE_REVIEW.md`.

## Entry 54: Subdomain sites design doc (2026-09-09)

**What**: Wrote `docs/SUBDOMAINS.md`, a proposed design for hosting sites on subdomains (`mimeo create --template eleventy-service service.example.com`). No code changed.

**Why**: Every "domain" string currently plays three roles at once — site hostname, DNS zone, and status/sync join key — which coincide only for apex domains. Subdomains split them and make zones one-to-many with sites; the doc's six required changes follow from that split (identity split, zone resolution as ownership check, per-site DNS desired state, drift scoping to managed names, type-conflict replacement, fleet joins). User asked for the write-up structured as "what needs to happen," with implementation detail quarantined in an appendix table.

**How**: Traced live behavior first: `validate_domains` already accepts subdomains syntactically, and `create` refuses cleanly at the ownership check (Porkbun's API is zone-scoped) before creating anything — correcting an earlier in-chat claim that repo/Pages creation would happen first. Indexed the doc in `docs/README.md`; added a Phase 8 task entry pointing at it. Four open decisions (repo naming, zone-resolution source, ignore_domains semantics, apex behavior freeze) deliberately left unratified — no DEC-xxx numbers assigned yet.

**Decisions**: None ratified; recommendations recorded in SUBDOMAINS.md's Open Decisions table.

**Files**: `docs/SUBDOMAINS.md` (new), `docs/README.md`, `docs/IMPLEMENTATION.md`, `docs/CONTEXT.md`.

## Entry 55: Repaired chronicle numbering and ordering (2026-09-09)

**What**: Sorted chronicle entries into ascending order within the four affected phase files (phase-5, phase-6, phase-7, phase-8) and resolved a duplicate number: the subdomain-design entry (added earlier tonight as Entry 53) became Entry 54, since the code-review pass legitimately owns 53 by commit order (`2e8580b`). Pure reordering — 413 lines moved, none added or removed. All other entry numbers preserved: IMPLEMENTATION.md and DECISIONS.md cross-reference entries by number.

**Why**: User noticed the numbering was "all messed up." Root cause of the duplicate: the code-review Entry 53 sat physically near the top of phase-8 (with 32-43 fully reversed below it), so a tail-of-file scan for the highest number only saw 52 — a misfiled entry poisoned the append recipe.

**How**: Per-file Python sort keyed on entry number, preamble preserved, duplicate resolved by title match. Hardened `~/.zcode/skills/session-wrapup/SKILL.md` (outside this repo) to compute the next number as the max across all matches via an explicit grep/sort pipeline plus a `uniq -d` duplicate guard. Noted but deliberately left alone: entries 49-52 are dated 2026-09-09 while their commits landed the evening of 09-08 — possibly written the morning after; dates unchanged pending user intent.

**Decisions**: None.

**Files**: `docs/chronicles/phase-{5,6,7,8}-*.md` (repair commit `29192be`); `~/.zcode/skills/session-wrapup/SKILL.md` (not a repo file).

## Entry 56: Implemented DEC-024 template substitution manifest (2026-09-09)

**What**: Implemented the DEC-024 manifest end to end: new `mimeo/providers/host/template_manifest.py` (strict `parse_manifest()`, `apply_substitutions()`, three format handlers), `GitHubHost` wiring (fetch-and-validate before any mutation, dev-path strip via manifest `dev_paths` or defaults, always-strip the manifest itself), and the deletion of `_customize_default_template` + `TEMPLATE_DEV_PATHS` -- no template-specific knowledge left in mimeo source. 333 tests passing (was 296), mypy clean, ruff at baseline.

**Why**: DEC-024's schema was ratified this session after surveying the real template files (`~/projects/mimeo-sites/TEMPLATES`, now 10 templates). The survey settled three open calls (DEC-024 addendum): `js-key` kept with a loosened unique-leaf resolution rule (a match-only alternative lost on evidence -- three orobia.* domains, demo brands, and `author@example.com` all coexist in the config files); mimeo.lol's letter-spaced `<h1>` fixed template-side with CSS (`17d308f`, user's commit); manifest carries `version`.

**How**: Handlers are pure functions, unit-tested against near-verbatim copies of the real files (tech-blog `metadata.js` with comments/nesting/`process.env`/placeholder email, pamphlet's `addPlugin` options object, pandoc-simple frontmatter). js-key scans line-wise with quote/comment masking and brace-depth tracking; ambiguity, non-string leaves, unbalanced braces, and unterminated strings all fail loud. Default strip list gained `CLAUDE.md` per user call. Invalid manifests abort before the repo existence check (test-proven). All verification mock-based -- live `create` run still owed once a template ships a manifest.

**Decisions**: DEC-024 (addendum + status flipped to implemented)

**Files**: `mimeo/providers/host/template_manifest.py` (new), `mimeo/providers/host/github.py`, `tests/providers/host/test_template_manifest.py` (new), `tests/providers/host/test_github.py`, `docs/{DECISIONS,IMPLEMENTATION,ARCHITECTURE,CODE_REVIEW}.md` (commit `13583f7`)

## Entry 57: Template manifests rolled out to all ten templates; DEC-024 live-verified (2026-09-10)

**What**: Wrote and validated `mimeo.template.json` for all ten tepiton templates (three string-replace/frontmatter, seven eleventy js-key), cleaned the eleventy family's dead identity data, committed and pushed all ten template repos plus the mimeo doc fix. User live-verified the whole path: `mimeo create bluegazebo.dev --template mimeo.lol` and `mimeo create tepiton.com --force` both landed the substitution correctly.

**Why**: The mimeo-side DEC-024 work (Entry 56) needed real manifests to be live-testable. A full survey of the eleventy family before writing them found the templates wrong in ways that argued for fixing rather than papering over: `author.url`/`author.email` read by no layout (only leaked into Atom feeds via whole-object pass-through), `feed.id` a leftover from the old feed.njk shape, two stale `notreally.config.js` copies, pamphlet's feed base hardcoded instead of derived, and three different real `orobia.*` domains plus demo brands as placeholders.

**How**: Cleanup first (trim dead keys, delete stale files, pamphlet `base: metadata.url`, normalize placeholders), which collapsed every eleventy manifest to one `js-key url` entry — plus an `about.md` string-replace for the three literary templates' "served from" line. Each manifest validated with mimeo's real parser against the real files; end-to-end proof built tech-blog with a substituted `url` and confirmed propagation to canonical/og/feed/sitemap. Two incident notes: an E2E `git checkout` briefly clobbered tech-blog's uncommitted trims (caught in the pre-commit survey, re-applied, rebuilt); string-replace's re-application semantics clarified in the DEC-024 addendum after validation exposed the subtlety (mimeo `5b19189`). pandoc-simple rebased onto a moved remote and its manifest re-validated against the changed frontmatter.

**Decisions**: DEC-024 (status flipped to Complete)

**Files**: mimeo-sites TEMPLATES/* (all ten repos, committed+pushed 2026-09-09/10); `docs/{DECISIONS,IMPLEMENTATION}.md` (this commit)

## Entry 58: Stage 6 (`template lint`) dropped before any work started (2026-09-10)

**What**: Dropped Stage 6 (`template lint TEMPLATE`). Docs-only session — no code written. Also a session pickup and a walkthrough of the pandoc-simple frontmatter drift incident that had been lint's motivating example.

**Why**: Walking through the actual incident showed the juice isn't worth the squeeze. DEC-024's deploy-time validation already aborts loudly on a bad manifest and names the failing entry before any repository is created, so lint would only buy *earlier* discovery of template/manifest drift. The fleet is ten templates with one maintainer, and the one drift incident to date (pandoc-simple's remote-side frontmatter cleanup, Entry 57) was caught by routine re-validation during the manifest rollout anyway.

**How**: Marked Stage 6 dropped in IMPLEMENTATION.md with the full rationale and a revisit condition (templates gaining outside contributors, or fleet growth; the read-only/per-entry-report design is recoverable from git history). Corrected DEC-025's two lint references (status note and collapse-list item 5), which still described lint as pending. CONTEXT.md's task list and Next Session repointed at the error-semantics refactor (CODE_REVIEW.md rec #2) and the SUBDOMAINS.md decisions.

**Decisions**: none new — a stage cancellation recorded in IMPLEMENTATION.md; DEC-025 text corrected (no semantic change)

**Files**: `docs/{CONTEXT,IMPLEMENTATION,DECISIONS}.md` (this commit)

## Entry 59: Branding centralized in the two eleventy landing templates; email parameterized (2026-09-11)

**What**: Docs-only for mimeo — all code work landed in mimeo-sites. eleventy-product and eleventy-service centralized branding in `content/_data/metadata.js` (name hoisted to a `const` so `description` follows it; `email`; a `brand` block of `[dark, light]` accent pairs), and their manifests gained a second substitution: `email` → `hello@{domain}`. Demo prose now follows the brand — .md bodies interpolate `{{ metadata.title }}`, frontmatter data is neutralized.

**Why**: User survey found branding "all over the place": demo brand woven through prose, hardcoded `hello@brand.example.com` addresses, accent hex duplicated between `css/index.css` and `generate-icons.mjs` — made concrete by instance `tepiton/002370.xyz`, whose edited metadata still left "Harborlight" on its About page. Design followed DEC-024's split: the generated site becomes rebrandable from one file; mimeo extends only the mechanical domain self-reference (email — DEC-024 addendum).

**How**: `base.njk` re-emits accent/link tokens from the `brand` block using index.css's exact selectors, later in source order (wins at equal specificity in all four theme contexts); contact falls back to `metadata.email` — service's section schema still fails the build if email is set nowhere, product's page cards gained `useSiteEmail: true`; `generate-icons.mjs` imports metadata for its accent (regenerated binaries byte-identical). Both manifests re-validated through mimeo's real parser, including after metadata.js gained a backtick template literal. Prose interpolation works because `markdownTemplateEngine: "njk"`; frontmatter can't interpolate, so those strings were neutralized (also killed a cross-template palette bug: service shipped product's blue `#a7c4ff` link-hover). Both live-verified on tepiton.github.io. 002370.xyz predates the prose fix: hand-edit its about.md or `--force` + re-apply metadata.

**Decisions**: DEC-024 (addendum: `email` is in-scope self-reference, same category as `url`)

**Files**: mimeo-sites TEMPLATES/eleventy-service (`fd7a898`, `37efa18`), TEMPLATES/eleventy-product (`38e9f1a`, `e469461`); this repo docs only (this commit)

## Entry 60: Template package.json identity fixed in the literary three (2026-09-11)

**What**: chapbook/folio/pamphlet `package.json` now tell the truth: names = repo names (were upstream-starter names), folio's inherited `9.0.0` → `1.0.0`, folio's placeholder `author`/`repository`/`funding`/`bugs`/`homepage` (`your-org` URLs, `youremailaddress@example.com`) deleted, pamphlet's empty `author` dropped. Lockfiles kept in sync — they mirror the root package name, and a mismatch can fail `npm ci` on the Pages deploy. Verified with the deploy steps themselves: `npm ci` + `npm run build` locally, green Actions on all three. (chapbook `223aa42`, folio `aad334b`, pamphlet `abc24ab`.)

**Why**: Survey of all seven eleventy templates found the four newer ones already clean and the literary three never scrubbed of upstream-starter identity. Since `mimeo create` ships the template's package.json to the generated site, the placeholder fields landed in site repos — the same wrong-self-reference class as the Harborlight prose (Entry 59), at near-zero visibility.

**How**: Design first: package.json identity fields are inert in a generated site (Pages runs `npm ci` + build, reading scripts/deps/engines; nothing displays name/repository/author), so the fix is consistency-with-the-template and *nothing for the site to do*. Stopping rule against template-parameterization creep, worth keeping: parameterize only what the site's build or its visitors consume — `url` and `email` pass that test, package identity fails it. User scoped the fix minimal (no description rewrites, no `private: true`). One incident note: rewriting the lock via JSON re-serialization churned the whole file; redone surgically as string replacement of exactly the name/version lines.

**Decisions**: none new — design stance recorded here: template package.json ships as-is, sites inherit it unchanged

**Files**: mimeo-sites TEMPLATES/eleventy-{chapbook,folio,pamphlet}/package.json + package-lock.json (commits above); this repo docs only (this commit)

## Entry 61: Error-path QoL -- structured gh status codes, honest output (2026-09-12)

**What**: Three-round pass on mimeo's error/output UX, all in mimeo code. (1) Output cleanup: each failure prints once (inline or recap, plus a one-line stderr trailer "N of M domains failed"), the `====SUMMARY====` banner and the false "Successfully created: 0/1 domain(s)" headline are gone, sigils ok/xx/!! became check/warn/cross glyphs, and the redundant "GitHub CLI command failed:" prefix dropped from gh errors. (2) CODE_REVIEW rec #2 plus BUG 4 and BUG 7: `HostError` carries `status_code` parsed from gh's "(HTTP N)" stderr in exactly one place; rename-422, manifest-404, Pages probe, and `get_pages_health` branch on codes; retry and `_categorize_error` are code-first with keyword fallback only when no code; unexpected exceptions exit 1/"error" instead of 5/"provider"; `get_pages_health` maps only genuine 404 to "no Pages", other failures propagate as "couldn't check". (3) create recap honesty and parallel feedback: the recap counts only actual creations, already-existed domains get warn blocks with --force guidance (visible in multi-domain runs where step logs are suppressed), DNS skip reasons render distinctly, and parallel runs print "Creating X..." plus a one-line outcome per domain instead of going silent after the --force confirm.

**Why**: Two live incidents drove it. `gh: Invalid cname (HTTP 400)` printed three times in three formats under a banner claiming "Successfully created: 0/1", while exiting 5 told automation it was transient. Then `create clarkegeagan.com clarkegeagan.org` reported "Created 2/2 domains" for two repos that already existed -- the recap equated "no error" with "created" -- and `create --force` on the same pair sat silent after the y confirm, indistinguishable from a hang.

**How**: User-driven QoL session with design sign-off (glyph sigils and the one-line stderr trailer chosen from mockups; BUG 7 folded into rec #2's scope). The exit-code contract change is deliberate: only confirmed-transient exits 5, definitive provider failures exit 1. `enable_https_enforcement`'s "certificate does not exist" check stays message-based on purpose (it distinguishes within a status code). The already-existed no-op keeps exit 0 -- converged-state semantics, flagged to the user, who accepted honest text over a nonzero code. One keyword-match site beyond the review's three was found and converted: the template-manifest 404 check.

**Decisions**: DEC-027 (structured error semantics + exit-code taxonomy), DEC-028 (create outcome reporting: created / already-existed / failed)

**Files**: mimeo/exceptions.py, mimeo/cli/{create,_processing}.py, mimeo/providers/host/github.py, mimeo/utils/retry.py + tests (d9a6020, suite 354 green); docs updates in this commit

## Entry 62: laptopistan system dark/light; tepiton.com template catalog (2026-09-13)

**What**: Two template-side items, no mimeo code. (1) laptopistan now follows the OS color scheme with no toggle: the five color literals became CSS custom properties on `:root` with one `prefers-color-scheme: dark` override, plus `color-scheme: light dark`. Dark is the design inverted (#111/#eee, #9a9a9a dim); light is the old palette unchanged; the #ec3013 selection accent is shared by both. Zero JS, no flash of wrong theme. Verified in a real browser both ways (system-driven dark branch confirmed via computed styles, light previewed by applying the `:root` defaults). (2) tepiton.github.io (the org Pages site at tepiton.com, pandoc-built) gained a template catalog: a ten-template table -- name linked to repo, live example, description fetched verbatim from each GitHub repo -- plus a pandoc build line in its pages.yml. The user then folded the list into index.md and iterated on styling; deployed and green.

**Why**: User asked for system-following theming with no toggle, then for a template list at the org site with GitHub-sourced descriptions. Facts surfaced while building it: all ten templates have Pages enabled, project pages redirect under the org's custom domain (tepiton.com/\<repo\>), and the mimeo.lol template's demo serves at mimeo.lol itself.

**How**: CSS variables + one media query; catalog links verified against the Pages API before writing. One known-stale doc left unfixed: TEMPLATES/CLAUDE.md says the mimeo.lol template's repo is tepiton/mimeo.lol, but the repo is actually `tepiton/mimeo`.

**Decisions**: none new -- design stance recorded here: no toggle, the OS setting is the single source of truth for laptopistan's theme.

**Files**: TEMPLATES/laptopistan/index.html (4233437, user-committed); tepiton.github.io (list.md superseded into index.md, user commits through the 09-14 deploys); this repo docs only (this commit)

## Entry 63: configurable template org/default template; README accuracy pass (2026-09-21)

**What**: `github.template_org` (env `MIMEO_GITHUB_TEMPLATE_ORG`, default tepiton) and `defaults.template` (env `MIMEO_DEFAULT_TEMPLATE`, default mimeo) are config settings now. `GitHubHost` takes `template_org` independent of `default_org` — validate, generate, and manifest calls all target it — and `create --template` falls back to `defaults.template` when omitted. `DEFAULT_TEMPLATE` renamed to "mimeo" (the tepiton repo was renamed from mimeo.lol). Same session: a README accuracy pass (uv run in Quick Start, `create` documenting --template/--force/--yes/--skip-dns, stale test count), `uv.lock` committed so `uv sync --frozen` works on fresh clones, and both the live config and config.toml.example rewritten clean with the destination-org vs template-org distinction explicit and adjacent.

**Why**: Template source and destination were both hardcoded to tepiton, so they could never differ; the default template named a repo that no longer exists. Also verified this session: the repo is clean to go public (no token-shaped strings anywhere in git history; config lives outside the repo; \*.nogit\* files blocked by the user's global gitignore) — public-as-visible, not advertised for use.

**How**: Config imports the two fallback constants from github.py (no cycle: nothing under providers imports config). Click's `--template` default is None, resolved after config load so the config value can be the effective default. 361 tests passing (+8: config parsing/env/type, create template-from-config, custom-org generate URL), ruff/mypy clean.

**Decisions**: DEC-029

**Files**: mimeo/config.py, mimeo/providers/host/github.py, mimeo/cli/create.py, README.md, config.toml.example, docs/{ARCHITECTURE,DECISIONS}.md — code at 24b3513; docs updates in this commit

## Entry 64: BUG 6 + D2 close-out; version 1.1.0 (2026-09-21)

**What**: Three items. (1) BUG 6: the schema_version notices now print to stderr (click.secho, yellow) instead of warnings.warn classes Python hides outside __main__ -- the "add schema_version = 1" nudge reached an audience of zero before; both the missing-version and future-version notices converted, tests assert on captured stderr. (2) D2 resolved by removal (DEC-030): default_registrar/default_host dropped from Config, example config, and tests -- the fields implied a provider factory that never existed, and with one registrar and one host a factory is a dict with one entry. Stale [defaults] registrar/host keys in existing configs are silently ignored. (3) Version bumped 0.1.0 -> 1.1.0 (pyproject, __version__, uv.lock); user's call to skip 1.0.

**Why**: BUG 6 was the last open code-review bug (minutes of work); D2 was sharpened by DEC-029 adding config fields that do real work next to two that did nothing; the version bump marks maturity after the DEC-029/030 config work.

**How**: _notice() helper in config.py wraps click.secho(err=True); config.py now imports click (already a hard dependency). CODE_REVIEW.md dispositions updated (BUG 6 FIXED, D2 RESOLVED, recommendations 4/6 struck); rec #6 now reduces to Pages IPs from api.github.com/meta + D1. 360 tests (-1: the now-empty defaults test), ruff/mypy clean.

**Decisions**: DEC-030

**Files**: mimeo/config.py, tests/{test_config,test_cli}.py, config.toml.example, docs/{CODE_REVIEW,DECISIONS,README}.md (291f945); pyproject.toml, mimeo/__init__.py, uv.lock (c773a84); live config edited outside the repo

## Entry 65: global --template-org/--deploy-org CLI flags (2026-09-21)

**What**: `mimeo --template-org ORG --deploy-org ORG` -- both orgs overridable per invocation, for every command. Precedence: CLI flags > MIMEO_* env vars > config file. Extends DEC-029's config settings to the command line.

**Why**: The orgs were config-file/env-only; trying a different template org or deploying to another destination required editing config. User asked for command-line specification.

**How**: Main group records the flags via set_cli_overrides (mirrors the set_log_format module-state pattern); apply_cli_overrides mutates the loaded Config. The application point is the shared load_config wrapper in _processing.py -- all seven create/status/sync load sites funnel through it, so one wiring point covers everything (GitHubHost construction, repo URLs, template validation). doctor exempt: it validates the config file itself. Autouse test fixture resets flag state between tests (module state would otherwise leak into direct-invoke tests); one e2e test goes through the main group and asserts GitHubHost(default_org/template_org) get the overrides. 361 tests, ruff/mypy clean.

**Decisions**: none new (extends DEC-029's precedence chain)

**Files**: mimeo/cli/{__init__,_processing}.py, tests/test_cli.py, README.md, config.toml.example (e786760); docs updates in this commit

## Entry 66: Track B closed as empirically served (2026-09-22)

**What**: Stage 4 (the gated E2E integration test lane hitting real Porkbun/GitHub APIs) closed without being built. Docs only, no code.

**Why**: The lane existed because live-API surprises are the mocked suite's blind spot -- and every such incident to date was caught by the real usage the lane meant to institutionalize: DEC-022's repo deletion (rollback designed after), DEC-026's ownership bugs (found by live runs), the Stage 5C extra-drift bug (live run against 002373.xyz), plus the rename-307 redirect, generate-vs-file-tree race, and stale-pages-artifact 422 quirks. A single-operator tool exercised live every session already has that regression coverage; what it lacks (repeatable-on-demand runs, destructive-path safety on a sacrificial account) doesn't justify a test account/org. User's call, matching the Stage 6 precedent (dropped with design preserved).

**How**: IMPLEMENTATION.md Stage 4 marked closed-by-empiricism with the incident list and hedge; CODE_REVIEW.md recommendation 5 and the blind-spot paragraph struck accordingly. Hedge recorded for dormancy: a scripts/e2e_smoke.sh against a junk domain, unrun by default. CONTEXT board reduces to the rec #6 long-termers; no blockers remain.

**Decisions**: none new (closure, not a design change)

**Files**: docs/{IMPLEMENTATION,CODE_REVIEW,CONTEXT}.md (this commit)

## Entry 67: README restructured per documentation principles; org flags documented (2026-09-22)

**What**: README overhaul, docs only. Global options is now a table documenting `--template-org`/`--deploy-org` (the config key and default each overrides) with the org model in prose -- templates and sites live in different orgs and need not match. Every command's commented example blocks became Task|Command tables; the two duplicate `### status` sections merged into one with `#### --source github/porkbun/dns` subsections; bold pseudo-heading lead-ins became natural prose; the annotated project tree trimmed to directory level; Validation folded into Development; the CLAUDE.md reference removed from Development.

**Why**: Entry 65 landed the org flags but Global options only mentioned them in passing. User asked for proper documentation and for the README to follow their documentation-principles gist (https://gist.github.com/pborenstein/80b6e1a9011b4a02ad13dfbc06874141): information vs. data distinction (tables for structured data), no redundant hierarchy or pseudo-headings, identical format for similar content, jargon-free language, LLM config files excluded from docs.

**How**: Net -91 lines. Judgment calls per the principles: the CLAUDE.md pointer dropped from Development (principles exclude LLM config files; the file itself untouched), per-file tree comments dropped (component detail is ARCHITECTURE.md's job), jq examples kept as table rows with escaped pipes. Flag semantics verified against cli/__init__.py and config.py before writing (precedence CLI > MIMEO_* env > config; template org defaults to tepiton, deploy org maps to github.default_org). No code changes.

**Decisions**: none new (documentation practice; the gist is the reference)

**Files**: README.md (7cc2f14)
