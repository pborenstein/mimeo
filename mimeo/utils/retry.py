"""Retry with exponential backoff and jitter."""

import random
import time
from collections.abc import Callable
from typing import TypeVar

from mimeo.exceptions import APIError, HostError, NetworkError

T = TypeVar("T")

# Status codes that indicate a transient server-side condition
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# Substrings in HostError messages that indicate transient gh CLI failures,
# used only when no HTTP status code was recovered from gh stderr (e.g.
# network-level failures). Shared with the CLI error categorizer.
_TRANSIENT_HOST_KEYWORDS = ("500", "502", "503", "timeout", "connection", "rate limit")


def _is_retryable(exc: BaseException) -> bool:
    """Return True if the exception represents a transient failure."""
    if isinstance(exc, APIError):
        return exc.status_code in _RETRYABLE_STATUS_CODES
    if isinstance(exc, NetworkError):
        return True
    if isinstance(exc, HostError):
        if exc.status_code is not None:
            return exc.status_code in _RETRYABLE_STATUS_CODES
        msg = str(exc).lower()
        return any(kw in msg for kw in _TRANSIENT_HOST_KEYWORDS)
    return False


def retry_with_jitter(
    fn: Callable[[], T],
    *,
    retries: int = 3,
    base: float = 2.0,
    cap: float = 30.0,
) -> T:
    """Call fn, retrying on transient errors with exponential backoff and jitter.

    Args:
        fn: Zero-argument callable to invoke.
        retries: Maximum number of retry attempts (not counting the first call).
        base: Base for the exponential backoff (seconds).
        cap: Maximum wait time in seconds before jitter is added.

    Returns:
        The return value of fn on success.

    Raises:
        The last exception raised by fn after all retries are exhausted, or
        immediately if the exception is not retryable.
    """
    last_exc: BaseException | None = None
    for attempt in range(retries + 1):
        try:
            return fn()
        except Exception as exc:
            if not _is_retryable(exc):
                raise
            last_exc = exc
            if attempt == retries:
                break
            wait = min(cap, base ** attempt) + random.uniform(0, 1)
            time.sleep(wait)

    assert last_exc is not None
    raise last_exc
