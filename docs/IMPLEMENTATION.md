# Mimeo Implementation Tracker

Living document tracking progress on the domain landing page provisioning tool.

**Last updated**: 2026-02-14

---

## Phase Overview

| Phase | Status | Description | Commits |
|-------|--------|-------------|---------|
| Phase 0: Research & Design | 🔄 In Progress | Project setup, API exploration, architecture design | Initial |
| Phase 1: Core CLI | 📋 Planned | CLI command structure, configuration management | - |
| Phase 2: Porkbun Integration | 📋 Planned | DNS configuration via Porkbun API | - |
| Phase 3: GitHub Pages Integration | 📋 Planned | Repository creation, Pages setup, workflow deployment | - |
| Phase 4: Content Templates | 📋 Planned | Template system for landing page generation | - |
| Phase 5: Polish & Testing | 📋 Planned | Error handling, testing, documentation | - |

---

## Current Phase

### Phase 0: Research & Design (2026-02-14 - Present)

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
- [ ] Review Porkbun API documentation for DNS management
- [ ] Review GitHub Pages documentation for custom domain setup
- [ ] Test Porkbun API authentication (requires API key)
- [ ] Test GitHub API for repository creation
- [ ] Document DNS record requirements for GitHub Pages

#### Architecture Design
- [ ] Design CLI command structure (mimeo <domain> --host --registrar --content)
- [ ] Design configuration file format for API credentials
- [ ] Design abstraction for registrar providers (future extensibility)
- [ ] Design abstraction for host providers (future extensibility)
- [ ] Design template system for content generation
- [ ] Document workflow sequence (registrar → host → verification)

#### Reference Implementation
- [ ] Study existing mimeo.lol setup
- [ ] Document DNS configuration currently in use
- [ ] Document GitHub Pages workflow currently in use
- [ ] Extract reusable patterns

**Next Steps**: Complete project initialization, then dive into API documentation and design the provider abstraction layer.

---

## Planned Phases

### Phase 1: Core CLI (Planned)

**Goal**: Implement basic CLI structure with configuration management.

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
