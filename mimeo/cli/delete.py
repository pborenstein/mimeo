"""Delete command: unlink a hostname, then delete the repository behind it."""

from pathlib import Path
from typing import Any, Dict, List

import click

from ..connection import Fleet
from ..models import Site
from ..operations import OperationError, unlink
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


def delete_one(fleet: Fleet, hostname: str, site: Site | None, fallback_ref: str, dry_run: bool) -> Dict[str, Any]:
    """Unlink a hostname and delete its repository.

    Args:
        fleet: The providers
        hostname: The hostname being torn down
        site: The site linked to it, or None when nothing is linked
        fallback_ref: Repository to delete when nothing is linked (the
            one `create` would have made)
        dry_run: Describe without changing anything
    """
    result: Dict[str, Any] = {
        "domain": hostname,
        "error": None,
        "error_category": None,
        "actions": [],
        "notes": [],
        "repo": site.ref if site else fallback_ref,
        "repo_deleted": False,
    }
    if site is None and fleet.netlify is not None:
        held = fleet.netlify.site_for(hostname)
        if held is not None:
            raise OperationError(
                f"{hostname} is served by the Netlify site {held.name}, so mimeo left it"
                f" alone. To remove that site, delete it at {held.admin_url}"
            )
    if site is not None:
        outcome, _ = unlink(fleet, hostname, dry_run=dry_run)
        result["actions"] += outcome.actions
        result["notes"] += outcome.notes
    else:
        result["notes"].append(f"no site was linked to {hostname}; DNS records left alone")

    assert fleet.repos is not None
    ref = result["repo"]
    builders = fleet.netlify.sites_building(ref) if fleet.netlify is not None else []
    if builders:
        names = ", ".join(s.name for s in builders)
        result["notes"].append(f"kept repository {ref}: it also builds the Netlify site {names}")
    elif dry_run:
        result["actions"].append(f"would delete repository {ref}")
    elif fleet.repos.delete_repository_if_exists(ref):
        result["repo_deleted"] = True
        result["actions"].append(f"delete repository {ref}")
    else:
        result["notes"].append(f"repository {ref} does not exist")
    return result


def _repo_would_be_deleted(fleet: Fleet, site: Site | None, ref: str, hostname: str) -> bool:
    """False when a Netlify site holds the hostname or builds from the repository."""
    if fleet.netlify is None:
        return True
    if site is None and fleet.netlify.site_for(hostname) is not None:
        return False
    return not fleet.netlify.sites_building(ref)


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
    help="Show what would be deleted without actually deleting anything",
)
@click.option("--yes", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def delete(
    ctx: click.Context,
    hostnames: tuple[str, ...],
    config: Path | None,
    dry_run: bool,
    yes: bool,
) -> None:
    """Tear down the site at each hostname, repository included.

    Does what `mimeo unlink` does (removes the site's address records
    and its custom-domain setting), then deletes the repository. The
    repository is whichever one's custom domain is the hostname, in any
    listed organization; the confirmation prompt names it. The domain
    registration, the nameservers, and every other record in the zone
    are left alone.

    To take a site off a hostname and keep the repository, use
    `mimeo unlink`.

    \b
    Examples:
        mimeo delete example.com --dry-run
        mimeo delete example.com
        mimeo delete site1.com site2.com --yes
    """
    if not hostnames:
        click.echo(ctx.get_help())
        ctx.exit(2)

    validate_domains(hostnames)
    cfg = load_config(config)
    log_format = get_log_format()
    names = [h.lower() for h in hostnames]

    try:
        with open_fleet(cfg) as fleet:
            if fleet.netlify is not None:
                fleet.netlify.require()
            # A repository is about to be deleted by name, so make sure no
            # differently named repository serves the hostname first.
            sites: Dict[str, Site | None] = {
                h: fleet.site_for(h, thorough=True)[0] for h in names
            }
            refs = {h: (s.ref if s else f"{cfg.github_username}/{h}") for h, s in sites.items()}

            doomed = [h for h in names if _repo_would_be_deleted(fleet, sites[h], refs[h], h)]
            kept = [h for h in names if sites[h] is not None and h not in doomed]
            if not dry_run and not yes and (doomed or kept):
                if doomed:
                    click.secho(
                        "WARNING: This will permanently delete these repositories:",
                        fg="red",
                        bold=True,
                    )
                    for hostname in doomed:
                        linked = "" if sites[hostname] else "  (not linked; named after the hostname)"
                        click.echo(f"  - {refs[hostname]}  for {hostname}{linked}")
                    click.echo()
                    click.secho(
                        "All content, issues, and history will be lost, and each site's "
                        "DNS records will be removed.",
                        fg="red",
                    )
                    click.echo()
                if kept:
                    click.secho(
                        "These sites will be unlinked and their DNS records removed. Their "
                        "repositories are kept because Netlify builds from them:",
                        fg="yellow",
                    )
                    for hostname in kept:
                        click.echo(f"  - {refs[hostname]}  for {hostname}")
                    click.echo()
                if not click.confirm("Continue?"):
                    click.echo("Aborted.")
                    return

            if dry_run:
                click.secho("DRY RUN MODE - No changes will be made", fg="cyan", bold=True)

            def _delete(hostname: str) -> Dict[str, Any]:
                return delete_one(fleet, hostname, sites[hostname], refs[hostname], dry_run)

            def _on_error(hostname: str, exc: BaseException) -> Dict[str, Any]:
                return {
                    "domain": hostname,
                    "error": str(exc),
                    "error_category": _categorize_error(exc)[1],
                    "actions": [],
                    "notes": [],
                }

            results = map_items(names, _delete, sequential=True, on_error=_on_error)
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
    else:
        _text(results)
    exit_on_errors(results)


def _text(results: List[Dict[str, Any]]) -> None:
    click.echo()
    for result in results:
        if result.get("error"):
            click.secho(f"✗ {result['domain']}", fg="red", bold=True)
            click.secho(f"  {result['error']}", fg="red")
        else:
            click.secho(f"✓ {result['domain']}", fg="green", bold=True)
            for action in result["actions"]:
                click.echo(f"  {action}")
            for note in result["notes"]:
                click.secho(f"  {note}", fg="yellow")
        click.echo()
