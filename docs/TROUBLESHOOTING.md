# Troubleshooting

Run `mimeo doctor` first. It checks Python version, `gh` authentication, token scopes, and config file validity. Most failures surface clearly there before any API calls are made.

## Table of Contents

- [Configuration errors](#configuration-errors)
- [GitHub authentication](#github-authentication)
- [GitHub Pages deployment](#github-pages-deployment)
- [DNS configuration](#dns-configuration)
- [HTTPS and SSL certificates](#https-and-ssl-certificates)
- [Partial failures and re-runs](#partial-failures-and-re-runs)
- [Network and API errors](#network-and-api-errors)

---

## Configuration errors

### "Configuration file not found"

**Symptoms:**

- `Configuration error: Configuration file not found: /Users/<you>/.config/mimeo/config.toml`
- Error appears immediately when running any command

**Solutions:**

1. Create the config directory and file:
   ```bash
   mkdir -p ~/.config/mimeo
   cp config.toml.example ~/.config/mimeo/config.toml
   chmod 600 ~/.config/mimeo/config.toml
   ```

2. Edit `~/.config/mimeo/config.toml` with your credentials:
   ```toml
   [porkbun]
   api_key = "pk1_your_key_here"
   secret_key = "sk1_your_secret_here"

   [github]
   default_org = "your-github-username"
   ```

3. Alternatively, use environment variables:
   ```bash
   export MIMEO_PORKBUN_API_KEY="pk1_..."
   export MIMEO_PORKBUN_SECRET="sk1_..."
   export MIMEO_GITHUB_USERNAME="your-username"
   ```

### "Missing required configuration"

**Symptoms:**

- `ConfigurationError: Missing required configuration:`
- Lists specific missing fields

**Solutions:**

1. Check which fields are missing in the error message
2. Verify your config file uses the correct section names:
   ```toml
   [porkbun]        # not [providers.porkbun]
   api_key = "..."
   secret_key = "..."

   [github]         # not [providers.github]
   default_org = "..."
   ```

3. Check for typos in key names — `api_key` and `secret_key` (not `api_secret`)

---

## GitHub authentication

### "GitHub CLI (gh) is not installed"

**Symptoms:**

- `HostError: GitHub CLI (gh) is not installed. Install it from https://cli.github.com`

**Solutions:**

```bash
# macOS
brew install gh

# Verify
gh --version
```

### "GitHub CLI is not authenticated"

**Symptoms:**

- `HostError: GitHub CLI (gh) is not authenticated. Run 'gh auth login' first.`

**Solutions:**

```bash
gh auth login
```

Follow the prompts. Choose HTTPS and authenticate via browser.

### "workflow scope missing"

**Symptoms:**

- `mimeo doctor` reports `fail  workflow scope`
- `HostError: GitHub CLI command failed: refusing to allow...` when pushing
- Git push fails silently during `create`

**Cause:** The GitHub Actions workflow file (`.github/workflows/static.yml`) requires the `workflow` scope to push. Standard `repo` scope is insufficient.

**Solutions:**

```bash
gh auth login --scopes repo,workflow
```

Or re-authenticate and explicitly add the scope:

```bash
gh auth refresh --scopes workflow
```

Verify the scope is present:

```bash
gh auth status
# Should show: Token scopes: 'gist', 'read:org', 'repo', 'workflow'
```

---

## GitHub Pages deployment

### Repository created but Pages not serving

**Symptoms:**

- `create` succeeds
- `https://example.com` or `https://username.github.io/example.com` returns 404

**Cause:** GitHub Actions deployment takes 1-3 minutes after the initial push.

**Solutions:**

1. Wait 2-3 minutes and refresh
2. Check the Actions tab in the repository: `https://github.com/username/example.com/actions`
3. If the workflow failed, re-run via GitHub UI or:
   ```bash
   gh workflow run static.yml --repo username/example.com
   ```

### "GitHub CLI command failed: Not Found" during repository creation

**Symptoms:**

- Error during `create` referencing repository creation
- `HostError: GitHub CLI command failed: Not Found`

**Solutions:**

1. Verify your GitHub username matches `default_org` in config
2. Check you are authenticated as the correct user:
   ```bash
   gh api user --jq .login
   ```
3. If using an organization, ensure you have permission to create repositories

### Repository already exists but create fails

**Symptoms:**

- `create` fails after "Repository exists" log line

**Cause:** Existing repository may have a conflicting Pages or branch configuration.

**Solutions:**

Mimeo is idempotent — re-running `create` on an existing repo skips the push and only updates Pages settings. If it fails, check:

```bash
gh api repos/username/example.com/pages
```

If Pages is misconfigured, delete the repo and re-run `create`, or manually configure Pages via the GitHub web UI.

---

## DNS configuration

### "Porkbun API error: ..."

**Symptoms:**

- `RegistrarError: Porkbun API error: <message>`
- DNS configuration step fails

**Common causes and solutions:**

1. **Invalid credentials**: Verify `api_key` starts with `pk1_` and `secret_key` starts with `sk1_`
2. **API access not enabled**: Go to Porkbun account settings and enable API access for the domain
3. **Domain not in your account**: The domain must be registered in the Porkbun account matching your API credentials
4. **Wrong API endpoint**: The code uses `api-ipv4.porkbun.com` — do not change this; the standard endpoint returns 403 errors

Verify your credentials work:

```bash
uv run scripts/smoke_test_porkbun.py
```

### DNS records created but site still shows old content

**Symptoms:**

- Porkbun DNS configuration succeeds
- Browser shows old content or NXDOMAIN

**Cause:** DNS propagation takes time — typically 5-30 minutes, sometimes up to 48 hours depending on TTL and resolver caching.

**Solutions:**

1. Wait and check propagation:
   ```bash
   dig example.com A
   dig www.example.com CNAME
   ```

2. Expected A record values:
   ```
   185.199.108.153
   185.199.109.153
   185.199.110.153
   185.199.111.153
   ```

3. Expected www CNAME value:
   ```
   username.github.io
   ```

4. Use a propagation checker: https://www.whatsmydns.net/

### "DNS records created but not yet propagated"

**Symptoms:**

- `create` completes with warning: `DNS records created but not yet propagated`
- `dns_pending: True` in summary

This is normal behavior, not an error. The records were created successfully. DNS propagation takes time that Mimeo does not wait for. To repair DNS records without reprovisioning the entire site:

```bash
mimeo sync example.com
```

For nameserver mismatches, reset nameservers as part of the repair:

```bash
mimeo sync example.com --reset-nameservers
```

For full reprovisioning (repository, Pages, and DNS), re-run `mimeo create`.

### Conflicting DNS records

**Symptoms:**

- `RegistrarError: Porkbun API error: A record already exists`

**Cause:** Mimeo deletes conflicting records before creating new ones, but certain edge cases (ALIAS records coexisting with A records) may cause conflicts.

**Solutions:**

1. Manually inspect existing records:
   ```bash
   uv run scripts/smoke_test_porkbun.py
   ```

2. Remove conflicting records via the Porkbun web UI
3. Run `mimeo sync example.com` to fix DNS records without reprovisioning

---

## HTTPS and SSL certificates

### "HTTPS enforcement pending SSL certificate"

**Symptoms:**

- `create` completes with warning: `HTTPS enforcement pending SSL certificate`
- `https_pending: True` in summary
- Site is accessible via HTTP but HTTPS returns a certificate error

**Cause:** GitHub takes time to provision an SSL certificate for the custom domain. This is expected for new deployments. The certificate must reach the `approved` state before HTTPS can be enforced.

**Solutions:**

1. Wait 15-60 minutes for certificate provisioning
2. Check certificate status:
   ```bash
   mimeo status --all --source github --health
   ```
   Status will show `cert_pending` while the certificate is being issued, and `fixable` once it is approved.

3. Once `fixable`, enable HTTPS enforcement:
   ```bash
   mimeo sync --all
   ```

### "fixable" status but fix fails

**Symptoms:**

- `mimeo status --all --source github --health` shows `fixable`
- `mimeo sync` reports an error for the site

**Cause:** The certificate transitioned states between the health check and the fix attempt.

**Solutions:**

1. Re-run `mimeo sync` — the operation is safe to retry
2. If it persists, check the Pages configuration directly:
   ```bash
   gh api repos/username/example.com/pages --jq '{https_enforced, https_certificate}'
   ```

### Site accessible via HTTP but HTTPS shows wrong certificate

**Symptoms:**

- `https://example.com` shows a certificate for `github.io` instead of the custom domain

**Cause:** Custom domain is not set in the Pages configuration, or HTTPS enforcement is not enabled.

**Solutions:**

```bash
# Check current Pages configuration
gh api repos/username/example.com/pages

# Verify custom domain is set
gh api repos/username/example.com/pages --jq .cname
```

Re-run `mimeo create example.com` to reconfigure the custom domain and attempt HTTPS enforcement.

---

## Partial failures and re-runs

### Site deployed but DNS not configured

**Symptoms:**

- `create` shows "Site deployed but DNS not configured"
- `dns_pending: True` in summary
- `github.io` URL works but custom domain does not resolve

**Solutions:**

Re-run `mimeo create example.com`. The command is idempotent:

- Repository already exists: skips push
- Pages already configured: skips Pages setup
- DNS records: deletes and recreates (idempotent)

### Multiple domains: some failed, some succeeded

**Symptoms:**

- Bulk `create` with multiple domains reports partial success
- Summary shows some domains succeeded and some failed

**Solutions:**

1. Re-run only the failed domains:
   ```bash
   mimeo create failed-domain.com another-failed.org
   ```

2. Use `--stop-on-error` in future runs to halt at first failure

3. Use `--sequential` for better per-step output when debugging:
   ```bash
   mimeo create example.com --sequential
   ```

### Re-running create after partial failure

The `create` command is safe to re-run at any point. It checks for existing state:

- Existing repository: skips creation and push
- Existing Pages configuration: skips Pages setup
- Existing DNS records: deletes matching records and recreates them

For DNS-only issues, use `mimeo sync example.com` to fix records without touching the repository or Pages configuration. For nameserver mismatches, add `--reset-nameservers`.

The only non-idempotent behavior is the content push — it is skipped if the repository already exists. To update site content on an existing repository, push directly to the repository.

---

## Network and API errors

### "Failed to communicate with Porkbun API"

**Symptoms:**

- `RegistrarError: Failed to communicate with Porkbun API: <network error>`

**Solutions:**

1. Check network connectivity
2. Verify Porkbun API status: https://porkbun.com
3. The HTTP client retries automatically on 429, 500, 502, 503, 504 responses with exponential backoff. Persistent errors indicate a Porkbun outage or connectivity problem.

### "GitHub CLI command failed" with rate limit message

**Symptoms:**

- Error message references rate limiting
- Concurrent `create` with many domains

**Solutions:**

1. Use `--sequential` to reduce API call concurrency:
   ```bash
   mimeo create domain1.com domain2.com --sequential
   ```

2. Wait and retry — GitHub rate limits reset hourly

### Timeout during DNS verification

**Symptoms:**

- `create` hangs at "Verifying DNS propagation"
- Takes several minutes before completing

DNS verification polls up to 10 times with 5-second delays (up to 50 seconds). This is expected behavior when DNS is slow to propagate. The command will complete with `dns_pending: True` if verification times out — the records were still created successfully.
