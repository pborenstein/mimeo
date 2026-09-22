# Mimeo Implementation Tracker

Living document tracking progress on the domain landing page provisioning tool.

**Last updated**: 2026-08-25

---

## Phase Overview

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 0: Research & Design | Complete | Project setup, API exploration, architecture design |
| Phase 1: Core Infrastructure | Complete | Configuration management, data models, provider abstractions |
| Phase 2: Porkbun Integration | Complete | DNS configuration via Porkbun API |
| Phase 3: GitHub Pages Integration | Complete | Repository creation, Pages setup, custom domains |
| Phase 4: Content Generation | Complete | Simple HTML generator (no template engine) |
| Phase 5: CLI Integration | Complete | Full CLI with create, list, health, fix commands |
| Phase 6: Hardening | Complete | Operational robustness and documentation |
| Phase 7: CLI Redesign | Complete | Rethink command structure from first principles |
| Phase 8: Consolidation | Current | Collapse verb sprawl into status/sync, unify CLI plumbing |

---

## Current Phase

### Phase 8: Consolidation (2026-07-06 - Present)

**Goal**: Reverse barnacleization. Mimeo is a fleet manager for
domain-to-GitHub-Pages sites, not a "website generator." Collapse the
per-incident verb sprawl (`dns repair`, `fix https`, `template apply`) into
declarative `status`/`sync`, unify the duplicated CLI fan-out plumbing, and
add E2E coverage. The tool should end this phase smaller, with fewer
front-door verbs than it started with. See DEC-021.

**Tasks**:

- [x] Stage 1: Shared domain-operation engine (debt paydown, no behavior change)
  - [x] Extend `_processing.py` into one fan-out engine: `map_items` (ordered
        partial results, exceptions become error rows), `render_results`
        (text/json/csv dispatch), `exit_on_errors` (partial -> EXIT_PARTIAL,
        total -> category code)
  - [x] Migrate `registrar list`, `dns check`, `dns show`, `fix https`,
        and `list` onto it (four hand-rolled thread pools removed; three of
        them crashed entirely on one bad future.result())
  - [x] Measure: command files shrank ~65 lines but the engine added ~110,
        so cli/ net +51 lines; the payoff is structural (one pool, one
        dispatch) and compounds when status/sync build on it
  - [x] Follow-up: fold `process_domains_concurrent` (create, dns repair,
        template apply) into `map_items` — the remaining duplicate pool
        deleted process_domains_concurrent, exit_on_failures, Lock
- [x] Stage 2: `mimeo status [DOMAINS...]` — the cross-provider join
  - [x] One table joining Porkbun domains x GitHub repos x DNS drift x
        Pages health (DOMAIN / EXPIRES / NS / DNS / SITE + summary line)
  - [x] Surface the diff: no-arg mode covers the union of both sides;
        domains without sites show "no repo", sites without domains show
        "-" on the registrar side; `--problems` filters to what needs
        attention
  - [x] Subsumes the `registrar list --with-dns` full-sweep use case
  - [x] `--with-dns` includes full live records (json/csv, and indented
        under each row in text); records fetched once and reused for the
        drift check via check_dns_drift(live_records=...)
  - [x] Fleet-wide requires explicit --all (sweep is slow: several API
        calls per domain); bare `mimeo status` refuses with guidance
  - Note: DNS column is "-" when no repo exists (no desired state to
    compare); drift/unhealthy are findings (exit 0), API errors are
    failures (EXIT_PARTIAL)
- [x] Stage 3: `mimeo sync [DOMAINS... | --all]` — converge on desired state
  - [x] One pass: applies missing DNS records + enables HTTPS when cert
        ready; resets nameservers only with --reset-nameservers (template
        apply stays manual — content is a choice, not drift)
  - [x] `--dry-run` previews planned actions; partial-failure exit codes
  - [x] Fleet-wide requires explicit --all; no-arg invocation refuses
        with guidance (mutating command, 105-domain blast radius)
  - [x] Acts on missing records only — extra records (e.g. Porkbun
        wildcard parking CNAME) are reported by status but never deleted
  - [x] Does not wait for DNS propagation (fleet-scale); `dns repair`
        remains the single-domain verified fix
  - [x] Fate of `dns repair` / `fix https`: kept as targeted scalpels
        (repair verifies propagation; fix https does discovery); sync is
        the batch front door
- [ ] Stage 4: E2E integration test lane (separate from unit tests, gated,
      hits real APIs; `create`/`status`/`sync` are the flows worth covering)
- [x] Identity fix: replace "A tool to generate websites quickly" with
      "Provision and manage custom-domain sites on GitHub Pages"
      (CLI help, pyproject, package docstring, CLAUDE.md); README gained
      status/sync command sections
- [x] Externally-managed domains handled honestly
  - [x] `dns show` (and `status --with-dns` text) explain an empty Porkbun
        zone when nameservers point elsewhere instead of "(no records)"
  - [x] `defaults.ignore_domains` config list trims `status --all` and
        `sync --all`; explicitly named domains always override
  - [x] `lookup_nameservers` made public (doctor.py already used it)
- [x] Carried from Phase 7: template parameterization (substitute domain
      into template files post-creation)
  - [x] `mimeo.lol` (the default template) hardcodes its own domain name in
        `<title>` and as letter-spaced text in `<h1>` — it's a live site
        being reused as a template. `_customize_default_template` now
        rewrites both forms to the target domain after generation.
  - [x] Fixed a second race: `generate`-from-template can return before
        GitHub populates the file tree, so the first `index.html` read can
        404 with "repository is empty" — same class of bug as Entry 30,
        different endpoint (contents API, not repo metadata). Retried
        (5x/2s) rather than swallowed.
  - [ ] Scoped to `mimeo.lol` only; `eleventy-*` templates (full site
        generators with their own config) are a separate, harder problem
  - [x] Surveyed all 8 tepiton templates (Entry 42, extended Entry 44). Site
        identity lives in a different file/format per family:
        `content/_data/metadata.js` `url:` key (eleventy-*, 5 templates),
        hardcoded HTML string (mimeo.lol, laptopistan.com), YAML frontmatter
        `title:` (pandoc-simple). Design shape decided: per-template manifest
        (`mimeo.template.json`) declaring `{file, format, key/match, value}`
        substitutions, format one of `js-key` / `string-replace` /
        `yaml-frontmatter-key`. Replaces `_customize_default_template`
        (currently `mimeo.lol`-only) with one dispatcher; templates with no
        manifest are skipped, not errored. Implemented 2026-09-09 — see the
        DEC-024 stage section below and Entry 56
  - [ ] Scope boundary clarified (Entry 44): mimeo only stamps the site's own
        domain into its one declared self-reference point (title/metadata
        url). Template authoring — bios, copy, deciding what "generic"
        looks like — is out of scope; Entry 43's identity scrub was that
        kind of work and correctly happened in mimeo-sites, not here
  - [x] Prerequisite: `eleventy-tech-blog` and `eleventy-prose-blog` shipped
        real live-site identity (`pborenstein.dev`/`.com`, real email, a
        `pborenstein.2025` git URL). Scrubbed (Entry 43) — both now use
        `example.com`/placeholder author info like the other three eleventy
        templates. Personal demo posts/pages replaced with generic ones.
        Lives in mimeo-sites, not this repo
- [x] `template apply --force` safety fix: rename-then-generate-then-delete
      instead of delete-then-generate (DEC-022)
- [x] `_rename_repository` uses numeric repo ID (`repositories/<id>`) to avoid
      GitHub 307 redirects on previously-renamed repos; retries once on 422
      (GitHub serializes rapid renames) (DEC-023)
- [x] `mimeo list --show-template`: optional flag fetches `template_repository`
      per repo via parallelized `gh api` calls; adds TEMPLATE column to text
      output and `template` field to json/csv
- [x] `template apply` validates template name before confirmation prompt via
      `validate_template()` — fails fast with clear message on typo
- [x] `_delete_stale_pages_artifacts` cleans up old `github-pages` artifacts
      after force-replace; GitHub's deploy-pages action fails if more than one
      artifact with that name exists in the same workflow run
  - [x] Live incident: a generate failure (source repo missing
        `is_template`) after the old delete-first ordering destroyed
        `tepiton/laptopistan.com` with no rollback; recovered via GitHub
        org deleted-repo restore
  - [x] `_ensure_is_template` checks/auto-sets `is_template` on the source
        repo before every `generate` call (was a bare, misleading 404)
  - [x] Force-replace renames the target out of the way instead of
        deleting it; only deletes the renamed-old repo after `generate`
        succeeds; renames back on any failure
- [x] Stage 5: Collapse 9 verbs to 5 (DEC-025). Read DEC-025 in full before
      starting — this section is the checklist, DEC-025 is the rationale.
      No provider-layer changes anywhere in this stage; `github.py` and
      `porkbun.py` are untouched. Target surface: `create`, `status`,
      `sync`, `doctor`. Complete and merged to `main` (2026-09-09, merge
      commit `56d75bd`). The fifth verb, `template lint`, is a separate
      concern (validates DEC-024's manifest schema rather than collapsing
      existing verbs) — moved to Stage 6.
  - [x] 5A: `create` absorbs `template apply`
        - [x] Add `--force` (bool) and `--yes` (bool, skip confirm) to
              `mimeo/cli/create.py`'s `create` command
        - [x] Wire `--force` to the existing `deploy_site(force=True)` path
              (already used by `template apply`, `mimeo/cli/template.py:133`)
        - [x] Port `template apply`'s confirmation-prompt logic (skipped by
              `--yes`) into `create`, gated on `--force`
        - [x] `--template` on `create` already exists and defaults to
              `DEFAULT_TEMPLATE`; `template apply`'s `--template` was
              `required=True` — no behavior change needed, just drop the
              requirement when merging
        - [x] Delete `mimeo/cli/template.py`; remove its registration in
              `mimeo/cli/__init__.py`
        - [x] Relocate `template apply`'s tests (confirm prompt, DEC-022
              rollback-on-failure case) onto `create --force` test cases
              (DEC-022 rollback coverage already lived at the provider layer
              in `tests/providers/host/test_github.py`, untouched; only the
              two CLI-layer tests moved)
        - [x] Update `create`'s help text: state that `--force` replaces an
              existing repo's content (same effect `template apply` had),
              and that the domain-substitution manifest (DEC-024, once
              implemented) reruns automatically on both plain `create` and
              `create --force`
  - [x] 5B: `status` absorbs `list`, `registrar list`, `dns show`, `dns check`
        - [x] Add `--source {github,porkbun,dns}` to `mimeo/cli/status.py`
        - [x] No `--source` = current full-join behavior (unchanged)
        - [x] `--source github` reproduces `list`'s output (repo name, url,
              updated, optionally health/template columns per
              `list --health`/`--show-template`) — verify column parity
              before deleting `list_cmd.py`
        - [x] `--source porkbun` reproduces `registrar list` (domain,
              expiry, optionally `--with-dns` records, which `status`
              already supports) — verify before deleting `registrar.py`
        - [x] `--source dns` reproduces `dns show` (raw live records, no
              comparison) when used alone, and `dns check` (drift only,
              read-only) when combined with the existing `--problems` flag
              — verify both shapes before deleting `dns.py`'s `show`/`check`
        - [x] Gap found and closed as planned: `list --show-template`'s
              TEMPLATE column had no `status` equivalent. Added `--show-template`
              to `status` itself (valid with `--source github` or the full
              join), backed by the same `get_template_repository()` call.
        - [x] Deleted `mimeo/cli/list_cmd.py` and `mimeo/cli/registrar.py`
              (registrar.py had nothing left once `list` moved); deleted
              `dns.py`'s `show` and `check` commands (repair stays for 5C)
        - [x] Removed dead registrations in `mimeo/cli/__init__.py`
              (`list_sites`, `dns.show`/`dns.check` implicitly via file
              deletion, `registrar`/`registrar_list`)
        - [x] Relocated all four commands' test coverage onto `status
              --source X` equivalents in `tests/test_status.py` (three new
              classes: `TestStatusSourceGithub`, `TestStatusSourcePorkbun`,
              `TestStatusSourceDns`); removed `TestListCommand`,
              `TestRegistrarListCommand`, and the `show`/`check` tests out
              of `TestDnsCommands` in `tests/test_cli.py`. 296 tests passing
              (up from 270), ruff/mypy clean.
        - [ ] Not done this session: a live-account smoke test against a
              real domain/repo (no Porkbun/GitHub credentials configured on
              this machine — only the example config template exists at
              `~/.config/mimeo/config.toml`). All verification here is
              mock-based; DEC-026's bugs were found by live testing, so
              treat this stage's `create`-adjacent paths as unverified
              against a real account until someone runs it live.
  - [x] 5C: `sync` absorbs `dns repair` and `fix https`
        - [x] **Before writing code**: read DEC-025's "Open question"
              section in full. Checked `sync --all`'s existing HTTPS-enable
              step (`mimeo/cli/sync.py`'s `_sync_domain`, calls
              `host.get_pages_health()` then `health_status() ==
              "fixable"` then `host.enable_https_enforcement()`) against
              `fix.py`'s `_fix_one`/discovery logic — confirmed identical
              check, no gap. Option (a) held; DEC-025 updated accordingly.
        - [x] Did **not** add `--wait`. Decided during implementation (not
              part of the original checklist) to drop the propagation poll
              entirely rather than recover it behind a flag, on the same
              reasoning DEC-026 used to drop `create`'s `verify_dns` call:
              it rarely observes real propagation and doesn't change
              `sync`'s behavior either way; `mimeo status` covers
              confirmation. DEC-025 and `sync`'s docstring updated to say
              so explicitly.
        - [x] Confirmed `sync`'s existing `--reset-nameservers` flag maps
              exactly onto `dns repair`'s nameserver-reset behavior (both
              call `registrar.update_nameservers()`) — no new flag needed.
        - [x] Deleted `mimeo/cli/dns.py` entirely (only `repair` remained
              after 5B deleted `show`/`check`) and its `dns` group
              registration in `mimeo/cli/__init__.py`.
        - [x] Deleted `mimeo/cli/fix.py`; removed its registration.
        - [x] No test relocation needed: `tests/test_sync.py`'s existing
              coverage (`test_all_targets_fleet_union`,
              `test_fixable_https_enabled`, `test_missing_dns_applied`,
              `test_reset_nameservers_flag`, `test_dry_run_makes_no_changes`)
              already exercised every case `TestFixHttpsCommand`/
              `TestDnsCommands` in `tests/test_cli.py` covered — those two
              classes were deleted outright, no new tests written. 292
              tests passing, ruff/mypy clean.
        - [x] Updated `create.py`'s "Use 'mimeo dns repair'..." log message
              and `sync.py`'s own docstring (which referenced `mimeo dns
              repair` for propagation confirmation) to point at `sync`/
              `status` instead.
        - [x] Fixed direct breakage in `README.md` and
              `docs/TROUBLESHOOTING.md` (command examples that named the
              now-deleted `mimeo dns repair`/`mimeo fix https`). Did NOT do
              a full pass on either file — both still reference other
              already-absorbed commands (`mimeo list --health`, `template
              apply`) from 5A/5B that predate this session; that's 5D's
              "Update README.md" line, not scope creep to redo here.
              `docs/ARCHITECTURE.md` still has a stale module map (lines
              ~22-23 name `dns.py`/`fix.py` directly) and multiple stale
              command sections — left entirely for 5D, it needs a
              structural rewrite, not a find/replace.
        - [x] **Bug found via live testing against `002373.xyz`** (real
              extra CNAME drift, see CONTEXT.md): `sync --dry-run` reported
              `ok` for a domain `status` correctly reported as `DNS:
              drift`. Cause: `_sync_domain` only checked
              `drift["missing"]`, never `drift["status"]`/`drift["extra"]`,
              so an extra-only result fell through to "ok" silently. Bug
              predates 5C (the DNS block wasn't touched by the merge) but
              surfaced because 5C makes `sync` the natural next command
              after `status` reports drift. Fixed: `sync` now reports the
              same `dns_status`/`extra` terms `status` uses instead of
              collapsing extra-only drift into "ok". See DEC-025's
              "Bug found post-merge" note for full detail. Test:
              `test_extra_only_reports_drift_not_ok`. 293 tests passing.
  - [x] 5D: Registration cleanup
        - [x] Read through `mimeo/cli/__init__.py`'s `main.add_command(...)`
              calls; confirmed exactly 4 registered (`create`, `status`,
              `sync`, `doctor`) — already correct from 5A/5B/5C, no change
              needed.
        - [x] Full test suite, mypy, ruff all pass clean: 294 tests passing,
              mypy clean (19 source files), ruff clean.
        - [x] Updated README.md's command reference section to the 5-verb
              surface: `mimeo list` section rewritten as `mimeo status
              --source github`, `mimeo registrar list` section rewritten as
              `mimeo status --source porkbun`, added a `mimeo status
              --source dns` section (raw records / drift, no prior README
              section existed for it). Updated project-structure file list
              and test count (233 -> 294).
        - [x] Rewrote `docs/ARCHITECTURE.md` structurally: component map,
              provider abstraction diagram, and command-workflow sections
              now reflect the 5-verb surface. Replaced the four separate
              List/DNS-check/DNS-repair/Fix-HTTPS/Template-apply workflow
              sections with Create/Status/Sync workflow sections matching
              current `create.py`/`status.py`/`sync.py` behavior (including
              `--source`, `--problems`, `--with-dns`, `--show-template`,
              `--reset-nameservers`, the extra-only-drift reporting fix from
              5C, and the dropped propagation poll).
        - [x] Deleted `docs/LIST_COMMAND.md` (documented the fully-deleted
              `mimeo list` command; not in the original checklist but found
              during the doc sweep — confirmed with user before deleting).
              Removed its two README references (Documentation table,
              project-structure file list).
        - [x] Fixed three stale `docs/TROUBLESHOOTING.md` refs found during
              the sweep: two `mimeo list --health` -> `mimeo status --all
              --source github --health`, one `mimeo dns repair` -> `mimeo
              sync`.
        - [x] Swept `docs/DECISIONS.md` for stale refs: none needed fixing —
              its mentions of `template apply`/`dns repair`/`list`/etc. are
              historical decision-record entries describing the surface as
              it existed at the time, which is correct for a decision log.
- [x] DEC-024 implementation: template manifest (2026-09-09). Schema
      ratified in DEC-024's addendum after surveying the real template
      files; read the addendum before touching this code.
  - [x] New module `mimeo/providers/host/template_manifest.py`:
        `parse_manifest()` (strict validation — unknown fields/formats/
        tokens, per-format key-vs-match rules, duplicate detection),
        `apply_substitutions()`, and the three handlers — `string-replace`
        (literal, all occurrences, absent match is loud), `js-key`
        (loosey-goosey: dotted path to a unique string-literal leaf
        through any object literal; unkeyed braces are path-transparent;
        ambiguity and non-string leaves are loud), `yaml-frontmatter-key`
        (set-by-key, top-level only). `DEFAULT_DEV_PATHS` =
        `["README.md", "docs/", "CLAUDE.md"]` — adds CLAUDE.md to the
        old hardcoded list per user call.
  - [x] `GitHubHost` wiring: `_fetch_template_manifest` (template-repo
        fetch, 404 -> None = no manifest, invalid -> HostError before any
        mutation), `_apply_template_manifest` (grouped by file, one
        read/write per file, no-op guard preserved), `_read_file_with_retry`
        (5x2s empty-repo race carried over), `_strip_template_dev_files`
        now takes dev_paths (manifest override or defaults); the manifest
        file itself is always stripped from generated repos.
        `_customize_default_template` and `TEMPLATE_DEV_PATHS` deleted —
        no template-specific knowledge left in mimeo source.
  - [x] Tests: `tests/providers/host/test_template_manifest.py` (42
        cases; fixtures mirror real template files — tech-blog's
        metadata.js with comments/nesting/process.env/placeholder email,
        pamphlet's addPlugin options object, pandoc-simple frontmatter,
        laptopistan/mimeo.lol HTML); `test_github.py` updated — manifest
        fetch/apply/integration, self-deploy no-op (supersedes the old
        repo-name gate), invalid-manifest-fails-before-mutation. 333
        tests passing (up from 296), mypy clean, ruff unchanged from
        baseline (same 5 pre-existing errors).
  - [x] Docs: DEC-024 addendum + status, ARCHITECTURE.md component map
        and create-workflow note updated.
  - [x] Follow-up outside this repo (mimeo-sites): add
        `mimeo.template.json` to every template — done 2026-09-09/10,
        all ten repos pushed. mimeo.lol/laptopistan.com: one
        string-replace entry. pandoc-simple: yaml-frontmatter-key on
        `title:`. Each eleventy template: js-key `url` (plus an
        about.md string-replace for chapbook/folio/pamphlet). The
        eleventy rollout also drove a template cleanup — deleted
        `author.url`/`author.email`/`feed.id` (read by nothing, only
        leaked into Atom feeds), deleted two stale `notreally.config.js`
        copies, made pamphlet's feed base derive from `metadata.url`,
        normalized all `url:` placeholders to `https://example.com/`.
        All templates build clean post-cleanup. Live-verified end to
        end by the user: `mimeo create bluegazebo.dev --template
        mimeo.lol` and `mimeo create tepiton.com --force`.
- [x] Stage 6: `template lint TEMPLATE` — **dropped 2026-09-10** before
      any work started, juice not worth the squeeze. Deploy-time
      validation already aborts loudly on a bad manifest and names the
      failing entry (DEC-024, Entry 56), so lint would only buy earlier
      discovery of template/manifest drift; the fleet is ten templates
      with one maintainer, and the one drift incident to date
      (pandoc-simple's remote-side frontmatter cleanup, Entry 57) was
      caught by routine re-validation. The full design (read-only, no
      domain argument, per-entry pass/fail report naming the manifest
      entry at fault) is preserved in git history; revisit if templates
      gain outside contributors or the fleet grows.
- [x] Code review fix pass (GLM 5.3's `docs/CODE_REVIEW.md`, 2026-09-08)
  - [x] Fixed BUG 1 (`domain_exists` conflated "not owned" with "API
        broken" — now only Porkbun's actual "Domain not found" response
        maps to `False`), BUG 2 (`create --force` help text falsely said
        DNS is untouched), BUG 3 (`status --source dns --problems` exited
        0 on API errors — added the missing `exit_on_errors` call), BUG 5
        (`--stop-on-error` on `create` was accepted and silently ignored —
        deleted the flag)
  - [x] Removed dead `verify_dns` entirely (ABC slot, Porkbun impl, and
        its stale test coverage — net -7 tests, 296 -> 289, all
        `verify_dns`-only); collapsed `HTTPClient`'s four HTTP verbs onto
        one `_request` helper and dropped its dead `max_retries`/
        `backoff_factor` ctor params; fixed a stale comment in
        `config.py`
  - [x] Left BUG 4, 6, 7, the error-semantics refactor, and D1-D5 (design
        concerns) untouched — out of scope for this pass. `default_
        registrar`/`default_host` (D2) and `ProviderError` deliberately
        left in the dead-code table too: D2 is documented user-facing
        config surface needing a real decision (factory vs. removal), not
        mechanical sweeping; `ProviderError` is a legitimate hierarchy
        node per the review's own framing
  - [x] `docs/CODE_REVIEW.md` updated inline (FIXED/REMOVED/left-open
        markers per finding) rather than tracked in a separate checklist
- [x] Error-path QoL + rec #2 pass (2026-09-12, Entry 61, DEC-027/028)
  - [x] Output cleanup: failures print once (one-line stderr trailer,
        not per-row `[category]` lines); `====SUMMARY====` banner and the
        false "Successfully created: 0/1 domain(s)" headline removed;
        sigils became check/warn/cross glyphs; redundant "GitHub CLI
        command failed:" prefix dropped from gh errors
  - [x] Structured error semantics (rec #2): `HostError.status_code`
        parsed from gh stderr in one place; rename-422, manifest-404,
        Pages probe, `get_pages_health`, retry, and `_categorize_error`
        branch on codes, keywords demoted to code-less fallback
  - [x] BUG 4 fixed (unexpected exceptions exit 1/"error", not
        5/"provider"; definitive provider failures exit 1); BUG 7 fixed
        (`get_pages_health`: only 404 means "no Pages", other failures
        propagate as "couldn't check")
  - [x] Honest `create` recap (DEC-028): created / already-existed /
        failed trichotomy, DNS skip reasons rendered, parallel runs
        narrate per-domain start/outcome instead of going silent
  - [ ] BUG 6 remains (missing-`schema_version` warning invisible to CLI
        users — `DeprecationWarning` is hidden outside `__main__`); small
        fix: stderr line or drop the check
- [x] Subdomain sites (`mimeo create service.example.com`) — closed
      2026-09-12 without implementation: getting the eleventy templates
      working was the answer. Full design preserved in
      `docs/SUBDOMAINS.md` if ever revived.
- [x] Config-driven template source + README accuracy pass (2026-09-21,
      Entry 63, DEC-029)
  - [x] `github.template_org` (env `MIMEO_GITHUB_TEMPLATE_ORG`, default
        tepiton) and `defaults.template` (env `MIMEO_DEFAULT_TEMPLATE`,
        default mimeo) added to Config with type validation;
        `GitHubHost` takes `template_org` independent of `default_org`
        and aims validate/generate/manifest calls at it; `create
        --template` resolves from config when omitted
  - [x] `DEFAULT_TEMPLATE` renamed mimeo.lol -> mimeo (template repo was
        renamed in tepiton); 361 tests passing, ruff/mypy clean
  - [x] README accuracy pass: `uv run` in Quick Start, `create` documents
        `--template`/`--force`/`--yes`/`--skip-dns`, test count corrected;
        `uv.lock` committed (un-ignored) so `uv sync --frozen` works on
        fresh clones
  - [x] Live `~/.config/mimeo/config.toml` and `config.toml.example`
        rewritten clean; destination-org vs template-org roles explicit
        and adjacent (live config outside the repo, not committed)

---

### Phase 7: CLI Redesign (2026-03-19 - 2026-07-06)

**Delivered**:

- `mimeo/cli/` package with task-oriented command groups (DEC-018)
- `dns check` / `dns repair` / `dns show`, `template apply`, `fix https`,
  `registrar list`
- `create` and `list` stripped to single responsibilities
  (removed `--force`, `--force-dns-update`, `--fix`, `--dns-check`)
- Domain validation at CLI entry points (DEC-019); public provider methods
  for CLI-facing operations (DEC-020)
- 25 code-review findings fixed; full documentation realignment
- Race condition fix: `_wait_for_repo()` after template generate
- Partial results for `registrar list` (per-domain errors, EXIT_PARTIAL,
  shared HTTP clients)
- 243 tests passing; mypy and ruff clean

---

### Phase 6: Hardening (2026-02-17 - 2026-03-19)

**Delivered**:

- `mimeo doctor` preflight command (Python, gh auth/scope, config, NS checks)
- Retry with jitter for transient API failures
- Failure taxonomy and exit codes (config / auth / rate-limit / transient / partial)
- `--workers N` configurable concurrency on `create`
- Config schema versioning and deprecation warnings
- Structured logging (`--log-format json`)
- DNS drift detection (`mimeo list --dns-check`)
- Registrar/DNS/Host three-layer separation
- `--force-dns-update` flag on `create`
- `mimeo registrar list` subcommand
- Replaced content generation with GitHub template repo API
- `--template` flag on `create`

---

## Completed Phases

### Phase 5: CLI Integration (2026-02-14 - 2026-02-16)

**Delivered**:

- `mimeo create <domain> [<domain>...]` — full end-to-end provisioning
  - Concurrent processing via ThreadPoolExecutor (up to 5 workers)
  - `--dry-run`, `--stop-on-error`, `--sequential` flags
  - Idempotent: handles existing repos, duplicate DNS records, HTTPS enforcement
- `mimeo list` — shows all repos tagged with `mimeo` topic
  - `--format text|json|csv` output formats
  - `--health` flag: concurrent Pages API health check per repo
  - `--fix` flag: enables HTTPS for repos with approved certs
  - Tabular text output sorted by severity (problems first)
- 160 tests passing
- Multiple successful E2E deployments: pepito.lol, mellowtimesphere.com, laminar.rodeo

**Key implementation details**:

- `_health_status()` is module-level (exported); used by CLI layer
- `--fix` implies `--health`; fix runs serially after concurrent health fetch
- Health status values: `pages_error`, `no_cert`, `cert_pending`, `fixable`, `healthy`
- Pre-existing mypy/ruff issues in cli.py fixed in Phase 6 (cast + f-string cleanup)

### Phase 4: Content Generation (Complete)

Simple HTML generator with string substitution. Minimal landing pages: dark theme (#1a1a1a / #e0e0e0), domain name with letter spacing, centered flexbox layout. No template engine.

### Phase 3: GitHub Pages Integration (Complete)

`GitHubHost` provider using `gh` CLI. Repository creation, GitHub Actions Pages workflow, custom domain CNAME, HTTPS enforcement. Uses `gh` credential helper for git push auth.

### Phase 2: Porkbun Integration (Complete)

`PorkbunRegistrar` provider. HTTP client with retry. DNS record creation/update (idempotent). Handles apex/subdomain normalization and ALIAS/A record conflicts.

### Phase 1: Core Infrastructure (Complete)

`Config` (TOML + env var loading), `DNSRecord`/`DeployResult` models, `Registrar`/`Host` ABCs, exception hierarchy.

### Phase 0: Research & Design (Complete)

Project scaffold, API research, architecture design, provider abstraction design. Reference implementation: mimeo.lol.

---

## Notes

**Design Principle**: Zero manual steps. `mimeo create domain.com` → live site, no intervention.

**Reference Site**: [mimeo.lol](https://mimeo.lol) / [pborenstein/mimeo.lol](https://github.com/pborenstein/mimeo.lol)

**Future Extensibility**: Provider ABCs support additional registrars (Namecheap, Cloudflare) and hosts (Netlify, Vercel). Template manifest design outlined in docs/CODEX-SPEAKS.md.
