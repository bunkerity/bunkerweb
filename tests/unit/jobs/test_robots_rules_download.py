"""Robots downloads publish deterministic rules and keep last-good content on failure."""

from unittest.mock import Mock

import pytest
import requests

from _other_jobs_helpers import Cache, load_job

JOB = "robotstxt/jobs/robots-txt-download.py"
DARK = "robotstxt/jobs/robots-txt-darkvisitors.py"


def test_rules_sorted_deduplicated_and_cached(tmp_path, monkeypatch, url_server):
    url_server.routes["/robots"] = (200, b"# comment\n; comment\nUser-agent: *\nDisallow: /z\nDisallow: /a\nDisallow: /z\n\n", {})
    env = {"USE_ROBOTSTXT": "yes", "ROBOTSTXT_URLS": url_server.http("/robots")}
    cache = Cache(tmp_path / "cache")
    get = requests.get
    _, status = load_job(monkeypatch, tmp_path, JOB, cache=cache, get=get, env=env)
    assert status == 1
    assert cache.data["app.example", "rules.list"] == b"Disallow: /a\nDisallow: /z\nUser-agent: *\n"
    _, status = load_job(monkeypatch, tmp_path, JOB, cache=cache, get=get, env=env)
    assert status == 0
    assert url_server.hits == ["/robots"]


def test_multisite_shares_source_and_cleans_unused_cache(tmp_path, monkeypatch):
    source = tmp_path / "robots.txt"
    source.write_text("Disallow: /private\n")
    cache = Cache(tmp_path / "cache")
    cache.cache_file("obsolete.list", b"old")
    cache.cache_file("rules.list", b"old", service_id="empty.example")
    _, status = load_job(
        monkeypatch,
        tmp_path,
        JOB,
        cache=cache,
        env={
            "SERVER_NAME": "one.example two.example empty.example disabled.example",
            "MULTISITE": "yes",
            "one.example_USE_ROBOTSTXT": "yes",
            "two.example_USE_ROBOTSTXT": "yes",
            "empty.example_USE_ROBOTSTXT": "yes",
            "one.example_ROBOTSTXT_URLS": source.as_uri(),
            "two.example_ROBOTSTXT_URLS": source.as_uri(),
        },
    )
    assert status == 1
    assert cache.data["one.example", "rules.list"] == cache.data["two.example", "rules.list"] == b"Disallow: /private\n"
    assert ("empty.example", "rules.list") not in cache.data
    assert ("", "obsolete.list") not in cache.data


@pytest.mark.parametrize("env", [{"SERVER_NAME": ""}, {}, {"USE_ROBOTSTXT": "yes", "ROBOTSTXT_COMMUNITY_LISTS": "unknown-list"}])
def test_no_download_configuration_exits_without_fetching(tmp_path, monkeypatch, env):
    get = Mock(side_effect=AssertionError("no download expected"))
    _, status = load_job(monkeypatch, tmp_path, JOB, get=get, env=env)
    assert status == 0
    get.assert_not_called()


def test_no_urls_removes_both_source_and_service_files(tmp_path, monkeypatch):
    cache = Cache(tmp_path / "cache")
    cache.cache_file("old.list", b"old")
    cache.cache_file("rules.list", b"old", service_id="app.example")
    _, status = load_job(monkeypatch, tmp_path, JOB, cache=cache, env={"USE_ROBOTSTXT": "yes"})
    assert status == 0
    assert cache.data == {}


@pytest.mark.parametrize("failure", ["http", "connection", "missing-file"])
def test_failed_source_keeps_last_published_rules(tmp_path, monkeypatch, failure):
    cache = Cache(tmp_path / "cache")
    cache.cache_file("rules.list", b"Disallow: /private\n", service_id="app.example")
    resp = requests.Response()
    resp.status_code = 503
    get = Mock(return_value=resp)
    url = "https://unit.invalid/robots.txt"
    if failure == "connection":
        get.side_effect = requests.ConnectionError("offline")
    elif failure == "missing-file":
        url = (tmp_path / "missing").as_uri()
    _, status = load_job(monkeypatch, tmp_path, JOB, cache=cache, get=get, env={"USE_ROBOTSTXT": "yes", "ROBOTSTXT_URLS": url})
    assert status == 2
    assert cache.data["app.example", "rules.list"] == b"Disallow: /private\n"
    if failure == "connection":
        assert get.call_count == 3


def _dark_response(status=200):
    response = requests.Response()
    response.status_code = status
    response._content = b"User-agent: AI\nDisallow: /private\n"
    return response


def test_darkvisitors_request_body_and_config_hash_control_refresh(tmp_path, monkeypatch):
    cache = Cache(tmp_path / "cache")
    post = Mock(return_value=_dark_response())
    env = {
        "USE_ROBOTSTXT": "yes",
        "ROBOTSTXT_DARKVISITORS_TOKEN": "unit-token",
        "ROBOTSTXT_DARKVISITORS_AGENT_TYPES": "AI, Search, ",
        "ROBOTSTXT_DARKVISITORS_DISALLOW": "/private",
    }
    _, status = load_job(monkeypatch, tmp_path, DARK, cache=cache, post=post, env=env)
    assert status == 1
    assert post.call_args.kwargs["json"] == {"agent_types": ["AI", "Search"], "disallow": "/private"}
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer unit-token"
    first = cache.data["app.example", "darkvisitors.list"]
    assert first.startswith(b"# config_hash: ")
    assert first.split(b"\n", 1)[1] == _dark_response().content
    _, status = load_job(monkeypatch, tmp_path, DARK, cache=cache, post=post, env=env)
    assert status == 0
    assert post.call_count == 1
    env["ROBOTSTXT_DARKVISITORS_DISALLOW"] = "/all"
    _, status = load_job(monkeypatch, tmp_path, DARK, cache=cache, post=post, env=env)
    assert status == 1
    assert post.call_count == 2
    assert cache.data["app.example", "darkvisitors.list"] != first


@pytest.mark.parametrize("failure", ["http", "connection", "unexpected"])
def test_darkvisitors_errors_keep_previous_content(tmp_path, monkeypatch, failure):
    cache = Cache(tmp_path / "cache")
    cache.cache_file("darkvisitors.list", b"retained", service_id="app.example")
    post = Mock(return_value=_dark_response(401))
    if failure != "http":
        post.side_effect = requests.ConnectionError("offline") if failure == "connection" else ValueError("bad response")
    _, status = load_job(
        monkeypatch,
        tmp_path,
        DARK,
        cache=cache,
        post=post,
        env={
            "USE_ROBOTSTXT": "yes",
            "ROBOTSTXT_DARKVISITORS_TOKEN": "unit-token",
            "ROBOTSTXT_DARKVISITORS_AGENT_TYPES": "AI",
        },
    )
    assert status == 2
    assert cache.data["app.example", "darkvisitors.list"] == b"retained"


def test_darkvisitors_missing_agents_removes_stale_list_without_request(tmp_path, monkeypatch):
    cache = Cache(tmp_path / "cache")
    cache.cache_file("darkvisitors.list", b"old", service_id="one.example")
    post = Mock()
    _, status = load_job(
        monkeypatch,
        tmp_path,
        DARK,
        cache=cache,
        post=post,
        env={
            "MULTISITE": "yes",
            "SERVER_NAME": "one.example disabled.example",
            "one.example_USE_ROBOTSTXT": "yes",
            "one.example_ROBOTSTXT_DARKVISITORS_TOKEN": "unit-token",
        },
    )
    assert status == 0
    assert cache.data == {}
    post.assert_not_called()
