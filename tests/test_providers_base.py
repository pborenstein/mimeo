"""Tests for provider base classes."""

from pathlib import Path

import pytest

from mimeo.models import DNSRecord, NameserverCheckResult
from mimeo.providers.base import DNSProvider, DeployResult, Host, Registrar


class ConcreteRegistrar(Registrar):
    """Concrete implementation of Registrar for testing."""

    def check_nameservers(self, domain: str) -> NameserverCheckResult:
        """Test implementation."""
        return NameserverCheckResult(ok=True, actual=[], expected=[])


class ConcreteDNSProvider(DNSProvider):
    """Concrete implementation of DNSProvider for testing."""

    def configure_dns(self, domain: str, records: list[DNSRecord]) -> None:
        """Test implementation."""
        pass

    def verify_dns(self, domain: str, records: list[DNSRecord]) -> bool:
        """Test implementation."""
        return True

    def check_nameservers(self, domain: str) -> NameserverCheckResult:
        """Test implementation."""
        return NameserverCheckResult(ok=True, actual=[], expected=[])


class ConcreteHost(Host):
    """Concrete implementation of Host for testing."""

    def deploy_site(self, domain: str, content_path: Path) -> DeployResult:
        """Test implementation."""
        return DeployResult(url=f"https://{domain}", repo_created=True, https_enabled=True)

    def required_dns_records(self, domain: str) -> list[DNSRecord]:
        """Test implementation."""
        return [DNSRecord(type="A", name="", content="1.2.3.4")]


def test_registrar_can_be_instantiated() -> None:
    """Concrete Registrar implementation should be instantiable."""
    registrar = ConcreteRegistrar()
    assert isinstance(registrar, Registrar)


def test_registrar_has_check_nameservers_method() -> None:
    """Registrar should have check_nameservers method."""
    registrar = ConcreteRegistrar()
    result = registrar.check_nameservers("example.com")
    assert isinstance(result, NameserverCheckResult)
    assert result.ok is True


def test_dns_provider_can_be_instantiated() -> None:
    """Concrete DNSProvider implementation should be instantiable."""
    provider = ConcreteDNSProvider()
    assert isinstance(provider, DNSProvider)


def test_dns_provider_has_configure_dns_method() -> None:
    """DNSProvider should have configure_dns method."""
    provider = ConcreteDNSProvider()
    records = [DNSRecord(type="A", name="@", content="1.2.3.4")]
    provider.configure_dns("example.com", records)


def test_dns_provider_has_verify_dns_method() -> None:
    """DNSProvider should have verify_dns method."""
    provider = ConcreteDNSProvider()
    records = [DNSRecord(type="A", name="@", content="1.2.3.4")]
    result = provider.verify_dns("example.com", records)
    assert result is True


def test_dns_provider_has_check_nameservers_method() -> None:
    """DNSProvider should have check_nameservers method."""
    provider = ConcreteDNSProvider()
    result = provider.check_nameservers("example.com")
    assert isinstance(result, NameserverCheckResult)


def test_host_can_be_instantiated() -> None:
    """Concrete Host implementation should be instantiable."""
    host = ConcreteHost()
    assert isinstance(host, Host)


def test_host_has_deploy_site_method() -> None:
    """Host should have deploy_site method."""
    host = ConcreteHost()
    result = host.deploy_site("example.com", Path("/tmp/site"))
    assert result.url == "https://example.com"
    assert result.repo_created is True
    assert result.https_enabled is True


def test_host_has_required_dns_records_method() -> None:
    """Host should have required_dns_records method."""
    host = ConcreteHost()
    records = host.required_dns_records("example.com")
    assert isinstance(records, list)
    assert len(records) > 0
    assert isinstance(records[0], DNSRecord)


def test_cannot_instantiate_abstract_registrar() -> None:
    """Cannot instantiate Registrar directly without implementing abstract methods."""
    with pytest.raises(TypeError):
        Registrar()  # type: ignore


def test_cannot_instantiate_abstract_dns_provider() -> None:
    """Cannot instantiate DNSProvider directly without implementing abstract methods."""
    with pytest.raises(TypeError):
        DNSProvider()  # type: ignore


def test_cannot_instantiate_abstract_host() -> None:
    """Cannot instantiate Host directly without implementing abstract methods."""
    with pytest.raises(TypeError):
        Host()  # type: ignore
