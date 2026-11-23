"""Netlify is read and reported, and never changed or damaged."""

from typing import Any

import pytest

from mimeo.cli.delete import delete_one
from mimeo.exceptions import HostError
from mimeo.models import DNSRecord, Site
from mimeo.operations import OperationError, link
from mimeo.plan import compare
from mimeo.providers.host.netlify import NetlifyReader
from tests.conftest import World

NS = ["dns1.p01.nsone.net", "dns2.p01.nsone.net"]


def account(calls: list[str] | None = None, fail: bool = False) -> NetlifyReader:
    sites = [
        {
            "id": "1",
            "name": "twohorses",
            "custom_domain": "twohorses.lol",
            "domain_aliases": ["twohorses.net"],
            "force_ssl": True,
            "admin_url": "https://app.netlify.test/twohorses",
            "build_settings": {"repo_path": "sites/twohorses", "repo_branch": "main"},
        },
        {
            "id": "2",
            "name": "tania",
            "custom_domain": "www.tania.test",
            "admin_url": "https://app.netlify.test/tania",
            "build_settings": {"repo_path": "sites/tania"},
        },
    ]

    def run(operation: str, data: dict[str, Any]) -> Any:
        if calls is not None:
            calls.append(operation)
        if fail:
            raise HostError("not logged in")
        if operation == "listSites":
            return sites
        if operation == "getDnsZones":
            return [
                {"name": "twohorses.lol", "dns_servers": NS},
                {"name": "stale.test", "dns_servers": NS},
            ]
        assert operation == "showSiteTLSCertificate"
        return {"state": "issued", "expires_at": "2099-01-01T00:00:00Z"}

    return NetlifyReader(run)


@pytest.fixture
def netlified(world: World) -> World:
    world.fleet.netlify = account()
    return world


def test_only_reads(world: World) -> None:
    calls: list[str] = []
    world.fleet.netlify = account(calls)
    world.registrar.ns["twohorses.lol"] = NS
    compare(world.fleet.read("twohorses.lol"), world.host)
    assert set(calls) == {"listSites", "getDnsZones", "showSiteTLSCertificate"}


def test_site_on_netlify_dns(netlified: World) -> None:
    netlified.registrar.ns["twohorses.lol"] = NS
    conn = netlified.fleet.read("twohorses.lol")
    plan = compare(conn, netlified.host)
    assert conn.site is None
    assert conn.netlify_dns
    assert (plan.records, plan.site) == ("netlify", "ok")
    assert not plan.has_problem


def test_stale_zone_is_not_netlify_dns(netlified: World) -> None:
    netlified.register("stale.test", netlified.cf)
    assert not netlified.fleet.read("stale.test").netlify_dns


def test_alias_on_outside_dns_is_checked_but_never_a_change(netlified: World) -> None:
    netlified.register("twohorses.net")
    plan = compare(netlified.fleet.read("twohorses.net"), netlified.host)
    assert plan.records == "missing"
    assert plan.problems and not plan.changes

    netlified.pb.seed("twohorses.net", DNSRecord(type="A", name="", content="75.2.60.5"))
    netlified.fleet.forget("twohorses.net")
    plan = compare(netlified.fleet.read("twohorses.net"), netlified.host)
    assert (plan.records, plan.has_problem) == ("ok", False)


def test_www_primary_is_the_apex_row(netlified: World) -> None:
    netlified.register("tania.test", netlified.cf)
    assert "www.tania.test" not in netlified.fleet.hostnames()
    assert netlified.fleet.read("tania.test").netlify.name == "tania"


def test_link_refuses_netlify_hostname(netlified: World) -> None:
    netlified.register("twohorses.net")
    with pytest.raises(OperationError, match="Netlify site twohorses"):
        link(netlified.fleet, "twohorses.net", Site("github", "sites/other"))
    assert netlified.pb.calls == []


def test_delete_keeps_a_repo_netlify_builds_from(netlified: World) -> None:
    netlified.register("shared.test")
    site = netlified.host.add("sites/twohorses", "shared.test")
    netlified.cache.set("shared.test", site)
    result = delete_one(netlified.fleet, "shared.test", site, site.ref, dry_run=False)
    assert not result["repo_deleted"]
    assert netlified.repos.deleted == []
    assert any("kept repository" in n for n in result["notes"])


def test_delete_refuses_a_netlify_hostname(netlified: World) -> None:
    netlified.register("twohorses.net")
    with pytest.raises(OperationError, match="left it"):
        delete_one(netlified.fleet, "twohorses.net", None, "sites/twohorses.net", dry_run=False)


def test_unreadable_account_stops_writes_but_not_reads(world: World) -> None:
    world.fleet.netlify = account(fail=True)
    world.register("example.test")
    compare(world.fleet.read("example.test"), world.host)
    assert "not logged in" in (world.fleet.netlify.error or "")
    with pytest.raises(HostError, match="netlify login"):
        link(world.fleet, "example.test", Site("github", "sites/example.test"))


def test_delete_still_asks_before_unlinking_a_kept_repo(netlified: World) -> None:
    from click.testing import CliRunner
    from contextlib import contextmanager
    from unittest.mock import patch

    from mimeo.cli import delete
    from mimeo.config import Config

    netlified.register("shared.test")
    site = netlified.host.add("sites/twohorses", "shared.test")
    netlified.cache.set("shared.test", site)

    @contextmanager
    def fleet(_cfg: Config) -> Any:
        yield netlified.fleet

    cfg = Config(porkbun_api_key="k", porkbun_secret="s", github_username="sites")
    with patch("mimeo.cli.delete.open_fleet", fleet), patch(
        "mimeo.config.Config.load", return_value=cfg
    ):
        result = CliRunner().invoke(delete, ["shared.test"], input="n\n")
    assert "Aborted" in result.output
    assert netlified.host.sites["sites/twohorses"].custom_domain == "shared.test"
