"""Abstract base classes for providers."""

from abc import ABC, abstractmethod
from pathlib import Path

from mimeo.models import DNSRecord


class Registrar(ABC):
    """Abstract base class for domain registrars."""

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


class Host(ABC):
    """Abstract base class for hosting providers."""

    @abstractmethod
    def deploy_site(self, domain: str, content_path: Path) -> str:
        """Deploy a site to the hosting provider.

        Args:
            domain: Domain name for the site
            content_path: Path to site content directory

        Returns:
            Live URL of the deployed site

        Raises:
            HostError: If deployment fails
        """
        pass

    @abstractmethod
    def configure_custom_domain(self, domain: str) -> None:
        """Configure custom domain in hosting provider settings.

        Args:
            domain: Custom domain to configure

        Raises:
            HostError: If custom domain configuration fails
        """
        pass
