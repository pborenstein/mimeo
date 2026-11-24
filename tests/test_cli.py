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
    _check_pages_ips,
    _check_python_version,
    create,
    delete,
    doctor,
    main,
)
from mimeo.cli._processing import set_cli_overrides, set_log_format

from mimeo.config import Config
from mimeo.exceptions import ConfigurationError, HostError, RegistrarError
from mimeo.models import DNSRecord


# Patch target prefixes for each submodule
_CREATE = "mimeo.cli.create"
_DOCTOR = "mimeo.cli.doctor"
_PROCESSING = "mimeo.cli._processing"


@pytest.fixture
def runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture(autouse=True)
def _clean_cli_state() -> None:
    """Reset --template-org/--deploy-org/--log-format module state around every test.

    Without the log-format reset, a test invoking ``main --log-format json``
    leaves the global at "json" and every later direct-command invocation
    renders JSON instead of text.
    """
    set_cli_overrides(None, None)
    set_log_format("text")
    yield
    set_cli_overrides(None, None)
    set_log_format("text")


@pytest.fixture(autouse=True)
def _credential_checks_off_network() -> Any:
    """Keep doctor's provider credential checks off the network."""
    with patch(f"{_DOCTOR}._check_porkbun_credentials", return_value=(True, "accepted", "")), patch(
        f"{_DOCTOR}._check_cloudflare_credentials", return_value=(True, "active", "")
    ), patch(f"{_DOCTOR}._check_cloudflare_settings", return_value=(True, "readable", "")):
        yield


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
        assert "Connect domains to the sites that serve them" in result.output

    def test_main_version(self, runner: CliRunner) -> None:
        """Test version flag."""
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "Mimeo" in result.output


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
        assert "cannot write" in fix

    @patch("mimeo.providers.registrar.porkbun.lookup_nameservers")
    def test_check_nameservers_cloudflare(self, mock_lookup: Any) -> None:
        """Cloudflare passes when a token is configured and fails without one."""
        mock_lookup.return_value = ["abby.ns.cloudflare.com", "valentin.ns.cloudflare.com"]
        assert _check_nameservers("example.com", cloudflare_configured=True) == (True, "cloudflare", "")
        ok, detail, fix = _check_nameservers("example.com")
        assert ok is False
        assert "[cloudflare]" in fix

    @patch("mimeo.providers.registrar.porkbun.lookup_nameservers")
    def test_check_nameservers_empty(self, mock_lookup: Any) -> None:
        """_check_nameservers fails when no NS records are found."""
        mock_lookup.return_value = []
        ok, detail, fix = _check_nameservers("example.com")
        assert ok is False
        assert "no NS records" in detail


class TestCheckPagesIps:
    """Tests for the GitHub Pages IP doctor check."""

    _META = (
        '["192.30.252.153/32","192.30.252.154/32","185.199.108.153/32",'
        '"185.199.109.153/32","185.199.110.153/32","185.199.111.153/32",'
        '"2606:50c0:8000::153/128","2606:50c0:8001::153/128",'
        '"2606:50c0:8002::153/128","2606:50c0:8003::153/128"]\n'
    )

    def _run(self, stdout: str, returncode: int = 0) -> MagicMock:
        result = MagicMock()
        result.returncode = returncode
        result.stdout = stdout
        result.stderr = ""
        return result

    def test_all_listed(self) -> None:
        """Passes when every hardcoded IP is in GitHub's meta pages list."""
        with patch(f"{_DOCTOR}.subprocess.run", return_value=self._run(self._META)):
            ok, detail, fix = _check_pages_ips()
        assert ok is True
        assert "8" in detail
        assert fix == ""

    def test_ip_dropped(self) -> None:
        """Fails and names the IP when GitHub no longer lists it."""
        meta = '["185.199.108.153/32","185.199.109.153/32","185.199.110.153/32"]'
        with patch(f"{_DOCTOR}.subprocess.run", return_value=self._run(meta)):
            ok, detail, fix = _check_pages_ips()
        assert ok is False
        assert "185.199.111.153" in detail
        assert "GITHUB_PAGES_IPS" in fix

    def test_fetch_fails(self) -> None:
        """Fails when gh api meta returns non-zero."""
        with patch(f"{_DOCTOR}.subprocess.run", return_value=self._run("", returncode=1)):
            ok, detail, fix = _check_pages_ips()
        assert ok is False
        assert "api.github.com/meta" in detail

    def test_bad_json(self) -> None:
        """Fails when the response is not a JSON list."""
        with patch(f"{_DOCTOR}.subprocess.run", return_value=self._run("not json")):
            ok, detail, fix = _check_pages_ips()
        assert ok is False
        assert "api.github.com/meta" in detail

    def test_gh_missing(self) -> None:
        """Fails when gh is not installed."""
        with patch(f"{_DOCTOR}.subprocess.run", side_effect=FileNotFoundError):
            ok, detail, fix = _check_pages_ips()
        assert ok is False
        assert "cli.github.com" in fix


class TestDoctorCommand:
    """Tests for the doctor CLI command."""

    @pytest.fixture(autouse=True)
    def _pages_ips_ok(self) -> Any:
        """Keep the Pages IP check off the network in command tests."""
        with patch(f"{_DOCTOR}._check_pages_ips", return_value=(True, "4 listed", "")):
            yield

    def test_doctor_reports_dropped_pages_ip(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Doctor exits non-zero when a Pages IP check fails."""
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(
            '[porkbun]\napi_key = "pk1_test"\nsecret_key = "sk1_test"\n'
            '[github]\ndefault_org = "testuser"\n'
        )

        def fake_run(cmd: list, **kwargs: Any) -> MagicMock:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "gh version 2.40.0\n  - Token scopes: 'repo', 'workflow'\n"
            mock_result.stderr = ""
            return mock_result

        failing = (False, "not listed: 185.199.111.153", "Update GITHUB_PAGES_IPS")
        with patch(f"{_DOCTOR}.subprocess.run", side_effect=fake_run), patch(
            f"{_DOCTOR}._check_pages_ips", return_value=failing
        ):
            result = runner.invoke(doctor, ["--config", str(cfg_file)])

        assert result.exit_code != 0
        assert "Pages IPs" in result.output
        assert "185.199.111.153" in result.output

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
        mock_ns.assert_called_once_with("example.com", False)

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

class TestLogFormatOption:
    """Tests for --log-format json option."""

    def test_log_format_in_main_help(self, runner: CliRunner) -> None:
        """--log-format appears in main help."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "--log-format" in result.output

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

        with patch(f"{_DOCTOR}.subprocess.run", side_effect=fake_run), patch(
            f"{_DOCTOR}._check_pages_ips", return_value=(True, "4 listed", "")
        ):
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




# Captured at import, before the autouse fixture replaces it.
_REAL_CLOUDFLARE_CHECK = __import__(
    "mimeo.cli.doctor", fromlist=["_check_cloudflare_credentials"]
)._check_cloudflare_credentials


class TestCloudflareCredentialCheck:
    """doctor verifies account-owned tokens through the account endpoint."""

    def _cfg(self, account_id: str | None) -> Config:
        return Config(
            porkbun_api_key="pk1_test",
            porkbun_secret="sk1_test",
            github_username="testuser",
            cloudflare_api_token="tok",
            cloudflare_account_id=account_id,
        )

    def _check(self, cfg: Config, side_effect: Any) -> tuple[Any, MagicMock]:
        from mimeo.providers.dns.cloudflare import CloudflareDNS

        with patch.object(CloudflareDNS, "_call", side_effect=side_effect) as call:
            return _REAL_CLOUDFLARE_CHECK(cfg), call

    def test_account_endpoint_first_when_account_id_is_set(self) -> None:
        (ok, detail, _), call = self._check(self._cfg("acct"), [{"result": {"status": "active"}}])
        assert (ok, detail) == (True, "active")
        assert call.call_args.args == ("GET", "/accounts/acct/tokens/verify")

    def test_falls_back_to_user_endpoint(self) -> None:
        from mimeo.exceptions import APIError

        (ok, _, _), call = self._check(
            self._cfg("acct"), [APIError("HTTP 401", status_code=401), {"result": {"status": "active"}}]
        )
        assert ok is True
        assert call.call_args.args == ("GET", "/user/tokens/verify")

    def test_inactive_token_fails(self) -> None:
        (ok, detail, _), _ = self._check(self._cfg(None), [{"result": {"status": "expired"}}])
        assert (ok, detail) == (False, "token is expired")
