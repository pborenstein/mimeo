"""Tests for Porkbun registrar provider."""

from unittest.mock import Mock, patch

import pytest
import responses
import dns.resolver

from mimeo.exceptions import RegistrarError, DNSError
from mimeo.models import DNSRecord
from mimeo.providers.registrar.porkbun import PorkbunRegistrar, GITHUB_PAGES_IPS


class TestPorkbunRetry:
    """Tests for retry behaviour in PorkbunRegistrar._make_request."""

    @pytest.fixture
    def registrar(self) -> PorkbunRegistrar:
        return PorkbunRegistrar(api_key="pk1_test_key", secret_key="sk1_test_secret")

    @patch("mimeo.utils.retry.time.sleep")
    @responses.activate
    def test_retries_on_429_then_succeeds(self, mock_sleep, registrar: PorkbunRegistrar) -> None:
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

        result = registrar._make_request("/dns/retrieve/example.com", {})
        assert result["status"] == "SUCCESS"
        assert mock_sleep.call_count == 1

    @patch("mimeo.utils.retry.time.sleep")
    @responses.activate
    def test_retries_on_503_then_succeeds(self, mock_sleep, registrar: PorkbunRegistrar) -> None:
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

        from mimeo.models import DNSRecord
        record = DNSRecord(type="A", name="", content="1.2.3.4", ttl=600)
        registrar._create_record("example.com", record)
        assert mock_sleep.call_count == 1

    @patch("mimeo.utils.retry.time.sleep")
    @responses.activate
    def test_no_retry_on_api_level_error(self, mock_sleep, registrar: PorkbunRegistrar) -> None:
        """A 200 response with status=ERROR (non-retryable) is not retried."""
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/retrieve/example.com",
            json={"status": "ERROR", "message": "Invalid authentication"},
            status=200,
        )

        with pytest.raises(RegistrarError) as exc_info:
            registrar._make_request("/dns/retrieve/example.com", {})

        assert "Invalid authentication" in str(exc_info.value)
        # Only one HTTP call — no retry on application-level errors
        assert len(responses.calls) == 1
        mock_sleep.assert_not_called()


class TestPorkbunRegistrar:
    """Tests for PorkbunRegistrar class."""

    @pytest.fixture
    def registrar(self) -> PorkbunRegistrar:
        """Create Porkbun registrar for testing."""
        return PorkbunRegistrar(
            api_key="pk1_test_key",
            secret_key="sk1_test_secret",
        )

    def test_initialization(self) -> None:
        """Test Porkbun registrar initialization."""
        registrar = PorkbunRegistrar(
            api_key="pk1_test_key",
            secret_key="sk1_test_secret",
        )
        assert registrar.api_key == "pk1_test_key"
        assert registrar.secret_key == "sk1_test_secret"
        assert registrar.client.base_url == "https://api-ipv4.porkbun.com/api/json/v3"

    def test_initialization_missing_credentials(self) -> None:
        """Test that initialization fails without credentials."""
        with pytest.raises(RegistrarError) as exc_info:
            PorkbunRegistrar(api_key="", secret_key="sk1_test_secret")
        assert "required" in str(exc_info.value)

        with pytest.raises(RegistrarError) as exc_info:
            PorkbunRegistrar(api_key="pk1_test_key", secret_key="")
        assert "required" in str(exc_info.value)

    def test_auth_payload(self, registrar: PorkbunRegistrar) -> None:
        """Test authentication payload generation."""
        payload = registrar._auth_payload()
        assert payload == {
            "apikey": "pk1_test_key",
            "secretapikey": "sk1_test_secret",
        }

    @responses.activate
    def test_make_request_success(self, registrar: PorkbunRegistrar) -> None:
        """Test successful API request."""
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/retrieve/example.com",
            json={"status": "SUCCESS", "records": []},
            status=200,
        )

        result = registrar._make_request("/dns/retrieve/example.com", {})
        assert result["status"] == "SUCCESS"

    @responses.activate
    def test_make_request_api_error(self, registrar: PorkbunRegistrar) -> None:
        """Test API request with API error response."""
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/create/example.com",
            json={"status": "ERROR", "message": "Invalid domain"},
            status=200,
        )

        with pytest.raises(RegistrarError) as exc_info:
            registrar._make_request("/dns/create/example.com", {})

        assert "Invalid domain" in str(exc_info.value)

    @responses.activate
    def test_get_domain_records(self, registrar: PorkbunRegistrar) -> None:
        """Test retrieving domain records."""
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/retrieve/example.com",
            json={
                "status": "SUCCESS",
                "records": [
                    {
                        "id": "123",
                        "type": "A",
                        "name": "",
                        "content": "1.2.3.4",
                        "ttl": "600",
                    },
                ],
            },
            status=200,
        )

        records = registrar._get_domain_records("example.com")
        assert len(records) == 1
        assert records[0]["type"] == "A"

    @responses.activate
    def test_delete_record(self, registrar: PorkbunRegistrar) -> None:
        """Test deleting a DNS record."""
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/delete/example.com/123",
            json={"status": "SUCCESS"},
            status=200,
        )

        # Should not raise
        registrar._delete_record("example.com", "123")

    @responses.activate
    def test_create_record(self, registrar: PorkbunRegistrar) -> None:
        """Test creating a DNS record."""
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/create/example.com",
            json={"status": "SUCCESS", "id": "456"},
            status=200,
        )

        record = DNSRecord(type="A", name="", content="1.2.3.4", ttl=600)
        registrar._create_record("example.com", record)

        # Verify request was made with correct payload
        assert len(responses.calls) == 1
        request_body = responses.calls[0].request.body
        assert b'"type": "A"' in request_body
        assert b'"content": "1.2.3.4"' in request_body

    @responses.activate
    def test_configure_dns(self, registrar: PorkbunRegistrar) -> None:
        """Test configuring DNS records."""
        # Mock retrieving existing records
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/retrieve/example.com",
            json={
                "status": "SUCCESS",
                "records": [
                    {
                        "id": "123",
                        "type": "A",
                        "name": "",
                        "content": "5.6.7.8",
                    },
                ],
            },
            status=200,
        )

        # Mock deleting old record
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/delete/example.com/123",
            json={"status": "SUCCESS"},
            status=200,
        )

        # Mock creating new records (4 A records + 1 CNAME)
        for _ in range(5):
            responses.add(
                responses.POST,
                "https://api-ipv4.porkbun.com/api/json/v3/dns/create/example.com",
                json={"status": "SUCCESS", "id": "456"},
                status=200,
            )

        # Configure DNS with GitHub Pages records
        records = PorkbunRegistrar.github_pages_records("example.com", "testuser")
        registrar.configure_dns("example.com", records)

        # Verify API calls: 1 retrieve + 1 delete + 5 creates = 7 total
        assert len(responses.calls) == 7

    @responses.activate
    def test_configure_dns_no_conflicts(self, registrar: PorkbunRegistrar) -> None:
        """Test configuring DNS with no conflicting records."""
        # Mock retrieving existing records (no conflicts)
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/retrieve/example.com",
            json={
                "status": "SUCCESS",
                "records": [
                    {
                        "id": "999",
                        "type": "TXT",
                        "name": "_verification",
                        "content": "verification-token",
                    },
                ],
            },
            status=200,
        )

        # Mock creating new record
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/create/example.com",
            json={"status": "SUCCESS", "id": "456"},
            status=200,
        )

        record = DNSRecord(type="A", name="", content="1.2.3.4", ttl=600)
        registrar.configure_dns("example.com", [record])

        # Verify API calls: 1 retrieve + 0 deletes + 1 create = 2 total
        assert len(responses.calls) == 2

    @patch("mimeo.providers.registrar.porkbun.dns.resolver.Resolver")
    def test_verify_dns_success(
        self,
        mock_resolver_class: Mock,
        registrar: PorkbunRegistrar,
    ) -> None:
        """Test successful DNS verification."""
        # Mock DNS resolver
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver

        # Mock DNS response for A record
        mock_answer = Mock()
        mock_answer.__str__ = Mock(return_value="1.2.3.4")
        mock_resolver.resolve.return_value = [mock_answer]

        record = DNSRecord(type="A", name="", content="1.2.3.4", ttl=600)
        result = registrar.verify_dns("example.com", [record], max_attempts=1)

        assert result is True
        mock_resolver.resolve.assert_called_once_with("example.com", "A")

    @patch("mimeo.providers.registrar.porkbun.dns.resolver.Resolver")
    def test_verify_dns_with_subdomain(
        self,
        mock_resolver_class: Mock,
        registrar: PorkbunRegistrar,
    ) -> None:
        """Test DNS verification for subdomain."""
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver

        # Mock DNS response for CNAME
        mock_answer = Mock()
        mock_answer.__str__ = Mock(return_value="target.example.com.")
        mock_resolver.resolve.return_value = [mock_answer]

        record = DNSRecord(type="CNAME", name="www", content="target.example.com", ttl=600)
        result = registrar.verify_dns("example.com", [record], max_attempts=1)

        assert result is True
        mock_resolver.resolve.assert_called_once_with("www.example.com", "CNAME")

    @patch("mimeo.providers.registrar.porkbun.dns.resolver.Resolver")
    def test_verify_dns_not_found(
        self,
        mock_resolver_class: Mock,
        registrar: PorkbunRegistrar,
    ) -> None:
        """Test DNS verification when record not found."""
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.resolve.side_effect = dns.resolver.NXDOMAIN()

        record = DNSRecord(type="A", name="", content="1.2.3.4", ttl=600)
        result = registrar.verify_dns("example.com", [record], max_attempts=1, delay=0)

        assert result is False

    @patch("mimeo.providers.registrar.porkbun.dns.resolver.Resolver")
    @patch("mimeo.providers.registrar.porkbun.time.sleep")
    def test_verify_dns_retry(
        self,
        mock_sleep: Mock,
        mock_resolver_class: Mock,
        registrar: PorkbunRegistrar,
    ) -> None:
        """Test DNS verification retries on failure."""
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver

        # First attempt: NXDOMAIN, second attempt: success
        mock_answer = Mock()
        mock_answer.__str__ = Mock(return_value="1.2.3.4")
        mock_resolver.resolve.side_effect = [
            dns.resolver.NXDOMAIN(),
            [mock_answer],
        ]

        record = DNSRecord(type="A", name="", content="1.2.3.4", ttl=600)
        result = registrar.verify_dns("example.com", [record], max_attempts=2, delay=1)

        assert result is True
        assert mock_resolver.resolve.call_count == 2
        mock_sleep.assert_called_once_with(1)

    @patch("mimeo.providers.registrar.porkbun.dns.resolver.Resolver")
    def test_verify_dns_wrong_content(
        self,
        mock_resolver_class: Mock,
        registrar: PorkbunRegistrar,
    ) -> None:
        """Test DNS verification when content doesn't match."""
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver

        # Return different IP than expected
        mock_answer = Mock()
        mock_answer.__str__ = Mock(return_value="9.9.9.9")
        mock_resolver.resolve.return_value = [mock_answer]

        record = DNSRecord(type="A", name="", content="1.2.3.4", ttl=600)
        result = registrar.verify_dns("example.com", [record], max_attempts=1)

        assert result is False

    @patch("mimeo.providers.registrar.porkbun.dns.resolver.Resolver")
    def test_verify_dns_unexpected_error(
        self,
        mock_resolver_class: Mock,
        registrar: PorkbunRegistrar,
    ) -> None:
        """Test DNS verification with unexpected error."""
        mock_resolver = Mock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.resolve.side_effect = Exception("Unexpected error")

        record = DNSRecord(type="A", name="", content="1.2.3.4", ttl=600)

        with pytest.raises(DNSError) as exc_info:
            registrar.verify_dns("example.com", [record], max_attempts=1)

        assert "unexpectedly" in str(exc_info.value)

    def test_github_pages_records(self) -> None:
        """Test generation of GitHub Pages DNS records."""
        records = PorkbunRegistrar.github_pages_records("example.com", "testuser")

        # Should have 4 A records + 1 CNAME = 5 total
        assert len(records) == 5

        # Check A records
        a_records = [r for r in records if r.type == "A"]
        assert len(a_records) == 4
        for i, record in enumerate(a_records):
            assert record.name == ""
            assert record.content == GITHUB_PAGES_IPS[i]
            assert record.ttl == 600

        # Check CNAME record
        cname_records = [r for r in records if r.type == "CNAME"]
        assert len(cname_records) == 1
        assert cname_records[0].name == "www"
        assert cname_records[0].content == "testuser.github.io"
        assert cname_records[0].ttl == 600

    def test_context_manager(self) -> None:
        """Test Porkbun registrar as context manager."""
        with PorkbunRegistrar(api_key="pk1_test", secret_key="sk1_test") as registrar:
            assert registrar.api_key == "pk1_test"

    @responses.activate
    def test_configure_dns_error_handling(self, registrar: PorkbunRegistrar) -> None:
        """Test error handling in configure_dns."""
        # Mock API error
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/retrieve/example.com",
            json={"status": "ERROR", "message": "Domain not found"},
            status=200,
        )

        record = DNSRecord(type="A", name="", content="1.2.3.4", ttl=600)

        with pytest.raises(RegistrarError) as exc_info:
            registrar.configure_dns("example.com", [record])

        assert "Domain not found" in str(exc_info.value)

    @responses.activate
    def test_configure_dns_apex_with_full_domain_name(
        self, registrar: PorkbunRegistrar
    ) -> None:
        """Test that apex records are matched when API returns full domain name.

        Porkbun API returns apex records with name="domain.com" instead of "".
        This test verifies that we normalize both representations for matching.
        Also tests that ALIAS records are deleted when creating A records.
        """
        # Mock retrieving existing records with full domain name for apex
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/retrieve/example.com",
            json={
                "status": "SUCCESS",
                "records": [
                    {
                        "id": "123",
                        "type": "A",
                        "name": "example.com",  # Full domain, not ""
                        "content": "5.6.7.8",
                    },
                    {
                        "id": "124",
                        "type": "ALIAS",
                        "name": "example.com",  # Parking record
                        "content": "pixie.porkbun.com",
                    },
                ],
            },
            status=200,
        )

        # Mock deleting both old records
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

        # Mock creating new A record
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/create/example.com",
            json={"status": "SUCCESS", "id": "456"},
            status=200,
        )

        # Configure with apex A record (using "" as name)
        record = DNSRecord(type="A", name="", content="1.2.3.4", ttl=600)
        registrar.configure_dns("example.com", [record])

        # Verify: 1 retrieve + 2 deletes (A + ALIAS) + 1 create = 4 total
        assert len(responses.calls) == 4

    @responses.activate
    def test_configure_dns_deletes_parking_records(
        self, registrar: PorkbunRegistrar
    ) -> None:
        """Test that Porkbun parking records are deleted when deploying.

        Porkbun adds ALIAS/CNAME parking records pointing to pixie.porkbun.com.
        When we configure apex A records and www CNAME, both parking records
        are deleted (ALIAS conflicts with A records at apex).
        """
        # Mock retrieving existing parking records
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/retrieve/example.com",
            json={
                "status": "SUCCESS",
                "records": [
                    {
                        "id": "parking-1",
                        "type": "ALIAS",
                        "name": "example.com",  # Apex parking - conflicts with A
                        "content": "pixie.porkbun.com",
                    },
                    {
                        "id": "parking-2",
                        "type": "CNAME",
                        "name": "www.example.com",  # www parking - matches
                        "content": "pixie.porkbun.com",
                    },
                ],
            },
            status=200,
        )

        # Mock deleting both parking records
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

        # Mock creating new records (4 A + 1 CNAME)
        for _ in range(5):
            responses.add(
                responses.POST,
                "https://api-ipv4.porkbun.com/api/json/v3/dns/create/example.com",
                json={"status": "SUCCESS", "id": "new-record"},
                status=200,
            )

        # Configure GitHub Pages records
        records = PorkbunRegistrar.github_pages_records("example.com", "testuser")
        registrar.configure_dns("example.com", records)

        # Verify: 1 retrieve + 2 deletes (ALIAS + CNAME) + 5 creates = 8 total
        assert len(responses.calls) == 8

    def test_normalize_record_name_apex(self, registrar: PorkbunRegistrar) -> None:
        """Test normalizing apex record names."""
        domain = "example.com"

        # All these should normalize to empty string
        assert registrar._normalize_record_name("", domain) == ""
        assert registrar._normalize_record_name("@", domain) == ""
        assert registrar._normalize_record_name("example.com", domain) == ""

    def test_normalize_record_name_subdomain(self, registrar: PorkbunRegistrar) -> None:
        """Test normalizing subdomain record names."""
        domain = "example.com"

        # Short form subdomains should remain unchanged
        assert registrar._normalize_record_name("www", domain) == "www"
        assert registrar._normalize_record_name("api", domain) == "api"

        # Fully qualified subdomains should be normalized to short form
        assert registrar._normalize_record_name("www.example.com", domain) == "www"
        assert registrar._normalize_record_name("api.example.com", domain) == "api"

    @responses.activate
    def test_check_dns_drift_ok(self, registrar: PorkbunRegistrar) -> None:
        """check_dns_drift returns ok when all expected records are present."""
        expected = PorkbunRegistrar.github_pages_records("example.com", "testuser")

        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/retrieve/example.com",
            json={
                "status": "SUCCESS",
                "records": [
                    {"id": str(i), "type": "A", "name": "", "content": ip, "ttl": "600"}
                    for i, ip in enumerate(GITHUB_PAGES_IPS)
                ] + [
                    {"id": "10", "type": "CNAME", "name": "www", "content": "testuser.github.io", "ttl": "600"},
                ],
            },
            status=200,
        )

        result = registrar.check_dns_drift("example.com", expected)
        assert result["status"] == "ok"
        assert result["missing"] == []

    @responses.activate
    def test_check_dns_drift_missing(self, registrar: PorkbunRegistrar) -> None:
        """check_dns_drift returns missing when expected records are absent."""
        expected = PorkbunRegistrar.github_pages_records("example.com", "testuser")

        # Only return some of the expected records
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/retrieve/example.com",
            json={
                "status": "SUCCESS",
                "records": [
                    {"id": "1", "type": "A", "name": "", "content": GITHUB_PAGES_IPS[0], "ttl": "600"},
                ],
            },
            status=200,
        )

        result = registrar.check_dns_drift("example.com", expected)
        assert result["status"] == "missing"
        assert len(result["missing"]) > 0

    @responses.activate
    def test_check_dns_drift_extra(self, registrar: PorkbunRegistrar) -> None:
        """check_dns_drift returns drift when live has extra records of managed types."""
        expected = [DNSRecord(type="A", name="", content=GITHUB_PAGES_IPS[0], ttl=600)]

        # Live has a different A record IP that is not in expected
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/retrieve/example.com",
            json={
                "status": "SUCCESS",
                "records": [
                    {"id": "1", "type": "A", "name": "", "content": GITHUB_PAGES_IPS[0], "ttl": "600"},
                    {"id": "2", "type": "A", "name": "", "content": "1.2.3.4", "ttl": "600"},
                ],
            },
            status=200,
        )

        result = registrar.check_dns_drift("example.com", expected)
        # extra record present but nothing missing - status is drift
        assert result["status"] == "drift"
        assert len(result["extra"]) > 0

    @responses.activate
    def test_configure_dns_deletes_alias_when_creating_a_records(
        self, registrar: PorkbunRegistrar
    ) -> None:
        """Test that ALIAS records at apex are deleted when creating A records.

        Porkbun doesn't allow ALIAS and A records at the same location.
        Even though they have different types, ALIAS must be deleted.
        """
        # Mock retrieving existing ALIAS record
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

        # Mock deleting ALIAS record
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/delete/example.com/alias-123",
            json={"status": "SUCCESS"},
            status=200,
        )

        # Mock creating A record
        responses.add(
            responses.POST,
            "https://api-ipv4.porkbun.com/api/json/v3/dns/create/example.com",
            json={"status": "SUCCESS", "id": "a-456"},
            status=200,
        )

        # Configure with A record at apex
        record = DNSRecord(type="A", name="", content="1.2.3.4", ttl=600)
        registrar.configure_dns("example.com", [record])

        # Verify: 1 retrieve + 1 delete (ALIAS) + 1 create (A) = 3 total
        assert len(responses.calls) == 3
