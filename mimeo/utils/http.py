"""HTTP client utilities with error handling."""

from typing import Any, Dict, Optional
from urllib.parse import urljoin

import requests

from mimeo.exceptions import APIError, NetworkError


class HTTPClient:
    """HTTP client with error handling.

    Provides a simple interface for making HTTP requests with:
    - Configurable timeouts
    - JSON request/response handling
    - Consistent error handling

    Retry logic is handled at the provider layer via retry_with_jitter.
    """

    def __init__(
        self,
        base_url: str,
        timeout: int = 30,
    ) -> None:
        """Initialize HTTP client.

        Args:
            base_url: Base URL for all requests
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

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

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Send an HTTP request and parse the JSON response.

        Args:
            method: HTTP method (e.g. "GET", "POST")
            path: API endpoint path
            params: Query parameters
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
            response = self.session.request(
                method,
                url,
                params=params,
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
        return self._request("GET", path, params=params, headers=headers)

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
        return self._request("POST", path, data=data, json=json, headers=headers)

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
        return self._request("PUT", path, data=data, json=json, headers=headers)

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
        return self._request("DELETE", path, params=params, headers=headers)

    def close(self) -> None:
        """Close the HTTP session."""
        self.session.close()

    def __enter__(self) -> "HTTPClient":
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()
