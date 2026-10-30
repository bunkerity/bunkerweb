"""DNSBL ignore lists filter, deduplicate, cache and isolate per-service content."""

from unittest.mock import Mock

import pytest
import requests

from _other_jobs_helpers import Cache, load_job

JOB = "dnsbl/jobs/dnsbl-download.py"


def test_local_list_filters_invalid_addresses_and_reuses_fresh_cache(tmp_path, monkeypatch, url_server):
    url_server.routes["/ignore"] = (200, b"# comment\n; comment\n192.0.2.4 note\n192.0.2.4\n2001:db8::/32\nnot-ip\n192.0.2.1/24\n\n", {})
    url = url_server.http("/ignore")
    cache = Cache(tmp_path / "cache")
    get = requests.get
    env = {"DNSBL_IGNORE_IP_URLS": url}
    _, status = load_job(monkeypatch, tmp_path, JOB, cache=cache, env=env, get=get)
    assert status == 1
    assert cache.data["app.example", "IGNORE_IP.list"] == b"192.0.2.4\n2001:db8::/32\n"
    _, status = load_job(monkeypatch, tmp_path, JOB, cache=cache, env=env, get=get)
    assert status == 0
    assert url_server.hits == ["/ignore"]


def test_multisite_shared_url_downloaded_once_and_unused_files_removed(tmp_path, monkeypatch, url_server):
    url_server.routes["/ignore"] = (200, b"203.0.113.5\n", {})
    cache = Cache(tmp_path / "cache")
    cache.cache_file("obsolete.list", b"old")
    cache.cache_file("IGNORE_IP.list", b"old", service_id="empty.example")
    _, status = load_job(
        monkeypatch,
        tmp_path,
        JOB,
        cache=cache,
        get=requests.get,
        env={
            "SERVER_NAME": "one.example two.example empty.example disabled.example",
            "MULTISITE": "yes",
            "one.example_DNSBL_IGNORE_IP_URLS": url_server.http("/ignore"),
            "two.example_DNSBL_IGNORE_IP_URLS": url_server.http("/ignore"),
            "disabled.example_USE_DNSBL": "no",
        },
    )
    assert status == 1
    assert cache.data["one.example", "IGNORE_IP.list"] == cache.data["two.example", "IGNORE_IP.list"] == b"203.0.113.5\n"
    assert ("empty.example", "IGNORE_IP.list") not in cache.data
    assert ("", "obsolete.list") not in cache.data
    assert url_server.hits == ["/ignore"]


@pytest.mark.parametrize("failure", ["http", "connection", "missing-file"])
def test_failed_source_keeps_previous_service_list(tmp_path, monkeypatch, failure, url_server):
    cache = Cache(tmp_path / "cache")
    cache.cache_file("IGNORE_IP.list", b"192.0.2.5\n", service_id="app.example")
    get = requests.get
    url = url_server.http("/missing")
    if failure == "connection":
        get = Mock(side_effect=requests.ConnectionError("offline"))
    elif failure == "missing-file":
        url = (tmp_path / "missing.list").as_uri()
    _, status = load_job(monkeypatch, tmp_path, JOB, cache=cache, get=get, env={"DNSBL_IGNORE_IP_URLS": url})
    assert status == 2
    assert cache.data["app.example", "IGNORE_IP.list"] == b"192.0.2.5\n"
    if failure == "connection":
        assert get.call_count == 3


def test_no_urls_purges_global_and_service_cache(tmp_path, monkeypatch):
    cache = Cache(tmp_path / "cache")
    cache.cache_file("source.list", b"old")
    cache.cache_file("IGNORE_IP.list", b"old", service_id="app.example")
    _, status = load_job(monkeypatch, tmp_path, JOB, cache=cache)
    assert status == 0
    assert cache.data == {}
    assert list(cache.job_path.rglob("*.list")) == []


@pytest.mark.parametrize("env", [{"SERVER_NAME": ""}, {"USE_DNSBL": "no"}])
def test_inactive_job_leaves_cache_untouched(tmp_path, monkeypatch, env):
    cache = Cache(tmp_path / "cache")
    cache.cache_file("IGNORE_IP.list", b"retained", service_id="app.example")
    _, status = load_job(monkeypatch, tmp_path, JOB, cache=cache, env=env)
    assert status == 0
    assert cache.data == {("app.example", "IGNORE_IP.list"): b"retained"}


def test_file_source_cache_write_failure_reports_failure(tmp_path, monkeypatch):
    source = tmp_path / "ignore.list"
    source.write_text("198.51.100.8\n")
    cache = Cache(tmp_path / "cache")
    real_write = cache.cache_file

    def cache_file(name, data, **kwargs):
        if name == "IGNORE_IP.list":
            return False, "disk full"
        return real_write(name, data, **kwargs)

    monkeypatch.setattr(cache, "cache_file", cache_file)
    _, status = load_job(monkeypatch, tmp_path, JOB, cache=cache, env={"DNSBL_IGNORE_IP_URLS": source.as_uri()})
    assert status == 2
    assert ("app.example", "IGNORE_IP.list") not in cache.data
