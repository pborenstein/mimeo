"""Create command: a repository from a template, then link it."""

from pathlib import Path
from typing import Any, Dict, List

import click

from ..config import DNS_PROVIDER_NAMES, Config
from ..connection import Fleet
from ..models import Site
from ..operations import OperationError, WouldStopService, delegate, link
from ._fleet import open_fleet
from ._processing import (
    _categorize_error,
    _emit,
    exit_on_errors,
    get_log_format,
    load_config,
    map_items,
    validate_domains,
)


def create_one(
    fleet: Fleet,
    cfg: Config,
    hostname: str,
    *,
    template: str,
    repo: str | None = None,
    dns: str | None = None,
    force: bool = False,
    skip_dns: bool = False,
    dry_run: bool = False,
    wait: bool = False,
) -> Dict[str, Any]:
    """Create the site for one hostname: delegate if needed, create the repo, link.

    Returns:
        A result row; raises on failure so map_items can build the error row
    """
    hostname = hostname.lower()
    site = Site("github", repo or f"{cfg.github_username}/{hostname}")
    owner, _, repo_name = site.ref.partition("/")
    result: Dict[str, Any] = {
        "domain": hostname,
        "error": None,
        "error_category": None,
        "created": False,
        "repo_existed": False,
        "url": f"https://{hostname}",
        "repo_url": f"https://github.com/{site.ref}",
        "https_pending": False,
        "actions": [],
        "notes": [],
    }

    # Nothing is created for a hostname no registered domain covers.
    zone = fleet.zone_for(hostname)
    if zone is None:
        raise OperationError(
            f"{hostname} is not covered by a domain registered in this account -- refusing to create"
        )
    current, _ = fleet.site_for(hostname)
    if current is not None and current != site:
        raise OperationError(
            f"{hostname} is already linked to {current}; run 'mimeo unlink {hostname}' first"
        )
    assert fleet.repos is not None

    # Move the zone to the chosen DNS provider when it sits at another
    # configured one. A subdomain never moves its parent zone.
    dns_name = (dns or cfg.default_dns).lower()
    serving = fleet.provider_for(fleet.nameservers(zone))
    if (
        not skip_dns
        and hostname == zone
        and serving is not None
        and serving.name != dns_name
        and fleet.provider_named(dns_name) is not None
    ):
        # create runs unattended, so a move that would stop a service is
        # not made: the site is created with the zone left where it is.
        try:
            moved = delegate(fleet, zone, dns_name, dry_run=dry_run)
        except WouldStopService as stopped:
            result["notes"].append(
                f"{zone} was left at {serving.name}. Moving it to {dns_name} would stop:"
            )
            result["notes"] += [f"  {stop}" for stop in stopped.stops]
            result["notes"].append(f"To move it anyway: mimeo delegate {zone} --dns {dns_name}")
        else:
            if dry_run and moved.stops:
                moved.actions = []
                moved.notes = [
                    f"{zone} would be left at {serving.name}. Moving it to {dns_name}"
                    " would stop:",
                    *[f"  {stop}" for stop in moved.stops],
                ]
            result["actions"] += moved.actions
            result["notes"] += moved.notes

    if dry_run:
        verb = "delete and recreate" if force else "create"
        result["actions"].append(f"would {verb} {site.ref} from template '{template}'")
    else:
        _, created, existed = fleet.repos.create_from_template(
            repo_name=repo_name, owner=owner, template_repo=template, force=force
        )
        result["created"] = created
        result["repo_existed"] = existed
        if created and existed:
            result["actions"].append(f"replace {site.ref} from template '{template}'")
        elif created:
            result["actions"].append(f"create {site.ref} from template '{template}'")
        else:
            result["notes"].append(
                f"{site.ref} already exists and was left unchanged "
                f"(use 'mimeo create --force' to replace it)"
            )

    linked = link(
        fleet, hostname, site, dry_run=dry_run, wait=900 if wait else 0, records=not skip_dns
    )
    result["actions"] += linked.actions
    result["notes"] += linked.notes
    result["https_pending"] = linked.https_pending
    return result


@click.command()
@click.argument("hostnames", nargs=-1)
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
    "--sequential", is_flag=True, help="Process hostnames one at a time instead of concurrently"
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
    default=None,
    help="Template repository name to use "
    "(default: defaults.template from config, else 'mimeo')",
)
@click.option(
    "--repo",
    default=None,
    metavar="OWNER/NAME",
    help="Repository to create (default: the hostname, in the default organization). "
    "One hostname only.",
)
@click.option(
    "--dns",
    type=click.Choice(DNS_PROVIDER_NAMES, case_sensitive=False),
    default=None,
    help="DNS provider the zone should be at (default: defaults.dns from config)",
)
@click.option(
    "--skip-dns",
    is_flag=True,
    help="Create the repo and set the custom domain only; leave nameservers and records alone",
)
@click.option(
    "--force",
    is_flag=True,
    help="Replace an existing repository's content with the template",
)
@click.option("--wait", is_flag=True, help="Wait up to 15 minutes for the certificate")
@click.option(
    "--yes",
    is_flag=True,
    help="Skip confirmation prompt (only relevant with --force)",
)
@click.pass_context
def create(
    ctx: click.Context,
    hostnames: tuple[str, ...],
    config: Path | None,
    dry_run: bool,
    sequential: bool,
    workers: int,
    template: str | None,
    repo: str | None,
    dns: str | None,
    skip_dns: bool,
    force: bool,
    wait: bool,
    yes: bool,
) -> None:
    """Create a site for each hostname and connect it.

    For each hostname: moves the zone to the default DNS provider if it
    sits at another configured one, creates a GitHub repository from a
    template, then does what `mimeo link` does (custom domain, DNS
    records, HTTPS). A subdomain gets one CNAME in its parent zone.

    If the repository already exists it is left unchanged and still
    linked. Use --force to replace its content with the template.
    WARNING: --force deletes the existing repository and recreates it --
    all existing content, issues, and history are lost.

    \b
    Examples:
        mimeo create example.com
        mimeo create site1.com site2.com site3.com
        mimeo create service.example.com --template eleventy-service
        mimeo create example.com --dns porkbun
        mimeo create example.com --dry-run
        mimeo create example.com --template mimeo --force
    """
    if not hostnames:
        click.echo(ctx.get_help())
        ctx.exit(2)
    if repo and len(hostnames) > 1:
        raise click.UsageError("--repo names one repository, so it takes one hostname")
    if repo and "/" not in repo:
        raise click.UsageError("--repo is written OWNER/NAME")

    validate_domains(hostnames)
    cfg = load_config(config)
    chosen_template = template or cfg.default_template
    log_format = get_log_format()
    owner_repo = [repo or f"{cfg.github_username}/{h.lower()}" for h in hostnames]

    if force and not dry_run and not yes:
        click.secho(
            "WARNING: This will delete and recreate the following repositories:",
            fg="red",
            bold=True,
        )
        for ref in owner_repo:
            click.echo(f"  - {ref}")
        click.echo()
        click.secho("All existing content, issues, and history will be lost.", fg="red")
        click.echo()
        if not click.confirm("Continue?"):
            click.echo("Aborted.")
            return

    if dry_run:
        click.secho("DRY RUN MODE - No changes will be made", fg="cyan", bold=True)
        click.echo()

    try:
        with open_fleet(cfg) as fleet:
            assert fleet.repos is not None
            try:
                fleet.repos.validate_template(chosen_template)
            except Exception as e:
                click.secho(str(e), fg="red", err=True)
                raise SystemExit(1)

            def _create(hostname: str) -> Dict[str, Any]:
                if log_format == "text" and len(hostnames) > 1:
                    click.echo(f"Creating {hostname}...")
                return create_one(
                    fleet,
                    cfg,
                    hostname,
                    template=chosen_template,
                    repo=repo,
                    dns=dns,
                    force=force,
                    skip_dns=skip_dns,
                    dry_run=dry_run,
                    wait=wait,
                )

            def _on_error(hostname: str, exc: BaseException) -> Dict[str, Any]:
                return {
                    "domain": hostname,
                    "error": str(exc),
                    "error_category": _categorize_error(exc)[1],
                    "actions": [],
                    "notes": [],
                }

            results = map_items(
                hostnames,
                _create,
                workers=workers,
                sequential=(dry_run or sequential or len(hostnames) == 1),
                on_error=_on_error,
            )
    except SystemExit:
        raise
    except Exception as e:
        exit_code, category = _categorize_error(e)
        click.secho(f"[{category}] {e}", fg="red", err=True)
        raise SystemExit(exit_code)

    if log_format == "json":
        for result in results:
            if result.get("error"):
                _emit("error", result["error"], domain=result["domain"])
            else:
                for action in result["actions"]:
                    _emit("info", action, domain=result["domain"])
                _emit("info", "success", domain=result["domain"])
    else:
        _text(results, dry_run)
    exit_on_errors(results)


def _text(results: List[Dict[str, Any]], dry_run: bool) -> None:
    total = len(results)
    failed = sum(1 for r in results if r.get("error"))
    created = sum(1 for r in results if not r.get("error") and r.get("created"))
    click.echo()
    if dry_run:
        click.secho(f"DRY RUN: would process {total} hostname(s)", fg="cyan", bold=True)
    else:
        color = "red" if failed == total else ("green" if not failed else "yellow")
        suffix = f" ({failed} failed)" if failed else ""
        click.secho(f"Created {created}/{total} site(s){suffix}", fg=color, bold=True)
    click.echo()

    for result in results:
        if result.get("error"):
            click.secho(f"✗ {result['domain']}", fg="red", bold=True)
            click.secho(f"  {result['error']}", fg="red")
            click.echo()
            continue
        click.secho(f"✓ {result['domain']}", fg="green", bold=True)
        for action in result["actions"]:
            click.echo(f"  {action}")
        for note in result["notes"]:
            click.secho(f"  {note}", fg="yellow")
        if not dry_run:
            click.echo(f"  URL: {result['url']}")
            click.echo(f"  Repository: {result['repo_url']}")
        click.echo()
