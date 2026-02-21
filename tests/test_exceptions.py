"""Tests for exception hierarchy."""

import pytest

from mimeo.exceptions import (
    ConfigurationError,
    DNSError,
    HostError,
    MimeoError,
    NSMismatchError,
    ProviderError,
    RegistrarError,
)


def test_mimeo_error_is_base_exception() -> None:
    """MimeoError should be base for all Mimeo exceptions."""
    error = MimeoError("test error")
    assert isinstance(error, Exception)
    assert str(error) == "test error"


def test_configuration_error_inherits_from_mimeo_error() -> None:
    """ConfigurationError should inherit from MimeoError."""
    error = ConfigurationError("config error")
    assert isinstance(error, MimeoError)
    assert isinstance(error, Exception)


def test_provider_error_inherits_from_mimeo_error() -> None:
    """ProviderError should inherit from MimeoError."""
    error = ProviderError("provider error")
    assert isinstance(error, MimeoError)


def test_registrar_error_inherits_from_provider_error() -> None:
    """RegistrarError should inherit from ProviderError."""
    error = RegistrarError("registrar error")
    assert isinstance(error, ProviderError)
    assert isinstance(error, MimeoError)


def test_host_error_inherits_from_provider_error() -> None:
    """HostError should inherit from ProviderError."""
    error = HostError("host error")
    assert isinstance(error, ProviderError)
    assert isinstance(error, MimeoError)


def test_dns_error_inherits_from_mimeo_error() -> None:
    """DNSError should inherit from MimeoError."""
    error = DNSError("dns error")
    assert isinstance(error, MimeoError)


def test_ns_mismatch_error_inherits_from_registrar_error() -> None:
    """NSMismatchError should inherit from RegistrarError."""
    error = NSMismatchError("ns mismatch")
    assert isinstance(error, RegistrarError)
    assert isinstance(error, ProviderError)
    assert isinstance(error, MimeoError)
