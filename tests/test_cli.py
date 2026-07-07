"""Tests for CLI module."""

import json
from pathlib import Path
from typing import Any, List
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from mimeo.cli import (
    _check_config,
    _check_gh_auth,
    _check_gh_installed,
    _check_gh_workflow_scope,
    _check_nameservers,
    _check_python_version,
    create,
    doctor,
    list_sites,
    main,
    registrar_list,
)

from mimeo.config import Config
from mimeo.exceptions import ConfigurationError, HostError, RegistrarError
from mimeo.models import DNSRecord, NameserverCheckResult
from mimeo.providers.base import DeployResult


# Patch target prefixes for each submodule
_CREATE = "mimeo.cli.create"
_LIST = "mimeo.cli.list_cmd"
_DOCTOR = "mimeo.cli.doctor"
_REGISTRAR = "mimeo.cli.registrar"
_PROCESSING = "mimeo.cli._processing"


@pytest.fixture
def runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_config() -> Config:
    """Create mock config."""
    return Config(
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
        assert "Provision and manage custom-domain sites on GitHub Pages" in result.output

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
        assert "Create and deploy new sites" in result.output
        assert "DOMAINS" in result.output

    def test_create_requires_domain(self, runner: CliRunner) -> None:
        """Test create command requires domain argument."""
        result = runner.invoke(create, [])
        assert result.exit_code != 0
        assert "Missing argument" in result.output

    @patch("mimeo.config.Config.load")
    @patch(f"{_CREATE}.GitHubHost")
    @patch(f"{_CREATE}.PorkbunRegistrar")
    @patch(f"{_CREATE}.PorkbunDNSProvider")
    def test_create_success(
        self,
        mock_dns_provider_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
        mock_dns_records: List[DNSRecord],
    ) -> None:
        """Test successful site creation."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.return_value = DeployResult(
            url="https://example.com", repo_created=True, https_enabled=True
        )
        mock_host.required_dns_records.return_value = mock_dns_records
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(
            ok=True, actual=[], expected=[]
        )
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        mock_dns_provider = MagicMock()
        mock_dns_provider.verify_dns.return_value = True
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(create, ["example.com"])

        assert result.exit_code == 0
        assert "Configuring GitHub repository" in result.output
        assert "Configuring DNS records" in result.output
        assert "Successfully created: 1/1 domain(s)" in result.output
        assert "https://example.com" in result.output

        mock_config_load.assert_called_once()
        mock_host_class.assert_called_once_with(default_org="testuser")
        mock_host.deploy_site.assert_called_once()
        mock_host.required_dns_records.assert_called_once_with("example.com")
        mock_registrar.check_nameservers.assert_called_once_with("example.com")
        mock_dns_provider.configure_dns.assert_called_once_with("example.com", mock_dns_records)
        mock_dns_provider.verify_dns.assert_called_once()

    @patch("mimeo.config.Config.load")
    @patch(f"{_CREATE}.GitHubHost")
    @patch(f"{_CREATE}.PorkbunRegistrar")
    @patch(f"{_CREATE}.PorkbunDNSProvider")
    def test_create_dns_not_verified(
        self,
        mock_dns_provider_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
        mock_dns_records: List[DNSRecord],
    ) -> None:
        """Test create command when DNS verification fails."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.return_value = DeployResult(
            url="https://example.com", repo_created=True, https_enabled=True
        )
        mock_host.required_dns_records.return_value = mock_dns_records
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(
            ok=True, actual=[], expected=[]
        )
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        mock_dns_provider = MagicMock()
        mock_dns_provider.verify_dns.return_value = False
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(create, ["example.com"])

        assert result.exit_code == 0
        assert "DNS records created but not yet propagated" in result.output
        assert "Successfully created: 1/1 domain(s)" in result.output

    @patch("mimeo.config.Config.load")
    def test_create_config_error(self, mock_config_load: Any, runner: CliRunner) -> None:
        """Test create command handles configuration errors."""
        mock_config_load.side_effect = ConfigurationError("Config file not found")

        result = runner.invoke(create, ["example.com"])

        assert result.exit_code == 2
        assert "Config file not found" in result.output

    @patch("mimeo.config.Config.load")
    @patch(f"{_CREATE}.GitHubHost")
    def test_create_deployment_error(
        self,
        mock_host_class: Any,
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

        assert result.exit_code == 5
        assert "GitHub API failed" in result.output

    @patch("mimeo.config.Config.load")
    @patch(f"{_CREATE}.GitHubHost")
    @patch(f"{_CREATE}.PorkbunRegistrar")
    @patch(f"{_CREATE}.PorkbunDNSProvider")
    def test_create_dns_error(
        self,
        mock_dns_provider_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
        mock_dns_records: List[DNSRecord],
    ) -> None:
        """Test create command handles DNS configuration errors gracefully."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.return_value = DeployResult(
            url="https://example.com", repo_created=True, https_enabled=True
        )
        mock_host.required_dns_records.return_value = mock_dns_records
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(
            ok=True, actual=[], expected=[]
        )
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        mock_dns_provider = MagicMock()
        mock_dns_provider.configure_dns.side_effect = RegistrarError("Porkbun API failed")
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(create, ["example.com"])

        assert result.exit_code == 0
        assert "DNS configuration failed" in result.output
        assert "Porkbun API failed" in result.output
        assert "Site deployed but DNS not configured" in result.output

    @patch("mimeo.config.Config.load")
    @patch(f"{_CREATE}.GitHubHost")
    @patch(f"{_CREATE}.PorkbunRegistrar")
    @patch(f"{_CREATE}.PorkbunDNSProvider")
    def test_create_ns_mismatch_skips_dns(
        self,
        mock_dns_provider_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
        mock_dns_records: List[DNSRecord],
    ) -> None:
        """When NS points elsewhere, DNS config is skipped with a warning."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.return_value = DeployResult(
            url="https://example.com", repo_created=True, https_enabled=True
        )
        mock_host.required_dns_records.return_value = mock_dns_records
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(
            ok=False,
            actual=["ns1.cloudflare.com", "ns2.cloudflare.com"],
            expected=["curitiba.ns.porkbun.com"],
        )
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        mock_dns_provider = MagicMock()
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(create, ["example.com"])

        assert result.exit_code == 0
        assert "NS records point to" in result.output
        assert "skipping DNS config" in result.output
        mock_dns_provider.configure_dns.assert_not_called()

    @patch("mimeo.config.Config.load")
    @patch(f"{_CREATE}.GitHubHost")
    @patch(f"{_CREATE}.PorkbunRegistrar")
    @patch(f"{_CREATE}.PorkbunDNSProvider")
    def test_create_with_custom_config(
        self,
        mock_dns_provider_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
        mock_dns_records: List[DNSRecord],
        tmp_path: Path,
    ) -> None:
        """Test create command with custom config file."""
        config_file = tmp_path / "custom.toml"
        config_file.write_text("")

        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.return_value = DeployResult(
            url="https://example.com", repo_created=True, https_enabled=True
        )
        mock_host.required_dns_records.return_value = mock_dns_records
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(
            ok=True, actual=[], expected=[]
        )
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        mock_dns_provider = MagicMock()
        mock_dns_provider.verify_dns.return_value = True
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(create, ["example.com", "--config", str(config_file)])

        assert result.exit_code == 0
        mock_config_load.assert_called_once_with(config_file)

    @patch("mimeo.config.Config.load")
    @patch(f"{_CREATE}.GitHubHost")
    @patch(f"{_CREATE}.PorkbunRegistrar")
    @patch(f"{_CREATE}.PorkbunDNSProvider")
    def test_create_calls_deploy_site(
        self,
        mock_dns_provider_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
        mock_dns_records: List[DNSRecord],
    ) -> None:
        """Test that create command calls deploy_site on the host."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.return_value = DeployResult(
            url="https://example.com", repo_created=True, https_enabled=True
        )
        mock_host.required_dns_records.return_value = mock_dns_records
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(
            ok=True, actual=[], expected=[]
        )
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        mock_dns_provider = MagicMock()
        mock_dns_provider.verify_dns.return_value = True
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(create, ["example.com"])

        assert result.exit_code == 0

    @patch("mimeo.config.Config.load")
    @patch(f"{_CREATE}.GitHubHost")
    @patch(f"{_CREATE}.PorkbunRegistrar")
    @patch(f"{_CREATE}.PorkbunDNSProvider")
    def test_create_displays_repository_url(
        self,
        mock_dns_provider_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
        mock_dns_records: List[DNSRecord],
    ) -> None:
        """Test that create command displays repository URL in output."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.return_value = DeployResult(
            url="https://example.com", repo_created=True, https_enabled=True
        )
        mock_host.required_dns_records.return_value = mock_dns_records
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(
            ok=True, actual=[], expected=[]
        )
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        mock_dns_provider = MagicMock()
        mock_dns_provider.verify_dns.return_value = True
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(create, ["example.com"])

        assert result.exit_code == 0
        assert "https://github.com/testuser/example.com" in result.output

    @patch("mimeo.config.Config.load")
    @patch(f"{_CREATE}.GitHubHost")
    @patch(f"{_CREATE}.PorkbunRegistrar")
    @patch(f"{_CREATE}.PorkbunDNSProvider")
    def test_create_passes_github_username_to_host(
        self,
        mock_dns_provider_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
        mock_dns_records: List[DNSRecord],
    ) -> None:
        """Test that create command passes GitHub username to host provider."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.return_value = DeployResult(
            url="https://example.com", repo_created=True, https_enabled=True
        )
        mock_host.required_dns_records.return_value = mock_dns_records
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(
            ok=True, actual=[], expected=[]
        )
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        mock_dns_provider = MagicMock()
        mock_dns_provider.verify_dns.return_value = True
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(create, ["example.com"])

        assert result.exit_code == 0
        mock_host_class.assert_called_once_with(default_org="testuser")

    @patch("mimeo.config.Config.load")
    @patch(f"{_CREATE}.GitHubHost")
    @patch(f"{_CREATE}.PorkbunRegistrar")
    @patch(f"{_CREATE}.PorkbunDNSProvider")
    def test_create_passes_credentials_to_registrar(
        self,
        mock_dns_provider_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
        mock_dns_records: List[DNSRecord],
    ) -> None:
        """Test that create command passes credentials to registrar and DNS provider."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.return_value = DeployResult(
            url="https://example.com", repo_created=True, https_enabled=True
        )
        mock_host.required_dns_records.return_value = mock_dns_records
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(
            ok=True, actual=[], expected=[]
        )
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        mock_dns_provider = MagicMock()
        mock_dns_provider.verify_dns.return_value = True
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(create, ["example.com"])

        assert result.exit_code == 0
        mock_registrar_class.assert_called_with("pk1_test", "sk1_test")
        mock_dns_provider_class.assert_called_with("pk1_test", "sk1_test")

    @patch("mimeo.config.Config.load")
    @patch(f"{_CREATE}.GitHubHost")
    @patch(f"{_CREATE}.PorkbunRegistrar")
    @patch(f"{_CREATE}.PorkbunDNSProvider")
    def test_create_multiple_domains_concurrent(
        self,
        mock_dns_provider_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
        mock_dns_records: List[DNSRecord],
    ) -> None:
        """Test create command with multiple domains processes concurrently."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.side_effect = lambda domain, **kw: DeployResult(
            url=f"https://{domain}", repo_created=True, https_enabled=True
        )
        mock_host.required_dns_records.return_value = mock_dns_records
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(
            ok=True, actual=[], expected=[]
        )
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        mock_dns_provider = MagicMock()
        mock_dns_provider.verify_dns.return_value = True
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(create, ["site1.com", "site2.com", "site3.com"])

        assert result.exit_code == 0
        assert "site1.com started" in result.output
        assert "site2.com started" in result.output
        assert "site3.com started" in result.output
        assert "site1.com completed" in result.output
        assert "site2.com completed" in result.output
        assert "site3.com completed" in result.output
        assert "Successfully created: 3/3 domain(s)" in result.output

        assert mock_host.deploy_site.call_count == 3
        assert mock_dns_provider.configure_dns.call_count == 3

    @patch("mimeo.config.Config.load")
    @patch(f"{_CREATE}.GitHubHost")
    @patch(f"{_CREATE}.PorkbunRegistrar")
    @patch(f"{_CREATE}.PorkbunDNSProvider")
    def test_create_multiple_domains_sequential(
        self,
        mock_dns_provider_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
        mock_dns_records: List[DNSRecord],
    ) -> None:
        """Test create command with --sequential flag."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.side_effect = lambda domain, **kw: DeployResult(
            url=f"https://{domain}", repo_created=True, https_enabled=True
        )
        mock_host.required_dns_records.return_value = mock_dns_records
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(
            ok=True, actual=[], expected=[]
        )
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        mock_dns_provider = MagicMock()
        mock_dns_provider.verify_dns.return_value = True
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(create, ["site1.com", "site2.com", "--sequential"])

        assert result.exit_code == 0
        assert "Processing site1.com" in result.output
        assert "Processing site2.com" in result.output
        assert "Successfully created: 2/2 domain(s)" in result.output


class TestCreateSkipDns:
    """Tests for create --skip-dns."""

    @patch("mimeo.config.Config.load")
    @patch(f"{_CREATE}.GitHubHost")
    def test_create_skip_dns(
        self,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """--skip-dns skips DNS configuration entirely."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.return_value = DeployResult(
            url="https://example.com", repo_created=True, https_enabled=True
        )
        mock_host.required_dns_records.return_value = []
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        result = runner.invoke(create, ["example.com", "--skip-dns"])

        assert result.exit_code == 0
        assert "Skipping DNS configuration" in result.output


class TestListCommand:
    """Tests for list CLI command."""

    @patch("mimeo.config.Config.load")
    @patch(f"{_LIST}.GitHubHost")
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

        result = runner.invoke(list_sites, [])

        assert result.exit_code == 0
        assert "NAME" in result.output
        assert "example.com" in result.output
        assert "test.com" in result.output
        assert "https://example.com" in result.output

    @patch("mimeo.config.Config.load")
    @patch(f"{_LIST}.GitHubHost")
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

        result = runner.invoke(list_sites, [])

        assert result.exit_code == 0
        assert "No mimeo-managed sites found" in result.output
        assert "mimeo create example.com" in result.output

    @patch("mimeo.config.Config.load")
    def test_list_config_error(
        self,
        mock_config_load: Any,
        runner: CliRunner,
    ) -> None:
        """Test list command with configuration error."""
        mock_config_load.side_effect = ConfigurationError("Config not found")

        result = runner.invoke(list_sites, [])

        assert result.exit_code == 2
        assert "Config not found" in result.output

    @patch("mimeo.config.Config.load")
    @patch(f"{_LIST}.GitHubHost")
    def test_list_json_format(
        self,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """Test list command with JSON output format."""
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

        result = runner.invoke(list_sites, ["--format", "json"])

        assert result.exit_code == 0

        import json

        output_data = json.loads(result.output)
        assert len(output_data) == 2
        assert output_data[0]["name"] == "example.com"
        assert output_data[0]["repository"] == "https://github.com/testuser/example.com"
        assert output_data[0]["site"] == "https://example.com"
        assert output_data[0]["updated"] == "2026-02-15"
        assert output_data[1]["name"] == "test.com"
        assert output_data[1]["site"] == "https://test.com"

    @patch("mimeo.config.Config.load")
    @patch(f"{_LIST}.GitHubHost")
    def test_list_json_format_empty(
        self,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """Test list command with JSON format when no repositories exist."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.list_mimeo_repositories.return_value = []
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        result = runner.invoke(list_sites, ["--format", "json"])

        assert result.exit_code == 0
        assert result.output.strip() == "[]"

    @patch("mimeo.config.Config.load")
    @patch(f"{_LIST}.GitHubHost")
    def test_list_csv_format(
        self,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """Test list command with CSV output format."""
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

        result = runner.invoke(list_sites, ["--format", "csv"])

        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert len(lines) == 3
        assert lines[0] == "name,repository,site,updated"
        assert (
            "example.com,https://github.com/testuser/example.com,https://example.com,2026-02-15"
            in lines[1]
        )
        assert (
            "test.com,https://github.com/testuser/test.com,https://test.com,2026-02-14" in lines[2]
        )

    @patch("mimeo.config.Config.load")
    @patch(f"{_LIST}.GitHubHost")
    def test_list_csv_format_empty(
        self,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """Test list command with CSV format when no repositories exist."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.list_mimeo_repositories.return_value = []
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        result = runner.invoke(list_sites, ["--format", "csv"])

        assert result.exit_code == 0
        assert result.output.strip() == "name,repository,site,updated"

    @patch("mimeo.config.Config.load")
    @patch(f"{_LIST}.GitHubHost")
    def test_list_health_text_format(
        self,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """Test list --health shows health status in text output."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.list_mimeo_repositories.return_value = [
            {
                "name": "example.com",
                "url": "https://github.com/testuser/example.com",
                "homepage": "https://example.com",
                "updatedAt": "2026-02-15T12:00:00Z",
            },
        ]
        mock_host.get_pages_health.return_value = {
            "pages_configured": True,
            "https_enforced": False,
            "cert_state": "approved",
            "pages_status": None,
        }
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        result = runner.invoke(list_sites, ["--health"])

        assert result.exit_code == 0
        assert "example.com" in result.output
        assert "fixable" in result.output
        mock_host.get_pages_health.assert_called_once_with("testuser/example.com")

    @patch("mimeo.config.Config.load")
    @patch(f"{_LIST}.GitHubHost")
    def test_list_health_json_format(
        self,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """Test list --health adds health fields to JSON output."""
        import json as json_mod

        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.list_mimeo_repositories.return_value = [
            {
                "name": "example.com",
                "url": "https://github.com/testuser/example.com",
                "homepage": "https://example.com",
                "updatedAt": "2026-02-15T12:00:00Z",
            },
        ]
        mock_host.get_pages_health.return_value = {
            "pages_configured": True,
            "https_enforced": True,
            "cert_state": "approved",
            "pages_status": None,
        }
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        result = runner.invoke(list_sites, ["--health", "--format", "json"])

        assert result.exit_code == 0
        data = json_mod.loads(result.output)
        assert len(data) == 1
        assert data[0]["health"] == "healthy"
        assert data[0]["https_enforced"] is True
        assert data[0]["cert_state"] == "approved"

    @patch("mimeo.config.Config.load")
    @patch(f"{_LIST}.GitHubHost")
    def test_list_health_csv_format(
        self,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """Test list --health adds extra columns to CSV output."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.list_mimeo_repositories.return_value = [
            {
                "name": "example.com",
                "url": "https://github.com/testuser/example.com",
                "homepage": "https://example.com",
                "updatedAt": "2026-02-15T12:00:00Z",
            },
        ]
        mock_host.get_pages_health.return_value = {
            "pages_configured": False,
            "https_enforced": False,
            "cert_state": None,
            "pages_status": None,
        }
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        result = runner.invoke(list_sites, ["--health", "--format", "csv"])

        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert lines[0] == "name,repository,site,updated,health,https_enforced,cert_state"
        assert "pages_error" in lines[1]

    def test_list_no_fix_flag(self, runner: CliRunner) -> None:
        """list command no longer has --fix flag."""
        result = runner.invoke(list_sites, ["--help"])
        assert "--fix" not in result.output

    def test_list_no_dns_check_flag(self, runner: CliRunner) -> None:
        """list command no longer has --dns-check flag."""
        result = runner.invoke(list_sites, ["--help"])
        assert "--dns-check" not in result.output


class TestDoctorHelpers:
    """Tests for doctor check helper functions."""

    def test_python_version_passes(self) -> None:
        """Current Python is >= 3.11 (required by pyproject.toml)."""
        ok, detail, fix = _check_python_version()
        assert ok is True
        assert "Python" in detail
        assert fix == ""

    def test_gh_installed_present(self) -> None:
        """gh is available when subprocess returns version output."""
        mock_result = MagicMock()
        mock_result.stdout = "gh version 2.40.0 (2024-01-01)\n"
        with patch(f"{_DOCTOR}.subprocess.run", return_value=mock_result):
            ok, detail, fix = _check_gh_installed()
        assert ok is True
        assert "gh version" in detail
        assert fix == ""

    def test_gh_installed_missing(self) -> None:
        """gh missing when FileNotFoundError is raised."""
        with patch(f"{_DOCTOR}.subprocess.run", side_effect=FileNotFoundError):
            ok, detail, fix = _check_gh_installed()
        assert ok is False
        assert "not found" in detail
        assert "cli.github.com" in fix

    def test_gh_auth_authenticated(self) -> None:
        """gh authenticated when returncode is 0."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch(f"{_DOCTOR}.subprocess.run", return_value=mock_result):
            ok, detail, fix = _check_gh_auth()
        assert ok is True
        assert fix == ""

    def test_gh_auth_not_authenticated(self) -> None:
        """gh not authenticated when returncode is non-zero."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch(f"{_DOCTOR}.subprocess.run", return_value=mock_result):
            ok, detail, fix = _check_gh_auth()
        assert ok is False
        assert "gh auth login" in fix

    def test_gh_auth_gh_missing(self) -> None:
        """Returns failure when gh is not installed."""
        with patch(f"{_DOCTOR}.subprocess.run", side_effect=FileNotFoundError):
            ok, detail, fix = _check_gh_auth()
        assert ok is False

    def test_workflow_scope_present(self) -> None:
        """Workflow scope detected when present in auth status output."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "  - Token scopes: 'repo', 'workflow'\n"
        mock_result.stderr = ""
        with patch(f"{_DOCTOR}.subprocess.run", return_value=mock_result):
            ok, detail, fix = _check_gh_workflow_scope()
        assert ok is True
        assert fix == ""

    def test_workflow_scope_missing(self) -> None:
        """Failure when workflow scope absent from token scopes."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "  - Token scopes: 'repo', 'read:org'\n"
        mock_result.stderr = ""
        with patch(f"{_DOCTOR}.subprocess.run", return_value=mock_result):
            ok, detail, fix = _check_gh_workflow_scope()
        assert ok is False
        assert "workflow" in fix

    def test_workflow_scope_not_authenticated(self) -> None:
        """Failure when gh is not authenticated."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = ""
        with patch(f"{_DOCTOR}.subprocess.run", return_value=mock_result):
            ok, detail, fix = _check_gh_workflow_scope()
        assert ok is False

    def test_workflow_scope_gh_missing(self) -> None:
        """Failure when gh is not installed."""
        with patch(f"{_DOCTOR}.subprocess.run", side_effect=FileNotFoundError):
            ok, detail, fix = _check_gh_workflow_scope()
        assert ok is False

    def test_check_config_valid(self, tmp_path: Path) -> None:
        """Config check passes with a valid config file."""
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(
            '[porkbun]\napi_key = "pk1_test"\nsecret_key = "sk1_test"\n'
            '[github]\ndefault_org = "testuser"\n'
        )
        ok, detail, fix = _check_config(cfg_file)
        assert ok is True
        assert fix == ""

    def test_check_config_missing_file(self, tmp_path: Path) -> None:
        """Config check fails when file does not exist."""
        cfg_file = tmp_path / "missing.toml"
        ok, detail, fix = _check_config(cfg_file)
        assert ok is False
        assert "not found" in detail

    def test_check_config_missing_keys(self, tmp_path: Path) -> None:
        """Config check fails when required keys are absent."""
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("[porkbun]\n")
        ok, detail, fix = _check_config(cfg_file)
        assert ok is False

    @patch("mimeo.providers.registrar.porkbun.lookup_nameservers")
    def test_check_nameservers_ok(self, mock_lookup: Any) -> None:
        """_check_nameservers passes when NS matches Porkbun."""
        from mimeo.providers.registrar.porkbun import PORKBUN_NAMESERVERS

        mock_lookup.return_value = sorted(PORKBUN_NAMESERVERS)
        ok, detail, fix = _check_nameservers("example.com")
        assert ok is True
        assert detail == "porkbun"
        assert fix == ""

    @patch("mimeo.providers.registrar.porkbun.lookup_nameservers")
    def test_check_nameservers_mismatch(self, mock_lookup: Any) -> None:
        """_check_nameservers fails when NS points elsewhere."""
        mock_lookup.return_value = ["ns1.cloudflare.com", "ns2.cloudflare.com"]
        ok, detail, fix = _check_nameservers("example.com")
        assert ok is False
        assert "cloudflare" in detail
        assert "Porkbun" in fix

    @patch("mimeo.providers.registrar.porkbun.lookup_nameservers")
    def test_check_nameservers_empty(self, mock_lookup: Any) -> None:
        """_check_nameservers fails when no NS records are found."""
        mock_lookup.return_value = []
        ok, detail, fix = _check_nameservers("example.com")
        assert ok is False
        assert "no NS records" in detail


class TestDoctorCommand:
    """Tests for the doctor CLI command."""

    def test_doctor_help(self, runner: CliRunner) -> None:
        """Doctor command shows help."""
        result = runner.invoke(doctor, ["--help"])
        assert result.exit_code == 0
        assert "prerequisites" in result.output.lower() or "check" in result.output.lower()

    def test_doctor_all_pass(self, runner: CliRunner, tmp_path: Path) -> None:
        """Doctor exits 0 when all checks pass."""
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(
            '[porkbun]\napi_key = "pk1_test"\nsecret_key = "sk1_test"\n'
            '[github]\ndefault_org = "testuser"\n'
        )

        def fake_run(cmd: list, **kwargs: Any) -> MagicMock:
            mock_result = MagicMock()
            mock_result.returncode = 0
            if "--version" in cmd:
                mock_result.stdout = "gh version 2.40.0\n"
                mock_result.stderr = ""
            else:
                mock_result.stdout = "  - Token scopes: 'repo', 'workflow'\n"
                mock_result.stderr = ""
            return mock_result

        with patch(f"{_DOCTOR}.subprocess.run", side_effect=fake_run):
            result = runner.invoke(doctor, ["--config", str(cfg_file)])

        assert result.exit_code == 0
        assert "All checks passed" in result.output

    def test_doctor_fails_on_missing_gh(self, runner: CliRunner, tmp_path: Path) -> None:
        """Doctor exits non-zero and prints remediation when gh is missing."""
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(
            '[porkbun]\napi_key = "pk1_test"\nsecret_key = "sk1_test"\n'
            '[github]\ndefault_org = "testuser"\n'
        )

        with patch(f"{_DOCTOR}.subprocess.run", side_effect=FileNotFoundError):
            result = runner.invoke(doctor, ["--config", str(cfg_file)])

        assert result.exit_code != 0
        assert "cli.github.com" in result.output

    def test_doctor_fails_on_bad_config(self, runner: CliRunner, tmp_path: Path) -> None:
        """Doctor exits non-zero when config file is missing."""

        def fake_run(cmd: list, **kwargs: Any) -> MagicMock:
            mock_result = MagicMock()
            mock_result.returncode = 0
            if "--version" in cmd:
                mock_result.stdout = "gh version 2.40.0\n"
                mock_result.stderr = ""
            else:
                mock_result.stdout = "  - Token scopes: 'repo', 'workflow'\n"
                mock_result.stderr = ""
            return mock_result

        missing = tmp_path / "no-such.toml"
        with patch(f"{_DOCTOR}.subprocess.run", side_effect=fake_run):
            result = runner.invoke(doctor, ["--config", str(missing)])

        assert result.exit_code != 0
        assert "not found" in result.output

    @patch(f"{_DOCTOR}._check_nameservers")
    def test_doctor_ns_check_ok(self, mock_ns: Any, runner: CliRunner, tmp_path: Path) -> None:
        """Doctor with domain args runs NS check and passes when NS is Porkbun."""
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(
            '[porkbun]\napi_key = "pk1_test"\nsecret_key = "sk1_test"\n'
            '[github]\ndefault_org = "testuser"\n'
        )
        mock_ns.return_value = (True, "porkbun", "")

        def fake_run(cmd: list, **kwargs: Any) -> MagicMock:
            m = MagicMock()
            m.returncode = 0
            m.stdout = (
                "gh version 2.40.0\n"
                if "--version" in cmd
                else "  - Token scopes: 'repo', 'workflow'\n"
            )
            m.stderr = ""
            return m

        with patch(f"{_DOCTOR}.subprocess.run", side_effect=fake_run):
            result = runner.invoke(doctor, ["--config", str(cfg_file), "example.com"])

        assert result.exit_code == 0
        assert "NS: example.com" in result.output
        assert "porkbun" in result.output
        assert "All checks passed" in result.output
        mock_ns.assert_called_once_with("example.com")

    @patch(f"{_DOCTOR}._check_nameservers")
    def test_doctor_ns_check_mismatch(
        self, mock_ns: Any, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Doctor exits non-zero and shows remediation when NS doesn't point to Porkbun."""
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(
            '[porkbun]\napi_key = "pk1_test"\nsecret_key = "sk1_test"\n'
            '[github]\ndefault_org = "testuser"\n'
        )
        mock_ns.return_value = (
            False,
            "ns1.cloudflare.com, ns2.cloudflare.com",
            "Nameservers don't point to Porkbun -- DNS config will be skipped on create.",
        )

        def fake_run(cmd: list, **kwargs: Any) -> MagicMock:
            m = MagicMock()
            m.returncode = 0
            m.stdout = (
                "gh version 2.40.0\n"
                if "--version" in cmd
                else "  - Token scopes: 'repo', 'workflow'\n"
            )
            m.stderr = ""
            return m

        with patch(f"{_DOCTOR}.subprocess.run", side_effect=fake_run):
            result = runner.invoke(doctor, ["--config", str(cfg_file), "example.com"])

        assert result.exit_code != 0
        assert "NS: example.com" in result.output
        assert "cloudflare" in result.output
        assert "Porkbun" in result.output

    @patch(f"{_DOCTOR}._check_nameservers")
    def test_doctor_ns_check_multiple_domains(
        self, mock_ns: Any, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Doctor checks NS for each domain provided."""
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(
            '[porkbun]\napi_key = "pk1_test"\nsecret_key = "sk1_test"\n'
            '[github]\ndefault_org = "testuser"\n'
        )
        mock_ns.return_value = (True, "porkbun", "")

        def fake_run(cmd: list, **kwargs: Any) -> MagicMock:
            m = MagicMock()
            m.returncode = 0
            m.stdout = (
                "gh version 2.40.0\n"
                if "--version" in cmd
                else "  - Token scopes: 'repo', 'workflow'\n"
            )
            m.stderr = ""
            return m

        with patch(f"{_DOCTOR}.subprocess.run", side_effect=fake_run):
            result = runner.invoke(doctor, ["--config", str(cfg_file), "site1.com", "site2.com"])

        assert result.exit_code == 0
        assert "NS: site1.com" in result.output
        assert "NS: site2.com" in result.output
        assert mock_ns.call_count == 2


class TestWorkersOption:
    """Tests for --workers option on create command."""

    def test_workers_help(self, runner: CliRunner) -> None:
        """--workers appears in create help."""
        result = runner.invoke(create, ["--help"])
        assert result.exit_code == 0
        assert "--workers" in result.output

    def test_workers_invalid_zero(self, runner: CliRunner) -> None:
        """--workers 0 is rejected."""
        result = runner.invoke(create, ["example.com", "--workers", "0"])
        assert result.exit_code != 0

    def test_workers_invalid_negative(self, runner: CliRunner) -> None:
        """Negative --workers is rejected."""
        result = runner.invoke(create, ["example.com", "--workers", "-1"])
        assert result.exit_code != 0

    @patch("mimeo.config.Config.load")
    @patch(f"{_CREATE}.GitHubHost")
    @patch(f"{_CREATE}.PorkbunRegistrar")
    @patch(f"{_PROCESSING}.ThreadPoolExecutor")
    def test_workers_passed_to_executor(
        self,
        mock_executor_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
        mock_dns_records: List[DNSRecord],
    ) -> None:
        """--workers value is forwarded to ThreadPoolExecutor."""
        mock_config_load.return_value = mock_config

        mock_executor = MagicMock()
        mock_future = MagicMock()
        mock_future.result.return_value = {
            "domain": "a.com",
            "success": True,
            "error": None,
            "error_category": None,
            "url": "https://a.com",
            "repo_url": "https://github.com/testuser/a.com",
            "https_pending": False,
            "dns_pending": False,
            "log": [],
        }
        mock_executor.submit.return_value = mock_future
        mock_executor.__enter__ = MagicMock(return_value=mock_executor)
        mock_executor.__exit__ = MagicMock(return_value=False)
        mock_executor_class.return_value = mock_executor

        with patch(f"{_PROCESSING}.as_completed", return_value=[mock_future]):
            runner.invoke(create, ["a.com", "b.com", "--workers", "3"])

        mock_executor_class.assert_called_once_with(max_workers=2)


class TestLogFormatOption:
    """Tests for --log-format json option."""

    def test_log_format_in_main_help(self, runner: CliRunner) -> None:
        """--log-format appears in main help."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "--log-format" in result.output

    @patch("mimeo.config.Config.load")
    @patch(f"{_CREATE}.GitHubHost")
    @patch(f"{_CREATE}.PorkbunRegistrar")
    @patch(f"{_CREATE}.PorkbunDNSProvider")
    def test_json_log_format_no_text_summary(
        self,
        mock_dns_provider_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
        mock_dns_records: List[DNSRecord],
    ) -> None:
        """--log-format json suppresses text SUMMARY banner."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.return_value = DeployResult(
            url="https://example.com", repo_created=True, https_enabled=True
        )
        mock_host.required_dns_records.return_value = mock_dns_records
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(
            ok=True, actual=[], expected=[]
        )
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        mock_dns_provider = MagicMock()
        mock_dns_provider.verify_dns.return_value = True
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(main, ["--log-format", "json", "create", "example.com"])

        assert result.exit_code == 0
        assert "SUMMARY" not in result.output
        import json as json_mod

        json_lines = [l for l in result.output.splitlines() if l.strip().startswith("{")]
        assert len(json_lines) > 0
        for line in json_lines:
            record = json_mod.loads(line)
            assert "ts" in record
            assert "level" in record
            assert "message" in record

    def test_doctor_json_log_format(self, runner: CliRunner, tmp_path: Path) -> None:
        """--log-format json doctor emits JSON records, no text table."""
        import json as json_mod

        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(
            '[porkbun]\napi_key = "pk1_test"\nsecret_key = "sk1_test"\n'
            '[github]\ndefault_org = "testuser"\n'
        )

        def fake_run(cmd: list, **kwargs: Any) -> MagicMock:
            m = MagicMock()
            m.returncode = 0
            if "--version" in cmd:
                m.stdout = "gh version 2.40.0\n"
                m.stderr = ""
            else:
                m.stdout = "  - Token scopes: 'repo', 'workflow'\n"
                m.stderr = ""
            return m

        with patch(f"{_DOCTOR}.subprocess.run", side_effect=fake_run):
            result = runner.invoke(
                main,
                ["--log-format", "json", "doctor", "--config", str(cfg_file)],
            )

        assert result.exit_code == 0
        assert "ok  " not in result.output
        json_lines = [l for l in result.output.splitlines() if l.strip().startswith("{")]
        assert len(json_lines) > 0
        for line in json_lines:
            record = json_mod.loads(line)
            assert "level" in record
            assert "message" in record


class TestFixHttpsCommand:
    """Tests for fix https command."""

    @patch("mimeo.config.Config.load")
    @patch(f"mimeo.cli.fix.GitHubHost")
    def test_fix_https_discovers_fixable(
        self,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """fix https discovers and fixes fixable repos."""
        from mimeo.cli.fix import https

        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.list_mimeo_repositories.return_value = [
            {
                "name": "fixable.com",
                "url": "https://github.com/testuser/fixable.com",
                "homepage": "https://fixable.com",
                "updatedAt": "2026-02-15T12:00:00Z",
            },
        ]
        mock_host.get_pages_health.return_value = {
            "pages_configured": True,
            "https_enforced": False,
            "cert_state": "approved",
            "pages_status": None,
        }
        mock_host.enable_https_enforcement.return_value = True
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        result = runner.invoke(https, [])

        assert result.exit_code == 0
        mock_host.enable_https_enforcement.assert_called_once_with("testuser/fixable.com")
        assert "fixable.com" in result.output

    @patch("mimeo.config.Config.load")
    @patch(f"mimeo.cli.fix.GitHubHost")
    def test_fix_https_specific_domains(
        self,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """fix https with specific domains fixes those repos."""
        from mimeo.cli.fix import https

        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.enable_https_enforcement.return_value = True
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        result = runner.invoke(https, ["example.com"])

        assert result.exit_code == 0
        mock_host.enable_https_enforcement.assert_called_once_with("testuser/example.com")


class TestDnsCommands:
    """Tests for dns check and dns repair commands."""

    @patch("mimeo.config.Config.load")
    @patch(f"mimeo.cli.dns.GitHubHost")
    @patch(f"mimeo.cli.dns.PorkbunRegistrar")
    @patch(f"mimeo.cli.dns.PorkbunDNSProvider")
    def test_dns_check(
        self,
        mock_dns_provider_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """dns check shows DNS status."""
        from mimeo.cli.dns import check

        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.required_dns_records.return_value = []
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(
            ok=True, actual=["curitiba.ns.porkbun.com"], expected=[]
        )
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        mock_dns_provider = MagicMock()
        mock_dns_provider.check_dns_drift.return_value = {
            "status": "ok",
            "missing": [],
            "extra": [],
        }
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(check, ["example.com"])

        assert result.exit_code == 0
        assert "example.com" in result.output
        assert "ok" in result.output

    @patch("mimeo.config.Config.load")
    @patch(f"mimeo.cli.dns.GitHubHost")
    @patch(f"mimeo.cli.dns.PorkbunRegistrar")
    @patch(f"mimeo.cli.dns.PorkbunDNSProvider")
    def test_dns_repair(
        self,
        mock_dns_provider_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
        mock_dns_records: List[DNSRecord],
    ) -> None:
        """dns repair configures DNS records."""
        from mimeo.cli.dns import repair

        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.required_dns_records.return_value = mock_dns_records
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(
            ok=True, actual=[], expected=[]
        )
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        mock_dns_provider = MagicMock()
        mock_dns_provider.verify_dns.return_value = True
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(repair, ["example.com"])

        assert result.exit_code == 0
        mock_dns_provider.configure_dns.assert_called_once()

    @patch("mimeo.config.Config.load")
    @patch(f"mimeo.cli.dns.GitHubHost")
    @patch(f"mimeo.cli.dns.PorkbunRegistrar")
    @patch(f"mimeo.cli.dns.PorkbunDNSProvider")
    def test_dns_repair_reset_nameservers(
        self,
        mock_dns_provider_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
        mock_dns_records: List[DNSRecord],
    ) -> None:
        """dns repair --reset-nameservers resets NS then configures DNS."""
        from mimeo.cli.dns import repair

        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.required_dns_records.return_value = mock_dns_records
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(
            ok=False,
            actual=["ns1.cloudflare.com"],
            expected=["curitiba.ns.porkbun.com"],
        )
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        mock_dns_provider = MagicMock()
        mock_dns_provider.verify_dns.return_value = True
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(repair, ["example.com", "--reset-nameservers"])

        assert result.exit_code == 0
        mock_registrar.update_nameservers.assert_called_once_with("example.com")
        mock_dns_provider.configure_dns.assert_called_once()

    SAMPLE_RECORDS = [
        {
            "id": "1",
            "type": "A",
            "name": "example.com",
            "content": "185.199.108.153",
            "ttl": "600",
            "prio": "0",
        },
        {
            "id": "2",
            "type": "CNAME",
            "name": "www.example.com",
            "content": "user.github.io",
            "ttl": "600",
            "prio": "0",
        },
    ]

    def _mock_dns_provider(self, mock_dns_provider_class: Any) -> MagicMock:
        mock_dns_provider = MagicMock()
        mock_dns_provider.get_domain_records.return_value = self.SAMPLE_RECORDS
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider
        return mock_dns_provider

    @patch("mimeo.config.Config.load")
    @patch("mimeo.cli.dns.PorkbunDNSProvider")
    def test_dns_show_text(
        self,
        mock_dns_provider_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """dns show prints a record table for the domain."""
        from mimeo.cli.dns import show

        mock_config_load.return_value = mock_config
        mock_dns_provider = self._mock_dns_provider(mock_dns_provider_class)

        result = runner.invoke(show, ["example.com"])

        assert result.exit_code == 0
        mock_dns_provider.get_domain_records.assert_called_once_with("example.com")
        assert "example.com" in result.output
        assert "185.199.108.153" in result.output
        assert "CNAME" in result.output

    @patch("mimeo.config.Config.load")
    @patch("mimeo.cli.dns.PorkbunDNSProvider")
    def test_dns_show_json(
        self,
        mock_dns_provider_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """dns show --format json emits a list of per-domain objects."""
        from mimeo.cli.dns import show

        mock_config_load.return_value = mock_config
        self._mock_dns_provider(mock_dns_provider_class)

        result = runner.invoke(show, ["example.com", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["domain"] == "example.com"
        assert data[0]["error"] is None
        assert len(data[0]["records"]) == 2
        assert data[0]["records"][0]["content"] == "185.199.108.153"

    @patch("mimeo.config.Config.load")
    @patch("mimeo.cli.dns.PorkbunDNSProvider")
    def test_dns_show_csv(
        self,
        mock_dns_provider_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """dns show --format csv emits one row per record."""
        from mimeo.cli.dns import show

        mock_config_load.return_value = mock_config
        self._mock_dns_provider(mock_dns_provider_class)

        result = runner.invoke(show, ["example.com", "--format", "csv"])

        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert lines[0] == "domain,type,name,ttl,prio,content"
        assert len(lines) == 3
        assert lines[1].startswith("example.com,A,")

    @patch("mimeo.cli.dns.lookup_nameservers")
    @patch("mimeo.config.Config.load")
    @patch("mimeo.cli.dns.PorkbunDNSProvider")
    def test_dns_show_no_records(
        self,
        mock_dns_provider_class: Any,
        mock_config_load: Any,
        mock_lookup: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """dns show handles a domain with no records."""
        from mimeo.cli.dns import show

        mock_config_load.return_value = mock_config
        mock_dns_provider = self._mock_dns_provider(mock_dns_provider_class)
        mock_dns_provider.get_domain_records.return_value = []
        mock_lookup.return_value = []

        result = runner.invoke(show, ["example.com"])

        assert result.exit_code == 0
        assert "no records" in result.output

    @patch("mimeo.cli.dns.lookup_nameservers")
    @patch("mimeo.config.Config.load")
    @patch("mimeo.cli.dns.PorkbunDNSProvider")
    def test_dns_show_empty_zone_external_ns_hint(
        self,
        mock_dns_provider_class: Any,
        mock_config_load: Any,
        mock_lookup: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """Empty Porkbun zone with external nameservers explains itself."""
        from mimeo.cli.dns import show

        mock_config_load.return_value = mock_config
        mock_dns_provider = self._mock_dns_provider(mock_dns_provider_class)
        mock_dns_provider.get_domain_records.return_value = []
        mock_lookup.return_value = ["dns1.p02.nsone.net", "dns2.p02.nsone.net"]

        result = runner.invoke(show, ["example.dev"])

        assert result.exit_code == 0
        assert "nsone.net" in result.output
        assert "managed there" in result.output

    @patch("mimeo.cli.dns.lookup_nameservers")
    @patch("mimeo.config.Config.load")
    @patch("mimeo.cli.dns.PorkbunDNSProvider")
    def test_dns_show_with_records_skips_ns_lookup(
        self,
        mock_dns_provider_class: Any,
        mock_config_load: Any,
        mock_lookup: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """The NS lookup only happens when the zone is empty."""
        from mimeo.cli.dns import show

        mock_config_load.return_value = mock_config
        self._mock_dns_provider(mock_dns_provider_class)

        result = runner.invoke(show, ["example.com"])

        assert result.exit_code == 0
        mock_lookup.assert_not_called()

    @patch("mimeo.config.Config.load")
    @patch("mimeo.cli.dns.PorkbunDNSProvider")
    def test_dns_show_partial_failure(
        self,
        mock_dns_provider_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """dns show keeps results for good domains when one fails."""
        from mimeo.cli.dns import show
        from mimeo.exceptions import EXIT_PARTIAL, RegistrarError

        mock_config_load.return_value = mock_config
        mock_dns_provider = self._mock_dns_provider(mock_dns_provider_class)
        mock_dns_provider.get_domain_records.side_effect = [
            self.SAMPLE_RECORDS,
            RegistrarError("Failed to communicate with Porkbun API: HTTP 503"),
        ]

        result = runner.invoke(show, ["good.com", "bad.com", "--format", "json"])

        assert result.exit_code == EXIT_PARTIAL
        data = json.loads(result.stdout)
        assert len(data) == 2
        assert data[0]["domain"] == "good.com"
        assert len(data[0]["records"]) == 2
        assert data[1]["domain"] == "bad.com"
        assert "503" in data[1]["error"]

    def test_dns_show_invalid_domain(self, runner: CliRunner) -> None:
        """dns show rejects invalid domain names."""
        from mimeo.cli.dns import show

        result = runner.invoke(show, ["not_a_domain"])

        assert result.exit_code != 0
        assert "Invalid domain name" in result.output


class TestTemplateApplyCommand:
    """Tests for template apply command."""

    @patch("mimeo.config.Config.load")
    @patch(f"mimeo.cli.template.GitHubHost")
    def test_template_apply_dry_run(
        self,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """template apply --dry-run shows what would happen."""
        from mimeo.cli.template import apply

        mock_config_load.return_value = mock_config

        result = runner.invoke(apply, ["example.com", "--template", "mimeo.lol", "--dry-run"])

        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        assert "Would delete and recreate" in result.output

    @patch("mimeo.config.Config.load")
    @patch(f"mimeo.cli.template.GitHubHost")
    def test_template_apply_with_yes(
        self,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """template apply --yes skips confirmation."""
        from mimeo.cli.template import apply

        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.return_value = DeployResult(
            url="https://example.com", repo_created=True, https_enabled=True, repo_existed=True
        )
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        result = runner.invoke(apply, ["example.com", "--template", "mimeo.lol", "--yes"])

        assert result.exit_code == 0
        mock_host.deploy_site.assert_called_once_with(
            "example.com", template="mimeo.lol", force=True
        )


class TestRegistrarListCommand:
    """Tests for the registrar list subcommand."""

    SAMPLE_DOMAINS = [
        {
            "domain": "example.com",
            "tld": "com",
            "expireDate": "2027-01-15",
            "autoRenew": "1",
        },
        {
            "domain": "example.net",
            "tld": "net",
            "expireDate": "2027-06-30",
            "autoRenew": "0",
        },
    ]

    def test_registrar_list_help(self, runner: CliRunner) -> None:
        """registrar list shows help."""
        result = runner.invoke(registrar_list, ["--help"])
        assert result.exit_code == 0
        assert "--format" in result.output
        assert "--with-dns" in result.output
        assert "--workers" in result.output

    def test_registrar_group_help(self, runner: CliRunner) -> None:
        """registrar group shows help with list subcommand."""
        result = runner.invoke(main, ["registrar", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output

    @patch("mimeo.config.Config.load")
    @patch(f"{_REGISTRAR}.PorkbunRegistrar")
    def test_registrar_list_text_format(
        self,
        mock_registrar_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """registrar list outputs a text table by default."""
        mock_config_load.return_value = mock_config

        mock_registrar = MagicMock()
        mock_registrar.list_domains.return_value = self.SAMPLE_DOMAINS
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(
            ok=True,
            actual=["curitiba.ns.porkbun.com"],
            expected=["curitiba.ns.porkbun.com"],
        )
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar.__exit__ = MagicMock(return_value=False)
        mock_registrar_class.return_value = mock_registrar

        result = runner.invoke(registrar_list, [])

        assert result.exit_code == 0
        assert "DOMAIN" in result.output
        assert "example.com" in result.output
        assert "example.net" in result.output

    @patch("mimeo.config.Config.load")
    @patch(f"{_REGISTRAR}.PorkbunRegistrar")
    def test_registrar_list_json_format(
        self,
        mock_registrar_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """registrar list --format json emits valid JSON."""
        import json as json_mod

        mock_config_load.return_value = mock_config

        mock_registrar = MagicMock()
        mock_registrar.list_domains.return_value = self.SAMPLE_DOMAINS
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(
            ok=True, actual=[], expected=[]
        )
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar.__exit__ = MagicMock(return_value=False)
        mock_registrar_class.return_value = mock_registrar

        result = runner.invoke(registrar_list, ["--format", "json"])

        assert result.exit_code == 0
        data = json_mod.loads(result.output)
        assert len(data) == 2
        assert data[0]["domain"] == "example.com"
        assert data[0]["tld"] == "com"
        assert data[0]["expires"] == "2027-01-15"
        assert data[0]["auto_renew"] is True
        assert data[1]["auto_renew"] is False

    @patch("mimeo.config.Config.load")
    @patch(f"{_REGISTRAR}.PorkbunRegistrar")
    def test_registrar_list_csv_format(
        self,
        mock_registrar_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """registrar list --format csv emits CSV with correct header."""
        mock_config_load.return_value = mock_config

        mock_registrar = MagicMock()
        mock_registrar.list_domains.return_value = self.SAMPLE_DOMAINS
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(
            ok=False, actual=["ns1.other.com"], expected=[]
        )
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar.__exit__ = MagicMock(return_value=False)
        mock_registrar_class.return_value = mock_registrar

        result = runner.invoke(registrar_list, ["--format", "csv"])

        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert lines[0] == "domain,tld,expires,auto_renew,ns_ok,nameservers,error"
        assert len(lines) == 3

    @patch("mimeo.config.Config.load")
    @patch(f"{_REGISTRAR}.PorkbunRegistrar")
    def test_registrar_list_csv_with_dns_header(
        self,
        mock_registrar_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """registrar list --format csv --with-dns includes dns_records column."""
        mock_config_load.return_value = mock_config

        mock_registrar = MagicMock()
        mock_registrar.list_domains.return_value = [self.SAMPLE_DOMAINS[0]]
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(
            ok=True, actual=[], expected=[]
        )
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar.__exit__ = MagicMock(return_value=False)
        mock_registrar_class.return_value = mock_registrar

        with patch(f"{_REGISTRAR}.PorkbunDNSProvider") as mock_dns_class:
            mock_dns = MagicMock()
            mock_dns.get_domain_records.return_value = []
            mock_dns.__enter__.return_value = mock_dns
            mock_dns.__exit__ = MagicMock(return_value=False)
            mock_dns_class.return_value = mock_dns

            result = runner.invoke(registrar_list, ["--format", "csv", "--with-dns"])

        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert "dns_records" in lines[0]

    @patch("mimeo.config.Config.load")
    @patch(f"{_REGISTRAR}.PorkbunRegistrar")
    def test_registrar_list_empty(
        self,
        mock_registrar_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """registrar list shows message when account has no domains."""
        mock_config_load.return_value = mock_config

        mock_registrar = MagicMock()
        mock_registrar.list_domains.return_value = []
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar.__exit__ = MagicMock(return_value=False)
        mock_registrar_class.return_value = mock_registrar

        result = runner.invoke(registrar_list, [])

        assert result.exit_code == 0
        assert "No domains found" in result.output

    @patch("mimeo.config.Config.load")
    @patch(f"{_REGISTRAR}.PorkbunRegistrar")
    def test_registrar_list_empty_json(
        self,
        mock_registrar_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """registrar list --format json with empty account outputs []."""
        mock_config_load.return_value = mock_config

        mock_registrar = MagicMock()
        mock_registrar.list_domains.return_value = []
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar.__exit__ = MagicMock(return_value=False)
        mock_registrar_class.return_value = mock_registrar

        result = runner.invoke(registrar_list, ["--format", "json"])

        assert result.exit_code == 0
        assert result.output.strip() == "[]"

    @patch("mimeo.config.Config.load")
    def test_registrar_list_config_error(
        self,
        mock_config_load: Any,
        runner: CliRunner,
    ) -> None:
        """registrar list exits with config error when config fails to load."""
        mock_config_load.side_effect = ConfigurationError("Config not found")

        result = runner.invoke(registrar_list, [])

        assert result.exit_code == 2
        assert "Config not found" in result.output

    @patch("mimeo.config.Config.load")
    @patch(f"{_REGISTRAR}.PorkbunRegistrar")
    def test_registrar_list_ns_ok_flag(
        self,
        mock_registrar_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """registrar list --format json includes ns_ok field."""
        import json as json_mod

        mock_config_load.return_value = mock_config

        mock_registrar = MagicMock()
        mock_registrar.list_domains.return_value = [self.SAMPLE_DOMAINS[0]]
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(
            ok=False, actual=["ns1.cloudflare.com"], expected=["curitiba.ns.porkbun.com"]
        )
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar.__exit__ = MagicMock(return_value=False)
        mock_registrar_class.return_value = mock_registrar

        result = runner.invoke(registrar_list, ["--format", "json"])

        assert result.exit_code == 0
        data = json_mod.loads(result.output)
        assert data[0]["ns_ok"] is False
        assert "ns1.cloudflare.com" in data[0]["nameservers"]

    @patch("mimeo.config.Config.load")
    @patch(f"{_REGISTRAR}.PorkbunRegistrar")
    def test_registrar_list_partial_failure(
        self,
        mock_registrar_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """registrar list keeps good domains when enrichment fails for one."""
        from mimeo.exceptions import EXIT_PARTIAL

        mock_config_load.return_value = mock_config

        mock_registrar = MagicMock()
        mock_registrar.list_domains.return_value = self.SAMPLE_DOMAINS
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar.__exit__ = MagicMock(return_value=False)
        mock_registrar_class.return_value = mock_registrar

        ok_result = NameserverCheckResult(
            ok=True,
            actual=["curitiba.ns.porkbun.com"],
            expected=["curitiba.ns.porkbun.com"],
        )

        def check_ns(domain: str) -> NameserverCheckResult:
            if domain == "example.net":
                raise RegistrarError("Failed to communicate with Porkbun API: HTTP 503")
            return ok_result

        mock_registrar.check_nameservers.side_effect = check_ns

        result = runner.invoke(registrar_list, ["--format", "json", "--workers", "1"])

        assert result.exit_code == EXIT_PARTIAL
        data = json.loads(result.stdout)
        assert len(data) == len(self.SAMPLE_DOMAINS)
        by_domain = {d["domain"]: d for d in data}
        assert by_domain["example.com"]["error"] is None
        assert by_domain["example.com"]["ns_ok"] is True
        assert "503" in by_domain["example.net"]["error"]
        assert "partial" in result.output

    @patch("mimeo.config.Config.load")
    @patch(f"{_REGISTRAR}.PorkbunRegistrar")
    def test_registrar_list_partial_failure_dns(
        self,
        mock_registrar_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """registrar list --with-dns keeps good domains when a DNS fetch fails."""
        from mimeo.exceptions import EXIT_PARTIAL

        mock_config_load.return_value = mock_config

        mock_registrar = MagicMock()
        mock_registrar.list_domains.return_value = self.SAMPLE_DOMAINS
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(
            ok=True,
            actual=["curitiba.ns.porkbun.com"],
            expected=["curitiba.ns.porkbun.com"],
        )
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar.__exit__ = MagicMock(return_value=False)
        mock_registrar_class.return_value = mock_registrar

        def get_records(domain: str) -> List[dict]:
            if domain == "example.net":
                raise RegistrarError("Failed to communicate with Porkbun API: HTTP 503")
            return [{"type": "A", "name": domain, "content": "1.2.3.4", "ttl": "600"}]

        with patch(f"{_REGISTRAR}.PorkbunDNSProvider") as mock_dns_class:
            mock_dns = MagicMock()
            mock_dns.get_domain_records.side_effect = get_records
            mock_dns.__enter__.return_value = mock_dns
            mock_dns.__exit__ = MagicMock(return_value=False)
            mock_dns_class.return_value = mock_dns

            result = runner.invoke(
                registrar_list, ["--format", "json", "--with-dns", "--workers", "1"]
            )

        assert result.exit_code == EXIT_PARTIAL
        data = json.loads(result.stdout)
        by_domain = {d["domain"]: d for d in data}
        assert len(by_domain["example.com"]["dns_records"]) == 1
        assert by_domain["example.net"]["dns_records"] == []
        assert "503" in by_domain["example.net"]["error"]
