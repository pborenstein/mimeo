"""Configuration management for Mimeo."""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from mimeo.exceptions import ConfigurationError


@dataclass
class Config:
    """Mimeo configuration."""

    workspace: Path
    porkbun_api_key: str
    porkbun_secret: str
    github_username: str
    default_registrar: str = "porkbun"
    default_host: str = "github"

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

        # Extract configuration with environment variable overrides
        defaults_config = data.get("defaults", {})
        porkbun_config = data.get("porkbun", {})
        github_config = data.get("github", {})

        # Workspace directory
        workspace_str = os.getenv("MIMEO_WORKSPACE")
        if not workspace_str:
            workspace_str = "~/.mimeo/sites"
        workspace = Path(workspace_str).expanduser()

        # Porkbun credentials
        porkbun_api_key = os.getenv("MIMEO_PORKBUN_API_KEY") or porkbun_config.get(
            "api_key"
        )
        porkbun_secret = os.getenv("MIMEO_PORKBUN_SECRET") or porkbun_config.get(
            "secret_key"
        )

        # GitHub username (use default_org from config, or get from gh CLI)
        github_username = os.getenv("MIMEO_GITHUB_USERNAME") or github_config.get(
            "default_org"
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

        return cls(
            workspace=workspace,
            porkbun_api_key=porkbun_api_key,
            porkbun_secret=porkbun_secret,
            github_username=github_username,
            default_registrar=defaults_config.get("registrar", "porkbun"),
            default_host=defaults_config.get("host", "github"),
        )
