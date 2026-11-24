"""Proxy command: turn on the DNS provider's proxy for sites."""

import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import click
import requests

from ..exceptions import EXIT_CONFIG
from ..operations import NotProxyable
from ..operations import proxy as proxy_site
from ._fleet import open_fleet, targets_for
from ._processing import _categorize_error, exit_on_errors, load_config, validate_domains

_ANSWER_WAIT = 60
_ANSWER_POLL = 5


def site_answers(hostname: str) -> bool:
    """True once https://hostname answers without an error, within a minute."""
    deadline = time.monotonic() + _ANSWER_WAIT
    while True:
        try:
            if requests.get(f"https://{hostname}/", timeout=10).status_code < 400:
                return True
        except requests.RequestException:
            pass
        if time.monotonic() >= deadline:
            return False
        time.sleep(_ANSWER_POLL)


def _text(rows: List[Dict[str, Any]], dry_run: bool) -> None:
    width = max((len(r["hostname"]) for r in rows), default=0)
    changed = skipped = failed = 0
    click.echo()
    for row in rows:
        click.echo(f"  {row['hostname']:<{width}}  ", nl=False)
        if row.get("error"):
            failed += 1
            click.secho(f"error: {row['error']}", fg="red")
        elif row.get("skipped"):
            skipped += 1
            click.secho(f"skipped: {row['skipped']}", dim=True)
        elif row["actions"]:
            changed += 1
            click.secho("; ".join(row["actions"]), fg="cyan")
        else:
            click.secho("; ".join(row["notes"]), fg="green")
    verb = "would change" if dry_run else "changed"
    click.echo()
    click.echo(f"{len(rows)} hostname(s): {changed} {verb}, {skipped} skipped, {failed} failed")
    click.echo()


@click.command()
@click.argument("hostnames", nargs=-1)
@click.option("--all", "proxy_all", is_flag=True, help="Proxy every site that can be proxied")
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    help="Path to config file (default: ~/.config/mimeo/config.toml)",
)
@click.option("--dry-run", is_flag=True, help="Show what would change without changing it")
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt for --all")
def proxy(
    hostnames: tuple[str, ...],
    proxy_all: bool,
    config: Path | None,
    dry_run: bool,
    yes: bool,
) -> None:
    """Turn on Cloudflare's proxy for each site.

    For each site: sets the zone to SSL/TLS mode Full with Always Use
    HTTPS on, turns on the proxy for the site's own address records,
    and checks that https:// still answers. If it does not, the proxy is
    switched back off and the run stops. Mail, TXT and other records are
    left alone.

    Skips, and says why, a hostname with no site, a Netlify site, and a
    domain whose DNS is not on Cloudflare.

    \b
    Examples:
        mimeo proxy example.com --dry-run
        mimeo proxy site1.com site2.com
        mimeo proxy --all --dry-run
        mimeo proxy --all
    """
    if hostnames and proxy_all:
        click.secho("Give either hostnames or --all, not both.", fg="red", err=True)
        sys.exit(EXIT_CONFIG)
    if not hostnames and not proxy_all:
        click.secho("Name the hostnames to proxy, or pass --all.", fg="red", err=True)
        sys.exit(EXIT_CONFIG)
    if hostnames:
        validate_domains(hostnames)
    if proxy_all and not dry_run and not yes:
        if not click.confirm("Turn on Cloudflare's proxy for every site on Cloudflare?"):
            click.echo("Aborted.")
            return

    rows: List[Dict[str, Any]] = []
    try:
        cfg = load_config(config)
        with open_fleet(cfg) as fleet:
            targets, search = targets_for(fleet, cfg, hostnames)
            stopped = False
            for hostname in targets:
                row: Dict[str, Any] = {
                    "hostname": hostname,
                    "actions": [],
                    "notes": [],
                    "skipped": None,
                    "error": None,
                }
                rows.append(row)
                if stopped:
                    row["skipped"] = "not attempted, because an earlier site failed"
                    continue
                try:
                    outcome = proxy_site(
                        fleet, hostname, dry_run=dry_run, search=search, check=site_answers
                    )
                    row["actions"] = outcome.actions
                    row["notes"] = outcome.notes
                except NotProxyable as e:
                    row["skipped"] = str(e)
                except Exception as e:
                    row["error"] = str(e)
                    row["error_category"] = _categorize_error(e)[1]
                    stopped = True
    except Exception as e:
        exit_code, category = _categorize_error(e)
        click.secho(f"[{category}] {e}", fg="red", err=True)
        sys.exit(exit_code)

    _text(rows, dry_run)
    exit_on_errors(rows)
