"""Fix commands for repairing site configuration."""

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict

import click

from ..exceptions import HostError
from ..providers.host.github import GitHubHost, _health_status
from ._processing import _categorize_error, load_config


@click.group()
def fix() -> None:
    """Fix site configuration issues."""
    pass


@fix.command()
@click.argument("domains", nargs=-1)
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    help="Path to config file (default: ~/.config/mimeo/config.toml)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be fixed without making changes",
)
def https(domains: tuple[str, ...], config: Path | None, dry_run: bool) -> None:
    """Enable HTTPS enforcement on sites with approved SSL certificates.

    If specific domains are given, fix those repos. Otherwise, discover
    and fix all fixable mimeo-managed repos.

    Examples:
        mimeo fix https                          # Fix all fixable sites
        mimeo fix https example.com              # Fix specific site
        mimeo fix https site1.com site2.com      # Fix multiple sites
        mimeo fix https --dry-run                # Preview changes
    """
    try:
        cfg = load_config(config)
        owner = cfg.github_username

        if dry_run:
            click.secho("DRY RUN MODE - No changes will be made", fg="cyan", bold=True)
            click.echo()

        with GitHubHost(default_org=owner) as host:
            if domains:
                # Fix specific domains
                targets = list(domains)
            else:
                # Discover fixable repos
                repos = host.list_mimeo_repositories()
                if not repos:
                    click.echo("No mimeo-managed sites found.")
                    return

                # Check health concurrently
                health_map: Dict[str, Dict[str, Any]] = {}
                with ThreadPoolExecutor(max_workers=10) as executor:
                    future_to_name = {
                        executor.submit(host.get_pages_health, f"{owner}/{r['name']}"): r["name"]
                        for r in repos
                    }
                    for future in as_completed(future_to_name):
                        name = future_to_name[future]
                        health_map[name] = future.result()

                targets = [
                    name for name, h in health_map.items()
                    if _health_status(h) == "fixable"
                ]

                if not targets:
                    click.echo("No sites need HTTPS fixing.")
                    return

                click.echo(f"Found {len(targets)} fixable site(s):")
                for t in targets:
                    click.echo(f"  - {t}")
                click.echo()

            # Apply fixes
            results = []
            for domain in targets:
                repo_full_name = f"{owner}/{domain}"
                if dry_run:
                    click.echo(f"  Would enable HTTPS on {repo_full_name}")
                    results.append({"name": domain, "success": True, "error": None})
                else:
                    try:
                        host._enable_https_enforcement(repo_full_name)
                        results.append({"name": domain, "success": True, "error": None})
                    except HostError as e:
                        results.append({"name": domain, "success": False, "error": str(e)})

            # Summary
            click.echo()
            if dry_run:
                click.secho(f"DRY RUN: Would fix HTTPS on {len(targets)} site(s)", fg="cyan")
            else:
                success_count = sum(1 for r in results if r["success"])
                click.secho("HTTPS enforcement results:", bold=True)
                for r in results:
                    if r["success"]:
                        click.secho(f"  ok {r['name']}", fg="green")
                    else:
                        click.secho(f"  xx {r['name']} ({r['error']})", fg="red")
                click.echo()
                color = "green" if success_count == len(results) else "yellow"
                click.secho(f"Fixed: {success_count}/{len(results)}", fg=color)

    except Exception as e:
        exit_code, category = _categorize_error(e)
        click.secho(f"[{category}] {e}", fg="red", err=True)
        sys.exit(exit_code)
