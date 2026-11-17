"""The link, unlink, delegate and scan commands."""

import sys
from pathlib import Path

import click

from ..config import DNS_PROVIDER_NAMES
from ..models import Site
from ..operations import delegate as delegate_zone
from ..operations import link as link_site
from ..operations import unlink as unlink_site
from ._fleet import echo_outcome, open_fleet, report_duplicates
from ._processing import _categorize_error, load_config, validate_domains

_config_option = click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    help="Path to config file (default: ~/.config/mimeo/config.toml)",
)
_dry_run_option = click.option(
    "--dry-run", is_flag=True, help="Show what would be changed without making changes"
)


def _fail(exc: BaseException) -> None:
    exit_code, category = _categorize_error(exc)
    click.secho(f"[{category}] {exc}", fg="red", err=True)
    sys.exit(exit_code)


@click.command()
@click.argument("hostname")
@click.argument("site", required=False)
@_config_option
@_dry_run_option
@click.option(
    "--wait",
    is_flag=True,
    help="Wait up to 15 minutes for the certificate, then enforce HTTPS",
)
@click.option("--skip-dns", is_flag=True, help="Set the custom domain only; leave DNS records alone")
def link(
    hostname: str,
    site: str | None,
    config: Path | None,
    dry_run: bool,
    wait: bool,
    skip_dns: bool,
) -> None:
    """Connect HOSTNAME to a site that already exists.

    Sets the site's custom domain, writes the DNS records the host needs
    at whichever configured provider serves the zone, and enforces HTTPS
    when the certificate is ready. Nothing else in the zone is touched,
    and no repository is created or changed.

    SITE is written github:OWNER/REPO. Left out, it is the repository
    named after the hostname in the default organization.

    \b
    Examples:
        mimeo link example.com
        mimeo link example.com github:someone/portfolio
        mimeo link service.example.com --dry-run
    """
    validate_domains((hostname,))
    try:
        cfg = load_config(config)
        target = Site.parse(site) if site else Site("github", f"{cfg.github_username}/{hostname.lower()}")
        with open_fleet(cfg) as fleet:
            outcome = link_site(
                fleet,
                hostname,
                target,
                dry_run=dry_run,
                wait=900 if wait else 0,
                records=not skip_dns,
            )
        click.echo(f"{hostname} -> {target}")
        echo_outcome(outcome, nothing="  Already linked; nothing to change.")
    except Exception as e:
        _fail(e)


@click.command()
@click.argument("hostname")
@_config_option
@_dry_run_option
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
def unlink(hostname: str, config: Path | None, dry_run: bool, yes: bool) -> None:
    """Disconnect HOSTNAME from its site.

    Removes the address records at the site's own names and the site's
    custom-domain setting. The site stops loading at HOSTNAME. The
    repository and every other record in the zone are left alone.

    \b
    Examples:
        mimeo unlink example.com --dry-run
        mimeo unlink service.example.com
    """
    validate_domains((hostname,))
    try:
        cfg = load_config(config)
        with open_fleet(cfg) as fleet:
            if not dry_run and not yes:
                preview, site = unlink_site(fleet, hostname, dry_run=True)
                click.echo(f"{hostname} is served by {site}. Unlinking:")
                echo_outcome(preview)
                if not click.confirm("Continue?"):
                    click.echo("Aborted.")
                    return
            outcome, site = unlink_site(fleet, hostname, dry_run=dry_run)
        click.echo(f"{hostname} -x- {site}")
        echo_outcome(outcome)
    except Exception as e:
        _fail(e)


@click.command()
@click.argument("zone")
@click.option(
    "--dns",
    "provider",
    type=click.Choice(DNS_PROVIDER_NAMES, case_sensitive=False),
    default=None,
    help="DNS provider to move the zone to (default: defaults.dns from config)",
)
@_config_option
@_dry_run_option
@click.option(
    "--empty",
    is_flag=True,
    help="Move the zone even though its current records cannot be read; it starts empty",
)
@click.option(
    "--yes",
    is_flag=True,
    help="Do not ask before a move that stops a service the current provider runs",
)
def delegate(
    zone: str, provider: str | None, config: Path | None, dry_run: bool, empty: bool, yes: bool
) -> None:
    """Move ZONE to another DNS provider.

    Copies every record except NS and SOA from the provider serving the
    zone now, reads the copies back to confirm them, then sets the
    nameservers at the registrar. Records are copied DNS-only. The old
    provider's records are left in place, so moving back is one command.

    Refuses when DNSSEC is enabled for the domain, and when the current
    provider is one mimeo cannot read (unless --empty).

    Some records point at services the current provider runs only for
    zones it serves, such as Cloudflare Email Routing or Cloudflare's
    proxy. Copying the records does not move the service. When the move
    would stop one, delegate says which and asks before changing
    anything (--yes skips the question).

    \b
    Examples:
        mimeo delegate example.com --dns cloudflare --dry-run
        mimeo delegate example.com --dns cloudflare
        mimeo delegate example.com --dns porkbun
    """
    validate_domains((zone,))
    try:
        cfg = load_config(config)
        name = (provider or cfg.default_dns).lower()
        with open_fleet(cfg) as fleet:

            def _confirm(stops: list[str]) -> bool:
                click.secho(f"Moving {zone} to {name} would stop:", fg="yellow")
                for stop in stops:
                    click.secho(f"  - {stop}", fg="yellow")
                return yes or click.confirm(f"Move {zone} anyway?", default=False)

            outcome = delegate_zone(
                fleet, zone, name, dry_run=dry_run, empty=empty, confirm=_confirm
            )
        click.echo(f"{zone} -> {name}")
        echo_outcome(outcome)
    except Exception as e:
        _fail(e)


@click.command()
@_config_option
def scan(config: Path | None) -> None:
    """Find every site in the listed organizations and rebuild the cache.

    mimeo remembers which repository serves which hostname in
    ~/.cache/mimeo/sites.json so it does not have to search every time.
    The custom-domain setting on each repository is the authority; this
    command reads it for every Pages repository in every organization
    listed under github.organizations and rewrites the cache from the
    result. Run it after linking a site outside mimeo.
    """
    try:
        cfg = load_config(config)
        with open_fleet(cfg) as fleet:
            duplicates = fleet.rescan()
            found = fleet.cache.hostnames()
            pairs = [(h, fleet.cache.get(h)) for h in found]
        report_duplicates(duplicates)
        width = max((len(h) for h in found), default=0)
        for hostname, site in pairs:
            click.echo(f"  {hostname:<{width}}  {site}")
        click.echo(
            f"{len(found)} site(s) with a custom domain in: {', '.join(cfg.organizations)}"
        )
    except Exception as e:
        _fail(e)
