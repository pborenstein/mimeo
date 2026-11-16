"""Tests for provider base classes."""

import pytest

from mimeo.providers.base import DNSProvider, Host, Registrar, RepoProvider
from tests.fakes import FakeDNS, FakeHost, FakeRegistrar


@pytest.mark.parametrize("interface", [Registrar, DNSProvider, Host, RepoProvider])
def test_interfaces_cannot_be_instantiated(interface: type) -> None:
    with pytest.raises(TypeError):
        interface()


def test_complete_implementations_instantiate() -> None:
    assert isinstance(FakeRegistrar(), Registrar)
    assert isinstance(FakeDNS("x"), DNSProvider)
    assert isinstance(FakeHost(), Host)


def test_partial_implementation_is_rejected() -> None:
    class Partial(DNSProvider):
        name = "partial"

        def serves(self, nameservers: list[str]) -> bool:
            return False

    with pytest.raises(TypeError):
        Partial()  # type: ignore[abstract]
