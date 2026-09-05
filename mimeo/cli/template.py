"""Template commands for managing site templates."""

from pathlib import Path
from typing import Any, Dict, List

import click

from ..providers.host.github import GitHubHost
from ._processing import (
    _categorize_error,
    _emit,
    exit_on_errors,
    get_log_format,
    load_config,
    map_items,
    render_results,
    validate_domains,
)


@click.group()
def template() -> None:
    """Manage site templates."""
    pass


@template.command()
@click.argument("domains", nargs=-1, required=True)
@click.option(
    "--template",
    "template_repo",
    required=True,
    help="Template repository name to use (from the tepiton org)",
)
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    help="Path to config file (default: ~/.config/mimeo/config.toml)",
)
@click.option(
    "--yes",
    is_flag=True,
    help="Skip confirmation prompt",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be changed without making changes",
)
@click.option(
    "--workers",
    type=click.IntRange(min=1),
    default=5,
    show_default=True,
    help="Maximum number of concurrent workers",
)
def apply(
    domains: tuple[str, ...],
    template_repo: str,
    config: Path | None,
    yes: bool,
    dry_run: bool,
    workers: int,
) -> None:
    """Replace repository content with a different template.

    WARNING: This deletes the existing repository and recreates it from
    the template. All existing content, issues, and history will be lost.
    DNS records are not modified.

    Examples:
        mimeo template apply example.com --template mimeo.lol
        mimeo template apply site1.com site2.com --template new-theme --yes
        mimeo template apply example.com --template mimeo.lol --dry-run
    """
    validate_domains(domains)
    cfg = load_config(config)
    log_format = get_log_format()

    with GitHubHost(default_org=cfg.github_username) as host:
        try:
            host.validate_template(template_repo)
        except Exception as e:
            click.secho(str(e), fg="red", err=True)
            raise SystemExit(1)

    if not dry_run and not yes:
        click.secho(
            "WARNING: This will delete and recreate the following repositories:",
            fg="red",
            bold=True,
        )
        for d in domains:
            click.echo(f"  - {cfg.github_username}/{d}")
        click.echo()
        click.secho("All existing content, issues, and history will be lost.", fg="red")
        click.echo()
        if not click.confirm("Continue?"):
            click.echo("Aborted.")
            return

    if dry_run:
        click.secho("DRY RUN MODE - No changes will be made", fg="cyan", bold=True)
        click.echo()

    verbose = dry_run or len(domains) == 1

    def _apply_template(domain: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {"domain": domain, "error": None, "error_category": None}

        def log(message: str, level: str = "info") -> None:
            _emit(level, message, domain=domain)
            if verbose and log_format == "text":
                if level == "error":
                    click.secho(f"  xx {message}", fg="red")
                elif level == "warning":
                    click.secho(f"  !! {message}", fg="yellow")
                elif level == "success":
                    click.secho(f"  ok {message}", fg="green")
                else:
                    click.echo(f"  {message}")

        if dry_run:
            log(
                f"Would delete and recreate {cfg.github_username}/{domain} from template '{template_repo}'"
            )
            log("Would re-enable GitHub Pages")
            log(f"Would configure custom domain: {domain}")
            return result

        with GitHubHost(default_org=cfg.github_username) as host:
            log(f"Replacing repository with template '{template_repo}'")
            deploy = host.deploy_site(domain, template=template_repo, force=True)

            if deploy.repo_created and deploy.repo_existed:
                log(f"Repository replaced: {cfg.github_username}/{domain}", "success")
            elif deploy.repo_created:
                log(f"Repository created (was new): {cfg.github_username}/{domain}", "success")
            else:
                log(f"Repository unchanged: {cfg.github_username}/{domain}", "warning")

            log("GitHub Pages enabled", "success")
            log(f"Custom domain configured: {domain}", "success")

            if not deploy.https_enabled:
                log("HTTPS enforcement pending SSL certificate", "warning")
            else:
                log("HTTPS enforcement enabled", "success")

        return result

    def _on_error(domain: str, exc: BaseException) -> Dict[str, Any]:
        _, category = _categorize_error(exc)
        return {"domain": domain, "error": str(exc), "error_category": category}

    def _text(results: List[Dict[str, Any]]) -> None:
        success_count = sum(1 for r in results if not r.get("error"))
        total_count = len(results)
        click.echo()
        if dry_run:
            click.secho(f"DRY RUN: Would apply template to {total_count} domain(s)", fg="cyan")
        else:
            color = "green" if success_count == total_count else "yellow"
            click.secho(f"Template apply: {success_count}/{total_count} succeeded", fg=color)
        click.echo()

    results = map_items(
        domains,
        _apply_template,
        workers=workers,
        sequential=(dry_run or len(domains) == 1),
        on_error=_on_error,
    )

    render_results(
        results,
        "json" if log_format == "json" else "text",
        csv_fields=["domain", "error", "error_category"],
        text=_text,
    )
    exit_on_errors(results)
