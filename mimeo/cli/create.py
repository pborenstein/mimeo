"""Create command for provisioning new sites."""

from pathlib import Path
from typing import Any, Dict, List

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
    exit_on_errors,
    get_log_format,
    load_config,
    map_items,
    render_results,
    validate_domains,
)


def _process_single_domain(
    domain: str,
    cfg: Any,
    dry_run: bool,
    verbose: bool = True,
    skip_dns: bool = False,
    template: str = DEFAULT_TEMPLATE,
    force: bool = False,
) -> Dict[str, Any]:
    """Process a single domain creation.

    Args:
        domain: Domain name to process
        cfg: Configuration object
        dry_run: If True, don't actually create anything
        skip_dns: If True, skip DNS configuration
        template: Template repository to use
        force: If True, replace an existing repository's content from
            the template instead of leaving it unchanged

    Returns:
        Dictionary with result information. Raises on hard failure so
        map_items can route it through on_error.
    """
    result: Dict[str, Any] = {
        "domain": domain,
        "error": None,
        "error_category": None,
        "created": False,
        "repo_existed": False,
        "url": None,
        "repo_url": None,
        "https_pending": False,
        "dns_pending": False,
        # None = DNS was configured (or run was dry); otherwise why it was skipped:
        # "repo-existed" | "skip-dns" | "ns-mismatch"
        "dns_skipped": None,
    }

    log_format = get_log_format()

    def log(message: str, level: str = "info") -> None:
        """Print to console in verbose/text mode and emit structured log."""
        _emit(level, message, domain=domain)

        if verbose and log_format == "text":
            if level == "error":
                click.secho(f"  ✗ {message}", fg="red")
            elif level == "warning":
                click.secho(f"  ⚠ {message}", fg="yellow")
            elif level == "success":
                click.secho(f"  ✓ {message}", fg="green")
            else:
                click.echo(f"  {message}")

    if dry_run:
        log("Would verify domain is registered in this Porkbun account")
        if force:
            log(
                f"Would delete and recreate {cfg.github_username}/{domain} from template '{template}'"
            )
        else:
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
        result["url"] = f"https://{domain}"
        result["repo_url"] = f"https://github.com/{cfg.github_username}/{domain}"
        return result

    # Verify domain ownership before touching anything. If the domain isn't
    # registered in this Porkbun account, create must do nothing else --
    # no repo, no Pages config, no CNAME write.
    log("Verifying domain ownership")
    with PorkbunRegistrar(cfg.porkbun_api_key, cfg.porkbun_secret) as registrar:
        if not registrar.domain_exists(domain):
            raise RegistrarError(
                f"{domain} is not registered in this Porkbun account -- refusing to create"
            )
    log("Domain ownership verified", "success")

    # Deploy to GitHub Pages
    log("Configuring GitHub repository")
    dns_records = None
    try:
        with GitHubHost(default_org=cfg.github_username) as host:
            deploy = host.deploy_site(domain, template=template, force=force)
            dns_records = host.required_dns_records(domain)
            result["url"] = deploy.url
            result["repo_url"] = f"https://github.com/{cfg.github_username}/{domain}"
            result["created"] = deploy.repo_created
            result["repo_existed"] = deploy.repo_existed

            if deploy.repo_created and deploy.repo_existed:
                log(f"Repository replaced: {cfg.github_username}/{domain}", "success")
            elif deploy.repo_created:
                log(
                    f"Repository created from template '{template}': {cfg.github_username}/{domain}",
                    "success",
                )
            else:
                log(f"Repository already exists: {cfg.github_username}/{domain}", "warning")
                log("Use 'mimeo create --force' to replace it with a different template", "warning")

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
        result["dns_skipped"] = "skip-dns"
        return result

    if not deploy.repo_created:
        log(
            "Repository already existed and was not replaced -- skipping DNS configuration",
            "info",
        )
        result["dns_pending"] = True
        result["dns_skipped"] = "repo-existed"
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
                log("Use 'mimeo sync' to fix DNS records once nameservers are correct", "warning")
                result["dns_pending"] = True
                result["dns_skipped"] = "ns-mismatch"
                result["ns_mismatch"] = ns_result.actual
            else:
                with PorkbunDNSProvider(cfg.porkbun_api_key, cfg.porkbun_secret) as dns:
                    for record in dns_records or []:
                        record_name = record.name or "@"
                        log(f"Creating {record.type} record: {record_name} -> {record.content}")

                    dns.configure_dns(domain, dns_records or [])
                    log("DNS records created", "success")
                    log("Run 'mimeo status' to confirm DNS propagation", "info")

    except RegistrarError as e:
        log(f"DNS configuration failed: {e}", "error")
        log("Site deployed but DNS not configured", "warning")
        result["dns_pending"] = True
        result["error_category"] = "partial"

    return result


@click.command()
@click.argument("domains", nargs=-1)
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
@click.option(
    "--force",
    is_flag=True,
    help="Replace an existing repository's content with the template",
)
@click.option(
    "--yes",
    is_flag=True,
    help="Skip confirmation prompt (only relevant with --force)",
)
@click.pass_context
def create(
    ctx: click.Context,
    domains: tuple[str, ...],
    config: Path | None,
    dry_run: bool,
    sequential: bool,
    workers: int,
    template: str,
    skip_dns: bool,
    force: bool,
    yes: bool,
) -> None:
    """Create and deploy new sites for one or more domains.

    Provisions a GitHub repository from a template, enables GitHub Pages,
    configures custom domain, and sets up DNS records.

    If a repository already exists, it is left unchanged. Use --force to
    replace an existing repository's content with a different template
    instead. WARNING: --force deletes the existing repository and recreates
    it from the template -- all existing content, issues, and history will
    be lost. DNS records are also reconfigured (existing managed records are
    deleted and recreated), unless --skip-dns is also passed.

    Multiple domains are processed concurrently for faster provisioning.

    \b
    Examples:
        mimeo create example.com
        mimeo create site1.com site2.com site3.com
        mimeo create example.com --dry-run
        mimeo create site1.com site2.com --sequential
        mimeo create example.com --skip-dns
        mimeo create example.com --template mimeo.lol --force
        mimeo create site1.com site2.com --template new-theme --force --yes
    """
    if not domains:
        click.echo(ctx.get_help())
        ctx.exit(2)

    validate_domains(domains)
    cfg = load_config(config)
    log_format = get_log_format()

    with GitHubHost(default_org=cfg.github_username) as host:
        try:
            host.validate_template(template)
        except Exception as e:
            click.secho(str(e), fg="red", err=True)
            raise SystemExit(1)

    if force and not dry_run and not yes:
        click.secho(
            "WARNING: This will delete and recreate the following repositories:",
            fg="red",
            bold=True,
        )
        for d in domains:
            click.echo(f"  - {cfg.github_username}/{d}")
        click.echo()
        click.secho("All existing content, issues, and history will be lost.", fg="red")
        click.echo()
        if not click.confirm("Continue?"):
            click.echo("Aborted.")
            return

    if dry_run:
        click.secho("DRY RUN MODE - No changes will be made", fg="cyan", bold=True)
        click.echo()

    verbose = dry_run or sequential or len(domains) == 1

    def _create_domain(domain: str) -> Dict[str, Any]:
        return _process_single_domain(
            domain,
            cfg,
            dry_run,
            verbose=verbose,
            skip_dns=skip_dns,
            template=template,
            force=force,
        )

    def _create_domain_with_progress(domain: str) -> Dict[str, Any]:
        """Parallel runs suppress step logs; announce start and outcome instead.

        Without this, a multi-domain run prints nothing between the
        confirmation prompt and the recap -- indistinguishable from a hang.
        """
        click.echo(f"Creating {domain}...")
        try:
            result = _create_domain(domain)
        except BaseException as exc:
            click.secho(f"✗ {domain}: {exc}", fg="red")
            raise
        if result.get("repo_existed") and not result.get("created"):
            click.secho(f"⚠ {domain}: already existed, left unchanged", fg="yellow")
        else:
            click.secho(f"✓ {domain} created", fg="green")
        return result

    def _on_error(domain: str, exc: BaseException) -> Dict[str, Any]:
        _, category = _categorize_error(exc)
        return {
            "domain": domain,
            "error": str(exc),
            "error_category": category,
            "url": None,
            "repo_url": None,
            "https_pending": False,
            "dns_pending": False,
        }

    def _headline(results: List[Dict[str, Any]]) -> tuple[str, str]:
        """Honest one-line outcome: only actual creations count as created."""
        total = len(results)
        failed = sum(1 for r in results if r.get("error"))
        created = sum(1 for r in results if not r.get("error") and r.get("created"))
        existed = sum(
            1
            for r in results
            if not r.get("error") and r.get("repo_existed") and not r.get("created")
        )
        if dry_run:
            return f"DRY RUN: would process {total} domains", "cyan"
        parts = []
        if existed:
            parts.append(f"{existed} already existed")
        if failed:
            parts.append(f"{failed} failed")
        text = f"Created {created}/{total} domains" + (f" ({', '.join(parts)})" if parts else "")
        color = "red" if failed == total else ("green" if not parts else "yellow")
        return text, color

    def _text(results: List[Dict[str, Any]]) -> None:
        text, color = _headline(results)
        click.echo()
        click.secho(text, fg=color, bold=True)
        click.echo()

        for result in results:
            domain = result["domain"]
            if result.get("error"):
                click.secho(f"✗ {domain}", fg="red", bold=True)
                click.secho(f"  {result.get('error', 'Unknown error')}", fg="red")
            else:
                if result.get("repo_existed") and not result.get("created"):
                    click.secho(f"⚠ {domain}", fg="yellow", bold=True)
                    click.secho(
                        "  Already exists, left unchanged"
                        " (use 'mimeo create --force' to replace it)",
                        fg="yellow",
                    )
                else:
                    click.secho(f"✓ {domain}", fg="green", bold=True)
                    if result.get("repo_existed"):
                        click.echo("  Replaced existing repository")
                if not dry_run:
                    click.echo(f"  URL: {result.get('url', 'N/A')}")
                    click.echo(f"  Repository: {result.get('repo_url', 'N/A')}")
                    if result.get("https_pending"):
                        click.secho("  HTTPS: Pending SSL certificate", fg="yellow")
                    dns_reason = result.get("dns_skipped")
                    if dns_reason == "repo-existed":
                        click.secho("  DNS: not configured (repository already existed)", fg="yellow")
                    elif dns_reason == "skip-dns":
                        click.secho("  DNS: not configured (--skip-dns)", fg="yellow")
                    elif dns_reason == "ns-mismatch":
                        click.secho("  DNS: pending nameserver fix (run 'mimeo sync')", fg="yellow")
                    elif result.get("dns_pending"):
                        click.secho("  DNS: Propagation pending", fg="yellow")
            click.echo()

    def _json_summary(results: List[Dict[str, Any]]) -> None:
        summary_msg, _ = _headline(results)
        _emit("info", summary_msg)
        for result in results:
            level = "info" if not result.get("error") else "error"
            _emit(
                level,
                "success" if not result.get("error") else result.get("error", "unknown error"),
                domain=result["domain"],
            )

    results = map_items(
        domains,
        _create_domain_with_progress if (not verbose and log_format == "text") else _create_domain,
        workers=workers,
        sequential=(dry_run or sequential or len(domains) == 1),
        on_error=_on_error,
    )

    if log_format == "json":
        _json_summary(results)
    else:
        render_results(
            results,
            "text",
            csv_fields=[
                "domain",
                "created",
                "repo_existed",
                "url",
                "repo_url",
                "https_pending",
                "dns_pending",
                "dns_skipped",
                "error",
            ],
            text=_text,
        )
    exit_on_errors(results)
