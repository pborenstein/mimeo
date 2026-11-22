# Decisions

Architectural decisions for Mimeo. Search with `grep -i "keyword" docs/DECISIONS.md`.

## Active Decisions

### DEC-001: Python with Click for CLI (2026-02-14)

**Status**: Active

**Context**: Need a robust, extensible CLI framework that supports subcommands, options, and eventual plugin architecture.

**Decision**: Use Python >=3.11 with Click framework for CLI implementation.

**Alternatives considered**:

- Bash script: Too limited for API integrations and error handling
- Go: Faster but Python better for rapid development and API client libraries
- Node.js: Good API support but less familiar for target users

**Consequences**: Python provides excellent API client libraries (requests, PyGithub), strong typing with mypy, and Click offers clean command structure. Trade-off is slower startup than compiled languages, but acceptable for this use case.

---

### DEC-002: uv for Package Management (2026-02-14)

**Status**: Active

**Context**: Need fast, reliable dependency management for Python project.

**Decision**: Use uv for package management and virtual environment handling.

**Alternatives considered**:

- pip + venv: Standard but slower and less reliable
- poetry: Good but slower than uv
- pipenv: Deprecated, not maintained

**Consequences**: uv provides fastest dependency resolution and installation. Consistent with modern Python tooling. Requires uv installation as prerequisite.

---

### DEC-003: Porkbun + GitHub Pages for Initial Implementation (2026-02-14)

**Status**: Active

**Context**: Need to choose initial registrar and host combination. Must support API automation and be free/low-cost.

**Decision**: Start with Porkbun (registrar) and GitHub Pages (host) for initial implementation.

**Alternatives considered**:

- Cloudflare Pages: Good but requires Cloudflare DNS transfer
- Netlify: Excellent but less clear on custom domain API automation
- Vercel: Similar to Netlify

**Consequences**: Porkbun has clean API and is where domains are already registered. GitHub Pages is free and well-documented for custom domains. Both have stable APIs. Will design provider abstraction to add other services later.

---

### DEC-004: Provider Abstraction for Extensibility (2026-02-14)

**Status**: Active

**Context**: Initial implementation targets Porkbun + GitHub Pages, but should support other providers in future.

**Decision**: Design registrar and host provider abstractions from the start, even though initial implementation only has one of each.

**Alternatives considered**:

- Hard-code Porkbun/GitHub: Faster to start but locks us in
- Plugin system: Over-engineered for current needs

**Consequences**: Slight upfront design cost, but enables adding Namecheap, Cloudflare, Netlify, etc. later without refactoring core logic. Abstractions should be minimal (registrar: configure_dns, host: deploy_site).

---

### DEC-005: tomllib for TOML Parsing (2026-02-14)

**Status**: Active

**Context**: Need to parse TOML configuration files for user credentials and settings.

**Decision**: Use Python's built-in `tomllib` (available in Python 3.11+) for TOML parsing.

**Alternatives considered**:

- toml package: External dependency, not needed since tomllib is in stdlib
- PyYAML for YAML config: Less human-friendly for configuration files

**Consequences**: Zero external dependencies for config parsing. Requires Python 3.11+ (already our minimum). tomllib is read-only, but we don't need to write config files.

---

### DEC-006: Dataclasses over Pydantic for Models (2026-02-14)

**Status**: Active

**Context**: Need data models for Domain, DNSRecord, and DeploymentConfig with validation.

**Decision**: Use standard library dataclasses with custom validation in `__post_init__`.

**Alternatives considered**:

- Pydantic: Powerful but adds external dependency
- attrs: Similar to dataclasses but external dependency
- Plain classes: Less boilerplate but more code

**Consequences**: Keep dependencies minimal. Dataclasses provide clean syntax and type hints. Custom validation gives us full control. Trade-off is less automatic validation than Pydantic, but sufficient for our needs.

---

### DEC-007: Environment Variable Overrides for Credentials (2026-02-14)

**Status**: Active

**Context**: Configuration should support both file-based and environment variable credentials for flexibility (CI/CD, Docker, etc.).

**Decision**: Support environment variable overrides for all credentials with `MIMEO_*` prefix. Env vars take precedence over config file values.

**Alternatives considered**:

- File-only config: Simpler but less flexible for deployment scenarios
- .env files: Adds dependency and complexity
- Command-line arguments: Too verbose for sensitive credentials

**Consequences**: Flexible deployment (local dev uses config file, CI uses env vars). Clear naming convention with MIMEO_ prefix. Follows 12-factor app principles.

---

### DEC-008: XDG Base Directory for Configuration (2026-02-14)

**Status**: Active

**Context**: Need to decide where to store user configuration file.

**Decision**: Use `~/.config/mimeo/config.toml` following XDG Base Directory specification.

**Alternatives considered**:

- ~/.mimeo/config.toml: Non-standard location
- /etc/mimeo/: System-wide, requires elevated permissions
- Current directory: Not portable

**Consequences**: Follows Unix/Linux conventions. Config separate from working directories. Cross-platform compatible (works on macOS, Linux). Standard location users expect.

---

### DEC-009: Porkbun IPv4 API Endpoint (2026-02-14)

**Status**: Active

**Context**: Need to choose correct Porkbun API endpoint for HTTP requests.

**Decision**: Use `https://api-ipv4.porkbun.com/api/json/v3` as the base URL for all Porkbun API calls.

**Alternatives considered**:

- https://porkbun.com/api/json/v3: Returns 403 Forbidden errors
- https://api.porkbun.com/api/json/v3: Not tested, IPv4 version recommended

**Consequences**: Successful API authentication and DNS operations. The IPv4-specific endpoint is required for API access to work. Using the wrong endpoint results in 403 errors even with valid credentials.

---

### DEC-010: Use gh CLI for GitHub Operations (2026-02-14)

**Status**: Active

**Context**: Need to interact with GitHub API for repository creation and Pages setup. Must handle authentication for both API calls and git push operations.

**Decision**: Use gh CLI for all GitHub operations rather than direct API access or PyGithub.

**Alternatives considered**:

- PyGithub library: Would need separate solution for git push authentication
- Direct API with requests: Same authentication challenges
- SSH keys: Requires users to set up SSH (additional friction)

**Consequences**: gh CLI handles OAuth flow and stores credentials. Can use `gh auth git-credential` as git credential helper for seamless HTTPS push authentication. Simpler for users (single `gh auth login` setup). Trade-off is dependency on external tool, but gh CLI is standard in developer workflows.

**Technical detail**: Configure git with `git config credential.https://github.com.helper "!gh auth git-credential"` to use gh for authentication.

---

### DEC-011: No Template Engine for Content Generation (2026-02-14)

**Status**: Active

**Context**: Need to generate minimal landing pages with domain names. Initial plan was to use Jinja2 template engine.

**Decision**: Use simple string substitution instead of a template engine. Hardcode HTML structure and styles.

**Alternatives considered**:

- Jinja2: Over-engineered for single variable substitution
- Other template engines: Same problem, unnecessary complexity

**Consequences**: Simpler code, no external dependencies, easier to understand. Trade-off is less flexibility for customization, but current goal is just "hello world on multiple domains" - not customizable templates. Can add templating later if needed.

---

### DEC-012: Flat Config Structure (2026-02-14)

**Status**: Active

**Context**: Config file structure needed to be user-friendly and match documentation terminology. Initial implementation used nested `[providers.porkbun]` structure but config.toml.example used flat `[porkbun]`.

**Decision**: Use flat config structure: `[porkbun]`, `[github]`, `[defaults]` (not `[providers.X]`).

**Alternatives considered**:

- Nested structure `[providers.porkbun]`: More hierarchical but doesn't match DNS provider documentation terminology
- Support both formats: Unnecessary complexity

**Consequences**: Config matches how Porkbun/GitHub documentation refers to these sections. Simpler for users to understand. Aligns config.toml.example with actual code expectations. Required updating all tests and config loading logic.

---

### DEC-013: Generate GitHub Actions Workflow (2026-02-14)

**Status**: Active

**Context**: GitHub Pages supports two deployment modes: legacy (branch-based) and workflow (GitHub Actions). Workflow mode is the modern approach and supports more customization.

**Decision**: Generate `.github/workflows/static.yml` file as part of content generation. Use GitHub Actions workflow deployment for all sites.

**Alternatives considered**:

- Legacy branch-based deployment: Simpler but deprecated path
- No workflow file: Would force users to manual setup
- Template-based workflow: Over-engineered for simple static deployment

**Consequences**: Sites deploy via GitHub Actions (modern, supported path). Requires `workflow` scope in gh CLI authentication. Generates standard workflow file copied from reference repo (mimeo.lol). Trade-off is slight complexity in content generation, but aligns with GitHub's recommended approach.

---

### DEC-014: DeployResult Dataclass as Return Value (2026-02-16)

**Status**: Active

**Context**: deploy_site() originally returned a bare string (the URL) and communicated additional state (repo_created, https_enabled) via instance flags set as side effects. CLI read these with hasattr() checks — a fragile pattern since the flags only existed if deploy_site() completed successfully.

**Decision**: Return a DeployResult(url, repo_created, https_enabled) dataclass from deploy_site(). Place DeployResult in providers/base.py alongside the Host ABC so it's part of the provider contract.

**Alternatives considered**:
- Tuple return: (url, repo_created, https_enabled) — unreadable at call sites
- Dict return: Loses type safety
- Keep instance flags: Works but fragile; breaks if deploy_site() is called more than once per instance

**Consequences**: deploy_site() signature changes from `-> str` to `-> DeployResult`. All callers and mocks must be updated. Type-safe, explicit, and no hidden side channels. The abstract Host.deploy_site() method now requires concrete implementations to return DeployResult.

---

### DEC-015: Three-Layer Provider Model — Registrar / DNSProvider / Host (2026-02-20)

**Status**: Active

**Context**: `PorkbunRegistrar` was conflating three distinct responsibilities: domain registration/ownership, DNS record management, and knowledge of what DNS records a specific host needs. This caused a real bug: when DNS is delegated to Cloudflare or Netlify, mimeo would write records via the Porkbun API, get a SUCCESS response, but those records would be invisible because Porkbun's DNS is not authoritative for the domain.

**Decision**: Introduce a three-layer model:
- `Registrar` — who the domain is registered with; knows how to check NS records. Does NOT manage DNS records.
- `DNSProvider` — who is authoritative for DNS; knows how to create/delete/verify records via that provider's API.
- `Host` — where content is served; knows what DNS records it requires via `required_dns_records(domain)`.

Porkbun is both a Registrar and a DNSProvider in the common case. When DNS is delegated, a different DNSProvider implementation is used.

**Alternatives considered**:
- Keep everything in `PorkbunRegistrar`, add a flag: Simpler short-term, but the flag becomes load-bearing and the class keeps growing.
- Separate NS check into a utility function: Doesn't express the abstraction; future providers (Cloudflare, Netlify) still need the same interface.

**Consequences**: `create` now does an NS check before touching DNS. Mismatch → warn and skip DNS config (site still deploys to .github.io). Adds `PorkbunDNSProvider` alongside `PorkbunRegistrar` in porkbun.py. All DNS test mocks updated to target `DNSProvider`. `Host` ABC gains `required_dns_records()` as a required abstract method.

---

### DEC-016: NS Check Warn-and-Skip Rather Than Hard-Fail (2026-02-20)

**Status**: Active

**Context**: When `create` detects that nameservers don't point to Porkbun, we have a choice: hard-fail the entire operation, or deploy the site and skip DNS config with a warning.

**Decision**: Warn-and-skip. The site is deployed to GitHub Pages and accessible via the `.github.io` URL. A warning is logged explaining that NS records point elsewhere and DNS was not configured.

**Alternatives considered**:
- Hard-fail (raise `NSMismatchError`): Prevents any work from being done. The user still has a working site at the .github.io URL if we proceed with deployment.
- Silently skip: Confusing; user expects DNS to be configured and doesn't know why it wasn't.

**Consequences**: `NSMismatchError` exists in the exception hierarchy for callers that want to hard-fail (e.g. a hypothetical `--strict` flag). The result dict gains `ns_mismatch` and `dns_pending` fields when skipped. `mimeo doctor domain.com` provides a way to check NS status proactively before running `create`.

---

### DEC-017: GitHub Template Repo API Replaces Local Content Generation (2026-03-19)

**Status**: Active

**Context**: `content.py` generated HTML inline via string substitution, then
git-initialized a temp directory and pushed it to GitHub. This was fragile
(local git, credential setup, temp dir lifecycle) and meant the source of truth
for site content lived in Python strings rather than actual repos.

**Decision**: Use GitHub's "Use this template" API (`POST /repos/{owner}/{repo}/generate`)
to instantiate new site repos from template repos in the `tepiton` org. Template
repos (`tepiton/mimeo.lol`, `tepiton/pandoc-simple`, etc.) are the authoritative
source of content and GitHub Actions workflows. `mimeo create` passes a `--template`
flag (default: `mimeo.lol`) to select the template.

**Alternatives considered**:
- Keep local generation, add template file copying: Still requires git operations
  and a local content pipeline; doesn't scale to complex templates (Eleventy etc.)
- Clone template repo and push: More steps than the API, same outcome

**Consequences**: `content.py` deleted. No local git operations during `create`.
Template repos must have `is_template=true` set on GitHub (done for `mimeo.lol`).
Parameterization (substituting domain into template files) requires a follow-up
step since the template API copies files verbatim.

---

### DEC-018: CLI Redesign -- Task-Oriented Command Groups (2026-03-20)

**Status**: Active

**Context**: `mimeo create` was overloaded -- it handled provisioning, DNS repair (`--force-dns-update`), and template re-application (`--force`). `list` had side effects (`--fix`) and DNS checking (`--dns-check`). DNS repair required running the full create flow. The CLI needed to be organized around actual use cases.

**Decision**: Split CLI into task-oriented commands:

- `create DOMAINS...` -- provision new sites only (no `--force`, no `--force-dns-update`)
- `dns check DOMAINS...` -- read-only DNS inspection (replaces `list --dns-check`)
- `dns repair DOMAINS...` -- fix DNS records (replaces `create --force-dns-update`)
- `template apply DOMAINS...` -- replace repo content (replaces `create --force`)
- `fix https [DOMAINS...]` -- enable HTTPS enforcement (replaces `list --fix`)
- `list` -- pure read-only (no `--fix`, no `--dns-check`)

Also converted `mimeo/cli.py` (1084 lines) to a `mimeo/cli/` package with one file per command group plus shared `_processing.py` utilities.

**Alternatives considered**:

- Keep single create with more flags: Leads to flag proliferation and confusing semantics
- Use positional subcommand style (`mimeo create dns-repair`): Doesn't compose well in Click

**Consequences**: Breaking changes to CLI flags (acceptable pre-1.0). Each command has a clear, single responsibility. `create` now prints guidance messages pointing to `template apply` and `dns repair` when it encounters existing repos or NS mismatches. Tests updated to patch submodule paths instead of `mimeo.cli.*`.

---

### DEC-019: Domain Validation at CLI Layer (2026-03-28)

**Status**: Active

**Context**: The `Domain` model existed with regex validation but was never used. The CLI accepted any string as a domain argument, including empty strings and non-domain text. Garbage input would propagate to GitHub and Porkbun API calls before failing.

**Decision**: Add `validate_domains()` in `_processing.py` using a regex pattern, called at the top of every CLI command that accepts domain arguments. Fail fast with exit code EXIT_CONFIG before making any API calls. Removed the unused `Domain` model from `models.py`.

**Alternatives considered**:
- Use the Domain model: Over-engineered (tld/sld extraction not needed), added unnecessary class hierarchy for simple validation
- Validate in each command separately: Duplication, easy to miss one

**Consequences**: All domain-accepting commands (`create`, `dns check`, `dns repair`, `template apply`) now reject invalid domains immediately. The `Domain` class is removed since it was never used outside tests. 233 tests pass.

---

### DEC-020: Public Provider Methods for CLI-Facing Operations (2026-03-28)

**Context**: CLI code was calling private methods on providers (`host._enable_https_enforcement()`, `dns_prov._get_domain_records()`). This defeated the ABC abstraction -- if provider implementations changed, CLI would break silently.

**Decision**: Make CLI-facing provider operations public API:
- `_health_status` -> `health_status` (module-level in github.py)
- `_enable_https_enforcement` -> `enable_https_enforcement` (added to Host ABC)

**Alternatives considered**:
- Keep private and accept coupling: Fragile, defeats abstraction purpose
- Create wrapper functions in a separate module: Unnecessary indirection

**Consequences**: Host ABC has `enable_https_enforcement` as an abstract method. Any new host provider must implement it. CLI goes through the public interface.

---

### DEC-021: Consolidate to Declarative status/sync Verbs (2026-07-06)

**Status**: Active (Phase 8)

**Context**: The CLI grew by accretion — each operational incident spawned its own remediation verb (`dns repair`, `fix https`, `template apply`) and its own diagnostic (`dns check`, `list --health`, `doctor`, `dns show`, `registrar list`). The two inventories (`list` = GitHub repos, `registrar list` = Porkbun domains) never join, so the fleet-level questions (domains without sites, sites without domains, drift, expiry risk) have no command. Half the codebase (~1,850 lines in `cli/`) is per-command copies of the same fan-out/render/error plumbing, which is where the recent zero-results bug lived. The tool's stated identity ("generate websites quickly") no longer matches what it does: content generation was delegated to GitHub template repos in DEC-017.

**Decision**: Reframe mimeo as a fleet manager for domain-to-GitHub-Pages sites and converge on two declarative front-door verbs:

- `mimeo status [DOMAINS...]` — read-only cross-provider join (registrar x DNS drift x Pages health), reporting the diff between desired and actual state
- `mimeo sync [DOMAINS...]` — apply whatever `status` flags (DNS records, HTTPS enforcement), with `--dry-run`

Template application stays a manual command: content choice is intent, not drift. Existing imperative commands become plumbing beneath status/sync (fate — alias vs deprecate — decided during Stage 3). Prerequisite: a single shared domain-operation engine in `_processing.py` replacing the per-command fan-out/render implementations.

**Alternatives considered**:

- Split into separate tools (registrar tool, DNS tool, Pages tool): Worse — the cross-provider join is the entire value; splitting destroys it
- Keep adding per-incident verbs: Unbounded command growth; every new failure mode demands a new subcommand forever
- Full desired-state config file (terraform-style): Overkill — desired state is derivable (Porkbun NS + GitHub Pages records + HTTPS on); no user-authored spec needed yet

**Consequences**: The CLI ends Phase 8 with fewer front-door verbs and less code than it started with. `registrar list --with-dns` full-account sweeps are subsumed by `status`. One-line identity changes to "Provision and manage custom-domain sites on GitHub Pages." Precedent: DEC-018 amputated `list --fix`/`list --dns-check` as misplaced — those were early gropes toward status/sync.

**Stage 3 resolutions (2026-07-06)**: Fleet-wide `sync` requires explicit `--all` (mutating command; implicit whole-fleet runs refused). `status` requires `--all` for fleet-wide too — not for safety but for cost: the sweep makes several API calls per domain and takes minutes on a 105-domain account. `sync` acts on missing DNS records only — extra records such as Porkbun's wildcard parking CNAME are reported by `status` but never deleted. `sync` does not wait for DNS propagation. `dns repair` and `fix https` are kept as targeted scalpels rather than deprecated: repair verifies propagation for a single domain, fix https does its own discovery; sync is the batch front door.

---

### DEC-022: Template Replace Is Rename-Then-Generate-Then-Delete, Not Delete-Then-Generate (2026-08-25)

**Status**: Active (Phase 8)

**Context**: `template apply --force` (via `_create_from_template`) deleted the target repo before attempting the template-generate call. A live run (`mimeo template apply --template mellowtimesphere.com laptopistan.com`) deleted `tepiton/laptopistan.com` and then failed the generate call with a 404, because the source repo `mellowtimesphere.com` was never flagged `is_template` on GitHub. Delete-then-generate has no rollback: any failure after the delete — wrong template flag, API hiccup, rate limit — destroys the target repo with nothing to replace it. Recovered only because `tepiton` is a GitHub Organization, which offers a ~90-day deleted-repo restore in Settings; a personal-owned repo would not have had that safety net.

**Decision**: Reorder repository replacement to be reversible:

1. Rename the existing target repo out of the way (`{name}-mimeo-replaced-{timestamp}`), not delete it
2. Verify (and auto-set) `is_template` on the source repo via new `_ensure_is_template` — GitHub's `generate` API 404s on a non-template source with no distinguishing error, so check the flag proactively instead of parsing a bare "Not Found"
3. Call `generate`
4. On any failure in steps 2-3, rename the displaced repo back to its original name and re-raise
5. Only on success, delete the renamed-old repo

Both `_ensure_is_template` and the `generate` call live inside the same try/except as the rollback, so a failure at either step restores the original name.

**Alternatives considered**:

- Leave delete-first, just fix the immediate `is_template` gap: Fixes today's incident, not the class — any other future generate failure (rate limit, network blip, wrong template name) would still destroy the target with no recovery
- Require manual `is_template` registration (a `template register` command): More explicit, but adds a command and a step users can still forget; auto-setting is strictly safer with no real downside since `is_template` has no cost to a repo already meant to be used this way

**Consequences**: `template apply --force` is now safe to fail: a 404, rate limit, or any other `HostError` during generate leaves the original repo intact under its original name. Costs one extra API call per apply (the `is_template` read) and, on force-replace, a temporary rename that's invisible unless the generate step fails. `_delete_repository` now only ever runs after a confirmed-successful generate.

---

### DEC-023: Rename Repository by Numeric ID, Not by Name (2026-08-27)

**Status**: Active (Phase 8)

**Context**: `_rename_repository` used `PATCH repos/<owner>/<name>` to rename a
repo. When a repo had been previously renamed, GitHub returns a 307 redirect on
the old name. `gh api` does not follow redirects on PATCH requests, so the rename
fails with "HTTP 307". This surfaced during `template apply --force`, where the
displaced-name repo (created by DEC-022's rename-out step) is later renamed back
on failure — the very scenario where a prior failed run left a redirect in place.
A second issue: GitHub serializes rename operations internally, so two renames in
quick succession can get a 422 "conflicting repository operation is still in
progress."

**Decision**: `_rename_repository` now:

1. Fetches the repo first via `GET repos/<owner>/<name>` to obtain its numeric `id`
2. PATCHes `repositories/<id>` instead of `repos/<owner>/<name>` — IDs are stable across renames, so no redirect is ever involved
3. Retries once on 422 after a 3-second sleep

**Alternatives considered**:

- Follow redirects at the `_gh_api` level: Would require detecting 3xx responses in the `gh` CLI output (not straightforward) and could mask other unintentional redirects
- Add `--follow-redirects` to the `gh api` call: `gh api` does not support this flag for non-GET methods

**Consequences**: `_rename_repository` now makes two API calls (GET + PATCH) instead of one. The GET is cheap and always needed to validate the repo exists before renaming. Rollback renames (the DEC-022 recovery path) are now reliable even when a prior failed run left GitHub's redirect table in a messy state.

---

### DEC-024: Template Substitution Scoped to Site's Own Domain, via Per-Template Manifest (2026-09-08)

**Status**: Complete (Phase 8) — implemented in mimeo 2026-09-09 (`mimeo/providers/host/template_manifest.py` plus `GitHubHost` wiring, per the schema addendum below), and all ten tepiton templates now ship a validated `mimeo.template.json` (2026-09-09/10, mimeo-sites). Live-verified via `mimeo create bluegazebo.dev --template mimeo.lol` and `mimeo create tepiton.com --force` — the string-replace substitution landed correctly on both a fresh create and a `--force` replace. The fleet is now eleven: `pandoc-resume` (added 2026-09-28 in mimeo-sites, live-tested by the user) ships the same validated manifest shape as `pandoc-simple` — one `yaml-frontmatter-key` on `index.md`'s `url` — and its own `CLAUDE.md`/`docs/` are stripped by the default `dev_paths`.

**Context**: `_customize_default_template` rewrites `mimeo.lol` -> `{domain}` in `index.html`, hardcoded to that one template, because `mimeo.lol` is itself a live site whose HTML hardcodes its own name. The open Phase 8 task ("template parameterization: pick a design shape") had drifted in scope during discussion toward general template authoring — bios, social handles, page copy, deciding what counts as "generic" identity (the concern behind Entry 43's mimeo-sites scrub). Re-examining mimeo's own identity shift (DEC-021: "fleet manager for domain-to-GitHub-Pages sites," not a site generator) surfaced that authoring judgment is a different tool's job; the piece that is legitimately mimeo's is narrow: when `foo.com` is deployed from a template, the template's boilerplate self-reference (its own name in `<title>`, `metadata.js`'s `url:`, frontmatter `title:`) should read `foo.com`, not the template's name. A survey of all 8 tepiton templates (extending Entry 42) found this single fact lives in three incompatible file formats: hardcoded HTML string (mimeo.lol, laptopistan.com), a JS object key (`content/_data/metadata.js` `url:`, used by the 5 eleventy-* templates), and YAML frontmatter (`index.md` `title:`, pandoc-simple).

**Decision**: Two scope decisions:

1. Mimeo's job is limited to propagating the target domain into a template's own declared self-reference point at deploy time — the same category as writing the DNS records or the Pages custom-domain field, not a general templating/content system. Template authoring (bios, tagline copy, what "generic" placeholder content looks like) stays out of mimeo; Entry 43's identity scrub correctly happened in mimeo-sites, not here, and future work of that kind belongs there too.
2. The substitution-point design shape is a per-template manifest file (`mimeo.template.json`) at the template repo's root, declaring one or more `{file, format, key or match, value}` entries, `value` templated with `{domain}`. Three format handlers cover the current template set: `js-key` (dotted-path key into a JS `export default {...}` object, e.g. `url` or `author.url`), `string-replace` (literal string match/replace, what `_customize_default_template` does today), `yaml-frontmatter-key` (a frontmatter key in a Markdown file). `deploy_site` reads the manifest post-generation if present and applies each substitution; no manifest present -> skipped, not an error, matching today's behavior for every template except mimeo.lol.

**Alternatives considered**:

- Token convention (every template writes `{{MIMEO_SITE_DOMAIN}}`, mimeo does a repo-wide find/replace): Simpler on mimeo's side, no manifest to parse, but doesn't fit the `js-key` case cleanly — `url: "https://orobia.net/"` isn't a token slot without either restructuring the template's own data file or falling back to fragile string matching against the placeholder URL anyway. Also requires every template author to know and apply the convention with no declared record of where they used it.
- mimeo-side per-template registry (mimeo hardcodes "for template X, the value lives at path Y"): What exists today for mimeo.lol, just generalized. Rejected because every new template requires a mimeo code change and release — the manifest's whole point is that a non-eleventy, non-mimeo-authored template costs mimeo nothing to support.
- Expand scope to general template parameterization (author name, social links, arbitrary branding fields): Rejected per scope decision 1 above — no mechanical substitution scheme turns "does this bio read as sufficiently generic" into a declared key/value; that's authoring judgment, done once per template, not once per domain.

**Consequences**: `_customize_default_template` is replaced by a manifest-driven dispatcher with three format handlers, used for every template that ships a manifest instead of only `mimeo.lol`. `laptopistan.com`'s hardcoded-HTML case becomes a manifest entry instead of a second special case in mimeo's code. The schema and handlers were implemented 2026-09-09 (see the addendum below, which ratifies the concrete schema and loosens the `js-key` resolution rule); every template gained its `mimeo.template.json` the same week. The eleventy-family rollout also drove a template cleanup in mimeo-sites: `author.url`/`author.email`/`feed.id` turned out to be read by no layout or config (only leaked into the Atom feed via whole-object pass-through) and were deleted, pamphlet's config now derives its feed base from `metadata.url`, and all `url:` placeholders were normalized to `https://example.com/` — leaving `metadata.js`'s `url` as the single site-identity key, so every eleventy manifest is one `js-key` entry (plus an `about.md` string-replace for the three literary templates).

**Addendum (2026-09-09): schema ratified; three open calls resolved.** A survey against the actual template files (`~/projects/mimeo-sites/TEMPLATES` — now 10 templates; `eleventy-product` and `eleventy-service` postdate the original survey of 8) settled the questions the decision left open:

1. **`js-key` kept, with a loosened resolution rule.** The original spec ("dotted-path key into a JS `export default {...}` object") does not cover pamphlet, whose self-reference lives in an `addPlugin(feedPlugin, {...})` options object in `eleventy.config.js`, not an `export default`. The handler instead resolves a dotted path against *any* object literal in the file: unkeyed braces (`export default {`, `return {`, function bodies, call arguments) are path-transparent; keyed openers (`author: {`) extend the path. The path must resolve to exactly one string-literal leaf — zero matches, multiple matches, or a non-string leaf are hard errors. A match-based alternative (drop `js-key`; string-replace the placeholder host) was considered and rejected on evidence: the templates' placeholders are three different `orobia.*` real-looking domains, per-template demo brands (`northlight.example.com`, `harborlight.example.com`), and `example.com` — mixed within single files — and `author@example.com` sits on a neighboring line of `metadata.js`, one careless host-substring pattern away from being rewritten. Set-by-key is indifferent to the current value, which is the point.
2. **Letter-spaced `<h1>` fixed in the template, not the schema.** mimeo.lol's `<h1>m i m e o . l o l</h1>` was the one value a `{domain}`-only grammar could not express. The template now ships plain `<h1>mimeo.lol</h1>` with CSS `letter-spacing` (mimeo-sites `17d308f`), so one `string-replace` entry covers both `<title>` and `<h1>` and the value grammar stays `{domain}`-only. No `{domain_spaced}` token.
3. **The manifest carries `version`.** Manifests live in template repos outside mimeo's release cadence; a future format change should fail with "unsupported manifest version" rather than field-level mysteries.

Ratified schema (`mimeo.template.json`, at the template repo root):

```json
{
  "version": 1,
  "dev_paths": ["README.md", "docs/", "CLAUDE.md"],
  "substitutions": [
    {"file": "index.html", "format": "string-replace",
     "match": "mimeo.lol", "value": "{domain}"},
    {"file": "content/_data/metadata.js", "format": "js-key",
     "key": "url", "value": "https://{domain}/"},
    {"file": "index.md", "format": "yaml-frontmatter-key",
     "key": "title", "value": "{domain}"}
  ]
}
```

Rules: `version` is required and must be `1`. `substitutions` is required and non-empty; each entry declares `file` (repo-relative path), `format` (`string-replace` | `js-key` | `yaml-frontmatter-key`), `value` (the literal token `{domain}` is the only templating; any other `{...}` in a value is a validation error), and `match` (string-replace) or `key` (the other two) per format — the wrong field for a format, an unknown field, or an unknown format is an error. `dev_paths` is optional: absent, the default `["README.md", "docs/", "CLAUDE.md"]` applies; present, it *replaces* the default entirely (no merging). A trailing `/` means a directory, matching `TEMPLATE_DEV_PATHS`' existing convention. The manifest file itself is always stripped from generated repos.

Semantics: `string-replace` does a literal (non-regex) replace of all occurrences; match absent from the file is an error (fail-loud against template drift), while a replace that yields the original content skips the write. `js-key` and `yaml-frontmatter-key` are set-by-key — they overwrite the value regardless of what is there, which makes them robust to whatever placeholder a template currently carries and safe to re-apply. `string-replace` is not re-appliable by construction (the match is consumed), but re-application cannot occur: `_apply_template_manifest` only ever runs on a freshly generated tree, since an existing repo without `--force` returns before the manifest step. All failures are loud: an unparseable manifest, an unresolvable key, a missing target file, or an unsupported version fails the deploy (`HostError`) rather than silently skipping — a declared manifest that quietly no-ops is exactly the misleading-outcome class the code review flags. Validation runs at fetch time, before any repository is created or mutated. The manifest is fetched from the *template* repo (fully populated, no empty-repo race); substitutions apply to the generated repo after the dev-file strip, carrying over `_customize_default_template`'s 5x2s read retry and grouping entries by file so one file is read and written once. Best-effort remains confined to the dev-path strip; substitution failures are fatal.

**Addendum (2026-09-11): `email` joins `url` as parameterized self-reference.** When eleventy-product and eleventy-service centralized their branding around `metadata.js` (mimeo-sites `fd7a898`/`38e9f1a`, prose follow-ons `37efa18`/`e469461`, Entry 59), the boundary question surfaced: is a contact address mimeo's business? The call: `email: "hello@{domain}"` is the same category as `url` — a mechanical, structurally-guaranteed function of the target domain, carrying no authoring judgment — so it sits inside this decision's scope, and both templates' manifests now carry a second `js-key` entry for it. Everything else from the centralization (palette pairs, prose interpolation, demo copy) is template authoring and stayed in mimeo-sites per the original scope ruling. No mimeo code changed: `js-key` with a `{domain}`-templated value already expressed the substitution; the schema and its rules are untouched.

---

### DEC-025: Collapse Nine Verbs to Five — Merge on Shared Write/Read Path, Not Surface Similarity (2026-09-08)

**Status**: Complete and merged to `main` (2026-09-09, merge commit `56d75bd`) — Stages 5A (`create` absorbs `template apply`), 5B (`status` absorbs `list`/`registrar list`/`dns show`/`dns check`), 5C (`sync` absorbs `dns repair`/`fix https`), and 5D (registration cleanup, full doc rewrite) are all implemented. Full task checklist in IMPLEMENTATION.md Phase 8 Stage 5. `template lint` was split out to its own Stage 6 (it validates DEC-024's manifest schema, not part of this verb-collapse); Stage 6 was subsequently dropped outright (2026-09-10, Entry 58) once DEC-024's deploy-time fail-loud validation made a standalone linter redundant for the fleet's size.

**Context**: DEC-021 (2026-07-06) built `status`/`sync` as declarative front doors but explicitly left `dns repair`, `fix https`, `list`, `registrar list`, `dns show`, `dns check`, `template apply` in place as separate verbs, deferring their fate ("alias vs deprecate — decided during Stage 3"). Stage 3 then resolved only two of them, keeping `dns repair` and `fix https` as "targeted scalpels rather than deprecated" — a decision made *for a reason*, not left open: at that time `sync` didn't wait for DNS propagation (a gap `repair` filled) and didn't auto-discover HTTPS-fixable repos (a gap `fix https` filled). `list`, `registrar list`, `dns show`, `dns check` were never revisited at all. Reviewing the full command surface (see Entry 44's atoms/composites map, and the discussion that followed it) found the remaining split isn't different operations — it's the same few write/read paths gated by which scope of domains and which subset of systems, expressed as separate verbs instead of flags. The test applied throughout: is this actually a different action, or the same action with a flag added? Every merge below passes that test the same way `create --force == template apply` does.

**Decision**: Collapse the CLI from nine top-level verbs (eleven counting dns/template/fix subcommands) to five:

1. `mimeo create DOMAIN [--template NAME] [--force] [--yes]` — absorbs `template apply`. `--force` on an existing repo does what `template apply` did (rename→generate→delete, DEC-022); `--yes` skips the confirmation prompt `template apply --force` used to require.
2. `mimeo status [DOMAIN... | --all] [--source github|porkbun|dns] [--with-dns] [--problems]` — absorbs `list`, `registrar list`, `dns show`, `dns check`. No `--source` = today's full cross-provider join. `--source github` = today's `list` (GitHub-only). `--source porkbun` = today's `registrar list`. `--source dns` = today's `dns show`/`dns check` (raw records vs. drift-only distinguished by `--problems`).
3. `mimeo sync [DOMAIN... | --all] [--reset-nameservers] [--dry-run]` — absorbs `dns repair` and `fix https`, **superseding** DEC-021 Stage 3's "keep as scalpels" call. Implemented in Stage 5C without a `--wait` flag: `dns repair`'s `verify_dns` propagation poll (10x/5s, ~50s) was dropped rather than recovered, for the same reason DEC-026 dropped it from `create` — it almost never observes real propagation and neither outcome changes what `sync` does next; `mimeo status` already exists to confirm propagation separately. `fix https`'s no-arg auto-discovery mode turned out to need no equivalent flag at all — see Open Question below, resolved during implementation.
4. `mimeo doctor` — unchanged. Local-environment checks are the one command that was never domain-state plumbing to begin with.
5. `mimeo template lint TEMPLATE` — new command, gated on DEC-024's manifest implementation landing first. Read-only manifest validation for template authors (does `mimeo.template.json` parse, do its `file`/`key`/`match` fields resolve against the actual template repo) with no domain argument and no writes. Not part of this collapse's critical path. *(Never built — dropped 2026-09-10 before implementation: deploy-time manifest validation already fails loud and names the entry at fault, so the linter only bought earlier drift discovery. Rationale in IMPLEMENTATION.md Phase 8 Stage 6 and Entry 58.)*

**Open question, resolved during Stage 5C implementation**: `fix https`'s no-arg mode auto-discovered fixable repos by calling `list_mimeo_repositories()` + `get_pages_health()` per repo and filtering to `health_status() == "fixable"`, then fixed only those. Option (a) from the original two candidates held: `sync`'s per-domain `_sync_domain` already calls the identical `get_pages_health()` + `health_status() == "fixable"` check as a normal step of every pass (`sync.py`, HTTPS-enable block) — verified directly against `fix.py`'s `_fix_one` before deleting it. `sync --all` (or `sync --all --dry-run` for a preview) already reproduces `fix https`'s discovery-and-fix behavior with no new flag; domains that aren't fixable simply report no action. No `--https-only` flag was added.

**Bug found post-merge via live testing (`002373.xyz`)**: `sync`'s pre-existing `_sync_domain` DNS step only ever inspected `PorkbunDNSProvider.check_dns_drift()`'s `missing` list, never its `status`/`extra` fields. `check_dns_drift` returns `status: "drift"` when there are extra (unmanaged) records but nothing missing — `status`'s DNS column already displayed this correctly (yellow `drift`, distinct from green `ok`) — but `sync --dry-run` silently reported `ok` for the same domain, because "no missing records" was the only condition it checked. This bug predates Stage 5C (`_sync_domain`'s DNS block is untouched by the `dns repair`/`fix https` merge; `dns repair` itself never called `check_dns_drift` at all, so it had no ok/drift distinction to get wrong), but went unnoticed until 5C made `sync` the natural next command to run after seeing `status` report drift, surfacing the inconsistency directly. Fixed in the same session: `sync` now sets `dns_status`/`extra` on the row and reports literally `"drift"` (matching `status`'s own term, not new sync-specific wording) instead of falling through to `"ok"`. No new flag, no behavior change to what `sync` acts on — it still never deletes extras, per this decision's own text above — only the reporting was wrong. Test: `test_extra_only_reports_drift_not_ok` in `tests/test_sync.py`.

**Alternatives considered**:

- Alias instead of deprecate (keep old command names as thin wrappers calling the new flag combinations, so old scripts keep working): Rejected — DEC-021 already tried "keep both" for `dns repair`/`fix https` and it didn't resolve the sprawl, it just delayed the decision. Nine verbs became eleven. Aliasing five more only grows the surface being explained rather than shrinking it. Pre-1.0, breaking changes are acceptable (see DEC-018's precedent for exactly this call).
- Leave `dns repair`/`fix https` split as DEC-021 Stage 3 decided: Rejected because the reasoning that justified the split (propagation-wait gap, auto-discovery gap) is closable with flags on `sync`, per this decision — reopening DEC-021's call is the point, not an oversight.
- Merge `doctor` into `status` too, for a fully unified surface: Rejected — `doctor` checks local tooling (Python version, `gh` auth, config validity), not domain state; forcing it under `status`'s domain-argument model would be fitting a shape rather than finding one.

**Consequences**: CLI drops from 9 top-level command groups to 5. `mimeo/cli/template.py`, `list_cmd.py`, `registrar.py`, `fix.py` are deleted; `dns.py` is deleted entirely once `show`/`check`/`repair` are absorbed (no subcommands remain). `create.py`, `status.py`, `sync.py` grow new flags but no new provider-layer code — every merge target already calls the same `mimeo/providers/host/github.py` and `mimeo/providers/registrar/porkbun.py` atoms the command it's replacing called (verified against source in Entry 44's session). Test files for the four deleted commands need their coverage relocated onto the surviving command's new flag combinations, not just deleted — this is the largest single piece of work in the plan. No changes to `_processing.py` or the provider layer.

### DEC-026: `create` Verifies Domain Ownership First and Never Touches DNS on an Unchanged Repo (2026-09-08)

**Status**: Active (Phase 8) — implemented as part of Stage 5A.

**Context**: Implementing Stage 5A (`create` absorbs `template apply`) surfaced two live incidents in the same session, both against real domains: (1) `mimeo create <domain-not-owned>` ran end-to-end — created a public GitHub repo, configured Pages, wrote a CNAME — for a domain not registered to this Porkbun account at all, with the only ownership-adjacent signal (`check_nameservers`) arriving after the repo already existed, as a warning, not a stop; `validate_domains` only checks string format, never registration. (2) `mimeo create <domain-with-existing-repo>` (no `--force`) correctly left the GitHub repo untouched, but still ran `PorkbunDNSProvider.configure_dns`, which deletes-then-recreates every matching DNS record unconditionally — so a plain `create` re-run against an already-deployed site silently rewrote its live DNS every time, with no `deploy.repo_created` check gating that step. Separately, `create`'s post-configure `verify_dns` poll (10 attempts x 5s, ~50s) almost never observes real propagation (which routinely takes minutes to hours) and neither outcome (verified / not-yet-propagated) changes anything `create` does next — it was blocking time spent confirming a fact `mimeo status` already exists to report.

**Decision**: Three changes to `_process_single_domain` in `mimeo/cli/create.py`:

1. Before any GitHub work, call `PorkbunRegistrar.domain_exists(domain)` (already existed at the provider layer, unused by `create`). If it returns `False`, raise `RegistrarError` immediately — no repo creation, no Pages config, no CNAME write, for that domain. Not gated by `--skip-dns`: this is an ownership check, not a DNS step.
2. After `deploy_site` returns, check `deploy.repo_created` before running the DNS-configure block at all. If the repo already existed and was not replaced (no `--force`), skip DNS configuration entirely — treat it like `--skip-dns` for that domain. DNS is now only touched on first creation or explicit `--force` replace.
3. Drop the `verify_dns` propagation poll from `create`. It now reports "DNS records created" and points to `mimeo status` for confirming propagation, rather than blocking ~50s for a check that rarely resolves and never changes behavior either way.

A fourth, related fix landed in the same session at the provider layer (`mimeo/providers/host/github.py`): a generated repo's `README.md` and everything under `docs/` — template-authoring documentation, not site content — is now deleted right after every fresh template generation (`_strip_template_dev_files`, best-effort). This was unrelated to the DNS/ownership issues but was found by inspecting the same live-repo content while chasing the domain-substitution question, and is the same class of problem: mimeo publishing something it should not.

**Alternatives considered**:

- Check ownership via `check_nameservers` (already called later in the flow) instead of adding a `domain_exists` call: Rejected — `check_nameservers` answers "do this domain's NS records point at Porkbun," which is a DNS-configuration question, not an ownership question; a domain can resolve NS to Porkbun-adjacent infrastructure without being registered in this account, and the existing code already treats an NS mismatch as a soft warning, which is the wrong severity for "you don't own this."
- Only skip DNS on existing-repo when `--skip-dns` is also implied automatically: Rejected as redundant — `deploy.repo_created` already carries the exact fact needed; no new flag required.
- Keep `verify_dns` but shrink the retry budget: Considered, rejected in favor of dropping it — even a short poll still blocks for a check whose result changes nothing `create` does, and `mimeo status` already exists as the place to check propagation/drift.

**Consequences**: `create` on a domain not owned in this Porkbun account now fails fast (`RegistrarError`, exit code 5, no side effects) instead of partially provisioning GitHub state for a domain the user doesn't control. `create` re-run against an already-deployed site is now a true no-op on DNS (matches its existing no-op behavior on the repo). `create` no longer blocks on DNS propagation; `dns_pending`/"DNS: Propagation pending" in the summary now also covers "skipped because repo already existed," which is consistent with its existing meaning ("DNS state not confirmed by this run"). Generated sites no longer publish template-authoring `README.md`/`docs/` as live site content. Two CLI tests were rewritten (dropped `verify_dns` assertions, added a repo-already-existed/DNS-skipped case) and one new CLI test class covers the ownership refusal; provider-layer tests for `_create_from_template` were updated to mock the new strip step, plus new unit tests for `_strip_template_dev_files`/`_delete_file`/`_delete_directory`. All changes verified live against real domains and repos in addition to the mocked test suite.

---

### DEC-027: Error Meaning Comes from Structured Status Codes, Not stderr Keywords (2026-09-12)

**Status**: Active (Phase 8) — implements `docs/CODE_REVIEW.md` rec #2; closes BUG 4 and BUG 7.

**Context**: Every GitHub operation is a `gh` subprocess, and failure meaning was recovered by substring-matching gh's stderr in four separate places: `"422"` for rename conflicts, `"404"` for template-manifest absence, `"certificate does not exist"` for HTTPS enforcement, and two gradually diverging transient-keyword tuples in `retry.py` and `_processing.py`. It worked because it was validated against live gh output once, but it is brittle across gh versions, and the damage was already visible in incidents: a 400 "Invalid cname" exited 5 ("transient"), inviting automation to retry a permanent failure; a `KeyError` from a provider response-shape change printed `[provider]` and exited 5 (BUG 4); `get_pages_health` mapped *any* `HostError` to `pages_configured: False`, so a network blip during a fleet sweep painted healthy sites as broken in `status` (BUG 7).

**Decision**: `HostError` carries a `status_code` (mirroring `APIError`), parsed from gh's `(HTTP NNN)` stderr in exactly one place (`_run_gh_command` in `github.py`); `_gh_api` preserves it through re-wrapping. All consumers branch on the code: `_rename_repository` (422 = retry once), the template-manifest fetch (404 = absent), the Pages GET probe and `get_pages_health` (404 = "no Pages"; anything else propagates), `retry_with_jitter` (`_RETRYABLE_STATUS_CODES` when a code exists), and `_categorize_error` (429 → exit 4, 5xx → 5, 401/403 → 3, any other code → exit 1 "provider", unexpected exception types → exit 1 "error" — the BUG 4 fix). Message keywords remain only as a fallback for code-less errors (network-level gh failures), via one shared tuple in `retry.py`. `enable_https_enforcement`'s "certificate does not exist" message check stays deliberately: it distinguishes *within* a status code, which structure cannot help.

**Alternatives considered**: Typed error subclasses per failure mode instead of a status code (rejected — heavier than needed; code + message covers every current call site); keep keyword matching and only fix the exit-code map (rejected — leaves the brittleness the review flagged as the root-cause shape behind BUGs 1 and 7).

**Consequences**: Exit-code contract change: only confirmed-transient failures exit 5; definitive provider failures (400/404/422, "gh not installed") exit 1. DEC-026's "ownership refusal exits 5" consequence is now exit 1 (`RegistrarError` with no code, unmatched) — DEC-026's behavior otherwise unchanged. `status` reports health-check failures as domain error rows ("couldn't check") instead of red SITE cells. Tests constructing 404-meaning `HostError`s must pass `status_code=404` explicitly — the parser lives in `_run_gh_command`, not the exception constructor.

---

### DEC-028: `create` Reports Created / Already-Existed / Failed as Distinct Outcomes (2026-09-12)

**Status**: Active (Phase 8).

**Context**: `create`'s recap equated "no error" with "created": a domain whose repo already existed (repo left unchanged, DNS skipped per DEC-026) was counted in "Successfully created: N/N domains" under a green check. Multi-domain runs suppress step logs, so the recap was the only view — `create a.com b.com` against two existing repos claimed "Created 2/2 domains" while creating nothing. Parallel runs also printed nothing between the `--force` confirmation and the recap (slow gh-bound deploys; silence reads as a hang), and "DNS: Propagation pending" rendered for repos whose DNS was *skipped*, not pending.

**Decision**: The result dict carries `created` / `repo_existed` / `dns_skipped` from the deploy. The headline counts only actual creations ("Created 0/2 domains (2 already existed)", "(N failed)" appended when present); the check glyph is reserved for creations; already-existed domains get a yellow warn block with the `--force` guidance; DNS lines state their reason ("not configured (repository already existed)" / "(--skip-dns)" / "pending nameserver fix (run 'mimeo sync')"); `--force` replacements say "Replaced existing repository". Parallel text runs print "Creating \<domain\>..." as each worker starts and one outcome line (check/warn/cross) as each completes. `--format csv` gains `created`/`repo_existed`/`dns_skipped` columns. The already-existed no-op keeps exit 0: nothing failed and the site is in its correct state — converged, like `mkdir -p` (flagged to the user during the session; honest text preferred over a nonzero code).

**Alternatives considered**: Nonzero exit for the no-op (rejected — breaks ensure-sites-exist scripting; the warn recap makes the no-op unmissable); full step logs in parallel mode (rejected — interleaved multi-thread logs are unreadable; start/outcome lines give liveness without the noise).

**Consequences**: Scripts parsing recap text or CSV see the trichotomy; exit-code consumers are unaffected (0 unchanged for success and no-op). Single-domain, `--sequential`, and dry-run output shapes are unchanged apart from the honest headline and DNS lines. Suite pins "Created 2/2" absent in both-existed runs and the progress lines present in parallel runs.

---

### DEC-029: Template Org and Default Template Are Config Settings (2026-09-21)

**Status**: Active (Phase 8).

**Context**: `TEMPLATE_ORG = "tepiton"` and `DEFAULT_TEMPLATE = "mimeo.lol"` were module constants in `providers/host/github.py`, while the destination org (where site repos are created) was already configurable (`github.default_org`). Templates and destinations effectively had to live in the same org, and the default template was frozen to a repo that has since been renamed on GitHub (`tepiton/mimeo.lol` → `tepiton/mimeo`). Extends the config-field side of the open D2 question (`default_registrar`/`default_host`).

**Decision**: Two new optional config settings with fallbacks: `github.template_org` (env `MIMEO_GITHUB_TEMPLATE_ORG`, default `tepiton`) and `defaults.template` (env `MIMEO_DEFAULT_TEMPLATE`, default `mimeo`), both type-validated. `GitHubHost` takes `template_org` as a constructor parameter (falling back to the constant); all template-repo API calls (validate, generate, manifest fetch) target `self.template_org`, independent of `default_org`. `create --template` resolves to `cfg.default_template` when the flag is omitted (`default=None` at the Click layer, resolved after config load). `DEFAULT_TEMPLATE` renamed to `"mimeo"` to match the renamed repo.

**Alternatives considered**: Keep both as constants (rejected — a per-deployment setting belongs in the config file, not a code edit); import the constants the other way, github.py ← config (rejected — providers must not grow a dependency on the config layer for two literal strings).

**Consequences**: One checkout can deploy from any template org to any destination org. `Config` imports the two constants from `providers.host.github` (no cycle: nothing under providers imports config). Tests asserting the `GitHubHost(...)` constructor contract gained the `template_org` kwarg; `--template`'s help text states the config-driven default. D2's remaining half — whether `default_registrar`/`default_host` stay as config fields or move behind a provider factory — is unaffected.

---

### DEC-030: `default_registrar`/`default_host` Config Fields Removed (2026-09-21)

**Status**: Active (Phase 8). Resolves D2 from `docs/CODE_REVIEW.md`.

**Context**: `Config` loaded `default_registrar`/`default_host` (`[defaults]` registrar/host) but every command instantiated `PorkbunRegistrar`/`GitHubHost` by name — the fields implied a provider factory that never existed. DEC-029 had just added config fields that *do* work (`template_org`, `default_template`), sharpening the contrast: a config option that does nothing is worse than no option, because it implies support.

**Decision**: Remove the fields. One registrar and one host exist, so a factory keyed on config would be a dict with a single entry; adding a provider is a code change (new class + wiring) regardless, at which point introducing a factory is trivial. Leftover `[defaults] registrar`/`host` keys in existing user configs are silently ignored — no breakage, no migration.

**Alternatives considered**: Wire the factory now (rejected — speculative generality: no second provider exists or is planned, and the abstraction tax would be paid for a dict with one entry); keep the fields as inert documentation (rejected — that is exactly the false advertising D2 flagged).

**Consequences**: `Config` no longer carries provider-selection state; provider choice is compile-time until a second provider ships. `config.toml.example`'s `[defaults]` section now documents only what it delivers (`template`, `ignore_domains`). Revisit the factory if a second registrar or host lands.

---

### DEC-031: `delete` Completes the Lifecycle as the Inverse of `create` (2026-09-29)

**Status**: Active (Phase 8). Implemented same day; the destructive primitives (`_delete_repository`, `_delete_record`) were already exercised by `create --force`, so the verb is the second half of `--force` without the rebuild.

**Context**: mimeo could make the domain-to-Pages promise (`create`), keep it (`sync`), and audit it (`status`), but unmaking it meant three web UIs — delete the repo, disable Pages, remove the Porkbun records. The immediate driver was repurposing scratch domains (`002371.xyz` & co.): the only CLI path was `create --force`, which obliterates and rebuilds in one step and cannot leave the domain dormant in between. Part of the command-model reconsideration that also produced `docs/SITE_ADDRESS.md` (proposed); passes the DEC-021 identity test — teardown is the fourth view of the one job.

**Decision**: A fifth verb, `mimeo delete [DOMAINS...]`, composable and confirmation-gated. Default is full teardown: delete the repository (Pages config and custom domain die with it — deleting the Pages config separately would be redundant) then remove exactly the managed DNS records (`required_dns_records()` matching by type + normalized name, including the ALIAS-at-apex parking record `configure_dns` would replace; unmanaged records are never touched). `--keep-repo` spares the repository and disables Pages instead — the recoverable half of the teardown, since `sync`/`create` can restore records and Pages trivially while repo deletion loses issues and history irrecoverably. Scope limits, deliberately: explicit domains only (no `--all` — fleet-wide deletion has no convergence floor under it the way `sync --all` does); registration and nameservers are never touched (Porkbun's API cannot deregister anyway, and the zone may outlive the site); host side first, and DNS cleanup only runs when the host stage succeeded (removing records under a live repo breaks a site the user asked to remove, which is a different, unrequested state). Repository deletion uses the REST endpoint (`DELETE /repos/{owner}/{repo}`) rather than `gh repo delete` so a missing repo surfaces as a structured 404 — a missing repo is reported and DNS cleanup still runs, since records can outlive repos. A domain absent from the Porkbun account gets repo/Pages teardown only, with a warning.

**Alternatives considered**: Granular `--dns`/`--pages`/`--repo` subset flags (rejected — only two coherent teardown modes exist, "everything" and "stop serving, keep the repo"; a second spelling adds combinatorial surface for no user); `--repo` opt-in with a dns+pages default (rejected — the scratch-domain workflow, the reason the verb exists, wants full teardown, and `--keep-repo` as the escape hatch keeps the irreversible-optimization argument); a `teardown` subcommand under `create` (rejected — DEC-025 already collapsed per-incident verbs into top-level lifecycle verbs).

**Consequences**: `delete` + `create` is the repurpose path; `create --force` remains the in-place replacement. Repo deletion needs the `delete_repo` token scope (same as `--force`) — a `doctor` check is a follow-up if other machines hit it. Under the proposed site-address model, teardown branches on zone presence exactly like create (a builtin site's teardown is repo-only) — no rework needed when that lands. Also fixed en passant: `tests/test_cli.py`'s autouse fixture now resets the `--log-format` global between tests; a `main --log-format json` invocation used to leak into later direct-command tests (existing create tests passed only by substring luck inside JSON records).

---

### DEC-032: `create` Sets the Repository Website Field; Homepage-Section Checkboxes Are Out of Scope (2026-09-29)

**Status**: Active (Phase 8). Prompted by the user hand-configuring `tepiton/amoxtli.dev` as the reference and asking mimeo to do it at create time.

**Context**: The repo's "Edit repository details" dialog has a Website field and, under "Include in the home page", checkboxes for Releases / Packages / Deployments and "Use your GitHub Pages website". A survey against the live API found the two halves have completely different automatability: the Website field is the standard `homepage` property (PATCH `/repos/{owner}/{repo}`), while the homepage-section checkboxes exist nowhere in the public API — absent from the REST OpenAPI spec (`repository-update` schema), from GraphQL `Repository` (only data connections: `releases`, `packages`, `deployments`), and from `UpdateRepositoryInput`; and an empirical PATCH with `has_releases`/`has_packages`/`has_deployments` on a scratch repo was silently ignored. They are frontend-only state; the GitHub community discussion requesting API access is the tracking thread.

**Decision**: `deploy_site` sets the repository Website field to `https://{domain}/` for every deploy (fresh, `--force` recreate, and the existed path — which already configures Pages settings and the custom domain, so presentation metadata is in keeping). The homepage-section checkboxes are deliberately not attempted; a `deploy` cannot toggle what no API exposes.

**Alternatives considered**: Drive the web UI (rejected — screen-scraping GitHub's frontend is exactly the fragility mimeo exists to avoid); re-check the API surface periodically (kept as a note, not code — revisit when GitHub ships fields; the probe method is recorded here and in Entry 71's chronicle).

**Consequences**: New and re-deployed sites get the site link in the About sidebar automatically; hiding the Releases/Packages/Deployments sections stays a per-repo manual click. One extra API call per deploy.

---

### DEC-033: Netlify Host Uses Netlify DNS — Nameserver Delegation (2026-10-02)

**Status**: Decided (Phase 8); implementation not scheduled. The full design is `docs/NETLIFY.md` (proposed).

**Context**: The Netlify design (Entries 72–75) offered two DNS modes. Mode A delegates the domain's nameservers to Netlify; mode B keeps DNS at Porkbun and points records at Netlify's load balancer. Mode B reuses all existing DNS code, has no nameserver-move risks, and was staged as the easier first pass. The user chose mode A: the reason to move the nameservers to Netlify is that Netlify then manages the DNS.

**Decision**: Netlify-hosted sites use Netlify DNS (mode A). `create` creates the zone, attaches the domain to the site (Netlify writes the apex/www records itself), then switches the domain's nameservers at Porkbun (`POST /domain/updateNameServers/{domain}`). Before switching, `create` prints the Porkbun-zone records that will stop being served and proceeds unless DNSSEC is enabled at Porkbun — the registry's DS records point at Porkbun's keys, and switching without updating them stops the whole domain resolving. Mode B is rejected and drops out of the staging. `delete` restores Porkbun's nameservers, amending DEC-031's "nameservers are never touched" for hosts that own the zone.

**Alternatives considered**: Mode B (rejected — leaves mimeo writing and checking DNS records, and certificate issuance waits on record propagation); mode B as a first pass with mode A later (rejected — a temporary path that would be partly discarded, and the goal is Netlify-managed DNS).

**Consequences**: The registrar work is in scope: `set_nameservers`, Netlify zone handling, and host-aware fleet checks (NETLIFY.md changes 4–5). Record-level drift checking does not apply to Netlify-hosted sites — drift is "NS still Netlify's, domain still attached." Unmanaged records left in the Porkbun zone are abandoned, not deleted; switching the NS back restores them. GitHub-hosted sites are unaffected: Porkbun DNS, unchanged.

---

## Superseded/Deprecated

[No superseded decisions yet]
### DEC-034: `create` Rejects Unflagged Template Repos Instead of Re-Flagging Them (2026-10-04)

**Status**: Active (Phase 8). Prompted by folio's retirement exposing the self-heal: `_ensure_is_template` PATCHed `is_template` back on any template repo lacking the flag, so unchecking the flag — the retirement mechanism — was silently undone by the next `create` that named the repo.

**Context**: The flag-set was added to avoid GitHub's confusing 404 from generate-from-template on an unflagged source repo. But the flag is the only offering switch mimeo respects: template selection is by name plus `is_template`, and mimeo hardcodes no template list. A tool that re-arms the switch the owner just threw off does not paper over a confusing error — it un-retires templates on the owner's behalf.

**Decision**: Reject instead of repair. `_ensure_is_template` is now `_require_is_template`: one GET, then a HostError ("may have been retired") if the flag is unset. `validate_template` — which `create` calls before any mutation — checks the same flag with the same message, so an unflagged name fails before the `--force` rename or any repository work begins.

**Alternatives considered**: Keep the self-heal and gate retirement on the archive alone (rejected — the uncheck-to-archive window re-arms the flag, and after archive the failure surfaces as a read-only PATCH error with no stated cause); a retire-list in mimeo config (rejected — the repo flag is the list; mimeo keeps no template registry).

**Consequences**: A template-org owner retires a template by unchecking one box; `create` naming it exits 1 with a clear message. Verified live against tepiton/eleventy-folio after retirement: exit 1, "may have been retired", nothing created. Generate-from-template on a repo whose owner merely forgot the flag now fails too — the message names the mechanism to fix.

---

### DEC-035: `sync` Converges DNS by Minimal Change; `create` Keeps Clear-and-Recreate (2026-10-26)

**Status**: Active (Phase 8) — closes `docs/CODE_REVIEW.md` D1. Implemented in Entry 86 (`4759f0c`).

**Context**: `sync` called `configure_dns` whenever any expected record was missing. `configure_dns` deletes every live record whose (type, name) is managed and recreates the full set, so one missing record churned the four correct apex A records and the `www` CNAME, and the action text ("apply 1 missing DNS record(s)") understated it. A wrong-target CNAME shows up in the drift check as both missing and extra, and a name can hold only one CNAME, so "create only what is missing" alone fails on that case.

**Decision**: `sync` plans per record (`plan_missing_records`) and then applies the plan (`apply_record_plan`). Records already correct are left alone. A live record is deleted only when it blocks one being added: a CNAME at the same name with a different target, or a parking ALIAS at the apex (Porkbun refuses A records beside it). Unrelated records (TXT, MX, other names) are never deleted, matching `sync`'s existing rule of not deleting records it does not manage. The plan step makes no API calls, so `--dry-run` reports exactly what would change. The text output reports "apply N missing" and "replace N" separately. `create` keeps `configure_dns`: on first provisioning, clearing conflicting records is the point.

**Alternatives considered**: Create-only with no deletes (rejected: fails on wrong-target CNAMEs, the common case once records drift). Delete every record that conflicts at a managed name, regardless of type (rejected: would delete user TXT records at `www`; wider than any observed failure).

**Consequences**: First live use (Entry 87) replaced `www` on 57 domains, one record each. Before this change, the same run would have rewritten five records per domain. `sync` now fetches live records once instead of twice.

---

### DEC-036: Pages IPs Stay Hardcoded; `doctor` Checks Them Against GitHub's List (2026-10-26)

**Status**: Active (Phase 8). Replaces the `docs/CODE_REVIEW.md` rec #6 item "fetch Pages IPs from `api.github.com/meta`". Implemented in Entry 85 (`1f19cbc`).

**Context**: mimeo writes `GITHUB_PAGES_IPS` (four IPv4 addresses) as apex A records. The risk is GitHub retiring an address while mimeo keeps writing it. As of 2026-10-26, the `pages` field of `api.github.com/meta` lists 10 entries: the four documented apex IPs, two legacy `192.30.252.153/154`, and four IPv6.

**Decision**: Keep the hardcoded list as the source of records. `mimeo doctor` gains a "Pages IPs" check: every hardcoded IP must appear in `meta`'s `pages` field (read via `gh api meta`). The check fails, naming the IP, when GitHub stops listing it.

**Alternatives considered**: Source the records from `meta` (rejected: adds the legacy IPs to every domain). Source them from `meta` and filter it (rejected: the filter is a hardcoded rule, so nothing is gained over the hardcoded list).

**Consequences**: Detection is manual, since it runs only when someone runs `doctor`. The `meta` list includes IPv6, but this decision does not cover AAAA records: mimeo writes none, and that question remains open.

---

### DEC-037: Porkbun Records Count Only When the Nameservers Are Porkbun's (2026-11-15)

**Status**: Active (Phase 8). Implemented in Entry 90.

**Context**: `status` read records from the Porkbun zone and treated them as live. blueberryhill.fyi and xhosi.com have Cloudflare nameservers, so their Porkbun records are not served, yet `status --source dns` printed them as the domain's DNS and `--problems` reported `DNS: ok`. The full view also counted non-Porkbun nameservers as "fixable with: mimeo sync", but sync skips those domains, and its only remedy (`--reset-nameservers`) would undo a deliberate move to Cloudflare. DNS for the fleet is moving to Cloudflare.

**Decision**: Every `status` view looks up the nameservers first. When they are Porkbun's, behavior is unchanged. Otherwise the Porkbun records are labelled not in use and are not compared: DNS status is `external` when another provider answers, `unknown` when the NS lookup returns nothing. Nameservers at another provider are not counted as a problem; an empty NS lookup is. Non-Porkbun nameservers are never counted as fixable by sync. The NS column shows `pb`, `ext` or `none`; `--source dns` JSON gains `nameservers` and `active`.

**Alternatives considered**: Check the records through public DNS (rejected for now: Cloudflare-proxied records resolve to Cloudflare IPs, so the check cannot confirm them). Read the Cloudflare zone (deferred to the 3.0 design, `docs/MIMEO3.md`).

**Consequences**: For domains on another DNS provider, `status` checks nothing about their records. A domain delegated somewhere by mistake no longer shows as a problem unless its site health shows it. `sync` is unchanged.

---

### DEC-038: The Redesign Ships as 2.0; SITE_ADDRESS.md Set Aside (2026-11-15)

**Status**: Active (Phase 8). User call.

**Context**: Entry 90 wrote the redesign notes as "mimeo 3.0" in `docs/MIMEO3.md`, but the current release is 1.3.0. `docs/SITE_ADDRESS.md` (proposed 2026-09) made a "site address" (`example.com`, `org.github.io`, `org.github.io/x`) the operand of every command and always created a repo, the opposite of the domain-first scope in the redesign notes.

**Decision**: The redesign ships as 2.0. The notes are renamed `docs/MIMEO2.md`; DEC-037 and Entry 90 refer to them by the old name. `docs/SITE_ADDRESS.md` is stale and is not an input to the 2.0 design; it stays in the repo for history.

**Alternatives considered**: 3.0 (rejected: skips a major version for no reason). Working SITE_ADDRESS.md's conflicts into the 2.0 notes (rejected: the user considers it stale).

**Consequences**: `docs/NETLIFY.md` still cites SITE_ADDRESS.md as a sibling that shares the repo/host split; that split stays a 2.0 question (MIMEO2.md question 3). Subdomain sites become 2.0 question 6.

---

### DEC-039: 2.0 Scope -- mimeo Connects a Domain to Its Host; `create` Stays as a Wrapper (2026-11-15)

**Status**: Active (Phase 8). User call, 2.0 design session.

**Context**: 1.x assumes Porkbun is registrar and DNS provider, GitHub Pages is the host, and every site repo is under one account. All three assumptions broke in Entry 90 (`docs/MIMEO2.md`, "Why Now"). The failures were all in the connection between a domain and its host: unserved Porkbun records reported as live, a site in another account shown as `no repo`, and mail records mimeo did not know about. Templates and content are already tracked in the tepiton meta-repo.

**Decision**: In 2.0, mimeo connects a domain to the host serving its site (nameservers, DNS records, the host's custom-domain setting, HTTPS) and keeps that connection correct. It adds no new site-creation features. `create` stays: it runs `delegate` if needed, the existing template repo creation, then `link`. The `is_template` rule (DEC-034) carries over unchanged.

**Alternatives considered**: Drop `create` and provision by hand with `delegate`, `gh repo create --template`, `link` (rejected: gives up the one-command path from domain name to running site).

**Consequences**: mimeo keeps its GitHub repo-creation code. `link` and `unlink` must work on a site that already exists in any account, so a site is no longer assumed to be the repo named after the domain under the configured account; how mimeo finds the site for a domain is decided separately (MIMEO2.md question 4).

---

### DEC-040: The Host's Custom-Domain Setting Records the Link; mimeo Caches It; Config Lists `organizations` (2026-11-15)

**Status**: Active (Phase 8). User call, 2.0 design session. Answers MIMEO2.md question 4.

**Context**: 1.x finds a domain's site by looking for a repo named after the domain under one configured account (`github_username`). gilborenstein.com is in `tepiton` and blueberryhill.fyi in `pborenstein`, so `status` shows them as `no repo`. Under DEC-039 a domain can be linked to any repo in any account, so the repo name no longer identifies the site.

**Decision**: A site belongs to a domain when the host's custom-domain setting names that domain (GitHub: the repo's Pages custom domain). That setting is the authority. mimeo keeps a cache of domain-to-site pairs at `~/.cache/mimeo/sites.json` so commands do not scan every time. The cache is never the authority: it can be deleted and rebuilt, and a command that uses a cached pair confirms it against the host before acting on it.

- Config gains `github.organizations`, a list of the GitHub organizations and user accounts mimeo scans. It replaces the single `github_username`. `github.default_org` still names where `create` and a bare `link` put a repo.
- `link`, `unlink` and `create` update the cache for the domain they act on.
- `mimeo scan` rebuilds the cache: it lists the repos in every listed organization and reads each one's custom domain.
- A single-domain command whose domain is missing from the cache, or whose cached repo no longer has that custom domain, tries `<organization>/<domain>` in each listed organization, then falls back to a scan.
- `status` reports two repos claiming one domain as a problem.
- `create` takes an optional `--repo owner/name`; the default stays `<default_org>/<domain>`.

**Alternatives considered**: No cache, scan on every command (rejected by the user: a fleet `status` would make one Pages API call per repo in every listed organization, including repos with no site). A registry that is the authority (rejected: it can disagree with the host's setting, the same kind of failure as the unserved Porkbun records in DEC-037).

**Consequences**: A site linked outside mimeo does not appear in fleet `status` until `mimeo scan` runs. The key is named `organizations` but also holds user accounts (`pborenstein`); GitHub lists repos for the two through different API endpoints, so the code must handle both. The cache holds repo names from every listed organization and lives outside the repo. Organizations and accounts are a GitHub notion, which is why the key sits under `github`; another host gets its own equivalent in its own config section.

---

### DEC-041: Registrar and DNS Provider Are Separate Interfaces; the Nameservers Pick the DNS Provider (2026-11-15)

**Status**: Active (Phase 8). User call, 2.0 design session. Answers MIMEO2.md question 5.

**Context**: 1.x treats Porkbun as registrar and DNS provider at once. DNS for the fleet is moving to Cloudflare while Porkbun stays the registrar, and some zones may stay on Porkbun DNS. Separating the two roles is one of the reasons for the redesign. `mimeo/providers/base.py` already has separate `Registrar` and `DNSProvider` base classes, both implemented by Porkbun; `DNSProvider` has one method (`configure_dns`) and `Registrar.update_nameservers` can only reset to Porkbun's nameservers.

**Decision**: The two stay separate interfaces.

- `Registrar` (Porkbun): list domains, read nameservers, set nameservers. `update_nameservers` takes the nameserver list to set.
- `DNSProvider` (Porkbun, Cloudflare): whether the zone exists, create the zone, the zone's nameservers, list records, add, change and delete a record.
- For any domain, mimeo reads the nameservers from the registrar and uses the configured DNS provider whose nameservers match. This extends DEC-037 from "Porkbun's or not" to "which provider". When no configured provider matches, DNS status is `external` as in DEC-037, and `link` and `sync` write no records.
- Config gains a `[cloudflare]` section holding an API token. `doctor` checks the credentials of every configured DNS provider.

**Alternatives considered**: One combined interface per vendor (rejected: Cloudflare would stub out the registrar half, and choosing a provider by nameserver needs the roles separate).

**Consequences**: Cloudflare is the first vendor implementing only `DNSProvider`. A second registrar is not designed for; `Registrar` has one implementation. Records at a provider the nameservers do not point to are never treated as live, by construction.

---

### DEC-042: `delegate` Copies Every Record Except NS and SOA, and Verifies Before Changing Nameservers (2026-11-15)

**Status**: Active (Phase 8). User call, 2.0 design session. Answers MIMEO2.md question 2.

**Context**: `delegate DOMAIN --dns PROVIDER` moves a zone to another DNS provider. A zone can hold records mimeo does not manage: xhosi.com has MX and SPF records for mail. Records that are not at the new provider when the nameservers change stop being served.

**Decision**: `delegate` copies every record from the provider currently serving the zone, except NS and SOA. Those two describe the provider itself (which servers answer for the zone, and the zone's bookkeeping), and each provider generates its own.

- Order: read all records from the current provider, create the zone at the new provider, write the records, read them back and compare, then set the nameservers at the registrar. A failed comparison stops before the nameserver change.
- The old zone's records are left in place. Under DEC-041 they are not treated as live, and switching back is one nameserver change.
- Copied records are written DNS-only, not proxied.
- `delegate` refuses to change nameservers while DNSSEC is enabled at the registrar. The registry's DS records point at the current provider's keys, so the switch would stop the domain resolving (the reasoning in `docs/NETLIFY.md`, open decision "Unmanaged records at the NS switch").
- `--dry-run` prints the records that would be copied.
- When the current nameservers match no configured provider, there is nothing to read. `delegate` creates the zone and leaves the nameservers alone unless given `--empty`.

**Alternatives considered**: Copy only the records mimeo manages and warn about the rest (rejected: mail breaks if the warning is missed).

**Consequences**: `DNSProvider` implementations must list and write every record type the fleet uses, not only A, AAAA and CNAME. Unverified (2026-11-15): Cloudflare may import records on its own when a zone is created through the API, as it does in the dashboard. If it does, `delegate` must reconcile with what Cloudflare put there; check Cloudflare's docs before implementing.

---

### DEC-043: `link` Writes DNS-Only Records and mimeo Leaves the Proxy Setting Alone (2026-11-15)

**Status**: Active (Phase 8). User call, 2.0 design session. Answers MIMEO2.md question 1.

**Context**: Each Cloudflare record has a proxy setting. With it off (DNS-only), the record resolves to the host's address and visitors connect to the host directly, as on Porkbun. With it on (proxied), the record resolves to Cloudflare's address and Cloudflare fetches the page from the host. blueberryhill.fyi and xhosi.com are proxied.

Checked 2026-11-15:

- [GitHub's docs](https://docs.github.com/en/pages/getting-started-with-github-pages/securing-your-github-pages-site-with-https) say a certificate can fail to generate when records are "not pointing to the IP addresses for GitHub Pages". They do not name Cloudflare; a proxied record resolves to Cloudflare's addresses.
- GitHub's Pages API reports xhosi.com's certificate as `bad_authz`, expiring 2026-12-12, and blueberryhill.fyi's as `approved`, expiring 2027-01-22.
- [Cloudflare's docs](https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/) say SSL mode Full does not check the host's certificate and Full (strict) requires it to be unexpired. The SSL mode of the two zones was not read.

**Decision**: `link` writes its records DNS-only. After that mimeo never changes a record's proxy setting: `status` and `sync` compare type, name and value, read through the provider's API, and a proxied record is not a problem. `status` shows the setting. There is no `--proxied` flag in 2.0; proxying is turned on in Cloudflare.

**Alternatives considered**: Proxied by default, with `link` writing DNS-only, waiting for the certificate and then turning proxying on, and `sync` repeating that for renewals (set aside by the user: decide from practice once domains are running this way). A `--proxied` flag (deferred with it).

**Consequences**: A domain that should be proxied needs one manual change in Cloudflare after `link`. mimeo does nothing about GitHub certificate renewal on proxied domains; xhosi.com's failed renewal is the first case to watch. This decision is expected to be revisited after live use.

---

### DEC-044: The Repo/Host Split Lands First, on 1.x (2026-11-15)

**Status**: Active (Phase 8). User call, 2.0 design session. Answers MIMEO2.md question 3.

**Context**: `GitHubHost` does repo work (create from template, manifest, dev-file strip, topics, delete, rename) and Pages work (enable Pages, custom domain, HTTPS enforcement, health). `docs/NETLIFY.md` change 1 moves the repo work to `providers/repo/github.py` with no behavior change. The 2.0 commands divide the same way: `link` and `unlink` use only the Pages work, and `create` is the repo work followed by `link` (DEC-039).

**Decision**: The split lands before any 2.0 work and ships as a 1.x release. It changes no behavior; the existing tests are the check.

**Alternatives considered**: Do the split as the first commits of 2.0 (rejected: mixes moved code with changed behavior, and leaves 1.x on a structure that differs from what follows).

**Consequences**: 2.0 starts from a codebase where the Pages host can be used without the repo code. The split is done whether or not Netlify is added.

---

### DEC-045: Subdomain Sites Are in 2.0 (2026-11-15)

**Status**: Active (Phase 8). User call, 2.0 design session. Answers MIMEO2.md question 6. Takes `docs/SUBDOMAINS.md` off ice; its design predates DEC-039 to DEC-041 and is input, not the plan.

**Context**: In 1.x one string is the site's hostname, the DNS zone, and the key matching repos to registrations. For `service.example.com` those differ: the zone is `example.com` and the record name is `service`, and one zone can hold several sites. Two of the three roles are already separated by this session's decisions: the matching key is the host's custom-domain setting (DEC-040), and DNS providers work on zones and records (DEC-041).

**Decision**: 2.0 commands take a hostname, and the zone is derived from it.

- The zone for a hostname is its longest suffix that is a domain at the registrar.
- `link service.example.com SITE` writes one record in the zone: CNAME `service` to the host's target (GitHub: `<owner>.github.io`). A subdomain site gets no `www` record.
- A site's records are the ones named for its hostname: for an apex site, the apex A/AAAA records and `www`; for a subdomain site, its one CNAME. `status`, `sync` and `unlink` read and change only those and leave every other record in the zone alone.
- `delegate` takes a zone. Given a subdomain it is an error.
- `create service.example.com` follows the same path; the repo defaults to `<default_org>/service.example.com`.

**Alternatives considered**: Write the interfaces with hostname and zone separate but defer the feature (rejected by the user in favor of doing it in 2.0).

**Consequences**: Tests must cover several sites in one zone, including `sync` and `unlink` on one site leaving the others' records intact. `sync` can no longer clear and rewrite a zone for any site; DEC-035's clear-and-recreate in `create` has to be narrowed to the site's own records.

---

### DEC-046: The 2.0 Design Is MIMEO2_DESIGN.md; Its Remaining Calls Were Made in One Pass (2026-11-15)

**Status**: Active (Phase 8). User call: after DEC-039 to DEC-045 the user asked for the rest of the design to be worked out without further questions, then for it to be built. Implemented in Entry 91.

**Context**: DEC-039 to DEC-045 answered scope and the six open questions in `docs/MIMEO2.md`. A buildable design needed more choices than those. `docs/MIMEO2_DESIGN.md` made them and lists each with its reason under "Calls Made Here".

**Decision**: `docs/MIMEO2_DESIGN.md` is the 2.0 design. The calls it adds:

- Every command runs one shared read (`Fleet.read`), one comparison (`compare`) and one apply. `status` prints the comparison's list of changes and `sync` applies it.
- `delete` stays, as `unlink` plus repository deletion. `unlink` never touches a repository.
- Config gains `defaults.dns`, the provider `create` and `delegate` put a zone at.
- mimeo owns the address records (A, AAAA, CNAME, ALIAS) at a site's own names: it adds the required ones that are missing and removes the others. Nothing else in a zone is touched.
- AAAA records are written at the apex. This closes the backlog item left open by DEC-036.
- Netlify is not in 2.0. Two open decisions in `docs/NETLIFY.md` ("unmanaged records at the NS switch", "where the host choice lives") are overtaken by DEC-042 and DEC-040 and get redone when Netlify is picked up.
- A version 1 config file loads unchanged, and mimeo then behaves as 1.x did.
- Cloudflare is called through the existing HTTP client; no SDK.

**Amends DEC-040**: a lookup that misses the cache runs a full scan only when the cache has never been filled by one, or when the caller is `delete`. Otherwise it tries `<organization>/<hostname>` and stops. DEC-040 said every miss falls back to a scan; a scan costs one API call per Pages repository, too much for each `status` of a domain with no site.

**Amends DEC-043**: a record mimeo adds takes the proxy setting already in use at its name, so adding a record does not change how the name is served. New names are still DNS-only.

**Alternatives considered**: Continuing question by question (ended by the user). Porting 1.x `status` and `sync` unchanged onto the new core before changing behavior (rejected: their `--source` views and Porkbun-only assumptions are what the redesign removes, so the port would have been written and then deleted).

**Consequences**: The 1.x command tests were replaced by tests that run the commands against in-memory providers. The first `sync --all` on 2.0 adds four AAAA records to every apex site at a configured provider. The Cloudflare provider and `delegate` have not been run against a live account; the vendor facts they rest on are listed as unverified in `docs/MIMEO2_DESIGN.md`. Other differences between the design text and the code are in that document's "As Built" section.

---

### DEC-047: A Proxied Name Is Not Asked for More A or AAAA Records (2026-11-16)

**Status**: Active (Phase 8). Found on the first live Cloudflare read (Entry 92). Narrows DEC-046's "AAAA records are written at the apex".

**Context**: 2.0 requires four A and four AAAA records at an apex. blueberryhill.fyi and xhosi.com each have four proxied A records and no AAAA records, so `status` showed both as `missing` and `sync` would have added four AAAA records to each. Cloudflare answers for a proxied name itself, over IPv4 and IPv6: both domains already resolve to Cloudflare AAAA addresses in public DNS with no AAAA record in the zone (observed 2026-11-14, `docs/MIMEO2.md`). The records behind a proxied name only tell Cloudflare where to fetch from.

**Decision**: When a name has at least one required address record that is proxied, `compare` does not report the name's other required A or AAAA records as missing. A name whose records are DNS-only is unchanged: all eight apex records are required. Extra address records are still removed either way.

**Alternatives considered**: Add the AAAA records proxied (rejected: eight records where four do the same job, and every proxied site would show as `missing` until synced). Have the host return different requirements for a proxied zone (rejected: the host does not know about proxying; the proxy setting is read from the DNS provider, and `plan.py` already reads it to follow DEC-043).

**Consequences**: A proxied apex with a single required A record passes as `ok`. If proxying is turned off on such a name, the next `status` shows the missing records and `sync` adds them.

---

### DEC-048: A Reported Problem Says What to Do, and `sync` Does It When It Can (2026-11-16)

**Status**: Active (Phase 8). User call, during the first live run of 2.0 (Entry 93).

**Context**: `status` printed `problem: certificate state is bad_authz, expires 2026-12-12`. The text is GitHub's state name. It does not say what is wrong for a visitor, and the steps that fix it were in `docs/IMPLEMENTATION.md`. mimeo has one user, who said a message must either offer the fix or give the steps, and must not send the reader elsewhere.

**Decision**:

- Every problem is a sentence about what is wrong, followed by what to do (`Plan.fixes`). The steps are built from what was read, so they name the hostname, the commands, the repository's settings page, and the records to change. Vendor state names stay in the JSON fields (`cert_state`) and out of the text.
- Steps are numbered when they are done in order and bulleted under `do one of:` when they are alternatives (`Plan.fixes_are_choices`).
- A site with no certificate, records that are right, and no proxied record gets a change, not a problem: `sync` removes the custom domain and sets it again, which is when GitHub requests a certificate. Verified 2026-11-16 on five sites. `sync` does not do this in the same run that writes records, because a record just written is not yet answered for (seen on Porkbun, Entry 93).
- A site whose hostname is not at the registrar is checked against public DNS. When DNS has no nameservers for it, the site is `no domain` and the choices are about the repository: `mimeo unlink`, `mimeo delete`, GitHub's transfer page, or registering the domain again. When the lookup cannot be made, nothing is concluded.

**Alternatives considered**: Have `sync` also do the proxied case (switch to DNS-only, wait for the certificate, switch back). Not done: it changes proxy settings, which DEC-043 rules out, and DEC-043 stands. For that case mimeo prints the steps. Prompting interactively inside `status` (rejected: `status` reads and `sync` writes; the offer is the `sync would:` line and the printed command).

**Consequences**: Removing and re-setting the custom domain takes the site off its hostname for the seconds between two API calls. If the second call fails the site has no custom domain, and the error gives the `mimeo link` command that restores it. The steps for the proxied case are unverified until they are carried out on xhosi.com. Narrows DEC-043's "mimeo does nothing about GitHub certificate renewal on proxied domains": it still changes nothing, and now says what to change.

---

### DEC-049: Requests to Porkbun Are Spaced 0.25 Seconds Apart (2026-11-16)

**Status**: Active (Phase 8).

**Context**: On 2026-11-16, three of five `status --all` runs over 109 hostnames lost one domain each to `HTTP 503 Service Temporarily Unavailable` from Porkbun's `dns/retrieve`. Five workers were sending requests with no spacing, and each request was retried three times over about 7 seconds. Whether Porkbun publishes a request limit is unverified.

**Decision**: Every Porkbun request from the process, from any worker and either client object, starts at least 0.25 seconds after the previous one. Retries go from three to five (waits of about 1, 2, 4, 8 and 16 seconds).

**Alternatives considered**: Fewer workers (rejected: the workers also serve GitHub and Cloudflare calls, which showed no failures). Longer retries alone (rejected: the other workers keep sending while one waits).

**Consequences**: `status --all` takes about 60 seconds for 109 hostnames. Three runs after the change had no failures; two runs before it were also clean, so this is not proof. The interval is a guess to revisit if 503s return.

---

### DEC-050: `sync` Switches the Proxy Off to Get a Certificate, Then Back On (2026-11-17)

**Status**: Active (Phase 8). User call. Supersedes the part of DEC-043 that says mimeo does nothing about certificate renewal on proxied domains, and the alternative DEC-048 set aside.

**Context**: DEC-043 left renewal behind Cloudflare's proxy to be decided "from practice once domains are running this way". The practice: xhosi.com's renewal failed (`bad_authz`); on 2026-11-17 the user did the seven steps DEC-048 made `status` print (records to DNS-only, custom domain removed and set again, wait, records back to proxied) and the certificate was issued. The user then asked why mimeo does not do that itself.

**Decision**: For a site with no certificate, a failed certificate, or an approved one within 14 days of expiry, whose records are right and in a zone mimeo can write:

- records not proxied: `sync` removes the custom domain and sets it again (as in DEC-048, now also for failed and expiring certificates);
- records proxied: `sync` switches the proxied records at the site's names to DNS-only, sets the custom domain again, looks at the certificate every 15 seconds for up to 15 minutes, sets the domain again if a request fails or three minutes pass, then switches the same records back to proxied and enforces HTTPS.

If a call fails during the sequence, the records are switched back before the error is raised. If the certificate does not arrive in 15 minutes, the records stay DNS-only, because switching them back would block the certificate again; the error names the records and says how to switch them back.

Everything else in DEC-043 stands: `link` writes DNS-only records, a proxied record is not a problem, and mimeo changes a proxy setting at no other time.

**Alternatives considered**: Keep printing the steps (rejected by the user: the tool knows the steps and has the access). Restore the proxy on timeout (rejected: it guarantees the certificate cannot arrive, and mimeo keeps no record that would let a later run finish the job).

**Consequences**: While the sequence runs, visitors reach GitHub directly and Cloudflare's rules for those names do not apply; with a valid certificate already in place the sequence took 22 seconds on 002370.xyz (2026-11-17). A timeout leaves a site unproxied until someone switches it back. `sync` has not yet repaired a failed renewal itself; blueberryhill.fyi near 2026-12-23 is the likely first case. mimeo keeps no memory that a site "should be" proxied; the sequence restores exactly the records that were proxied when it started.

---

### DEC-051: `delegate` Asks Before a Move That Would Stop a Service (2026-11-17)

**Status**: Active (Phase 8). User call.

**Context**: `mimeo delegate xhosi.com --dns porkbun --dry-run` listed sixteen records to copy and nothing else. Three of them are MX records pointing at Cloudflare Email Routing, which delivers mail only for zones Cloudflare serves. The copy would have been faithful and incoming mail would have stopped.

**Decision**: Each DNS provider can say what stops when a zone leaves it (`DNSProvider.stops_on_leaving`). `delegate` asks the current provider before changing anything. With something on the list, the command prints it and asks; `--yes` skips the question; `--dry-run` lists each item as `would stop:`. Called from code with no way to ask, `delegate` refuses (`WouldStopService`). `create` catches that, leaves the zone where it is, creates the site there, and prints the `delegate` command.

Known cases: Cloudflare MX records at `mx.cloudflare.net` (Email Routing); any proxied Cloudflare record; Porkbun MX records at `porkbun.com` (worded "may stop").

**Alternatives considered**: Refuse outright (rejected: the user may have moved mail first and want the move). Warn and proceed (rejected: the damage is silent and shows up as missing mail).

**Consequences**: The list is only what the providers' code knows about. Two of its three entries rest on unverified vendor behavior: Email Routing's dependence on Cloudflare serving the zone is from how the service is set up, and Porkbun's forwarding behavior was not checked at all (as of 2026-11-17). A service not on the list moves without a question.

---

### DEC-052: Porkbun Mail Is Not a Service `delegate` Warns About (2026-11-17)

**Status**: Active (Phase 8). Narrows DEC-051.

**Context**: DEC-051 listed three services a move could stop and marked two of its vendor facts unverified. Checked 2026-11-17:

- Cloudflare's [Email Routing docs](https://developers.cloudflare.com/email-routing/): "It is available to all Cloudflare customers using Cloudflare as an authoritative nameserver." The Email Routing warning stands.
- Porkbun's guide [How to use Porkbun email when your DNS is hosted elsewhere](https://kb.porkbun.com/article/47-how-to-use-porkbun-email-when-your-dns-is-hosted-elsewhere) says forwarding works with DNS elsewhere when the MX records point at `fwd1.porkbun.com` and `fwd2.porkbun.com`.

**Decision**: `PorkbunDNSProvider` reports nothing on leaving. `delegate` copies the MX records, so Porkbun forwarding keeps working after a move to Cloudflare.

**Alternatives considered**: Keep the warning worded "may" (rejected: it now contradicts the vendor's own documentation, and a question nobody needs to answer trains people to answer yes).

**Consequences**: Moving a Porkbun zone that uses Porkbun mail forwarding asks nothing. Porkbun's email hosting (as opposed to forwarding) was not looked at separately.


---

### DEC-053: Porkbun's Move to Cloudflare Is an Alternative to `delegate`; mimeo Does Not Use Its API (2026-11-22)

**Status**: Active (Phase 8). User question, answered without a code change.

**Context**: The user connected their Cloudflare account to Porkbun and asked whether Porkbun's move feature helps or hinders mimeo. Porkbun's guide [Move domains to Cloudflare](https://porkbun.com/llms/guides/move-domains-to-cloudflare) (read 2026-11-22) says Porkbun creates the zone in the connected Cloudflare account, copies the records it holds, and changes the nameservers at the registry. It is API-driven after a one-time browser consent, takes up to 500 domains per call, refuses domains with DNSSEC on, and creates records DNS-only. A domain can sit in `activating` (nameservers changed, Cloudflare zone not yet active) for up to 72 hours; the guide cites one that took 59. After the move Porkbun's `/dns/*` endpoints still accept writes, but they change only Porkbun's copy, not what resolves. Porkbun also offers record management on the Cloudflare zone through its own API (`/cloudflare/createRecord`, `setProxy` and others).

**Decision**: Either path can move a domain from Porkbun DNS to Cloudflare, and mimeo needs no change for one moved by Porkbun:

- mimeo picks the DNS provider from the nameservers (DEC-041), so a moved domain reads as Cloudflare once they change, the same as after `delegate`.
- Porkbun's records after the move are ignored, as any Porkbun records are when Porkbun's nameservers are not serving (DEC-037).
- mimeo sees the new zone only if its Cloudflare token covers it. A token scoped to "All Domains" (as TROUBLESHOOTING.md says to make it) does.

Use `delegate` when the read-back check matters: it compares the written records before changing the nameservers (DEC-042), and Porkbun's guide describes no such check and does not list which record types it copies. Use Porkbun's tool to move several domains at once, after looking at `/cloudflare/preview/{domain}`.

**Alternatives considered**: Have mimeo manage Cloudflare records through Porkbun's API and drop its own Cloudflare token (rejected: Cloudflare support would then work only for domains registered at Porkbun, against the registrar/DNS split in DEC-041). Have `delegate` call Porkbun's move API for the Porkbun-to-Cloudflare case (rejected: it would lose the read-back check and add a 72-hour asynchronous state for no gain on single domains).

**Consequences**: DEC-042's unverified question (whether Cloudflare imports records on its own when a zone is created through the API) is still open for `delegate`, and does not arise for a Porkbun move. During `activating`, `status` can show Cloudflare as the DNS provider while Cloudflare is not yet answering for the zone.
