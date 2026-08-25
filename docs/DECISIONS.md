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

## Superseded/Deprecated

[No superseded decisions yet]
