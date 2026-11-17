"""Build the Fleet a command works with, and shape what it read for output."""

from contextlib import ExitStack, contextmanager
from typing import Any, Dict, Iterator

import click

from ..cache import SiteCache
from ..config import Config
from ..connection import Connection, Fleet
from ..models import DNSRecord
from ..operations import Outcome
from ..plan import Plan
from ..providers.base import DNSProvider
from ..providers.dns.cloudflare import CloudflareDNS
from ..providers.host.github import GitHubHost
from ..providers.registrar.porkbun import (
    PorkbunDNSProvider,
    PorkbunRegistrar,
    public_nameservers,
)


@contextmanager
def open_fleet(cfg: Config) -> Iterator[Fleet]:
    """Open every configured provider and bundle them into a Fleet."""
    with ExitStack() as stack:
        registrar = stack.enter_context(PorkbunRegistrar(cfg.porkbun_api_key, cfg.porkbun_secret))
        providers: list[DNSProvider] = [
            stack.enter_context(PorkbunDNSProvider(cfg.porkbun_api_key, cfg.porkbun_secret))
        ]
        if cfg.cloudflare_api_token:
            providers.append(
                stack.enter_context(
                    CloudflareDNS(cfg.cloudflare_api_token, cfg.cloudflare_account_id)
                )
            )
        host = stack.enter_context(
            GitHubHost(
                default_org=cfg.github_username,
                template_org=cfg.template_org,
                organizations=cfg.organizations,
            )
        )
        yield Fleet(
            registrar, providers, host, SiteCache(), repos=host.repos, lookup=public_nameservers
        )


def targets_for(
    fleet: Fleet, cfg: Config, hostnames: tuple[str, ...]
) -> tuple[list[str], bool]:
    """Work out which hostnames a status or sync run covers.

    Named hostnames are used as given, and a hostname with no cached
    site is looked for at the host. With none named, the run covers
    every registered domain and every cached site, minus the config's
    ignore list, and relies on a scan having filled the cache; the scan
    is run here if it never has been.

    Returns:
        (hostnames, whether to look for uncached sites)
    """
    if hostnames:
        return [h.lower() for h in hostnames], True

    if not fleet.cache.scanned:
        click.secho("Looking for sites in every listed organization (first run)...", dim=True, err=True)
        report_duplicates(fleet.rescan())

    everything = fleet.hostnames()
    ignored = sorted(set(everything) & set(cfg.ignore_domains))
    if ignored:
        click.secho(
            f"({len(ignored)} domain(s) ignored per config: {', '.join(ignored)})",
            fg="white",
            dim=True,
            err=True,
        )
    return [h for h in everything if h not in ignored], False


def report_duplicates(duplicates: Dict[str, Any]) -> None:
    """Warn about hostnames more than one site claims."""
    for hostname, sites in sorted(duplicates.items()):
        click.secho(
            f"warning: {hostname} is the custom domain of more than one site: "
            f"{', '.join(str(s) for s in sites)}",
            fg="yellow",
            err=True,
        )


def _record_dict(record: DNSRecord) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "type": record.type,
        "name": record.name or "@",
        "content": record.content,
        "ttl": record.ttl,
    }
    if record.priority is not None:
        out["priority"] = record.priority
    if record.proxied is not None:
        out["proxied"] = record.proxied
    return out


def result_row(conn: Connection, plan: Plan, with_records: bool = False) -> Dict[str, Any]:
    """Flatten a Connection and its Plan into one output row."""
    registration = conn.registration or {}
    if conn.dns is not None:
        dns = conn.dns.name
    elif conn.zone is None:
        dns = None
    else:
        dns = "external" if conn.nameservers else "none"
    state = conn.state
    row: Dict[str, Any] = {
        "hostname": conn.hostname,
        "zone": conn.zone,
        "registered": conn.zone is not None,
        "expires": str(registration.get("expireDate", ""))[:10] if not conn.label else "",
        "auto_renew": (
            registration.get("autoRenew") in ("1", 1, True) if registration and not conn.label else None
        ),
        "nameservers": conn.nameservers,
        "dns": dns,
        "proxied": plan.proxied,
        "records": plan.records,
        "missing": [r.describe() for r in plan.missing],
        "extra": [r.describe() for r in plan.extra],
        "site": str(conn.site) if conn.site else None,
        "site_status": plan.site,
        "https_enforced": state.https_enforced if state else None,
        "cert_state": state.cert_state if state else None,
        "cert_expires": state.cert_expires if state else None,
        "changes": [c.summary for c in plan.changes],
        "problems": list(plan.problems),
        "fixes": list(plan.fixes),
        "fixes_are_choices": plan.fixes_are_choices,
        "has_problem": plan.has_problem,
        "fixable": plan.fixable,
        "error": None,
    }
    if with_records:
        row["zone_records"] = [_record_dict(r) for r in conn.records or []]
    return row


def echo_problems(row: Dict[str, Any], color: str) -> None:
    """Print what is wrong with a hostname and the steps that fix it."""
    for problem in row.get("problems") or []:
        click.secho(f"      problem: {problem}", fg=color)
    fixes = row.get("fixes") or []
    if fixes and row.get("fixes_are_choices"):
        click.echo("      do one of:")
        for choice in fixes:
            click.echo(f"        - {choice}")
    elif fixes:
        click.echo("      to fix:")
        for number, step in enumerate(fixes, 1):
            click.echo(f"        {number}. {step}")


def error_row(hostname: str, exc: BaseException, category: str) -> Dict[str, Any]:
    """The row for a hostname whose read or compare raised."""
    return {
        "hostname": hostname,
        "zone": None,
        "registered": None,
        "expires": "",
        "auto_renew": None,
        "nameservers": [],
        "dns": None,
        "proxied": None,
        "records": None,
        "missing": [],
        "extra": [],
        "site": None,
        "site_status": None,
        "https_enforced": None,
        "cert_state": None,
        "cert_expires": None,
        "changes": [],
        "problems": [],
        "fixes": [],
        "has_problem": True,
        "fixable": False,
        "error": str(exc),
        "error_category": category,
    }


def echo_outcome(outcome: Outcome, nothing: str = "Nothing to change.") -> None:
    """Print an operation's actions and notes."""
    if not outcome.actions and not outcome.notes:
        click.echo(nothing)
    for action in outcome.actions:
        click.echo(f"  {action}")
    for note in outcome.notes:
        click.secho(f"  {note}", fg="yellow")
