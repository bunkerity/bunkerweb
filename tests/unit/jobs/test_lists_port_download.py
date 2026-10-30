"""Run the actual four download scripts against a local source and a scoped cache."""

import json
import logging
import os
import runpy
import sys
from pathlib import Path
from time import time
from types import SimpleNamespace

import pytest

from common_utils import bytes_hash

ROOT = Path(os.environ.get("BW_LISTS_PORT_ROOT", Path(__file__).resolve().parents[3]))
PLUGINS = ("blacklist", "greylist", "whitelist", "realip")
SOURCE = json.dumps(
    {
        "prefixes": [
            {"service": "CLOUDFRONT", "region": "GLOBAL", "ip_prefix": "192.0.2.0/24"},
            {"service": "EC2", "region": "GLOBAL", "ip_prefix": "198.51.100.0/24"},
            {"service": "CLOUDFRONT", "region": "eu-west-1", "ip_prefix": "203.0.113.0/24"},
            {"service": "CLOUDFRONT", "region": "GLOBAL", "ip_prefix": "not-an-ip"},
        ],
        "ipv6_prefixes": [{"service": "CLOUDFRONT", "region": "GLOBAL", "ipv6_prefix": "2001:db8::/32"}],
    }
).encode()


class Cache:
    def __init__(self, path):
        self.job_path = path
        self.data = {}

    def get_cache(self, name, **kwargs):
        data = self.data.get(("", name))
        return {"last_update": time(), "data": data} if data is not None else None

    def cache_file(self, name, data, service_id="", **kwargs):
        self.data[service_id, name] = data
        path = self.job_path / service_id / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return True, ""

    def cache_hash(self, name, service_id=""):
        data = self.data.get((service_id, name))
        return bytes_hash(data) if data is not None else None

    def del_cache(self, name, service_id=""):
        path = name if isinstance(name, Path) else self.job_path / service_id / name
        self.data.pop((service_id, path.name), None)
        path.unlink(missing_ok=True)
        return True, ""


def run_job(plugin, urls, cache, monkeypatch, **extra):
    for key in list(os.environ):
        if key.startswith(("BLACKLIST_", "GREYLIST_", "WHITELIST_", "REAL_IP_")):
            monkeypatch.delenv(key)
    env = {
        "SERVER_NAME": "lists.example",
        "MULTISITE": "no",
        "USE_BLACKLIST": "yes",
        "USE_GREYLIST": "yes",
        "USE_WHITELIST": "yes",
        "USE_REAL_IP": "yes",
        "BLACKLIST_COMMUNITY_LISTS": "",
        "REAL_IP_FROM_URLS" if plugin == "realip" else f"{plugin.upper()}_IP_URLS": urls,
        **extra,
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setitem(sys.modules, "jobs", SimpleNamespace(Job=lambda *args: cache))
    monkeypatch.setitem(sys.modules, "logger", SimpleNamespace(getLogger=logging.getLogger))
    with pytest.raises(SystemExit) as result:
        runpy.run_path(str(ROOT / "src/common/core" / plugin / "jobs" / f"{plugin}-download.py"))
    return result.value.code


@pytest.mark.parametrize("plugin", PLUGINS)
def test_filtered_job_exact_entries_distinct_fragment_caches(plugin, url_server, tmp_path, monkeypatch):
    url_server.routes["/aws"] = (200, SOURCE, {"Content-Type": "application/json"})
    base = url_server.http("/aws")
    url = base + "#service=CLOUDFRONT&region=GLOBAL&ip_prefix&ipv6_prefix"
    cache = Cache(tmp_path / "cache")
    assert run_job(plugin, url, cache, monkeypatch) == 1
    name = "combined.list" if plugin == "realip" else "IP.list"
    assert cache.data["" if plugin == "realip" else "lists.example", name] == b"192.0.2.0/24\n2001:db8::/32\n"
    assert url_server.hits == ["/aws"]
    assert run_job(plugin, url, cache, monkeypatch) == 0
    assert url_server.hits == ["/aws"]
    assert run_job(plugin, base + "#service=EC2&ip_prefix", cache, monkeypatch) == 1
    assert cache.data["" if plugin == "realip" else "lists.example", name] == b"198.51.100.0/24\n"
    assert url_server.hits == ["/aws", "/aws"]
    assert run_job(plugin, url, cache, monkeypatch) == 1
    assert cache.data["" if plugin == "realip" else "lists.example", name] == b"192.0.2.0/24\n2001:db8::/32\n"


@pytest.mark.parametrize("plugin", PLUGINS)
def test_http_failure_retains_previous_service_cache(plugin, url_server, tmp_path, monkeypatch):
    url_server.routes["/list"] = (200, b"192.0.2.1\n", {})
    cache = Cache(tmp_path / "cache")
    assert run_job(plugin, url_server.http("/list"), cache, monkeypatch) == 1
    name = "combined.list" if plugin == "realip" else "IP.list"
    url_server.routes["/error"] = (503, b"error", {})
    assert run_job(plugin, url_server.http("/error"), cache, monkeypatch) == 2
    assert cache.data["" if plugin == "realip" else "lists.example", name] == b"192.0.2.1\n"


def test_ignore_user_agent_keeps_whole_line(url_server, tmp_path, monkeypatch):
    url_server.routes["/ua"] = (200, b"Mozilla/5.0 Example Bot\n", {})
    cache = Cache(tmp_path / "cache")
    assert run_job("blacklist", "", cache, monkeypatch, BLACKLIST_IGNORE_USER_AGENT_URLS=url_server.http("/ua")) == 1
    assert cache.data["lists.example", "IGNORE_USER_AGENT.list"] == b"(?:\\b)Mozilla/5.0 Example Bot(?:\\b)\n"
