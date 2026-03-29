"""List command for querying mimeo-managed sites."""

import csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict

import click

from ..providers.host.github import GitHubHost, health_status
from ..config import Config
from ._processing import _categorize_error


@click.command(name="list")
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
    help="Output format (default: text)",
)
@click.option("--health", is_flag=True, help="Check Pages configuration health for each site")
def list_sites(config: Path | None, output_format: str, health: bool) -> None:
    """List all mimeo-managed sites.

    Shows repositories tagged with the 'mimeo' topic. This is a read-only
    command with no side effects.

    \b
    Basic usage:
        mimeo list                    # Human-readable text format
        mimeo list --format json      # JSON output
        mimeo list --format csv       # CSV output

    \b
    Extracting specific data:
        # Just domain names
        mimeo list --format csv | tail -n +2 | cut -d, -f1

        # Just site URLs
        mimeo list --format json | jq -r '.[].site'

        # Just repository URLs
        mimeo list --format csv | tail -n +2 | cut -d, -f2

    \b
    Processing with jq:
        # Count total sites
        mimeo list --format json | jq 'length'

        # Filter by update date
        mimeo list --format json | jq '.[] | select(.updated == "2026-02-15")'

        # Get names of recently updated sites
        mimeo list --format json | jq -r '.[] | select(.updated >= "2026-02-01") | .name'

    \b
    Importing data:
        # Export to CSV file
        mimeo list --format csv > sites.csv

        # Create simple list for scripts
        mimeo list --format csv | tail -n +2 | cut -d, -f1 > domains.txt
    """
    try:
        cfg = Config.load(config)

        with GitHubHost(default_org=cfg.github_username) as host:
            repos = host.list_mimeo_repositories()

            if not repos:
                if output_format == "json":
                    click.echo("[]")
                elif output_format == "csv":
                    fieldnames = ["name", "repository", "site", "updated"]
                    if health:
                        fieldnames += ["health", "https_enforced", "cert_state"]
                    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
                    writer.writeheader()
                else:
                    click.echo("No mimeo-managed sites found.")
                    click.echo()
                    click.echo("Create your first site with: mimeo create example.com")
                return

            owner = cfg.github_username
            normalized_repos = []
            for repo in repos:
                name = repo.get("name", "")
                url = repo.get("url", "")
                pages_url = repo.get("homepage") or f"https://{name}"
                updated = repo.get("updatedAt", "")[:10]

                normalized_repos.append(
                    {
                        "name": name,
                        "repository": url,
                        "site": pages_url,
                        "updated": updated,
                    }
                )

            if health:
                health_map: Dict[str, Dict[str, Any]] = {}
                with ThreadPoolExecutor(max_workers=10) as executor:
                    future_to_name = {
                        executor.submit(host.get_pages_health, f"{owner}/{r['name']}"): r["name"]
                        for r in normalized_repos
                    }
                    for future in as_completed(future_to_name):
                        name = future_to_name[future]
                        health_map[name] = future.result()

                for repo_data in normalized_repos:
                    h = health_map.get(
                        repo_data["name"],
                        {
                            "pages_configured": False,
                            "https_enforced": False,
                            "cert_state": None,
                            "pages_status": None,
                        },
                    )
                    repo_data["health"] = health_status(h)
                    repo_data["https_enforced"] = h["https_enforced"]
                    repo_data["cert_state"] = h["cert_state"]

            # Sort
            _status_order = {
                "pages_error": 0,
                "no_cert": 1,
                "cert_pending": 2,
                "fixable": 3,
                "healthy": 4,
            }
            if health:
                normalized_repos.sort(
                    key=lambda r: (_status_order.get(r.get("health", "pages_error"), 0), r["name"])
                )
            else:
                normalized_repos.sort(key=lambda r: r["name"])

            # Display results
            if output_format == "json":
                click.echo(json.dumps(normalized_repos, indent=2))
            elif output_format == "csv":
                fieldnames = ["name", "repository", "site", "updated"]
                if health:
                    fieldnames += ["health", "https_enforced", "cert_state"]
                writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(normalized_repos)
            else:
                _health_colors = {
                    "healthy": "green",
                    "fixable": "yellow",
                    "cert_pending": "yellow",
                    "no_cert": "red",
                    "pages_error": "red",
                }
                _health_labels = {
                    "healthy": "ok",
                    "fixable": "fixable",
                    "cert_pending": "pending",
                    "no_cert": "no cert",
                    "pages_error": "error",
                }

                name_w = max(len(r["name"]) for r in normalized_repos)
                site_w = max(len(r["site"]) for r in normalized_repos)

                click.echo()

                header_parts = f"  {'NAME':<{name_w}}  {'SITE':<{site_w}}  {'UPDATED':<10}"
                if health:
                    header_parts += "  HEALTH"
                click.secho(header_parts, bold=True)
                click.secho("  " + "-" * (len(header_parts) - 2), fg="white", dim=True)

                for repo_data in normalized_repos:
                    name = repo_data["name"]
                    site = repo_data["site"]
                    updated = repo_data["updated"]
                    row = f"  {name:<{name_w}}  {site:<{site_w}}  {updated:<10}"
                    click.echo(row, nl=False)
                    if health:
                        status = repo_data.get("health", "pages_error")
                        color = _health_colors.get(status, "white")
                        label = _health_labels.get(status, status)
                        click.echo("  ", nl=False)
                        click.secho(f"{label:<8}", fg=color, nl=False)
                    click.echo()

                click.echo()

    except Exception as e:
        exit_code, category = _categorize_error(e)
        click.secho(f"[{category}] {e}", fg="red", err=True)
        sys.exit(exit_code)
