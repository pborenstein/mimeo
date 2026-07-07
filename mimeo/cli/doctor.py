"""Doctor command for checking prerequisites."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

import click

from ..config import Config
from ..exceptions import EXIT_CONFIG, ConfigurationError
from ._processing import _emit, get_log_format


def _check_python_version() -> tuple[bool, str, str]:
    """Check that Python is >= 3.11."""
    major, minor = sys.version_info[:2]
    if major >= 3 and minor >= 11:
        return True, f"Python {major}.{minor}", ""
    return False, f"Python {major}.{minor}", "Install Python 3.11 or later."


def _check_gh_installed() -> tuple[bool, str, str]:
    """Check that the gh CLI is installed."""
    try:
        result = subprocess.run(
            ["gh", "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        version_line = result.stdout.splitlines()[0] if result.stdout else "gh"
        return True, version_line, ""
    except FileNotFoundError:
        return False, "not found", "Install gh from https://cli.github.com"


def _check_gh_auth() -> tuple[bool, str, str]:
    """Check that gh is authenticated."""
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return True, "authenticated", ""
        return False, "not authenticated", "Run 'gh auth login' to authenticate."
    except FileNotFoundError:
        return False, "gh not installed", "Install gh from https://cli.github.com"


def _check_gh_workflow_scope() -> tuple[bool, str, str]:
    """Check that the gh token has the 'workflow' scope."""
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return False, "cannot check (not authenticated)", "Run 'gh auth login' first."
        output = result.stdout + result.stderr
        for line in output.splitlines():
            if "Token scopes" in line:
                if "'workflow'" in line or '"workflow"' in line:
                    return True, "workflow scope present", ""
                return (
                    False,
                    "workflow scope missing",
                    "Re-authenticate with workflow scope: "
                    "gh auth login --scopes repo,workflow",
                )
        return False, "could not determine scopes", "Re-authenticate: gh auth login --scopes repo,workflow"
    except FileNotFoundError:
        return False, "gh not installed", "Install gh from https://cli.github.com"


def _check_nameservers(domain: str) -> tuple[bool, str, str]:
    """Check that a domain's nameservers point to Porkbun."""
    from ..providers.registrar.porkbun import PORKBUN_NAMESERVERS, lookup_nameservers
    ns = lookup_nameservers(domain)
    expected = sorted(PORKBUN_NAMESERVERS)
    if not ns:
        return False, "no NS records found", "Check that the domain is registered and DNS is reachable."
    if sorted(ns) == expected:
        return True, "porkbun", ""
    return False, ", ".join(ns), "Nameservers don't point to Porkbun -- DNS config will be skipped on create."


def _check_config(config_path: Path | None) -> tuple[bool, str, str]:
    """Check that the config file exists and is valid."""
    if config_path is None:
        config_path = Path.home() / ".config" / "mimeo" / "config.toml"
    if not config_path.exists():
        return (
            False,
            f"not found: {config_path}",
            f"Create {config_path} with your API credentials. See README for format.",
        )
    try:
        Config.load(config_path)
        return True, str(config_path), ""
    except ConfigurationError as e:
        first_line = str(e).splitlines()[0]
        return False, first_line, "Fix the configuration issues listed above."


@click.command()
@click.option(
    "--config",
    type=click.Path(path_type=Path),
    help="Path to config file (default: ~/.config/mimeo/config.toml)",
)
@click.argument("domains", nargs=-1)
def doctor(config: Path | None, domains: tuple[str, ...]) -> None:
    """Check that all prerequisites for mimeo are met.

    Optionally checks nameserver configuration for one or more domains.

    \b
    Verifies:
      - Python version >= 3.11
      - gh CLI is installed
      - gh CLI is authenticated
      - GitHub token has the 'workflow' scope
      - Config file exists and is valid
      - NS records for each DOMAIN point to Porkbun (if domains provided)

    \b
    Examples:
        mimeo doctor
        mimeo doctor example.com
        mimeo doctor site1.com site2.com site3.com

    Prints a pass/fail result for each check with remediation
    instructions for any failures.
    """
    log_format = get_log_format()

    checks: List[tuple[str, Any]] = [
        ("Python >= 3.11", _check_python_version),
        ("gh installed", _check_gh_installed),
        ("gh authenticated", _check_gh_auth),
        ("workflow scope", _check_gh_workflow_scope),
        ("config file", lambda: _check_config(config)),
    ]

    for domain in domains:
        checks.append((f"NS: {domain}", lambda d=domain: _check_nameservers(d)))

    all_ok = True
    if log_format == "text":
        click.echo()
    for label, check_fn in checks:
        ok, detail, fix = check_fn()
        if not ok:
            all_ok = False
        if log_format == "json":
            record: Dict[str, Any] = {"check": label, "ok": ok, "detail": detail}
            if not ok and fix:
                record["fix"] = fix
            _emit("info" if ok else "error", json.dumps(record))
        else:
            if ok:
                click.secho("  ok  ", fg="green", nl=False, bold=True)
            else:
                click.secho(" fail ", fg="red", nl=False, bold=True)
            click.echo(f"  {label:<22} {detail}")
            if not ok and fix:
                click.secho(f"            -> {fix}", fg="yellow")

    if log_format == "text":
        click.echo()
        if all_ok:
            click.secho("All checks passed.", fg="green", bold=True)
        else:
            click.secho("Some checks failed. Address the issues above before running mimeo.", fg="red")
    else:
        _emit("info" if all_ok else "error", "all checks passed" if all_ok else "some checks failed")

    if not all_ok:
        sys.exit(EXIT_CONFIG)
