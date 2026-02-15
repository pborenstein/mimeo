"""Porkbun registrar provider implementation."""

import time
from typing import Any, Dict, List

import dns.resolver

from mimeo.exceptions import RegistrarError, DNSError
from mimeo.models import DNSRecord
from mimeo.providers.base import Registrar
from mimeo.utils.http import HTTPClient


# GitHub Pages IP addresses for A records
GITHUB_PAGES_IPS = [
    "185.199.108.153",
    "185.199.109.153",
    "185.199.110.153",
    "185.199.111.153",
]


class PorkbunRegistrar(Registrar):
    """Porkbun registrar provider for DNS management.

    Uses the Porkbun API v3 to configure DNS records for domains.
    API documentation: https://porkbun.com/api/json/v3/documentation
    """

    BASE_URL = "https://api-ipv4.porkbun.com/api/json/v3"

    def __init__(self, api_key: str, secret_key: str) -> None:
        """Initialize Porkbun registrar.

        Args:
            api_key: Porkbun API key (starts with 'pk1_')
            secret_key: Porkbun secret key (starts with 'sk1_')

        Raises:
            RegistrarError: If credentials are invalid
        """
        if not api_key or not secret_key:
            raise RegistrarError("Porkbun API key and secret key are required")

        self.api_key = api_key
        self.secret_key = secret_key
        self.client = HTTPClient(self.BASE_URL)

    def _auth_payload(self) -> Dict[str, str]:
        """Build authentication payload for API requests.

        Returns:
            Dictionary with API credentials
        """
        return {
            "apikey": self.api_key,
            "secretapikey": self.secret_key,
        }

    def _make_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make authenticated API request.

        Args:
            endpoint: API endpoint path
            payload: Request payload (auth will be added)

        Returns:
            API response data

        Raises:
            RegistrarError: If API request fails
        """
        # Add authentication to payload
        full_payload = {**self._auth_payload(), **payload}

        try:
            response = self.client.post(endpoint, json=full_payload)

            # Check API status
            if response.get("status") != "SUCCESS":
                error_msg = response.get("message", "Unknown error")
                raise RegistrarError(f"Porkbun API error: {error_msg}")

            return response
        except Exception as e:
            if isinstance(e, RegistrarError):
                raise
            raise RegistrarError(f"Failed to communicate with Porkbun API: {e}") from e

    def _get_domain_records(self, domain: str) -> List[Dict[str, Any]]:
        """Retrieve all DNS records for a domain.

        Args:
            domain: Domain name

        Returns:
            List of DNS records from API

        Raises:
            RegistrarError: If retrieval fails
        """
        response = self._make_request(
            f"/dns/retrieve/{domain}",
            {},
        )
        records: List[Dict[str, Any]] = response.get("records", [])
        return records

    def _delete_record(self, domain: str, record_id: str) -> None:
        """Delete a DNS record.

        Args:
            domain: Domain name
            record_id: Record ID to delete

        Raises:
            RegistrarError: If deletion fails
        """
        self._make_request(
            f"/dns/delete/{domain}/{record_id}",
            {},
        )

    def _create_record(self, domain: str, record: DNSRecord) -> None:
        """Create a DNS record.

        Args:
            domain: Domain name
            record: DNS record to create

        Raises:
            RegistrarError: If creation fails
        """
        payload = {
            "type": record.type,
            "name": record.name,
            "content": record.content,
            "ttl": str(record.ttl),
        }

        self._make_request(
            f"/dns/create/{domain}",
            payload,
        )

    def _normalize_record_name(self, name: str, domain: str) -> str:
        """Normalize record name for comparison.

        Porkbun API can return:
        - Apex records as "" or the full domain name
        - Subdomains as "www" or "www.domain.com"

        We normalize to our internal representation (empty string for apex,
        subdomain part only for subdomains).

        Args:
            name: Record name from API or internal representation
            domain: Domain name

        Returns:
            Normalized name (empty string for apex, subdomain only otherwise)
        """
        # Apex records can be represented as "", "@", or the full domain
        if name in ("", "@", domain):
            return ""

        # If the name ends with the domain, strip it off
        # e.g., "www.example.com" -> "www"
        if name.endswith(f".{domain}"):
            return name[: -len(domain) - 1]

        return name

    def configure_dns(self, domain: str, records: List[DNSRecord]) -> None:
        """Configure DNS records for a domain.

        This will:
        1. Retrieve existing records
        2. Delete records that conflict with the new configuration
        3. Create new records

        Args:
            domain: Domain name to configure
            records: List of DNS records to create/update

        Raises:
            RegistrarError: If DNS configuration fails
        """
        try:
            # Get existing records
            existing_records = self._get_domain_records(domain)

            # Build set of (type, name) tuples we want to manage
            # Normalize names for consistent comparison
            managed_records = {
                (r.type, self._normalize_record_name(r.name, domain))
                for r in records
            }

            # Delete conflicting existing records
            for existing in existing_records:
                record_type = existing.get("type", "")
                record_name = existing.get("name", "")
                record_id = existing.get("id", "")

                # Normalize the existing record name for comparison
                normalized_name = self._normalize_record_name(record_name, domain)

                # Delete if this record type/name combination is in our managed set
                if (record_type, normalized_name) in managed_records:
                    self._delete_record(domain, record_id)
                # Also delete ALIAS records at apex when creating A records
                # (Porkbun doesn't allow both at the same location)
                elif (
                    record_type == "ALIAS"
                    and normalized_name == ""
                    and ("A", "") in managed_records
                ):
                    self._delete_record(domain, record_id)

            # Create new records
            for record in records:
                self._create_record(domain, record)

        except Exception as e:
            if isinstance(e, RegistrarError):
                raise
            raise RegistrarError(f"Failed to configure DNS for {domain}: {e}") from e

    def verify_dns(
        self,
        domain: str,
        records: List[DNSRecord],
        max_attempts: int = 10,
        delay: int = 5,
    ) -> bool:
        """Verify DNS records have propagated.

        Args:
            domain: Domain name to verify
            records: Expected DNS records
            max_attempts: Maximum number of verification attempts
            delay: Delay between attempts in seconds

        Returns:
            True if all records are verified, False otherwise

        Raises:
            DNSError: If verification fails unexpectedly
        """
        resolver = dns.resolver.Resolver()
        resolver.timeout = 5
        resolver.lifetime = 5

        for attempt in range(max_attempts):
            try:
                all_verified = True

                for record in records:
                    # Build query name (apex domain uses @ or empty string)
                    if record.name in ("", "@"):
                        query_name = domain
                    else:
                        query_name = f"{record.name}.{domain}"

                    try:
                        # Query DNS
                        answers = resolver.resolve(query_name, record.type)

                        # Check if expected content is in answers
                        found = False
                        for rdata in answers:
                            # Compare content (normalize trailing dots for CNAME)
                            actual_content = str(rdata).rstrip(".")
                            expected_content = record.content.rstrip(".")

                            if actual_content == expected_content:
                                found = True
                                break

                        if not found:
                            all_verified = False
                            break

                    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                        # Record doesn't exist yet
                        all_verified = False
                        break
                    except dns.exception.Timeout:
                        # DNS timeout, try again
                        all_verified = False
                        break

                # If all records verified, we're done
                if all_verified:
                    return True

                # Wait before next attempt (except on last attempt)
                if attempt < max_attempts - 1:
                    time.sleep(delay)

            except Exception as e:
                raise DNSError(f"DNS verification failed unexpectedly: {e}") from e

        # All attempts exhausted
        return False

    @staticmethod
    def github_pages_records(domain: str, github_user: str) -> List[DNSRecord]:
        """Generate DNS records for GitHub Pages.

        Args:
            domain: Domain name
            github_user: GitHub username or organization

        Returns:
            List of DNS records (4 A records + 1 CNAME for www)
        """
        records = []

        # A records for apex domain
        for ip in GITHUB_PAGES_IPS:
            records.append(
                DNSRecord(
                    type="A",
                    name="",  # Apex domain
                    content=ip,
                    ttl=600,
                )
            )

        # CNAME for www subdomain
        records.append(
            DNSRecord(
                type="CNAME",
                name="www",
                content=f"{github_user}.github.io",
                ttl=600,
            )
        )

        return records

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self) -> "PorkbunRegistrar":
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()
