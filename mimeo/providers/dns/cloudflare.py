"""Cloudflare DNS provider.

Cloudflare holds zones and records; it is never the registrar here.
API reference: https://developers.cloudflare.com/api/
"""

from typing import Any, Dict

from mimeo.exceptions import APIError
from mimeo.models import DNSRecord, relative_name
from mimeo.providers.base import DNSProvider
from mimeo.utils.http import HTTPClient
from mimeo.utils.retry import retry_with_jitter

# ttl 1 is Cloudflare's "automatic"; proxied records always use it.
_AUTO_TTL = 1
_PRIORITY_TYPES = frozenset({"MX", "SRV", "URI"})


class CloudflareDNS(DNSProvider):
    """Cloudflare zones and records, through the v4 API with a bearer token."""

    name = "cloudflare"
    # Cloudflare has no ALIAS type; it flattens a CNAME at the apex instead.
    unsupported_types = frozenset({"ALIAS"})
    BASE_URL = "https://api.cloudflare.com/client/v4"

    def __init__(self, api_token: str, account_id: str | None = None) -> None:
        """Initialize the provider.

        Args:
            api_token: API token with zone read and DNS edit permissions
            account_id: Account that new zones are created in (needed
                only by create_zone)

        Raises:
            APIError: If no token is given
        """
        if not api_token:
            raise APIError("Cloudflare API token is required")
        self.api_token = api_token
        self.account_id = account_id
        self.client = HTTPClient(self.BASE_URL)
        self._zone_cache: Dict[str, Dict[str, Any]] = {}

    def _call(
        self,
        method: str,
        path: str,
        params: Dict[str, Any] | None = None,
        json: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Make one API call and return the whole response envelope.

        Raises:
            APIError: On an HTTP error or an envelope with success false
        """
        headers = {"Authorization": f"Bearer {self.api_token}"}
        response = retry_with_jitter(
            lambda: self.client._request(method, path, params=params, json=json, headers=headers)
        )
        if not response.get("success", False):
            errors = response.get("errors") or []
            detail = "; ".join(str(e.get("message", e)) for e in errors) or "unknown error"
            raise APIError(f"Cloudflare API error: {detail}")
        return response

    def _zone(self, zone: str) -> Dict[str, Any] | None:
        """Look up a zone by name; None when the account has no such zone."""
        if zone in self._zone_cache:
            return self._zone_cache[zone]
        result = self._call("GET", "/zones", params={"name": zone}).get("result") or []
        if not result:
            return None
        self._zone_cache[zone] = result[0]
        return self._zone_cache[zone]

    def _zone_id(self, zone: str) -> str:
        found = self._zone(zone)
        if found is None:
            raise APIError(f"Cloudflare has no zone {zone}", status_code=404)
        return str(found["id"])

    def serves(self, nameservers: list[str]) -> bool:
        """True when every nameserver is one of Cloudflare's."""
        return bool(nameservers) and all(n.endswith(".ns.cloudflare.com") for n in nameservers)

    def zone_exists(self, zone: str) -> bool:
        """True when the account has the zone."""
        return self._zone(zone) is not None

    def create_zone(self, zone: str) -> None:
        """Create a full-setup zone in the configured account.

        Raises:
            APIError: If no account ID is configured or the call fails
        """
        if self._zone(zone) is not None:
            return
        if not self.account_id:
            raise APIError(
                "Creating a Cloudflare zone needs cloudflare.account_id in the config"
            )
        response = self._call(
            "POST",
            "/zones",
            json={"name": zone, "account": {"id": self.account_id}, "type": "full"},
        )
        self._zone_cache[zone] = response["result"]

    def zone_nameservers(self, zone: str) -> list[str]:
        """The two nameservers Cloudflare assigned to the zone."""
        found = self._zone(zone)
        if found is None:
            raise APIError(f"Cloudflare has no zone {zone}", status_code=404)
        return sorted(str(n).rstrip(".").lower() for n in found.get("name_servers") or [])

    def list_records(self, zone: str) -> list[DNSRecord]:
        """Every record in the zone, following pagination."""
        zone_id = self._zone_id(zone)
        records: list[DNSRecord] = []
        page = 1
        while True:
            response = self._call(
                "GET",
                f"/zones/{zone_id}/dns_records",
                params={"per_page": 100, "page": page},
            )
            for raw in response.get("result") or []:
                priority = raw.get("priority")
                records.append(
                    DNSRecord(
                        type=str(raw.get("type", "")),
                        name=relative_name(str(raw.get("name", "")), zone),
                        content=str(raw.get("content", "")),
                        ttl=int(raw.get("ttl") or _AUTO_TTL),
                        priority=int(priority) if priority is not None else None,
                        proxied=bool(raw.get("proxied", False)),
                        id=str(raw.get("id", "")),
                    )
                )
            info = response.get("result_info") or {}
            if page >= int(info.get("total_pages") or 1):
                return records
            page += 1

    def add_record(self, zone: str, record: DNSRecord) -> None:
        """Add a record. DNS-only unless the record says proxied."""
        proxied = bool(record.proxied)
        body: Dict[str, Any] = {
            "type": record.type,
            "name": f"{record.name}.{zone}" if record.name else zone,
            "content": record.content,
            "ttl": _AUTO_TTL if proxied else record.ttl,
        }
        if record.type in ("A", "AAAA", "CNAME"):
            body["proxied"] = proxied
        if record.type in _PRIORITY_TYPES and record.priority is not None:
            body["priority"] = record.priority
        self._call("POST", f"/zones/{self._zone_id(zone)}/dns_records", json=body)

    def delete_record(self, zone: str, record: DNSRecord) -> None:
        """Delete a record by the ID list_records returned."""
        if not record.id:
            raise APIError(f"Cannot delete a record without an ID: {record.describe()}")
        self._call("DELETE", f"/zones/{self._zone_id(zone)}/dns_records/{record.id}")

    def set_proxied(self, zone: str, record: DNSRecord, proxied: bool) -> None:
        """Turn the proxy on or off for a record, by the ID list_records returned."""
        if not record.id:
            raise APIError(f"Cannot change a record without an ID: {record.describe()}")
        self._call(
            "PATCH",
            f"/zones/{self._zone_id(zone)}/dns_records/{record.id}",
            json={"proxied": proxied},
        )

    def stops_on_leaving(self, zone: str, records: list[DNSRecord]) -> list[str]:
        """Email Routing and the proxy work only while Cloudflare serves the zone.

        Email Routing needing Cloudflare as the zone's DNS is from how the
        service is set up in the dashboard; not checked against
        Cloudflare's documentation (as of 2026-11-17).
        """
        stops: list[str] = []
        if any(
            r.type == "MX" and r.content.rstrip(".").lower().endswith(".mx.cloudflare.net")
            for r in records
        ):
            stops.append(
                f"Mail to {zone} is delivered by Cloudflare Email Routing (the MX records"
                " point at mx.cloudflare.net), which works only while Cloudflare serves"
                " the zone. Incoming mail would stop."
            )
        proxied = sorted({f"{r.type} {r.name or '@'}" for r in records if r.proxied})
        if proxied:
            stops.append(
                f"Cloudflare's proxy is on for {', '.join(proxied)}. The copies are"
                " plain records, so visitors would reach the site directly and anything"
                " set up in Cloudflare for those names (caching, rules, redirects) would"
                " stop applying."
            )
        return stops

    def close(self) -> None:
        """Close the HTTP session."""
        self.client.close()

    def __enter__(self) -> "CloudflareDNS":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
