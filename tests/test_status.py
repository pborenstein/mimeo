"""Tests for the status command."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from mimeo.cli.status import status
from mimeo.config import Config
from mimeo.models import NameserverCheckResult

_STATUS = "mimeo.cli.status"


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_config(tmp_path: Any) -> Config:
    return Config(
        porkbun_api_key="pk1_test",
        porkbun_secret="sk1_test",
        github_username="testorg",
    )


def _make_host(repos: list, health: dict | None = None) -> MagicMock:
    host = MagicMock()
    host.list_mimeo_repositories.return_value = repos
    host.get_pages_health.return_value = health or {
        "pages_configured": True,
        "https_enforced": True,
        "cert_state": "approved",
        "pages_status": "built",
    }
    host.required_dns_records.return_value = []
    host.__enter__.return_value = host
    host.__exit__ = MagicMock(return_value=False)
    return host


def _make_registrar(domains: list, ns_ok: bool = True) -> MagicMock:
    registrar = MagicMock()
    registrar.list_domains.return_value = domains
    registrar.check_nameservers.return_value = NameserverCheckResult(
        ok=ns_ok,
        actual=["curitiba.ns.porkbun.com"] if ns_ok else ["ns1.cloudflare.com"],
        expected=["curitiba.ns.porkbun.com"],
    )
    registrar.__enter__.return_value = registrar
    registrar.__exit__ = MagicMock(return_value=False)
    return registrar


def _make_dns_provider(drift_status: str = "ok") -> MagicMock:
    dns_provider = MagicMock()
    dns_provider.check_dns_drift.return_value = {
        "status": drift_status,
        "missing": [],
        "extra": [],
    }
    dns_provider.__enter__.return_value = dns_provider
    dns_provider.__exit__ = MagicMock(return_value=False)
    return dns_provider


class TestStatusGuards:
    def test_no_args_refused(self, runner: CliRunner) -> None:
        """status with no domains and no --all refuses to run."""
        from mimeo.exceptions import EXIT_CONFIG

        result = runner.invoke(status, [])
        assert result.exit_code == EXIT_CONFIG
        assert "--all" in result.output

    def test_domains_and_all_refused(self, runner: CliRunner) -> None:
        from mimeo.exceptions import EXIT_CONFIG

        result = runner.invoke(status, ["example.com", "--all"])
        assert result.exit_code == EXIT_CONFIG
        assert "not both" in result.output


class TestStatusCommand:
    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.GitHubHost")
    @patch(f"{_STATUS}.PorkbunRegistrar")
    @patch(f"{_STATUS}.PorkbunDNSProvider")
    def test_fleet_union(
        self,
        mock_dns_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """No-arg status covers the union of registered domains and repos."""
        mock_config_load.return_value = mock_config
        mock_registrar_class.return_value = _make_registrar(
            [{"domain": "both.com", "expireDate": "2027-01-01", "autoRenew": "1"},
             {"domain": "nosite.com", "expireDate": "2027-01-01", "autoRenew": "0"}]
        )
        mock_host_class.return_value = _make_host(
            [{"name": "both.com"}, {"name": "noregistrar.com"}]
        )
        mock_dns_class.return_value = _make_dns_provider()

        result = runner.invoke(status, ["--all", "--format", "json"])

        assert result.exit_code == 0
        data = {r["domain"]: r for r in json.loads(result.stdout)}
        assert set(data) == {"both.com", "nosite.com", "noregistrar.com"}

        assert data["both.com"]["registered"] is True
        assert data["both.com"]["repo"] is True
        assert data["both.com"]["dns_status"] == "ok"
        assert data["both.com"]["site_health"] == "healthy"

        assert data["nosite.com"]["repo"] is False
        assert data["nosite.com"]["site_health"] is None
        assert data["nosite.com"]["dns_status"] is None

        assert data["noregistrar.com"]["registered"] is False
        assert data["noregistrar.com"]["expires"] == ""
        assert data["noregistrar.com"]["site_health"] == "healthy"

    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.GitHubHost")
    @patch(f"{_STATUS}.PorkbunRegistrar")
    @patch(f"{_STATUS}.PorkbunDNSProvider")
    def test_specific_domains(
        self,
        mock_dns_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """Explicit domains are reported even when unknown to both sides."""
        mock_config_load.return_value = mock_config
        mock_registrar_class.return_value = _make_registrar([])
        mock_host_class.return_value = _make_host([])
        mock_dns_class.return_value = _make_dns_provider()

        result = runner.invoke(status, ["unknown.com", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["domain"] == "unknown.com"
        assert data[0]["registered"] is False
        assert data[0]["repo"] is False

    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.GitHubHost")
    @patch(f"{_STATUS}.PorkbunRegistrar")
    @patch(f"{_STATUS}.PorkbunDNSProvider")
    def test_problems_filter(
        self,
        mock_dns_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """--problems hides fully healthy domains."""
        mock_config_load.return_value = mock_config
        mock_registrar_class.return_value = _make_registrar(
            [{"domain": "healthy.com", "expireDate": "2027-01-01", "autoRenew": "1"},
             {"domain": "nosite.com", "expireDate": "2027-01-01", "autoRenew": "1"}]
        )
        mock_host_class.return_value = _make_host([{"name": "healthy.com"}])
        mock_dns_class.return_value = _make_dns_provider()

        result = runner.invoke(status, ["--all", "--problems", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert [r["domain"] for r in data] == ["nosite.com"]

    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.GitHubHost")
    @patch(f"{_STATUS}.PorkbunRegistrar")
    @patch(f"{_STATUS}.PorkbunDNSProvider")
    def test_text_output(
        self,
        mock_dns_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """Text table shows the summary line and per-domain columns."""
        mock_config_load.return_value = mock_config
        mock_registrar_class.return_value = _make_registrar(
            [{"domain": "site.com", "expireDate": "2027-01-01 00:00:00", "autoRenew": "1"}]
        )
        mock_host_class.return_value = _make_host([{"name": "site.com"}])
        mock_dns_class.return_value = _make_dns_provider()

        result = runner.invoke(status, ["--all"])

        assert result.exit_code == 0
        assert "DOMAIN" in result.output
        assert "site.com" in result.output
        assert "2027-01-01" in result.output
        assert "1 domain(s), 0 with issues" in result.output

    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.GitHubHost")
    @patch(f"{_STATUS}.PorkbunRegistrar")
    @patch(f"{_STATUS}.PorkbunDNSProvider")
    def test_partial_failure(
        self,
        mock_dns_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """A failing domain becomes an error row; others survive."""
        from mimeo.exceptions import EXIT_PARTIAL, RegistrarError

        mock_config_load.return_value = mock_config
        registrar = _make_registrar(
            [{"domain": "good.com", "expireDate": "2027-01-01", "autoRenew": "1"},
             {"domain": "bad.com", "expireDate": "2027-01-01", "autoRenew": "1"}]
        )

        def check_ns(domain: str) -> NameserverCheckResult:
            if domain == "bad.com":
                raise RegistrarError("Failed to communicate with Porkbun API: HTTP 503")
            return NameserverCheckResult(
                ok=True, actual=["curitiba.ns.porkbun.com"], expected=[]
            )

        registrar.check_nameservers.side_effect = check_ns
        mock_registrar_class.return_value = registrar
        mock_host_class.return_value = _make_host([{"name": "good.com"}])
        mock_dns_class.return_value = _make_dns_provider()

        result = runner.invoke(status, ["--all", "--format", "json", "--workers", "1"])

        assert result.exit_code == EXIT_PARTIAL
        data = {r["domain"]: r for r in json.loads(result.stdout)}
        assert data["good.com"]["error"] is None
        assert data["good.com"]["site_health"] == "healthy"
        assert "503" in data["bad.com"]["error"]

    def test_invalid_domain(self, runner: CliRunner) -> None:
        result = runner.invoke(status, ["not_a_domain"])
        assert result.exit_code != 0
        assert "Invalid domain name" in result.output

    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.GitHubHost")
    @patch(f"{_STATUS}.PorkbunRegistrar")
    @patch(f"{_STATUS}.PorkbunDNSProvider")
    def test_ignore_domains_trim_fleet_but_not_explicit(
        self,
        mock_dns_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
    ) -> None:
        """Config ignore list trims --all sweeps; explicit names override."""
        cfg = Config(
            porkbun_api_key="pk1_test",
            porkbun_secret="sk1_test",
            github_username="testorg",
            ignore_domains=["elsewhere.dev"],
        )
        mock_config_load.return_value = cfg
        mock_registrar_class.return_value = _make_registrar(
            [{"domain": "managed.com", "expireDate": "2027-01-01", "autoRenew": "1"},
             {"domain": "elsewhere.dev", "expireDate": "2027-01-01", "autoRenew": "1"}]
        )
        mock_host_class.return_value = _make_host([{"name": "managed.com"}])
        mock_dns_class.return_value = _make_dns_provider()

        fleet = runner.invoke(status, ["--all", "--format", "json"])
        assert fleet.exit_code == 0
        assert [r["domain"] for r in json.loads(fleet.stdout)] == ["managed.com"]
        assert "ignored per config" in fleet.output

        explicit = runner.invoke(status, ["elsewhere.dev", "--format", "json"])
        assert explicit.exit_code == 0
        assert [r["domain"] for r in json.loads(explicit.stdout)] == ["elsewhere.dev"]

    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.GitHubHost")
    @patch(f"{_STATUS}.PorkbunRegistrar")
    @patch(f"{_STATUS}.PorkbunDNSProvider")
    def test_with_dns_includes_records_and_fetches_once(
        self,
        mock_dns_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """--with-dns adds raw records without a second retrieve call."""
        records = [
            {"type": "A", "name": "site.com", "content": "185.199.108.153", "ttl": "600"},
            {"type": "CNAME", "name": "www.site.com", "content": "user.github.io", "ttl": "600"},
        ]
        mock_config_load.return_value = mock_config
        mock_registrar_class.return_value = _make_registrar(
            [{"domain": "site.com", "expireDate": "2027-01-01", "autoRenew": "1"}]
        )
        mock_host_class.return_value = _make_host([{"name": "site.com"}])
        dns_provider = _make_dns_provider()
        dns_provider.get_domain_records.return_value = records
        mock_dns_class.return_value = dns_provider

        result = runner.invoke(status, ["site.com", "--with-dns", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data[0]["dns_records"] == records
        dns_provider.get_domain_records.assert_called_once_with("site.com")
        # drift check received the pre-fetched records instead of refetching
        _, kwargs = dns_provider.check_dns_drift.call_args
        assert kwargs["live_records"] == records

    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.GitHubHost")
    @patch(f"{_STATUS}.PorkbunRegistrar")
    @patch(f"{_STATUS}.PorkbunDNSProvider")
    def test_without_dns_no_records_no_extra_call(
        self,
        mock_dns_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        mock_config_load.return_value = mock_config
        mock_registrar_class.return_value = _make_registrar(
            [{"domain": "site.com", "expireDate": "2027-01-01", "autoRenew": "1"}]
        )
        mock_host_class.return_value = _make_host([{"name": "site.com"}])
        dns_provider = _make_dns_provider()
        mock_dns_class.return_value = dns_provider

        result = runner.invoke(status, ["site.com", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data[0]["dns_records"] == []
        dns_provider.get_domain_records.assert_not_called()

    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.GitHubHost")
    @patch(f"{_STATUS}.PorkbunRegistrar")
    @patch(f"{_STATUS}.PorkbunDNSProvider")
    def test_drift_is_not_an_error_exit(
        self,
        mock_dns_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """Drift and unhealthy sites are findings, not command failures."""
        mock_config_load.return_value = mock_config
        mock_registrar_class.return_value = _make_registrar(
            [{"domain": "drifty.com", "expireDate": "2027-01-01", "autoRenew": "1"}],
            ns_ok=False,
        )
        mock_host_class.return_value = _make_host(
            [{"name": "drifty.com"}],
            health={
                "pages_configured": True,
                "https_enforced": False,
                "cert_state": "approved",
                "pages_status": "built",
            },
        )
        mock_dns_class.return_value = _make_dns_provider(drift_status="missing")

        result = runner.invoke(status, ["--all", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data[0]["dns_status"] == "missing"
        assert data[0]["site_health"] == "fixable"
        assert data[0]["ns_ok"] is False


class TestStatusSourceGithub:
    """Tests for status --source github (absorbed from the former `list`)."""

    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.GitHubHost")
    def test_shows_repositories(
        self,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
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

        result = runner.invoke(status, ["--source", "github", "--all"])

        assert result.exit_code == 0
        assert "NAME" in result.output
        assert "example.com" in result.output
        assert "test.com" in result.output
        assert "https://example.com" in result.output

    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.GitHubHost")
    def test_no_repositories(
        self,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        mock_config_load.return_value = mock_config

        mock_host = MagicMock()
        mock_host.list_mimeo_repositories.return_value = []
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        result = runner.invoke(status, ["--source", "github", "--all"])

        assert result.exit_code == 0
        assert "No mimeo-managed sites found" in result.output
        assert "mimeo create example.com" in result.output

    @patch("mimeo.config.Config.load")
    def test_config_error(
        self,
        mock_config_load: Any,
        runner: CliRunner,
    ) -> None:
        from mimeo.exceptions import ConfigurationError

        mock_config_load.side_effect = ConfigurationError("Config not found")

        result = runner.invoke(status, ["--source", "github", "--all"])

        assert result.exit_code == 2
        assert "Config not found" in result.output

    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.GitHubHost")
    def test_json_format(
        self,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
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

        result = runner.invoke(status, ["--source", "github", "--all", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2
        assert data[0]["domain"] == "example.com"
        assert data[0]["repository"] == "https://github.com/testuser/example.com"
        assert data[0]["site"] == "https://example.com"
        assert data[0]["updated"] == "2026-02-15"

    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.GitHubHost")
    def test_csv_format(
        self,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
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
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        result = runner.invoke(status, ["--source", "github", "--all", "--format", "csv"])

        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert lines[0] == "domain,repository,site,updated"
        assert (
            "example.com,https://github.com/testuser/example.com,https://example.com,2026-02-15"
            in lines[1]
        )

    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.GitHubHost")
    def test_health_text_format(
        self,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
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

        result = runner.invoke(status, ["--source", "github", "--all", "--health"])

        assert result.exit_code == 0
        assert "example.com" in result.output
        assert "fixable" in result.output
        mock_host.get_pages_health.assert_called_once_with("testorg/example.com")

    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.GitHubHost")
    def test_health_json_format(
        self,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
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

        result = runner.invoke(
            status, ["--source", "github", "--all", "--health", "--format", "json"]
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["health"] == "healthy"
        assert data[0]["https_enforced"] is True
        assert data[0]["cert_state"] == "approved"

    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.GitHubHost")
    def test_health_csv_format(
        self,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
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

        result = runner.invoke(
            status, ["--source", "github", "--all", "--health", "--format", "csv"]
        )

        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert lines[0] == "domain,repository,site,updated,health,https_enforced,cert_state"
        assert "pages_error" in lines[1]

    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.GitHubHost")
    def test_show_template(
        self,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """--show-template adds a TEMPLATE column via get_template_repository()."""
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
        mock_host.get_template_repository.return_value = "mimeo-default-template"
        mock_host.__enter__.return_value = mock_host
        mock_host_class.return_value = mock_host

        result = runner.invoke(
            status, ["--source", "github", "--all", "--show-template", "--format", "json"]
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["template"] == "mimeo-default-template"
        mock_host.get_template_repository.assert_called_once_with("testorg/example.com")

    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.GitHubHost")
    def test_domain_args_filter_repos(
        self,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """Named domains filter the repo set instead of requiring --all."""
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

        result = runner.invoke(
            status, ["--source", "github", "example.com", "--format", "json"]
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["domain"] == "example.com"


class TestStatusSourcePorkbun:
    """Tests for status --source porkbun (absorbed from `registrar list`)."""

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

    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.PorkbunRegistrar")
    def test_text_format(
        self,
        mock_registrar_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
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

        result = runner.invoke(status, ["--source", "porkbun", "--all"])

        assert result.exit_code == 0
        assert "DOMAIN" in result.output
        assert "example.com" in result.output
        assert "example.net" in result.output

    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.PorkbunRegistrar")
    def test_json_format(
        self,
        mock_registrar_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        mock_config_load.return_value = mock_config

        mock_registrar = MagicMock()
        mock_registrar.list_domains.return_value = self.SAMPLE_DOMAINS
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(
            ok=True, actual=[], expected=[]
        )
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar.__exit__ = MagicMock(return_value=False)
        mock_registrar_class.return_value = mock_registrar

        result = runner.invoke(status, ["--source", "porkbun", "--all", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2
        assert data[0]["domain"] == "example.com"
        assert data[0]["tld"] == "com"
        assert data[0]["expires"] == "2027-01-15"
        assert data[0]["auto_renew"] is True
        assert data[1]["auto_renew"] is False

    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.PorkbunRegistrar")
    def test_csv_format(
        self,
        mock_registrar_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        mock_config_load.return_value = mock_config

        mock_registrar = MagicMock()
        mock_registrar.list_domains.return_value = self.SAMPLE_DOMAINS
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(
            ok=False, actual=["ns1.other.com"], expected=[]
        )
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar.__exit__ = MagicMock(return_value=False)
        mock_registrar_class.return_value = mock_registrar

        result = runner.invoke(status, ["--source", "porkbun", "--all", "--format", "csv"])

        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert lines[0] == "domain,tld,expires,auto_renew,ns_ok,nameservers,error"
        assert len(lines) == 3

    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.PorkbunRegistrar")
    def test_csv_with_dns_header(
        self,
        mock_registrar_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        mock_config_load.return_value = mock_config

        mock_registrar = MagicMock()
        mock_registrar.list_domains.return_value = [self.SAMPLE_DOMAINS[0]]
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(
            ok=True, actual=[], expected=[]
        )
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar.__exit__ = MagicMock(return_value=False)
        mock_registrar_class.return_value = mock_registrar

        with patch(f"{_STATUS}.PorkbunDNSProvider") as mock_dns_class:
            mock_dns = MagicMock()
            mock_dns.get_domain_records.return_value = []
            mock_dns.__enter__.return_value = mock_dns
            mock_dns.__exit__ = MagicMock(return_value=False)
            mock_dns_class.return_value = mock_dns

            result = runner.invoke(
                status, ["--source", "porkbun", "--all", "--format", "csv", "--with-dns"]
            )

        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert "dns_records" in lines[0]

    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.PorkbunRegistrar")
    def test_empty(
        self,
        mock_registrar_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        mock_config_load.return_value = mock_config

        mock_registrar = MagicMock()
        mock_registrar.list_domains.return_value = []
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar.__exit__ = MagicMock(return_value=False)
        mock_registrar_class.return_value = mock_registrar

        result = runner.invoke(status, ["--source", "porkbun", "--all"])

        assert result.exit_code == 0
        assert "No domains found" in result.output

    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.PorkbunRegistrar")
    def test_ns_ok_flag(
        self,
        mock_registrar_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        mock_config_load.return_value = mock_config

        mock_registrar = MagicMock()
        mock_registrar.list_domains.return_value = [self.SAMPLE_DOMAINS[0]]
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(
            ok=False, actual=["ns1.cloudflare.com"], expected=["curitiba.ns.porkbun.com"]
        )
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar.__exit__ = MagicMock(return_value=False)
        mock_registrar_class.return_value = mock_registrar

        result = runner.invoke(status, ["--source", "porkbun", "--all", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["ns_ok"] is False
        assert "ns1.cloudflare.com" in data[0]["nameservers"]

    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.PorkbunRegistrar")
    def test_domain_args_filter(
        self,
        mock_registrar_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """Named domains filter the registrar's domain set."""
        mock_config_load.return_value = mock_config

        mock_registrar = MagicMock()
        mock_registrar.list_domains.return_value = self.SAMPLE_DOMAINS
        mock_registrar.check_nameservers.return_value = NameserverCheckResult(
            ok=True, actual=[], expected=[]
        )
        mock_registrar.__enter__.return_value = mock_registrar
        mock_registrar.__exit__ = MagicMock(return_value=False)
        mock_registrar_class.return_value = mock_registrar

        result = runner.invoke(
            status, ["--source", "porkbun", "example.com", "--format", "json"]
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["domain"] == "example.com"


class TestStatusSourceDns:
    """Tests for status --source dns (absorbed from `dns show` / `dns check`)."""

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

    def test_no_domains_refused(self, runner: CliRunner) -> None:
        """--source dns has no fleet-wide mode; --all isn't enough."""
        from mimeo.exceptions import EXIT_CONFIG

        result = runner.invoke(status, ["--source", "dns", "--all"])
        assert result.exit_code == EXIT_CONFIG
        assert "Name the domains" in result.output

    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.PorkbunDNSProvider")
    def test_show_text(
        self,
        mock_dns_provider_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """--source dns alone prints a raw record table (like `dns show`)."""
        mock_config_load.return_value = mock_config
        mock_dns_provider = self._mock_dns_provider(mock_dns_provider_class)

        result = runner.invoke(status, ["--source", "dns", "example.com"])

        assert result.exit_code == 0
        mock_dns_provider.get_domain_records.assert_called_once_with("example.com")
        assert "example.com" in result.output
        assert "185.199.108.153" in result.output
        assert "CNAME" in result.output

    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.PorkbunDNSProvider")
    def test_show_json(
        self,
        mock_dns_provider_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        mock_config_load.return_value = mock_config
        self._mock_dns_provider(mock_dns_provider_class)

        result = runner.invoke(status, ["--source", "dns", "example.com", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["domain"] == "example.com"
        assert data[0]["error"] is None
        assert len(data[0]["records"]) == 2
        assert data[0]["records"][0]["content"] == "185.199.108.153"

    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.PorkbunDNSProvider")
    def test_show_csv(
        self,
        mock_dns_provider_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        mock_config_load.return_value = mock_config
        self._mock_dns_provider(mock_dns_provider_class)

        result = runner.invoke(status, ["--source", "dns", "example.com", "--format", "csv"])

        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert lines[0] == "domain,type,name,ttl,prio,content"
        assert len(lines) == 3
        assert lines[1].startswith("example.com,A,")

    @patch(f"{_STATUS}.lookup_nameservers")
    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.PorkbunDNSProvider")
    def test_show_no_records(
        self,
        mock_dns_provider_class: Any,
        mock_config_load: Any,
        mock_lookup: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        mock_config_load.return_value = mock_config
        mock_dns_provider = self._mock_dns_provider(mock_dns_provider_class)
        mock_dns_provider.get_domain_records.return_value = []
        mock_lookup.return_value = []

        result = runner.invoke(status, ["--source", "dns", "example.com"])

        assert result.exit_code == 0
        assert "no records" in result.output

    @patch(f"{_STATUS}.lookup_nameservers")
    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.PorkbunDNSProvider")
    def test_show_empty_zone_external_ns_hint(
        self,
        mock_dns_provider_class: Any,
        mock_config_load: Any,
        mock_lookup: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        mock_config_load.return_value = mock_config
        mock_dns_provider = self._mock_dns_provider(mock_dns_provider_class)
        mock_dns_provider.get_domain_records.return_value = []
        mock_lookup.return_value = ["dns1.p02.nsone.net", "dns2.p02.nsone.net"]

        result = runner.invoke(status, ["--source", "dns", "example.dev"])

        assert result.exit_code == 0
        assert "nsone.net" in result.output
        assert "managed there" in result.output

    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.PorkbunDNSProvider")
    def test_show_partial_failure(
        self,
        mock_dns_provider_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        from mimeo.exceptions import EXIT_PARTIAL, RegistrarError

        mock_config_load.return_value = mock_config
        mock_dns_provider = self._mock_dns_provider(mock_dns_provider_class)
        mock_dns_provider.get_domain_records.side_effect = [
            self.SAMPLE_RECORDS,
            RegistrarError("Failed to communicate with Porkbun API: HTTP 503"),
        ]

        result = runner.invoke(
            status, ["--source", "dns", "good.com", "bad.com", "--format", "json"]
        )

        assert result.exit_code == EXIT_PARTIAL
        data = json.loads(result.stdout)
        assert len(data) == 2
        assert data[0]["domain"] == "good.com"
        assert len(data[0]["records"]) == 2
        assert data[1]["domain"] == "bad.com"
        assert "503" in data[1]["error"]

    def test_show_invalid_domain(self, runner: CliRunner) -> None:
        result = runner.invoke(status, ["--source", "dns", "not_a_domain"])
        assert result.exit_code != 0
        assert "Invalid domain name" in result.output

    @patch("mimeo.config.Config.load")
    @patch(f"{_STATUS}.GitHubHost")
    @patch(f"{_STATUS}.PorkbunRegistrar")
    @patch(f"{_STATUS}.PorkbunDNSProvider")
    def test_check_shows_drift(
        self,
        mock_dns_provider_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """--source dns --problems reproduces `dns check`'s drift comparison."""
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

        result = runner.invoke(status, ["--source", "dns", "example.com", "--problems"])

        assert result.exit_code == 0
        assert "example.com" in result.output
        assert "ok" in result.output
