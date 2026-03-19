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

## Superseded/Deprecated

[No superseded decisions yet]
