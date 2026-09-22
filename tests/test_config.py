"""Tests for configuration management."""

import os
from pathlib import Path

import pytest
from _pytest.capture import CaptureFixture

from mimeo.config import Config
from mimeo.exceptions import ConfigurationError
from mimeo.providers.host.github import DEFAULT_TEMPLATE, TEMPLATE_ORG


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


def test_load_config_from_file(temp_config_file: Path) -> None:
    """Config should load from TOML file."""
    config = Config.load(temp_config_file)

    assert config.porkbun_api_key == "pk1_test_key"
    assert config.porkbun_secret == "sk1_test_secret"
    assert config.github_username == "testuser"


def test_env_var_overrides(temp_config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment variables should override config file values."""
    monkeypatch.setenv("MIMEO_PORKBUN_API_KEY", "env_key")
    monkeypatch.setenv("MIMEO_PORKBUN_SECRET", "env_secret")
    monkeypatch.setenv("MIMEO_GITHUB_USERNAME", "envuser")

    config = Config.load(temp_config_file)

    assert config.porkbun_api_key == "env_key"
    assert config.porkbun_secret == "env_secret"
    assert config.github_username == "envuser"


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


def test_no_schema_version_notices_on_stderr(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """Missing schema_version prints a visible stderr notice."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        "[porkbun]\napi_key = \"pk1_test\"\nsecret_key = \"sk1_test\"\n"
        "[github]\ndefault_org = \"testuser\"\n"
    )
    Config.load(config_file)
    assert "no schema_version" in capsys.readouterr().err


def test_current_schema_version_no_notice(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """schema_version = 1 loads without any stderr notice."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        "schema_version = 1\n"
        "[porkbun]\napi_key = \"pk1_test\"\nsecret_key = \"sk1_test\"\n"
        "[github]\ndefault_org = \"testuser\"\n"
    )
    cfg = Config.load(config_file)
    assert cfg.porkbun_api_key == "pk1_test"
    assert capsys.readouterr().err == ""


def test_future_schema_version_notices_on_stderr(tmp_path: Path, capsys: CaptureFixture[str]) -> None:
    """schema_version higher than current prints a visible stderr notice."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        "schema_version = 999\n"
        "[porkbun]\napi_key = \"pk1_test\"\nsecret_key = \"sk1_test\"\n"
        "[github]\ndefault_org = \"testuser\"\n"
    )
    Config.load(config_file)
    assert "only understands schema_version" in capsys.readouterr().err


def test_invalid_schema_version_raises(tmp_path: Path) -> None:
    """Non-positive schema_version raises ConfigurationError."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        "schema_version = 0\n"
        "[porkbun]\napi_key = \"pk1_test\"\nsecret_key = \"sk1_test\"\n"
        "[github]\ndefault_org = \"testuser\"\n"
    )
    with pytest.raises(ConfigurationError, match="Invalid schema_version"):
        Config.load(config_file)




def test_ignore_domains_default_empty(temp_config_file: Path) -> None:
    """ignore_domains defaults to an empty list."""
    config = Config.load(temp_config_file)
    assert config.ignore_domains == []


def test_ignore_domains_parsed_and_lowercased(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
schema_version = 1

[porkbun]
api_key = "pk1_test"
secret_key = "sk1_test"

[github]
default_org = "testuser"

[defaults]
ignore_domains = ["Example.DEV", "elsewhere.net"]
"""
    )
    config = Config.load(config_file)
    assert config.ignore_domains == ["example.dev", "elsewhere.net"]


def test_ignore_domains_invalid_type(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
schema_version = 1

[porkbun]
api_key = "pk1_test"
secret_key = "sk1_test"

[github]
default_org = "testuser"

[defaults]
ignore_domains = "example.dev"
"""
    )
    with pytest.raises(ConfigurationError) as exc_info:
        Config.load(config_file)
    assert "ignore_domains" in str(exc_info.value)


def test_template_settings_default_to_provider_constants(temp_config_file: Path) -> None:
    """template_org/default_template fall back to the provider defaults."""
    config = Config.load(temp_config_file)
    assert config.template_org == TEMPLATE_ORG
    assert config.default_template == DEFAULT_TEMPLATE


def test_template_settings_parsed_from_file(tmp_path: Path) -> None:
    """github.template_org and defaults.template override the fallbacks."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
schema_version = 1

[porkbun]
api_key = "pk1_test"
secret_key = "sk1_test"

[github]
default_org = "testuser"
template_org = "my-org"

[defaults]
template = "my-template"
"""
    )
    config = Config.load(config_file)
    assert config.template_org == "my-org"
    assert config.default_template == "my-template"


def test_template_settings_env_var_overrides(
    temp_config_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MIMEO_GITHUB_TEMPLATE_ORG / MIMEO_DEFAULT_TEMPLATE win over the file."""
    monkeypatch.setenv("MIMEO_GITHUB_TEMPLATE_ORG", "env-org")
    monkeypatch.setenv("MIMEO_DEFAULT_TEMPLATE", "env-template")

    config = Config.load(temp_config_file)

    assert config.template_org == "env-org"
    assert config.default_template == "env-template"


def test_template_settings_invalid_type(tmp_path: Path) -> None:
    """Non-string template settings raise ConfigurationError."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
schema_version = 1

[porkbun]
api_key = "pk1_test"
secret_key = "sk1_test"

[github]
default_org = "testuser"
template_org = 123
"""
    )
    with pytest.raises(ConfigurationError) as exc_info:
        Config.load(config_file)
    assert "github.template_org" in str(exc_info.value)
