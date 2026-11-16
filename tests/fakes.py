"""In-memory providers for testing the read, compare and apply steps."""

from typing import Any

from mimeo.models import DNSRecord, Site, SiteState
from mimeo.providers.base import DNSProvider, Host, Registrar, RepoProvider

PAGES_V4 = ["185.199.108.153", "185.199.109.153", "185.199.110.153", "185.199.111.153"]
PAGES_V6 = [
    "2606:50c0:8000::153",
    "2606:50c0:8001::153",
    "2606:50c0:8002::153",
    "2606:50c0:8003::153",
]


class FakeRegistrar(Registrar):
    """Domains with nameservers, held in dicts."""

    def __init__(self, domains: dict[str, list[str]] | None = None) -> None:
        self.ns: dict[str, list[str]] = dict(domains or {})
        self.dnssec: set[str] = set()

    def list_domains(self) -> list[dict[str, Any]]:
        return [{"domain": d, "expireDate": "2027-06-01 00:00:00", "autoRenew": "1"} for d in self.ns]

    def get_nameservers(self, domain: str) -> list[str]:
        return sorted(self.ns[domain])

    def set_nameservers(self, domain: str, nameservers: list[str]) -> None:
        self.ns[domain] = list(nameservers)

    def dnssec_enabled(self, domain: str) -> bool:
        return domain in self.dnssec


class FakeDNS(DNSProvider):
    """Zones of records, held in a dict. Nameservers are ns1/ns2.<name>.test."""

    def __init__(self, name: str, proxies: bool = False) -> None:
        self.name = name
        self.proxies = proxies
        self.zones: dict[str, list[DNSRecord]] = {}
        self._next_id = 1
        self.calls: list[tuple[str, str, str]] = []

    @property
    def nameserver_names(self) -> list[str]:
        return [f"ns1.{self.name}.test", f"ns2.{self.name}.test"]

    def serves(self, nameservers: list[str]) -> bool:
        return bool(nameservers) and all(n.endswith(f".{self.name}.test") for n in nameservers)

    def zone_exists(self, zone: str) -> bool:
        return zone in self.zones

    def create_zone(self, zone: str) -> None:
        self.zones.setdefault(zone, [])

    def zone_nameservers(self, zone: str) -> list[str]:
        return self.nameserver_names

    def list_records(self, zone: str) -> list[DNSRecord]:
        return list(self.zones[zone])

    def add_record(self, zone: str, record: DNSRecord) -> None:
        stored = DNSRecord(
            type=record.type,
            name=record.name,
            content=record.content,
            ttl=record.ttl,
            priority=record.priority,
            proxied=bool(record.proxied) if self.proxies else None,
            id=str(self._next_id),
        )
        self._next_id += 1
        self.zones[zone].append(stored)
        self.calls.append(("add", zone, record.describe()))

    def delete_record(self, zone: str, record: DNSRecord) -> None:
        self.zones[zone] = [r for r in self.zones[zone] if r.id != record.id]
        self.calls.append(("delete", zone, record.describe()))

    def seed(self, zone: str, *records: DNSRecord) -> None:
        """Put records in a zone without recording calls."""
        self.zones.setdefault(zone, [])
        for record in records:
            self.add_record(zone, record)
        self.calls.clear()


class FakeHost(Host):
    """Sites with a custom domain and certificate state, held in a dict."""

    name = "github"

    def __init__(self, organizations: list[str] | None = None) -> None:
        self.organizations = organizations or ["sites"]
        self.sites: dict[str, SiteState] = {}
        self.scans = 0

    def add(
        self,
        ref: str,
        hostname: str | None,
        cert_state: str | None = "approved",
        https_enforced: bool = True,
        cert_expires: str | None = "2099-01-01",
    ) -> Site:
        self.sites[ref] = SiteState(
            configured=True,
            custom_domain=hostname,
            https_enforced=https_enforced,
            cert_state=cert_state,
            cert_expires=cert_expires,
        )
        return Site(host=self.name, ref=ref)

    def find_site(self, hostname: str) -> Site | None:
        for org in self.organizations:
            ref = f"{org}/{hostname}"
            state = self.sites.get(ref)
            if state is not None and state.custom_domain == hostname:
                return Site(host=self.name, ref=ref)
        return None

    def scan(self) -> dict[str, list[Site]]:
        self.scans += 1
        found: dict[str, list[Site]] = {}
        for ref, state in self.sites.items():
            if state.custom_domain and ref.split("/")[0] in self.organizations:
                found.setdefault(state.custom_domain, []).append(Site(host=self.name, ref=ref))
        return found

    def state(self, site: Site) -> SiteState:
        return self.sites.get(site.ref, SiteState(configured=False))

    def set_custom_domain(self, site: Site, hostname: str | None) -> None:
        state = self.sites.setdefault(site.ref, SiteState(configured=True))
        state.configured = True
        state.custom_domain = hostname

    def required_records(self, site: Site, label: str) -> list[DNSRecord]:
        target = f"{site.ref.split('/')[0]}.github.io"
        if label:
            return [DNSRecord(type="CNAME", name=label, content=target)]
        records = [DNSRecord(type="A", name="", content=ip) for ip in PAGES_V4]
        records += [DNSRecord(type="AAAA", name="", content=ip) for ip in PAGES_V6]
        records.append(DNSRecord(type="CNAME", name="www", content=target))
        return records

    def enforce_https(self, site: Site) -> bool:
        state = self.sites[site.ref]
        if state.cert_state != "approved":
            return False
        state.https_enforced = True
        return True


class FakeRepos(RepoProvider):
    """Repositories as entries in a FakeHost's site table."""

    def __init__(self, host: FakeHost, templates: tuple[str, ...] = ("mimeo",)) -> None:
        self.host = host
        self.templates = templates
        self.created: list[tuple[str, str]] = []
        self.deleted: list[str] = []

    def validate_template(self, template_repo: str) -> None:
        from mimeo.exceptions import HostError

        if template_repo not in self.templates:
            raise HostError(f"Template '{template_repo}' not found")

    def create_from_template(
        self,
        repo_name: str,
        owner: str,
        template_repo: str,
        private: bool = False,
        force: bool = False,
    ) -> tuple[str, bool, bool]:
        ref = f"{owner}/{repo_name}"
        existed = ref in self.host.sites
        if existed and not force:
            return ref, False, True
        # A fresh repository has Pages off and no custom domain.
        self.host.sites[ref] = SiteState(configured=True, cert_state="approved", cert_expires="2099-01-01")
        self.created.append((ref, template_repo))
        return ref, True, existed

    def delete_repository_if_exists(self, repo_full_name: str) -> bool:
        if repo_full_name not in self.host.sites:
            return False
        del self.host.sites[repo_full_name]
        self.deleted.append(repo_full_name)
        return True
