"""Tests for provider base classes."""

from pathlib import Path

import pytest

from mimeo.models import DNSRecord
from mimeo.providers.base import DeployResult, Host, Registrar


class ConcreteRegistrar(Registrar):
    """Concrete implementation of Registrar for testing."""

    def configure_dns(self, domain: str, records: list[DNSRecord]) -> None:
        """Test implementation."""
        pass

    def verify_dns(self, domain: str, records: list[DNSRecord]) -> bool:
        """Test implementation."""
        return True


class ConcreteHost(Host):
    """Concrete implementation of Host for testing."""

    def deploy_site(self, domain: str, content_path: Path) -> DeployResult:
        """Test implementation."""
        return DeployResult(url=f"https://{domain}", repo_created=True, https_enabled=True)


def test_registrar_can_be_instantiated() -> None:
    """Concrete Registrar implementation should be instantiable."""
    registrar = ConcreteRegistrar()
    assert isinstance(registrar, Registrar)


def test_registrar_has_configure_dns_method() -> None:
    """Registrar should have configure_dns method."""
    registrar = ConcreteRegistrar()
    records = [DNSRecord(type="A", name="@", content="1.2.3.4")]
    registrar.configure_dns("example.com", records)


def test_registrar_has_verify_dns_method() -> None:
    """Registrar should have verify_dns method."""
    registrar = ConcreteRegistrar()
    records = [DNSRecord(type="A", name="@", content="1.2.3.4")]
    result = registrar.verify_dns("example.com", records)
    assert result is True


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


def test_cannot_instantiate_abstract_registrar() -> None:
    """Cannot instantiate Registrar directly without implementing abstract methods."""
    with pytest.raises(TypeError):
        Registrar()  # type: ignore


def test_cannot_instantiate_abstract_host() -> None:
    """Cannot instantiate Host directly without implementing abstract methods."""
    with pytest.raises(TypeError):
        Host()  # type: ignore
