"""DNS commands for checking and repairing DNS records."""

from pathlib import Path
from typing import Any, Dict, List

import click

from ..providers.host.github import GitHubHost
from ..providers.registrar.porkbun import (
    PorkbunDNSProvider,
    PorkbunRegistrar,
)
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


@click.group()
def dns() -> None:
    """Check and repair DNS records."""
    pass


@dns.command()
@click.argument("domains", nargs=-1, required=True)
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    help="Path to config file (default: ~/.config/mimeo/config.toml)",
)
@click.option(
    "--reset-nameservers",
    is_flag=True,
    help="Reset nameservers to Porkbun when they point elsewhere",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be changed without making changes",
)
@click.option(
    "--workers",
    type=click.IntRange(min=1),
    default=5,
    show_default=True,
    help="Maximum number of concurrent workers",
)
def repair(
    domains: tuple[str, ...],
    config: Path | None,
    reset_nameservers: bool,
    dry_run: bool,
    workers: int,
) -> None:
    """Re-apply expected DNS records for one or more domains.

    Configures the DNS records needed for GitHub Pages without touching
    the GitHub repository or Pages configuration.

    Examples:
        mimeo dns repair example.com
        mimeo dns repair site1.com site2.com --reset-nameservers
        mimeo dns repair example.com --dry-run
    """
    validate_domains(domains)
    cfg = load_config(config)
    log_format = get_log_format()

    if dry_run:
        click.secho("DRY RUN MODE - No changes will be made", fg="cyan", bold=True)
        click.echo()

    verbose = dry_run or len(domains) == 1

    def _repair_domain(domain: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {"domain": domain, "error": None, "error_category": None}

        def log(message: str, level: str = "info") -> None:
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

        with GitHubHost(default_org=cfg.github_username) as host:
            dns_records = host.required_dns_records(domain)

        with PorkbunRegistrar(cfg.porkbun_api_key, cfg.porkbun_secret) as registrar:
            ns_result = registrar.check_nameservers(domain)

            if not ns_result.ok:
                actual_ns = ", ".join(ns_result.actual) if ns_result.actual else "unknown"
                if reset_nameservers:
                    if dry_run:
                        log(f"Would reset nameservers from {actual_ns} to Porkbun", "warning")
                    else:
                        log(
                            f"NS records point to {actual_ns} -- resetting to Porkbun",
                            "warning",
                        )
                        registrar.update_nameservers(domain)
                        log("Nameservers updated to Porkbun", "success")
                else:
                    log(
                        f"NS records point to {actual_ns}, not Porkbun -- use --reset-nameservers to fix",
                        "error",
                    )
                    result["error"] = f"NS mismatch: {actual_ns}"
                    result["error_category"] = "provider"
                    return result

        if dry_run:
            for record in dns_records:
                record_name = record.name or "@"
                log(f"Would create {record.type} record: {record_name} -> {record.content}")
            log("Would verify DNS propagation")
            return result

        with PorkbunDNSProvider(cfg.porkbun_api_key, cfg.porkbun_secret) as dns_prov:
            for record in dns_records:
                record_name = record.name or "@"
                log(f"Creating {record.type} record: {record_name} -> {record.content}")

            dns_prov.configure_dns(domain, dns_records)
            log("DNS records created", "success")

            log("Verifying DNS propagation")
            verified = dns_prov.verify_dns(
                domain,
                dns_records,
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

        return result

    def _on_error(domain: str, exc: BaseException) -> Dict[str, Any]:
        _, category = _categorize_error(exc)
        return {"domain": domain, "error": str(exc), "error_category": category}

    def _text(results: List[Dict[str, Any]]) -> None:
        success_count = sum(1 for r in results if not r.get("error"))
        total_count = len(results)
        click.echo()
        if dry_run:
            click.secho(f"DRY RUN: Would repair DNS for {total_count} domain(s)", fg="cyan")
        else:
            color = "green" if success_count == total_count else "yellow"
            click.secho(f"DNS repair: {success_count}/{total_count} succeeded", fg=color)
        click.echo()

    results = map_items(
        domains,
        _repair_domain,
        workers=workers,
        sequential=(dry_run or len(domains) == 1),
        on_error=_on_error,
    )

    render_results(
        results,
        "json" if log_format == "json" else "text",
        csv_fields=["domain", "error", "error_category"],
        text=_text,
    )
    exit_on_errors(results)
