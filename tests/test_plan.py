"""Tests for the read, compare and apply steps against in-memory providers."""

from datetime import date

import pytest

from mimeo.exceptions import HostError

from mimeo.models import DNSRecord, Site
from mimeo.plan import apply, compare
from tests.conftest import World


def _plan(world: World, hostname: str):
    conn = world.fleet.read(hostname)
    return conn, compare(conn, world.host, today=date(2026, 11, 15))


class TestRead:
    def test_apex_reads_all_four_things(self, world: World) -> None:
        world.healthy_site("example.com")
        conn = world.fleet.read("example.com")
        assert conn.zone == "example.com"
        assert conn.label == ""
        assert conn.dns is world.pb
        assert len(conn.records or []) == 9
        assert conn.site == Site("github", "sites/example.com")
        assert conn.state is not None and conn.state.custom_domain == "example.com"

    def test_subdomain_zone_is_longest_registered_suffix(self, world: World) -> None:
        world.register("example.com")
        conn = world.fleet.read("a.service.example.com")
        assert conn.zone == "example.com"
        assert conn.label == "a.service"

    def test_unregistered_hostname_has_no_zone(self, world: World) -> None:
        conn = world.fleet.read("elsewhere.org")
        assert conn.zone is None
        assert conn.records is None

    def test_nameservers_pick_the_provider(self, world: World) -> None:
        world.register("example.com", world.cf)
        # Stale records at the provider the nameservers do not name.
        world.pb.seed("example.com", DNSRecord(type="A", name="", content="1.2.3.4"))
        conn = world.fleet.read("example.com")
        assert conn.dns is world.cf
        assert conn.records == []

    def test_unknown_nameservers_give_no_provider(self, world: World) -> None:
        world.registrar.ns["example.com"] = ["ns1.somewhere.else"]
        conn = world.fleet.read("example.com")
        assert conn.dns is None
        assert conn.records is None

    def test_site_found_in_another_organization(self, world: World) -> None:
        world.register("example.com")
        world.host.add("other/example.com", "example.com")
        conn = world.fleet.read("example.com")
        assert conn.site == Site("github", "other/example.com")
        assert world.cache.get("example.com") == conn.site

    def test_stale_cache_entry_is_dropped(self, world: World) -> None:
        world.register("example.com")
        site = world.host.add("other/renamed", "different.com")
        world.cache.set("example.com", site)
        conn = world.fleet.read("example.com")
        assert conn.site is None
        assert world.cache.get("example.com") is None

    def test_first_lookup_scans_when_the_cache_never_has(self, world: World) -> None:
        world.register("example.com")
        world.host.add("other/odd-name", "example.com")
        conn = world.fleet.read("example.com")
        assert conn.site == Site("github", "other/odd-name")
        assert world.host.scans == 1
        # A later miss does not scan again.
        world.fleet.read("parked.com")
        assert world.host.scans == 1

    def test_thorough_lookup_scans_even_after_a_scan(self, world: World) -> None:
        world.fleet.rescan()
        world.host.add("other/odd-name", "example.com")
        assert world.fleet.site_for("example.com")[0] is None
        assert world.fleet.site_for("example.com", thorough=True)[0] == Site("github", "other/odd-name")

    def test_fleet_read_does_not_search(self, world: World) -> None:
        world.register("example.com")
        world.host.add("sites/example.com", "example.com")
        conn = world.fleet.read("example.com", search=False)
        assert conn.site is None

    def test_rescan_fills_cache_and_reports_duplicates(self, world: World) -> None:
        world.host.add("sites/a.com", "a.com")
        world.host.add("other/elsewhere", "a.com")
        world.host.add("other/odd-name", "b.com")
        duplicates = world.fleet.rescan()
        assert world.cache.get("b.com") == Site("github", "other/odd-name")
        assert list(duplicates) == ["a.com"]
        assert world.cache.scanned

    def test_zone_records_read_once_for_sites_sharing_a_zone(self, world: World) -> None:
        world.healthy_site("example.com")
        world.healthy_site("service.example.com", zone="example.com")
        first = world.fleet.read("example.com")
        second = world.fleet.read("service.example.com")
        assert first.records is second.records


class TestCompare:
    def test_healthy_site_has_no_changes(self, world: World) -> None:
        world.healthy_site("example.com")
        _, plan = _plan(world, "example.com")
        assert plan.records == "ok"
        assert plan.site == "ok"
        assert not plan.has_problem

    def test_registered_domain_with_no_site_is_not_a_problem(self, world: World) -> None:
        world.register("parked.com")
        _, plan = _plan(world, "parked.com")
        assert plan.site is None
        assert not plan.has_problem

    def test_missing_records_are_added(self, world: World) -> None:
        world.register("example.com")
        world.host.add("sites/example.com", "example.com")
        _, plan = _plan(world, "example.com")
        assert plan.records == "missing"
        assert len(plan.missing) == 9
        assert [c.action for c in plan.changes] == ["add_record"] * 9

    def test_extra_address_record_at_site_name_is_removed_first(self, world: World) -> None:
        world.register("example.com")
        site = world.host.add("sites/example.com", "example.com")
        required = [r for r in world.host.required_records(site, "") if r.name == ""]
        world.pb.seed(
            "example.com",
            *required,
            DNSRecord(type="CNAME", name="www", content="old.example.net"),
        )
        _, plan = _plan(world, "example.com")
        assert [c.summary for c in plan.changes] == [
            "remove CNAME www -> old.example.net",
            "add CNAME www -> sites.github.io",
        ]

    def test_apex_alias_is_removed(self, world: World) -> None:
        world.healthy_site("example.com")
        world.pb.seed("example.com", DNSRecord(type="ALIAS", name="", content="pixie.porkbun.com"))
        _, plan = _plan(world, "example.com")
        assert plan.records == "extra"
        assert [c.action for c in plan.changes] == ["delete_record"]

    def test_records_mimeo_does_not_own_are_left_alone(self, world: World) -> None:
        world.healthy_site("example.com")
        world.pb.seed(
            "example.com",
            DNSRecord(type="MX", name="", content="mx.example.net", priority=10),
            DNSRecord(type="TXT", name="", content="v=spf1 -all"),
            DNSRecord(type="A", name="mail", content="9.9.9.9"),
            DNSRecord(type="CNAME", name="service", content="sites.github.io"),
        )
        _, plan = _plan(world, "example.com")
        assert not plan.changes
        assert plan.records == "ok"

    def test_subdomain_site_needs_one_cname_and_leaves_apex_alone(self, world: World) -> None:
        world.healthy_site("example.com")
        world.host.add("sites/service.example.com", "service.example.com")
        conn, plan = _plan(world, "service.example.com")
        assert [c.summary for c in plan.changes] == ["add CNAME service -> sites.github.io"]
        apply(conn, plan, world.host)
        world.fleet.forget("example.com")
        _, apex_plan = _plan(world, "example.com")
        assert not apex_plan.changes

    def test_cname_target_follows_repo_owner(self, world: World) -> None:
        world.register("example.com")
        world.host.add("other/example.com", "example.com")
        _, plan = _plan(world, "example.com")
        assert plan.changes[-1].summary == "add CNAME www -> other.github.io"

    def test_external_dns_is_not_compared_and_not_a_problem(self, world: World) -> None:
        world.registrar.ns["example.com"] = ["ns1.somewhere.else"]
        world.host.add("sites/example.com", "example.com")
        _, plan = _plan(world, "example.com")
        assert plan.records == "external"
        assert not plan.has_problem

    def test_no_nameservers_is_a_problem_sync_cannot_fix(self, world: World) -> None:
        world.registrar.ns["example.com"] = []
        world.host.add("sites/example.com", "example.com")
        _, plan = _plan(world, "example.com")
        assert plan.records == "unknown"
        assert plan.has_problem and not plan.fixable

    def test_new_record_takes_proxy_setting_in_use_at_its_name(self, world: World) -> None:
        world.register("example.com", world.cf)
        world.host.add("sites/example.com", "example.com")
        world.cf.seed(
            "example.com",
            DNSRecord(type="CNAME", name="www", content="old.example.net", proxied=True),
        )
        _, plan = _plan(world, "example.com")
        by_summary = {c.summary: c.record for c in plan.changes}
        assert by_summary["add CNAME www -> sites.github.io"].proxied is True
        assert by_summary["add A @ -> 185.199.108.153"].proxied is None

    def test_proxied_apex_with_only_a_records_needs_no_aaaa(self, world: World) -> None:
        world.register("example.com", world.cf)
        site = world.host.add("sites/example.com", "example.com")
        present = [r for r in world.host.required_records(site, "") if r.type != "AAAA"]
        for record in present:
            record.proxied = True
        world.cf.seed("example.com", *present)
        _, plan = _plan(world, "example.com")
        assert plan.records == "ok"
        assert not plan.has_problem

    def test_dns_only_apex_still_needs_aaaa(self, world: World) -> None:
        world.register("example.com", world.cf)
        site = world.host.add("sites/example.com", "example.com")
        world.cf.seed(
            "example.com", *[r for r in world.host.required_records(site, "") if r.type != "AAAA"]
        )
        _, plan = _plan(world, "example.com")
        assert [c.summary for c in plan.changes] == [
            f"add AAAA @ -> 2606:50c0:800{i}::153" for i in range(4)
        ]

    def test_proxied_records_are_not_a_problem(self, world: World) -> None:
        world.register("example.com", world.cf)
        site = world.host.add("sites/example.com", "example.com")
        required = world.host.required_records(site, "")
        for record in required:
            record.proxied = True
        world.cf.seed("example.com", *required)
        _, plan = _plan(world, "example.com")
        assert not plan.has_problem


class TestCompareSite:
    def _site(self, world: World, **kwargs) -> None:
        world.healthy_site("example.com")
        world.host.add("sites/example.com", "example.com", **kwargs)

    def test_approved_cert_without_enforcement_is_fixable(self, world: World) -> None:
        self._site(world, https_enforced=False)
        conn, plan = _plan(world, "example.com")
        assert plan.site == "fixable"
        assert apply(conn, plan, world.host) == ["enforce HTTPS"]
        assert world.host.sites["sites/example.com"].https_enforced

    def test_pending_cert_is_a_problem_without_a_fix(self, world: World) -> None:
        self._site(world, cert_state="authorization_created", https_enforced=False)
        _, plan = _plan(world, "example.com")
        assert plan.site == "pending"
        assert plan.has_problem and not plan.fixable

    def test_failed_renewal_shows_even_when_https_is_enforced(self, world: World) -> None:
        self._site(world, cert_state="bad_authz", cert_expires="2026-12-12")
        _, plan = _plan(world, "example.com")
        assert plan.site == "cert error"
        assert plan.problems == [
            "The HTTPS certificate could not be renewed. It expires 2026-12-12; after"
            " that date browsers refuse to open https://example.com."
        ]
        assert plan.fixes == [
            "Open https://github.com/sites/example.com/settings/pages",
            "Under Custom domain, click Remove",
            "Type example.com back into Custom domain and click Save",
            "Wait 15 minutes, then run: mimeo status example.com. Repeat until SITE says"
            " ok or fixable; it can take an hour.",
        ]

    def test_no_certificate_is_requested_by_sync(self, world: World) -> None:
        self._site(world, cert_state=None, https_enforced=False)
        conn, plan = _plan(world, "example.com")
        assert plan.site == "no cert"
        assert plan.fixable and not plan.problems
        calls: list[str | None] = []
        real = world.host.set_custom_domain

        def _record(site, hostname):  # type: ignore[no-untyped-def]
            calls.append(hostname)
            real(site, hostname)

        world.host.set_custom_domain = _record  # type: ignore[method-assign]
        done = apply(conn, plan, world.host)
        assert done == [
            "request the HTTPS certificate (removes the custom domain and sets it again)"
        ]
        assert calls == [None, "example.com"]
        assert world.host.sites["sites/example.com"].custom_domain == "example.com"

    def test_failing_to_set_the_domain_again_says_how_to_put_it_back(self, world: World) -> None:
        self._site(world, cert_state=None, https_enforced=False)
        conn, plan = _plan(world, "example.com")
        real = world.host.set_custom_domain

        def _fail(site, hostname):  # type: ignore[no-untyped-def]
            if hostname is not None:
                raise HostError("boom", status_code=500)
            real(site, hostname)

        world.host.set_custom_domain = _fail  # type: ignore[method-assign]
        with pytest.raises(HostError, match="mimeo link example.com github:sites/example.com"):
            apply(conn, plan, world.host)

    def test_no_certificate_with_wrong_records_is_two_syncs(self, world: World) -> None:
        world.register("example.com")
        world.host.add("sites/example.com", "example.com", cert_state=None, https_enforced=False)
        _, plan = _plan(world, "example.com")
        assert plan.records == "missing"
        assert all(c.target == "dns" for c in plan.changes)
        assert plan.fixes[0] == "Run: mimeo sync example.com"
        assert plan.fixes[1].startswith("Wait 5 minutes, then run: mimeo sync example.com again")

    def test_no_certificate_behind_a_proxy_is_fixed_by_hand(self, world: World) -> None:
        world.register("example.com", world.cf)
        site = world.host.add("sites/example.com", "example.com", cert_state=None)
        records = world.host.required_records(site, "")
        for record in records:
            record.proxied = True
        world.cf.seed("example.com", *records)
        _, plan = _plan(world, "example.com")
        assert not plan.fixable
        assert plan.fixes[0] == "In the Cf dashboard, open example.com > DNS > Records"

    def test_certificate_steps_take_the_proxy_out_of_the_way(self, world: World) -> None:
        world.register("example.com", world.cf)
        site = world.host.add(
            "sites/example.com", "example.com", cert_state="bad_authz", cert_expires="2026-12-12"
        )
        records = world.host.required_records(site, "")
        for record in records:
            record.proxied = True
        world.cf.seed("example.com", *records)
        _, plan = _plan(world, "example.com")
        assert plan.fixes[0] == "In the Cf dashboard, open example.com > DNS > Records"
        assert plan.fixes[1].startswith("Edit each of these and switch Proxy status to DNS only: ")
        assert plan.fixes[-1] == "Switch the same records back to Proxied"

    def test_an_expired_certificate_is_said_to_have_expired(self, world: World) -> None:
        self._site(world, cert_state="bad_authz", cert_expires="2026-11-14")
        _, plan = _plan(world, "example.com")
        assert "It expired 2026-11-14, so browsers refuse" in plan.problems[0]

    def test_approved_cert_close_to_expiry_is_flagged(self, world: World) -> None:
        self._site(world, cert_expires="2026-11-20")
        _, plan = _plan(world, "example.com")
        assert plan.site == "expiring"

    def test_no_cert(self, world: World) -> None:
        self._site(world, cert_state=None, https_enforced=False)
        _, plan = _plan(world, "example.com")
        assert plan.site == "no cert"


class TestApply:
    def test_apply_makes_the_next_comparison_clean(self, world: World) -> None:
        world.register("example.com")
        world.host.add("sites/example.com", "example.com", https_enforced=False)
        world.pb.seed("example.com", DNSRecord(type="ALIAS", name="", content="pixie.porkbun.com"))
        conn, plan = _plan(world, "example.com")
        done = apply(conn, plan, world.host)
        assert done[0] == "remove ALIAS @ -> pixie.porkbun.com"
        assert done[-1] == "enforce HTTPS"
        world.fleet.forget("example.com")
        _, after = _plan(world, "example.com")
        assert not after.has_problem


class TestDomainIsGone:
    def _site_without_domain(self, world: World, answers: list[str] | None) -> None:
        site = world.host.add("sites/gone.com", "gone.com", cert_state="bad_authz")
        world.cache.set("gone.com", site)
        world.fleet.lookup = lambda name: answers

    def test_site_whose_domain_has_no_dns_offers_what_to_do_with_the_repo(
        self, world: World
    ) -> None:
        self._site_without_domain(world, [])
        _, plan = _plan(world, "gone.com")
        assert plan.site == "no domain"
        assert "the registration has most likely lapsed" in plan.problems[0]
        assert plan.fixes_are_choices
        assert plan.fixes[0] == "Keep the repository and take the domain off it: mimeo unlink gone.com"
        assert plan.fixes[1] == "Delete the repository: mimeo delete gone.com"
        assert "https://github.com/sites/gone.com/settings" in plan.fixes[2]

    def test_site_whose_domain_answers_elsewhere_is_judged_as_usual(self, world: World) -> None:
        self._site_without_domain(world, ["ns1.elsewhere.net"])
        _, plan = _plan(world, "gone.com")
        assert plan.site == "cert error"
        assert not plan.fixes_are_choices

    def test_a_lookup_that_could_not_be_made_concludes_nothing(self, world: World) -> None:
        self._site_without_domain(world, None)
        _, plan = _plan(world, "gone.com")
        assert plan.site == "cert error"

    def test_unlink_works_on_a_site_whose_domain_is_gone(self, world: World) -> None:
        from mimeo.operations import unlink

        self._site_without_domain(world, [])
        unlink(world.fleet, "gone.com")
        assert world.host.sites["sites/gone.com"].custom_domain is None
