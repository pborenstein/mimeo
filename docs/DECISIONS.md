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

## Superseded/Deprecated

[No superseded decisions yet]
