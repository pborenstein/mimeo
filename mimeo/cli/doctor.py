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


def _check_pages_ips() -> tuple[bool, str, str]:
    """Check that GitHub still lists every hardcoded Pages IP.

    mimeo writes GITHUB_PAGES_IPS as apex A records. GitHub publishes the
    current Pages addresses in the ``pages`` field of api.github.com/meta,
    which also carries legacy and IPv6 entries, so the list is used only to
    confirm the hardcoded set, never as the source of records.
    """
    from ..providers.host.github import GITHUB_PAGES_IPS, GITHUB_PAGES_IPV6

    hardcoded = GITHUB_PAGES_IPS + GITHUB_PAGES_IPV6
    try:
        result = subprocess.run(
            ["gh", "api", "meta", "--jq", ".pages"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return False, "gh not installed", "Install gh from https://cli.github.com"
    unreachable = "could not read api.github.com/meta"
    if result.returncode != 0:
        return False, unreachable, "Check network access and 'gh auth status'."
    try:
        listed = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False, unreachable, "Unexpected response from 'gh api meta'."
    if not isinstance(listed, list):
        return False, unreachable, "Unexpected response from 'gh api meta'."
    addresses = {str(entry).split("/")[0] for entry in listed}
    missing = [ip for ip in hardcoded if ip not in addresses]
    if missing:
        return (
            False,
            f"not listed by GitHub: {', '.join(missing)}",
            "Update GITHUB_PAGES_IPS / GITHUB_PAGES_IPV6 in mimeo/providers/host/github.py from "
            "GitHub's Pages docs, then run 'mimeo sync --all'.",
        )
    return True, f"all {len(hardcoded)} listed by GitHub", ""


def _check_nameservers(domain: str, cloudflare_configured: bool = False) -> tuple[bool, str, str]:
    """Check that a domain's nameservers belong to a DNS provider mimeo can write to."""
    from ..providers.registrar.porkbun import lookup_nameservers
    ns = lookup_nameservers(domain)
    if not ns:
        return False, "no NS records found", "Check that the domain is registered and DNS is reachable."
    if all(n.endswith(".porkbun.com") for n in ns):
        return True, "porkbun", ""
    if all(n.endswith(".ns.cloudflare.com") for n in ns):
        if cloudflare_configured:
            return True, "cloudflare", ""
        return (
            False,
            "cloudflare",
            "Add a [cloudflare] section with api_token to the config so mimeo can write the records.",
        )
    return (
        False,
        ", ".join(ns),
        "mimeo cannot write records at this DNS provider -- link will list them for you to add.",
    )


def _check_porkbun_credentials(cfg: Config) -> tuple[bool, str, str]:
    """Check that the Porkbun keys are accepted."""
    from ..providers.registrar.porkbun import PorkbunRegistrar
    try:
        with PorkbunRegistrar(cfg.porkbun_api_key, cfg.porkbun_secret) as registrar:
            registrar._make_request("/ping", {})
    except Exception as e:
        return False, str(e), "Check porkbun.api_key and porkbun.secret_key, and that API access is on."
    return True, "accepted", ""


def _check_cloudflare_credentials(cfg: Config) -> tuple[bool, str, str]:
    """Check that the Cloudflare token is active."""
    from ..providers.dns.cloudflare import CloudflareDNS
    # A token created under "Account API tokens" is verified through the
    # account; one created under a user profile, through the user.
    paths = ["/user/tokens/verify"]
    if cfg.cloudflare_account_id:
        paths.insert(0, f"/accounts/{cfg.cloudflare_account_id}/tokens/verify")
    result: Dict[str, Any] = {}
    error: Exception | None = None
    with CloudflareDNS(cfg.cloudflare_api_token or "", cfg.cloudflare_account_id) as cloudflare:
        for path in paths:
            try:
                result = cloudflare._call("GET", path).get("result") or {}
                error = None
                break
            except Exception as e:
                error = e
    if error is not None:
        return False, str(error), "Check cloudflare.api_token (needs Zone Read and DNS Edit)."
    token_status = str(result.get("status", "unknown"))
    if token_status != "active":
        return False, f"token is {token_status}", "Create a new API token in Cloudflare."
    if not cfg.cloudflare_account_id:
        return True, "active (no account_id: cannot create zones)", ""
    return True, "active", ""


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
      - GitHub still lists mimeo's Pages IPs (api.github.com/meta)
      - Porkbun keys, and the Cloudflare token if configured, are accepted
      - NS records for each DOMAIN belong to a DNS provider mimeo can
        write to (if domains provided)

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
        ("Pages IPs", _check_pages_ips),
    ]

    try:
        cfg: Config | None = Config.load(config)
    except Exception:
        cfg = None  # reported by the config file check
    if cfg is not None:
        loaded = cfg
        checks.append(("Porkbun keys", lambda: _check_porkbun_credentials(loaded)))
        if cfg.cloudflare_api_token:
            checks.append(("Cloudflare token", lambda: _check_cloudflare_credentials(loaded)))

    cloudflare_configured = bool(cfg and cfg.cloudflare_api_token)
    for domain in domains:
        checks.append(
            (f"NS: {domain}", lambda d=domain: _check_nameservers(d, cloudflare_configured))
        )

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
