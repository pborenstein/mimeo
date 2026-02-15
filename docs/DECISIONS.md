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

## Superseded/Deprecated

[No superseded decisions yet]
