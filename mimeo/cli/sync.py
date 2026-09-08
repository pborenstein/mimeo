"""Sync command: converge domains on their desired state."""

import sys
from pathlib import Path
from typing import Any, Dict, List

import click

from ..exceptions import EXIT_CONFIG
from ..providers.host.github import GitHubHost, health_status
from ..providers.registrar.porkbun import PorkbunDNSProvider, PorkbunRegistrar
from ._processing import (
    _categorize_error,
    exit_on_errors,
    load_config,
    map_items,
    render_results,
    validate_domains,
)


def _text(rows: List[Dict[str, Any]]) -> None:
    if not rows:
        click.echo("Nothing to sync.")
        return

    domain_w = max(max(len(r["domain"]) for r in rows), len("DOMAIN"))

    click.echo()
    changed = 0
    skipped = 0
    errors = 0
    for row in rows:
        click.echo(f"  {row['domain']:<{domain_w}}  ", nl=False)
        if row.get("error"):
            errors += 1
            click.secho(f"error: {row['error']}", fg="red")
        elif row.get("skipped"):
            skipped += 1
            click.secho(f"skipped: {row['skipped']}", fg="yellow")
        elif row["actions"]:
            changed += 1
            click.secho(", ".join(row["actions"]), fg="cyan")
        else:
            click.secho("ok", fg="green")

    click.echo()
    color = "green" if errors == 0 else "yellow"
    click.secho(
        f"{len(rows)} domain(s): {changed} changed, "
        f"{len(rows) - changed - skipped - errors} already ok, "
        f"{skipped} skipped, {errors} errors",
        fg=color,
    )
    click.echo()


@click.command()
@click.argument("domains", nargs=-1)
@click.option(
    "--all",
    "sync_all",
    is_flag=True,
    help="Sync every domain in the fleet (required when no domains are given)",
)
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
def sync(
    domains: tuple[str, ...],
    sync_all: bool,
    config: Path | None,
    output_format: str,
    reset_nameservers: bool,
    dry_run: bool,
    workers: int,
) -> None:
    """Converge domains on their desired state.

    For each domain that is registered in Porkbun and has a mimeo repo:
    applies missing DNS records for GitHub Pages and enables HTTPS
    enforcement when the certificate is ready. Reports (but does not act
    on) anything else.

    This command changes DNS records and repository settings. Because of
    that, syncing the whole fleet requires an explicit --all; naming
    domains is always allowed.

    \b
    What sync will NOT do:
      - create repositories (use: mimeo create)
      - change site content (use: mimeo create --force)
      - delete DNS records it does not manage (extra records are
        reported by mimeo status but left alone)
      - touch nameservers unless --reset-nameservers is given
      - wait for DNS propagation (run mimeo status afterwards to
        confirm, or mimeo dns repair for a single verified fix)

    \b
    Examples:
        mimeo sync example.com
        mimeo sync --all --dry-run
        mimeo sync --all
        mimeo sync site1.com site2.com --reset-nameservers
    """
    if domains and sync_all:
        click.secho("Give either domain names or --all, not both.", fg="red", err=True)
        sys.exit(EXIT_CONFIG)
    if not domains and not sync_all:
        click.secho(
            "Refusing to sync the whole fleet implicitly. "
            "Name the domains to sync, or pass --all (try --all --dry-run first).",
            fg="red",
            err=True,
        )
        sys.exit(EXIT_CONFIG)
    if domains:
        validate_domains(domains)

    if dry_run and output_format == "text":
        click.secho("DRY RUN MODE - No changes will be made", fg="cyan", bold=True)

    would = "would " if dry_run else ""

    try:
        cfg = load_config(config)
        owner = cfg.github_username

        with GitHubHost(default_org=owner) as host, \
                PorkbunRegistrar(cfg.porkbun_api_key, cfg.porkbun_secret) as registrar, \
                PorkbunDNSProvider(cfg.porkbun_api_key, cfg.porkbun_secret) as dns_provider:

            registered = {d.get("domain", "") for d in registrar.list_domains()}
            repo_names = {r.get("name", "") for r in host.list_mimeo_repositories()}

            if domains:
                targets = list(domains)
            else:
                # Explicitly named domains are always synced; the config
                # ignore list only trims fleet-wide runs.
                ignored = (registered | repo_names) & set(cfg.ignore_domains)
                targets = sorted((registered | repo_names) - ignored)
                if ignored:
                    click.secho(
                        f"({len(ignored)} domain(s) ignored per config: "
                        f"{', '.join(sorted(ignored))})",
                        fg="white",
                        dim=True,
                        err=True,
                    )

            def _sync_domain(domain: str) -> Dict[str, Any]:
                row: Dict[str, Any] = {
                    "domain": domain,
                    "actions": [],
                    "skipped": None,
                    "error": None,
                }

                if domain not in registered:
                    row["skipped"] = "not in Porkbun account"
                    return row
                if domain not in repo_names:
                    row["skipped"] = "no repo (use: mimeo create)"
                    return row

                try:
                    ns_result = registrar.check_nameservers(domain)
                    if not ns_result.ok:
                        actual = ", ".join(ns_result.actual) if ns_result.actual else "unknown"
                        if not reset_nameservers:
                            row["skipped"] = (
                                f"nameservers point to {actual} -- "
                                "use --reset-nameservers to fix"
                            )
                            return row
                        if not dry_run:
                            registrar.update_nameservers(domain)
                        row["actions"].append(f"{would}reset nameservers to Porkbun")

                    expected = host.required_dns_records(domain)
                    drift = dns_provider.check_dns_drift(domain, expected)
                    if drift["missing"]:
                        if not dry_run:
                            dns_provider.configure_dns(domain, expected)
                        row["actions"].append(
                            f"{would}apply {len(drift['missing'])} missing DNS record(s)"
                        )

                    health = host.get_pages_health(f"{owner}/{domain}")
                    if health_status(health) == "fixable":
                        if not dry_run:
                            host.enable_https_enforcement(f"{owner}/{domain}")
                        row["actions"].append(f"{would}enable HTTPS enforcement")
                except Exception as exc:
                    _, category = _categorize_error(exc)
                    row["error"] = str(exc)
                    row["error_category"] = category

                return row

            def _on_error(domain: str, exc: BaseException) -> Dict[str, Any]:
                _, category = _categorize_error(exc)
                return {
                    "domain": domain,
                    "actions": [],
                    "skipped": None,
                    "error": str(exc),
                    "error_category": category,
                }

            results = map_items(
                targets,
                _sync_domain,
                workers=workers,
                sequential=dry_run,
                on_error=_on_error,
            )

        def _csv_rows(row: Dict[str, Any]) -> List[Dict[str, Any]]:
            flat = dict(row)
            flat["actions"] = "|".join(row["actions"])
            return [flat]

        render_results(
            results,
            output_format,
            csv_fields=["domain", "actions", "skipped", "error"],
            csv_rows=_csv_rows,
            text=_text,
        )
        exit_on_errors(results)

    except Exception as e:
        exit_code, category = _categorize_error(e)
        click.secho(f"[{category}] {e}", fg="red", err=True)
        sys.exit(exit_code)
