"""Tests for the hostname-to-site cache."""

from pathlib import Path

from mimeo.cache import SiteCache
from mimeo.models import Site


def test_missing_file_is_an_empty_unscanned_cache(tmp_path: Path) -> None:
    cache = SiteCache(tmp_path / "none" / "sites.json")
    assert cache.hostnames() == []
    assert not cache.scanned


def test_set_persists_and_reloads(tmp_path: Path) -> None:
    path = tmp_path / "sites.json"
    SiteCache(path).set("example.com", Site("github", "org/example.com"))
    assert SiteCache(path).get("example.com") == Site("github", "org/example.com")


def test_remove(tmp_path: Path) -> None:
    path = tmp_path / "sites.json"
    cache = SiteCache(path)
    cache.set("example.com", Site("github", "org/example.com"))
    cache.remove("example.com")
    assert SiteCache(path).get("example.com") is None


def test_replace_marks_the_cache_scanned(tmp_path: Path) -> None:
    path = tmp_path / "sites.json"
    cache = SiteCache(path)
    cache.set("old.com", Site("github", "org/old.com"))
    cache.replace({"new.com": Site("github", "org/new.com")})
    reloaded = SiteCache(path)
    assert reloaded.hostnames() == ["new.com"]
    assert reloaded.scanned


def test_corrupt_file_is_an_empty_cache(tmp_path: Path) -> None:
    path = tmp_path / "sites.json"
    path.write_text("{not json")
    assert SiteCache(path).hostnames() == []
