"""Sync command: apply the changes status lists."""

import sys
from pathlib import Path
from typing import Any, Dict, List

import click

from ..exceptions import EXIT_CONFIG
from ..plan import apply, compare
from ._fleet import echo_problems, open_fleet, targets_for
from ._processing import (
    _categorize_error,
    exit_on_errors,
    load_config,
    map_items,
    render_results,
    validate_domains,
)


def _text(rows: List[Dict[str, Any]], dry_run: bool = False) -> None:
    if not rows:
        click.echo("Nothing to sync.")
        return

    host_w = max(len(r["hostname"]) for r in rows)
    click.echo()
    changed = skipped = errors = unresolved = 0
    for row in rows:
        click.echo(f"  {row['hostname']:<{host_w}}  ", nl=False)
        if row.get("error"):
            errors += 1
            click.secho(f"error: {row['error']}", fg="red")
        elif row.get("skipped"):
            skipped += 1
            click.secho(f"skipped: {row['skipped']}", fg="white", dim=True)
        elif row["actions"]:
            changed += 1
            click.secho(", ".join(row["actions"]), fg="cyan")
        elif row["problems"]:
            click.secho("not fixable by sync", fg="yellow")
        else:
            click.secho("ok", fg="green")
        if row.get("problems") and not row.get("error"):
            unresolved += 1
            echo_problems(row, "yellow")

    click.echo()
    already_ok = len(rows) - changed - skipped - errors
    verb = "would change" if dry_run else "changed"
    click.secho(
        f"{len(rows)} hostname(s): {changed} {verb}, {already_ok} unchanged, "
        f"{skipped} skipped, {errors} errors; {unresolved} with problems sync cannot fix",
        fg="green" if errors == 0 else "yellow",
    )
    click.echo()


@click.command()
@click.argument("hostnames", nargs=-1)
@click.option(
    "--all",
    "sync_all",
    is_flag=True,
    help="Sync every registered domain and known site (required when no hostnames are given)",
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
@click.option("--dry-run", is_flag=True, help="Show what would be changed without making changes")
@click.option(
    "--workers",
    type=click.IntRange(min=1),
    default=5,
    show_default=True,
    help="Maximum number of concurrent workers",
)
def sync(
    hostnames: tuple[str, ...],
    sync_all: bool,
    config: Path | None,
    output_format: str,
    dry_run: bool,
    workers: int,
) -> None:
    """Apply the changes `mimeo status` lists.

    For each hostname with a site: adds the address records the host
    needs, removes address records at the site's own names that it does
    not need, requests the HTTPS certificate when there is none, and
    enforces HTTPS when the certificate is ready. The
    records are written at whichever configured DNS provider the
    nameservers belong to.

    \b
    What sync will NOT do:
      - touch any record that is not an address record (A, AAAA, CNAME,
        ALIAS) at one of the site's own names
      - change a record's proxy setting
      - change nameservers (use: mimeo delegate)
      - link a hostname to a site (use: mimeo link)
      - write to a zone served by a provider that is not configured

    \b
    Examples:
        mimeo sync example.com
        mimeo sync --all --dry-run
        mimeo sync --all
    """
    if hostnames and sync_all:
        click.secho("Give either hostnames or --all, not both.", fg="red", err=True)
        sys.exit(EXIT_CONFIG)
    if not hostnames and not sync_all:
        click.secho(
            "Refusing to sync the whole fleet implicitly. "
            "Name the hostnames to sync, or pass --all (try --all --dry-run first).",
            fg="red",
            err=True,
        )
        sys.exit(EXIT_CONFIG)
    if hostnames:
        validate_domains(hostnames)

    if dry_run and output_format == "text":
        click.secho("DRY RUN MODE - No changes will be made", fg="cyan", bold=True)

    try:
        cfg = load_config(config)
        with open_fleet(cfg) as fleet:
            targets, search = targets_for(fleet, cfg, hostnames)

            def _sync(hostname: str) -> Dict[str, Any]:
                row: Dict[str, Any] = {
                    "hostname": hostname,
                    "actions": [],
                    "problems": [],
                    "fixes": [],
                    "skipped": None,
                    "error": None,
                }
                conn = fleet.read(hostname, search=search)
                if conn.site is None:
                    row["skipped"] = (
                        "served by Netlify (mimeo does not change Netlify sites)"
                        if conn.netlify is not None
                        else "no site (use: mimeo link or mimeo create)"
                    )
                    return row
                plan = compare(conn, fleet.host)
                row["problems"] = list(plan.problems)
                # The steps were worked out before this run changed anything,
                # so a step that says to run this very command is already done.
                done = f"Run: mimeo sync {hostname}"
                row["fixes"] = [f for f in plan.fixes if dry_run or f != done]
                row["fixes_are_choices"] = plan.fixes_are_choices
                if plan.records == "external":
                    row["skipped"] = "DNS is at a provider that is not configured"
                if dry_run:
                    row["actions"] = [f"would {c.summary}" for c in plan.changes]
                else:
                    row["actions"] = apply(conn, plan, fleet.host)
                    if conn.zone is not None and row["actions"]:
                        fleet.forget(conn.zone)
                if row["actions"]:
                    row["skipped"] = None
                return row

            def _on_error(hostname: str, exc: BaseException) -> Dict[str, Any]:
                return {
                    "hostname": hostname,
                    "actions": [],
                    "problems": [],
                    "fixes": [],
                    "skipped": None,
                    "error": str(exc),
                    "error_category": _categorize_error(exc)[1],
                }

            results = map_items(
                targets, _sync, workers=workers, sequential=dry_run, on_error=_on_error
            )

        def _csv_rows(row: Dict[str, Any]) -> List[Dict[str, Any]]:
            flat = dict(row)
            flat["actions"] = "|".join(row["actions"])
            flat["problems"] = "|".join(row["problems"])
            flat["fixes"] = "|".join(row["fixes"])
            return [flat]

        render_results(
            results,
            output_format,
            csv_fields=["hostname", "actions", "problems", "fixes", "skipped", "error"],
            csv_rows=_csv_rows,
            text=lambda rows: _text(rows, dry_run),
        )
        exit_on_errors(results)
    except Exception as e:
        exit_code, category = _categorize_error(e)
        click.secho(f"[{category}] {e}", fg="red", err=True)
        sys.exit(exit_code)
