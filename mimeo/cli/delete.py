"""Delete command for tearing down sites."""

from pathlib import Path
from typing import Any, Dict, List

import click

from ..exceptions import (
    HostError,
    RegistrarError,
)
from ..providers.host.github import GitHubHost
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
    keep_repo: bool = False,
) -> Dict[str, Any]:
    """Process a single domain teardown.

    Host side first (reverse of create): the repository goes -- or its
    Pages configuration, with --keep-repo -- then the managed DNS
    records. DNS cleanup only runs when the host side succeeded: with
    the repository still alive, removing records would break a site the
    user asked to remove, which is a different (unrequested) state.

    Args:
        domain: Domain name to process
        cfg: Configuration object
        dry_run: If True, don't delete anything
        verbose: If True, print per-step logs
        keep_repo: If True, keep the repository and disable Pages only

    Returns:
        Dictionary with result information. Raises on hard failure so
        map_items can route it through on_error.
    """
    result: Dict[str, Any] = {
        "domain": domain,
        "error": None,
        "error_category": None,
        "repo_deleted": False,
        "repo_existed": True,
        "pages_disabled": False,
        "records_removed": 0,
        # None = records were removed (or run was dry); otherwise why they
        # were left: "not-registered"
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
        if keep_repo:
            log(f"Would keep repository: {cfg.github_username}/{domain}")
            log("Would disable GitHub Pages (custom domain removed with it)")
        else:
            log(f"Would delete repository: {cfg.github_username}/{domain}")
            log("  (Pages site and custom domain go with it; content, issues, and history are lost)")
        log("Would remove managed DNS records (if the zone is in this Porkbun account):")
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
        log("Would NOT touch the domain registration or nameservers")
        return result

    # Host side first: deleting the repository takes Pages and the custom
    # domain with it; with --keep-repo, disabling Pages stops the site.
    log("Tearing down GitHub side")
    dns_records = None
    try:
        with GitHubHost(
            default_org=cfg.github_username, template_org=cfg.template_org
        ) as host:
            teardown = host.teardown_site(domain, delete_repository=not keep_repo)
            dns_records = host.required_dns_records(domain)
            result["repo_deleted"] = teardown["repo_deleted"]
            result["repo_existed"] = teardown["repo_existed"]
            result["pages_disabled"] = teardown["pages_disabled"]

            if keep_repo:
                if teardown["pages_disabled"]:
                    log("GitHub Pages disabled", "success")
                else:
                    log("GitHub Pages was not enabled", "warning")
            elif teardown["repo_deleted"]:
                log(f"Repository deleted: {teardown['repo_full_name']}", "success")
            else:
                log(f"No repository found: {teardown['repo_full_name']}", "warning")
    except HostError as e:
        log(f"GitHub teardown failed: {e}", "error")
        raise

    # DNS side: delete exactly the records create/sync would manage.
    log("Removing managed DNS records")
    try:
        with PorkbunRegistrar(cfg.porkbun_api_key, cfg.porkbun_secret) as registrar:
            if not registrar.domain_exists(domain):
                log(
                    f"{domain} is not registered in this Porkbun account -- skipping DNS cleanup",
                    "warning",
                )
                result["dns_skipped"] = "not-registered"
            else:
                with PorkbunDNSProvider(cfg.porkbun_api_key, cfg.porkbun_secret) as dns:
                    for record in dns_records or []:
                        record_name = record.name or "@"
                        log(f"Removing {record.type} record: {record_name} -> {record.content}")
                    removed = dns.remove_dns_records(domain, dns_records or [])
                    result["records_removed"] = removed
                    if removed:
                        log(f"Removed {removed} DNS records", "success")
                    else:
                        log("No managed DNS records found", "info")

    except RegistrarError as e:
        log(f"DNS cleanup failed: {e}", "error")
        result["error"] = f"DNS cleanup failed: {e}"
        result["error_category"] = _categorize_error(e)[1]

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
    help="Show what would be deleted without actually deleting anything",
)
@click.option(
    "--keep-repo",
    is_flag=True,
    help="Keep the repository (disable GitHub Pages only); DNS records are still removed",
)
@click.option(
    "--yes",
    is_flag=True,
    help="Skip confirmation prompt",
)
@click.pass_context
def delete(
    ctx: click.Context,
    domains: tuple[str, ...],
    config: Path | None,
    dry_run: bool,
    keep_repo: bool,
    yes: bool,
) -> None:
    """Tear down deployed sites.

    Deletes each site's GitHub repository (Pages site and custom domain go
    with it) and removes the managed DNS records (GitHub Pages A/CNAME) from
    Porkbun. With --keep-repo, the repository is spared and only its Pages
    configuration is disabled. The domain registration and nameservers are
    never touched -- use 'mimeo create' to rebuild the site.

    Domains must be named explicitly; there is no fleet-wide mode.

    \b
    Examples:
        mimeo delete example.com
        mimeo delete 002371.xyz --yes
        mimeo delete example.com --keep-repo
        mimeo delete example.com --dry-run
    """
    if not domains:
        click.echo(ctx.get_help())
        ctx.exit(2)

    validate_domains(domains)
    cfg = load_config(config)
    log_format = get_log_format()

    if not dry_run and not yes:
        if keep_repo:
            click.secho(
                "This will stop the following sites from serving:", fg="yellow", bold=True
            )
            for d in domains:
                click.echo(
                    f"  - {d} (repository kept, GitHub Pages disabled,"
                    " managed DNS records removed)"
                )
        else:
            click.secho(
                "WARNING: This will permanently delete the following repositories:",
                fg="red",
                bold=True,
            )
            for d in domains:
                click.echo(f"  - {cfg.github_username}/{d}")
            click.echo()
            click.secho(
                "Pages sites and custom domains go with them -- all content,"
                " issues, and history will be lost. Managed DNS records"
                " (GitHub Pages A/CNAME) will be removed from Porkbun.",
                fg="red",
            )
        click.echo()
        click.echo("Domain registrations are NOT touched.")
        click.echo()
        if not click.confirm("Continue?"):
            click.echo("Aborted.")
            return

    if dry_run:
        click.secho("DRY RUN MODE - No changes will be made", fg="cyan", bold=True)
        click.echo()

    def _delete_domain(domain: str) -> Dict[str, Any]:
        return _process_single_domain(
            domain,
            cfg,
            dry_run,
            verbose=True,
            keep_repo=keep_repo,
        )

    def _on_error(domain: str, exc: BaseException) -> Dict[str, Any]:
        _, category = _categorize_error(exc)
        return {
            "domain": domain,
            "error": str(exc),
            "error_category": category,
            "repo_deleted": False,
            "repo_existed": True,
            "pages_disabled": False,
            "records_removed": 0,
            "dns_skipped": None,
        }

    def _headline(results: List[Dict[str, Any]]) -> tuple[str, str]:
        """Honest one-line outcome: teardowns that hit nothing don't count."""
        total = len(results)
        failed = sum(1 for r in results if r.get("error"))
        deleted = sum(
            1
            for r in results
            if not r.get("error") and (r.get("repo_deleted") or r.get("pages_disabled"))
        )
        if dry_run:
            return f"DRY RUN: would process {total} domains", "cyan"
        parts = []
        if total - failed - deleted:
            parts.append(f"{total - failed - deleted} nothing to delete")
        if failed:
            parts.append(f"{failed} failed")
        text = f"Deleted {deleted}/{total} domains" + (f" ({', '.join(parts)})" if parts else "")
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
                continue
            torn_down = result.get("repo_deleted") or result.get("pages_disabled")
            if torn_down:
                click.secho(f"✓ {domain}", fg="green", bold=True)
            else:
                click.secho(f"⚠ {domain}", fg="yellow", bold=True)
                click.secho("  Nothing to delete (no repository, Pages not enabled)", fg="yellow")
            if not dry_run:
                if keep_repo:
                    if result.get("pages_disabled"):
                        click.echo("  GitHub Pages: disabled")
                    else:
                        click.echo("  GitHub Pages: was not enabled")
                    click.echo("  Repository: kept (--keep-repo)")
                elif result.get("repo_deleted"):
                    click.echo("  Repository: deleted")
                else:
                    click.echo("  Repository: not found")
                if result.get("dns_skipped") == "not-registered":
                    click.secho("  DNS: not in Porkbun account -- nothing removed", fg="yellow")
                else:
                    click.echo(f"  DNS: {result.get('records_removed', 0)} managed records removed")
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
        _delete_domain,
        sequential=True,
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
                "repo_deleted",
                "repo_existed",
                "pages_disabled",
                "records_removed",
                "dns_skipped",
                "error",
            ],
            text=_text,
        )
    exit_on_errors(results)
