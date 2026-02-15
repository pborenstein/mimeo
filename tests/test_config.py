"""Tests for configuration management."""

import os
from pathlib import Path

import pytest

from mimeo.config import Config
from mimeo.exceptions import ConfigurationError


@pytest.fixture
def temp_config_file(tmp_path: Path) -> Path:
    """Create a temporary config file."""
    config_dir = tmp_path / "mimeo"
    config_dir.mkdir()
    config_file = config_dir / "config.toml"
    config_file.write_text(
        """
[porkbun]
api_key = "pk1_test_key"
secret_key = "sk1_test_secret"

[github]
default_org = "testuser"
"""
    )
    return config_file


@pytest.fixture
def minimal_config_file(tmp_path: Path) -> Path:
    """Create a minimal config file without optional fields."""
    config_dir = tmp_path / "mimeo"
    config_dir.mkdir()
    config_file = config_dir / "config.toml"
    config_file.write_text(
        """
[porkbun]
api_key = "pk1_test"
secret_key = "sk1_test"

[github]
default_org = "testuser"
"""
    )
    return config_file


def test_load_config_from_file(temp_config_file: Path) -> None:
    """Config should load from TOML file."""
    config = Config.load(temp_config_file)

    assert config.porkbun_api_key == "pk1_test_key"
    assert config.porkbun_secret == "sk1_test_secret"
    assert config.github_username == "testuser"
    assert config.default_registrar == "porkbun"
    assert config.default_host == "github"


def test_load_config_with_defaults(minimal_config_file: Path) -> None:
    """Config should use defaults for optional fields."""
    config = Config.load(minimal_config_file)

    assert config.workspace == Path.home() / ".mimeo" / "sites"
    assert config.default_registrar == "porkbun"
    assert config.default_host == "github"


def test_env_var_overrides(temp_config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment variables should override config file values."""
    monkeypatch.setenv("MIMEO_PORKBUN_API_KEY", "env_key")
    monkeypatch.setenv("MIMEO_PORKBUN_SECRET", "env_secret")
    monkeypatch.setenv("MIMEO_GITHUB_USERNAME", "envuser")
    monkeypatch.setenv("MIMEO_WORKSPACE", "/tmp/custom")

    config = Config.load(temp_config_file)

    assert config.porkbun_api_key == "env_key"
    assert config.porkbun_secret == "env_secret"
    assert config.github_username == "envuser"
    assert config.workspace == Path("/tmp/custom")


def test_missing_config_file() -> None:
    """Should raise ConfigurationError if config file doesn't exist."""
    with pytest.raises(ConfigurationError, match="Configuration file not found"):
        Config.load(Path("/nonexistent/config.toml"))


def test_missing_porkbun_api_key(tmp_path: Path) -> None:
    """Should raise ConfigurationError if Porkbun API key is missing."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[providers.porkbun]
api_secret = "sk1_test"

[providers.github]
username = "testuser"
"""
    )

    with pytest.raises(ConfigurationError, match="Missing required configuration"):
        Config.load(config_file)


def test_missing_porkbun_secret(tmp_path: Path) -> None:
    """Should raise ConfigurationError if Porkbun secret is missing."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[providers.porkbun]
api_key = "pk1_test"

[providers.github]
username = "testuser"
"""
    )

    with pytest.raises(ConfigurationError, match="Missing required configuration"):
        Config.load(config_file)


def test_missing_github_username(tmp_path: Path) -> None:
    """Should raise ConfigurationError if GitHub username is missing."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[providers.porkbun]
api_key = "pk1_test"
api_secret = "sk1_test"
"""
    )

    with pytest.raises(ConfigurationError, match="Missing required configuration"):
        Config.load(config_file)


def test_invalid_toml(tmp_path: Path) -> None:
    """Should raise ConfigurationError if TOML is invalid."""
    config_file = tmp_path / "config.toml"
    config_file.write_text("invalid toml [[[")

    with pytest.raises(ConfigurationError, match="Failed to parse config file"):
        Config.load(config_file)


def test_workspace_expands_tilde(temp_config_file: Path) -> None:
    """Workspace path should expand ~ to home directory."""
    config = Config.load(temp_config_file)
    assert str(config.workspace).startswith(str(Path.home()))
    assert "~" not in str(config.workspace)
