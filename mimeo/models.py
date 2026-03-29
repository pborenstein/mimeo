"""Data models for Mimeo."""

from dataclasses import dataclass
from typing import Literal


DNSRecordType = Literal["A", "AAAA", "CNAME", "MX", "TXT", "NS", "SRV"]


@dataclass
class DNSRecord:
    """Represents a DNS record."""

    type: DNSRecordType
    name: str
    content: str
    ttl: int = 600

    def __post_init__(self) -> None:
        """Validate DNS record."""
        if self.ttl < 0:
            raise ValueError(f"TTL must be non-negative, got {self.ttl}")
        if not self.content:
            raise ValueError("DNS record content cannot be empty")


@dataclass
class NameserverCheckResult:
    """Result of a nameserver check for a domain."""

    ok: bool
    actual: list[str]
    expected: list[str]
