"""Tests for the commands, run against in-memory providers."""

import json
from contextlib import contextmanager
from typing import Any, Iterator
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from mimeo.cli import create, delegate, delete, link, main, scan, status, sync, unlink
from mimeo.cli._processing import set_cli_overrides, set_log_format
from mimeo.config import Config
from mimeo.exceptions import EXIT_CONFIG, EXIT_PARTIAL
from mimeo.models import DNSRecord, Site
from tests.conftest import World

_MODULES = ["status", "sync", "connect", "create", "delete"]


@pytest.fixture
def cfg() -> Config:
    return Config(
        porkbun_api_key="pk1_test",
        porkbun_secret="sk1_test",
        github_username="sites",
        organizations=["sites", "other"],
        default_dns="pb",
    )


@pytest.fixture
def run(world: World, cfg: Config) -> Iterator[Any]:
    """Invoke a command with the fake world in place of real providers."""

    @contextmanager
    def fake_open_fleet(_cfg: Config) -> Iterator[Any]:
        yield world.fleet

    set_cli_overrides(None, None)
    set_log_format("text")
    patches = [patch(f"mimeo.cli.{m}.open_fleet", fake_open_fleet) for m in _MODULES]
    patches.append(patch("mimeo.config.Config.load", return_value=cfg))
    for p in patches:
        p.start()
    runner = CliRunner()

    def _run(command: Any, *args: str, input: str | None = None) -> Any:
        return runner.invoke(command, list(args), input=input)

    yield _run
    for p in patches:
        p.stop()
    set_log_format("text")


class TestStatus:
    def test_requires_hostnames_or_all(self, run: Any) -> None:
        assert run(status).exit_code == EXIT_CONFIG
        assert run(status, "a.com", "--all").exit_code == EXIT_CONFIG

    def test_rejects_invalid_hostname(self, run: Any) -> None:
        assert run(status, "not a domain").exit_code == EXIT_CONFIG

    def test_healthy_site(self, run: Any, world: World) -> None:
        world.healthy_site("example.com")
        result = run(status, "example.com")
        assert result.exit_code == 0
        assert "sites/example.com" in result.output
        assert "1 hostname(s), 0 with issues" in result.output

    def test_named_hostname_lists_what_sync_would_do(self, run: Any, world: World) -> None:
        world.register("example.com")
        world.host.add("sites/example.com", "example.com")
        result = run(status, "example.com")
        assert "missing" in result.output
        assert "sync would: add CNAME www -> sites.github.io" in result.output
        assert "1 with issues (1 fixable with: mimeo sync)" in result.output

    def test_json_row(self, run: Any, world: World) -> None:
        world.register("example.com", world.cf)
        site = world.host.add("other/example.com", "example.com", cert_state="bad_authz", cert_expires="2026-12-12")
        records = world.host.required_records(site, "")
        for record in records:
            record.proxied = True
        world.cf.seed("example.com", *records)
        row = json.loads(run(status, "example.com", "--format", "json").output)[0]
        assert row["dns"] == "cf"
        assert row["proxied"] is True
        assert row["records"] == "ok"
        assert row["site"] == "github:other/example.com"
        assert row["site_status"] == "cert error"
        assert row["problems"][0].startswith("The HTTPS certificate could not be renewed.")
        assert row["fixes"][-1] == "Switch the same records back to Proxied"
        assert row["fixable"] is False

    def test_all_scans_once_then_covers_registered_and_cached(self, run: Any, world: World) -> None:
        world.register("parked.com")
        world.healthy_site("example.com")
        world.host.add("other/odd-name", "elsewhere.org")
        world.cache.remove("example.com")
        rows = json.loads(run(status, "--all", "--format", "json").stdout)
        assert [r["hostname"] for r in rows] == ["elsewhere.org", "example.com", "parked.com"]
        assert world.host.scans == 1
        run(status, "--all")
        assert world.host.scans == 1

    def test_all_honors_ignore_list(self, run: Any, world: World, cfg: Config) -> None:
        world.register("parked.com")
        world.register("ignored.com")
        cfg.ignore_domains = ["ignored.com"]
        rows = json.loads(run(status, "--all", "--format", "json").stdout)
        assert [r["hostname"] for r in rows] == ["parked.com"]

    def test_problems_filter(self, run: Any, world: World) -> None:
        world.healthy_site("good.com")
        world.register("bad.com")
        world.host.add("sites/bad.com", "bad.com")
        rows = json.loads(run(status, "good.com", "bad.com", "--problems", "--format", "json").output)
        assert [r["hostname"] for r in rows] == ["bad.com"]

    def test_records_flag_shows_the_zone(self, run: Any, world: World) -> None:
        world.healthy_site("example.com")
        world.pb.seed("example.com", DNSRecord(type="MX", name="", content="mx.example.net", priority=10))
        result = run(status, "example.com", "--records")
        assert "mx.example.net" in result.output

    def test_one_failing_hostname_does_not_hide_the_others(self, run: Any, world: World) -> None:
        world.healthy_site("good.com")
        world.register("bad.com")
        world.pb.zones.pop("bad.com")  # list_records raises KeyError
        result = run(status, "good.com", "bad.com")
        assert result.exit_code == EXIT_PARTIAL
        assert "good.com" in result.output


class TestSync:
    def test_requires_hostnames_or_all(self, run: Any) -> None:
        assert run(sync).exit_code == EXIT_CONFIG

    def test_applies_what_status_listed(self, run: Any, world: World) -> None:
        world.register("example.com")
        world.host.add("sites/example.com", "example.com", https_enforced=False)
        result = run(sync, "example.com")
        assert result.exit_code == 0
        assert "1 changed" in result.output
        assert len(world.pb.zones["example.com"]) == 9
        assert world.host.sites["sites/example.com"].https_enforced
        row = json.loads(run(status, "example.com", "--format", "json").output)[0]
        assert row["has_problem"] is False

    def test_dry_run_changes_nothing(self, run: Any, world: World) -> None:
        world.register("example.com")
        world.host.add("sites/example.com", "example.com")
        result = run(sync, "example.com", "--dry-run")
        assert "would add A @ -> 185.199.108.153" in result.output
        assert world.pb.zones["example.com"] == []

    def test_hostname_without_a_site_is_skipped(self, run: Any, world: World) -> None:
        world.register("parked.com")
        result = run(sync, "parked.com")
        assert "skipped: no site" in result.output

    def test_external_dns_is_skipped_but_https_still_enforced(self, run: Any, world: World) -> None:
        world.registrar.ns["example.com"] = ["ns1.somewhere.else"]
        world.host.add("sites/example.com", "example.com", https_enforced=False)
        row = json.loads(run(sync, "example.com", "--format", "json").output)[0]
        assert row["actions"] == ["enforce HTTPS"]

    def test_unfixable_problem_is_reported(self, run: Any, world: World) -> None:
        world.healthy_site("example.com")
        world.host.add("sites/example.com", "example.com", cert_state="bad_authz")
        result = run(sync, "example.com")
        assert "problem: The HTTPS certificate could not be renewed." in result.output
        assert "to fix:" in result.output
        assert "1. Open https://github.com/sites/example.com/settings/pages" in result.output
        assert "1 with problems sync cannot fix" in result.output

    def test_all_syncs_every_site(self, run: Any, world: World) -> None:
        for name in ("a.com", "b.com"):
            world.register(name)
            world.host.add(f"sites/{name}", name)
        world.register("parked.com")
        result = run(sync, "--all")
        assert "2 changed" in result.output
        assert "1 skipped" in result.output


class TestLinkUnlink:
    def test_link_defaults_to_repo_named_after_hostname(self, run: Any, world: World) -> None:
        world.register("example.com")
        world.host.add("sites/example.com", None)
        result = run(link, "example.com")
        assert result.exit_code == 0
        assert "example.com -> github:sites/example.com" in result.output
        assert world.cache.get("example.com") == Site("github", "sites/example.com")

    def test_link_to_named_site(self, run: Any, world: World) -> None:
        world.register("example.com")
        world.host.add("other/portfolio", None)
        result = run(link, "example.com", "github:other/portfolio")
        assert result.exit_code == 0
        assert world.host.sites["other/portfolio"].custom_domain == "example.com"

    def test_link_rejects_badly_written_site(self, run: Any, world: World) -> None:
        result = run(link, "example.com", "other/portfolio")
        assert result.exit_code != 0
        assert "host:reference" in result.output

    def test_link_skip_dns(self, run: Any, world: World) -> None:
        world.register("example.com")
        world.host.add("sites/example.com", None)
        run(link, "example.com", "--skip-dns")
        assert world.pb.zones["example.com"] == []
        assert world.host.sites["sites/example.com"].custom_domain == "example.com"

    def test_unlink_asks_first(self, run: Any, world: World) -> None:
        world.healthy_site("example.com")
        result = run(unlink, "example.com", input="n\n")
        assert "Aborted." in result.output
        assert len(world.pb.zones["example.com"]) == 9

    def test_unlink_yes(self, run: Any, world: World) -> None:
        world.healthy_site("example.com")
        result = run(unlink, "example.com", "--yes")
        assert result.exit_code == 0
        assert world.pb.zones["example.com"] == []
        assert "sites/example.com" in world.host.sites  # the repository stays

    def test_unlink_without_site_fails(self, run: Any, world: World) -> None:
        world.register("example.com")
        result = run(unlink, "example.com", "--yes")
        assert result.exit_code != 0
        assert "No site is linked" in result.output


class TestDelegateScan:
    def test_delegate_uses_default_dns_when_not_named(self, run: Any, world: World, cfg: Config) -> None:
        world.healthy_site("example.com")
        cfg.default_dns = "cf"
        result = run(delegate, "example.com")
        assert result.exit_code == 0
        assert world.registrar.ns["example.com"] == world.cf.nameserver_names

    def test_delegate_refusal_is_an_error(self, run: Any, world: World, cfg: Config) -> None:
        world.healthy_site("example.com")
        world.registrar.dnssec.add("example.com")
        cfg.default_dns = "cf"
        result = run(delegate, "example.com")
        assert result.exit_code != 0
        assert "DNSSEC" in result.output

    def test_scan_lists_sites_and_warns_about_duplicates(self, run: Any, world: World) -> None:
        world.host.add("sites/a.com", "a.com")
        world.host.add("other/copy", "a.com")
        world.host.add("other/odd-name", "b.com")
        result = run(scan)
        assert result.exit_code == 0
        assert "github:other/odd-name" in result.output
        assert "2 site(s) with a custom domain in: sites, other" in result.output
        assert "more than one site" in result.output


class TestCreateDelete:
    def test_create_makes_repo_and_links_it(self, run: Any, world: World) -> None:
        world.register("example.com")
        result = run(create, "example.com")
        assert result.exit_code == 0, result.output
        assert world.repos.created == [("sites/example.com", "mimeo")]
        assert world.host.sites["sites/example.com"].custom_domain == "example.com"
        assert len(world.pb.zones["example.com"]) == 9
        assert "Created 1/1 site(s)" in result.output

    def test_create_refuses_unregistered_hostname_before_creating_anything(self, run: Any, world: World) -> None:
        result = run(create, "example.com")
        assert result.exit_code != 0
        assert "refusing to create" in result.output
        assert world.repos.created == []

    def test_create_rejects_unknown_template(self, run: Any, world: World) -> None:
        world.register("example.com")
        result = run(create, "example.com", "--template", "nope")
        assert result.exit_code == 1
        assert world.repos.created == []

    def test_create_delegates_to_default_dns_first(self, run: Any, world: World, cfg: Config) -> None:
        world.register("example.com")
        world.pb.seed("example.com", DNSRecord(type="MX", name="", content="mx.example.net", priority=10))
        cfg.default_dns = "cf"
        result = run(create, "example.com")
        assert result.exit_code == 0, result.output
        assert world.registrar.ns["example.com"] == world.cf.nameserver_names
        types = sorted(r.type for r in world.cf.zones["example.com"])
        assert types.count("MX") == 1 and types.count("A") == 4
        assert world.pb.zones["example.com"][0].type == "MX" and len(world.pb.zones["example.com"]) == 1

    def test_create_dns_flag_overrides_default(self, run: Any, world: World, cfg: Config) -> None:
        world.register("example.com")
        cfg.default_dns = "cf"
        with patch("mimeo.cli.create.DNS_PROVIDER_NAMES", ("pb", "cf")):
            pass
        from mimeo.cli.create import create_one

        create_one(world.fleet, cfg, "example.com", template="mimeo", dns="pb")
        assert world.registrar.ns["example.com"] == world.pb.nameserver_names

    def test_create_subdomain_adds_one_record_and_never_delegates(self, run: Any, world: World, cfg: Config) -> None:
        world.healthy_site("example.com")
        cfg.default_dns = "cf"
        result = run(create, "service.example.com")
        assert result.exit_code == 0, result.output
        assert world.registrar.ns["example.com"] == world.pb.nameserver_names
        assert len(world.pb.zones["example.com"]) == 10

    def test_create_with_repo_option(self, run: Any, world: World) -> None:
        world.register("example.com")
        result = run(create, "example.com", "--repo", "other/portfolio")
        assert result.exit_code == 0, result.output
        assert world.repos.created == [("other/portfolio", "mimeo")]
        assert [r for r in world.pb.zones["example.com"] if r.name == "www"][0].content == "other.github.io"

    def test_create_repo_option_takes_one_hostname(self, run: Any, world: World) -> None:
        assert run(create, "a.com", "b.com", "--repo", "other/x").exit_code == 2

    def test_create_existing_repo_is_left_unchanged_and_linked(self, run: Any, world: World) -> None:
        world.register("example.com")
        world.host.add("sites/example.com", None)
        result = run(create, "example.com")
        assert world.repos.created == []
        assert "already exists and was left unchanged" in result.output
        assert world.host.sites["sites/example.com"].custom_domain == "example.com"

    def test_create_force_asks_then_replaces(self, run: Any, world: World) -> None:
        world.healthy_site("example.com")
        assert "Aborted." in run(create, "example.com", "--force", input="n\n").output
        assert world.repos.created == []
        result = run(create, "example.com", "--force", "--yes")
        assert result.exit_code == 0, result.output
        assert world.repos.created == [("sites/example.com", "mimeo")]
        assert world.host.sites["sites/example.com"].custom_domain == "example.com"

    def test_create_dry_run(self, run: Any, world: World) -> None:
        world.register("example.com")
        result = run(create, "example.com", "--dry-run")
        assert result.exit_code == 0, result.output
        assert "would create sites/example.com from template 'mimeo'" in result.output
        assert "would add CNAME www -> sites.github.io" in result.output
        assert world.repos.created == []
        assert world.pb.zones["example.com"] == []

    def test_create_partial_failure_exit_code(self, run: Any, world: World) -> None:
        world.register("good.com")
        result = run(create, "good.com", "unregistered.com", "--sequential")
        assert result.exit_code == EXIT_PARTIAL
        assert "Created 1/2 site(s) (1 failed)" in result.output

    def test_create_json_log_format_has_no_text_summary(self, run: Any, world: World) -> None:
        world.register("example.com")
        result = run(main, "--log-format", "json", "create", "example.com")
        assert result.exit_code == 0, result.output
        assert "Created" not in result.output
        lines = [json.loads(line) for line in result.output.splitlines() if line.startswith("{")]
        assert lines[-1]["message"] == "success"

    def test_delete_names_the_repo_and_asks(self, run: Any, world: World) -> None:
        world.register("example.com")
        site = world.host.add("other/portfolio", "example.com")
        world.pb.seed("example.com", *world.host.required_records(site, ""))
        result = run(delete, "example.com", input="n\n")
        assert "other/portfolio  for example.com" in result.output
        assert world.repos.deleted == []

    def test_delete_unlinks_and_deletes_the_repo(self, run: Any, world: World) -> None:
        world.healthy_site("example.com")
        world.pb.seed("example.com", DNSRecord(type="MX", name="", content="mx.example.net", priority=10))
        result = run(delete, "example.com", "--yes")
        assert result.exit_code == 0, result.output
        assert world.repos.deleted == ["sites/example.com"]
        assert [r.type for r in world.pb.zones["example.com"]] == ["MX"]
        assert world.cache.get("example.com") is None

    def test_delete_dry_run(self, run: Any, world: World) -> None:
        world.healthy_site("example.com")
        result = run(delete, "example.com", "--dry-run")
        assert "would delete repository sites/example.com" in result.output
        assert world.repos.deleted == []
        assert len(world.pb.zones["example.com"]) == 9

    def test_delete_with_nothing_linked_falls_back_to_the_named_repo(self, run: Any, world: World) -> None:
        world.register("example.com")
        world.host.add("sites/example.com", None)
        world.pb.seed("example.com", DNSRecord(type="A", name="", content="9.9.9.9"))
        result = run(delete, "example.com", "--yes")
        assert world.repos.deleted == ["sites/example.com"]
        assert len(world.pb.zones["example.com"]) == 1
        assert "no site was linked" in result.output
