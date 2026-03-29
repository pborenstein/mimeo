"""DNS commands for checking and repairing DNS records."""

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, cast

import click

from ..providers.host.github import GitHubHost
from ..providers.registrar.porkbun import PorkbunDNSProvider, PorkbunRegistrar
from ._processing import (
    _categorize_error,
    _emit,
    get_log_format,
    load_config,
    process_domains_concurrent,
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
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "csv"], case_sensitive=False),
    default="text",
    show_default=True,
    help="Output format",
)
@click.option(
    "--workers",
    type=click.IntRange(min=1),
    default=5,
    show_default=True,
    help="Maximum number of concurrent workers",
)
def check(domains: tuple[str, ...], config: Path | None, output_format: str, workers: int) -> None:
    """Check DNS records and nameserver configuration for drift.

    Compares expected DNS records (for GitHub Pages) against live records
    in Porkbun, and checks that nameservers point to Porkbun.

    Examples:
        mimeo dns check example.com
        mimeo dns check site1.com site2.com --format json
    """
    validate_domains(domains)
    try:
        cfg = load_config(config)
        results: List[Dict[str, Any]] = []

        with GitHubHost(default_org=cfg.github_username) as host:
            with PorkbunRegistrar(cfg.porkbun_api_key, cfg.porkbun_secret) as registrar:
                with PorkbunDNSProvider(cfg.porkbun_api_key, cfg.porkbun_secret) as dns_provider:

                    def _check_domain(domain: str) -> Dict[str, Any]:
                        expected = host.required_dns_records(domain)
                        ns_result = registrar.check_nameservers(domain)
                        try:
                            drift = dns_provider.check_dns_drift(domain, expected)
                        except Exception as exc:
                            drift = {
                                "status": "error",
                                "missing": [],
                                "extra": [],
                                "error": str(exc),
                            }

                        return {
                            "domain": domain,
                            "ns_ok": ns_result.ok,
                            "nameservers": ns_result.actual,
                            "dns_status": drift["status"],
                            "missing": drift.get("missing", []),
                            "extra": drift.get("extra", []),
                            "error": drift.get("error"),
                        }

                    if len(domains) == 1:
                        results.append(_check_domain(domains[0]))
                    else:
                        with ThreadPoolExecutor(max_workers=min(len(domains), workers)) as executor:
                            future_to_domain = {
                                executor.submit(_check_domain, d): d for d in domains
                            }
                            for future in as_completed(future_to_domain):
                                results.append(future.result())

        # Sort by original domain order
        domain_order = {d: i for i, d in enumerate(domains)}
        results.sort(key=lambda r: domain_order.get(r["domain"], 999))

        if output_format == "json":
            click.echo(json.dumps(results, indent=2))
        elif output_format == "csv":
            import csv

            fieldnames = ["domain", "ns_ok", "nameservers", "dns_status"]
            writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for row in results:
                flat = dict(row)
                flat["nameservers"] = "|".join(row.get("nameservers") or [])
                writer.writerow(flat)
        else:
            click.echo()
            _dns_colors = {"ok": "green", "drift": "yellow", "missing": "red", "error": "red"}
            _ns_colors = {True: "green", False: "red"}

            for r in results:
                click.secho(f"  {r['domain']}", bold=True)
                ns_label = (
                    "ok (porkbun)"
                    if r["ns_ok"]
                    else ", ".join(r["nameservers"])
                    if r["nameservers"]
                    else "unknown"
                )
                click.echo("    NS: ", nl=False)
                click.secho(ns_label, fg=_ns_colors.get(r["ns_ok"], "white"))

                click.echo("    DNS: ", nl=False)
                click.secho(r["dns_status"], fg=_dns_colors.get(r["dns_status"], "white"))

                for rec in r.get("missing", []):
                    click.secho(
                        f"      missing: {rec['type']} {rec['name']} -> {rec['content']}", fg="red"
                    )
                for rec in r.get("extra", []):
                    click.secho(
                        f"      extra:   {rec['type']} {rec['name']} -> {rec['content']}",
                        fg="yellow",
                    )
                if r.get("error"):
                    click.secho(f"      error: {r['error']}", fg="red")
                click.echo()

    except Exception as e:
        exit_code, category = _categorize_error(e)
        click.secho(f"[{category}] {e}", fg="red", err=True)
        sys.exit(exit_code)


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

    def _repair_domain(domain: str) -> dict:
        result: Dict[str, Any] = {
            "domain": domain,
            "success": False,
            "error": None,
            "error_category": None,
            "log": [],
        }

        verbose = dry_run or len(domains) == 1

        def log(message: str, level: str = "info") -> None:
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
                result["success"] = True
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

            result["success"] = True

        except Exception as e:
            exit_code, category = _categorize_error(e)
            result["error"] = f"[{category}] {e}"
            result["error_category"] = category
            log(str(result["error"]), "error")

        return result

    results = process_domains_concurrent(
        domains,
        _repair_domain,
        workers,
        sequential=(len(domains) == 1),
        stop_on_error=False,
        dry_run=dry_run,
    )

    # Summary
    success_count = sum(1 for r in results if r["success"])
    total_count = len(results)

    if log_format != "json":
        click.echo()
        if dry_run:
            click.secho(f"DRY RUN: Would repair DNS for {total_count} domain(s)", fg="cyan")
        else:
            color = "green" if success_count == total_count else "yellow"
            click.secho(f"DNS repair: {success_count}/{total_count} succeeded", fg=color)
        click.echo()

    from ._processing import exit_on_failures

    exit_on_failures(results)
