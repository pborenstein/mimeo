"""Tests for data models."""

import pytest

from mimeo.models import DNSRecord


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
