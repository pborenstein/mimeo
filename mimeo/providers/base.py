"""Abstract base classes for providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any  # noqa: F401 — kept for subclass use

from mimeo.models import DNSRecord, NameserverCheckResult


class Registrar(ABC):
    """Abstract base class for domain registrars."""

    @abstractmethod
    def check_nameservers(self, domain: str) -> NameserverCheckResult:
        """Check whether the domain's nameservers match this registrar.

        Args:
            domain: Domain name to check

        Returns:
            NameserverCheckResult with ok flag and actual/expected nameservers
        """
        pass

    @abstractmethod
    def update_nameservers(self, domain: str) -> None:
        """Reset the domain's nameservers to this registrar's defaults.

        Args:
            domain: Domain name to update

        Raises:
            RegistrarError: If the update fails
        """
        pass

    @abstractmethod
    def list_domains(self) -> list[dict[str, Any]]:
        """Return all domains in the account.

        Returns:
            List of domain info dicts as returned by the registrar API.

        Raises:
            RegistrarError: If the API call fails
        """
        pass


class DNSProvider(ABC):
    """Abstract base class for DNS providers."""

    @abstractmethod
    def configure_dns(self, domain: str, records: list[DNSRecord]) -> None:
        """Configure DNS records for a domain.

        Args:
            domain: Domain name to configure
            records: List of DNS records to create/update

        Raises:
            RegistrarError: If DNS configuration fails
        """
        pass

    @abstractmethod
    def verify_dns(self, domain: str, records: list[DNSRecord]) -> bool:
        """Verify DNS records have propagated.

        Args:
            domain: Domain name to verify
            records: Expected DNS records

        Returns:
            True if all records are verified, False otherwise

        Raises:
            DNSError: If verification fails unexpectedly
        """
        pass

    @abstractmethod
    def check_nameservers(self, domain: str) -> NameserverCheckResult:
        """Check whether the domain's nameservers point to this provider.

        Args:
            domain: Domain name to check

        Returns:
            NameserverCheckResult with ok flag and actual/expected nameservers
        """
        pass


@dataclass
class DeployResult:
    """Result of a site deployment."""

    url: str
    repo_created: bool
    https_enabled: bool
    repo_existed: bool = False


class Host(ABC):
    """Abstract base class for hosting providers."""

    @abstractmethod
    def deploy_site(self, domain: str) -> DeployResult:
        """Deploy a site to the hosting provider.

        Args:
            domain: Domain name for the site

        Returns:
            DeployResult with url, repo_created, and https_enabled flags

        Raises:
            HostError: If deployment fails
        """
        pass

    @abstractmethod
    def required_dns_records(self, domain: str) -> list[DNSRecord]:
        """Return the DNS records required for this host to serve the domain.

        Args:
            domain: Domain name for the site

        Returns:
            List of DNSRecord objects that must be configured
        """
        pass
