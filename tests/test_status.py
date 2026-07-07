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

        result = runner.invoke(status, ["--format", "json"])

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

        result = runner.invoke(status, ["--problems", "--format", "json"])

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

        result = runner.invoke(status, [])

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

        result = runner.invoke(status, ["--format", "json", "--workers", "1"])

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

        result = runner.invoke(status, ["--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data[0]["dns_status"] == "missing"
        assert data[0]["site_health"] == "fixable"
        assert data[0]["ns_ok"] is False
