"""Tests for link, unlink and delegate against in-memory providers."""

import pytest

from mimeo.models import DNSRecord, ProxyTLS, Site
from mimeo.operations import NotProxyable, OperationError, delegate, link, proxy, unlink
from mimeo.plan import compare
from tests.conftest import World

SITE = Site("github", "sites/example.com")


class TestLink:
    def test_link_sets_domain_writes_records_and_caches(self, world: World) -> None:
        world.register("example.com")
        world.host.add("sites/example.com", None)
        outcome = link(world.fleet, "example.com", SITE)
        assert outcome.actions[0] == "set the custom domain of github:sites/example.com to example.com"
        assert len(world.pb.zones["example.com"]) == 9
        assert world.cache.get("example.com") == SITE
        assert not outcome.https_pending
        assert not compare(world.fleet.read("example.com"), world.host).has_problem

    def test_link_to_a_repo_with_another_name_in_another_org(self, world: World) -> None:
        world.register("example.com")
        site = world.host.add("other/portfolio", None)
        link(world.fleet, "example.com", site)
        www = [r for r in world.pb.zones["example.com"] if r.name == "www"]
        assert www[0].content == "other.github.io"

    def test_link_is_idempotent(self, world: World) -> None:
        world.healthy_site("example.com")
        outcome = link(world.fleet, "example.com", SITE)
        assert outcome.actions == []
        assert world.pb.calls == []

    def test_link_refuses_a_hostname_another_site_serves(self, world: World) -> None:
        world.healthy_site("example.com")
        with pytest.raises(OperationError, match="already linked to github:sites/example.com"):
            link(world.fleet, "example.com", Site("github", "other/thing"))

    def test_link_refuses_an_unknown_host(self, world: World) -> None:
        with pytest.raises(OperationError, match="netlify"):
            link(world.fleet, "example.com", Site("netlify", "thing"))

    def test_dry_run_changes_nothing_and_lists_everything(self, world: World) -> None:
        world.register("example.com")
        world.host.add("sites/example.com", None)
        outcome = link(world.fleet, "example.com", SITE, dry_run=True)
        assert len(outcome.actions) == 10
        assert all(a.startswith("would ") for a in outcome.actions)
        assert world.pb.zones["example.com"] == []
        assert world.host.sites["sites/example.com"].custom_domain is None
        assert world.cache.get("example.com") is None

    def test_subdomain_link_adds_one_cname(self, world: World) -> None:
        world.healthy_site("example.com")
        site = world.host.add("sites/service.example.com", None)
        outcome = link(world.fleet, "service.example.com", site)
        assert "add CNAME service -> sites.github.io" in outcome.actions
        assert len(world.pb.zones["example.com"]) == 10

    def test_records_on_cloudflare_are_written_dns_only(self, world: World) -> None:
        world.register("example.com", world.cf)
        world.host.add("sites/example.com", None)
        link(world.fleet, "example.com", SITE)
        assert [r.proxied for r in world.cf.zones["example.com"]] == [False] * 9
        assert world.pb.zones.get("example.com", []) == []

    def test_external_dns_lists_the_records_to_create_by_hand(self, world: World) -> None:
        world.registrar.ns["example.com"] = ["ns1.somewhere.else"]
        world.host.add("sites/example.com", None)
        outcome = link(world.fleet, "example.com", SITE)
        assert "not a configured DNS provider" in outcome.notes[0]
        assert "  CNAME www -> sites.github.io" in outcome.notes

    def test_pending_certificate_is_reported(self, world: World) -> None:
        world.register("example.com")
        world.host.add("sites/example.com", None, cert_state="new", https_enforced=False)
        outcome = link(world.fleet, "example.com", SITE)
        assert outcome.https_pending
        assert "mimeo sync" in outcome.notes[-1]

    def test_wait_enforces_https_when_the_certificate_arrives(self, world: World) -> None:
        world.register("example.com")
        world.host.add("sites/example.com", None, cert_state="new", https_enforced=False)
        naps: list[float] = []

        def nap(seconds: float) -> None:
            naps.append(seconds)
            if len(naps) == 2:
                world.host.sites["sites/example.com"].cert_state = "approved"

        outcome = link(world.fleet, "example.com", SITE, wait=600, sleep=nap)
        assert not outcome.https_pending
        assert outcome.actions[-1] == "enforce HTTPS"
        assert len(naps) == 2


class TestUnlink:
    def test_unlink_removes_site_records_and_custom_domain_only(self, world: World) -> None:
        world.healthy_site("example.com")
        world.pb.seed("example.com", DNSRecord(type="MX", name="", content="mx.example.net", priority=10))
        outcome, site = unlink(world.fleet, "example.com")
        assert site == SITE
        assert [r.type for r in world.pb.zones["example.com"]] == ["MX"]
        assert world.host.sites["sites/example.com"].custom_domain is None
        assert world.cache.get("example.com") is None
        assert outcome.actions[-1] == "remove the custom domain from github:sites/example.com"

    def test_unlink_subdomain_leaves_the_apex_site(self, world: World) -> None:
        world.healthy_site("example.com")
        world.healthy_site("service.example.com", zone="example.com")
        unlink(world.fleet, "service.example.com")
        assert len(world.pb.zones["example.com"]) == 9
        assert not compare(world.fleet.read("example.com"), world.host).has_problem

    def test_unlink_without_a_site_refuses(self, world: World) -> None:
        world.register("example.com")
        with pytest.raises(OperationError, match="No site is linked"):
            unlink(world.fleet, "example.com")

    def test_dry_run(self, world: World) -> None:
        world.healthy_site("example.com")
        outcome, _ = unlink(world.fleet, "example.com", dry_run=True)
        assert len(outcome.actions) == 10
        assert len(world.pb.zones["example.com"]) == 9
        assert world.host.sites["sites/example.com"].custom_domain == "example.com"


class TestDelegate:
    def _zone_with_mail(self, world: World) -> None:
        world.healthy_site("example.com")
        world.pb.seed(
            "example.com",
            DNSRecord(type="MX", name="", content="mx.example.net", priority=10),
            DNSRecord(type="TXT", name="", content="v=spf1 include:example.net ~all"),
            DNSRecord(type="NS", name="", content="ns1.pb.test"),
        )

    def test_copies_everything_but_ns_then_switches_nameservers(self, world: World) -> None:
        self._zone_with_mail(world)
        outcome = delegate(world.fleet, "example.com", "cf")
        copied = world.cf.zones["example.com"]
        assert len(copied) == 11
        assert "NS" not in {r.type for r in copied}
        assert [r.priority for r in copied if r.type == "MX"] == [10]
        assert all(r.proxied is False for r in copied)
        assert world.registrar.ns["example.com"] == world.cf.nameserver_names
        assert outcome.actions[-1].startswith("set nameservers to ns1.cf.test")
        # The old zone is left as it was.
        assert len(world.pb.zones["example.com"]) == 12

    def test_site_is_healthy_at_the_new_provider(self, world: World) -> None:
        self._zone_with_mail(world)
        delegate(world.fleet, "example.com", "cf")
        conn = world.fleet.read("example.com")
        assert conn.dns is world.cf
        assert not compare(conn, world.host).has_problem

    def test_moving_back(self, world: World) -> None:
        self._zone_with_mail(world)
        delegate(world.fleet, "example.com", "cf")
        outcome = delegate(world.fleet, "example.com", "pb")
        assert world.registrar.ns["example.com"] == world.pb.nameserver_names
        assert [a for a in outcome.actions if a.startswith("copy")] == []

    def test_dry_run_changes_nothing(self, world: World) -> None:
        self._zone_with_mail(world)
        outcome = delegate(world.fleet, "example.com", "cf", dry_run=True)
        assert outcome.actions[0] == "would create zone example.com at cf"
        assert len([a for a in outcome.actions if a.startswith("would copy")]) == 11
        assert "example.com" not in world.cf.zones
        assert world.registrar.ns["example.com"] == world.pb.nameserver_names

    def test_dry_run_lists_only_what_the_target_lacks(self, world: World) -> None:
        self._zone_with_mail(world)
        delegate(world.fleet, "example.com", "cf")
        delegate(world.fleet, "example.com", "pb")
        outcome = delegate(world.fleet, "example.com", "cf", dry_run=True)
        assert [a for a in outcome.actions if a.startswith("would copy")] == []
        assert outcome.actions == ["would set the nameservers of example.com to cf's"]

    def test_already_there(self, world: World) -> None:
        world.register("example.com", world.cf)
        outcome = delegate(world.fleet, "example.com", "cf")
        assert outcome.actions == []
        assert outcome.notes == ["example.com is already served by cf"]

    def test_refuses_while_dnssec_is_enabled(self, world: World) -> None:
        self._zone_with_mail(world)
        world.registrar.dnssec.add("example.com")
        with pytest.raises(OperationError, match="DNSSEC"):
            delegate(world.fleet, "example.com", "cf")
        assert world.registrar.ns["example.com"] == world.pb.nameserver_names

    def test_refuses_a_subdomain(self, world: World) -> None:
        world.register("example.com")
        with pytest.raises(OperationError, match="inside example.com"):
            delegate(world.fleet, "service.example.com", "cf")

    def test_refuses_an_unregistered_zone(self, world: World) -> None:
        with pytest.raises(OperationError, match="not registered"):
            delegate(world.fleet, "example.com", "cf")

    def test_refuses_an_unconfigured_provider(self, world: World) -> None:
        world.register("example.com")
        with pytest.raises(OperationError, match="configured: pb, cf"):
            delegate(world.fleet, "example.com", "route53")

    def test_unreadable_current_provider_needs_empty(self, world: World) -> None:
        world.registrar.ns["example.com"] = ["ns1.somewhere.else"]
        with pytest.raises(OperationError, match="--empty"):
            delegate(world.fleet, "example.com", "cf")
        delegate(world.fleet, "example.com", "cf", empty=True)
        assert world.cf.zones["example.com"] == []
        assert world.registrar.ns["example.com"] == world.cf.nameserver_names

    def test_failed_copy_leaves_nameservers_alone(self, world: World) -> None:
        self._zone_with_mail(world)
        world.cf.add_record = lambda zone, record: None  # type: ignore[method-assign]
        with pytest.raises(OperationError, match="did not arrive"):
            delegate(world.fleet, "example.com", "cf")
        assert world.registrar.ns["example.com"] == world.pb.nameserver_names

    def test_unsupported_types_are_reported_not_copied(self, world: World) -> None:
        world.register("example.com")
        world.pb.seed("example.com", DNSRecord(type="ALIAS", name="", content="pixie.porkbun.com"))
        world.cf.unsupported_types = frozenset({"ALIAS"})
        outcome = delegate(world.fleet, "example.com", "cf")
        assert world.cf.zones["example.com"] == []
        assert outcome.notes[0] == "not copied (cf has no ALIAS type): ALIAS @ -> pixie.porkbun.com"

    def test_records_already_at_the_target_are_not_duplicated(self, world: World) -> None:
        self._zone_with_mail(world)
        world.cf.seed("example.com", DNSRecord(type="MX", name="", content="mx.example.net", priority=10))
        delegate(world.fleet, "example.com", "cf")
        assert len([r for r in world.cf.zones["example.com"] if r.type == "MX"]) == 1


class TestProxy:
    def _site(self, world: World) -> None:
        world.healthy_site("example.com", dns=world.cf)
        world.cf.seed(
            "example.com",
            DNSRecord(type="MX", name="", content="mail.example.net", priority=10),
            DNSRecord(type="A", name="other", content="192.0.2.1"),
        )
        world.cf.tls["example.com"] = ProxyTLS("flexible", True, False)

    def test_sets_https_first_and_proxies_only_the_sites_records(self, world: World) -> None:
        self._site(world)
        outcome = proxy(world.fleet, "example.com", check=lambda hostname: True)
        assert world.cf.calls[0] == ("set proxy tls", "example.com", "")
        assert world.cf.tls["example.com"].correct
        by_name = {(r.type, r.name): r.proxied for r in world.cf.zones["example.com"]}
        assert by_name[("A", "")] and by_name[("AAAA", "")] and by_name[("CNAME", "www")]
        assert not by_name[("MX", "")] and not by_name[("A", "other")]
        assert len(outcome.actions) == 2

    def test_dry_run_changes_nothing(self, world: World) -> None:
        self._site(world)
        outcome = proxy(world.fleet, "example.com", dry_run=True)
        assert world.cf.calls == []
        assert all(a.startswith("would ") for a in outcome.actions)

    def test_switches_back_when_the_site_stops_answering(self, world: World) -> None:
        self._site(world)
        with pytest.raises(OperationError, match="switched back off"):
            proxy(world.fleet, "example.com", check=lambda hostname: False)
        assert not any(r.proxied for r in world.cf.zones["example.com"])

    def test_already_proxied_changes_nothing(self, world: World) -> None:
        self._site(world)
        proxy(world.fleet, "example.com", check=lambda hostname: True)
        world.cf.calls.clear()
        outcome = proxy(world.fleet, "example.com", check=lambda hostname: True)
        assert outcome.notes == ["already proxied"] and world.cf.calls == []

    def test_refuses_wrong_records(self, world: World) -> None:
        world.register("example.com", world.cf)
        world.host.add("sites/example.com", "example.com")
        with pytest.raises(OperationError, match="mimeo sync example.com"):
            proxy(world.fleet, "example.com")

    def test_no_proxy_at_the_provider_says_how_to_move(self, world: World) -> None:
        world.healthy_site("example.com")
        with pytest.raises(NotProxyable, match="mimeo delegate example.com --dns cloudflare"):
            proxy(world.fleet, "example.com")
