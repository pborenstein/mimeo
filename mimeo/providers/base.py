"""Abstract base classes for providers.

Four roles, each a separate interface (DEC-041, DEC-044):

- Registrar: holds the registration and the nameserver setting
- DNSProvider: holds a zone's records
- Host: serves a site and holds its custom-domain setting
- RepoProvider: creates and removes the repository behind a site
"""

from abc import ABC, abstractmethod
from typing import Any

from mimeo.models import DNSRecord, Site, SiteState


class Registrar(ABC):
    """A domain registrar."""

    @abstractmethod
    def list_domains(self) -> list[dict[str, Any]]:
        """Return all domains in the account, as the registrar reports them."""

    @abstractmethod
    def get_nameservers(self, domain: str) -> list[str]:
        """Return the nameservers set for the domain, lowercase and sorted."""

    @abstractmethod
    def set_nameservers(self, domain: str, nameservers: list[str]) -> None:
        """Set the domain's nameservers."""

    @abstractmethod
    def dnssec_enabled(self, domain: str) -> bool:
        """Return True when the registry holds DNSSEC records for the domain."""


class DNSProvider(ABC):
    """A DNS provider: zones and the records in them."""

    name: str
    # Record types the provider cannot hold; `delegate` does not copy them.
    unsupported_types: frozenset[str] = frozenset()

    @abstractmethod
    def serves(self, nameservers: list[str]) -> bool:
        """Return True when these nameservers belong to this provider."""

    @abstractmethod
    def zone_exists(self, zone: str) -> bool:
        """Return True when the provider has the zone."""

    @abstractmethod
    def create_zone(self, zone: str) -> None:
        """Create the zone. A zone that already exists is left alone."""

    @abstractmethod
    def zone_nameservers(self, zone: str) -> list[str]:
        """Return the nameservers the provider answers on for the zone."""

    @abstractmethod
    def list_records(self, zone: str) -> list[DNSRecord]:
        """Return every record in the zone, names relative to the zone."""

    @abstractmethod
    def add_record(self, zone: str, record: DNSRecord) -> None:
        """Add a record to the zone."""

    @abstractmethod
    def delete_record(self, zone: str, record: DNSRecord) -> None:
        """Delete a record previously returned by list_records."""

    def set_proxied(self, zone: str, record: DNSRecord, proxied: bool) -> None:
        """Turn the provider's proxy on or off for a record list_records returned.

        Only providers that have a proxy setting implement this.
        """
        raise NotImplementedError(f"{self.name} has no proxy setting")

    def stops_on_leaving(self, zone: str, records: list[DNSRecord]) -> list[str]:
        """Say what stops working when the zone moves to another provider.

        Some records point at services the provider runs only for zones
        it serves. Copying such a record elsewhere keeps the record and
        loses the service. One sentence per service; empty when the
        records carry over whole.
        """
        return []


class Host(ABC):
    """A hosting provider: serves sites and links each to a hostname."""

    name: str
    # The organizations or accounts `scan` searches.
    organizations: list[str]

    @abstractmethod
    def find_site(self, hostname: str) -> Site | None:
        """Find the site whose custom domain is the hostname, without a full scan.

        Checks only the places a site for this hostname would be by
        default. Returns None when it is not there.
        """

    @abstractmethod
    def scan(self) -> dict[str, list[Site]]:
        """Return every site with a custom domain, keyed by that hostname."""

    @abstractmethod
    def state(self, site: Site) -> SiteState:
        """Return the site's custom domain, certificate and HTTPS state."""

    @abstractmethod
    def set_custom_domain(self, site: Site, hostname: str | None) -> None:
        """Set the site's custom domain, or remove it when hostname is None."""

    @abstractmethod
    def required_records(self, site: Site, label: str) -> list[DNSRecord]:
        """Return the records the host needs for a hostname.

        Args:
            site: The site being served
            label: The hostname relative to its zone ("" for the apex)
        """

    @abstractmethod
    def enforce_https(self, site: Site) -> bool:
        """Turn on HTTPS enforcement. Returns False when no certificate exists yet."""


class RepoProvider(ABC):
    """Creates and removes the repository behind a site."""

    @abstractmethod
    def validate_template(self, template_repo: str) -> None:
        """Raise unless the template exists and is offered as a template."""

    @abstractmethod
    def create_from_template(
        self,
        repo_name: str,
        owner: str,
        template_repo: str,
        private: bool = False,
        force: bool = False,
    ) -> tuple[str, bool, bool]:
        """Create a repository from a template.

        Returns:
            (full name, created, existed before)
        """

    @abstractmethod
    def delete_repository_if_exists(self, repo_full_name: str) -> bool:
        """Delete a repository. Returns False when it did not exist."""
