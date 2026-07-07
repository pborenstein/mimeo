"""Tests for the sync command."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from mimeo.cli.sync import sync
from mimeo.config import Config
from mimeo.exceptions import EXIT_CONFIG, EXIT_PARTIAL, RegistrarError
from mimeo.models import NameserverCheckResult

_SYNC = "mimeo.cli.sync"


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_config() -> Config:
    return Config(
        porkbun_api_key="pk1_test",
        porkbun_secret="sk1_test",
        github_username="testorg",
    )


def _make_host(repos: list, health_state: str = "healthy") -> MagicMock:
    health_by_state = {
        "healthy": {
            "pages_configured": True,
            "https_enforced": True,
            "cert_state": "approved",
            "pages_status": "built",
        },
        "fixable": {
            "pages_configured": True,
            "https_enforced": False,
            "cert_state": "approved",
            "pages_status": "built",
        },
    }
    host = MagicMock()
    host.list_mimeo_repositories.return_value = repos
    host.get_pages_health.return_value = health_by_state[health_state]
    host.required_dns_records.return_value = []
    host.__enter__.return_value = host
    host.__exit__ = MagicMock(return_value=False)
    return host


def _make_registrar(domains: list, ns_ok: bool = True) -> MagicMock:
    registrar = MagicMock()
    registrar.list_domains.return_value = [{"domain": d} for d in domains]
    registrar.check_nameservers.return_value = NameserverCheckResult(
        ok=ns_ok,
        actual=["curitiba.ns.porkbun.com"] if ns_ok else ["ns1.cloudflare.com"],
        expected=["curitiba.ns.porkbun.com"],
    )
    registrar.__enter__.return_value = registrar
    registrar.__exit__ = MagicMock(return_value=False)
    return registrar


def _make_dns_provider(missing: list | None = None) -> MagicMock:
    dns_provider = MagicMock()
    dns_provider.check_dns_drift.return_value = {
        "status": "missing" if missing else "ok",
        "missing": missing or [],
        "extra": [],
    }
    dns_provider.__enter__.return_value = dns_provider
    dns_provider.__exit__ = MagicMock(return_value=False)
    return dns_provider


class TestSyncGuards:
    def test_no_args_refused(self, runner: CliRunner) -> None:
        """sync with no domains and no --all refuses to run."""
        result = runner.invoke(sync, [])
        assert result.exit_code == EXIT_CONFIG
        assert "--all" in result.output

    def test_domains_and_all_refused(self, runner: CliRunner) -> None:
        result = runner.invoke(sync, ["example.com", "--all"])
        assert result.exit_code == EXIT_CONFIG
        assert "not both" in result.output

    def test_invalid_domain(self, runner: CliRunner) -> None:
        result = runner.invoke(sync, ["not_a_domain"])
        assert result.exit_code != 0
        assert "Invalid domain name" in result.output


class TestSyncActions:
    @patch("mimeo.config.Config.load")
    @patch(f"{_SYNC}.GitHubHost")
    @patch(f"{_SYNC}.PorkbunRegistrar")
    @patch(f"{_SYNC}.PorkbunDNSProvider")
    def test_healthy_domain_no_actions(
        self,
        mock_dns_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        mock_config_load.return_value = mock_config
        mock_registrar_class.return_value = _make_registrar(["ok.com"])
        mock_host_class.return_value = _make_host([{"name": "ok.com"}])
        mock_dns_provider = _make_dns_provider()
        mock_dns_class.return_value = mock_dns_provider

        result = runner.invoke(sync, ["ok.com", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data[0]["actions"] == []
        assert data[0]["skipped"] is None
        mock_dns_provider.configure_dns.assert_not_called()

    @patch("mimeo.config.Config.load")
    @patch(f"{_SYNC}.GitHubHost")
    @patch(f"{_SYNC}.PorkbunRegistrar")
    @patch(f"{_SYNC}.PorkbunDNSProvider")
    def test_missing_dns_applied(
        self,
        mock_dns_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        mock_config_load.return_value = mock_config
        mock_registrar_class.return_value = _make_registrar(["drifty.com"])
        mock_host_class.return_value = _make_host([{"name": "drifty.com"}])
        mock_dns_provider = _make_dns_provider(
            missing=[{"type": "A", "name": "@", "content": "185.199.108.153"}]
        )
        mock_dns_class.return_value = mock_dns_provider

        result = runner.invoke(sync, ["drifty.com", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert any("DNS record" in a for a in data[0]["actions"])
        mock_dns_provider.configure_dns.assert_called_once()

    @patch("mimeo.config.Config.load")
    @patch(f"{_SYNC}.GitHubHost")
    @patch(f"{_SYNC}.PorkbunRegistrar")
    @patch(f"{_SYNC}.PorkbunDNSProvider")
    def test_fixable_https_enabled(
        self,
        mock_dns_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        mock_config_load.return_value = mock_config
        mock_registrar_class.return_value = _make_registrar(["fix.com"])
        mock_host = _make_host([{"name": "fix.com"}], health_state="fixable")
        mock_host_class.return_value = mock_host
        mock_dns_class.return_value = _make_dns_provider()

        result = runner.invoke(sync, ["fix.com", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert any("HTTPS" in a for a in data[0]["actions"])
        mock_host.enable_https_enforcement.assert_called_once_with("testorg/fix.com")

    @patch("mimeo.config.Config.load")
    @patch(f"{_SYNC}.GitHubHost")
    @patch(f"{_SYNC}.PorkbunRegistrar")
    @patch(f"{_SYNC}.PorkbunDNSProvider")
    def test_dry_run_makes_no_changes(
        self,
        mock_dns_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        mock_config_load.return_value = mock_config
        mock_registrar_class.return_value = _make_registrar(["drifty.com"])
        mock_host = _make_host([{"name": "drifty.com"}], health_state="fixable")
        mock_host_class.return_value = mock_host
        mock_dns_provider = _make_dns_provider(
            missing=[{"type": "A", "name": "@", "content": "185.199.108.153"}]
        )
        mock_dns_class.return_value = mock_dns_provider

        result = runner.invoke(sync, ["drifty.com", "--dry-run", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert any(a.startswith("would ") for a in data[0]["actions"])
        assert len(data[0]["actions"]) == 2
        mock_dns_provider.configure_dns.assert_not_called()
        mock_host.enable_https_enforcement.assert_not_called()

    @patch("mimeo.config.Config.load")
    @patch(f"{_SYNC}.GitHubHost")
    @patch(f"{_SYNC}.PorkbunRegistrar")
    @patch(f"{_SYNC}.PorkbunDNSProvider")
    def test_skips(
        self,
        mock_dns_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        """Unregistered domains, repo-less domains, and NS mismatches skip."""
        mock_config_load.return_value = mock_config
        mock_registrar_class.return_value = _make_registrar(
            ["norepo.com", "badns.com"], ns_ok=False
        )
        mock_host_class.return_value = _make_host([{"name": "badns.com"}])
        mock_dns_provider = _make_dns_provider()
        mock_dns_class.return_value = mock_dns_provider

        result = runner.invoke(
            sync,
            ["unregistered.com", "norepo.com", "badns.com", "--format", "json"],
        )

        assert result.exit_code == 0
        data = {r["domain"]: r for r in json.loads(result.stdout)}
        assert "not in Porkbun account" in data["unregistered.com"]["skipped"]
        assert "no repo" in data["norepo.com"]["skipped"]
        assert "--reset-nameservers" in data["badns.com"]["skipped"]
        mock_dns_provider.configure_dns.assert_not_called()

    @patch("mimeo.config.Config.load")
    @patch(f"{_SYNC}.GitHubHost")
    @patch(f"{_SYNC}.PorkbunRegistrar")
    @patch(f"{_SYNC}.PorkbunDNSProvider")
    def test_reset_nameservers_flag(
        self,
        mock_dns_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        mock_config_load.return_value = mock_config
        registrar = _make_registrar(["badns.com"], ns_ok=False)
        mock_registrar_class.return_value = registrar
        mock_host_class.return_value = _make_host([{"name": "badns.com"}])
        mock_dns_class.return_value = _make_dns_provider()

        result = runner.invoke(
            sync, ["badns.com", "--reset-nameservers", "--format", "json"]
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert any("nameservers" in a for a in data[0]["actions"])
        registrar.update_nameservers.assert_called_once_with("badns.com")

    @patch("mimeo.config.Config.load")
    @patch(f"{_SYNC}.GitHubHost")
    @patch(f"{_SYNC}.PorkbunRegistrar")
    @patch(f"{_SYNC}.PorkbunDNSProvider")
    def test_all_targets_fleet_union(
        self,
        mock_dns_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        mock_config_load.return_value = mock_config
        mock_registrar_class.return_value = _make_registrar(["a.com", "b.com"])
        mock_host_class.return_value = _make_host([{"name": "b.com"}, {"name": "c.com"}])
        mock_dns_class.return_value = _make_dns_provider()

        result = runner.invoke(sync, ["--all", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert [r["domain"] for r in data] == ["a.com", "b.com", "c.com"]

    @patch("mimeo.config.Config.load")
    @patch(f"{_SYNC}.GitHubHost")
    @patch(f"{_SYNC}.PorkbunRegistrar")
    @patch(f"{_SYNC}.PorkbunDNSProvider")
    def test_ignore_domains_trim_all_but_not_explicit(
        self,
        mock_dns_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
    ) -> None:
        """Config ignore list trims --all runs; explicit names override."""
        cfg = Config(
            porkbun_api_key="pk1_test",
            porkbun_secret="sk1_test",
            github_username="testorg",
            ignore_domains=["elsewhere.dev"],
        )
        mock_config_load.return_value = cfg
        mock_registrar_class.return_value = _make_registrar(
            ["managed.com", "elsewhere.dev"]
        )
        mock_host_class.return_value = _make_host([{"name": "managed.com"}])
        mock_dns_class.return_value = _make_dns_provider()

        fleet = runner.invoke(sync, ["--all", "--format", "json"])
        assert fleet.exit_code == 0
        assert [r["domain"] for r in json.loads(fleet.stdout)] == ["managed.com"]
        assert "ignored per config" in fleet.output

        explicit = runner.invoke(sync, ["elsewhere.dev", "--format", "json"])
        assert explicit.exit_code == 0
        data = json.loads(explicit.stdout)
        assert data[0]["domain"] == "elsewhere.dev"

    @patch("mimeo.config.Config.load")
    @patch(f"{_SYNC}.GitHubHost")
    @patch(f"{_SYNC}.PorkbunRegistrar")
    @patch(f"{_SYNC}.PorkbunDNSProvider")
    def test_partial_failure(
        self,
        mock_dns_class: Any,
        mock_registrar_class: Any,
        mock_host_class: Any,
        mock_config_load: Any,
        runner: CliRunner,
        mock_config: Config,
    ) -> None:
        mock_config_load.return_value = mock_config
        registrar = _make_registrar(["good.com", "bad.com"])

        def check_ns(domain: str) -> NameserverCheckResult:
            if domain == "bad.com":
                raise RegistrarError("Failed to communicate with Porkbun API: HTTP 503")
            return NameserverCheckResult(
                ok=True, actual=["curitiba.ns.porkbun.com"], expected=[]
            )

        registrar.check_nameservers.side_effect = check_ns
        mock_registrar_class.return_value = registrar
        mock_host_class.return_value = _make_host(
            [{"name": "good.com"}, {"name": "bad.com"}]
        )
        mock_dns_class.return_value = _make_dns_provider()

        result = runner.invoke(
            sync, ["good.com", "bad.com", "--format", "json", "--workers", "1"]
        )

        assert result.exit_code == EXIT_PARTIAL
        data = {r["domain"]: r for r in json.loads(result.stdout)}
        assert data["good.com"]["error"] is None
        assert "503" in data["bad.com"]["error"]
