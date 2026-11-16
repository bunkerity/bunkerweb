"""Cached feeds use current validators and delete rows by relative cache name."""

import pytest

from common_utils import bytes_hash
from test_lists_port_download import Cache, run_job

PLUGINS = ("blacklist", "greylist", "whitelist", "realip", "dnsbl")
URL = "https://feeds.example/list"
URL_FILE = f"{bytes_hash(URL, algorithm='sha1')}.list"


class NamedCache(Cache):
    def del_cache(self, name, service_id=""):
        # Job.del_cache passes this name to the DB, which stores relative names.
        if not isinstance(name, str) or "/" in name:
            return False, "expected relative cache name"
        return super().del_cache(name, service_id=service_id)


def run_feed(plugin, kind, cache, monkeypatch, url=URL):
    extra = {"USE_DNSBL": "yes", "DNSBL_IGNORE_IP_URLS": url} if plugin == "dnsbl" else {}
    if plugin not in ("realip", "dnsbl") and kind != "IP":
        extra[f"{plugin.upper()}_{kind}_URLS"] = url
    return run_job(plugin, url if kind == "IP" else "", cache, monkeypatch, **extra)


@pytest.mark.parametrize("plugin", PLUGINS)
def test_cached_invalid_ip_is_rejected(plugin, tmp_path, monkeypatch):
    cache = NamedCache(tmp_path / "cache")
    cache.cache_file(URL_FILE, b"# feed\nnot-an-ip\n192.0.2.1\n2001:db8::/32\n")
    kind = "IGNORE_IP" if plugin == "dnsbl" else "IP"
    assert run_feed(plugin, kind, cache, monkeypatch) == 1
    name = "combined.list" if plugin == "realip" else f"{kind}.list"
    assert cache.data["" if plugin == "realip" else "lists.example", name] == b"192.0.2.1\n2001:db8::/32\n"
    assert run_feed(plugin, kind, cache, monkeypatch) == 0


@pytest.mark.parametrize(("plugin", "kind"), [(p, k) for p in ("blacklist", "greylist", "whitelist") for k in ("ASN", "RDNS", "URI", "USER_AGENT")])
def test_cached_kind_validation_and_user_agent_idempotence(plugin, kind, tmp_path, monkeypatch):
    raw, expected = {
        "ASN": (b"AS123\ninvalid\n", b"123\n"),
        "RDNS": (b"EXAMPLE.COM\ninvalid entry\n", b"example.com\n"),
        "URI": (b"/admin\ninvalid\n", b"/admin\n"),
        "USER_AGENT": (b"(?:\\b)Example Bot(?:\\b)\n", b"(?:\\b)Example Bot(?:\\b)\n"),
    }[kind]
    cache = NamedCache(tmp_path / "cache")
    cache.cache_file(URL_FILE, b"# feed\n" + raw)
    assert run_feed(plugin, kind, cache, monkeypatch) == 1
    assert cache.data["lists.example", f"{kind}.list"] == expected
    assert run_feed(plugin, kind, cache, monkeypatch) == 0


@pytest.mark.parametrize("plugin", PLUGINS)
def test_removed_url_cache_row_is_deleted(plugin, tmp_path, monkeypatch):
    cache = NamedCache(tmp_path / "cache")
    cache.cache_file("removed.list", b"# old feed\n198.51.100.1\n")
    cache.cache_file(URL_FILE, b"# feed\n192.0.2.1\n")
    assert run_feed(plugin, "IGNORE_IP" if plugin == "dnsbl" else "IP", cache, monkeypatch) == 1
    assert ("", "removed.list") not in cache.data


@pytest.mark.parametrize("plugin", ("blacklist", "greylist", "whitelist"))
def test_last_url_removal_publishes_deletion(plugin, tmp_path, monkeypatch):
    cache = NamedCache(tmp_path / "cache")
    cache.cache_file(URL_FILE, b"# feed\n192.0.2.1\n")
    cache.cache_file("IP.list", b"192.0.2.1\n", service_id="lists.example")
    assert run_feed(plugin, "IP", cache, monkeypatch, url="") == 1
    assert not cache.data
    assert run_feed(plugin, "IP", cache, monkeypatch, url="") == 0
