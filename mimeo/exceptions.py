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


class NetworkError(MimeoError):
    """Raised when network requests fail."""

    pass


class APIError(MimeoError):
    """Raised when API returns an error response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        """Initialize API error.

        Args:
            message: Error message
            status_code: HTTP status code if applicable
        """
        super().__init__(message)
        self.status_code = status_code
