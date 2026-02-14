# Mimeo Implementation Plan

## Context

Mimeo addresses a common problem: 70+ domains sitting dormant because manual provisioning overhead (DNS setup, hosting configuration, page creation) creates too much friction. This tool automates the complete workflow via APIs—zero manual steps from domain name to live landing page.

**Current State**: Project initialized (Python 3.11+ with uv, Click CLI scaffold, test infrastructure, documentation system). Ready for implementation.

**User Intent**: Build a production-ready tool that can provision landing pages for all 57 Porkbun-managed domains (72% of portfolio) with a single command per domain, with future extensibility for other providers.

## Architecture

### Core Design Principles

1. **Provider Abstraction**: Separate interfaces for DNS providers (registrars) and hosting providers from day one
2. **Idempotency**: Safe to run commands multiple times without duplication
3. **Zero Manual Steps**: Everything automated via Porkbun and GitHub APIs
4. **CLI-First**: Scriptable for batch operations across dozens of domains
5. **Incremental**: Build in testable phases, each delivering standalone value

### Module Structure

```
mimeo/
├── config.py              # Configuration from ~/.config/mimeo/config.toml
├── models.py              # Domain, DNSRecord, DeploymentConfig models
├── exceptions.py          # MimeoError, ConfigurationError, ProviderError, etc.
├── providers/
│   ├── base.py            # Registrar and Host abstract base classes
│   ├── registrar/
│   │   └── porkbun.py     # Porkbun DNS API client
│   └── host/
│       └── github_pages.py # GitHub Pages deployment automation
├── templates/
│   └── minimal.py         # Minimal landing page (mimeo.lol style)
└── utils/
    ├── http.py            # HTTP client with retry logic
    └── git.py             # Git operations (init, commit, push)
```

## Implementation Phases

### Phase 1: Core Infrastructure (1-2 sessions)

**Goal**: Configuration management, data models, and provider abstraction layer.

**Files to Create**:

1. **`mimeo/config.py`** - Configuration system
   - Load from `~/.config/mimeo/config.toml`
   - Environment variable overrides (`MIMEO_PORKBUN_API_KEY`, etc.)
   - Validate required credentials exist
   - Default settings: workspace dir, default providers

   ```python
   class Config:
       workspace: Path  # ~/.mimeo/sites
       porkbun_api_key: str
       porkbun_secret: str
       github_username: str
       default_registrar: str = "porkbun"
       default_host: str = "github"
   ```

2. **`mimeo/models.py`** - Data models
   - `Domain`: domain name, TLD validation
   - `DNSRecord`: type, name, content, TTL
   - `DeploymentConfig`: registrar, host, template options
   - Use dataclasses or Pydantic for validation

3. **`mimeo/exceptions.py`** - Exception hierarchy
   - `MimeoError` (base)
   - `ConfigurationError`, `ProviderError`
   - `RegistrarError`, `HostError`, `DNSError`

4. **`mimeo/providers/base.py`** - Abstract interfaces
   ```python
   class Registrar(ABC):
       @abstractmethod
       def configure_dns(self, domain: str, records: List[DNSRecord]) -> None:
           """Configure DNS records for GitHub Pages"""

       @abstractmethod
       def verify_dns(self, domain: str, records: List[DNSRecord]) -> bool:
           """Verify DNS records propagated"""

   class Host(ABC):
       @abstractmethod
       def deploy_site(self, domain: str, content_path: Path) -> str:
           """Deploy site, return live URL"""

       @abstractmethod
       def configure_custom_domain(self, domain: str) -> None:
           """Configure custom domain in hosting settings"""
   ```

**Config File Format** (`~/.config/mimeo/config.toml`):
```toml
[mimeo]
workspace = "~/.mimeo/sites"

[providers.porkbun]
api_key = "pk1_..."
api_secret = "sk1_..."

[providers.github]
username = "pborenstein"
# Uses gh CLI auth, or set token = "ghp_..."
```

**Dependencies to Add**:
```toml
dependencies = [
    "click>=8.0",      # Already added
    "requests>=2.31",  # HTTP client for Porkbun API
    "dnspython>=2.4",  # DNS verification
]
```

**Tests**:
- Config loading from file and env vars
- Model validation (valid/invalid domains)
- Provider registry lookup

**Success Criteria**:
- Configuration loads API credentials correctly
- Models validate domain names
- Provider ABCs defined and documented

---

### Phase 2: Porkbun DNS Integration (2-3 sessions)

**Goal**: Automate DNS configuration for GitHub Pages via Porkbun API.

**Files to Create**:

1. **`mimeo/providers/registrar/porkbun.py`** - Porkbun API client
   - Base URL: `https://api.porkbun.com/api/json/v3/`
   - Auth: Include API key/secret in request body
   - Key methods:
     - `create_record(domain, type, name, content, ttl=600)`
     - `get_record(domain, type, name)`
     - `update_record_if_needed()` (idempotency)

   **GitHub Pages DNS Requirements**:
   - 4 A records (apex domain) → GitHub IPs:
     - 185.199.108.153
     - 185.199.109.153
     - 185.199.110.153
     - 185.199.111.153
   - 1 CNAME record: `www` → `{username}.github.io`
   - TTL: 600 seconds (minimum)

2. **`mimeo/utils/http.py`** - HTTP utilities
   - Retry with exponential backoff
   - Rate limit handling
   - Error response parsing

**API Integration Details**:

Create DNS record:
```
POST /dns/create/{domain}
Body: {
  "apikey": "pk1_...",
  "secretapikey": "sk1_...",
  "name": "www",
  "type": "CNAME",
  "content": "pborenstein.github.io",
  "ttl": 600
}
```

Check existing record:
```
POST /dns/retrieveByNameType/{domain}/{type}/{subdomain}
```

**Idempotency Strategy**:
1. Query existing records first
2. If record exists with correct content: skip
3. If record exists with wrong content: update
4. If record doesn't exist: create

**DNS Verification**:
- Use `dnspython` to query DNS after creation
- Poll with timeout (5 minutes default, configurable)
- Handle propagation delays gracefully

**Tests**:
- Mock Porkbun API responses
- Test A record creation (4 records)
- Test CNAME record creation
- Test idempotency (don't duplicate)
- Test error handling (auth failure, rate limits)

**Success Criteria**:
- Can create all GitHub Pages DNS records via API
- DNS verification detects when propagation completes
- Idempotent (safe to re-run)

---

### Phase 3: GitHub Pages Integration (3-4 sessions)

**Goal**: Automate repository creation and GitHub Pages deployment.

**Files to Create**:

1. **`mimeo/providers/host/github_pages.py`** - GitHub automation
   - Strategy: Use `gh` CLI (already available, handles auth)
   - Fallback: Can add PyGithub library later

   **Workflow**:
   1. Create local repo in `~/.mimeo/sites/{domain}/`
   2. Generate index.html from template
   3. Create CNAME file with domain name
   4. Create `.github/workflows/pages.yml` workflow
   5. Initialize git, commit files
   6. Create remote repo: `gh repo create {domain} --public`
   7. Push to main branch
   8. Configure Pages settings (CNAME auto-detected)
   9. Poll for deployment completion

2. **`mimeo/utils/git.py`** - Git operations
   - Initialize repository
   - Create commits with proper messages
   - Add remote origin
   - Push to remote
   - Use subprocess for git commands (or gitpython library)

**GitHub Actions Workflow** (`.github/workflows/pages.yml`):
```yaml
name: Deploy to GitHub Pages

on:
  push:
    branches: [main]

permissions:
  contents: read
  pages: write
  id-token: write

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/configure-pages@v4
      - uses: actions/upload-pages-artifact@v3
        with:
          path: '.'
      - uses: actions/deploy-pages@v4
```

**Repository Structure**:
```
{domain}/
├── index.html           # Landing page
├── CNAME                # Custom domain (e.g., "example.com")
└── .github/
    └── workflows/
        └── pages.yml    # Deployment workflow
```

**gh CLI Commands**:
```bash
# Create repository
gh repo create {domain} --public --description "Landing page for {domain}"

# Check if repo exists
gh repo view {domain} 2>/dev/null || echo "not found"

# Get Pages deployment status
gh api repos/{owner}/{repo}/pages
```

**Deployment Verification**:
- Poll GitHub API for Pages build status
- Wait for "built" status (timeout: 10 minutes)
- Verify site responds at `https://{domain}`

**Tests**:
- Mock git subprocess calls
- Mock gh CLI subprocess calls
- Test workflow file generation
- Test idempotency (don't recreate existing repos)

**Success Criteria**:
- Can create GitHub repository via gh CLI
- Can push content with workflow file
- Pages deployment succeeds
- Site is live at custom domain

---

### Phase 4: Template System (1-2 sessions)

**Goal**: Generate landing page HTML from templates.

**Files to Create**:

1. **`mimeo/templates/minimal.py`** - Minimal template
   - Based on mimeo.lol reference design
   - Single HTML file with embedded CSS
   - No external dependencies or build process

   **Template Design** (from mimeo.lol):
   ```html
   <!DOCTYPE html>
   <html>
   <head>
       <meta charset="UTF-8">
       <title>{domain}</title>
       <style>
           body {
               background: #1a1a1a;
               color: #e0e0e0;
               display: flex;
               justify-content: center;
               align-items: center;
               height: 100vh;
               margin: 0;
               font-family: sans-serif;
           }
           h1 {
               font-size: 3em;
               letter-spacing: 0.1em;
           }
       </style>
   </head>
   <body>
       <h1>{spaced_domain}</h1>
   </body>
   </html>
   ```

   **Features**:
   - Dark theme: #1a1a1a background, #e0e0e0 text
   - Centered flexbox layout
   - Domain name with letter spacing (e.g., "m i m e o . l o l")
   - Responsive (works on all screen sizes)

2. **Template Implementation**:
   - Simple string substitution (no need for Jinja2 initially)
   - Variables: `{domain}`, `{spaced_domain}`
   - Future: Add more templates (card, splash, etc.)

**Tests**:
- Test HTML generation
- Verify letter spacing formatting
- Test with various domain names

**Success Criteria**:
- Generates valid HTML matching mimeo.lol design
- Letter spacing works correctly
- Dark theme renders properly

---

### Phase 5: CLI Orchestration (2-3 sessions)

**Goal**: Wire up complete workflow in CLI command.

**Files to Modify**:

1. **`mimeo/cli.py`** - Expand CLI with provision command
   ```bash
   mimeo provision <domain> [OPTIONS]
   ```

   **Options**:
   - `--registrar` (default: porkbun)
   - `--host` (default: github)
   - `--template` (default: minimal)
   - `--dry-run`: Show what would happen without executing
   - `--verbose`: Detailed logging
   - `--force`: Overwrite existing deployment
   - `--no-verify`: Skip DNS verification

   **Workflow Orchestration**:
   1. Load configuration
   2. Validate domain name
   3. Check domain uses Porkbun nameservers (filter from CSV)
   4. Generate landing page from template
   5. Create local repository
   6. Configure DNS via Porkbun API (4 A records + CNAME)
   7. Verify DNS propagation (poll with timeout)
   8. Create GitHub repository
   9. Push content with workflow
   10. Wait for Pages deployment
   11. Verify site is live
   12. Print success message with URL

   **Progress Indication**:
   ```
   ✓ Configuration loaded
   ✓ Domain validated: example.com
   ✓ Generated landing page from minimal template
   ⏳ Configuring DNS records...
     ✓ Created A record → 185.199.108.153
     ✓ Created A record → 185.199.109.153
     ✓ Created A record → 185.199.110.153
     ✓ Created A record → 185.199.111.153
     ✓ Created CNAME record: www → pborenstein.github.io
   ⏳ Waiting for DNS propagation... (may take up to 5 minutes)
   ✓ DNS records verified
   ✓ Created GitHub repository: example.com
   ✓ Pushed content to main branch
   ⏳ Waiting for Pages deployment...
   ✓ Site deployed successfully

   🎉 Landing page live at: https://example.com
   ```

**Error Handling**:
- Catch `ConfigurationError`: Show config file path, missing credentials
- Catch `RegistrarError`: Porkbun API failures, auth errors
- Catch `HostError`: GitHub failures, repo conflicts
- Catch `DNSError`: Propagation timeout, verification failures
- Clear messages with remediation steps
- Proper exit codes (0=success, 1=error)

**Additional Commands** (future):
```bash
mimeo list                    # List deployed sites
mimeo verify <domain>         # Check DNS and deployment status
mimeo remove <domain>         # Remove deployment
```

**Tests**:
- Integration tests with all mocked APIs
- CLI command tests (Click test runner)
- Error handling tests for each failure mode

**Success Criteria**:
- `mimeo provision example.com` works end-to-end
- Progress indication is clear and informative
- Errors display helpful messages
- Dry-run mode shows what would happen

---

### Phase 6: Production Readiness (2-3 sessions)

**Goal**: Polish for production use with all 57 Porkbun domains.

**Enhancements**:

1. **Domain Filtering** (from `data/porkbun-domains.csv`)
   - Read CSV to get domain list
   - Filter by nameserver: only "ns.porkbun.com" domains
   - 57 domains eligible (72% of portfolio)
   - Reject domains with external nameservers (NSOne, Cloudflare, Google)

2. **Batch Operations**
   ```bash
   # Provision all Porkbun-managed domains
   mimeo batch --filter-ns porkbun --template minimal --dry-run

   # Provision from file
   mimeo batch --domains domains.txt
   ```

   **Features**:
   - Process domains in sequence (avoid rate limits)
   - Continue on individual failures
   - Summary report at end
   - Throttling between requests

3. **Enhanced Error Handling**
   - DNS propagation timeout → Clear message about wait time
   - GitHub rate limits → Exponential backoff with retry
   - Domain not in Porkbun → Error with explanation
   - External nameservers → Error message, suggest changing NS
   - Repository exists → Idempotent handling or --force flag

4. **Comprehensive Testing**
   - End-to-end integration test with mocks
   - Test all error paths
   - Coverage target: >80%
   - Manual testing with real APIs (1-2 test domains)

5. **Documentation**
   - Update README with usage examples
   - API credential setup guide (Porkbun + GitHub)
   - Troubleshooting section (common errors)
   - Architecture documentation
   - Batch operation guide

**Success Criteria**:
- Can provision all 57 eligible domains
- Batch operations work reliably
- Error messages guide users to solutions
- Documentation covers all use cases
- Ready for production use

---

## Critical Files (Implementation Order)

1. **`mimeo/config.py`** - Foundation for all API interactions
2. **`mimeo/providers/base.py`** - Defines interfaces for extensibility
3. **`mimeo/providers/registrar/porkbun.py`** - DNS automation (core workflow)
4. **`mimeo/providers/host/github_pages.py`** - Hosting automation (core workflow)
5. **`mimeo/templates/minimal.py`** - Content generation
6. **`mimeo/cli.py`** - Orchestration (ties everything together)

---

## Verification Strategy

**After Each Phase**:
1. Run `uv run pytest` - All tests pass
2. Run `uv run mypy mimeo` - Type checking passes
3. Run `uv run ruff check mimeo` - Linting passes

**End-to-End Verification** (Phase 5+):
1. Set up test domain with Porkbun nameservers
2. Run: `uv run mimeo provision test-domain.com --dry-run`
3. Verify plan looks correct
4. Run: `uv run mimeo provision test-domain.com`
5. Verify DNS records created in Porkbun dashboard
6. Verify GitHub repo created
7. Verify site live at https://test-domain.com
8. Verify HTTPS certificate issued
9. Test idempotency: run same command again, should succeed without duplication

**Production Verification** (Phase 6):
1. Choose 1-2 real domains from portfolio
2. Run provision command
3. Verify complete workflow
4. Document any issues encountered
5. Fix issues, then proceed with batch operations

---

## Dependencies Summary

**Add to `pyproject.toml`**:
```toml
dependencies = [
    "click>=8.0",      # CLI (already present)
    "requests>=2.31",  # Porkbun API
    "dnspython>=2.4",  # DNS verification
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",       # Already present
    "mypy>=1.6.0",         # Already present
    "ruff>=0.1.0",         # Already present
    "pytest-mock>=3.12",   # Mocking
    "pytest-cov>=4.1",     # Coverage
    "responses>=0.24",     # HTTP mocking
]
```

---

## API References

**Porkbun API**: https://porkbun.com/api/json/v3/documentation
- DNS record creation, retrieval, updates
- Authentication via API key/secret in request body

**GitHub Pages**: https://docs.github.com/en/pages
- Custom domain configuration
- DNS requirements (A records + CNAME)
- Deployment via GitHub Actions

**Reference Implementation**: https://github.com/pborenstein/mimeo.lol
- Minimal landing page design
- GitHub Actions workflow
- CNAME configuration

---

## Workspace Layout

```
~/.mimeo/
├── config.toml              # User configuration
├── logs/
│   └── mimeo.log           # Application logs
└── sites/
    ├── example.com/         # Local git repo
    │   ├── index.html
    │   ├── CNAME
    │   └── .github/workflows/pages.yml
    ├── another-domain.com/
    └── ...
```

---

## Risk Mitigation

**DNS Propagation**: Poll with timeout, clear progress messages, `--no-verify` option to skip

**GitHub Rate Limits**: Exponential backoff, throttle batch operations, respect API headers

**API Auth Failures**: Validate credentials before operations, clear error messages

**Repository Conflicts**: Check existence first, idempotent handling, `--force` option

**Domain Eligibility**: Filter by nameserver, reject external DNS with helpful message

---

## Success Metrics

**Phase Completion**:
- Phase 1: Config and models working
- Phase 2: DNS records created via Porkbun API
- Phase 3: GitHub repos deployed with Pages
- Phase 4: Landing pages generated from template
- Phase 5: End-to-end workflow functional
- Phase 6: Production-ready for all 57 domains

**Final Success**:
- ✅ Single command provisions complete landing page
- ✅ Zero manual steps required
- ✅ Works for all 57 Porkbun-managed domains
- ✅ Idempotent and safe to re-run
- ✅ Clear error messages guide users
- ✅ Extensible for future providers/templates
