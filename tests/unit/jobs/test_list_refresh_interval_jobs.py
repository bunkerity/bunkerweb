"""List download intervals gate requests without dropping cached entries."""

import datetime
import json
import os
import re
import time
from pathlib import Path

import pytest
import requests

from common_utils import bytes_hash
from _other_jobs_helpers import Cache, load_job

ROOT = Path(__file__).resolve().parents[3]
PLUGINS = ("blacklist", "greylist", "whitelist")
OLD = b"192.0.2.1\n"
NEW = b"198.51.100.2\n"


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    now = int(time.time())
    monkeypatch.setattr(time, "time", lambda: now)


class TimedCache(Cache):
    def get_cache(self, name, service_id="", **kwargs):
        cached = super().get_cache(name, service_id, **kwargs)
        if isinstance(cached, dict):
            cached["last_update"] = cached["path"].stat().st_mtime
        return cached


def seed_url(cache, url, age):
    name = f"{bytes_hash(url, algorithm='sha1')}.list"
    cache.cache_file(name, b"# Downloaded from " + url.encode() + b"\n" + OLD)
    timestamp = time.time() - age
    os.utime(cache.job_path / name, (timestamp, timestamp))
    return name


def run_list_job(plugin, cache, tmp_path, monkeypatch, env):
    class FixedDatetime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls.fromtimestamp(time.time(), tz)

    # Scope the clock to the job: certificate fixture validation needs the real datetime class.
    with monkeypatch.context() as clock:
        clock.setattr(datetime, "datetime", FixedDatetime)
        return load_job(
            monkeypatch,
            tmp_path,
            f"{plugin}/jobs/{plugin}-download.py",
            cache=cache,
            env={"SERVER_NAME": "lists.example", "BLACKLIST_COMMUNITY_LISTS": "", f"USE_{plugin.upper()}": "yes", **env},
            # The HTTP boundary stays real; the loader otherwise blocks every request.
            get=requests.get,
        )[1]


@pytest.mark.parametrize("plugin", PLUGINS)
@pytest.mark.parametrize(
    ("interval", "age", "refresh"),
    [
        (None, 1800, False),
        (None, 3600, True),
        (None, 5400, True),
        ("24h", 3 * 3600, False),
        ("24h", 25 * 3600, True),
        ("86400", 3 * 3600, False),
        ("1d", 25 * 3600, True),
        ("0", 60, True),
        ("0", -60, True),
        ("500ms", 0.1, False),
        ("500ms", 2, True),
        ("invalid", 1800, False),
        ("invalid", 5400, True),
    ],
)
def test_interval_controls_fetch_and_publishes_cached_entries(plugin, interval, age, refresh, url_server, tmp_path, monkeypatch):
    url_server.routes["/list"] = (200, NEW, {})
    url = url_server.http("/list")
    cache = TimedCache(tmp_path / "cache")
    name = seed_url(cache, url, age)
    env = {f"{plugin.upper()}_IP_URLS": url}
    if interval is not None:
        env[f"{plugin.upper()}_URLS_REFRESH_INTERVAL"] = interval
    # Sibling settings must not override this job's own value or default.
    env.update({f"{other.upper()}_URLS_REFRESH_INTERVAL": "0" for other in PLUGINS if other != plugin})

    assert run_list_job(plugin, cache, tmp_path, monkeypatch, env) == 1
    assert url_server.hits == (["/list"] if refresh else [])
    assert cache.data["lists.example", "IP.list"] == (NEW if refresh else OLD)
    assert cache.data["", name].endswith(NEW if refresh else OLD)


@pytest.mark.parametrize("plugin", PLUGINS)
def test_long_interval_still_fetches_uncached_url(plugin, url_server, tmp_path, monkeypatch):
    url_server.routes["/list"] = (200, NEW, {})
    cache = TimedCache(tmp_path / "cache")
    env = {f"{plugin.upper()}_IP_URLS": url_server.http("/list"), f"{plugin.upper()}_URLS_REFRESH_INTERVAL": "24h"}
    assert run_list_job(plugin, cache, tmp_path, monkeypatch, env) == 1
    assert url_server.hits == ["/list"]
    assert cache.data["lists.example", "IP.list"] == NEW


@pytest.mark.parametrize("plugin", PLUGINS)
@pytest.mark.parametrize(("status", "body"), [(503, b"unavailable"), (200, b"invalid-ip\n")])
def test_failed_refresh_keeps_last_valid_entries(plugin, status, body, url_server, tmp_path, monkeypatch):
    url_server.routes["/list"] = (status, body, {})
    url = url_server.http("/list")
    cache = TimedCache(tmp_path / "cache")
    name = seed_url(cache, url, 25 * 3600)
    timestamp = (cache.job_path / name).stat().st_mtime
    env = {f"{plugin.upper()}_IP_URLS": url, f"{plugin.upper()}_URLS_REFRESH_INTERVAL": "24h"}

    assert run_list_job(plugin, cache, tmp_path, monkeypatch, env) == 2
    assert url_server.hits == ["/list"]
    assert cache.data["lists.example", "IP.list"] == OLD
    assert cache.data["", name].endswith(OLD)
    assert (cache.job_path / name).stat().st_mtime == timestamp


@pytest.mark.parametrize("plugin", PLUGINS)
def test_multisite_interval_override_and_global_inheritance(plugin, url_server, tmp_path, monkeypatch):
    cache = TimedCache(tmp_path / "cache")
    env = {"MULTISITE": "yes", "SERVER_NAME": "daily.example hourly.example", f"{plugin.upper()}_URLS_REFRESH_INTERVAL": "24h"}
    for service in ("daily.example", "hourly.example"):
        url_server.routes[f"/{service}"] = (200, NEW, {})
        url = url_server.http(f"/{service}")
        seed_url(cache, url, 3 * 3600)
        env.update({f"{service}_USE_{plugin.upper()}": "yes", f"{service}_{plugin.upper()}_IP_URLS": url, f"{service}_BLACKLIST_COMMUNITY_LISTS": ""})
    env[f"hourly.example_{plugin.upper()}_URLS_REFRESH_INTERVAL"] = "1h"

    assert run_list_job(plugin, cache, tmp_path, monkeypatch, env) == 1
    assert url_server.hits == ["/hourly.example"]
    assert cache.data["daily.example", "IP.list"] == OLD
    assert cache.data["hourly.example", "IP.list"] == NEW


@pytest.mark.parametrize("plugin", PLUGINS)
@pytest.mark.parametrize("services", ["daily.example hourly.example", "hourly.example daily.example"])
def test_shared_url_refreshes_for_shortest_service_interval(plugin, services, url_server, tmp_path, monkeypatch):
    url_server.routes["/list"] = (200, NEW, {})
    url = url_server.http("/list")
    cache = TimedCache(tmp_path / "cache")
    seed_url(cache, url, 3 * 3600)
    env = {"MULTISITE": "yes", "SERVER_NAME": services}
    for service, interval in (("daily.example", "24h"), ("hourly.example", "1h")):
        env.update(
            {
                f"{service}_USE_{plugin.upper()}": "yes",
                f"{service}_{plugin.upper()}_IP_URLS": url,
                f"{service}_{plugin.upper()}_URLS_REFRESH_INTERVAL": interval,
                f"{service}_BLACKLIST_COMMUNITY_LISTS": "",
            }
        )
    assert run_list_job(plugin, cache, tmp_path, monkeypatch, env) == 1
    assert url_server.hits == ["/list"]
    assert cache.data["hourly.example", "IP.list"] == NEW
    # Both services converge to the shared refreshed cache on the next run.
    assert run_list_job(plugin, cache, tmp_path, monkeypatch, env) in (0, 1)
    assert url_server.hits == ["/list"]
    assert cache.data["daily.example", "IP.list"] == NEW


@pytest.mark.parametrize("plugin", PLUGINS)
def test_setting_schema_accepts_durations_and_rejects_invalid_values(plugin):
    settings = json.loads((ROOT / "src/common/core" / plugin / "plugin.json").read_text())["settings"]
    setting = settings.get(f"{plugin.upper()}_URLS_REFRESH_INTERVAL")
    assert setting is not None, "URL refresh interval setting is missing"
    assert setting["context"] == settings[f"{plugin.upper()}_IP_URLS"]["context"] == "multisite"
    assert setting["type"] == "text"
    assert setting["default"] == "1h"
    for value in ("0", "3600", "500ms", "1s", "60m", "24h", "1d", "1w", "1M", "1y"):
        assert re.search(setting["regex"], value), value
    for value in ("", "-1", "1.5h", "daily", "1H", "1h30m", " 1h", "1h ", "１２h", "1h\nOTHER=yes"):
        assert not re.search(setting["regex"], value), value
