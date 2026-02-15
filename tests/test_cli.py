"""Tests for CLI module."""

from pathlib import Path
from typing import Any, List
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from mimeo.cli import create, list, main
from mimeo.config import Config
from mimeo.exceptions import ConfigurationError, HostError, RegistrarError
from mimeo.models import DNSRecord


@pytest.fixture
def runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_config(tmp_path: Path) -> Config:
    """Create mock config."""
    return Config(
        workspace=tmp_path,
        porkbun_api_key="pk1_test",
        porkbun_secret="sk1_test",
        github_username="testuser",
        default_registrar="porkbun",
        default_host="github",
    )


@pytest.fixture
def mock_dns_records() -> List[DNSRecord]:
    """Create mock DNS records."""
    return [
        DNSRecord(type="A", name="", content="185.199.108.153", ttl=600),
        DNSRecord(type="CNAME", name="www", content="testuser.github.io", ttl=600),
    ]


class TestMainCommand:
    """Tests for main CLI command group."""

    def test_main_help(self, runner: CliRunner) -> None:
        """Test main command shows help."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "A tool to generate websites quickly" in result.output

    def test_main_version(self, runner: CliRunner) -> None:
        """Test version flag."""
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "Mimeo" in result.output


class TestCreateCommand:
    """Tests for create command."""

    def test_create_help(self, runner: CliRunner) -> None:
        """Test create command shows help."""
        result = runner.invoke(create, ["--help"])
        assert result.exit_code == 0
        assert "Create and deploy a minimal landing page" in result.output
        assert "DOMAIN" in result.output

    def test_create_requires_domain(self, runner: CliRunner) -> None:
        """Test create command requires domain argument."""
        result = runner.invoke(create, [])
        assert result.exit_code != 0
        assert "Missing argument" in result.output

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.generate_minimal_site")
    @patch("mimeo.cli.GitHubHost")
    @patch("mimeo.cli.PorkbunRegistrar")
    def test_create_success(
        self,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_generate: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
        mock_dns_records: List[DNSRecord],
    ) -> None:
        """Test successful site creation."""
        # Setup mocks
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.return_value = "https://example.com"
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.verify_dns.return_value = True
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar
        mock_registrar_class.github_pages_records.return_value = mock_dns_records

        # Run command
        result = runner.invoke(create, ["example.com"])

        # Verify success
        assert result.exit_code == 0
        assert "Loading configuration" in result.output
        assert "Generating site for example.com" in result.output
        assert "Deploying to GitHub Pages" in result.output
        assert "Configuring DNS records" in result.output
        assert "Site successfully deployed!" in result.output
        assert "https://example.com" in result.output

        # Verify mocks called correctly
        mock_config_load.assert_called_once()
        mock_generate.assert_called_once()
        mock_host_class.assert_called_once_with(default_org="testuser")
        mock_host.deploy_site.assert_called_once()
        mock_registrar_class.github_pages_records.assert_called_once_with(
            "example.com", "testuser"
        )
        mock_registrar.configure_dns.assert_called_once_with("example.com", mock_dns_records)
        mock_registrar.verify_dns.assert_called_once()

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.generate_minimal_site")
    @patch("mimeo.cli.GitHubHost")
    @patch("mimeo.cli.PorkbunRegistrar")
    def test_create_dns_not_verified(
        self,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_generate: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
        mock_dns_records: List[DNSRecord],
    ) -> None:
        """Test create command when DNS verification fails."""
        # Setup mocks
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.return_value = "https://example.com"
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.verify_dns.return_value = False  # DNS not verified
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar
        mock_registrar_class.github_pages_records.return_value = mock_dns_records

        # Run command
        result = runner.invoke(create, ["example.com"])

        # Verify success but with warning
        assert result.exit_code == 0
        assert "DNS records created but not yet propagated" in result.output
        assert "Site successfully deployed!" in result.output

    @patch("mimeo.cli.Config.load")
    def test_create_config_error(self, mock_config_load: Any, runner: CliRunner) -> None:
        """Test create command handles configuration errors."""
        mock_config_load.side_effect = ConfigurationError("Config file not found")

        result = runner.invoke(create, ["example.com"])

        assert result.exit_code == 1
        assert "Configuration error" in result.output
        assert "Config file not found" in result.output

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.generate_minimal_site")
    @patch("mimeo.cli.GitHubHost")
    def test_create_deployment_error(
        self,
        mock_host_class: Any,
        mock_generate: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """Test create command handles deployment errors."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.side_effect = HostError("GitHub API failed")
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        result = runner.invoke(create, ["example.com"])

        assert result.exit_code == 1
        assert "Deployment error" in result.output
        assert "GitHub API failed" in result.output

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.generate_minimal_site")
    @patch("mimeo.cli.GitHubHost")
    @patch("mimeo.cli.PorkbunRegistrar")
    def test_create_dns_error(
        self,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_generate: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
        mock_dns_records: List[DNSRecord],
    ) -> None:
        """Test create command handles DNS configuration errors."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.return_value = "https://example.com"
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.configure_dns.side_effect = RegistrarError("Porkbun API failed")
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar
        mock_registrar_class.github_pages_records.return_value = mock_dns_records

        result = runner.invoke(create, ["example.com"])

        assert result.exit_code == 1
        assert "DNS configuration error" in result.output
        assert "Porkbun API failed" in result.output

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.generate_minimal_site")
    def test_create_content_generation_error(
        self,
        mock_generate: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """Test create command handles content generation errors."""
        mock_config_load.return_value = mock_config
        mock_generate.side_effect = OSError("Failed to write file")

        result = runner.invoke(create, ["example.com"])

        assert result.exit_code == 1
        assert "Unexpected error" in result.output

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.generate_minimal_site")
    @patch("mimeo.cli.GitHubHost")
    @patch("mimeo.cli.PorkbunRegistrar")
    def test_create_with_custom_config(
        self,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_generate: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
        mock_dns_records: List[DNSRecord],
        tmp_path: Path,
    ) -> None:
        """Test create command with custom config file."""
        # Create a config file
        config_file = tmp_path / "custom.toml"
        config_file.write_text("")

        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.return_value = "https://example.com"
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.verify_dns.return_value = True
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar
        mock_registrar_class.github_pages_records.return_value = mock_dns_records

        result = runner.invoke(create, ["example.com", "--config", str(config_file)])

        assert result.exit_code == 0
        mock_config_load.assert_called_once_with(config_file)

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.generate_minimal_site")
    @patch("mimeo.cli.GitHubHost")
    @patch("mimeo.cli.PorkbunRegistrar")
    def test_create_generates_content_in_temp_dir(
        self,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_generate: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
        mock_dns_records: List[DNSRecord],
    ) -> None:
        """Test that create command generates content in temporary directory."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.return_value = "https://example.com"
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.verify_dns.return_value = True
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar
        mock_registrar_class.github_pages_records.return_value = mock_dns_records

        result = runner.invoke(create, ["example.com"])

        assert result.exit_code == 0
        # Verify generate_minimal_site was called with Path object
        args = mock_generate.call_args[0]
        assert args[0] == "example.com"
        assert isinstance(args[1], Path)

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.generate_minimal_site")
    @patch("mimeo.cli.GitHubHost")
    @patch("mimeo.cli.PorkbunRegistrar")
    def test_create_displays_repository_url(
        self,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_generate: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
        mock_dns_records: List[DNSRecord],
    ) -> None:
        """Test that create command displays repository URL in output."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.return_value = "https://example.com"
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.verify_dns.return_value = True
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar
        mock_registrar_class.github_pages_records.return_value = mock_dns_records

        result = runner.invoke(create, ["example.com"])

        assert result.exit_code == 0
        assert "https://github.com/testuser/example.com" in result.output

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.generate_minimal_site")
    @patch("mimeo.cli.GitHubHost")
    @patch("mimeo.cli.PorkbunRegistrar")
    def test_create_passes_github_username_to_host(
        self,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_generate: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
        mock_dns_records: List[DNSRecord],
    ) -> None:
        """Test that create command passes GitHub username to host provider."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.return_value = "https://example.com"
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.verify_dns.return_value = True
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar
        mock_registrar_class.github_pages_records.return_value = mock_dns_records

        result = runner.invoke(create, ["example.com"])

        assert result.exit_code == 0
        mock_host_class.assert_called_once_with(default_org="testuser")

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.generate_minimal_site")
    @patch("mimeo.cli.GitHubHost")
    @patch("mimeo.cli.PorkbunRegistrar")
    def test_create_passes_credentials_to_registrar(
        self,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_generate: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
        mock_dns_records: List[DNSRecord],
    ) -> None:
        """Test that create command passes credentials to registrar."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.return_value = "https://example.com"
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.verify_dns.return_value = True
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar
        mock_registrar_class.github_pages_records.return_value = mock_dns_records

        result = runner.invoke(create, ["example.com"])

        assert result.exit_code == 0
        mock_registrar_class.assert_called_with("pk1_test", "sk1_test")


class TestListCommand:
    """Tests for list CLI command."""

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.GitHubHost")
    def test_list_shows_repositories(
        self,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """Test list command shows mimeo repositories."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.list_mimeo_repositories.return_value = [
            {
                "name": "example.com",
                "url": "https://github.com/testuser/example.com",
                "homepage": "https://example.com",
                "updatedAt": "2026-02-15T12:00:00Z",
            },
            {
                "name": "test.com",
                "url": "https://github.com/testuser/test.com",
                "homepage": None,
                "updatedAt": "2026-02-14T10:00:00Z",
            },
        ]
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        result = runner.invoke(list, [])

        assert result.exit_code == 0
        assert "Mimeo-managed sites (2)" in result.output
        assert "example.com" in result.output
        assert "test.com" in result.output
        assert "https://github.com/testuser/example.com" in result.output
        assert "https://example.com" in result.output

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.GitHubHost")
    def test_list_no_repositories(
        self,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """Test list command when no repositories exist."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.list_mimeo_repositories.return_value = []
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        result = runner.invoke(list, [])

        assert result.exit_code == 0
        assert "No mimeo-managed sites found" in result.output
        assert "mimeo create example.com" in result.output

    @patch("mimeo.cli.Config.load")
    def test_list_config_error(
        self,
        mock_config_load: Any,
        runner: CliRunner,
    ) -> None:
        """Test list command with configuration error."""
        mock_config_load.side_effect = ConfigurationError("Config not found")

        result = runner.invoke(list, [])

        assert result.exit_code == 1
        assert "Configuration error" in result.output
