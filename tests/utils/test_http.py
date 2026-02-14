"""Tests for HTTP client utilities."""

import pytest
import responses
from requests.exceptions import ConnectionError, Timeout

from mimeo.exceptions import APIError, NetworkError
from mimeo.utils.http import HTTPClient


class TestHTTPClient:
    """Tests for HTTPClient class."""

    @pytest.fixture
    def client(self) -> HTTPClient:
        """Create HTTP client for testing."""
        return HTTPClient(base_url="https://api.example.com")

    def test_initialization(self) -> None:
        """Test HTTP client initialization."""
        client = HTTPClient(
            base_url="https://api.example.com",
            timeout=60,
            max_retries=5,
            backoff_factor=1.0,
        )
        assert client.base_url == "https://api.example.com"
        assert client.timeout == 60

    def test_base_url_trailing_slash(self) -> None:
        """Test that trailing slash is removed from base URL."""
        client = HTTPClient(base_url="https://api.example.com/")
        assert client.base_url == "https://api.example.com"

    @responses.activate
    def test_get_success(self, client: HTTPClient) -> None:
        """Test successful GET request."""
        responses.add(
            responses.GET,
            "https://api.example.com/users",
            json={"users": ["alice", "bob"]},
            status=200,
        )

        result = client.get("/users")
        assert result == {"users": ["alice", "bob"]}

    @responses.activate
    def test_get_with_params(self, client: HTTPClient) -> None:
        """Test GET request with query parameters."""
        responses.add(
            responses.GET,
            "https://api.example.com/search?q=test&limit=10",
            json={"results": []},
            status=200,
        )

        result = client.get("/search", params={"q": "test", "limit": 10})
        assert result == {"results": []}

    @responses.activate
    def test_get_with_headers(self, client: HTTPClient) -> None:
        """Test GET request with custom headers."""
        def request_callback(request):
            assert request.headers["X-Custom-Header"] == "test-value"
            return (200, {}, '{"status": "ok"}')

        responses.add_callback(
            responses.GET,
            "https://api.example.com/data",
            callback=request_callback,
        )

        result = client.get("/data", headers={"X-Custom-Header": "test-value"})
        assert result == {"status": "ok"}

    @responses.activate
    def test_post_success(self, client: HTTPClient) -> None:
        """Test successful POST request."""
        responses.add(
            responses.POST,
            "https://api.example.com/users",
            json={"id": "123", "name": "alice"},
            status=201,
        )

        result = client.post("/users", json={"name": "alice"})
        assert result == {"id": "123", "name": "alice"}

    @responses.activate
    def test_post_with_data(self, client: HTTPClient) -> None:
        """Test POST request with form data."""
        def request_callback(request):
            assert request.body == "key=value"
            return (200, {}, '{"status": "created"}')

        responses.add_callback(
            responses.POST,
            "https://api.example.com/form",
            callback=request_callback,
        )

        result = client.post("/form", data={"key": "value"})
        assert result == {"status": "created"}

    @responses.activate
    def test_put_success(self, client: HTTPClient) -> None:
        """Test successful PUT request."""
        responses.add(
            responses.PUT,
            "https://api.example.com/users/123",
            json={"id": "123", "name": "alice-updated"},
            status=200,
        )

        result = client.put("/users/123", json={"name": "alice-updated"})
        assert result == {"id": "123", "name": "alice-updated"}

    @responses.activate
    def test_delete_success(self, client: HTTPClient) -> None:
        """Test successful DELETE request."""
        responses.add(
            responses.DELETE,
            "https://api.example.com/users/123",
            json={"status": "deleted"},
            status=200,
        )

        result = client.delete("/users/123")
        assert result == {"status": "deleted"}

    @responses.activate
    def test_http_error_with_json_message(self, client: HTTPClient) -> None:
        """Test HTTP error with JSON error message."""
        responses.add(
            responses.GET,
            "https://api.example.com/users",
            json={"message": "Not found"},
            status=404,
        )

        with pytest.raises(APIError) as exc_info:
            client.get("/users")

        assert "404" in str(exc_info.value)
        assert "Not found" in str(exc_info.value)
        assert exc_info.value.status_code == 404

    @responses.activate
    def test_http_error_without_json(self, client: HTTPClient) -> None:
        """Test HTTP error without JSON response."""
        # Use 404 instead of 500 to avoid retry logic
        responses.add(
            responses.GET,
            "https://api.example.com/users",
            body="Not Found",
            status=404,
        )

        with pytest.raises(APIError) as exc_info:
            client.get("/users")

        assert "404" in str(exc_info.value)
        assert exc_info.value.status_code == 404

    @responses.activate
    def test_invalid_json_response(self, client: HTTPClient) -> None:
        """Test handling of invalid JSON response."""
        responses.add(
            responses.GET,
            "https://api.example.com/users",
            body="not valid json",
            status=200,
        )

        with pytest.raises(APIError) as exc_info:
            client.get("/users")

        assert "Invalid JSON response" in str(exc_info.value)

    @responses.activate
    def test_network_error(self, client: HTTPClient) -> None:
        """Test handling of network errors."""
        responses.add(
            responses.GET,
            "https://api.example.com/users",
            body=ConnectionError("Network unreachable"),
        )

        with pytest.raises(NetworkError) as exc_info:
            client.get("/users")

        assert "Network request failed" in str(exc_info.value)

    @responses.activate
    def test_timeout_error(self, client: HTTPClient) -> None:
        """Test handling of timeout errors."""
        responses.add(
            responses.GET,
            "https://api.example.com/users",
            body=Timeout("Request timed out"),
        )

        with pytest.raises(NetworkError) as exc_info:
            client.get("/users")

        assert "Network request failed" in str(exc_info.value)

    @responses.activate
    def test_retry_on_server_error(self) -> None:
        """Test that client retries on server errors."""
        # First two requests fail, third succeeds
        responses.add(
            responses.GET,
            "https://api.example.com/users",
            status=503,
        )
        responses.add(
            responses.GET,
            "https://api.example.com/users",
            status=503,
        )
        responses.add(
            responses.GET,
            "https://api.example.com/users",
            json={"users": []},
            status=200,
        )

        client = HTTPClient(
            base_url="https://api.example.com",
            max_retries=2,
            backoff_factor=0.1,  # Fast retries for testing
        )

        result = client.get("/users")
        assert result == {"users": []}
        assert len(responses.calls) == 3  # Verify retry happened

    def test_context_manager(self) -> None:
        """Test HTTP client as context manager."""
        with HTTPClient(base_url="https://api.example.com") as client:
            assert client.session is not None

        # Session should be closed after context exit
        # (no direct way to test this without internal access)

    def test_build_url_with_leading_slash(self, client: HTTPClient) -> None:
        """Test URL building with leading slash in path."""
        url = client._build_url("/users")
        assert url == "https://api.example.com/users"

    def test_build_url_without_leading_slash(self, client: HTTPClient) -> None:
        """Test URL building without leading slash in path."""
        url = client._build_url("users")
        assert url == "https://api.example.com/users"

    def test_build_url_with_nested_path(self, client: HTTPClient) -> None:
        """Test URL building with nested path."""
        url = client._build_url("/api/v1/users")
        assert url == "https://api.example.com/api/v1/users"
