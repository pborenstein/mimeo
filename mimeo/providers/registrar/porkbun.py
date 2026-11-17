"""Porkbun registrar and DNS provider implementations."""

import threading
import time
from typing import Any, Dict, List

import dns.resolver

from mimeo.exceptions import RegistrarError
from mimeo.models import DNSRecord, relative_name
from mimeo.providers.base import DNSProvider, Registrar
from mimeo.utils.http import HTTPClient
from mimeo.utils.retry import retry_with_jitter


# Porkbun authoritative nameservers
PORKBUN_NAMESERVERS = [
    "curitiba.ns.porkbun.com",
    "fortaleza.ns.porkbun.com",
    "maceio.ns.porkbun.com",
    "salvador.ns.porkbun.com",
]


def lookup_nameservers(domain: str) -> list[str]:
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


def public_nameservers(domain: str) -> list[str] | None:
    """Ask public DNS for a domain's nameservers, telling "none" from "could not ask".

    Returns:
        The nameservers; an empty list when DNS says the name does not
        exist or has no nameservers; None when the question could not
        be answered (timeout, no network), so nothing can be concluded.
    """
    resolver = dns.resolver.Resolver()
    resolver.timeout = 5
    resolver.lifetime = 5
    try:
        answers = resolver.resolve(domain, "NS")
        return sorted(str(r).rstrip(".").lower() for r in answers)
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return []
    except Exception:
        return None


# Seen 2026-11-16: with five workers sending requests as fast as they
# could, three fleet sweeps out of five lost one domain to a 503 that
# outlasted three retries. Whether Porkbun publishes a request limit is
# unverified; the interval is this code's choice. So every
# request from this process, whichever worker or client object sends it,
# starts at least this long after the last.
MIN_INTERVAL = 0.25
_pace_lock = threading.Lock()
_next_start = 0.0


def _pace() -> None:
    """Wait for this request's turn."""
    global _next_start
    with _pace_lock:
        now = time.monotonic()
        start = max(now, _next_start)
        _next_start = start + MIN_INTERVAL
    if start > now:
        time.sleep(start - now)


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
            def _send() -> Dict[str, Any]:
                _pace()
                return self.client.post(endpoint, json=full_payload)

            # Five retries wait about 1, 2, 4, 8 and 16 seconds.
            response = retry_with_jitter(_send, retries=5)
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

    def get_nameservers(self, domain: str) -> list[str]:
        """Return the nameservers set for the domain at the registrar.

        This is the registrar's own setting, not a public DNS lookup, so
        it is current the moment set_nameservers returns.

        Raises:
            RegistrarError: If the API call fails
        """
        response = self._make_request(f"/domain/getNs/{domain}", {})
        return sorted(str(n).rstrip(".").lower() for n in response.get("ns") or [])

    def set_nameservers(self, domain: str, nameservers: list[str]) -> None:
        """Set the domain's nameservers.

        Raises:
            RegistrarError: If the API call fails
        """
        self._make_request(f"/domain/updateNs/{domain}", {"ns": list(nameservers)})

    def dnssec_enabled(self, domain: str) -> bool:
        """Return True when the registry holds DNSSEC records for the domain.

        Raises:
            RegistrarError: If the API call fails
        """
        response = self._make_request(f"/dns/getDnssecRecords/{domain}", {})
        return bool(response.get("records"))

    def list_domains(self) -> List[Dict[str, Any]]:
        """Return all domains in the Porkbun account.

        Returns:
            List of domain info dicts from the Porkbun API.

        Raises:
            RegistrarError: If the API call fails
        """
        response = self._make_request("/domain/listAll", {})
        domains: List[Dict[str, Any]] = response.get("domains", [])
        return domains

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

    name = "porkbun"

    def serves(self, nameservers: list[str]) -> bool:
        """True when every nameserver is one of Porkbun's."""
        return bool(nameservers) and all(n.endswith(".porkbun.com") for n in nameservers)

    def zone_exists(self, zone: str) -> bool:
        """Porkbun keeps a zone for every domain registered there."""
        return True

    def create_zone(self, zone: str) -> None:
        """Nothing to do: the zone exists for every registered domain."""

    def zone_nameservers(self, zone: str) -> list[str]:
        """Porkbun answers for every zone on the same four nameservers."""
        return sorted(PORKBUN_NAMESERVERS)

    def list_records(self, zone: str) -> list[DNSRecord]:
        """Every record in the zone, names relative to the zone.

        Raises:
            RegistrarError: If the API call fails
        """
        records: list[DNSRecord] = []
        for raw in self.get_domain_records(zone):
            record_type = str(raw.get("type", ""))
            prio = raw.get("prio")
            records.append(
                DNSRecord(
                    type=record_type,
                    name=relative_name(str(raw.get("name", "")), zone),
                    content=str(raw.get("content", "")),
                    ttl=int(raw.get("ttl") or 600),
                    priority=(
                        int(str(prio))
                        if record_type in ("MX", "SRV") and prio not in (None, "")
                        else None
                    ),
                    id=str(raw.get("id", "")),
                )
            )
        return records

    def add_record(self, zone: str, record: DNSRecord) -> None:
        """Add a record. Porkbun's minimum TTL is 600 seconds.

        Raises:
            RegistrarError: If the API call fails
        """
        payload = {
            "type": record.type,
            "name": record.name,
            "content": record.content,
            "ttl": str(max(record.ttl, 600)),
        }
        if record.priority is not None:
            payload["prio"] = str(record.priority)
        self._make_request(f"/dns/create/{zone}", payload)

    def delete_record(self, zone: str, record: DNSRecord) -> None:
        """Delete a record by the ID list_records returned.

        Raises:
            RegistrarError: If the record has no ID or the API call fails
        """
        if not record.id:
            raise RegistrarError(f"Cannot delete a record without an ID: {record.describe()}")
        self._delete_record(zone, record.id)

    def get_domain_records(self, domain: str) -> List[Dict[str, Any]]:
        """Retrieve all DNS records for a domain.

        Args:
            domain: Domain name to query

        Returns:
            List of record dicts from the Porkbun API.

        Raises:
            RegistrarError: If the API call fails
        """
        response = self._make_request(f"/dns/retrieve/{domain}", {})
        records: List[Dict[str, Any]] = response.get("records", [])
        return records

    def _delete_record(self, domain: str, record_id: str) -> None:
        """Delete a DNS record."""
        self._make_request(f"/dns/delete/{domain}/{record_id}", {})

    # No stops_on_leaving: Porkbun's mail forwarding keeps working when the
    # zone is served elsewhere, as long as the MX records still point at
    # fwd1/fwd2.porkbun.com, and delegate copies them. Porkbun's guide
    # "How to use Porkbun email when your DNS is hosted elsewhere",
    # https://kb.porkbun.com/article/47 (checked 2026-11-18).

    def __enter__(self) -> "PorkbunDNSProvider":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
