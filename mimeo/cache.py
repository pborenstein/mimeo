"""Cache of which site serves which hostname (DEC-040).

The host's custom-domain setting is the authority for the link between
a hostname and a site. This file only saves looking it up: it can be
deleted at any time, and commands confirm a cached pair against the
host before acting on it.
"""

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from mimeo.models import Site


def default_cache_path() -> Path:
    """Where the cache file lives: $MIMEO_CACHE_DIR or ~/.cache/mimeo."""
    base = os.getenv("MIMEO_CACHE_DIR")
    directory = Path(base) if base else Path.home() / ".cache" / "mimeo"
    return directory / "sites.json"


class SiteCache:
    """Hostname-to-site pairs, kept in one JSON file."""

    def __init__(self, path: Path | None = None) -> None:
        """Open the cache at `path` (default: default_cache_path())."""
        self.path = path or default_cache_path()
        self._lock = threading.Lock()
        self._sites: Dict[str, Site] = {}
        self.scanned_at: str | None = None
        self._load()

    def _load(self) -> None:
        """Read the file. A missing or unreadable file is an empty cache."""
        try:
            data: Dict[str, Any] = json.loads(self.path.read_text())
            self.scanned_at = data.get("scanned_at")
            self._sites = {
                str(hostname): Site.parse(str(ref))
                for hostname, ref in (data.get("sites") or {}).items()
            }
        except (OSError, ValueError, AttributeError):
            self._sites = {}
            self.scanned_at = None

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "scanned_at": self.scanned_at,
            "sites": {h: str(s) for h, s in sorted(self._sites.items())},
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2) + "\n")
        tmp.replace(self.path)

    @property
    def scanned(self) -> bool:
        """True once a full scan has filled the cache."""
        return self.scanned_at is not None

    def get(self, hostname: str) -> Site | None:
        """The cached site for a hostname, if any."""
        with self._lock:
            return self._sites.get(hostname)

    def hostnames(self) -> list[str]:
        """Every hostname with a cached site."""
        with self._lock:
            return sorted(self._sites)

    def set(self, hostname: str, site: Site) -> None:
        """Record that `site` serves `hostname`."""
        with self._lock:
            if self._sites.get(hostname) == site:
                return
            self._sites[hostname] = site
            self._save()

    def remove(self, hostname: str) -> None:
        """Forget the pair for `hostname`."""
        with self._lock:
            if self._sites.pop(hostname, None) is not None:
                self._save()

    def replace(self, sites: Dict[str, Site]) -> None:
        """Replace the whole cache with the result of a scan."""
        with self._lock:
            self._sites = dict(sites)
            self.scanned_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            self._save()
