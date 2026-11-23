"""Status command: what connects each hostname to its site, and what is wrong."""

import sys
from pathlib import Path
from typing import Any, Dict, List

import click

from ..exceptions import EXIT_CONFIG
from ..plan import compare
from ._fleet import echo_problems, error_row, open_fleet, result_row, targets_for
from ._processing import (
    _categorize_error,
    exit_on_errors,
    load_config,
    map_items,
    render_results,
    validate_domains,
)

_CSV_FIELDS = [
    "hostname",
    "zone",
    "expires",
    "auto_renew",
    "dns",
    "proxied",
    "records",
    "site",
    "host",
    "source_repo",
    "site_status",
    "https_enforced",
    "cert_state",
    "cert_expires",
    "changes",
    "problems",
    "fixes",
    "notes",
    "error",
]

_RECORDS_COLORS = {
    "ok": "green",
    "missing": "red",
    "extra": "yellow",
    "external": "cyan",
    "netlify": "cyan",
    "unknown": "red",
}
_SITE_COLORS = {
    "ok": "green",
    "fixable": "yellow",
    "pending": "yellow",
    "expiring": "red",
    "no cert": "red",
    "cert error": "red",
    "no pages": "red",
    "no domain": "red",
}


def _dns_label(row: Dict[str, Any]) -> str:
    dns = row["dns"] or "-"
    return f"{dns}*" if row.get("proxied") else dns


def _registered_elsewhere(row: Dict[str, Any]) -> bool:
    """True for a hostname outside the registrar account that DNS answers for."""
    return row.get("registered") is False and bool(row.get("nameservers"))


def _repo_label(row: Dict[str, Any]) -> str:
    """The REPO column: the repository, marked when Netlify builds it."""
    if row.get("host") == "netlify":
        return f"{row.get('source_repo') or row['site']} (netlify)"
    return (row["site"] or "-").removeprefix("github:")


def _text(rows: List[Dict[str, Any]], detail: bool) -> None:
    if not rows:
        click.echo("Nothing to report.")
        return

    host_w = max(max(len(r["hostname"]) for r in rows), len("HOSTNAME"))
    dns_w = max(max(len(_dns_label(r)) for r in rows), len("DNS"))
    site_w = max(max(len(r["site_status"] or "no site") for r in rows), len("SITE"))

    click.echo()
    header = (
        f"  {'HOSTNAME':<{host_w}}  {'EXPIRES':<10}  {'RENEW':<5}  {'DNS':<{dns_w}}  "
        f"{'RECORDS':<8}  {'SITE':<{site_w}}  REPO"
    )
    click.secho(header, bold=True)
    click.secho("  " + "-" * (len(header) - 2), fg="white", dim=True)

    problems = 0
    fixable = 0
    proxied = False
    for row in rows:
        problems += bool(row["has_problem"])
        fixable += bool(row["fixable"])
        proxied = proxied or bool(row.get("proxied"))

        expires = row["expires"] or ("elsewhere" if _registered_elsewhere(row) else "-")
        click.echo(f"  {row['hostname']:<{host_w}}  {expires:<10}  ", nl=False)
        renewal_off = row.get("auto_renew") is False
        click.secho(f"{'off' if renewal_off else '':<5}", fg="yellow" if renewal_off else None, nl=False)
        click.echo("  ", nl=False)
        dns_color = {"external": "cyan", "none": "red"}.get(row["dns"] or "", None)
        click.secho(f"{_dns_label(row):<{dns_w}}", fg=dns_color, nl=False)
        click.echo("  ", nl=False)
        records = row["records"] or "-"
        click.secho(f"{records:<8}", fg=_RECORDS_COLORS.get(records), nl=False)
        click.echo("  ", nl=False)
        site = row["site_status"] or ("no site" if not row.get("error") else "-")
        click.secho(f"{site:<{site_w}}", fg=_SITE_COLORS.get(site), nl=False)
        click.echo(f"  {_repo_label(row)}", nl=False)
        if row.get("error"):
            click.secho(f"  [{row['error']}]", fg="red", nl=False)
        click.echo()

        if detail:
            for change in row["changes"]:
                click.secho(f"      sync would: {change}", fg="yellow")
            echo_problems(row, "red")
            for rec in row.get("zone_records") or []:
                flag = " (proxied)" if rec.get("proxied") else ""
                click.secho(
                    f"      {rec['type']:<6} {rec['name']:<20} {rec['content']}{flag}", dim=True
                )

    click.echo()
    summary = f"{len(rows)} hostname(s), {problems} with issues"
    if fixable:
        summary += f" ({fixable} fixable with: mimeo sync)"
    click.secho(summary, fg="green" if problems == 0 else "yellow")
    if not detail and any(row["problems"] for row in rows):
        click.echo("For what is wrong and the steps to fix each: mimeo status --all --problems")
    if proxied:
        click.secho("* records are proxied through the DNS provider", dim=True)
    click.echo()


@click.command()
@click.argument("hostnames", nargs=-1)
@click.option(
    "--all",
    "status_all",
    is_flag=True,
    help="Report on every registered domain and known site (required when no hostnames are given)",
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
@click.option("--problems", is_flag=True, help="Show only hostnames that need attention")
@click.option(
    "--records",
    "with_records",
    is_flag=True,
    help="Include every record in the zone, read from the provider that serves it",
)
def status(
    hostnames: tuple[str, ...],
    status_all: bool,
    config: Path | None,
    output_format: str,
    workers: int,
    problems: bool,
    with_records: bool,
) -> None:
    """Show what connects each hostname to its site, and what is wrong.

    For each hostname mimeo reads the registration, the nameservers, the
    DNS records at whichever configured provider the nameservers belong
    to, and the site whose custom domain is the hostname. It then lists
    the changes `mimeo sync` would make and the problems it cannot fix.
    Nothing is changed.

    \b
    Columns:
        EXPIRES  registration expiry ("-" for a subdomain or a hostname
                 whose domain is not at the registrar)
        RENEW    "off" when the registration will not renew automatically;
                 blank when it will, or when it does not apply
        DNS      the provider serving the zone: porkbun, cloudflare,
                 netlify, external (another provider; mimeo cannot read its
                 records), none (the registrar reports no nameservers).
                 A trailing * means the site's records are proxied.
        RECORDS  the site's address records against what the host needs:
                 ok, missing, extra, external, netlify (Netlify manages
                 them), unknown
        SITE     ok, fixable (certificate ready, HTTPS not enforced),
                 pending, no cert, cert error, expiring, no pages,
                 no site
        REPO     the repository whose custom domain is the hostname, or
                 the repository a Netlify site builds from, marked
                 (netlify). mimeo reads Netlify sites and never changes them.

    \b
    Examples:
        mimeo status example.com
        mimeo status service.example.com --records
        mimeo status --all
        mimeo status --all --problems
        mimeo status --all --format json | jq '.[] | select(.fixable)'
    """
    if hostnames and status_all:
        click.secho("Give either hostnames or --all, not both.", fg="red", err=True)
        sys.exit(EXIT_CONFIG)
    if not hostnames and not status_all:
        click.secho(
            "A whole-fleet sweep takes several API calls per hostname. "
            "Name the hostnames to check, or pass --all.",
            fg="red",
            err=True,
        )
        sys.exit(EXIT_CONFIG)
    if hostnames:
        validate_domains(hostnames)

    try:
        cfg = load_config(config)
        with open_fleet(cfg) as fleet:
            targets, search = targets_for(fleet, cfg, hostnames)

            def _row(hostname: str) -> Dict[str, Any]:
                conn = fleet.read(hostname, search=search)
                return result_row(conn, compare(conn, fleet.host), with_records=with_records)

            def _on_error(hostname: str, exc: BaseException) -> Dict[str, Any]:
                return error_row(hostname, exc, _categorize_error(exc)[1])

            results = map_items(targets, _row, workers=workers, on_error=_on_error)

        if problems:
            results = [r for r in results if r["has_problem"]]

        def _csv_rows(row: Dict[str, Any]) -> List[Dict[str, Any]]:
            flat = dict(row)
            flat["changes"] = "|".join(row["changes"])
            flat["problems"] = "|".join(row["problems"])
            flat["fixes"] = "|".join(row["fixes"])
            flat["notes"] = "|".join(row["notes"])
            return [flat]

        detail = bool(hostnames) or problems or with_records
        render_results(
            results,
            output_format,
            csv_fields=_CSV_FIELDS,
            csv_rows=_csv_rows,
            text=lambda rows: _text(rows, detail),
        )
        exit_on_errors(results)
    except Exception as e:
        exit_code, category = _categorize_error(e)
        click.secho(f"[{category}] {e}", fg="red", err=True)
        sys.exit(exit_code)
