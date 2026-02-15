"""Command-line interface for Mimeo."""

import tempfile
from pathlib import Path

import click

from . import __version__
from .config import Config
from .content import generate_minimal_site
from .exceptions import ConfigurationError, HostError, RegistrarError
from .providers.host.github import GitHubHost
from .providers.registrar.porkbun import PorkbunRegistrar


def _process_single_domain(domain: str, cfg: Config, dry_run: bool) -> dict:
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
        "url": None,
        "repo_url": None,
        "https_pending": False,
        "dns_pending": False,
        "log": [],
    }

    def log(message: str, level: str = "info") -> None:
        """Add to result log and print to console."""
        result["log"].append({"message": message, "level": level})
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
            log("Creating GitHub repository")
            try:
                with GitHubHost(default_org=cfg.github_username) as host:
                    site_url = host.deploy_site(domain, content_path)
                    result["url"] = site_url
                    result["repo_url"] = f"https://github.com/{cfg.github_username}/{domain}"

                    log(f"Repository created: {cfg.github_username}/{domain}", "success")
                    log("Content pushed to GitHub", "success")
                    log("GitHub Pages enabled", "success")
                    log(f"Custom domain configured: {domain}", "success")

                    # Check if HTTPS enforcement was enabled
                    if hasattr(host, '_https_enabled') and not host._https_enabled:
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

        result["success"] = True

    except ConfigurationError as e:
        result["error"] = f"Configuration error: {e}"
        log(str(result["error"]), "error")
    except HostError as e:
        result["error"] = f"Deployment error: {e}"
        log(str(result["error"]), "error")
    except Exception as e:
        result["error"] = f"Unexpected error: {e}"
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
def create(domains: tuple[str, ...], config: Path | None, dry_run: bool, stop_on_error: bool) -> None:
    """Create and deploy minimal landing pages for one or more domains.

    This command will:
    1. Generate a minimal landing page
    2. Deploy to GitHub Pages
    3. Configure DNS records
    4. Set up custom domain

    Examples:
        mimeo create example.com
        mimeo create site1.com site2.com site3.com
        mimeo create example.com --dry-run
    """
    # Load configuration once
    try:
        click.echo("Loading configuration...")
        cfg = Config.load(config)
    except ConfigurationError as e:
        click.secho(f"Configuration error: {e}", fg="red", err=True)
        raise click.Abort()

    if dry_run:
        click.secho("DRY RUN MODE - No changes will be made", fg="cyan", bold=True)
        click.echo()

    # Track results for summary
    results = []

    # Process each domain
    for idx, domain in enumerate(domains, 1):
        if len(domains) > 1:
            click.echo()
            click.secho(f"[{idx}/{len(domains)}] Processing {domain}", fg="cyan", bold=True)
            click.secho("=" * 60, fg="cyan")

        result = _process_single_domain(domain, cfg, dry_run)
        results.append(result)

        # Stop on error if requested
        if stop_on_error and not result["success"]:
            click.echo()
            click.secho(f"Stopping due to error with {domain}", fg="red")
            break

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
                    click.secho(f"  HTTPS: Pending SSL certificate", fg="yellow")
                if result.get("dns_pending"):
                    click.secho(f"  DNS: Propagation pending", fg="yellow")
        else:
            click.secho(f"✗ {domain}", fg="red", bold=True)
            click.secho(f"  Error: {result.get('error', 'Unknown error')}", fg="red")
        click.echo()

    # Exit with error if any failed
    if success_count < total_count:
        raise click.Abort()


@main.command()
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    help="Path to config file (default: ~/.config/mimeo/config.toml)",
)
def list(config: Path | None) -> None:
    """List all mimeo-managed sites.

    Shows repositories tagged with the 'mimeo' topic.

    Example:
        mimeo list
    """
    try:
        # Load configuration
        cfg = Config.load(config)

        # Get mimeo-tagged repositories from GitHub
        with GitHubHost(default_org=cfg.github_username) as host:
            repos = host.list_mimeo_repositories()

        if not repos:
            click.echo("No mimeo-managed sites found.")
            click.echo()
            click.echo("Create your first site with: mimeo create example.com")
            return

        # Display results
        click.echo()
        click.secho(f"Mimeo-managed sites ({len(repos)}):", bold=True)
        click.echo()

        for repo in repos:
            name = repo.get("name", "")
            url = repo.get("url", "")
            pages_url = repo.get("homepage") or f"https://{name}"
            updated = repo.get("updatedAt", "")[:10]  # Just the date part

            click.secho(f"  • {name}", fg="cyan", bold=True)
            click.echo(f"    Repository: {url}")
            click.echo(f"    Site: {pages_url}")
            click.secho(f"    Updated: {updated}", fg="white", dim=True)
            click.echo()

    except ConfigurationError as e:
        click.secho(f"Configuration error: {e}", fg="red", err=True)
        raise click.Abort()
    except HostError as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        raise click.Abort()
    except Exception as e:
        click.secho(f"Unexpected error: {e}", fg="red", err=True)
        raise click.Abort()


if __name__ == "__main__":
    main()
