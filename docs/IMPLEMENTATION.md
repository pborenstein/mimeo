# Mimeo Implementation Tracker

Living document tracking progress on the domain landing page provisioning tool.

**Last updated**: 2026-02-14

---

## Phase Overview

| Phase | Status | Description | Commits |
|-------|--------|-------------|---------|
| Phase 0: Research & Design | ✅ Complete | Project setup, API exploration, architecture design | Initial |
| Phase 1: Core Infrastructure | 🔵 Current | Configuration management, data models, provider abstractions | - |
| Phase 2: Porkbun Integration | 📋 Planned | DNS configuration via Porkbun API | - |
| Phase 3: GitHub Pages Integration | 📋 Planned | Repository creation, Pages setup, workflow deployment | - |
| Phase 4: Content Templates | 📋 Planned | Template system for landing page generation | - |
| Phase 5: Polish & Testing | 📋 Planned | Error handling, testing, documentation | - |

---

## Completed Phases

### Phase 0: Research & Design (2026-02-14 - 2026-02-14)

**Goal**: Establish project foundation, understand API requirements, design architecture for automating domain landing page provisioning.

**Context**: Starting with 70+ dormant domains. Initial implementation targets Porkbun (registrar) and GitHub Pages (host). Must be fully automated with no manual steps.

**Tasks**:

#### Project Setup
- [x] Initialize Python project structure with uv
- [x] Set up documentation system (CONTEXT.md, IMPLEMENTATION.md, DECISIONS.md)
- [x] Create basic CLI scaffold with Click
- [x] Configure development tools (pytest, mypy, ruff)
- [x] Set up virtual environment and verify CLI works
- [x] Verify tests pass (1/1 passing)

#### API Research
- [x] Review Porkbun API documentation for DNS management
- [x] Review GitHub Pages documentation for custom domain setup
- [x] Document DNS record requirements for GitHub Pages (4 A records + CNAME)
- [ ] Test Porkbun API authentication (requires API key)
- [ ] Test GitHub API for repository creation

#### Architecture Design
- [x] Design CLI command structure (mimeo provision <domain> with options)
- [x] Design configuration file format for API credentials (~/.config/mimeo/config.toml)
- [x] Design abstraction for registrar providers (Registrar ABC)
- [x] Design abstraction for host providers (Host ABC)
- [x] Design template system for content generation (minimal template)
- [x] Document workflow sequence (config → template → DNS → repo → deploy)
- [x] Create comprehensive implementation plan (docs/PLAN.md)

#### Reference Implementation
- [x] Study existing mimeo.lol setup
- [x] Document DNS configuration (GitHub Pages A records + CNAME)
- [x] Document GitHub Pages workflow (Actions deployment)
- [x] Extract reusable patterns (dark theme, letter spacing)

---

## Current Phase

### 🔵 Phase 1: Core Infrastructure (2026-02-14 - Present)

**Goal**: Configuration management, data models, and provider abstraction layer.

**Tasks**:

- [x] Add Phase 1 dependencies (requests, dnspython, pytest-mock, pytest-cov, responses)
- [x] Create mimeo/exceptions.py with error hierarchy
- [x] Create mimeo/models.py with Domain, DNSRecord, DeploymentConfig
- [x] Create mimeo/config.py with TOML loading and env var overrides
- [x] Create mimeo/providers/base.py with Registrar and Host ABCs
- [x] Write comprehensive tests (38 tests passing)
- [x] Verify type checking passes (mypy)
- [x] Verify linting passes (ruff)

**Success Criteria**: ✅ All criteria met

- Configuration loads API credentials from file and env vars
- Models validate domain names and DNS records
- Provider ABCs defined with clear interfaces
- All tests passing (38/38)
- Type checking passes
- Linting passes

**Next Steps**: Begin Phase 2 - Implement Porkbun API integration for DNS management.

---

## Planned Phases

### Phase 2: Porkbun Integration (Planned)

**Goal**: Automate DNS configuration via Porkbun API.

**Key deliverables**:

- CLI command parsing with Click
- Configuration file loading (API keys, defaults)
- Provider selection (--host, --registrar flags)
- Dry-run mode for safety
- Verbose logging support

### Phase 2: Porkbun Integration (Planned)

**Goal**: Automate DNS configuration via Porkbun API.

**Key deliverables**:

- Porkbun API client implementation
- DNS record creation for GitHub Pages (A and CNAME records)
- API error handling and retry logic
- Verification that DNS propagated correctly

**GitHub Pages DNS Requirements**:

- A records: 185.199.108.153, 185.199.109.153, 185.199.110.153, 185.199.111.153
- CNAME record: www → username.github.io

### Phase 3: GitHub Pages Integration (Planned)

**Goal**: Automate repository creation and GitHub Pages setup.

**Key deliverables**:

- GitHub API client (via gh CLI or PyGithub)
- Local repository creation in ./mimeo-sites/
- Remote repository creation on GitHub
- GitHub Pages workflow file generation
- Custom domain configuration in repository settings
- CNAME file creation

### Phase 4: Content Templates (Planned)

**Goal**: Implement template system for landing page generation.

**Key deliverables**:

- Template engine (Jinja2 or similar)
- "minimal" template (domain name displayed beautifully)
- Template variable substitution
- Static asset handling (CSS, fonts)
- Mobile-responsive design

### Phase 5: Polish & Testing (Planned)

**Goal**: Production-ready tool with comprehensive testing.

**Key deliverables**:

- End-to-end integration tests
- Error handling for all failure modes
- User-friendly error messages
- Progress indicators during provisioning
- Rollback capability for failed deployments
- Comprehensive README with examples

---

## Notes

**Reference Site**: mimeo.lol
- Website: https://mimeo.lol
- GitHub: pborenstein/mimeo.lol
- Use this as template for generated sites

**Design Principle**: Zero manual steps. Tool should go from "mimeo example.com" to live site without user intervention.

**Future Extensibility**: Design provider abstraction to support additional registrars (Namecheap, Cloudflare) and hosts (Netlify, Vercel) later.
