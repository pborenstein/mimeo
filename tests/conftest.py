"""Shared fixtures."""

from pathlib import Path

import pytest

from mimeo.cache import SiteCache
from mimeo.connection import Fleet
from tests.fakes import FakeDNS, FakeHost, FakeRegistrar


class World:
    """A registrar, two DNS providers, a host and a cache wired into a Fleet."""

    def __init__(self, cache_path: Path) -> None:
        self.pb = FakeDNS("pb")
        self.cf = FakeDNS("cf", proxies=True)
        self.registrar = FakeRegistrar()
        self.host = FakeHost(["sites", "other"])
        self.cache = SiteCache(cache_path)
        self.fleet = Fleet(self.registrar, [self.pb, self.cf], self.host, self.cache)

    def register(self, domain: str, dns: FakeDNS | None = None) -> None:
        """Register a domain with its zone at a provider (default: pb)."""
        provider = dns or self.pb
        self.registrar.ns[domain] = provider.nameserver_names
        provider.zones.setdefault(domain, [])

    def healthy_site(self, hostname: str, zone: str | None = None, dns: FakeDNS | None = None) -> None:
        """A registered hostname with a site and every required record."""
        zone = zone or hostname
        provider = dns or self.pb
        if zone not in self.registrar.ns:
            self.register(zone, provider)
        site = self.host.add(f"sites/{hostname}", hostname)
        label = hostname[: -len(zone)].rstrip(".")
        provider.seed(zone, *self.host.required_records(site, label))
        self.cache.set(hostname, site)


@pytest.fixture
def world(tmp_path: Path) -> World:
    return World(tmp_path / "sites.json")
