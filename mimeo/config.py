"""Configuration management for Mimeo."""

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import click

from mimeo.exceptions import ConfigurationError
from mimeo.providers.host.github import DEFAULT_TEMPLATE, TEMPLATE_ORG

CURRENT_SCHEMA_VERSION = 1


def _notice(message: str) -> None:
    """Print a config notice to stderr, visible to CLI users."""
    click.secho(message, fg="yellow", err=True)


@dataclass
class Config:
    """Mimeo configuration."""

    porkbun_api_key: str
    porkbun_secret: str
    github_username: str
    template_org: str = TEMPLATE_ORG
    default_template: str = DEFAULT_TEMPLATE
    ignore_domains: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        """Load configuration from file and environment variables.

        Args:
            config_path: Path to config file. Defaults to ~/.config/mimeo/config.toml

        Returns:
            Config instance

        Raises:
            ConfigurationError: If config file is missing or invalid
        """
        if config_path is None:
            config_path = Path.home() / ".config" / "mimeo" / "config.toml"

        if not config_path.exists():
            raise ConfigurationError(
                f"Configuration file not found: {config_path}\n"
                f"Create a config file at {config_path} with your API credentials.\n"
                f"See documentation for config file format."
            )

        try:
            with open(config_path, "rb") as f:
                data = tomllib.load(f)
        except Exception as e:
            raise ConfigurationError(f"Failed to parse config file {config_path}: {e}")

        # Validate schema version. Notices print to stderr directly:
        # warnings.warn is invisible to CLI users (DeprecationWarning is
        # filtered outside __main__), which defeated the point (BUG 6).
        schema_version = data.get("schema_version")
        if schema_version is None:
            _notice(
                f"Config file {config_path} has no schema_version. "
                f"Add 'schema_version = {CURRENT_SCHEMA_VERSION}' to suppress this notice."
            )
        elif not isinstance(schema_version, int) or schema_version < 1:
            raise ConfigurationError(
                f"Invalid schema_version in {config_path}: must be a positive integer"
            )
        elif schema_version > CURRENT_SCHEMA_VERSION:
            _notice(
                f"Config file {config_path} uses schema_version {schema_version}, "
                f"but this version of mimeo only understands schema_version "
                f"{CURRENT_SCHEMA_VERSION}. Some settings may be ignored."
            )

        # Extract configuration with environment variable overrides
        defaults_config = data.get("defaults", {})
        porkbun_config = data.get("porkbun", {})
        github_config = data.get("github", {})

        # Porkbun credentials
        porkbun_api_key = os.getenv("MIMEO_PORKBUN_API_KEY") or porkbun_config.get(
            "api_key"
        )
        porkbun_secret = os.getenv("MIMEO_PORKBUN_SECRET") or porkbun_config.get(
            "secret_key"
        )

        # GitHub username (required; no fallback to gh CLI's authenticated user)
        github_username = os.getenv("MIMEO_GITHUB_USERNAME") or github_config.get(
            "default_org"
        )

        # Template org and default template (optional; fall back to the
        # provider defaults when neither config nor environment sets them)
        template_org = os.getenv("MIMEO_GITHUB_TEMPLATE_ORG") or github_config.get(
            "template_org"
        )
        default_template = os.getenv("MIMEO_DEFAULT_TEMPLATE") or defaults_config.get(
            "template"
        )

        # Validate required credentials
        missing = []
        if not porkbun_api_key:
            missing.append("Porkbun API key (porkbun.api_key or MIMEO_PORKBUN_API_KEY)")
        if not porkbun_secret:
            missing.append("Porkbun secret key (porkbun.secret_key or MIMEO_PORKBUN_SECRET)")
        if not github_username:
            missing.append("GitHub username (github.default_org or MIMEO_GITHUB_USERNAME)")

        if missing:
            raise ConfigurationError(
                "Missing required configuration:\n" + "\n".join(f"  - {m}" for m in missing)
            )

        ignore_domains = defaults_config.get("ignore_domains", [])
        if not isinstance(ignore_domains, list) or not all(
            isinstance(d, str) for d in ignore_domains
        ):
            raise ConfigurationError(
                f"defaults.ignore_domains in {config_path} must be a list of domain names"
            )

        for label, value in (
            ("github.template_org", template_org),
            ("defaults.template", default_template),
        ):
            if value is not None and not isinstance(value, str):
                raise ConfigurationError(
                    f"{label} in {config_path} must be a string"
                )

        return cls(
            porkbun_api_key=porkbun_api_key,
            porkbun_secret=porkbun_secret,
            github_username=github_username,
            template_org=template_org or TEMPLATE_ORG,
            default_template=default_template or DEFAULT_TEMPLATE,
            ignore_domains=[d.lower() for d in ignore_domains],
        )
