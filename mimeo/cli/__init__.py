"""Command-line interface for Mimeo."""

import click

from .. import __version__
from ._processing import _categorize_error, _emit, set_log_format
from .create import create
from .dns import dns
from .doctor import (
    _check_config,
    _check_gh_auth,
    _check_gh_installed,
    _check_gh_workflow_scope,
    _check_nameservers,
    _check_python_version,
    doctor,
)
from .fix import fix
from .list_cmd import list_sites
from .registrar import registrar, registrar_list
from .status import status
from .template import template


@click.group()
@click.version_option(version=__version__, prog_name="Mimeo")
@click.option(
    "--log-format",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    help="Log output format (default: text)",
)
def main(log_format: str) -> None:
    """A tool to generate websites quickly"""
    set_log_format(log_format)


main.add_command(create)
main.add_command(status)
main.add_command(list_sites)
main.add_command(dns)
main.add_command(template)
main.add_command(fix)
main.add_command(registrar)
main.add_command(doctor)


__all__ = [
    "main",
    "create",
    "status",
    "list_sites",
    "dns",
    "template",
    "fix",
    "registrar",
    "registrar_list",
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
