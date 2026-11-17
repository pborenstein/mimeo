"""Read everything that connects a hostname to its site.

Four things have to agree for a site to load at a hostname: the
registration, the nameservers, the DNS records at whichever provider
the nameservers name, and the host's custom-domain setting. `Fleet.read`
collects all four into one `Connection`. Every command starts here.
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Dict

from mimeo.cache import SiteCache
from mimeo.models import DNSRecord, Site, SiteState
from mimeo.providers.base import DNSProvider, Host, Registrar, RepoProvider


@dataclass
class Connection:
    """What was read about one hostname."""

    hostname: str
    # The registered domain the hostname belongs to; None when no suffix
    # of the hostname is at the registrar.
    zone: str | None = None
    # The hostname relative to the zone: "" for the apex.
    label: str = ""
    registration: Dict[str, Any] | None = None
    nameservers: list[str] = field(default_factory=list)
    # The configured provider the nameservers belong to; None when they
    # belong to none of them.
    dns: DNSProvider | None = None
    # Every record in the zone at that provider; None when dns is None.
    records: list[DNSRecord] | None = None
    site: Site | None = None
    state: SiteState | None = None
    # For a site whose hostname is not at the registrar: the nameservers
    # public DNS gives for it. Empty when nothing answers, which is what
    # a lapsed registration looks like. None when it was not looked up.
    public_nameservers: list[str] | None = None


class Fleet:
    """The providers a run works with, and what has been read from them."""

    def __init__(
        self,
        registrar: Registrar,
        dns_providers: list[DNSProvider],
        host: Host,
        cache: SiteCache,
        repos: RepoProvider | None = None,
        lookup: Callable[[str], list[str] | None] | None = None,
    ) -> None:
        """Bundle the providers.

        Args:
            registrar: The registrar holding the domains
            dns_providers: Every configured DNS provider
            host: The host serving sites
            cache: Hostname-to-site cache
            repos: Creates and deletes repositories (`create` and
                `delete` only)
            lookup: Asks public DNS for a domain's nameservers. Used
                for a site whose hostname is not at the registrar.
        """
        self.repos = repos
        self.lookup = lookup
        self.registrar = registrar
        self.dns_providers = dns_providers
        self.host = host
        self.cache = cache
        self._lock = threading.Lock()
        self._registered: Dict[str, Dict[str, Any]] | None = None
        self._nameservers: Dict[str, list[str]] = {}
        self._records: Dict[str, list[DNSRecord]] = {}

    @property
    def registered(self) -> Dict[str, Dict[str, Any]]:
        """Domains at the registrar, keyed by name. Read once per run."""
        with self._lock:
            if self._registered is None:
                self._registered = {
                    str(d.get("domain", "")).lower(): d for d in self.registrar.list_domains()
                }
            return self._registered

    def zone_for(self, hostname: str) -> str | None:
        """The longest suffix of the hostname that is a registered domain."""
        labels = hostname.lower().split(".")
        for i in range(len(labels) - 1):
            candidate = ".".join(labels[i:])
            if candidate in self.registered:
                return candidate
        return None

    def provider_for(self, nameservers: list[str]) -> DNSProvider | None:
        """The configured DNS provider these nameservers belong to."""
        for provider in self.dns_providers:
            if provider.serves(nameservers):
                return provider
        return None

    def provider_named(self, name: str) -> DNSProvider | None:
        """The configured DNS provider with this name."""
        for provider in self.dns_providers:
            if provider.name == name:
                return provider
        return None

    def nameservers(self, zone: str) -> list[str]:
        """The zone's nameservers as set at the registrar. Read once per run."""
        with self._lock:
            cached = self._nameservers.get(zone)
        if cached is not None:
            return cached
        found = self.registrar.get_nameservers(zone)
        with self._lock:
            self._nameservers[zone] = found
        return found

    def zone_records(self, zone: str, provider: DNSProvider) -> list[DNSRecord]:
        """Every record in the zone. Read once per run, shared by its sites."""
        with self._lock:
            cached = self._records.get(zone)
        if cached is not None:
            return cached
        found = provider.list_records(zone)
        with self._lock:
            self._records[zone] = found
        return found

    def forget(self, zone: str) -> None:
        """Drop what was read about a zone, after changing it."""
        with self._lock:
            self._nameservers.pop(zone, None)
            self._records.pop(zone, None)

    def rescan(self) -> Dict[str, list[Site]]:
        """Ask the host for every site and rebuild the cache from the answer.

        Returns:
            Hostnames claimed by more than one site. The cache keeps the
            first claim for each.
        """
        found = self.host.scan()
        self.cache.replace(
            {hostname: sites[0] for hostname, sites in found.items()},
            organizations=self.host.organizations,
        )
        return {hostname: sites for hostname, sites in found.items() if len(sites) > 1}

    @property
    def cache_current(self) -> bool:
        """True when the cache was filled by a scan of the organizations listed now."""
        return self.cache.covers(self.host.organizations)

    def site_for(
        self, hostname: str, search: bool = True, thorough: bool = False
    ) -> tuple[Site | None, SiteState | None]:
        """Find the site whose custom domain is the hostname.

        A cached pair is confirmed against the host and dropped when the
        host disagrees. With `search`, a hostname with no confirmed pair
        is then looked for in the default places (Host.find_site), and
        after that by a full scan when the cache has never been filled
        by one or was filled from a different list of organizations, or when
        `thorough` is set. A fleet-wide run passes
        search=False and relies on the scan that filled the cache.

        Args:
            hostname: The hostname to find the site for
            search: Look beyond the cache
            thorough: Always scan before concluding there is no site.
                For callers about to do something that cannot be undone.
        """
        cached = self.cache.get(hostname)
        if cached is not None:
            state = self.host.state(cached)
            if state.custom_domain == hostname:
                return cached, state
            self.cache.remove(hostname)
        if not search:
            return None, None
        found = self.host.find_site(hostname)
        if found is None and (thorough or not self.cache_current):
            self.rescan()
            found = self.cache.get(hostname)
        if found is None:
            return None, None
        self.cache.set(hostname, found)
        return found, self.host.state(found)

    def read(self, hostname: str, search: bool = True) -> Connection:
        """Read the registration, nameservers, records and site for a hostname."""
        hostname = hostname.lower()
        conn = Connection(hostname=hostname)

        zone = self.zone_for(hostname)
        if zone is not None:
            conn.zone = zone
            conn.label = hostname[: -len(zone)].rstrip(".")
            conn.registration = self.registered[zone]
            conn.nameservers = self.nameservers(zone)
            conn.dns = self.provider_for(conn.nameservers)
            if conn.dns is not None:
                conn.records = self.zone_records(zone, conn.dns)

        conn.site, conn.state = self.site_for(hostname, search=search)
        if zone is None and conn.site is not None and self.lookup is not None:
            conn.public_nameservers = self._public_nameservers(hostname)
        return conn

    def _public_nameservers(self, hostname: str) -> list[str] | None:
        """Nameservers public DNS gives for the hostname or a parent of it.

        Empty when DNS has none for any of them; None when a lookup
        could not be made, so nothing is concluded from it.
        """
        labels = hostname.split(".")
        assert self.lookup is not None
        for i in range(len(labels) - 1):
            found = self.lookup(".".join(labels[i:]))
            if found is None:
                return None
            if found:
                return found
        return []

    def hostnames(self) -> list[str]:
        """Every hostname a fleet-wide run covers: registered domains and cached sites."""
        return sorted(set(self.registered) | set(self.cache.hostnames()))
