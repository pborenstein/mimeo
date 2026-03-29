"""Tests for Porkbun registrar and DNS provider."""

from unittest.mock import Mock, patch

import pytest
import responses
import dns.resolver

from mimeo.exceptions import RegistrarError, DNSError
from mimeo.models import DNSRecord, NameserverCheckResult
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
    def test_retries_on_503_then_succeeds(self, mock_sleep, provider: PorkbunDNSProvider) -> None:
        """A 503 response is retried and the eventual success is returned."""
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/create/example.com",
            status=503,
        )
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/create/example.com",
            json={"status": "SUCCESS", "id": "123"},
            status=200,
        )

        record = DNSRecord(type="A", name="", content="1.2.3.4", ttl=600)
        provider._create_record("example.com", record)
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

    @patch("mimeo.providers.registrar.porkbun._lookup_nameservers")
    def test_check_nameservers_ok(self, mock_lookup: Mock, registrar: PorkbunRegistrar) -> None:
        """check_nameservers returns ok=True when NS matches Porkbun."""
        mock_lookup.return_value = sorted(PORKBUN_NAMESERVERS)

        result = registrar.check_nameservers("example.com")

        assert isinstance(result, NameserverCheckResult)
        assert result.ok is True
        assert result.actual == sorted(PORKBUN_NAMESERVERS)
        assert result.expected == sorted(PORKBUN_NAMESERVERS)
        mock_lookup.assert_called_once_with("example.com")

    @patch("mimeo.providers.registrar.porkbun._lookup_nameservers")
    def test_check_nameservers_mismatch(
        self, mock_lookup: Mock, registrar: PorkbunRegistrar
    ) -> None:
        """check_nameservers returns ok=False when NS points elsewhere."""
        cloudflare_ns = ["ava.ns.cloudflare.com", "ken.ns.cloudflare.com"]
        mock_lookup.return_value = cloudflare_ns

        result = registrar.check_nameservers("example.com")

        assert result.ok is False
        assert result.actual == cloudflare_ns
        assert result.expected == sorted(PORKBUN_NAMESERVERS)

    @patch("mimeo.providers.registrar.porkbun._lookup_nameservers")
    def test_check_nameservers_empty(self, mock_lookup: Mock, registrar: PorkbunRegistrar) -> None:
        """check_nameservers returns ok=False when DNS lookup returns nothing."""
        mock_lookup.return_value = []

        result = registrar.check_nameservers("example.com")

        assert result.ok is False
        assert result.actual == []

    @responses.activate
    def test_update_nameservers_success(self, registrar: PorkbunRegistrar) -> None:
        """update_nameservers calls /domain/updateNs with Porkbun NS list."""
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/domain/updateNs/example.com",
            json={"status": "SUCCESS"},
            status=200,
        )

        registrar.update_nameservers("example.com")

        assert len(responses.calls) == 1
        import json

        payload = json.loads(responses.calls[0].request.body)
        assert payload["ns"] == PORKBUN_NAMESERVERS

    @responses.activate
    def test_update_nameservers_api_error(self, registrar: PorkbunRegistrar) -> None:
        """update_nameservers raises RegistrarError on API failure."""
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/domain/updateNs/example.com",
            json={"status": "ERROR", "message": "Domain not found"},
            status=200,
        )

        with pytest.raises(RegistrarError, match="Domain not found"):
            registrar.update_nameservers("example.com")

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
        records = provider._get_domain_records("example.com")
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

    @responses.activate
    def test_create_record(self, provider: PorkbunDNSProvider) -> None:
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/create/example.com",
            json={"status": "SUCCESS", "id": "456"},
            status=200,
        )
        record = DNSRecord(type="A", name="", content="1.2.3.4", ttl=600)
        provider._create_record("example.com", record)

        assert len(responses.calls) == 1
        request_body = responses.calls[0].request.body
        assert b'"type": "A"' in request_body
        assert b'"content": "1.2.3.4"' in request_body

    @responses.activate
    def test_configure_dns(self, provider: PorkbunDNSProvider) -> None:
        """Test configuring DNS records."""
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/retrieve/example.com",
            json={
                "status": "SUCCESS",
                "records": [
                    {"id": "123", "type": "A", "name": "", "content": "5.6.7.8"},
                ],
            },
            status=200,
        )
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/delete/example.com/123",
            json={"status": "SUCCESS"},
            status=200,
        )
        for _ in range(5):
            responses.add(
                responses.POST,
                "https://api-ipv4.porkbun.com/api/json/v3/dns/create/example.com",
                json={"status": "SUCCESS", "id": "456"},
                status=200,
            )

        records = [DNSRecord(type="A", name="", content=ip, ttl=600) for ip in GITHUB_PAGES_IPS] + [
            DNSRecord(type="CNAME", name="www", content="testuser.github.io", ttl=600)
        ]
        provider.configure_dns("example.com", records)

        # 1 retrieve + 1 delete + 5 creates = 7 total
        assert len(responses.calls) == 7

    @responses.activate
    def test_configure_dns_no_conflicts(self, provider: PorkbunDNSProvider) -> None:
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/retrieve/example.com",
            json={
                "status": "SUCCESS",
                "records": [
                    {"id": "999", "type": "TXT", "name": "_verification", "content": "token"},
                ],
            },
            status=200,
        )
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/create/example.com",
            json={"status": "SUCCESS", "id": "456"},
            status=200,
        )

        record = DNSRecord(type="A", name="", content="1.2.3.4", ttl=600)
        provider.configure_dns("example.com", [record])

        # 1 retrieve + 0 deletes + 1 create = 2 total
        assert len(responses.calls) == 2

    @patch("mimeo.providers.registrar.porkbun.dns.resolver.Resolver")
    def test_verify_dns_success(
        self, mock_resolver_class: Mock, provider: PorkbunDNSProvider
    ) -> None:
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver

        mock_answer = Mock()
        mock_answer.__str__ = Mock(return_value="1.2.3.4")
        mock_resolver.resolve.return_value = [mock_answer]

        record = DNSRecord(type="A", name="", content="1.2.3.4", ttl=600)
        result = provider.verify_dns("example.com", [record], max_attempts=1)

        assert result is True
        mock_resolver.resolve.assert_called_once_with("example.com", "A")

    @patch("mimeo.providers.registrar.porkbun.dns.resolver.Resolver")
    def test_verify_dns_with_subdomain(
        self, mock_resolver_class: Mock, provider: PorkbunDNSProvider
    ) -> None:
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver

        mock_answer = Mock()
        mock_answer.__str__ = Mock(return_value="target.example.com.")
        mock_resolver.resolve.return_value = [mock_answer]

        record = DNSRecord(type="CNAME", name="www", content="target.example.com", ttl=600)
        result = provider.verify_dns("example.com", [record], max_attempts=1)

        assert result is True
        mock_resolver.resolve.assert_called_once_with("www.example.com", "CNAME")

    @patch("mimeo.providers.registrar.porkbun.dns.resolver.Resolver")
    def test_verify_dns_not_found(
        self, mock_resolver_class: Mock, provider: PorkbunDNSProvider
    ) -> None:
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.resolve.side_effect = dns.resolver.NXDOMAIN()

        record = DNSRecord(type="A", name="", content="1.2.3.4", ttl=600)
        result = provider.verify_dns("example.com", [record], max_attempts=1, delay=0)

        assert result is False

    @patch("mimeo.providers.registrar.porkbun.dns.resolver.Resolver")
    @patch("mimeo.providers.registrar.porkbun.time.sleep")
    def test_verify_dns_retry(
        self,
        mock_sleep: Mock,
        mock_resolver_class: Mock,
        provider: PorkbunDNSProvider,
    ) -> None:
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver

        mock_answer = Mock()
        mock_answer.__str__ = Mock(return_value="1.2.3.4")
        mock_resolver.resolve.side_effect = [
            dns.resolver.NXDOMAIN(),
            [mock_answer],
        ]

        record = DNSRecord(type="A", name="", content="1.2.3.4", ttl=600)
        result = provider.verify_dns("example.com", [record], max_attempts=2, delay=1)

        assert result is True
        assert mock_resolver.resolve.call_count == 2
        mock_sleep.assert_called_once_with(1)

    @patch("mimeo.providers.registrar.porkbun.dns.resolver.Resolver")
    def test_verify_dns_wrong_content(
        self, mock_resolver_class: Mock, provider: PorkbunDNSProvider
    ) -> None:
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver

        mock_answer = Mock()
        mock_answer.__str__ = Mock(return_value="9.9.9.9")
        mock_resolver.resolve.return_value = [mock_answer]

        record = DNSRecord(type="A", name="", content="1.2.3.4", ttl=600)
        result = provider.verify_dns("example.com", [record], max_attempts=1)

        assert result is False

    @patch("mimeo.providers.registrar.porkbun.dns.resolver.Resolver")
    def test_verify_dns_unexpected_error(
        self, mock_resolver_class: Mock, provider: PorkbunDNSProvider
    ) -> None:
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.resolve.side_effect = Exception("Unexpected error")

        record = DNSRecord(type="A", name="", content="1.2.3.4", ttl=600)

        with pytest.raises(DNSError) as exc_info:
            provider.verify_dns("example.com", [record], max_attempts=1)

        assert "unexpectedly" in str(exc_info.value)

    def test_normalize_record_name_apex(self, provider: PorkbunDNSProvider) -> None:
        domain = "example.com"
        assert provider._normalize_record_name("", domain) == ""
        assert provider._normalize_record_name("@", domain) == ""
        assert provider._normalize_record_name("example.com", domain) == ""

    def test_normalize_record_name_subdomain(self, provider: PorkbunDNSProvider) -> None:
        domain = "example.com"
        assert provider._normalize_record_name("www", domain) == "www"
        assert provider._normalize_record_name("api", domain) == "api"
        assert provider._normalize_record_name("www.example.com", domain) == "www"
        assert provider._normalize_record_name("api.example.com", domain) == "api"

    @responses.activate
    def test_configure_dns_error_handling(self, provider: PorkbunDNSProvider) -> None:
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/retrieve/example.com",
            json={"status": "ERROR", "message": "Domain not found"},
            status=200,
        )
        record = DNSRecord(type="A", name="", content="1.2.3.4", ttl=600)
        with pytest.raises(RegistrarError) as exc_info:
            provider.configure_dns("example.com", [record])
        assert "Domain not found" in str(exc_info.value)

    @responses.activate
    def test_configure_dns_apex_with_full_domain_name(self, provider: PorkbunDNSProvider) -> None:
        """Apex records are matched when API returns full domain name."""
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/retrieve/example.com",
            json={
                "status": "SUCCESS",
                "records": [
                    {"id": "123", "type": "A", "name": "example.com", "content": "5.6.7.8"},
                    {
                        "id": "124",
                        "type": "ALIAS",
                        "name": "example.com",
                        "content": "pixie.porkbun.com",
                    },
                ],
            },
            status=200,
        )
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/delete/example.com/123",
            json={"status": "SUCCESS"},
            status=200,
        )
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/delete/example.com/124",
            json={"status": "SUCCESS"},
            status=200,
        )
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/create/example.com",
            json={"status": "SUCCESS", "id": "456"},
            status=200,
        )

        record = DNSRecord(type="A", name="", content="1.2.3.4", ttl=600)
        provider.configure_dns("example.com", [record])

        # 1 retrieve + 2 deletes (A + ALIAS) + 1 create = 4 total
        assert len(responses.calls) == 4

    @responses.activate
    def test_configure_dns_deletes_parking_records(self, provider: PorkbunDNSProvider) -> None:
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/retrieve/example.com",
            json={
                "status": "SUCCESS",
                "records": [
                    {
                        "id": "parking-1",
                        "type": "ALIAS",
                        "name": "example.com",
                        "content": "pixie.porkbun.com",
                    },
                    {
                        "id": "parking-2",
                        "type": "CNAME",
                        "name": "www.example.com",
                        "content": "pixie.porkbun.com",
                    },
                ],
            },
            status=200,
        )
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/delete/example.com/parking-1",
            json={"status": "SUCCESS"},
            status=200,
        )
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/delete/example.com/parking-2",
            json={"status": "SUCCESS"},
            status=200,
        )
        for _ in range(5):
            responses.add(
                responses.POST,
                "https://api-ipv4.porkbun.com/api/json/v3/dns/create/example.com",
                json={"status": "SUCCESS", "id": "new-record"},
                status=200,
            )

        records = [DNSRecord(type="A", name="", content=ip, ttl=600) for ip in GITHUB_PAGES_IPS] + [
            DNSRecord(type="CNAME", name="www", content="testuser.github.io", ttl=600)
        ]
        provider.configure_dns("example.com", records)

        # 1 retrieve + 2 deletes + 5 creates = 8 total
        assert len(responses.calls) == 8

    @responses.activate
    def test_check_dns_drift_ok(self, provider: PorkbunDNSProvider) -> None:
        """check_dns_drift returns ok when all expected records are present."""
        expected = [
            DNSRecord(type="A", name="", content=ip, ttl=600) for ip in GITHUB_PAGES_IPS
        ] + [DNSRecord(type="CNAME", name="www", content="testuser.github.io", ttl=600)]

        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/retrieve/example.com",
            json={
                "status": "SUCCESS",
                "records": [
                    {"id": str(i), "type": "A", "name": "", "content": ip, "ttl": "600"}
                    for i, ip in enumerate(GITHUB_PAGES_IPS)
                ]
                + [
                    {
                        "id": "10",
                        "type": "CNAME",
                        "name": "www",
                        "content": "testuser.github.io",
                        "ttl": "600",
                    },
                ],
            },
            status=200,
        )

        result = provider.check_dns_drift("example.com", expected)
        assert result["status"] == "ok"
        assert result["missing"] == []

    @responses.activate
    def test_check_dns_drift_missing(self, provider: PorkbunDNSProvider) -> None:
        expected = [
            DNSRecord(type="A", name="", content=ip, ttl=600) for ip in GITHUB_PAGES_IPS
        ] + [DNSRecord(type="CNAME", name="www", content="testuser.github.io", ttl=600)]

        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/retrieve/example.com",
            json={
                "status": "SUCCESS",
                "records": [
                    {
                        "id": "1",
                        "type": "A",
                        "name": "",
                        "content": GITHUB_PAGES_IPS[0],
                        "ttl": "600",
                    },
                ],
            },
            status=200,
        )

        result = provider.check_dns_drift("example.com", expected)
        assert result["status"] == "missing"
        assert len(result["missing"]) > 0

    @responses.activate
    def test_check_dns_drift_extra(self, provider: PorkbunDNSProvider) -> None:
        expected = [DNSRecord(type="A", name="", content=GITHUB_PAGES_IPS[0], ttl=600)]

        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/retrieve/example.com",
            json={
                "status": "SUCCESS",
                "records": [
                    {
                        "id": "1",
                        "type": "A",
                        "name": "",
                        "content": GITHUB_PAGES_IPS[0],
                        "ttl": "600",
                    },
                    {"id": "2", "type": "A", "name": "", "content": "1.2.3.4", "ttl": "600"},
                ],
            },
            status=200,
        )

        result = provider.check_dns_drift("example.com", expected)
        assert result["status"] == "drift"
        assert len(result["extra"]) > 0

    @responses.activate
    def test_configure_dns_deletes_alias_when_creating_a_records(
        self, provider: PorkbunDNSProvider
    ) -> None:
        """ALIAS records at apex are deleted when creating A records."""
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/retrieve/example.com",
            json={
                "status": "SUCCESS",
                "records": [
                    {
                        "id": "alias-123",
                        "type": "ALIAS",
                        "name": "example.com",
                        "content": "uixie.porkbun.com",
                    },
                ],
            },
            status=200,
        )
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/delete/example.com/alias-123",
            json={"status": "SUCCESS"},
            status=200,
        )
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/create/example.com",
            json={"status": "SUCCESS", "id": "a-456"},
            status=200,
        )

        record = DNSRecord(type="A", name="", content="1.2.3.4", ttl=600)
        provider.configure_dns("example.com", [record])

        # 1 retrieve + 1 delete (ALIAS) + 1 create (A) = 3 total
        assert len(responses.calls) == 3


# ---------------------------------------------------------------------------
# PORKBUN_NAMESERVERS constant
# ---------------------------------------------------------------------------


def test_porkbun_nameservers_constant() -> None:
    """PORKBUN_NAMESERVERS contains the four expected city names."""
    assert len(PORKBUN_NAMESERVERS) == 4
    for ns in PORKBUN_NAMESERVERS:
        assert ns.endswith(".ns.porkbun.com")
