"""Release selection and pagination, including the shipped job's cache and error paths."""

import json
import runpy
import sys
import time
import types
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

import common_utils

ROOT = Path(__file__).resolve().parents[3]
JOB_FILE = ROOT / "src/common/core/jobs/jobs/update-check.py"


def release(tag, **kwargs):
    return {"tag_name": tag, "prerelease": False, "draft": False, **kwargs}


def response(batch, status=200):
    result = requests.Response()
    result.status_code = status
    result._content = json.dumps(batch).encode()
    return result


@pytest.mark.parametrize(
    "current,tags,expected",
    [
        ("1.7.0", ["v1.8.0", "v1.7.2", "v1.7.10", "v1.6.99"], "v1.7.10"),
        ("1.7.0", ["v1.8.0", "v1.6.99"], None),
        ("1.7.0-alpha", ["v1.8.0", "v1.6.99"], None),
        ("1.7.0-alpha", ["v1.7.0-alpha", "v1.7.0-alpha2"], "v1.7.0-alpha2"),
        ("1.7.0~alpha", ["v1.7.0-alpha2", "v1.7.0-beta1"], "v1.7.0-beta1"),
        ("1.7.0-alpha", ["v1.7.0-beta1", "v1.7.0-rc1"], "v1.7.0-rc1"),
        ("1.7.0-alpha", ["v1.7.0-rc1", "v1.7.0"], "v1.7.0"),
        ("1.7.0", ["v1.7.1-rc1", "v1.7.0"], "v1.7.0"),
        ("1.7.0", ["v1.7.1-rc1"], None),
        ("dev", ["v1.8.0-rc1", "v1.7.2", "v1.6.99"], "v1.7.2"),
    ],
)
def test_selects_highest_eligible_version_in_installed_line(current, tags, expected):
    releases = [release(tag, prerelease="-" in tag) for tag in tags]
    picked = common_utils.pick_latest_line_release(releases, current)
    assert (picked["tag_name"] if picked else None) == expected


def test_ignores_drafts_invalid_tags_and_prerelease_flags_for_stable_install():
    expected = release("v1.7.1")
    releases = [
        release("v1.7.99", draft=True),
        release("v1.7.98", prerelease=True),
        release("v1.7.97-rc1"),
        release("invalid"),
        release(None),
        {},
        None,
        expected,
    ]
    assert common_utils.pick_latest_line_release(releases, "1.7.0") is expected


@pytest.mark.parametrize("batches,count", [([[]], 0), ([[release("v1.7.1")]], 1), ([[release("v1.8.0")] * 100, []], 100)])
def test_pagination_stops_on_short_or_empty_page(batches, count):
    get = Mock(side_effect=[response(batch) for batch in batches])
    assert len(common_utils.fetch_bunkerweb_releases(get)) == count
    assert get.call_count == len(batches)
    for page, call in enumerate(get.call_args_list, 1):
        assert call.args == (f"https://api.github.com/repos/bunkerity/bunkerweb/releases?per_page=100&page={page}",)
        assert call.kwargs == {"headers": {"User-Agent": "BunkerWeb"}, "timeout": 3}


def test_pagination_reaches_older_page_and_has_a_hard_cap():
    get = Mock(side_effect=[response([release("v1.8.0")] * 100), response([release("v1.7.1")])])
    releases = common_utils.fetch_bunkerweb_releases(get)
    assert common_utils.pick_latest_line_release(releases, "1.7.0")["tag_name"] == "v1.7.1"
    get = Mock(return_value=response([release("v1.8.0")] * 100))
    assert len(common_utils.fetch_bunkerweb_releases(get)) == 1000
    assert get.call_count == 10


@pytest.mark.parametrize("status", [403, 429, 500])
def test_github_http_errors_propagate_even_after_a_full_page(status):
    get = Mock(side_effect=[response([release("v1.8.0")] * 100), response({"message": "GitHub error"}, status)])
    with pytest.raises(requests.exceptions.HTTPError):
        common_utils.fetch_bunkerweb_releases(get)


def test_github_error_object_is_not_a_partial_release_listing():
    with pytest.raises(ValueError):
        common_utils.fetch_bunkerweb_releases(Mock(return_value=response({"message": "API error"})))


def run_job(monkeypatch, get, current="1.7.0-alpha", cached=None, age=0):
    logger = Mock()
    job = Mock()
    job.get_cache.return_value = {"data": json.dumps(cached).encode(), "last_update": time.time() - age} if cached else None
    monkeypatch.setitem(sys.modules, "jobs", types.SimpleNamespace(Job=lambda *args: job))
    monkeypatch.setitem(sys.modules, "logger", types.SimpleNamespace(getLogger=lambda *args: logger))
    monkeypatch.setattr(common_utils, "get_version", lambda: current)
    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr(time, "sleep", lambda *args: None)
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(str(JOB_FILE), run_name="__main__")
    return exited.value.code, logger, job


def test_job_announces_same_line_prerelease(monkeypatch):
    get = Mock(return_value=response([release("v1.8.0"), release("v1.7.0-beta1", prerelease=True)]))
    code, logger, job = run_job(monkeypatch, get)
    assert code == 0
    assert any("1.7.0-beta1" in call.args[0] for call in logger.warning.call_args_list)
    assert json.loads(job.cache_file.call_args.args[1])["tag_name"] == "v1.7.0-beta1"


@pytest.mark.parametrize("age", [0, 7200])
def test_job_never_uses_off_line_cache_on_api_failure(monkeypatch, age):
    get = Mock(side_effect=requests.exceptions.HTTPError("GitHub unavailable"))
    code, logger, job = run_job(monkeypatch, get, cached=release("v1.8.0"), age=age)
    assert code == 0
    assert get.called
    assert not any("A NEW VERSION" in call.args[0] for call in logger.warning.call_args_list)
    job.cache_file.assert_not_called()


@pytest.mark.parametrize("age", [0, 7200])
def test_job_keeps_eligible_cache_and_cooldown(monkeypatch, age):
    get = Mock(side_effect=requests.exceptions.HTTPError("GitHub unavailable"))
    code, logger, job = run_job(monkeypatch, get, cached=release("v1.7.0-beta1", prerelease=True), age=age)
    assert code == 0
    assert get.called == bool(age)
    assert any("1.7.0-beta1" in call.args[0] for call in logger.warning.call_args_list)


def test_job_rejects_prerelease_cache_on_stable_install(monkeypatch):
    get = Mock(return_value=response([release("v1.7.1")]))
    code, logger, job = run_job(monkeypatch, get, current="1.7.0", cached=release("v1.7.2-rc1", prerelease=True))
    assert code == 0
    assert get.called
    assert json.loads(job.cache_file.call_args.args[1])["tag_name"] == "v1.7.1"


def test_job_retries_connection_errors_then_skips_without_failing(monkeypatch):
    get = Mock(side_effect=requests.exceptions.ConnectionError("offline"))
    code, logger, job = run_job(monkeypatch, get)
    assert code == 0
    assert get.call_count == 3
    logger.error.assert_not_called()


def test_job_does_not_log_an_older_line_as_an_upgrade(monkeypatch):
    get = Mock(return_value=response([release("v1.6.99"), release("v1.7.0-alpha2", prerelease=True)]))
    code, logger, job = run_job(monkeypatch, get)
    assert code == 0
    assert not any("newer release line" in call.args[0] for call in logger.info.call_args_list)


def test_job_only_logs_upgrade_guide_for_newer_line(monkeypatch):
    get = Mock(return_value=response([release("v1.8.0"), release("v1.7.0-alpha2", prerelease=True)]))
    code, logger, job = run_job(monkeypatch, get)
    assert code == 0
    assert any("https://docs.bunkerweb.io/1.7/upgrading/" in call.args[0] for call in logger.info.call_args_list)
    assert json.loads(job.cache_file.call_args.args[1])["tag_name"] == "v1.7.0-alpha2"


@pytest.mark.parametrize("cached", [None, release("v1.8.0"), release("v1.7.0-beta1", prerelease=True)])
def test_job_with_no_matching_release_only_reuses_eligible_cache(monkeypatch, cached):
    get = Mock(return_value=response([release("v1.8.0"), release("v1.6.99")]))
    code, logger, job = run_job(monkeypatch, get, cached=cached, age=7200)
    assert code == (0 if cached and cached["tag_name"] == "v1.7.0-beta1" else 2)
    assert not any("Latest Version: \033[1;92m1.8" in call.args[0] for call in logger.warning.call_args_list)
    job.cache_file.assert_not_called()
