"""Create command for provisioning new sites."""

from pathlib import Path
from typing import Any, Dict, List, cast

import click

from ..exceptions import (
    HostError,
    RegistrarError,
)
from ..providers.host.github import DEFAULT_TEMPLATE, GitHubHost
from ..providers.registrar.porkbun import PorkbunDNSProvider, PorkbunRegistrar
from ._processing import (
    _categorize_error,
    _emit,
    exit_on_failures,
    get_log_format,
    load_config,
    process_domains_concurrent,
    validate_domains,
)


def _process_single_domain(
    domain: str,
    cfg: Any,
    dry_run: bool,
    verbose: bool = True,
    skip_dns: bool = False,
    template: str = DEFAULT_TEMPLATE,
) -> dict:
    """Process a single domain creation.

    Args:
        domain: Domain name to process
        cfg: Configuration object
        dry_run: If True, don't actually create anything
        skip_dns: If True, skip DNS configuration
        template: Template repository to use

    Returns:
        Dictionary with result information
    """
    result: Dict[str, Any] = {
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

    log_format = get_log_format()

    def log(message: str, level: str = "info") -> None:
        """Add to result log and optionally print to console."""
        cast(List, result["log"]).append({"message": message, "level": level})
        _emit(level, message, domain=domain)

        if verbose and log_format == "text":
            if level == "error":
                click.secho(f"  xx {message}", fg="red")
            elif level == "warning":
                click.secho(f"  !! {message}", fg="yellow")
            elif level == "success":
                click.secho(f"  ok {message}", fg="green")
            else:
                click.echo(f"  {message}")

    try:
        if dry_run:
            log(f"Would generate site for {domain}")
            log(f"Would create repository: {cfg.github_username}/{domain}")
            log("Would deploy to GitHub Pages")
            if not skip_dns:
                log("Would check nameservers before configuring DNS")
                log("Would configure DNS records (if NS points to Porkbun):")
                from mimeo.providers.host.github import GITHUB_PAGES_IPS
                from mimeo.models import DNSRecord as _DNSRecord

                dry_records = [
                    _DNSRecord(type="A", name="", content=ip, ttl=600) for ip in GITHUB_PAGES_IPS
                ] + [
                    _DNSRecord(
                        type="CNAME",
                        name="www",
                        content=f"{cfg.github_username}.github.io",
                        ttl=600,
                    )
                ]
                for record in dry_records:
                    log(f"  - {record.type} {record.name or '@'} -> {record.content}")
            else:
                log("Would skip DNS configuration (--skip-dns)")
            result["success"] = True
            result["url"] = f"https://{domain}"
            result["repo_url"] = f"https://github.com/{cfg.github_username}/{domain}"
            return result

        # Deploy to GitHub Pages
        log("Configuring GitHub repository")
        dns_records = None
        try:
            with GitHubHost(default_org=cfg.github_username) as host:
                deploy = host.deploy_site(domain, template=template)
                dns_records = host.required_dns_records(domain)
                result["url"] = deploy.url
                result["repo_url"] = f"https://github.com/{cfg.github_username}/{domain}"

                if deploy.repo_created:
                    log(
                        f"Repository created from template '{template}': {cfg.github_username}/{domain}",
                        "success",
                    )
                else:
                    log(f"Repository already exists: {cfg.github_username}/{domain}", "warning")
                    log(
                        "Use 'mimeo template apply' to replace with a different template", "warning"
                    )
                    # Still configure Pages and domain for existing repos

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

        if skip_dns:
            log("Skipping DNS configuration (--skip-dns)", "info")
            result["dns_pending"] = True
            result["success"] = True
            return result

        # Configure DNS
        log("Configuring DNS records")
        try:
            with PorkbunRegistrar(cfg.porkbun_api_key, cfg.porkbun_secret) as registrar:
                ns_result = registrar.check_nameservers(domain)
                if not ns_result.ok:
                    actual_ns = ", ".join(ns_result.actual) if ns_result.actual else "unknown"
                    log(
                        f"NS records point to {actual_ns}, not Porkbun -- skipping DNS config",
                        "warning",
                    )
                    log("Use 'mimeo dns repair' to fix DNS records", "warning")
                    result["dns_pending"] = True
                    result["ns_mismatch"] = ns_result.actual
                else:
                    with PorkbunDNSProvider(cfg.porkbun_api_key, cfg.porkbun_secret) as dns:
                        for record in dns_records or []:
                            record_name = record.name or "@"
                            log(f"Creating {record.type} record: {record_name} -> {record.content}")

                        dns.configure_dns(domain, dns_records or [])
                        log("DNS records created", "success")

                        log("Verifying DNS propagation")
                        verified = dns.verify_dns(
                            domain,
                            dns_records or [],
                            max_attempts=10,
                            delay=5,
                            progress_callback=lambda attempt, max_att: click.echo(
                                f"  DNS check {attempt}/{max_att} -- retrying..."
                            ),
                        )
                        if verified:
                            log("DNS records verified", "success")
                        else:
                            log(
                                "DNS records created but not yet propagated (may take up to 24 hours)",
                                "warning",
                            )
                            result["dns_pending"] = True

        except RegistrarError as e:
            log(f"DNS configuration failed: {e}", "error")
            log("Site deployed but DNS not configured", "warning")
            result["dns_pending"] = True
            result["error_category"] = "partial"

        result["success"] = True

    except Exception as e:
        exit_code, category = _categorize_error(e)
        result["error"] = f"[{category}] {e}"
        result["error_category"] = category
        log(str(result["error"]), "error")

    return result


@click.command()
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
@click.option(
    "--workers",
    type=click.IntRange(min=1),
    default=5,
    show_default=True,
    help="Maximum number of concurrent workers",
)
@click.option(
    "--template",
    default=DEFAULT_TEMPLATE,
    show_default=True,
    help="Template repository name to use (from the tepiton org)",
)
@click.option(
    "--skip-dns",
    is_flag=True,
    help="Create repo and Pages only, handle DNS separately",
)
def create(
    domains: tuple[str, ...],
    config: Path | None,
    dry_run: bool,
    stop_on_error: bool,
    sequential: bool,
    workers: int,
    template: str,
    skip_dns: bool,
) -> None:
    """Create and deploy new sites for one or more domains.

    Provisions a GitHub repository from a template, enables GitHub Pages,
    configures custom domain, and sets up DNS records.

    If a repository already exists, it is left unchanged. Use 'mimeo template apply'
    to replace it with a different template.

    Multiple domains are processed concurrently for faster provisioning.

    Examples:
        mimeo create example.com
        mimeo create site1.com site2.com site3.com
        mimeo create example.com --dry-run
        mimeo create site1.com site2.com --sequential
        mimeo create example.com --skip-dns
    """
    validate_domains(domains)
    cfg = load_config(config)
    log_format = get_log_format()

    if dry_run:
        click.secho("DRY RUN MODE - No changes will be made", fg="cyan", bold=True)
        click.echo()

    def process_fn(domain: str) -> dict:
        use_verbose = dry_run or sequential or len(domains) == 1
        return _process_single_domain(
            domain,
            cfg,
            dry_run,
            verbose=use_verbose,
            skip_dns=skip_dns,
            template=template,
        )

    results = process_domains_concurrent(
        domains,
        process_fn,
        workers,
        sequential,
        stop_on_error,
        dry_run,
    )

    # Print summary
    success_count = sum(1 for r in results if r["success"])
    total_count = len(results)

    if log_format == "json":
        summary_msg = (
            f"DRY RUN: Would process {total_count} domain(s)"
            if dry_run
            else f"Completed: {success_count}/{total_count} succeeded"
        )
        _emit("info", summary_msg)
        for result in results:
            level = "info" if result["success"] else "error"
            _emit(
                level,
                "success" if result["success"] else result.get("error", "unknown error"),
                domain=result["domain"],
            )
    else:
        click.echo()
        click.secho("=" * 60, fg="white", bold=True)
        click.secho("SUMMARY", fg="white", bold=True)
        click.secho("=" * 60, fg="white", bold=True)
        click.echo()

        if dry_run:
            click.secho(f"DRY RUN: Would process {total_count} domain(s)", fg="cyan")
        else:
            click.secho(
                f"Successfully created: {success_count}/{total_count} domain(s)",
                fg="green" if success_count == total_count else "yellow",
            )

        click.echo()

        for result in results:
            domain = result["domain"]
            if result["success"]:
                click.secho(f"ok {domain}", fg="green", bold=True)
                if not dry_run:
                    click.echo(f"  URL: {result.get('url', 'N/A')}")
                    click.echo(f"  Repository: {result.get('repo_url', 'N/A')}")
                    if result.get("https_pending"):
                        click.secho("  HTTPS: Pending SSL certificate", fg="yellow")
                    if result.get("dns_pending"):
                        click.secho("  DNS: Propagation pending", fg="yellow")
            else:
                click.secho(f"xx {domain}", fg="red", bold=True)
                click.secho(f"  Error: {result.get('error', 'Unknown error')}", fg="red")
            click.echo()

    exit_on_failures(results)
