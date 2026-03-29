# Mimeo Code Review

A critical, user-perspective review of the mimeo codebase (v0.1.0).

**Date**: 2026-03-28
**Scope**: All source in `mimeo/`, all tests in `tests/`, documentation, and README.
**Stats**: ~2,700 lines of source (excluding init files), 244 tests passing, clean ruff + mypy.

---

## Executive Summary

Mimeo does one thing -- take a domain from nothing to a live GitHub Pages site with Porkbun DNS -- and it does it well enough to be useful. The architecture is clean, the provider abstractions are sensible, and the test suite is thorough.

But the polish has gaps that a user will hit. Some are real bugs (documented flags that don't exist, env var name mismatches). Some are design issues that will hurt as the tool grows (CLI code reaching into private provider methods, no domain validation despite a Domain model existing). And some are user-hostile defaults (no progress during DNS propagation, silent partial failures, noisy stdout that breaks piping).

The codebase is in good shape for a v0.1.0. The issues below are ranked by severity.

---

## Critical Issues

### 1. README documents a flag that doesn't exist

The README lists:

```
mimeo create example.com --force-dns-update
```

There is no `--force-dns-update` flag on the create command. The `create --help` output confirms it. A user copy-pasting from the README will get an error.

**Fix**: Either implement the flag or remove it from the README.

### 2. Config example has wrong environment variable name

`config.toml.example` line 17 says:

```
export MIMEO_PORKBUN_SECRET_KEY="your-secret"
```

But `config.py:86` reads:

```python
os.getenv("MIMEO_PORKBUN_SECRET")
```

Anyone following the example to set up env vars will have their secret silently ignored, falling back to the config file (or failing with "Missing required configuration" if there's no config file). This is the kind of silent failure that wastes an hour of debugging.

**Fix**: Change the example to `MIMEO_PORKBUN_SECRET`.

### 3. README project structure references a file that doesn't exist

The README lists `mimeo/content.py` as "Landing page HTML generation". No such file exists. The project structure diagram is out of date.

**Fix**: Update the README to reflect the actual file layout (templates are now fetched from GitHub repos, not generated locally).

### 4. No domain validation at the CLI layer

The `Domain` model exists in `models.py` with a regex validator, but it is never used anywhere. The create command accepts any string:

```
mimeo create "not a domain"
mimeo create ""
```

Both will proceed to call GitHub and Porkbun APIs with garbage input. The Domain model should be the gatekeeper.

**Fix**: Validate domain arguments at the CLI entry point using `Domain(name)`. Fail fast before making any API calls.

### 5. No ownership check before creating a site

`mimeo create random.com` will create a GitHub repo even if you don't own the domain in Porkbun. The tool should verify the domain exists in the registrar account before proceeding with the host setup. As-is, you can end up with orphaned GitHub repos for domains you don't control.

---

## Design Concerns

### 6. CLI code reaches into private provider methods

`fix.py:98` calls `host._enable_https_enforcement(repo_full_name)` directly. `registrar.py:110` calls `dns_prov._get_domain_records(domain_name)`. These are private methods (underscore prefix) being used as public API.

If the provider implementation changes, the CLI breaks with no warning. This defeats the purpose of the ABC layer.

**Fix**: Add public methods to the provider ABCs for operations the CLI needs (`enable_https`, `get_dns_records`). Make the CLI go through the public interface.

### 7. `_health_status` is a private function imported in CLI code

`list_cmd.py` and `fix.py` both import `_health_status` from `github.py`. This function should either be public (drop the underscore) or live in a shared utilities module.

### 8. GITHUB_PAGES_IPS defined in the wrong module

The GitHub Pages IP addresses live in `porkbun.py` but are imported by `github.py`. The Host provider depends on the Registrar provider for its own configuration data. If someone adds a new host provider, they'd need to import DNS IPs from a registrar module.

**Fix**: Move `GITHUB_PAGES_IPS` to `github.py` (or a shared constants module). The host should own its own IPs. The registrar uses them for DNS config, so it should import from the host.

### 9. Duplicated `check_nameservers` in Registrar and DNSProvider

Both `PorkbunRegistrar` and `PorkbunDNSProvider` have identical `check_nameservers` implementations. They inherit from different ABCs (`Registrar`, `DNSProvider`) that both declare the same method. This is a red flag that the abstraction might be wrong -- nameserver management is a registrar concern, not a DNS record concern.

**Fix**: Remove `check_nameservers` from `DNSProvider` ABC. Users who need to check nameservers should use the `Registrar`.

### 10. Host ABC doesn't match its concrete implementation

`Host.deploy_site()` takes `(domain)` but `GitHubHost.deploy_site()` takes `(domain, template, force)`. Callers that use the ABC can't pass template or force. This means the abstraction doesn't actually support swapping hosts without changing caller code.

**Fix**: Either add `template` and `force` to the ABC, or restructure so callers don't depend on host-specific parameters.

---

## User Experience Issues

### 11. No progress indication during DNS propagation

DNS verification does up to 10 attempts with 5-second delays (50 seconds max). The user sees nothing during this wait. For a CLI tool, silence feels like a hang.

**Fix**: Print a dot or a spinner character between attempts. Or at minimum, print "Waiting for DNS propagation (attempt 1/10)...".

### 12. `load_config` prints "Loading configuration..." to stdout

This message appears in text mode, JSON mode, and even when piping output to other commands. It pollutes `mimeo list --format csv | cut -d, -f1` output with a non-CSV line.

**Fix**: Print to stderr or remove entirely. Config loading should be silent unless it fails.

### 13. Partial failures are silent in concurrent mode

When processing multiple domains concurrently, if DNS configuration fails for one domain, the summary just shows "2/3 succeeded" in yellow. The user has to scan back through the output to figure out which one failed and why. In concurrent mode, domain outputs are interleaved and hard to follow.

**Fix**: Always print a per-domain failure summary at the end, even in concurrent mode.

### 14. No confirmation prompt for destructive DNS changes

`dns repair` deletes all matching DNS records and recreates them. There's a `--dry-run` flag but no confirmation prompt by default. If someone runs `mimeo dns repair example.com --reset-nameservers` by accident, it silently nukes and recreated their DNS.

**Fix**: Add a confirmation prompt when making destructive changes, similar to `template apply`.

### 15. `registrar list --with-dns` creates a new HTTP session per domain

The `_enrich` function in `registrar.py` creates a new `PorkbunRegistrar` and `PorkbunDNSProvider` for every domain. For 100 domains, that's 200 HTTP sessions. This is wasteful and slower than reusing a single session.

**Fix**: Create the provider instances once before the thread pool and pass them to `_enrich`.

---

## Code Quality Issues

### 16. Dead code: `NSMismatchError` is never raised

`exceptions.py` defines `NSMismatchError(RegistrarError)` but nothing in the codebase raises it. The `check_nameservers` methods return a result object instead.

**Fix**: Remove it or use it in `check_nameservers` when NS doesn't match.

### 17. Dead code: `Domain` model is never used

The `Domain` class with its validation, `tld`, and `sld` properties is defined but never instantiated anywhere. The CLI operates on raw strings.

### 18. `--format` shadows Python builtin

Multiple CLI commands use `format` as a parameter name (e.g., `list_cmd.py:30`). This shadows the Python builtin `format()`. While it works because Click parameters are local, it's a linting red flag and can cause confusion.

**Fix**: Use `output_format` consistently (as `registrar.py` already does).

### 19. `test_cli.py` has massive mock setup duplication

Almost every test repeats the same 15-line mock setup for `mock_host`, `mock_registrar`, `mock_dns_provider`. The file is ~1,400 lines when it could be ~800 with proper fixture reuse.

**Fix**: Extract the common "all providers mocked successfully" setup into a single fixture or decorator.

### 20. Thread safety of `click.echo` in concurrent mode

`click.echo()` and `click.secho()` are not thread-safe. In concurrent mode, multiple threads write to stdout simultaneously, which can produce garbled output. The `_console_lock` exists in `_processing.py` but isn't used in the per-domain logging functions (`_process_single_domain`, `_repair_domain`, `_apply_template`).

**Fix**: Route all concurrent output through the lock, or buffer per-thread and print sequentially at the end.

---

## Minor Issues

### 21. `configure_dns` is not transactional

The method deletes all matching records, then creates new ones. If creation fails partway through (e.g., API error on record 3 of 5), the domain is left in a broken state with missing records. There's no rollback.

**Mitigation**: The DNS records are simple enough that re-running the command fixes it. But the user should be warned.

### 22. `list_mimeo_repositories` hardcodes limit of 1000

GitHub search API caps at 1000 results. For this tool's use case, that's fine. But if someone manages thousands of domains through mimeo, they'll silently not see all of them.

### 23. `check_dns_drift` ignores TTL differences

Records with matching type/name/content but different TTLs are considered "ok". This is probably fine for the use case but could mask configuration drift.

### 24. `fix https` has no `--workers` option

Every other multi-domain command supports `--workers` for concurrency. `fix https` processes targets sequentially in a for loop.

### 25. Exit code 1 is never used

The exit code constants skip from 0 (`EXIT_OK`) to 2 (`EXIT_CONFIG`). Exit code 1 (the standard Unix error code) is never used, which might confuse users checking `$?`.

---

## What's Done Well

- **Exception hierarchy** is clean and maps well to exit codes. `_categorize_error` does a good job classifying failures.
- **Retry logic** with exponential backoff and jitter is production-quality. The `_is_retryable` function correctly distinguishes transient from permanent failures.
- **Provider abstraction via ABCs** is the right approach. Even though it has coupling issues now, the shape is correct for adding Cloudflare, Route53, Netlify, etc.
- **Context manager pattern** for providers ensures sessions are cleaned up.
- **Dry-run support** across create, dns repair, and template apply is thorough.
- **Concurrent processing** with `ThreadPoolExecutor` and ordered results is well-implemented.
- **Test coverage** is strong at 244 tests with good use of `responses` and mocking.
- **JSON logging mode** (`--log-format json`) makes the tool scriptable.
- **CSV output** across list commands makes data exportable.

---

## Recommendations (Priority Order)

1. Fix the env var name in `config.toml.example` (2 minutes, breaks setup for env-var users)
2. Remove or implement `--force-dns-update` from README (5 minutes)
3. Add domain validation at CLI entry points using the existing `Domain` model (30 minutes)
4. Move "Loading configuration..." to stderr or remove it (5 minutes)
5. Make `_health_status` and `_enable_https_enforcement` public API on the Host class (20 minutes)
6. Move `GITHUB_PAGES_IPS` to `github.py` (15 minutes)
7. Add progress indication during DNS propagation (30 minutes)
8. Add ownership check in `create` before deploying to GitHub (1 hour)
9. Reuse HTTP sessions in `registrar list --with-dns` (30 minutes)
10. Remove dead code (`NSMismatchError`, unused `Domain`) (15 minutes)
