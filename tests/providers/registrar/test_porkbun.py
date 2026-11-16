"""Tests for Porkbun registrar and DNS provider."""

from unittest.mock import Mock, patch

import pytest
import responses

from mimeo.exceptions import RegistrarError
from mimeo.models import DNSRecord
from mimeo.providers.host.github import GITHUB_PAGES_IPS
from mimeo.providers.registrar.porkbun import (
    PORKBUN_NAMESERVERS,
    PorkbunDNSProvider,
    PorkbunRegistrar,
)


# ---------------------------------------------------------------------------
# Shared retry tests (use PorkbunDNSProvider since it exercises _make_request)
# ---------------------------------------------------------------------------


class TestPorkbunRetry:
    """Tests for retry behaviour in _make_request."""

    @pytest.fixture
    def provider(self) -> PorkbunDNSProvider:
        return PorkbunDNSProvider(api_key="pk1_test_key", secret_key="sk1_test_secret")

    @patch("mimeo.utils.retry.time.sleep")
    @responses.activate
    def test_retries_on_429_then_succeeds(self, mock_sleep, provider: PorkbunDNSProvider) -> None:
        """A 429 response is retried and the eventual success is returned."""
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/retrieve/example.com",
            status=429,
        )
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/retrieve/example.com",
            json={"status": "SUCCESS", "records": []},
            status=200,
        )

        result = provider._make_request("/dns/retrieve/example.com", {})
        assert result["status"] == "SUCCESS"
        assert mock_sleep.call_count == 1

    @patch("mimeo.utils.retry.time.sleep")
    @responses.activate
    def test_no_retry_on_api_level_error(self, mock_sleep, provider: PorkbunDNSProvider) -> None:
        """A 200 response with status=ERROR (non-retryable) is not retried."""
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/retrieve/example.com",
            json={"status": "ERROR", "message": "Invalid authentication"},
            status=200,
        )

        with pytest.raises(RegistrarError) as exc_info:
            provider._make_request("/dns/retrieve/example.com", {})

        assert "Invalid authentication" in str(exc_info.value)
        assert len(responses.calls) == 1
        mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# PorkbunRegistrar tests
# ---------------------------------------------------------------------------


class TestPorkbunRegistrar:
    """Tests for PorkbunRegistrar class."""

    @pytest.fixture
    def registrar(self) -> PorkbunRegistrar:
        return PorkbunRegistrar(api_key="pk1_test_key", secret_key="sk1_test_secret")

    def test_initialization(self) -> None:
        registrar = PorkbunRegistrar(api_key="pk1_test_key", secret_key="sk1_test_secret")
        assert registrar.api_key == "pk1_test_key"
        assert registrar.secret_key == "sk1_test_secret"
        assert registrar.client.base_url == "https://api-ipv4.porkbun.com/api/json/v3"

    def test_initialization_missing_credentials(self) -> None:
        with pytest.raises(RegistrarError) as exc_info:
            PorkbunRegistrar(api_key="", secret_key="sk1_test_secret")
        assert "required" in str(exc_info.value)

        with pytest.raises(RegistrarError) as exc_info:
            PorkbunRegistrar(api_key="pk1_test_key", secret_key="")
        assert "required" in str(exc_info.value)

    def test_context_manager(self) -> None:
        with PorkbunRegistrar(api_key="pk1_test", secret_key="sk1_test") as registrar:
            assert registrar.api_key == "pk1_test"

    @responses.activate
    def test_list_domains_success(self, registrar: PorkbunRegistrar) -> None:
        """list_domains returns domain list from /domain/listAll."""
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/domain/listAll",
            json={
                "status": "SUCCESS",
                "domains": [
                    {
                        "domain": "example.com",
                        "tld": "com",
                        "expireDate": "2027-01-01",
                        "autoRenew": "1",
                    },
                    {
                        "domain": "example.net",
                        "tld": "net",
                        "expireDate": "2027-06-01",
                        "autoRenew": "0",
                    },
                ],
            },
            status=200,
        )

        result = registrar.list_domains()
        assert len(result) == 2
        assert result[0]["domain"] == "example.com"
        assert result[1]["domain"] == "example.net"

    @responses.activate
    def test_list_domains_empty(self, registrar: PorkbunRegistrar) -> None:
        """list_domains returns empty list when account has no domains."""
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/domain/listAll",
            json={"status": "SUCCESS", "domains": []},
            status=200,
        )

        result = registrar.list_domains()
        assert result == []

    @responses.activate
    def test_list_domains_api_error(self, registrar: PorkbunRegistrar) -> None:
        """list_domains raises RegistrarError on API failure."""
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/domain/listAll",
            json={"status": "ERROR", "message": "Invalid authentication"},
            status=200,
        )

        with pytest.raises(RegistrarError, match="Invalid authentication"):
            registrar.list_domains()


# ---------------------------------------------------------------------------
# PorkbunDNSProvider tests
# ---------------------------------------------------------------------------


class TestPorkbunDNSProvider:
    """Tests for PorkbunDNSProvider class."""

    @pytest.fixture
    def provider(self) -> PorkbunDNSProvider:
        return PorkbunDNSProvider(api_key="pk1_test_key", secret_key="sk1_test_secret")

    def test_initialization(self) -> None:
        provider = PorkbunDNSProvider(api_key="pk1_test_key", secret_key="sk1_test_secret")
        assert provider.api_key == "pk1_test_key"
        assert provider.secret_key == "sk1_test_secret"
        assert provider.client.base_url == "https://api-ipv4.porkbun.com/api/json/v3"

    def test_initialization_missing_credentials(self) -> None:
        with pytest.raises(RegistrarError):
            PorkbunDNSProvider(api_key="", secret_key="sk1_test_secret")

    def test_auth_payload(self, provider: PorkbunDNSProvider) -> None:
        payload = provider._auth_payload()
        assert payload == {
            "apikey": "pk1_test_key",
            "secretapikey": "sk1_test_secret",
        }

    def test_context_manager(self) -> None:
        with PorkbunDNSProvider(api_key="pk1_test", secret_key="sk1_test") as provider:
            assert provider.api_key == "pk1_test"

    @responses.activate
    def test_make_request_success(self, provider: PorkbunDNSProvider) -> None:
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/retrieve/example.com",
            json={"status": "SUCCESS", "records": []},
            status=200,
        )
        result = provider._make_request("/dns/retrieve/example.com", {})
        assert result["status"] == "SUCCESS"

    @responses.activate
    def test_make_request_api_error(self, provider: PorkbunDNSProvider) -> None:
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/create/example.com",
            json={"status": "ERROR", "message": "Invalid domain"},
            status=200,
        )
        with pytest.raises(RegistrarError) as exc_info:
            provider._make_request("/dns/create/example.com", {})
        assert "Invalid domain" in str(exc_info.value)

    @responses.activate
    def test_get_domain_records(self, provider: PorkbunDNSProvider) -> None:
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/retrieve/example.com",
            json={
                "status": "SUCCESS",
                "records": [
                    {"id": "123", "type": "A", "name": "", "content": "1.2.3.4", "ttl": "600"},
                ],
            },
            status=200,
        )
        records = provider.get_domain_records("example.com")
        assert len(records) == 1
        assert records[0]["type"] == "A"

    @responses.activate
    def test_delete_record(self, provider: PorkbunDNSProvider) -> None:
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/delete/example.com/123",
            json={"status": "SUCCESS"},
            status=200,
        )
        provider._delete_record("example.com", "123")


# ---------------------------------------------------------------------------
# PORKBUN_NAMESERVERS constant
# ---------------------------------------------------------------------------


def test_porkbun_nameservers_constant() -> None:
    """PORKBUN_NAMESERVERS contains the four expected city names."""
    assert len(PORKBUN_NAMESERVERS) == 4
    for ns in PORKBUN_NAMESERVERS:
        assert ns.endswith(".ns.porkbun.com")


class TestRemoveDNSRecords:
    """Tests for remove_dns_records (the inverse of configure_dns)."""

    @pytest.fixture
    def provider(self) -> PorkbunDNSProvider:
        return PorkbunDNSProvider(api_key="pk1_test_key", secret_key="sk1_test_secret")

    @pytest.fixture
    def managed_records(self) -> list[DNSRecord]:
        return [DNSRecord(type="A", name="", content=ip, ttl=600) for ip in GITHUB_PAGES_IPS] + [
            DNSRecord(type="CNAME", name="www", content="testuser.github.io", ttl=600)
        ]


class TestMissingRecordPlan:
    """Tests for plan_missing_records / apply_record_plan (sync's D1 path)."""

    @pytest.fixture
    def provider(self) -> PorkbunDNSProvider:
        return PorkbunDNSProvider(api_key="pk1_test_key", secret_key="sk1_test_secret")

    @pytest.fixture
    def expected(self) -> list[DNSRecord]:
        return [DNSRecord(type="A", name="", content=ip, ttl=600) for ip in GITHUB_PAGES_IPS] + [
            DNSRecord(type="CNAME", name="www", content="testuser.github.io", ttl=600)
        ]

    def _live_correct(self) -> list[dict]:
        live = [
            {"id": f"a{i}", "type": "A", "name": "example.com", "content": ip}
            for i, ip in enumerate(GITHUB_PAGES_IPS)
        ]
        live.append(
            {"id": "c1", "type": "CNAME", "name": "www.example.com", "content": "testuser.github.io"}
        )
        return live


class TestPorkbunNewInterfaces:
    """The Registrar and DNSProvider methods added for 2.0."""

    def test_get_nameservers_reads_the_registrar_setting(self) -> None:
        registrar = PorkbunRegistrar("pk1_x", "sk1_x")
        with patch.object(registrar, "_make_request") as request:
            request.return_value = {"status": "SUCCESS", "ns": ["B.ns.example.", "a.ns.example"]}
            assert registrar.get_nameservers("example.com") == ["a.ns.example", "b.ns.example"]
        request.assert_called_once_with("/domain/getNs/example.com", {})

    def test_set_nameservers_sends_the_given_list(self) -> None:
        registrar = PorkbunRegistrar("pk1_x", "sk1_x")
        with patch.object(registrar, "_make_request") as request:
            registrar.set_nameservers("example.com", ["a.ns.cloudflare.com", "b.ns.cloudflare.com"])
        request.assert_called_once_with(
            "/domain/updateNs/example.com", {"ns": ["a.ns.cloudflare.com", "b.ns.cloudflare.com"]}
        )

    def test_dnssec_enabled(self) -> None:
        registrar = PorkbunRegistrar("pk1_x", "sk1_x")
        with patch.object(registrar, "_make_request") as request:
            request.return_value = {"status": "SUCCESS", "records": {"123": {"keyTag": "123"}}}
            assert registrar.dnssec_enabled("example.com")
            request.return_value = {"status": "SUCCESS", "records": {}}
            assert not registrar.dnssec_enabled("example.com")

    def test_serves_only_porkbun_nameservers(self) -> None:
        dns = PorkbunDNSProvider("pk1_x", "sk1_x")
        assert dns.serves(sorted(PORKBUN_NAMESERVERS))
        assert not dns.serves(["ada.ns.cloudflare.com"])
        assert not dns.serves([])

    def test_list_records_makes_names_relative_and_keeps_mx_priority(self) -> None:
        dns = PorkbunDNSProvider("pk1_x", "sk1_x")
        raw = [
            {"id": "1", "name": "example.com", "type": "A", "content": "1.2.3.4", "ttl": "600", "prio": "0"},
            {"id": "2", "name": "www.example.com", "type": "CNAME", "content": "x.github.io", "ttl": "600", "prio": None},
            {"id": "3", "name": "example.com", "type": "MX", "content": "mx.example.net", "ttl": "600", "prio": "10"},
        ]
        with patch.object(dns, "get_domain_records", return_value=raw):
            records = dns.list_records("example.com")
        assert [(r.type, r.name, r.priority, r.id) for r in records] == [
            ("A", "", None, "1"), ("CNAME", "www", None, "2"), ("MX", "", 10, "3"),
        ]

    def test_add_record_raises_ttl_to_porkbun_minimum_and_sends_priority(self) -> None:
        dns = PorkbunDNSProvider("pk1_x", "sk1_x")
        with patch.object(dns, "_make_request") as request:
            dns.add_record("example.com", DNSRecord(type="MX", name="", content="mx.example.net", ttl=1, priority=10))
        request.assert_called_once_with(
            "/dns/create/example.com",
            {"type": "MX", "name": "", "content": "mx.example.net", "ttl": "600", "prio": "10"},
        )

    def test_delete_record_uses_the_record_id(self) -> None:
        dns = PorkbunDNSProvider("pk1_x", "sk1_x")
        with patch.object(dns, "_make_request") as request:
            dns.delete_record("example.com", DNSRecord(type="A", name="", content="1.2.3.4", id="42"))
        request.assert_called_once_with("/dns/delete/example.com/42", {})
