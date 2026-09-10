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

**Status**: Implemented in mimeo (Phase 8, 2026-09-09) — `mimeo/providers/host/template_manifest.py` plus `GitHubHost` wiring, per the schema addendum below. The templates' own `mimeo.template.json` files are pending follow-up work in mimeo-sites (mimeo.lol first); until a template ships one it deploys exactly as before, except mimeo.lol, which loses its hardcoded customization until its manifest lands (accepted window).

**Context**: `_customize_default_template` rewrites `mimeo.lol` -> `{domain}` in `index.html`, hardcoded to that one template, because `mimeo.lol` is itself a live site whose HTML hardcodes its own name. The open Phase 8 task ("template parameterization: pick a design shape") had drifted in scope during discussion toward general template authoring — bios, social handles, page copy, deciding what counts as "generic" identity (the concern behind Entry 43's mimeo-sites scrub). Re-examining mimeo's own identity shift (DEC-021: "fleet manager for domain-to-GitHub-Pages sites," not a site generator) surfaced that authoring judgment is a different tool's job; the piece that is legitimately mimeo's is narrow: when `foo.com` is deployed from a template, the template's boilerplate self-reference (its own name in `<title>`, `metadata.js`'s `url:`, frontmatter `title:`) should read `foo.com`, not the template's name. A survey of all 8 tepiton templates (extending Entry 42) found this single fact lives in three incompatible file formats: hardcoded HTML string (mimeo.lol, laptopistan.com), a JS object key (`content/_data/metadata.js` `url:`, used by the 5 eleventy-* templates), and YAML frontmatter (`index.md` `title:`, pandoc-simple).

**Decision**: Two scope decisions:

1. Mimeo's job is limited to propagating the target domain into a template's own declared self-reference point at deploy time — the same category as writing the DNS records or the Pages custom-domain field, not a general templating/content system. Template authoring (bios, tagline copy, what "generic" placeholder content looks like) stays out of mimeo; Entry 43's identity scrub correctly happened in mimeo-sites, not here, and future work of that kind belongs there too.
2. The substitution-point design shape is a per-template manifest file (`mimeo.template.json`) at the template repo's root, declaring one or more `{file, format, key or match, value}` entries, `value` templated with `{domain}`. Three format handlers cover the current template set: `js-key` (dotted-path key into a JS `export default {...}` object, e.g. `url` or `author.url`), `string-replace` (literal string match/replace, what `_customize_default_template` does today), `yaml-frontmatter-key` (a frontmatter key in a Markdown file). `deploy_site` reads the manifest post-generation if present and applies each substitution; no manifest present -> skipped, not an error, matching today's behavior for every template except mimeo.lol.

**Alternatives considered**:

- Token convention (every template writes `{{MIMEO_SITE_DOMAIN}}`, mimeo does a repo-wide find/replace): Simpler on mimeo's side, no manifest to parse, but doesn't fit the `js-key` case cleanly — `url: "https://orobia.net/"` isn't a token slot without either restructuring the template's own data file or falling back to fragile string matching against the placeholder URL anyway. Also requires every template author to know and apply the convention with no declared record of where they used it.
- mimeo-side per-template registry (mimeo hardcodes "for template X, the value lives at path Y"): What exists today for mimeo.lol, just generalized. Rejected because every new template requires a mimeo code change and release — the manifest's whole point is that a non-eleventy, non-mimeo-authored template costs mimeo nothing to support.
- Expand scope to general template parameterization (author name, social links, arbitrary branding fields): Rejected per scope decision 1 above — no mechanical substitution scheme turns "does this bio read as sufficiently generic" into a declared key/value; that's authoring judgment, done once per template, not once per domain.

**Consequences**: `_customize_default_template` is replaced by a manifest-driven dispatcher with three format handlers, used for every template that ships a manifest instead of only `mimeo.lol`. `laptopistan.com`'s hardcoded-HTML case becomes a manifest entry instead of a second special case in mimeo's code. The schema and handlers were implemented 2026-09-09 (see the addendum below, which ratifies the concrete schema and loosens the `js-key` resolution rule); existing templates (mimeo.lol first, since it's already relied on) still need a `mimeo.template.json` added, which is mimeo-sites work.

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

---

### DEC-025: Collapse Nine Verbs to Five — Merge on Shared Write/Read Path, Not Surface Similarity (2026-09-08)

**Status**: Complete and merged to `main` (2026-09-09, merge commit `56d75bd`) — Stages 5A (`create` absorbs `template apply`), 5B (`status` absorbs `list`/`registrar list`/`dns show`/`dns check`), 5C (`sync` absorbs `dns repair`/`fix https`), and 5D (registration cleanup, full doc rewrite) are all implemented. Full task checklist in IMPLEMENTATION.md Phase 8 Stage 5. `template lint` was split out to its own Stage 6 (it validates DEC-024's manifest schema, not part of this verb-collapse), blocked on DEC-024.

**Context**: DEC-021 (2026-07-06) built `status`/`sync` as declarative front doors but explicitly left `dns repair`, `fix https`, `list`, `registrar list`, `dns show`, `dns check`, `template apply` in place as separate verbs, deferring their fate ("alias vs deprecate — decided during Stage 3"). Stage 3 then resolved only two of them, keeping `dns repair` and `fix https` as "targeted scalpels rather than deprecated" — a decision made *for a reason*, not left open: at that time `sync` didn't wait for DNS propagation (a gap `repair` filled) and didn't auto-discover HTTPS-fixable repos (a gap `fix https` filled). `list`, `registrar list`, `dns show`, `dns check` were never revisited at all. Reviewing the full command surface (see Entry 44's atoms/composites map, and the discussion that followed it) found the remaining split isn't different operations — it's the same few write/read paths gated by which scope of domains and which subset of systems, expressed as separate verbs instead of flags. The test applied throughout: is this actually a different action, or the same action with a flag added? Every merge below passes that test the same way `create --force == template apply` does.

**Decision**: Collapse the CLI from nine top-level verbs (eleven counting dns/template/fix subcommands) to five:

1. `mimeo create DOMAIN [--template NAME] [--force] [--yes]` — absorbs `template apply`. `--force` on an existing repo does what `template apply` did (rename→generate→delete, DEC-022); `--yes` skips the confirmation prompt `template apply --force` used to require.
2. `mimeo status [DOMAIN... | --all] [--source github|porkbun|dns] [--with-dns] [--problems]` — absorbs `list`, `registrar list`, `dns show`, `dns check`. No `--source` = today's full cross-provider join. `--source github` = today's `list` (GitHub-only). `--source porkbun` = today's `registrar list`. `--source dns` = today's `dns show`/`dns check` (raw records vs. drift-only distinguished by `--problems`).
3. `mimeo sync [DOMAIN... | --all] [--reset-nameservers] [--dry-run]` — absorbs `dns repair` and `fix https`, **superseding** DEC-021 Stage 3's "keep as scalpels" call. Implemented in Stage 5C without a `--wait` flag: `dns repair`'s `verify_dns` propagation poll (10x/5s, ~50s) was dropped rather than recovered, for the same reason DEC-026 dropped it from `create` — it almost never observes real propagation and neither outcome changes what `sync` does next; `mimeo status` already exists to confirm propagation separately. `fix https`'s no-arg auto-discovery mode turned out to need no equivalent flag at all — see Open Question below, resolved during implementation.
4. `mimeo doctor` — unchanged. Local-environment checks are the one command that was never domain-state plumbing to begin with.
5. `mimeo template lint TEMPLATE` — new command, gated on DEC-024's manifest implementation landing first. Read-only manifest validation for template authors (does `mimeo.template.json` parse, do its `file`/`key`/`match` fields resolve against the actual template repo) with no domain argument and no writes. Not part of this collapse's critical path.

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

## Superseded/Deprecated

[No superseded decisions yet]
