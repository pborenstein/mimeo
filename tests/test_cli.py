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
    main,
)
from mimeo.cli._processing import set_cli_overrides

from mimeo.config import Config
from mimeo.exceptions import ConfigurationError, HostError, RegistrarError
from mimeo.models import DNSRecord, NameserverCheckResult
from mimeo.providers.base import DeployResult


# Patch target prefixes for each submodule
_CREATE = "mimeo.cli.create"
_DOCTOR = "mimeo.cli.doctor"
_PROCESSING = "mimeo.cli._processing"


@pytest.fixture
def runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture(autouse=True)
def _clean_cli_overrides() -> None:
    """Reset --template-org/--deploy-org module state around every test."""
    set_cli_overrides(None, None)
    yield
    set_cli_overrides(None, None)


@pytest.fixture
def mock_config() -> Config:
    """Create mock config."""
    return Config(
        porkbun_api_key="pk1_test",
        porkbun_secret="sk1_test",
        github_username="testuser",
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
        """No domain args prints full help instead of Click's terse error."""
        result = runner.invoke(create, [])
        assert result.exit_code != 0
        assert "Missing argument" not in result.output
        assert "Usage: create" in result.output
        assert "Provisions a GitHub repository from a template" in result.output

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
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(create, ["example.com"])

        assert result.exit_code == 0
        assert "Configuring GitHub repository" in result.output
        assert "Configuring DNS records" in result.output
        assert "Created 1/1 domains" in result.output
        assert "https://example.com" in result.output

        mock_config_load.assert_called_once()
        mock_host_class.assert_called_with(
            default_org="testuser", template_org="tepiton"
        )
        mock_host.deploy_site.assert_called_once()
        mock_host.required_dns_records.assert_called_once_with("example.com")
        mock_registrar.check_nameservers.assert_called_once_with("example.com")
        mock_dns_provider.configure_dns.assert_called_once_with("example.com", mock_dns_records)

    @patch("mimeo.config.Config.load")
    @patch(f"{_CREATE}.GitHubHost")
    @patch(f"{_CREATE}.PorkbunRegistrar")
    def test_create_skips_dns_when_repo_already_existed(
        self,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
        mock_dns_records: List[DNSRecord],
    ) -> None:
        """create does not touch DNS when the repo already existed (no --force)."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.return_value = DeployResult(
            url="https://example.com", repo_created=False, https_enabled=True, repo_existed=True
        )
        mock_host.required_dns_records.return_value = mock_dns_records
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.domain_exists.return_value = True
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        result = runner.invoke(create, ["example.com"])

        assert result.exit_code == 0
        assert "Repository already exists" in result.output
        assert "skipping DNS configuration" in result.output
        mock_registrar.check_nameservers.assert_not_called()
        # The recap must not claim a creation that did not happen
        assert "Created 0/1 domains (1 already existed)" in result.output
        assert "⚠ example.com" in result.output
        assert "✓ example.com" not in result.output
        assert "DNS: not configured (repository already existed)" in result.output

    @patch("mimeo.config.Config.load")
    @patch(f"{_CREATE}.GitHubHost")
    @patch(f"{_CREATE}.PorkbunRegistrar")
    def test_create_recap_counts_only_actual_creations(
        self,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """Both repos already existed: recap says 0 created, never 'Created 2/2'.

        Multi-domain runs suppress the step logs, so the recap is the only
        view -- it must carry the already-existed outcome on its own.
        """
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.side_effect = lambda domain, **kw: DeployResult(
            url=f"https://{domain}", repo_created=False, https_enabled=True, repo_existed=True
        )
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.domain_exists.return_value = True
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        result = runner.invoke(create, ["clarkegeagan.com", "clarkegeagan.org"])

        assert result.exit_code == 0
        assert "Created 0/2 domains (2 already existed)" in result.output
        assert "Created 2/2" not in result.output
        # two progress outcome lines + two recap blocks
        assert result.output.count("already existed, left unchanged") == 2
        assert result.output.count("Already exists, left unchanged") == 2
        assert "✓" not in result.output
        assert "DNS: not configured (repository already existed)" in result.output

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

        with patch(f"{_CREATE}.PorkbunRegistrar") as mock_registrar_class:
            mock_registrar = MagicMock()
            mock_registrar.domain_exists.return_value = True
            mock_registrar.__enter__.return_value = mock_registrar
            mock_registrar_class.return_value = mock_registrar

            result = runner.invoke(create, ["example.com"])

        # Unmatched provider failure: definitive, not transient -- exits 1
        assert result.exit_code == 1
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
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(create, ["example.com"])

        assert result.exit_code == 0
        mock_host_class.assert_called_with(
            default_org="testuser", template_org="tepiton"
        )

    @patch("mimeo.config.Config.load")
    @patch(f"{_CREATE}.GitHubHost")
    @patch(f"{_CREATE}.PorkbunRegistrar")
    def test_create_template_defaults_to_config(
        self,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
        mock_dns_records: List[DNSRecord],
    ) -> None:
        """Omitting --template uses defaults.template from config."""
        mock_config.default_template = "custom-template"
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

        result = runner.invoke(create, ["example.com"])

        assert result.exit_code == 0
        mock_host.deploy_site.assert_called_with(
            "example.com", template="custom-template", force=False
        )

    @patch("mimeo.config.Config.load")
    @patch(f"{_CREATE}.GitHubHost")
    @patch(f"{_CREATE}.PorkbunRegistrar")
    def test_create_global_org_flags_override_config(
        self,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
        mock_dns_records: List[DNSRecord],
    ) -> None:
        """Global --template-org/--deploy-org flags win over config values."""
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

        result = runner.invoke(
            main,
            [
                "--template-org", "cli-tpl-org",
                "--deploy-org", "cli-deploy-org",
                "create", "example.com",
            ],
        )

        assert result.exit_code == 0
        mock_host_class.assert_called_with(
            default_org="cli-deploy-org", template_org="cli-tpl-org"
        )

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
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(create, ["site1.com", "site2.com", "site3.com"])

        assert result.exit_code == 0
        assert "site1.com" in result.output
        assert "site2.com" in result.output
        assert "site3.com" in result.output
        assert "Created 3/3 domains" in result.output

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
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(create, ["site1.com", "site2.com", "--sequential"])

        assert result.exit_code == 0
        assert "site1.com" in result.output
        assert "site2.com" in result.output
        assert "Created 2/2 domains" in result.output

    @patch("mimeo.config.Config.load")
    @patch(f"{_CREATE}.GitHubHost")
    @patch(f"{_CREATE}.PorkbunRegistrar")
    @patch(f"{_CREATE}.PorkbunDNSProvider")
    def test_create_parallel_reports_progress(
        self,
        mock_dns_provider_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
        mock_dns_records: List[DNSRecord],
    ) -> None:
        """Parallel runs announce each domain's start and outcome -- no silent gaps.

        Step logs are suppressed for parallel runs, so without these lines a
        multi-domain create prints nothing between start and recap.
        """
        mock_config_load.return_value = mock_config

        def _deploy(domain: str, **kw: Any) -> Any:
            if domain == "old.com":
                return DeployResult(
                    url=f"https://{domain}", repo_created=False, https_enabled=True, repo_existed=True
                )
            if domain == "bad.com":
                raise HostError(
                    "PUT repos/tepiton/bad.com/pages: gh: Invalid cname (HTTP 400)",
                    status_code=400,
                )
            return DeployResult(
                url=f"https://{domain}", repo_created=True, https_enabled=True, repo_existed=False
            )

        mock_host = MagicMock()
        mock_host.deploy_site.side_effect = _deploy
        mock_host.required_dns_records.return_value = mock_dns_records
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.domain_exists.return_value = True
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(
            ok=True, actual=[], expected=[]
        )
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        mock_dns_provider = MagicMock()
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(create, ["new.com", "old.com", "bad.com"])

        # One "Creating" line per domain, emitted as each worker starts
        assert "Creating new.com..." in result.output
        assert "Creating old.com..." in result.output
        assert "Creating bad.com..." in result.output
        # One outcome line per domain, in whatever order they finish
        assert "✓ new.com created" in result.output
        assert "⚠ old.com: already existed, left unchanged" in result.output
        assert "✗ bad.com: PUT repos/tepiton/bad.com/pages" in result.output
        assert "Created 1/3 domains (1 already existed, 1 failed)" in result.output
        assert result.exit_code == 6


class TestCreateDomainOwnership:
    """Tests that create refuses to act on domains not owned in Porkbun."""

    @patch("mimeo.config.Config.load")
    @patch(f"{_CREATE}.GitHubHost")
    @patch(f"{_CREATE}.PorkbunRegistrar")
    def test_create_refuses_unregistered_domain(
        self,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """create does nothing to GitHub when the domain isn't in this Porkbun account."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.domain_exists.return_value = False
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        result = runner.invoke(create, ["not-mine.com"])

        assert result.exit_code != 0
        assert "not registered in this Porkbun account" in result.output
        mock_host.deploy_site.assert_not_called()

    @patch("mimeo.config.Config.load")
    @patch(f"{_CREATE}.GitHubHost")
    @patch(f"{_CREATE}.PorkbunRegistrar")
    def test_create_failure_output_is_deduplicated(
        self,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """Failure detail appears inline and once in the recap -- no banner, no third copy."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        mock_registrar = MagicMock()
        mock_registrar.domain_exists.return_value = False
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        result = runner.invoke(create, ["not-mine.com"])

        assert result.exit_code != 0
        assert "SUMMARY" not in result.output
        assert "Successfully created" not in result.output
        assert "[provider]" not in result.output
        assert "Created 0/1 domains" in result.output
        # ownership failure raises before any inline step log: the recap is
        # the single place the reason appears
        assert result.output.count("not registered in this Porkbun account") == 1
        assert "1 of 1 domains failed" in result.output

    @patch("mimeo.config.Config.load")
    @patch(f"{_CREATE}.GitHubHost")
    def test_create_dry_run_mentions_ownership_check(
        self,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """--dry-run output reflects the ownership check even though it isn't run."""
        mock_config_load.return_value = mock_config

        result = runner.invoke(create, ["example.com", "--dry-run"])

        assert result.exit_code == 0
        assert "Would verify domain is registered in this Porkbun account" in result.output


class TestCreateSkipDns:
    """Tests for create --skip-dns."""

    @patch("mimeo.config.Config.load")
    @patch(f"{_CREATE}.GitHubHost")
    @patch(f"{_CREATE}.PorkbunRegistrar")
    def test_create_skip_dns(
        self,
        mock_registrar_class: Any,
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

        mock_registrar = MagicMock()
        mock_registrar.domain_exists.return_value = True
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar_class.return_value = mock_registrar

        result = runner.invoke(create, ["example.com", "--skip-dns"])

        assert result.exit_code == 0
        assert "Skipping DNS configuration" in result.output


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


class TestCreateForceCommand:
    """Tests for create --force (absorbed from the former template apply)."""

    @patch("mimeo.config.Config.load")
    @patch(f"{_CREATE}.GitHubHost")
    def test_create_force_dry_run(
        self,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """create --force --dry-run shows what would happen."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        result = runner.invoke(
            create, ["example.com", "--template", "mimeo", "--force", "--dry-run"]
        )

        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        assert "Would delete and recreate" in result.output

    @patch("mimeo.config.Config.load")
    @patch(f"{_CREATE}.GitHubHost")
    @patch(f"{_CREATE}.PorkbunRegistrar")
    @patch(f"{_CREATE}.PorkbunDNSProvider")
    def test_create_force_with_yes(
        self,
        mock_dns_provider_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
        mock_dns_records: List[DNSRecord],
    ) -> None:
        """create --force --yes skips confirmation."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.deploy_site.return_value = DeployResult(
            url="https://example.com", repo_created=True, https_enabled=True, repo_existed=True
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
        mock_dns_provider.__enter__.return_value = mock_dns_provider
        mock_dns_provider_class.return_value = mock_dns_provider

        result = runner.invoke(
            create, ["example.com", "--template", "mimeo", "--force", "--yes"]
        )

        assert result.exit_code == 0
        mock_host.deploy_site.assert_called_once_with(
            "example.com", template="mimeo", force=True
        )

    @patch("mimeo.config.Config.load")
    @patch(f"{_CREATE}.GitHubHost")
    def test_create_force_prompts_without_yes(
        self,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """create --force without --yes prompts for confirmation and aborts on 'n'."""
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        result = runner.invoke(
            create, ["example.com", "--template", "mimeo", "--force"], input="n\n"
        )

        assert result.exit_code == 0
        assert "WARNING" in result.output
        assert "Aborted." in result.output
        mock_host.deploy_site.assert_not_called()
