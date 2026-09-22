"""Command-line interface for Mimeo."""

import click

from .. import __version__
from ._processing import (
    _categorize_error,
    _emit,
    set_cli_overrides,
    set_log_format,
)
from .create import create
from .doctor import (
    _check_config,
    _check_gh_auth,
    _check_gh_installed,
    _check_gh_workflow_scope,
    _check_nameservers,
    _check_python_version,
    doctor,
)
from .status import status
from .sync import sync


@click.group()
@click.version_option(version=__version__, prog_name="Mimeo")
@click.option(
    "--log-format",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    help="Log output format (default: text)",
)
@click.option(
    "--template-org",
    metavar="ORG",
    default=None,
    help="Org holding template repositories (overrides github.template_org)",
)
@click.option(
    "--deploy-org",
    metavar="ORG",
    default=None,
    help="GitHub user/org where site repositories are created "
    "(overrides github.default_org)",
)
def main(
    log_format: str, template_org: str | None, deploy_org: str | None
) -> None:
    """Provision and manage custom-domain sites on GitHub Pages."""
    set_log_format(log_format)
    set_cli_overrides(template_org, deploy_org)


main.add_command(create)
main.add_command(status)
main.add_command(sync)
main.add_command(doctor)


__all__ = [
    "main",
    "create",
    "status",
    "sync",
    "doctor",
    "_check_config",
    "_check_gh_auth",
    "_check_gh_installed",
    "_check_gh_workflow_scope",
    "_check_nameservers",
    "_check_python_version",
    "_categorize_error",
    "_emit",
]
