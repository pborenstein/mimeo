"""Read-only view of the sites and DNS zones in a Netlify account.

mimeo does not manage Netlify sites. It reads them so that `status` can
report them and so that `create`, `link` and `delete` do not damage
them. Every call here is a read made through the `netlify` CLI, which
holds the login (`netlify login`).
"""

import json
import os
import shutil
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from mimeo.exceptions import HostError

# The apex address and hostnames Netlify documents for DNS hosted elsewhere:
# https://docs.netlify.com/domains-https/custom-domains/ (read 2026-11-22).
NETLIFY_APEX_IP = "75.2.60.5"
NETLIFY_TARGETS = ("netlify.app", "netlify.com")

SKIP_ENV = "MIMEO_SKIP_NETLIFY"
_PAGE_SIZE = 100
_TIMEOUT = 30

Runner = Callable[[str, dict[str, Any]], Any]


@dataclass(frozen=True)
class NetlifySite:
    """A site in the Netlify account."""

    id: str
    name: str
    hostnames: tuple[str, ...]
    repo: str | None = None
    branch: str | None = None
    force_ssl: bool = False
    admin_url: str = ""


@dataclass(frozen=True)
class NetlifyCertificate:
    """The certificate Netlify holds for a site."""

    state: str | None = None
    expires: str | None = None


@dataclass
class _Loaded:
    sites: list[NetlifySite] = field(default_factory=list)
    zones: dict[str, set[str]] = field(default_factory=dict)
    by_hostname: dict[str, NetlifySite] = field(default_factory=dict)


def run_netlify_api(operation: str, data: dict[str, Any]) -> Any:
    """Run one `netlify api` read and return its parsed JSON.

    Raises:
        HostError: If the command fails or its output is not JSON
    """
    try:
        result = subprocess.run(
            ["netlify", "api", operation, "--data", json.dumps(data)],
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL,
            timeout=_TIMEOUT,
        )
    except FileNotFoundError as e:
        raise HostError("The Netlify CLI is not installed") from e
    except subprocess.TimeoutExpired as e:
        raise HostError(f"netlify api {operation} did not answer in {_TIMEOUT} seconds") from e
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "no error output"
        status = 404 if "not found" in message.lower() or "404" in message else None
        raise HostError(f"netlify api {operation} failed: {message}", status_code=status)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise HostError(f"netlify api {operation} returned something other than JSON") from e


def _name_variants(hostname: str) -> set[str]:
    """The hostname and its www or non-www twin; Netlify serves both."""
    if hostname.startswith("www."):
        return {hostname, hostname[4:]}
    return {hostname, f"www.{hostname}"}


def _parse_site(raw: dict[str, Any]) -> NetlifySite:
    names = [raw.get("custom_domain"), *(raw.get("domain_aliases") or [])]
    build = raw.get("build_settings") or {}
    return NetlifySite(
        id=str(raw.get("id", "")),
        name=str(raw.get("name", "")),
        hostnames=tuple(str(n).lower() for n in names if n),
        repo=build.get("repo_path") or None,
        branch=build.get("repo_branch") or None,
        force_ssl=bool(raw.get("force_ssl")),
        admin_url=str(raw.get("admin_url") or ""),
    )


class NetlifyReader:
    """The account's sites and zones, read once per run."""

    def __init__(self, run: Runner = run_netlify_api) -> None:
        """Set up the reader. Nothing is read until it is needed."""
        self._run = run
        self._lock = threading.Lock()
        self._loaded: _Loaded | None = None
        self._certificates: dict[str, NetlifyCertificate | None] = {}
        self.error: str | None = None

    def load(self) -> None:
        """Read sites and zones. A failure is kept in `error`, not raised."""
        with self._lock:
            if self._loaded is not None:
                return
            try:
                self._loaded = self._read()
            except HostError as e:
                self.error = str(e)
                self._loaded = _Loaded()

    def require(self) -> None:
        """Stop a command that must not run without knowing Netlify's sites.

        Raises:
            HostError: If the account could not be read
        """
        self.load()
        if self.error:
            raise HostError(
                f"Could not read the Netlify account, so mimeo cannot tell whether this "
                f"would damage a Netlify site: {self.error}\n"
                f"Run: netlify login. If you do not use Netlify, set {SKIP_ENV}=1."
            )

    def _read(self) -> _Loaded:
        loaded = _Loaded()
        page = 1
        while True:
            batch = self._run("listSites", {"per_page": _PAGE_SIZE, "page": page})
            loaded.sites += [_parse_site(raw) for raw in batch]
            if len(batch) < _PAGE_SIZE:
                break
            page += 1
        for site in loaded.sites:
            for hostname in site.hostnames:
                for name in _name_variants(hostname):
                    loaded.by_hostname.setdefault(name, site)
        for zone in self._run("getDnsZones", {}):
            servers = {str(s).rstrip(".").lower() for s in zone.get("dns_servers") or []}
            loaded.zones[str(zone.get("name", "")).lower()] = servers
        return loaded

    def _data(self) -> _Loaded:
        self.load()
        assert self._loaded is not None
        return self._loaded

    @property
    def sites(self) -> list[NetlifySite]:
        """Every site in the account."""
        return list(self._data().sites)

    def site_for(self, hostname: str) -> NetlifySite | None:
        """The site serving this hostname, counting its www or non-www twin."""
        return self._data().by_hostname.get(hostname.lower())

    def sites_building(self, repo: str) -> list[NetlifySite]:
        """The sites that build from this GitHub repository."""
        wanted = repo.lower()
        return [s for s in self._data().sites if s.repo and s.repo.lower() == wanted]

    def serves_zone(self, zone: str, nameservers: list[str]) -> bool:
        """True when the zone is in this account and the registrar points at it.

        A zone can stay in the account after the domain moves away, and
        Netlify's nameservers are NS1's, shared with NS1's other
        customers, so neither the zone nor the names are enough alone.
        """
        servers = self._data().zones.get(zone.lower())
        if not servers or not nameservers:
            return False
        return {n.rstrip(".").lower() for n in nameservers} == servers

    def certificate(self, site: NetlifySite) -> NetlifyCertificate | None:
        """The site's certificate; None when it has none.

        Raises:
            HostError: If it could not be read
        """
        with self._lock:
            if site.id in self._certificates:
                return self._certificates[site.id]
        try:
            raw = self._run("showSiteTLSCertificate", {"site_id": site.id})
            found: NetlifyCertificate | None = NetlifyCertificate(
                state=raw.get("state"), expires=raw.get("expires_at")
            )
        except HostError as e:
            if e.status_code != 404:
                raise
            found = None
        with self._lock:
            self._certificates[site.id] = found
        return found


def open_reader() -> NetlifyReader | None:
    """A reader, or None when the Netlify CLI is absent or switched off."""
    if os.getenv(SKIP_ENV) or shutil.which("netlify") is None:
        return None
    return NetlifyReader()
