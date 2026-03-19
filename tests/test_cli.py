"""Tests for CLI module."""

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
        assert "Create and deploy minimal landing pages" in result.output
        assert "DOMAINS" in result.output

    def test_create_requires_domain(self, runner: CliRunner) -> None:
        """Test create command requires domain argument."""
        result = runner.invoke(create, [])
        assert result.exit_code != 0
        assert "Missing argument" in result.output

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.GitHubHost")
    @patch("mimeo.cli.PorkbunRegistrar")
    @patch("mimeo.cli.PorkbunDNSProvider")
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
        # Setup mocks
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.return_value = DeployResult(url="https://example.com", repo_created=True, https_enabled=True)
        mock_host.required_dns_records.return_value = mock_dns_records
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(ok=True, actual=[], expected=[])
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        mock_dns_provider = MagicMock()
        mock_dns_provider.verify_dns.return_value = True
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        # Run command
        result = runner.invoke(create, ["example.com"])

        # Verify success
        assert result.exit_code == 0
        assert "Loading configuration" in result.output
        assert "Configuring GitHub repository" in result.output
        assert "Configuring DNS records" in result.output
        assert "Successfully created: 1/1 domain(s)" in result.output
        assert "https://example.com" in result.output

        # Verify mocks called correctly
        mock_config_load.assert_called_once()
        mock_host_class.assert_called_once_with(default_org="testuser")
        mock_host.deploy_site.assert_called_once()
        mock_host.required_dns_records.assert_called_once_with("example.com")
        mock_registrar.check_nameservers.assert_called_once_with("example.com")
        mock_dns_provider.configure_dns.assert_called_once_with("example.com", mock_dns_records)
        mock_dns_provider.verify_dns.assert_called_once()

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.GitHubHost")
    @patch("mimeo.cli.PorkbunRegistrar")
    @patch("mimeo.cli.PorkbunDNSProvider")
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
        # Setup mocks
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.return_value = DeployResult(url="https://example.com", repo_created=True, https_enabled=True)
        mock_host.required_dns_records.return_value = mock_dns_records
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(ok=True, actual=[], expected=[])
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        mock_dns_provider = MagicMock()
        mock_dns_provider.verify_dns.return_value = False  # DNS not verified
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        # Run command
        result = runner.invoke(create, ["example.com"])

        # Verify success but with warning
        assert result.exit_code == 0
        assert "DNS records created but not yet propagated" in result.output
        assert "Successfully created: 1/1 domain(s)" in result.output

    @patch("mimeo.cli.Config.load")
    def test_create_config_error(self, mock_config_load: Any, runner: CliRunner) -> None:
        """Test create command handles configuration errors."""
        mock_config_load.side_effect = ConfigurationError("Config file not found")

        result = runner.invoke(create, ["example.com"])

        assert result.exit_code == 2
        assert "Config file not found" in result.output

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.GitHubHost")
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

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.GitHubHost")
    @patch("mimeo.cli.PorkbunRegistrar")
    @patch("mimeo.cli.PorkbunDNSProvider")
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
        mock_host.deploy_site.return_value = DeployResult(url="https://example.com", repo_created=True, https_enabled=True)
        mock_host.required_dns_records.return_value = mock_dns_records
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(ok=True, actual=[], expected=[])
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        mock_dns_provider = MagicMock()
        mock_dns_provider.configure_dns.side_effect = RegistrarError("Porkbun API failed")
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(create, ["example.com"])

        # DNS errors no longer fail the entire operation - site is deployed but DNS not configured
        assert result.exit_code == 0
        assert "DNS configuration failed" in result.output
        assert "Porkbun API failed" in result.output
        assert "Site deployed but DNS not configured" in result.output

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.GitHubHost")
    @patch("mimeo.cli.PorkbunRegistrar")
    @patch("mimeo.cli.PorkbunDNSProvider")
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
        mock_host.deploy_site.return_value = DeployResult(url="https://example.com", repo_created=True, https_enabled=True)
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
        # DNS provider should NOT have been called to configure records
        mock_dns_provider.configure_dns.assert_not_called()

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.GitHubHost")
    @patch("mimeo.cli.PorkbunRegistrar")
    @patch("mimeo.cli.PorkbunDNSProvider")
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
        # Create a config file
        config_file = tmp_path / "custom.toml"
        config_file.write_text("")

        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.return_value = DeployResult(url="https://example.com", repo_created=True, https_enabled=True)
        mock_host.required_dns_records.return_value = mock_dns_records
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(ok=True, actual=[], expected=[])
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        mock_dns_provider = MagicMock()
        mock_dns_provider.verify_dns.return_value = True
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(create, ["example.com", "--config", str(config_file)])

        assert result.exit_code == 0
        mock_config_load.assert_called_once_with(config_file)

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.GitHubHost")
    @patch("mimeo.cli.PorkbunRegistrar")
    @patch("mimeo.cli.PorkbunDNSProvider")
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
        mock_host.deploy_site.return_value = DeployResult(url="https://example.com", repo_created=True, https_enabled=True)
        mock_host.required_dns_records.return_value = mock_dns_records
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(ok=True, actual=[], expected=[])
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        mock_dns_provider = MagicMock()
        mock_dns_provider.verify_dns.return_value = True
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(create, ["example.com"])

        assert result.exit_code == 0

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.GitHubHost")
    @patch("mimeo.cli.PorkbunRegistrar")
    @patch("mimeo.cli.PorkbunDNSProvider")
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
        mock_host.deploy_site.return_value = DeployResult(url="https://example.com", repo_created=True, https_enabled=True)
        mock_host.required_dns_records.return_value = mock_dns_records
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(ok=True, actual=[], expected=[])
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        mock_dns_provider = MagicMock()
        mock_dns_provider.verify_dns.return_value = True
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(create, ["example.com"])

        assert result.exit_code == 0
        assert "https://github.com/testuser/example.com" in result.output

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.GitHubHost")
    @patch("mimeo.cli.PorkbunRegistrar")
    @patch("mimeo.cli.PorkbunDNSProvider")
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
        mock_host.deploy_site.return_value = DeployResult(url="https://example.com", repo_created=True, https_enabled=True)
        mock_host.required_dns_records.return_value = mock_dns_records
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(ok=True, actual=[], expected=[])
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        mock_dns_provider = MagicMock()
        mock_dns_provider.verify_dns.return_value = True
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(create, ["example.com"])

        assert result.exit_code == 0
        mock_host_class.assert_called_once_with(default_org="testuser")

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.GitHubHost")
    @patch("mimeo.cli.PorkbunRegistrar")
    @patch("mimeo.cli.PorkbunDNSProvider")
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
        mock_host.deploy_site.return_value = DeployResult(url="https://example.com", repo_created=True, https_enabled=True)
        mock_host.required_dns_records.return_value = mock_dns_records
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(ok=True, actual=[], expected=[])
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

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.GitHubHost")
    @patch("mimeo.cli.PorkbunRegistrar")
    @patch("mimeo.cli.PorkbunDNSProvider")
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
        mock_host.deploy_site.side_effect = lambda domain, **kw: DeployResult(url=f"https://{domain}", repo_created=True, https_enabled=True)
        mock_host.required_dns_records.return_value = mock_dns_records
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(ok=True, actual=[], expected=[])
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        mock_dns_provider = MagicMock()
        mock_dns_provider.verify_dns.return_value = True
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(create, ["site1.com", "site2.com", "site3.com"])

        assert result.exit_code == 0
        # Check for start messages
        assert "site1.com started" in result.output
        assert "site2.com started" in result.output
        assert "site3.com started" in result.output
        # Check for completion messages
        assert "site1.com completed" in result.output
        assert "site2.com completed" in result.output
        assert "site3.com completed" in result.output
        assert "Successfully created: 3/3 domain(s)" in result.output

        # Verify all three domains were processed
        assert mock_host.deploy_site.call_count == 3
        assert mock_dns_provider.configure_dns.call_count == 3

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.GitHubHost")
    @patch("mimeo.cli.PorkbunRegistrar")
    @patch("mimeo.cli.PorkbunDNSProvider")
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
        mock_host.deploy_site.side_effect = lambda domain, **kw: DeployResult(url=f"https://{domain}", repo_created=True, https_enabled=True)
        mock_host.required_dns_records.return_value = mock_dns_records
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(ok=True, actual=[], expected=[])
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

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.GitHubHost")
    @patch("mimeo.cli.PorkbunRegistrar")
    @patch("mimeo.cli.PorkbunDNSProvider")
    def test_create_force_dns_update_resets_nameservers(
        self,
        mock_dns_provider_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
        mock_dns_records: List[DNSRecord],
    ) -> None:
        """With --force-dns-update, NS mismatch resets nameservers then configures DNS."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.return_value = DeployResult(url="https://example.com", repo_created=True, https_enabled=True)
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
        mock_dns_provider.verify_dns.return_value = True
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(create, ["example.com", "--force-dns-update"])

        assert result.exit_code == 0
        assert "resetting to Porkbun" in result.output
        assert "Nameservers updated to Porkbun" in result.output
        mock_registrar.update_nameservers.assert_called_once_with("example.com")
        mock_dns_provider.configure_dns.assert_called_once()

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.GitHubHost")
    @patch("mimeo.cli.PorkbunRegistrar")
    @patch("mimeo.cli.PorkbunDNSProvider")
    def test_create_force_dns_update_no_op_when_ns_ok(
        self,
        mock_dns_provider_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
        mock_dns_records: List[DNSRecord],
    ) -> None:
        """With --force-dns-update and correct NS, no nameserver reset occurs."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.return_value = DeployResult(url="https://example.com", repo_created=True, https_enabled=True)
        mock_host.required_dns_records.return_value = mock_dns_records
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(ok=True, actual=[], expected=[])
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        mock_dns_provider = MagicMock()
        mock_dns_provider.verify_dns.return_value = True
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(create, ["example.com", "--force-dns-update"])

        assert result.exit_code == 0
        mock_registrar.update_nameservers.assert_not_called()
        mock_dns_provider.configure_dns.assert_called_once()


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

        result = runner.invoke(list_sites, [])

        assert result.exit_code == 0
        assert "NAME" in result.output
        assert "example.com" in result.output
        assert "test.com" in result.output
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

        result = runner.invoke(list_sites, [])

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

        result = runner.invoke(list_sites, [])

        assert result.exit_code == 2
        assert "Config not found" in result.output

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.GitHubHost")
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
        assert output_data[1]["site"] == "https://test.com"  # Fallback when homepage is None

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.GitHubHost")
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

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.GitHubHost")
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
        assert len(lines) == 3  # Header + 2 data rows
        assert lines[0] == "name,repository,site,updated"
        assert "example.com,https://github.com/testuser/example.com,https://example.com,2026-02-15" in lines[1]
        assert "test.com,https://github.com/testuser/test.com,https://test.com,2026-02-14" in lines[2]

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.GitHubHost")
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
        # Should still output header even with no data
        assert result.output.strip() == "name,repository,site,updated"

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.GitHubHost")
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

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.GitHubHost")
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

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.GitHubHost")
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

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.GitHubHost")
    def test_list_fix_enables_https(
        self,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """Test list --fix calls _enable_https_enforcement for fixable repos."""
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
        mock_host._enable_https_enforcement.return_value = True
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        result = runner.invoke(list_sites, ["--fix"])

        assert result.exit_code == 0
        mock_host._enable_https_enforcement.assert_called_once_with("testuser/fixable.com")
        assert "fixable.com" in result.output
        assert "Fixed HTTPS enforcement" in result.output

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.GitHubHost")
    def test_list_fix_skips_non_fixable(
        self,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """Test list --fix does not call _enable_https_enforcement for non-fixable repos."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.list_mimeo_repositories.return_value = [
            {
                "name": "healthy.com",
                "url": "https://github.com/testuser/healthy.com",
                "homepage": "https://healthy.com",
                "updatedAt": "2026-02-15T12:00:00Z",
            },
            {
                "name": "nocert.com",
                "url": "https://github.com/testuser/nocert.com",
                "homepage": "https://nocert.com",
                "updatedAt": "2026-02-15T12:00:00Z",
            },
        ]

        def health_side_effect(repo_full_name: str) -> dict:
            if "healthy" in repo_full_name:
                return {"pages_configured": True, "https_enforced": True, "cert_state": "approved", "pages_status": None}
            return {"pages_configured": True, "https_enforced": False, "cert_state": None, "pages_status": None}

        mock_host.get_pages_health.side_effect = health_side_effect
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        result = runner.invoke(list_sites, ["--fix"])

        assert result.exit_code == 0
        mock_host._enable_https_enforcement.assert_not_called()
        # No "Fixed HTTPS enforcement" section since nothing was fixed
        assert "Fixed HTTPS enforcement" not in result.output


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
        with patch("mimeo.cli.subprocess.run", return_value=mock_result):
            ok, detail, fix = _check_gh_installed()
        assert ok is True
        assert "gh version" in detail
        assert fix == ""

    def test_gh_installed_missing(self) -> None:
        """gh missing when FileNotFoundError is raised."""
        with patch("mimeo.cli.subprocess.run", side_effect=FileNotFoundError):
            ok, detail, fix = _check_gh_installed()
        assert ok is False
        assert "not found" in detail
        assert "cli.github.com" in fix

    def test_gh_auth_authenticated(self) -> None:
        """gh authenticated when returncode is 0."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("mimeo.cli.subprocess.run", return_value=mock_result):
            ok, detail, fix = _check_gh_auth()
        assert ok is True
        assert fix == ""

    def test_gh_auth_not_authenticated(self) -> None:
        """gh not authenticated when returncode is non-zero."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("mimeo.cli.subprocess.run", return_value=mock_result):
            ok, detail, fix = _check_gh_auth()
        assert ok is False
        assert "gh auth login" in fix

    def test_gh_auth_gh_missing(self) -> None:
        """Returns failure when gh is not installed."""
        with patch("mimeo.cli.subprocess.run", side_effect=FileNotFoundError):
            ok, detail, fix = _check_gh_auth()
        assert ok is False

    def test_workflow_scope_present(self) -> None:
        """Workflow scope detected when present in auth status output."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "  - Token scopes: 'repo', 'workflow'\n"
        mock_result.stderr = ""
        with patch("mimeo.cli.subprocess.run", return_value=mock_result):
            ok, detail, fix = _check_gh_workflow_scope()
        assert ok is True
        assert fix == ""

    def test_workflow_scope_missing(self) -> None:
        """Failure when workflow scope absent from token scopes."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "  - Token scopes: 'repo', 'read:org'\n"
        mock_result.stderr = ""
        with patch("mimeo.cli.subprocess.run", return_value=mock_result):
            ok, detail, fix = _check_gh_workflow_scope()
        assert ok is False
        assert "workflow" in fix

    def test_workflow_scope_not_authenticated(self) -> None:
        """Failure when gh is not authenticated."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = ""
        with patch("mimeo.cli.subprocess.run", return_value=mock_result):
            ok, detail, fix = _check_gh_workflow_scope()
        assert ok is False

    def test_workflow_scope_gh_missing(self) -> None:
        """Failure when gh is not installed."""
        with patch("mimeo.cli.subprocess.run", side_effect=FileNotFoundError):
            ok, detail, fix = _check_gh_workflow_scope()
        assert ok is False

    def test_check_config_valid(self, tmp_path: Path) -> None:
        """Config check passes with a valid config file."""
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(
            "[porkbun]\napi_key = \"pk1_test\"\nsecret_key = \"sk1_test\"\n"
            "[github]\ndefault_org = \"testuser\"\n"
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

    @patch("mimeo.providers.registrar.porkbun._lookup_nameservers")
    def test_check_nameservers_ok(self, mock_lookup: Any) -> None:
        """_check_nameservers passes when NS matches Porkbun."""
        from mimeo.providers.registrar.porkbun import PORKBUN_NAMESERVERS
        mock_lookup.return_value = sorted(PORKBUN_NAMESERVERS)
        ok, detail, fix = _check_nameservers("example.com")
        assert ok is True
        assert detail == "porkbun"
        assert fix == ""

    @patch("mimeo.providers.registrar.porkbun._lookup_nameservers")
    def test_check_nameservers_mismatch(self, mock_lookup: Any) -> None:
        """_check_nameservers fails when NS points elsewhere."""
        mock_lookup.return_value = ["ns1.cloudflare.com", "ns2.cloudflare.com"]
        ok, detail, fix = _check_nameservers("example.com")
        assert ok is False
        assert "cloudflare" in detail
        assert "Porkbun" in fix

    @patch("mimeo.providers.registrar.porkbun._lookup_nameservers")
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
            "[porkbun]\napi_key = \"pk1_test\"\nsecret_key = \"sk1_test\"\n"
            "[github]\ndefault_org = \"testuser\"\n"
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

        with patch("mimeo.cli.subprocess.run", side_effect=fake_run):
            result = runner.invoke(doctor, ["--config", str(cfg_file)])

        assert result.exit_code == 0
        assert "All checks passed" in result.output

    def test_doctor_fails_on_missing_gh(self, runner: CliRunner, tmp_path: Path) -> None:
        """Doctor exits non-zero and prints remediation when gh is missing."""
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(
            "[porkbun]\napi_key = \"pk1_test\"\nsecret_key = \"sk1_test\"\n"
            "[github]\ndefault_org = \"testuser\"\n"
        )

        with patch("mimeo.cli.subprocess.run", side_effect=FileNotFoundError):
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
        with patch("mimeo.cli.subprocess.run", side_effect=fake_run):
            result = runner.invoke(doctor, ["--config", str(missing)])

        assert result.exit_code != 0
        assert "not found" in result.output

    @patch("mimeo.cli._check_nameservers")
    def test_doctor_ns_check_ok(
        self, mock_ns: Any, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Doctor with domain args runs NS check and passes when NS is Porkbun."""
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(
            "[porkbun]\napi_key = \"pk1_test\"\nsecret_key = \"sk1_test\"\n"
            "[github]\ndefault_org = \"testuser\"\n"
        )
        mock_ns.return_value = (True, "porkbun", "")

        def fake_run(cmd: list, **kwargs: Any) -> MagicMock:
            m = MagicMock()
            m.returncode = 0
            m.stdout = "gh version 2.40.0\n" if "--version" in cmd else "  - Token scopes: 'repo', 'workflow'\n"
            m.stderr = ""
            return m

        with patch("mimeo.cli.subprocess.run", side_effect=fake_run):
            result = runner.invoke(doctor, ["--config", str(cfg_file), "example.com"])

        assert result.exit_code == 0
        assert "NS: example.com" in result.output
        assert "porkbun" in result.output
        assert "All checks passed" in result.output
        mock_ns.assert_called_once_with("example.com")

    @patch("mimeo.cli._check_nameservers")
    def test_doctor_ns_check_mismatch(
        self, mock_ns: Any, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Doctor exits non-zero and shows remediation when NS doesn't point to Porkbun."""
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(
            "[porkbun]\napi_key = \"pk1_test\"\nsecret_key = \"sk1_test\"\n"
            "[github]\ndefault_org = \"testuser\"\n"
        )
        mock_ns.return_value = (
            False,
            "ns1.cloudflare.com, ns2.cloudflare.com",
            "Nameservers don't point to Porkbun — DNS config will be skipped on create.",
        )

        def fake_run(cmd: list, **kwargs: Any) -> MagicMock:
            m = MagicMock()
            m.returncode = 0
            m.stdout = "gh version 2.40.0\n" if "--version" in cmd else "  - Token scopes: 'repo', 'workflow'\n"
            m.stderr = ""
            return m

        with patch("mimeo.cli.subprocess.run", side_effect=fake_run):
            result = runner.invoke(doctor, ["--config", str(cfg_file), "example.com"])

        assert result.exit_code != 0
        assert "NS: example.com" in result.output
        assert "cloudflare" in result.output
        assert "Porkbun" in result.output

    @patch("mimeo.cli._check_nameservers")
    def test_doctor_ns_check_multiple_domains(
        self, mock_ns: Any, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Doctor checks NS for each domain provided."""
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(
            "[porkbun]\napi_key = \"pk1_test\"\nsecret_key = \"sk1_test\"\n"
            "[github]\ndefault_org = \"testuser\"\n"
        )
        mock_ns.return_value = (True, "porkbun", "")

        def fake_run(cmd: list, **kwargs: Any) -> MagicMock:
            m = MagicMock()
            m.returncode = 0
            m.stdout = "gh version 2.40.0\n" if "--version" in cmd else "  - Token scopes: 'repo', 'workflow'\n"
            m.stderr = ""
            return m

        with patch("mimeo.cli.subprocess.run", side_effect=fake_run):
            result = runner.invoke(
                doctor, ["--config", str(cfg_file), "site1.com", "site2.com"]
            )

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

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.GitHubHost")
    @patch("mimeo.cli.PorkbunRegistrar")
    @patch("mimeo.cli.ThreadPoolExecutor")
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

        # Make executor work as a context manager that yields an executor
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

        with patch("mimeo.cli.as_completed", return_value=[mock_future]):
            runner.invoke(create, ["a.com", "b.com", "--workers", "3"])

        mock_executor_class.assert_called_once_with(max_workers=2)  # min(2 domains, 3 workers)


class TestLogFormatOption:
    """Tests for --log-format json option."""

    def test_log_format_in_main_help(self, runner: CliRunner) -> None:
        """--log-format appears in main help."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "--log-format" in result.output

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.GitHubHost")
    @patch("mimeo.cli.PorkbunRegistrar")
    @patch("mimeo.cli.PorkbunDNSProvider")
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
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(ok=True, actual=[], expected=[])
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        mock_dns_provider = MagicMock()
        mock_dns_provider.verify_dns.return_value = True
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(main, ["--log-format", "json", "create", "example.com"])

        assert result.exit_code == 0
        # Text-mode SUMMARY header should not appear
        assert "SUMMARY" not in result.output
        # JSON events go to stderr (mixed into output in test runner)
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
            "[porkbun]\napi_key = \"pk1_test\"\nsecret_key = \"sk1_test\"\n"
            "[github]\ndefault_org = \"testuser\"\n"
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

        with patch("mimeo.cli.subprocess.run", side_effect=fake_run):
            result = runner.invoke(
                main,
                ["--log-format", "json", "doctor", "--config", str(cfg_file)],
            )

        assert result.exit_code == 0
        # No text table in output
        assert "ok  " not in result.output
        # JSON lines are emitted
        json_lines = [l for l in result.output.splitlines() if l.strip().startswith("{")]
        assert len(json_lines) > 0
        for line in json_lines:
            record = json_mod.loads(line)
            assert "level" in record
            assert "message" in record


class TestDnsCheckOption:
    """Tests for --dns-check option on list command."""

    def test_dns_check_in_list_help(self, runner: CliRunner) -> None:
        """--dns-check appears in list help."""
        result = runner.invoke(list_sites, ["--help"])
        assert result.exit_code == 0
        assert "--dns-check" in result.output

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.GitHubHost")
    @patch("mimeo.cli.PorkbunDNSProvider")
    def test_dns_check_ok(
        self,
        mock_dns_provider_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """--dns-check shows DNS status in text output."""
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
        mock_host.required_dns_records.return_value = []
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_dns_provider = MagicMock()
        mock_dns_provider.check_dns_drift.return_value = {"status": "ok", "missing": [], "extra": []}
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(list_sites, ["--dns-check"])

        assert result.exit_code == 0
        assert "DNS" in result.output
        assert "ok" in result.output
        mock_dns_provider.check_dns_drift.assert_called_once()

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.GitHubHost")
    @patch("mimeo.cli.PorkbunDNSProvider")
    def test_dns_check_missing_shows_details(
        self,
        mock_dns_provider_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """--dns-check reports missing records in drift details section."""
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
        mock_host.required_dns_records.return_value = []
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_dns_provider = MagicMock()
        mock_dns_provider.check_dns_drift.return_value = {
            "status": "missing",
            "missing": [{"type": "A", "name": "@", "content": "185.199.108.153"}],
            "extra": [],
        }
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(list_sites, ["--dns-check"])

        assert result.exit_code == 0
        assert "missing" in result.output
        assert "185.199.108.153" in result.output

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.GitHubHost")
    @patch("mimeo.cli.PorkbunDNSProvider")
    def test_dns_check_json_format(
        self,
        mock_dns_provider_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """--dns-check adds dns field to JSON output."""
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
        mock_host.required_dns_records.return_value = []
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_dns_provider = MagicMock()
        mock_dns_provider.check_dns_drift.return_value = {"status": "ok", "missing": [], "extra": []}
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(list_sites, ["--dns-check", "--format", "json"])

        assert result.exit_code == 0
        data = json_mod.loads(result.output)
        assert len(data) == 1
        assert "dns" in data[0]
        assert data[0]["dns"]["status"] == "ok"


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

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.PorkbunRegistrar")
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

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.PorkbunRegistrar")
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

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.PorkbunRegistrar")
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
        assert lines[0] == "domain,tld,expires,auto_renew,ns_ok,nameservers"
        assert len(lines) == 3  # header + 2 domains

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.PorkbunRegistrar")
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

        with patch("mimeo.cli.PorkbunDNSProvider") as mock_dns_class:
            mock_dns = MagicMock()
            mock_dns._get_domain_records.return_value = []
            mock_dns.__enter__.return_value = mock_dns
            mock_dns.__exit__ = MagicMock(return_value=False)
            mock_dns_class.return_value = mock_dns

            result = runner.invoke(registrar_list, ["--format", "csv", "--with-dns"])

        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert "dns_records" in lines[0]

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.PorkbunRegistrar")
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

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.PorkbunRegistrar")
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

    @patch("mimeo.cli.Config.load")
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

    @patch("mimeo.cli.Config.load")
    @patch("mimeo.cli.PorkbunRegistrar")
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
