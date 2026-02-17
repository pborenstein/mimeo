"""Tests for data models."""

import pytest

from mimeo.models import DNSRecord, Domain


class TestDomain:
    """Tests for Domain model."""

    def test_valid_domain(self) -> None:
        """Domain should accept valid domain names."""
        domain = Domain("example.com")
        assert domain.name == "example.com"

    def test_valid_subdomain(self) -> None:
        """Domain should accept subdomains."""
        domain = Domain("www.example.com")
        assert domain.name == "www.example.com"

    def test_invalid_domain_no_tld(self) -> None:
        """Domain should reject names without TLD."""
        with pytest.raises(ValueError, match="Invalid domain name"):
            Domain("localhost")

    def test_invalid_domain_spaces(self) -> None:
        """Domain should reject names with spaces."""
        with pytest.raises(ValueError, match="Invalid domain name"):
            Domain("example .com")

    def test_invalid_domain_special_chars(self) -> None:
        """Domain should reject names with special characters."""
        with pytest.raises(ValueError, match="Invalid domain name"):
            Domain("example@com")

    def test_tld_extraction(self) -> None:
        """Domain should extract TLD correctly."""
        domain = Domain("example.com")
        assert domain.tld == "com"

        domain2 = Domain("example.co.uk")
        assert domain2.tld == "uk"

    def test_sld_extraction(self) -> None:
        """Domain should extract SLD correctly."""
        domain = Domain("example.com")
        assert domain.sld == "example"

        domain2 = Domain("www.example.com")
        assert domain2.sld == "www.example"


class TestDNSRecord:
    """Tests for DNSRecord model."""

    def test_valid_a_record(self) -> None:
        """DNSRecord should accept valid A record."""
        record = DNSRecord(type="A", name="@", content="185.199.108.153", ttl=600)
        assert record.type == "A"
        assert record.name == "@"
        assert record.content == "185.199.108.153"
        assert record.ttl == 600

    def test_valid_cname_record(self) -> None:
        """DNSRecord should accept valid CNAME record."""
        record = DNSRecord(type="CNAME", name="www", content="example.com", ttl=300)
        assert record.type == "CNAME"
        assert record.name == "www"
        assert record.content == "example.com"

    def test_default_ttl(self) -> None:
        """DNSRecord should use default TTL of 600."""
        record = DNSRecord(type="A", name="@", content="1.2.3.4")
        assert record.ttl == 600

    def test_negative_ttl(self) -> None:
        """DNSRecord should reject negative TTL."""
        with pytest.raises(ValueError, match="TTL must be non-negative"):
            DNSRecord(type="A", name="@", content="1.2.3.4", ttl=-1)

    def test_empty_content(self) -> None:
        """DNSRecord should reject empty content."""
        with pytest.raises(ValueError, match="content cannot be empty"):
            DNSRecord(type="A", name="@", content="")


