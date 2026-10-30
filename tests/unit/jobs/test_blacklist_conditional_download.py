"""Conditional GET (ETag / Last-Modified) in the blacklist download job, against a local server and a cache that can age."""

import logging
import os
import runpy
import sys
from hashlib import sha1, sha256
from pathlib import Path
from time import time
from types import SimpleNamespace

import pytest
import requests

from common_utils import bytes_hash

ROOT = Path(os.environ.get("BW_BLACKLIST_JOB_ROOT", Path(__file__).resolve().parents[3]))
JOB_SCRIPT = ROOT / "src/common/core/blacklist/jobs/blacklist-download.py"
ETAG = '"v1"'
LAST_MODIFIED = "Wed, 21 Oct 2026 07:28:00 GMT"
ENTRIES = b"192.0.2.1\n198.51.100.0/24\n"


class Cache:
    """Job cache stand-in that keeps last_update per file, so a test can push it past the 1-hour skip."""

    def __init__(self, path):
        self.job_path = path
        self.data = {}
        self.updated = {}

    def get_cache(self, name, service_id="", **kwargs):
        data = self.data.get((service_id, name))
        return {"last_update": self.updated[service_id, name], "data": data} if data is not None else None

    def cache_file(self, name, data, service_id="", **kwargs):
        self.data[service_id, name] = data
        self.updated[service_id, name] = time()
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
        self.updated.pop((service_id, path.name), None)
        path.unlink(missing_ok=True)
        return True, ""

    def url_files(self):
        return {name: data for (service_id, name), data in self.data.items() if not service_id}

    def age(self):
        for key in self.updated:
            self.updated[key] -= 7200


def run_job(cache, monkeypatch, **urls):
    for key in list(os.environ):
        if key.startswith("BLACKLIST_"):
            monkeypatch.delenv(key)
    for key, value in {"SERVER_NAME": "lists.example", "MULTISITE": "no", "USE_BLACKLIST": "yes", "BLACKLIST_COMMUNITY_LISTS": "", **urls}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setitem(sys.modules, "jobs", SimpleNamespace(Job=lambda *args: cache))
    monkeypatch.setitem(sys.modules, "logger", SimpleNamespace(getLogger=logging.getLogger))
    with pytest.raises(SystemExit) as result:
        runpy.run_path(str(JOB_SCRIPT))
    return result.value.code


def conditional_route(seen, etag=ETAG, body=ENTRIES):
    """Answer 304 when the client replays ``etag``, else 200 with validators; record what was sent."""

    def route(headers):
        seen.append((headers.get("If-None-Match"), headers.get("If-Modified-Since")))
        if headers.get("If-None-Match") == etag:
            return 304, b"", {"ETag": etag}
        return 200, body, {"ETag": etag, "Last-Modified": LAST_MODIFIED}

    return route


@pytest.mark.parametrize("etag", (pytest.param(ETAG, id="strong-etag"), pytest.param('W/"v1"', id="weak-etag")))
def test_validators_stored_then_replayed_and_304_reuses_entries(etag, url_server, tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    seen = []
    url_server.routes["/ips"] = conditional_route(seen, etag=etag)
    url = url_server.http("/ips")
    cache = Cache(tmp_path)

    assert run_job(cache, monkeypatch, BLACKLIST_IP_URLS=url) == 1
    assert seen == [(None, None)]
    assert list(cache.url_files().values()) == [f"# Downloaded from {url}\n# ETag: {etag}\n# Last-Modified: {LAST_MODIFIED}\n".encode() + ENTRIES]

    # Within the hour: no request, and the header lines are not read back as entries
    assert run_job(cache, monkeypatch, BLACKLIST_IP_URLS=url) == 0
    assert len(seen) == 1
    assert cache.data["lists.example", "IP.list"] == ENTRIES

    # Past the hour: both validators replayed as stored, 304 keeps the entries and restarts the hour
    cache.age()
    caplog.clear()
    assert run_job(cache, monkeypatch, BLACKLIST_IP_URLS=url) == 0
    assert seen[-1] == (etag, LAST_MODIFIED)
    assert cache.data["lists.example", "IP.list"] == ENTRIES
    assert all(time() - updated < 60 for (service_id, _), updated in cache.updated.items() if not service_id)
    assert "Not modified: 1" in caplog.text


def test_304_on_header_only_cache_writes_no_list(url_server, tmp_path, monkeypatch):
    seen = []
    url_server.routes["/ips"] = conditional_route(seen, body=b"# no entries yet\n")
    url = url_server.http("/ips")
    cache = Cache(tmp_path)
    assert run_job(cache, monkeypatch, BLACKLIST_IP_URLS=url) == 0
    assert list(cache.url_files().values()) == [f"# Downloaded from {url}\n# ETag: {ETAG}\n# Last-Modified: {LAST_MODIFIED}\n".encode()]

    cache.age()
    assert run_job(cache, monkeypatch, BLACKLIST_IP_URLS=url) == 0
    assert seen[-1] == (ETAG, LAST_MODIFIED)
    assert ("lists.example", "IP.list") not in cache.data


def test_failed_url_keeps_its_last_cached_entries(url_server, tmp_path, monkeypatch, caplog):
    url_server.routes["/a"] = (200, b"192.0.2.1\n", {})
    url_server.routes["/b"] = (200, b"198.51.100.1\n", {})
    urls = f"{url_server.http('/a')} {url_server.http('/b')}"
    cache = Cache(tmp_path)
    assert run_job(cache, monkeypatch, BLACKLIST_IP_URLS=urls) == 1

    # /b goes down and /a changes: /a's update lands, /b's last good entries stay
    url_server.routes["/a"] = (200, b"192.0.2.2\n", {})
    url_server.routes["/b"] = (503, b"down", {})
    cache.age()
    assert run_job(cache, monkeypatch, BLACKLIST_IP_URLS=urls) == 2
    assert cache.data["lists.example", "IP.list"] == b"192.0.2.2\n198.51.100.1\n"
    assert "Using the last cached IP entries" in caplog.text


def test_changed_validator_downloads_new_entries(url_server, tmp_path, monkeypatch):
    seen = []
    url_server.routes["/ips"] = conditional_route(seen)
    url = url_server.http("/ips")
    cache = Cache(tmp_path)
    assert run_job(cache, monkeypatch, BLACKLIST_IP_URLS=url) == 1

    url_server.routes["/ips"] = conditional_route(seen, etag='"v2"', body=b"203.0.113.7\n")
    cache.age()
    assert run_job(cache, monkeypatch, BLACKLIST_IP_URLS=url) == 1
    assert seen[-1] == (ETAG, LAST_MODIFIED)
    assert cache.data["lists.example", "IP.list"] == b"203.0.113.7\n"
    assert b'# ETag: "v2"\n' in next(iter(cache.url_files().values()))


def test_unsolicited_304_without_cache_is_a_failure(url_server, tmp_path, monkeypatch):
    url_server.routes["/ips"] = (304, b"", {})
    cache = Cache(tmp_path)
    assert run_job(cache, monkeypatch, BLACKLIST_IP_URLS=url_server.http("/ips")) == 2
    assert ("lists.example", "IP.list") not in cache.data
    assert not cache.url_files()


def test_connection_refused_retries_three_times_then_fails(tmp_path, monkeypatch):
    attempts, waits = [], []

    def refuse(*args, **kwargs):
        attempts.append(args[0])
        raise requests.exceptions.ConnectionError("refused")

    # The job binds both names at import time, so patch them before runpy executes it
    monkeypatch.setattr("requests.get", refuse)
    monkeypatch.setattr("time.sleep", waits.append)
    cache = Cache(tmp_path)
    assert run_job(cache, monkeypatch, BLACKLIST_IP_URLS="http://127.0.0.1:9/ips") == 2
    assert len(attempts) == 3
    assert waits == [3, 3]
    assert not cache.url_files()


@pytest.mark.parametrize(
    "header",
    (
        pytest.param(b"", id="legacy-cache-without-validators"),
        pytest.param(b'# ETag: "a\rb"\n', id="validator-with-carriage-return"),
    ),
)
def test_cache_without_usable_validator_gets_plain_download(header, url_server, tmp_path, monkeypatch):
    seen = []
    url_server.routes["/ips"] = conditional_route(seen)
    url = url_server.http("/ips")
    cache = Cache(tmp_path)
    assert run_job(cache, monkeypatch, BLACKLIST_IP_URLS=url) == 1

    [url_file] = cache.url_files()
    cache.cache_file(url_file, f"# Downloaded from {url}\n".encode() + header + ENTRIES)
    cache.age()
    assert run_job(cache, monkeypatch, BLACKLIST_IP_URLS=url) == 0
    assert seen[-1] == (None, None)
    assert f"# ETag: {ETAG}\n".encode() in cache.url_files()[url_file]


def test_url_cache_file_named_by_sha256_of_kind_and_url(url_server, tmp_path, monkeypatch):
    url_server.routes["/ips"] = (200, ENTRIES, {})
    url = url_server.http("/ips")
    cache = Cache(tmp_path)
    assert run_job(cache, monkeypatch, BLACKLIST_IP_URLS=url) == 1
    assert list(cache.url_files()) == [f"{sha256(f'IP:{url}'.encode()).hexdigest()}.list"]


def test_legacy_sha1_url_file_is_removed(url_server, tmp_path, monkeypatch):
    url_server.routes["/ips"] = (200, ENTRIES, {})
    url = url_server.http("/ips")
    cache = Cache(tmp_path)
    legacy = f"{sha1(url.encode()).hexdigest()}.list"
    cache.cache_file(legacy, f"# Downloaded from {url}\n".encode() + ENTRIES)
    assert run_job(cache, monkeypatch, BLACKLIST_IP_URLS=url) == 1
    assert legacy not in cache.url_files()
    assert not (tmp_path / legacy).exists()


def test_failure_for_one_kind_does_not_skip_another_kind(url_server, tmp_path, monkeypatch):
    url_server.routes["/mixed"] = (200, b"/admin\n", {})
    url = url_server.http("/mixed")
    ip_url_file = f"{sha256(f'IP:{url}'.encode()).hexdigest()}.list"

    class FailingIpCache(Cache):
        def cache_file(self, name, data, service_id="", **kwargs):
            if name == ip_url_file:
                raise OSError("disk full")
            return super().cache_file(name, data, service_id, **kwargs)

    cache = FailingIpCache(tmp_path)
    # IP runs first (KINDS order): its cache write fails, URI must still download and publish its list
    assert run_job(cache, monkeypatch, BLACKLIST_IP_URLS=url, BLACKLIST_URI_URLS=url) == 2
    assert cache.data["lists.example", "URI.list"] == b"/admin\n"


def test_same_url_under_two_kinds_keeps_entries_apart(url_server, tmp_path, monkeypatch):
    seen = []
    url_server.routes["/mixed"] = conditional_route(seen, body=b"/admin\n")
    url = url_server.http("/mixed")
    cache = Cache(tmp_path)
    assert run_job(cache, monkeypatch, BLACKLIST_USER_AGENT_URLS=url, BLACKLIST_URI_URLS=url) == 1
    assert cache.data["lists.example", "USER_AGENT.list"] == b"(?:\\b)/admin(?:\\b)\n"
    assert cache.data["lists.example", "URI.list"] == b"/admin\n"

    # The 304 path must keep them apart too
    cache.age()
    assert run_job(cache, monkeypatch, BLACKLIST_USER_AGENT_URLS=url, BLACKLIST_URI_URLS=url) == 0
    assert seen[-2:] == [(ETAG, LAST_MODIFIED)] * 2
    assert cache.data["lists.example", "URI.list"] == b"/admin\n"
