"""List command for querying mimeo-managed sites."""

import sys
from pathlib import Path
from typing import Any, Dict, List

import click

from ..providers.host.github import GitHubHost, health_status
from ..config import Config
from ._processing import _categorize_error, map_items, render_results


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
    csv_fields = ["name", "repository", "site", "updated"]
    if health:
        csv_fields += ["health", "https_enforced", "cert_state"]

    def _text(rows: List[Dict[str, Any]]) -> None:
        if not rows:
            click.echo("No mimeo-managed sites found.")
            click.echo()
            click.echo("Create your first site with: mimeo create example.com")
            return

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

        name_w = max(len(r["name"]) for r in rows)
        site_w = max(len(r["site"]) for r in rows)

        click.echo()

        header_parts = f"  {'NAME':<{name_w}}  {'SITE':<{site_w}}  {'UPDATED':<10}"
        if health:
            header_parts += "  HEALTH"
        click.secho(header_parts, bold=True)
        click.secho("  " + "-" * (len(header_parts) - 2), fg="white", dim=True)

        for repo_data in rows:
            row = (
                f"  {repo_data['name']:<{name_w}}"
                f"  {repo_data['site']:<{site_w}}"
                f"  {repo_data['updated']:<10}"
            )
            click.echo(row, nl=False)
            if health:
                status = repo_data.get("health", "pages_error")
                color = _health_colors.get(status, "white")
                label = _health_labels.get(status, status)
                click.echo("  ", nl=False)
                click.secho(f"{label:<8}", fg=color, nl=False)
            click.echo()

        click.echo()

    try:
        cfg = Config.load(config)

        with GitHubHost(default_org=cfg.github_username) as host:
            repos = host.list_mimeo_repositories()

            if not repos:
                render_results([], output_format, csv_fields=csv_fields, text=_text)
                return

            owner = cfg.github_username
            normalized_repos = []
            for repo in repos:
                name = repo.get("name", "")
                normalized_repos.append(
                    {
                        "name": name,
                        "repository": repo.get("url", ""),
                        "site": repo.get("homepage") or f"https://{name}",
                        "updated": repo.get("updatedAt", "")[:10],
                    }
                )

            if health:

                def _with_health(repo_data: Dict[str, Any]) -> Dict[str, Any]:
                    h = host.get_pages_health(f"{owner}/{repo_data['name']}")
                    return {
                        **repo_data,
                        "health": health_status(h),
                        "https_enforced": h["https_enforced"],
                        "cert_state": h["cert_state"],
                    }

                def _on_error(
                    repo_data: Dict[str, Any], exc: BaseException
                ) -> Dict[str, Any]:
                    return {
                        **repo_data,
                        "health": "pages_error",
                        "https_enforced": False,
                        "cert_state": None,
                    }

                normalized_repos = map_items(
                    normalized_repos, _with_health, workers=10, on_error=_on_error
                )

        # Sort: problems first when health is shown, else by name
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

        render_results(normalized_repos, output_format, csv_fields=csv_fields, text=_text)

    except Exception as e:
        exit_code, category = _categorize_error(e)
        click.secho(f"[{category}] {e}", fg="red", err=True)
        sys.exit(exit_code)
