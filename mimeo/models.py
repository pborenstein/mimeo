"""Data models for Mimeo."""

import re
from dataclasses import dataclass
from typing import Literal


DNSRecordType = Literal["A", "AAAA", "CNAME", "MX", "TXT", "NS", "SRV"]


@dataclass
class Domain:
    """Represents a domain name with validation."""

    name: str

    def __post_init__(self) -> None:
        """Validate domain name format."""
        if not self.is_valid():
            raise ValueError(f"Invalid domain name: {self.name}")

    def is_valid(self) -> bool:
        """Check if domain name is valid."""
        # Basic domain validation: alphanumeric, hyphens, dots, must have at least one dot
        pattern = r"^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$"
        return bool(re.match(pattern, self.name.lower()))

    @property
    def tld(self) -> str:
        """Extract top-level domain."""
        return self.name.split(".")[-1]

    @property
    def sld(self) -> str:
        """Extract second-level domain (domain without TLD)."""
        parts = self.name.split(".")
        if len(parts) >= 2:
            return ".".join(parts[:-1])
        return self.name


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
class DeploymentConfig:
    """Configuration for a deployment."""

    domain: Domain
    registrar: str = "porkbun"
    host: str = "github"
    template: str = "minimal"
    force: bool = False
    dry_run: bool = False
    verbose: bool = False
    no_verify: bool = False
