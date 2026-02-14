"""Exception hierarchy for Mimeo."""


class MimeoError(Exception):
    """Base exception for all Mimeo errors."""

    pass


class ConfigurationError(MimeoError):
    """Raised when configuration is invalid or missing."""

    pass


class ProviderError(MimeoError):
    """Base exception for provider-related errors."""

    pass


class RegistrarError(ProviderError):
    """Raised when registrar operations fail."""

    pass


class HostError(ProviderError):
    """Raised when hosting provider operations fail."""

    pass


class DNSError(MimeoError):
    """Raised when DNS operations or verification fail."""

    pass
