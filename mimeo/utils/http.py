"""HTTP client utilities with retry logic and error handling."""

from typing import Any, Dict, Optional
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from mimeo.exceptions import APIError, NetworkError


class HTTPClient:
    """HTTP client with automatic retries and error handling.

    Provides a simple interface for making HTTP requests with:
    - Automatic retries with exponential backoff
    - Configurable timeouts
    - JSON request/response handling
    - Consistent error handling
    """

    def __init__(
        self,
        base_url: str,
        timeout: int = 30,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ) -> None:
        """Initialize HTTP client.

        Args:
            base_url: Base URL for all requests
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            backoff_factor: Backoff factor for retries (delay = backoff_factor * (2 ** retry_number))
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        # Configure retry strategy
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"],
        )

        # Create session with retry adapter
        self.session = requests.Session()
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _build_url(self, path: str) -> str:
        """Build full URL from base URL and path.

        Args:
            path: API endpoint path

        Returns:
            Full URL
        """
        return urljoin(self.base_url + "/", path.lstrip("/"))

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Handle HTTP response and extract JSON.

        Args:
            response: HTTP response object

        Returns:
            Parsed JSON response

        Raises:
            APIError: If API returns an error status or invalid JSON
        """
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            # Try to extract error message from response body
            try:
                error_data = response.json()
                error_msg = error_data.get("message", str(e))
            except Exception:
                error_msg = str(e)

            raise APIError(
                f"HTTP {response.status_code}: {error_msg}",
                status_code=response.status_code,
            ) from e

        try:
            data: Dict[str, Any] = response.json()
            return data
        except requests.JSONDecodeError as e:
            raise APIError(f"Invalid JSON response: {e}") from e

    def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Send GET request.

        Args:
            path: API endpoint path
            params: Query parameters
            headers: Additional headers

        Returns:
            Parsed JSON response

        Raises:
            NetworkError: If network request fails
            APIError: If API returns an error
        """
        url = self._build_url(path)

        try:
            response = self.session.get(
                url,
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
            return self._handle_response(response)
        except requests.RequestException as e:
            if isinstance(e, requests.HTTPError):
                raise  # Already handled by _handle_response
            raise NetworkError(f"Network request failed: {e}") from e

    def post(
        self,
        path: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Send POST request.

        Args:
            path: API endpoint path
            data: Form data
            json: JSON data
            headers: Additional headers

        Returns:
            Parsed JSON response

        Raises:
            NetworkError: If network request fails
            APIError: If API returns an error
        """
        url = self._build_url(path)

        try:
            response = self.session.post(
                url,
                data=data,
                json=json,
                headers=headers,
                timeout=self.timeout,
            )
            return self._handle_response(response)
        except requests.RequestException as e:
            if isinstance(e, requests.HTTPError):
                raise  # Already handled by _handle_response
            raise NetworkError(f"Network request failed: {e}") from e

    def put(
        self,
        path: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Send PUT request.

        Args:
            path: API endpoint path
            data: Form data
            json: JSON data
            headers: Additional headers

        Returns:
            Parsed JSON response

        Raises:
            NetworkError: If network request fails
            APIError: If API returns an error
        """
        url = self._build_url(path)

        try:
            response = self.session.put(
                url,
                data=data,
                json=json,
                headers=headers,
                timeout=self.timeout,
            )
            return self._handle_response(response)
        except requests.RequestException as e:
            if isinstance(e, requests.HTTPError):
                raise  # Already handled by _handle_response
            raise NetworkError(f"Network request failed: {e}") from e

    def delete(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Send DELETE request.

        Args:
            path: API endpoint path
            params: Query parameters
            headers: Additional headers

        Returns:
            Parsed JSON response

        Raises:
            NetworkError: If network request fails
            APIError: If API returns an error
        """
        url = self._build_url(path)

        try:
            response = self.session.delete(
                url,
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
            return self._handle_response(response)
        except requests.RequestException as e:
            if isinstance(e, requests.HTTPError):
                raise  # Already handled by _handle_response
            raise NetworkError(f"Network request failed: {e}") from e

    def close(self) -> None:
        """Close the HTTP session."""
        self.session.close()

    def __enter__(self) -> "HTTPClient":
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()
