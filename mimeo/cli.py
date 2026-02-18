"""Command-line interface for Mimeo."""

import csv
import json
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, cast

import click

from . import __version__
from .config import Config
from .content import generate_minimal_site
from .exceptions import (
    EXIT_AUTH,
    EXIT_CONFIG,
    EXIT_PARTIAL,
    EXIT_RATE_LIMIT,
    EXIT_TRANSIENT,
    APIError,
    ConfigurationError,
    HostError,
    NetworkError,
    RegistrarError,
)
from .providers.host.github import GitHubHost, _health_status
from .providers.registrar.porkbun import PorkbunRegistrar

# Lock for thread-safe console output
_console_lock = Lock()

_AUTH_KEYWORDS = ("unauthorized", "authentication", "forbidden", "invalid api key", "bad credentials")
_RATE_LIMIT_KEYWORDS = ("rate limit", "429")
_TRANSIENT_KEYWORDS = ("502", "503", "500", "timeout", "connection")


def _categorize_error(exc: BaseException) -> tuple[int, str]:
    """Return (exit_code, category_label) for an exception.

    Args:
        exc: The exception to categorize

    Returns:
        Tuple of exit code and short category label for display
    """
    if isinstance(exc, ConfigurationError):
        return EXIT_CONFIG, "config"

    msg = str(exc).lower()

    if isinstance(exc, APIError):
        if exc.status_code == 429 or any(k in msg for k in _RATE_LIMIT_KEYWORDS):
            return EXIT_RATE_LIMIT, "rate-limit"
        if exc.status_code in (500, 502, 503, 504):
            return EXIT_TRANSIENT, "transient"
        if any(k in msg for k in _AUTH_KEYWORDS):
            return EXIT_AUTH, "auth"

    if isinstance(exc, NetworkError):
        return EXIT_TRANSIENT, "transient"

    if isinstance(exc, (HostError, RegistrarError)):
        if any(k in msg for k in _AUTH_KEYWORDS):
            return EXIT_AUTH, "auth"
        if any(k in msg for k in _RATE_LIMIT_KEYWORDS):
            return EXIT_RATE_LIMIT, "rate-limit"
        if any(k in msg for k in _TRANSIENT_KEYWORDS):
            return EXIT_TRANSIENT, "transient"

    return EXIT_TRANSIENT, "provider"


def _process_single_domain(domain: str, cfg: Config, dry_run: bool, verbose: bool = True) -> dict:
    """Process a single domain creation.

    Args:
        domain: Domain name to process
        cfg: Configuration object
        dry_run: If True, don't actually create anything

    Returns:
        Dictionary with result information
    """
    result = {
        "domain": domain,
        "success": False,
        "error": None,
        "error_category": None,
        "url": None,
        "repo_url": None,
        "https_pending": False,
        "dns_pending": False,
        "log": [],
    }

    def log(message: str, level: str = "info") -> None:
        """Add to result log and optionally print to console."""
        cast(List, result["log"]).append({"message": message, "level": level})

        # Only print to console in verbose mode (sequential/dry-run)
        if verbose:
            if level == "error":
                click.secho(f"  ✗ {message}", fg="red")
            elif level == "warning":
                click.secho(f"  ⚠ {message}", fg="yellow")
            elif level == "success":
                click.secho(f"  ✓ {message}", fg="green")
            else:
                click.echo(f"  {message}")

    try:
        if dry_run:
            log(f"Would generate site for {domain}")
            log(f"Would create repository: {cfg.github_username}/{domain}")
            log("Would deploy to GitHub Pages")
            log("Would configure DNS records:")
            dns_records = PorkbunRegistrar.github_pages_records(domain, cfg.github_username)
            for record in dns_records:
                log(f"  - {record.type} {record.name or '@'} -> {record.content}")
            result["success"] = True
            result["url"] = f"https://{domain}"
            result["repo_url"] = f"https://github.com/{cfg.github_username}/{domain}"
            return result

        # Create temporary directory for site content
        with tempfile.TemporaryDirectory() as temp_dir:
            content_path = Path(temp_dir)

            # Generate site content
            log("Generating site content")
            try:
                generate_minimal_site(domain, content_path)
                log("Site content generated", "success")
            except Exception as e:
                log(f"Failed to generate site content: {e}", "error")
                raise

            # Deploy to GitHub Pages
            log("Configuring GitHub repository")
            try:
                with GitHubHost(default_org=cfg.github_username) as host:
                    deploy = host.deploy_site(domain, content_path)
                    result["url"] = deploy.url
                    result["repo_url"] = f"https://github.com/{cfg.github_username}/{domain}"

                    if deploy.repo_created:
                        log(f"Repository created: {cfg.github_username}/{domain}", "success")
                        log("Content pushed to GitHub", "success")
                    else:
                        log(f"Repository exists: {cfg.github_username}/{domain}", "info")
                        log("Skipped content push (using existing content)", "info")

                    log("GitHub Pages enabled", "success")
                    log(f"Custom domain configured: {domain}", "success")

                    if not deploy.https_enabled:
                        log("HTTPS enforcement pending SSL certificate", "warning")
                        result["https_pending"] = True
                    else:
                        log("HTTPS enforcement enabled", "success")
            except HostError as e:
                log(f"GitHub deployment failed: {e}", "error")
                raise

            # Configure DNS
            log("Configuring DNS records")
            try:
                dns_records = PorkbunRegistrar.github_pages_records(
                    domain, cfg.github_username
                )

                with PorkbunRegistrar(cfg.porkbun_api_key, cfg.porkbun_secret) as registrar:
                    # Log what we're creating
                    for record in dns_records:
                        record_name = record.name or "@"
                        log(f"Creating {record.type} record: {record_name} -> {record.content}")

                    registrar.configure_dns(domain, dns_records)
                    log("DNS records created", "success")

                    # Verify DNS propagation
                    log("Verifying DNS propagation")
                    verified = registrar.verify_dns(domain, dns_records, max_attempts=10, delay=5)
                    if verified:
                        log("DNS records verified", "success")
                    else:
                        log("DNS records created but not yet propagated (may take up to 24 hours)", "warning")
                        result["dns_pending"] = True

            except RegistrarError as e:
                log(f"DNS configuration failed: {e}", "error")
                log("Site deployed but DNS not configured", "warning")
                # Don't raise - site is still accessible via github.io URL
                result["dns_pending"] = True
                result["error_category"] = "partial"

        result["success"] = True

    except Exception as e:
        exit_code, category = _categorize_error(e)
        result["error"] = f"[{category}] {e}"
        result["error_category"] = category
        log(str(result["error"]), "error")

    return result


@click.group()
@click.version_option(version=__version__, prog_name="Mimeo")
def main() -> None:
    """A tool to generate websites quickly"""
    pass


@main.command()
@click.argument("domains", nargs=-1, required=True)
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    help="Path to config file (default: ~/.config/mimeo/config.toml)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be created without actually creating anything",
)
@click.option(
    "--stop-on-error",
    is_flag=True,
    help="Stop processing if any domain fails (default: continue with remaining domains)",
)
@click.option(
    "--sequential",
    is_flag=True,
    help="Process domains sequentially instead of concurrently",
)
def create(domains: tuple[str, ...], config: Path | None, dry_run: bool, stop_on_error: bool, sequential: bool) -> None:
    """Create and deploy minimal landing pages for one or more domains.

    This command will:
    1. Generate a minimal landing page
    2. Deploy to GitHub Pages
    3. Configure DNS records
    4. Set up custom domain

    Multiple domains are processed concurrently for faster provisioning.

    Examples:
        mimeo create example.com
        mimeo create site1.com site2.com site3.com
        mimeo create example.com --dry-run
        mimeo create site1.com site2.com --sequential
    """
    # Load configuration once
    try:
        click.echo("Loading configuration...")
        cfg = Config.load(config)
    except ConfigurationError as e:
        click.secho(f"[config] {e}", fg="red", err=True)
        sys.exit(EXIT_CONFIG)

    if dry_run:
        click.secho("DRY RUN MODE - No changes will be made", fg="cyan", bold=True)
        click.echo()

    # Track results for summary
    results = []

    # Process domains concurrently or sequentially
    # Always use sequential mode for dry-run or single domain
    if dry_run or sequential or len(domains) == 1:
        # Sequential processing (verbose mode)
        for idx, domain in enumerate(domains, 1):
            if len(domains) > 1:
                click.echo()
                click.secho(f"[{idx}/{len(domains)}] Processing {domain}", fg="cyan", bold=True)
                click.secho("=" * 60, fg="cyan")

            result = _process_single_domain(domain, cfg, dry_run, verbose=True)
            results.append(result)

            # Stop on error if requested
            if stop_on_error and not result["success"]:
                click.echo()
                click.secho(f"Stopping due to error with {domain}", fg="red")
                break
    else:
        # Concurrent processing (non-verbose to avoid garbled output)
        click.echo()

        # Use ThreadPoolExecutor for concurrent processing
        # Limit to 5 workers to avoid overwhelming APIs
        with ThreadPoolExecutor(max_workers=min(len(domains), 5)) as executor:
            # Submit all tasks and show as they start
            future_to_domain = {}
            for domain in domains:
                future = executor.submit(_process_single_domain, domain, cfg, dry_run, verbose=False)
                future_to_domain[future] = domain
                click.secho(f"→ {domain} started", fg="cyan")

            click.echo()

            # Process results as they complete
            for future in as_completed(future_to_domain):
                domain = future_to_domain[future]
                try:
                    result = future.result()
                    results.append(result)

                    # Show completion status
                    if result["success"]:
                        click.secho(f"✓ {domain} completed", fg="green")
                    else:
                        click.secho(f"✗ {domain} failed: {result.get('error', 'Unknown error')}", fg="red")

                except Exception as e:
                    # Should not happen as exceptions are caught in _process_single_domain
                    click.secho(f"✗ {domain} failed unexpectedly: {e}", fg="red")
                    results.append({
                        "domain": domain,
                        "success": False,
                        "error": str(e),
                    })

        # Sort results by original domain order for consistent summary
        domain_order = {domain: idx for idx, domain in enumerate(domains)}
        results.sort(key=lambda r: domain_order.get(r["domain"], 999))

    # Print summary
    click.echo()
    click.secho("=" * 60, fg="white", bold=True)
    click.secho("SUMMARY", fg="white", bold=True)
    click.secho("=" * 60, fg="white", bold=True)
    click.echo()

    success_count = sum(1 for r in results if r["success"])
    total_count = len(results)

    if dry_run:
        click.secho(f"DRY RUN: Would process {total_count} domain(s)", fg="cyan")
    else:
        click.secho(f"Successfully created: {success_count}/{total_count} domain(s)", fg="green" if success_count == total_count else "yellow")

    click.echo()

    for result in results:
        domain = result["domain"]
        if result["success"]:
            click.secho(f"✓ {domain}", fg="green", bold=True)
            if not dry_run:
                click.echo(f"  URL: {result.get('url', 'N/A')}")
                click.echo(f"  Repository: {result.get('repo_url', 'N/A')}")
                if result.get("https_pending"):
                    click.secho("  HTTPS: Pending SSL certificate", fg="yellow")
                if result.get("dns_pending"):
                    click.secho("  DNS: Propagation pending", fg="yellow")
        else:
            click.secho(f"✗ {domain}", fg="red", bold=True)
            click.secho(f"  Error: {result.get('error', 'Unknown error')}", fg="red")
        click.echo()

    # Exit with error if any failed, using the most severe error category
    if success_count < total_count:
        _category_to_code = {
            "config": EXIT_CONFIG,
            "auth": EXIT_AUTH,
            "rate-limit": EXIT_RATE_LIMIT,
            "transient": EXIT_TRANSIENT,
            "provider": EXIT_TRANSIENT,
            "partial": EXIT_PARTIAL,
        }
        failed = [r for r in results if not r["success"]]
        codes = [_category_to_code.get(r.get("error_category") or "transient", EXIT_TRANSIENT) for r in failed]
        sys.exit(min(codes))  # lower code = more specific / severe


@main.command()
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    help="Path to config file (default: ~/.config/mimeo/config.toml)",
)
@click.option(
    "--format",
    type=click.Choice(["text", "json", "csv"], case_sensitive=False),
    default="text",
    help="Output format (default: text)",
)
@click.option("--health", is_flag=True, help="Check Pages configuration health for each site")
@click.option("--fix", is_flag=True, help="Enable HTTPS for sites with approved certificates (implies --health)")
def list(config: Path | None, format: str, health: bool, fix: bool) -> None:
    """List all mimeo-managed sites.

    Shows repositories tagged with the 'mimeo' topic.

    \b
    Basic usage:
        mimeo list                    # Human-readable text format
        mimeo list --format json      # JSON output
        mimeo list --format csv       # CSV output

    \b
    Extracting specific data:
        # Just domain names
        mimeo list --format csv | tail -n +2 | cut -d, -f1

        # Just site URLs
        mimeo list --format json | jq -r '.[].site'

        # Just repository URLs
        mimeo list --format csv | tail -n +2 | cut -d, -f2

    \b
    Processing with jq:
        # Count total sites
        mimeo list --format json | jq 'length'

        # Filter by update date
        mimeo list --format json | jq '.[] | select(.updated == "2026-02-15")'

        # Get names of recently updated sites
        mimeo list --format json | jq -r '.[] | select(.updated >= "2026-02-01") | .name'

    \b
    Importing data:
        # Export to CSV file
        mimeo list --format csv > sites.csv

        # Create simple list for scripts
        mimeo list --format csv | tail -n +2 | cut -d, -f1 > domains.txt
    """
    # --fix implies --health
    if fix:
        health = True

    try:
        # Load configuration
        cfg = Config.load(config)

        # Get mimeo-tagged repositories from GitHub
        with GitHubHost(default_org=cfg.github_username) as host:
            repos = host.list_mimeo_repositories()

            if not repos:
                if format == "json":
                    click.echo("[]")
                elif format == "csv":
                    fieldnames = ["name", "repository", "site", "updated"]
                    if health:
                        fieldnames += ["health", "https_enforced", "cert_state"]
                    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
                    writer.writeheader()
                else:
                    click.echo("No mimeo-managed sites found.")
                    click.echo()
                    click.echo("Create your first site with: mimeo create example.com")
                return

            # Normalize repository data
            owner = cfg.github_username
            normalized_repos = []
            for repo in repos:
                name = repo.get("name", "")
                url = repo.get("url", "")
                pages_url = repo.get("homepage") or f"https://{name}"
                updated = repo.get("updatedAt", "")[:10]

                normalized_repos.append({
                    "name": name,
                    "repository": url,
                    "site": pages_url,
                    "updated": updated,
                })

            # Fetch health data concurrently if requested
            if health:
                health_map: Dict[str, Dict[str, Any]] = {}
                with ThreadPoolExecutor(max_workers=10) as executor:
                    future_to_name = {
                        executor.submit(host.get_pages_health, f"{owner}/{r['name']}"): r["name"]
                        for r in normalized_repos
                    }
                    for future in as_completed(future_to_name):
                        name = future_to_name[future]
                        health_map[name] = future.result()

                for repo_data in normalized_repos:
                    h = health_map.get(repo_data["name"], {
                        "pages_configured": False,
                        "https_enforced": False,
                        "cert_state": None,
                        "pages_status": None,
                    })
                    repo_data["health"] = _health_status(h)
                    repo_data["https_enforced"] = h["https_enforced"]
                    repo_data["cert_state"] = h["cert_state"]

            # Run fixes for fixable repos
            fix_results: List[Dict[str, Any]] = []
            if fix:
                fixable = [r for r in normalized_repos if r.get("health") == "fixable"]
                for repo_data in fixable:
                    repo_full_name = f"{owner}/{repo_data['name']}"
                    try:
                        host._enable_https_enforcement(repo_full_name)
                        fix_results.append({"name": repo_data["name"], "success": True, "error": None})
                        repo_data["health"] = "healthy"
                        repo_data["https_enforced"] = True
                    except HostError as e:
                        fix_results.append({"name": repo_data["name"], "success": False, "error": str(e)})

        # Sort order: with health, group by severity then name; otherwise by name
        _status_order = {"pages_error": 0, "no_cert": 1, "cert_pending": 2, "fixable": 3, "healthy": 4}
        if health:
            normalized_repos.sort(key=lambda r: (_status_order.get(r.get("health", "pages_error"), 0), r["name"]))
        else:
            normalized_repos.sort(key=lambda r: r["name"])

        # Display results based on format
        if format == "json":
            click.echo(json.dumps(normalized_repos, indent=2))
        elif format == "csv":
            fieldnames = ["name", "repository", "site", "updated"]
            if health:
                fieldnames += ["health", "https_enforced", "cert_state"]
            writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(normalized_repos)
        else:
            # Text format: tabular layout
            _health_colors = {
                "healthy": "green",
                "fixable": "yellow",
                "cert_pending": "yellow",
                "no_cert": "red",
                "pages_error": "red",
            }
            _health_labels = {
                "healthy": "ok",
                "fixable": "fixable",
                "cert_pending": "pending",
                "no_cert": "no cert",
                "pages_error": "error",
            }

            # Calculate column widths
            name_w = max(len(r["name"]) for r in normalized_repos)
            site_w = max(len(r["site"]) for r in normalized_repos)

            click.echo()

            # Header
            if health:
                header = f"  {'NAME':<{name_w}}  {'SITE':<{site_w}}  {'UPDATED':<10}  STATUS"
            else:
                header = f"  {'NAME':<{name_w}}  {'SITE':<{site_w}}  UPDATED"
            click.secho(header, bold=True)
            click.secho("  " + "-" * (len(header) - 2), fg="white", dim=True)

            for repo_data in normalized_repos:
                name = repo_data["name"]
                site = repo_data["site"]
                updated = repo_data["updated"]
                if health:
                    status = repo_data.get("health", "pages_error")
                    color = _health_colors.get(status, "white")
                    label = _health_labels.get(status, status)
                    row = f"  {name:<{name_w}}  {site:<{site_w}}  {updated:<10}  "
                    click.echo(row, nl=False)
                    click.secho(label, fg=color)
                else:
                    click.echo(f"  {name:<{name_w}}  {site:<{site_w}}  {updated}")

            click.echo()

            if fix_results:
                click.secho("Fixed HTTPS enforcement:", bold=True)
                for r in fix_results:
                    if r["success"]:
                        click.secho(f"  ✓ {r['name']}", fg="green")
                    else:
                        click.secho(f"  ✗ {r['name']} ({r['error']})", fg="red")
                click.echo()

    except Exception as e:
        exit_code, category = _categorize_error(e)
        click.secho(f"[{category}] {e}", fg="red", err=True)
        sys.exit(exit_code)


def _check_python_version() -> tuple[bool, str, str]:
    """Check that Python is >= 3.11."""
    major, minor = sys.version_info[:2]
    if major >= 3 and minor >= 11:
        return True, f"Python {major}.{minor}", ""
    return False, f"Python {major}.{minor}", "Install Python 3.11 or later."


def _check_gh_installed() -> tuple[bool, str, str]:
    """Check that the gh CLI is installed."""
    try:
        result = subprocess.run(
            ["gh", "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        version_line = result.stdout.splitlines()[0] if result.stdout else "gh"
        return True, version_line, ""
    except FileNotFoundError:
        return False, "not found", "Install gh from https://cli.github.com"


def _check_gh_auth() -> tuple[bool, str, str]:
    """Check that gh is authenticated."""
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return True, "authenticated", ""
        return False, "not authenticated", "Run 'gh auth login' to authenticate."
    except FileNotFoundError:
        return False, "gh not installed", "Install gh from https://cli.github.com"


def _check_gh_workflow_scope() -> tuple[bool, str, str]:
    """Check that the gh token has the 'workflow' scope."""
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return False, "cannot check (not authenticated)", "Run 'gh auth login' first."
        output = result.stdout + result.stderr
        for line in output.splitlines():
            if "Token scopes" in line:
                if "'workflow'" in line or '"workflow"' in line:
                    return True, "workflow scope present", ""
                return (
                    False,
                    "workflow scope missing",
                    "Re-authenticate with workflow scope: "
                    "gh auth login --scopes repo,workflow",
                )
        return False, "could not determine scopes", "Re-authenticate: gh auth login --scopes repo,workflow"
    except FileNotFoundError:
        return False, "gh not installed", "Install gh from https://cli.github.com"


def _check_config(config_path: Path | None) -> tuple[bool, str, str]:
    """Check that the config file exists and is valid."""
    if config_path is None:
        config_path = Path.home() / ".config" / "mimeo" / "config.toml"
    if not config_path.exists():
        return (
            False,
            f"not found: {config_path}",
            f"Create {config_path} with your API credentials. See README for format.",
        )
    try:
        Config.load(config_path)
        return True, str(config_path), ""
    except ConfigurationError as e:
        first_line = str(e).splitlines()[0]
        return False, first_line, "Fix the configuration issues listed above."


@main.command()
@click.option(
    "--config",
    type=click.Path(path_type=Path),
    help="Path to config file (default: ~/.config/mimeo/config.toml)",
)
def doctor(config: Path | None) -> None:
    """Check that all prerequisites for mimeo are met.

    Verifies:
      - Python version >= 3.11
      - gh CLI is installed
      - gh CLI is authenticated
      - GitHub token has the 'workflow' scope
      - Config file exists and is valid

    Prints a pass/fail result for each check with remediation
    instructions for any failures.
    """
    checks = [
        ("Python >= 3.11", _check_python_version),
        ("gh installed", _check_gh_installed),
        ("gh authenticated", _check_gh_auth),
        ("workflow scope", _check_gh_workflow_scope),
        ("config file", lambda: _check_config(config)),
    ]

    all_ok = True
    click.echo()
    for label, check_fn in checks:
        ok, detail, fix = check_fn()
        if ok:
            click.secho("  ok  ", fg="green", nl=False, bold=True)
        else:
            click.secho(" fail ", fg="red", nl=False, bold=True)
            all_ok = False
        click.echo(f"  {label:<22} {detail}")
        if not ok and fix:
            click.secho(f"            -> {fix}", fg="yellow")

    click.echo()
    if all_ok:
        click.secho("All checks passed.", fg="green", bold=True)
    else:
        click.secho("Some checks failed. Address the issues above before running mimeo.", fg="red")
        sys.exit(EXIT_CONFIG)


if __name__ == "__main__":
    main()
