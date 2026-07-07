"""Status command: cross-provider view of the whole fleet."""

import sys
from pathlib import Path
from typing import Any, Dict, List

import click

from ..providers.host.github import GitHubHost, health_status
from ..providers.registrar.porkbun import PorkbunDNSProvider, PorkbunRegistrar
from ..exceptions import EXIT_CONFIG
from ._processing import (
    _categorize_error,
    exit_on_errors,
    load_config,
    map_items,
    render_results,
    validate_domains,
)

_CSV_FIELDS = [
    "domain",
    "registered",
    "expires",
    "auto_renew",
    "ns_ok",
    "repo",
    "dns_status",
    "site_health",
    "https_enforced",
    "cert_state",
    "error",
]

_DNS_COLORS = {"ok": "green", "drift": "yellow", "missing": "red", "error": "red"}
_SITE_COLORS = {
    "healthy": "green",
    "fixable": "yellow",
    "cert_pending": "yellow",
    "no_cert": "red",
    "pages_error": "red",
}
_SITE_LABELS = {
    "healthy": "ok",
    "fixable": "fixable",
    "cert_pending": "pending",
    "no_cert": "no cert",
    "pages_error": "error",
}


def _has_problem(row: Dict[str, Any]) -> bool:
    """True when anything about the domain needs attention."""
    if row.get("error"):
        return True
    if not row["registered"] or not row["repo"]:
        return True
    if not row["ns_ok"]:
        return True
    if row["dns_status"] not in ("ok", None):
        return True
    if row["site_health"] not in ("healthy", None):
        return True
    return False


def _text(rows: List[Dict[str, Any]], with_dns: bool = False) -> None:
    if not rows:
        click.echo("Nothing to report.")
        return

    domain_w = max(max(len(r["domain"]) for r in rows), len("DOMAIN"))
    expires_w = max(max(len(r["expires"] or "-") for r in rows), len("EXPIRES"))

    click.echo()
    header = f"  {'DOMAIN':<{domain_w}}  {'EXPIRES':<{expires_w}}  {'NS':<4}  {'DNS':<8}  SITE"
    click.secho(header, bold=True)
    click.secho("  " + "-" * (len(header) - 2), fg="white", dim=True)

    problems = 0
    for row in rows:
        if _has_problem(row):
            problems += 1

        click.echo(f"  {row['domain']:<{domain_w}}  ", nl=False)

        expires = (row["expires"] or "-")[:10] if row["registered"] else "-"
        click.echo(f"{expires:<{expires_w}}  ", nl=False)

        if not row["registered"]:
            click.secho(f"{'-':<4}", fg="red", nl=False)
        elif row["ns_ok"]:
            click.secho(f"{'ok':<4}", fg="green", nl=False)
        else:
            click.secho(f"{'no':<4}", fg="red", nl=False)
        click.echo("  ", nl=False)

        dns_status = row["dns_status"]
        if dns_status is None:
            click.echo(f"{'-':<8}", nl=False)
        else:
            click.secho(f"{dns_status:<8}", fg=_DNS_COLORS.get(dns_status, "white"), nl=False)
        click.echo("  ", nl=False)

        if not row["repo"]:
            click.secho("no repo", fg="red" if row["registered"] else "white", nl=False)
        else:
            site = row["site_health"] or "pages_error"
            click.secho(
                _SITE_LABELS.get(site, site), fg=_SITE_COLORS.get(site, "white"), nl=False
            )

        if row.get("error"):
            click.secho(f"  [{row['error']}]", fg="red", nl=False)
        click.echo()

        if with_dns and row.get("dns_records"):
            recs = row["dns_records"]
            type_w = max(len(r.get("type", "")) for r in recs)
            name_w = max(len(r.get("name", "")) for r in recs)
            ttl_w = max(len(str(r.get("ttl", ""))) for r in recs)
            for rec in recs:
                click.secho(
                    f"      {rec.get('type',''):<{type_w}}  {rec.get('name',''):<{name_w}}  "
                    f"{str(rec.get('ttl','')):<{ttl_w}}  {rec.get('content','')}",
                    dim=True,
                )

    click.echo()
    color = "green" if problems == 0 else "yellow"
    click.secho(f"{len(rows)} domain(s), {problems} with issues", fg=color)
    click.echo()


@click.command()
@click.argument("domains", nargs=-1)
@click.option(
    "--all",
    "status_all",
    is_flag=True,
    help="Report on every domain in the fleet (required when no domains are given)",
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
    "--workers",
    type=click.IntRange(min=1),
    default=5,
    show_default=True,
    help="Maximum number of concurrent workers",
)
@click.option(
    "--problems",
    is_flag=True,
    help="Show only domains that need attention",
)
@click.option(
    "--with-dns",
    is_flag=True,
    help="Include the full live DNS records for each registered domain",
)
def status(
    domains: tuple[str, ...],
    status_all: bool,
    config: Path | None,
    output_format: str,
    workers: int,
    problems: bool,
    with_dns: bool,
) -> None:
    """Show fleet status: registrar, DNS, and site health in one view.

    Joins the Porkbun account against mimeo-managed GitHub repositories.
    With --all, covers the union of both: registered domains with no
    site show as "no repo"; sites whose domain is not in the account
    show "-" on the registrar side. A fleet sweep makes several API
    calls per domain, so it takes a while on large accounts — name
    domains for a quick check.

    \b
    Columns:
        EXPIRES  registration expiry ("-" if not in Porkbun account)
        NS       nameservers point to Porkbun
        DNS      live records vs GitHub Pages expectations
                 ("-" when there is no repo: no desired state to compare)
        SITE     Pages health (ok / fixable / pending / no cert / error)

    \b
    Examples:
        mimeo status example.com           # one domain
        mimeo status --all                 # whole fleet (takes a while)
        mimeo status --all --problems      # only what needs attention
        mimeo status --all --format json | jq '.[] | select(.dns_status == "drift")'
        mimeo status example.com --with-dns --format json | jq '.[0].dns_records'
    """
    if domains and status_all:
        click.secho("Give either domain names or --all, not both.", fg="red", err=True)
        sys.exit(EXIT_CONFIG)
    if not domains and not status_all:
        click.secho(
            "A whole-fleet sweep takes several API calls per domain. "
            "Name the domains to check, or pass --all to do the full fleet.",
            fg="red",
            err=True,
        )
        sys.exit(EXIT_CONFIG)
    if domains:
        validate_domains(domains)

    try:
        cfg = load_config(config)
        owner = cfg.github_username

        with GitHubHost(default_org=owner) as host, \
                PorkbunRegistrar(cfg.porkbun_api_key, cfg.porkbun_secret) as registrar, \
                PorkbunDNSProvider(cfg.porkbun_api_key, cfg.porkbun_secret) as dns_provider:

            registered_map: Dict[str, Dict[str, Any]] = {
                d.get("domain", ""): d for d in registrar.list_domains()
            }
            repo_names = {r.get("name", "") for r in host.list_mimeo_repositories()}

            if domains:
                targets = list(domains)
            else:
                targets = sorted(set(registered_map) | repo_names)

            def _status_row(domain: str) -> Dict[str, Any]:
                info = registered_map.get(domain)
                row: Dict[str, Any] = {
                    "domain": domain,
                    "registered": info is not None,
                    "expires": info.get("expireDate", "") if info else "",
                    "auto_renew": info.get("autoRenew") in ("1", 1, True) if info else None,
                    "ns_ok": None,
                    "nameservers": [],
                    "repo": domain in repo_names,
                    "dns_status": None,
                    "missing": [],
                    "extra": [],
                    "site_health": None,
                    "https_enforced": None,
                    "cert_state": None,
                    "dns_records": [],
                    "error": None,
                }

                try:
                    if row["registered"]:
                        ns_result = registrar.check_nameservers(domain)
                        row["ns_ok"] = ns_result.ok
                        row["nameservers"] = ns_result.actual

                    live_records = None
                    if with_dns and row["registered"]:
                        live_records = dns_provider.get_domain_records(domain)
                        row["dns_records"] = live_records

                    if row["repo"]:
                        health = host.get_pages_health(f"{owner}/{domain}")
                        row["site_health"] = health_status(health)
                        row["https_enforced"] = health["https_enforced"]
                        row["cert_state"] = health["cert_state"]

                        if row["registered"]:
                            expected = host.required_dns_records(domain)
                            drift = dns_provider.check_dns_drift(
                                domain, expected, live_records=live_records
                            )
                            row["dns_status"] = drift["status"]
                            row["missing"] = drift.get("missing", [])
                            row["extra"] = drift.get("extra", [])
                except Exception as exc:
                    _, category = _categorize_error(exc)
                    row["error"] = str(exc)
                    row["error_category"] = category

                return row

            def _on_error(domain: str, exc: BaseException) -> Dict[str, Any]:
                _, category = _categorize_error(exc)
                return {
                    "domain": domain,
                    "registered": domain in registered_map,
                    "expires": "",
                    "auto_renew": None,
                    "ns_ok": None,
                    "nameservers": [],
                    "repo": domain in repo_names,
                    "dns_status": None,
                    "missing": [],
                    "extra": [],
                    "site_health": None,
                    "https_enforced": None,
                    "cert_state": None,
                    "dns_records": [],
                    "error": str(exc),
                    "error_category": category,
                }

            results = map_items(targets, _status_row, workers=workers, on_error=_on_error)

        if problems:
            results = [r for r in results if _has_problem(r)]

        csv_fields = list(_CSV_FIELDS)
        csv_rows = None
        if with_dns:
            csv_fields.insert(-1, "dns_records")

            def csv_rows(row: Dict[str, Any]) -> List[Dict[str, Any]]:
                flat = dict(row)
                flat["dns_records"] = "|".join(
                    f"{r.get('type','')}:{r.get('name','')}={r.get('content','')}"
                    for r in row.get("dns_records") or []
                )
                return [flat]

        render_results(
            results,
            output_format,
            csv_fields=csv_fields,
            csv_rows=csv_rows,
            text=lambda rows: _text(rows, with_dns=with_dns),
        )
        exit_on_errors(results)

    except Exception as e:
        exit_code, category = _categorize_error(e)
        click.secho(f"[{category}] {e}", fg="red", err=True)
        sys.exit(exit_code)
