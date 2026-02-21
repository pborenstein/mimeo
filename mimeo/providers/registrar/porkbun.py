"""Porkbun registrar and DNS provider implementations."""

import time
from typing import Any, Dict, List

import dns.resolver

from mimeo.exceptions import RegistrarError, DNSError
from mimeo.models import DNSRecord, NameserverCheckResult
from mimeo.providers.base import DNSProvider, Registrar
from mimeo.utils.http import HTTPClient
from mimeo.utils.retry import retry_with_jitter


# GitHub Pages IP addresses for A records
GITHUB_PAGES_IPS = [
    "185.199.108.153",
    "185.199.109.153",
    "185.199.110.153",
    "185.199.111.153",
]

# Porkbun authoritative nameservers
PORKBUN_NAMESERVERS = [
    "curitiba.ns.porkbun.com",
    "fortaleza.ns.porkbun.com",
    "maceio.ns.porkbun.com",
    "salvador.ns.porkbun.com",
]


def _lookup_nameservers(domain: str) -> list[str]:
    """Look up the NS records for a domain via public DNS.

    Args:
        domain: Domain name to query

    Returns:
        Sorted list of nameserver hostnames (lowercase, no trailing dot)
    """
    resolver = dns.resolver.Resolver()
    resolver.timeout = 5
    resolver.lifetime = 5
    try:
        answers = resolver.resolve(domain, "NS")
        return sorted(str(r).rstrip(".").lower() for r in answers)
    except Exception:
        return []


class _PorkbunClient:
    """Shared Porkbun API client plumbing."""

    BASE_URL = "https://api-ipv4.porkbun.com/api/json/v3"

    def __init__(self, api_key: str, secret_key: str) -> None:
        if not api_key or not secret_key:
            raise RegistrarError("Porkbun API key and secret key are required")
        self.api_key = api_key
        self.secret_key = secret_key
        self.client = HTTPClient(self.BASE_URL)

    def _auth_payload(self) -> Dict[str, str]:
        return {
            "apikey": self.api_key,
            "secretapikey": self.secret_key,
        }

    def _make_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        full_payload = {**self._auth_payload(), **payload}
        try:
            response = retry_with_jitter(
                lambda: self.client.post(endpoint, json=full_payload)
            )
            if response.get("status") != "SUCCESS":
                error_msg = response.get("message", "Unknown error")
                raise RegistrarError(f"Porkbun API error: {error_msg}")
            return response
        except Exception as e:
            if isinstance(e, RegistrarError):
                raise
            raise RegistrarError(f"Failed to communicate with Porkbun API: {e}") from e

    def close(self) -> None:
        self.client.close()


class PorkbunRegistrar(_PorkbunClient, Registrar):
    """Porkbun registrar provider.

    Manages domain registration concerns. Does not manage DNS records.
    API documentation: https://porkbun.com/api/json/v3/documentation
    """

    def __init__(self, api_key: str, secret_key: str) -> None:
        """Initialize Porkbun registrar.

        Args:
            api_key: Porkbun API key (starts with 'pk1_')
            secret_key: Porkbun secret key (starts with 'sk1_')

        Raises:
            RegistrarError: If credentials are invalid
        """
        _PorkbunClient.__init__(self, api_key, secret_key)

    def check_nameservers(self, domain: str) -> NameserverCheckResult:
        """Check whether the domain's NS records point to Porkbun.

        Args:
            domain: Domain name to check

        Returns:
            NameserverCheckResult with ok flag and actual/expected nameservers
        """
        actual = _lookup_nameservers(domain)
        expected = sorted(PORKBUN_NAMESERVERS)
        ok = actual == expected
        return NameserverCheckResult(ok=ok, actual=actual, expected=expected)

    def update_nameservers(self, domain: str) -> None:
        """Reset the domain's nameservers to Porkbun defaults.

        Args:
            domain: Domain name to update

        Raises:
            RegistrarError: If the API call fails
        """
        self._make_request(
            f"/domain/updateNs/{domain}",
            {"ns": PORKBUN_NAMESERVERS},
        )

    def __enter__(self) -> "PorkbunRegistrar":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class PorkbunDNSProvider(_PorkbunClient, DNSProvider):
    """Porkbun DNS provider for DNS record management.

    Uses the Porkbun API v3 to configure DNS records for domains.
    API documentation: https://porkbun.com/api/json/v3/documentation
    """

    def __init__(self, api_key: str, secret_key: str) -> None:
        """Initialize Porkbun DNS provider.

        Args:
            api_key: Porkbun API key (starts with 'pk1_')
            secret_key: Porkbun secret key (starts with 'sk1_')

        Raises:
            RegistrarError: If credentials are invalid
        """
        _PorkbunClient.__init__(self, api_key, secret_key)

    def check_nameservers(self, domain: str) -> NameserverCheckResult:
        """Check whether the domain's NS records point to Porkbun.

        Args:
            domain: Domain name to check

        Returns:
            NameserverCheckResult with ok flag and actual/expected nameservers
        """
        actual = _lookup_nameservers(domain)
        expected = sorted(PORKBUN_NAMESERVERS)
        ok = actual == expected
        return NameserverCheckResult(ok=ok, actual=actual, expected=expected)

    def _get_domain_records(self, domain: str) -> List[Dict[str, Any]]:
        """Retrieve all DNS records for a domain."""
        response = self._make_request(f"/dns/retrieve/{domain}", {})
        records: List[Dict[str, Any]] = response.get("records", [])
        return records

    def _delete_record(self, domain: str, record_id: str) -> None:
        """Delete a DNS record."""
        self._make_request(f"/dns/delete/{domain}/{record_id}", {})

    def _create_record(self, domain: str, record: DNSRecord) -> None:
        """Create a DNS record."""
        payload = {
            "type": record.type,
            "name": record.name,
            "content": record.content,
            "ttl": str(record.ttl),
        }
        self._make_request(f"/dns/create/{domain}", payload)

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
        if name in ("", "@", domain):
            return ""
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
            existing_records = self._get_domain_records(domain)

            managed_records = {
                (r.type, self._normalize_record_name(r.name, domain))
                for r in records
            }

            for existing in existing_records:
                record_type = existing.get("type", "")
                record_name = existing.get("name", "")
                record_id = existing.get("id", "")

                normalized_name = self._normalize_record_name(record_name, domain)

                if (record_type, normalized_name) in managed_records:
                    self._delete_record(domain, record_id)
                elif (
                    record_type == "ALIAS"
                    and normalized_name == ""
                    and ("A", "") in managed_records
                ):
                    self._delete_record(domain, record_id)

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
                    if record.name in ("", "@"):
                        query_name = domain
                    else:
                        query_name = f"{record.name}.{domain}"

                    try:
                        answers = resolver.resolve(query_name, record.type)

                        found = False
                        for rdata in answers:
                            actual_content = str(rdata).rstrip(".")
                            expected_content = record.content.rstrip(".")

                            if actual_content == expected_content:
                                found = True
                                break

                        if not found:
                            all_verified = False
                            break

                    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                        all_verified = False
                        break
                    except dns.exception.Timeout:
                        all_verified = False
                        break

                if all_verified:
                    return True

                if attempt < max_attempts - 1:
                    time.sleep(delay)

            except Exception as e:
                raise DNSError(f"DNS verification failed unexpectedly: {e}") from e

        return False

    def check_dns_drift(self, domain: str, expected: List[DNSRecord]) -> Dict[str, Any]:
        """Compare expected DNS records against live Porkbun records.

        Args:
            domain: Domain name to check
            expected: Expected DNS records

        Returns:
            Dict with keys:
              - status: "ok" | "drift" | "missing"
              - missing: list of expected records not found in Porkbun
              - extra: list of Porkbun records not in expected set
        """
        live_records = self._get_domain_records(domain)

        live_set = {
            (
                r.get("type", ""),
                self._normalize_record_name(r.get("name", ""), domain),
                r.get("content", "").rstrip("."),
            )
            for r in live_records
        }

        expected_set = {
            (rec.type, self._normalize_record_name(rec.name, domain), rec.content.rstrip("."))
            for rec in expected
        }

        missing = [
            {"type": t, "name": n or "@", "content": c}
            for t, n, c in expected_set - live_set
        ]
        extra = [
            {"type": t, "name": n or "@", "content": c}
            for t, n, c in live_set - expected_set
            if t in {rec.type for rec in expected}
        ]

        if missing:
            status = "missing"
        elif extra:
            status = "drift"
        else:
            status = "ok"

        return {"status": status, "missing": missing, "extra": extra}

    def __enter__(self) -> "PorkbunDNSProvider":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
