"""Tests for the Cloudflare DNS provider."""

from typing import Any
from unittest.mock import patch

import pytest

from mimeo.exceptions import APIError
from mimeo.models import DNSRecord
from mimeo.providers.dns.cloudflare import CloudflareDNS

ZONE = {"id": "z1", "name": "example.com", "name_servers": ["Ada.ns.cloudflare.com.", "bob.ns.cloudflare.com"]}


def ok(result: Any, total_pages: int = 1) -> dict[str, Any]:
    return {"success": True, "errors": [], "result": result, "result_info": {"total_pages": total_pages}}


@pytest.fixture
def cf() -> CloudflareDNS:
    return CloudflareDNS("token", account_id="acct")


def test_requires_a_token() -> None:
    with pytest.raises(APIError):
        CloudflareDNS("")


def test_serves_only_cloudflare_nameservers(cf: CloudflareDNS) -> None:
    assert cf.serves(["ada.ns.cloudflare.com", "bob.ns.cloudflare.com"])
    assert not cf.serves(["ada.ns.cloudflare.com", "maceio.ns.porkbun.com"])
    assert not cf.serves([])


def test_calls_carry_the_bearer_token(cf: CloudflareDNS) -> None:
    with patch.object(cf.client, "_request", return_value=ok([ZONE])) as request:
        assert cf.zone_exists("example.com")
    request.assert_called_once_with(
        "GET", "/zones", params={"name": "example.com"}, json=None,
        headers={"Authorization": "Bearer token"},
    )


def test_zone_lookup_is_cached(cf: CloudflareDNS) -> None:
    with patch.object(cf.client, "_request", return_value=ok([ZONE])) as request:
        cf.zone_exists("example.com")
        assert cf.zone_nameservers("example.com") == ["ada.ns.cloudflare.com", "bob.ns.cloudflare.com"]
    assert request.call_count == 1


def test_missing_zone(cf: CloudflareDNS) -> None:
    with patch.object(cf.client, "_request", return_value=ok([])):
        assert not cf.zone_exists("example.com")
        with pytest.raises(APIError) as exc_info:
            cf.list_records("example.com")
    assert exc_info.value.status_code == 404


def test_envelope_failure_raises_with_the_error_messages(cf: CloudflareDNS) -> None:
    failure = {"success": False, "errors": [{"code": 1003, "message": "Invalid zone"}], "result": None}
    with patch.object(cf.client, "_request", return_value=failure):
        with pytest.raises(APIError, match="Invalid zone"):
            cf.zone_exists("example.com")


def test_create_zone_posts_account_and_full_type(cf: CloudflareDNS) -> None:
    with patch.object(cf.client, "_request", side_effect=[ok([]), ok(ZONE)]) as request:
        cf.create_zone("example.com")
    assert request.call_args_list[1].kwargs["json"] == {
        "name": "example.com", "account": {"id": "acct"}, "type": "full",
    }
    assert cf.zone_exists("example.com")  # served from the cache, no further call


def test_create_zone_leaves_an_existing_zone_alone(cf: CloudflareDNS) -> None:
    with patch.object(cf.client, "_request", return_value=ok([ZONE])) as request:
        cf.create_zone("example.com")
    assert request.call_count == 1


def test_create_zone_needs_an_account_id() -> None:
    cf = CloudflareDNS("token")
    with patch.object(cf.client, "_request", return_value=ok([])):
        with pytest.raises(APIError, match="account_id"):
            cf.create_zone("example.com")


def test_list_records_follows_pages_and_makes_names_relative(cf: CloudflareDNS) -> None:
    page1 = [
        {"id": "r1", "type": "A", "name": "example.com", "content": "1.2.3.4", "ttl": 1, "proxied": True},
        {"id": "r2", "type": "CNAME", "name": "www.example.com", "content": "x.github.io", "ttl": 300, "proxied": False},
    ]
    page2 = [{"id": "r3", "type": "MX", "name": "example.com", "content": "mx.example.net", "ttl": 1, "priority": 10}]
    with patch.object(cf.client, "_request", side_effect=[ok([ZONE]), ok(page1, 2), ok(page2, 2)]):
        records = cf.list_records("example.com")
    assert [(r.type, r.name, r.proxied, r.id) for r in records] == [
        ("A", "", True, "r1"), ("CNAME", "www", False, "r2"), ("MX", "", False, "r3"),
    ]
    assert records[2].priority == 10


def test_add_record_is_dns_only_by_default(cf: CloudflareDNS) -> None:
    with patch.object(cf.client, "_request", side_effect=[ok([ZONE]), ok({})]) as request:
        cf.add_record("example.com", DNSRecord(type="CNAME", name="www", content="x.github.io"))
    assert request.call_args.args == ("POST", "/zones/z1/dns_records")
    assert request.call_args.kwargs["json"] == {
        "type": "CNAME", "name": "www.example.com", "content": "x.github.io", "ttl": 600, "proxied": False,
    }


def test_add_proxied_record_uses_automatic_ttl(cf: CloudflareDNS) -> None:
    with patch.object(cf.client, "_request", side_effect=[ok([ZONE]), ok({})]) as request:
        cf.add_record("example.com", DNSRecord(type="A", name="", content="1.2.3.4", proxied=True))
    assert request.call_args.kwargs["json"] == {
        "type": "A", "name": "example.com", "content": "1.2.3.4", "ttl": 1, "proxied": True,
    }


def test_add_mx_record_sends_priority_and_no_proxy_field(cf: CloudflareDNS) -> None:
    with patch.object(cf.client, "_request", side_effect=[ok([ZONE]), ok({})]) as request:
        cf.add_record("example.com", DNSRecord(type="MX", name="", content="mx.example.net", priority=10))
    body = request.call_args.kwargs["json"]
    assert body["priority"] == 10
    assert "proxied" not in body


def test_delete_record(cf: CloudflareDNS) -> None:
    with patch.object(cf.client, "_request", side_effect=[ok([ZONE]), ok({})]) as request:
        cf.delete_record("example.com", DNSRecord(type="A", name="", content="1.2.3.4", id="r1"))
    assert request.call_args.args == ("DELETE", "/zones/z1/dns_records/r1")


def test_delete_record_without_id_raises(cf: CloudflareDNS) -> None:
    with pytest.raises(APIError):
        cf.delete_record("example.com", DNSRecord(type="A", name="", content="1.2.3.4"))


def _settings(values: dict[str, str]) -> tuple[Any, list[tuple[str, str]]]:
    """A fake Cloudflare API holding zone settings, and the list of writes made."""
    writes: list[tuple[str, str]] = []

    def request(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        if path == "/zones":
            return ok([ZONE])
        key = path.rsplit("/", 1)[1]
        if method == "PATCH":
            values[key] = kwargs["json"]["value"]
            writes.append((key, values[key]))
        return ok({"id": key, "value": values[key]})

    return request, writes


def test_proxy_tls_reads_the_three_settings(cf: CloudflareDNS) -> None:
    values = {"ssl": "full", "ssl_automatic_mode": "auto", "always_use_https": "off"}
    request, _ = _settings(values)
    with patch.object(cf.client, "_request", side_effect=request):
        tls = cf.proxy_tls("example.com")
    assert (tls.mode, tls.automatic, tls.always_https) == ("full", True, False)
    assert not tls.correct


def test_set_proxy_tls_turns_automatic_off_first(cf: CloudflareDNS) -> None:
    values = {"ssl": "strict", "ssl_automatic_mode": "auto", "always_use_https": "off"}
    request, writes = _settings(values)
    with patch.object(cf.client, "_request", side_effect=request):
        cf.set_proxy_tls("example.com")
        assert cf.proxy_tls("example.com").correct
    assert writes == [
        ("ssl_automatic_mode", "custom"),
        ("ssl", "full"),
        ("always_use_https", "on"),
    ]


def test_set_proxy_tls_writes_only_what_is_wrong(cf: CloudflareDNS) -> None:
    values = {"ssl": "full", "ssl_automatic_mode": "custom", "always_use_https": "off"}
    request, writes = _settings(values)
    with patch.object(cf.client, "_request", side_effect=request):
        cf.set_proxy_tls("example.com")
    assert writes == [("always_use_https", "on")]


def test_denied_settings_say_which_permission_to_add(cf: CloudflareDNS) -> None:
    def request(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        if path == "/zones":
            return ok([ZONE])
        raise APIError("Unauthorized", status_code=403)

    with patch.object(cf.client, "_request", side_effect=request):
        with pytest.raises(APIError, match="Zone > Zone Settings > Edit"):
            cf.proxy_tls("example.com")
