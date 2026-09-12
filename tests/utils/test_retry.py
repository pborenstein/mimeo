"""Tests for retry_with_jitter helper."""

from unittest.mock import patch

import pytest

from mimeo.exceptions import APIError, ConfigurationError, HostError, NetworkError
from mimeo.utils.retry import retry_with_jitter


class TestRetryWithJitter:
    """Tests for retry_with_jitter."""

    @patch("mimeo.utils.retry.time.sleep")
    def test_success_on_first_attempt(self, mock_sleep) -> None:
        """Returns immediately when fn succeeds on first call."""
        fn = lambda: "ok"
        result = retry_with_jitter(fn)
        assert result == "ok"
        mock_sleep.assert_not_called()

    @patch("mimeo.utils.retry.time.sleep")
    def test_retries_on_api_error_429(self, mock_sleep) -> None:
        """Retries on APIError with status 429."""
        calls = []

        def fn():
            calls.append(1)
            if len(calls) < 3:
                raise APIError("rate limited", status_code=429)
            return "done"

        result = retry_with_jitter(fn, retries=3)
        assert result == "done"
        assert len(calls) == 3
        assert mock_sleep.call_count == 2

    @patch("mimeo.utils.retry.time.sleep")
    def test_retries_on_api_error_503(self, mock_sleep) -> None:
        """Retries on APIError with status 503."""
        calls = []

        def fn():
            calls.append(1)
            if len(calls) == 1:
                raise APIError("service unavailable", status_code=503)
            return "ok"

        result = retry_with_jitter(fn, retries=2)
        assert result == "ok"
        assert mock_sleep.call_count == 1

    @patch("mimeo.utils.retry.time.sleep")
    def test_retries_on_network_error(self, mock_sleep) -> None:
        """Retries on NetworkError."""
        calls = []

        def fn():
            calls.append(1)
            if len(calls) == 1:
                raise NetworkError("connection refused")
            return "recovered"

        result = retry_with_jitter(fn, retries=2)
        assert result == "recovered"
        assert mock_sleep.call_count == 1

    @patch("mimeo.utils.retry.time.sleep")
    def test_retries_on_host_error_with_502(self, mock_sleep) -> None:
        """Retries on HostError containing '502'."""
        calls = []

        def fn():
            calls.append(1)
            if len(calls) == 1:
                raise HostError("gh: 502 Bad Gateway (HTTP 502)")
            return "ok"

        result = retry_with_jitter(fn, retries=2)
        assert result == "ok"
        assert mock_sleep.call_count == 1

    @patch("mimeo.utils.retry.time.sleep")
    def test_retries_on_host_error_rate_limit(self, mock_sleep) -> None:
        """Retries on HostError containing 'rate limit'."""
        calls = []

        def fn():
            calls.append(1)
            if len(calls) == 1:
                raise HostError("gh: API rate limit exceeded (HTTP 429)")
            return "ok"

        result = retry_with_jitter(fn, retries=2)
        assert result == "ok"
        assert mock_sleep.call_count == 1

    @patch("mimeo.utils.retry.time.sleep")
    def test_retries_on_host_error_with_retryable_status_code(self, mock_sleep) -> None:
        """Retries on HostError carrying a retryable structured status code."""
        calls = []

        def fn():
            calls.append(1)
            if len(calls) == 1:
                raise HostError("gh: Server Error (HTTP 502)", status_code=502)
            return "ok"

        result = retry_with_jitter(fn, retries=2)
        assert result == "ok"
        assert mock_sleep.call_count == 1

    @patch("mimeo.utils.retry.time.sleep")
    def test_does_not_retry_host_error_with_definitive_status_code(self, mock_sleep) -> None:
        """A 404 HostError is definitive -- no retry."""
        calls = []

        def fn():
            calls.append(1)
            raise HostError("gh: Not Found (HTTP 404)", status_code=404)

        with pytest.raises(HostError):
            retry_with_jitter(fn, retries=2)
        assert len(calls) == 1
        mock_sleep.assert_not_called()

    def test_status_code_takes_precedence_over_message_keywords(self) -> None:
        """A definitive code wins even if the message mentions transient keywords."""
        calls = []

        def fn():
            calls.append(1)
            raise HostError("upstream said 502 but (HTTP 400)", status_code=400)

        with pytest.raises(HostError):
            retry_with_jitter(fn, retries=2)
        assert len(calls) == 1

    @patch("mimeo.utils.retry.time.sleep")
    def test_does_not_retry_non_retryable_api_error(self, mock_sleep) -> None:
        """Does not retry on APIError with non-retryable status (e.g. 404)."""
        def fn():
            raise APIError("not found", status_code=404)

        with pytest.raises(APIError) as exc_info:
            retry_with_jitter(fn, retries=3)

        assert exc_info.value.status_code == 404
        mock_sleep.assert_not_called()

    @patch("mimeo.utils.retry.time.sleep")
    def test_does_not_retry_non_retryable_api_error_401(self, mock_sleep) -> None:
        """Does not retry on APIError 401 (auth failure)."""
        def fn():
            raise APIError("unauthorized", status_code=401)

        with pytest.raises(APIError):
            retry_with_jitter(fn, retries=3)

        mock_sleep.assert_not_called()

    @patch("mimeo.utils.retry.time.sleep")
    def test_does_not_retry_configuration_error(self, mock_sleep) -> None:
        """Does not retry on non-retryable exception types."""
        def fn():
            raise ConfigurationError("bad config")

        with pytest.raises(ConfigurationError):
            retry_with_jitter(fn, retries=3)

        mock_sleep.assert_not_called()

    @patch("mimeo.utils.retry.time.sleep")
    def test_does_not_retry_host_error_non_transient(self, mock_sleep) -> None:
        """Does not retry on HostError without transient keywords."""
        def fn():
            raise HostError("Repository already exists")

        with pytest.raises(HostError) as exc_info:
            retry_with_jitter(fn, retries=3)

        assert "already exists" in str(exc_info.value)
        mock_sleep.assert_not_called()

    @patch("mimeo.utils.retry.time.sleep")
    def test_raises_after_max_retries(self, mock_sleep) -> None:
        """Raises the last exception after exhausting all retries."""
        def fn():
            raise APIError("server error", status_code=500)

        with pytest.raises(APIError) as exc_info:
            retry_with_jitter(fn, retries=2)

        assert exc_info.value.status_code == 500
        assert mock_sleep.call_count == 2

    @patch("mimeo.utils.retry.random.uniform")
    @patch("mimeo.utils.retry.time.sleep")
    def test_jitter_is_in_expected_range(self, mock_sleep, mock_uniform) -> None:
        """Sleep duration is base**attempt + uniform(0,1) capped at cap."""
        mock_uniform.return_value = 0.5

        calls = []

        def fn():
            calls.append(1)
            if len(calls) <= 2:
                raise APIError("error", status_code=503)
            return "ok"

        retry_with_jitter(fn, retries=3, base=2.0, cap=30.0)

        # Attempt 0 fails: wait = min(30, 2**0) + 0.5 = 1.0 + 0.5 = 1.5
        # Attempt 1 fails: wait = min(30, 2**1) + 0.5 = 2.0 + 0.5 = 2.5
        assert mock_sleep.call_args_list[0][0][0] == pytest.approx(1.5)
        assert mock_sleep.call_args_list[1][0][0] == pytest.approx(2.5)

    @patch("mimeo.utils.retry.random.uniform")
    @patch("mimeo.utils.retry.time.sleep")
    def test_cap_limits_wait_time(self, mock_sleep, mock_uniform) -> None:
        """Wait time is capped before jitter is added."""
        mock_uniform.return_value = 0.0

        calls = []

        def fn():
            calls.append(1)
            if len(calls) <= 5:
                raise NetworkError("timeout")
            return "ok"

        retry_with_jitter(fn, retries=6, base=2.0, cap=5.0)

        # By attempt 3: 2**3 = 8 > cap=5 -> capped at 5.0 + 0.0 = 5.0
        sleep_values = [c[0][0] for c in mock_sleep.call_args_list]
        assert all(v <= 6.0 for v in sleep_values)  # cap=5 + max jitter=1
        # Verify capping kicks in
        assert sleep_values[3] == pytest.approx(5.0)
