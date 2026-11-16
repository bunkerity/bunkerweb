"""With ``BUNKERNET_FILTER_HEADERS=yes`` queued reports get the same filter as new ones before they are sent.

``bunkernet-send.py`` forwards the reports the instances queued (``/bunkernet/reports``) and the ones
it cached in ``reports.json``. Both can predate the Lua filter, so for a service that sets the option
the job keeps only the allowlisted request headers and blanks the matched header and cookie values
before ``send_reports``. With the default (``no``) the reports go out as they were queued.
"""

import copy
import json
import re
import sys
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import os
import runpy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]


class Cache:
    def __init__(self, _path):
        self.data = {}
        self.db = Mock()

    def cache_file(self, name, data):
        self.data["", name] = data
        return True, ""

    def get_cache(self, name, **_kwargs):
        return self.data.get(("", name))

    def del_cache(self, name):
        self.data.pop(("", name), None)
        return True, ""


def load_job(monkeypatch, _tmp_path, job, *, env=None, cache):
    monkeypatch.setitem(sys.modules, "jobs", SimpleNamespace(Job=lambda *_a: cache))
    monkeypatch.setitem(sys.modules, "logger", SimpleNamespace(getLogger=lambda *_a: Mock()))
    with patch.dict(os.environ, env or {}, clear=True), pytest.raises(SystemExit) as exc:
        runpy.run_path(str(ROOT / "src/common/core" / job))
    return None, exc.value.code


JOB = "bunkernet/jobs/bunkernet-send.py"
LUA = ROOT / "src" / "common" / "core" / "bunkernet" / "bunkernet.lua"
FILTER_ON = {"BUNKERNET_FILTER_HEADERS": "yes"}
ALLOWED = ["user-agent", "accept", "accept-encoding", "accept-language", "content-type", "content-length"]


def report(**extra):
    return {
        "ip": "203.0.113.5",
        "reason": "modsecurity",
        "method": "GET",
        "url": "/",
        "server_name": "www.example.com",
        "date": "2026-10-28T10:00:00Z",
        **extra,
    }


OLD = report(
    headers={"user-agent": "curl/8", "cookie": "session=abc", "authorization": "Bearer t0ken", "accept": "*/*"},
    data={
        "ids": ["941100"],
        "msgs": ["XSS"],
        "matched_vars": ["<script>", "abc", "Bearer t0ken"],
        "matched_var_names": ["ARGS:q", "REQUEST_COOKIES:session", "REQUEST_HEADERS:Authorization"],
        "anomaly_score": ["5"],
    },
)
CLEAN = report(
    date="2026-10-28T11:00:00Z",
    headers={"user-agent": "curl/8", "accept": "*/*"},
    data={"ids": ["949110"], "msgs": ["m"], "matched_vars": ["<b>"], "matched_var_names": ["ARGS:a"], "anomaly_score": ["5"]},
)


def report_for(server_name, template, date):
    return {**copy.deepcopy(template), "server_name": server_name, "date": date}


def run(monkeypatch, tmp_path, *, cached=(), queued=(), env=FILTER_ON):
    """Load the job with a forced send and return ``(batches, cache)``."""
    cache = Cache(tmp_path / "cache")
    cache.cache_file("instance.id", b"instance-id")
    cache.db.get_metadata.return_value = {"scheduler_first_start": False}
    cache.db.get_instances.return_value = []
    if cached:
        created = (datetime.now().astimezone() - timedelta(hours=25)).isoformat()
        cache.cache_file("reports.json", json.dumps({"created": created, "reports": list(cached)}).encode())
    batches = []

    def send_reports(batch, instance_id):
        assert instance_id == "instance-id"
        batches.append(json.loads(json.dumps(batch)))
        return True, 200, {}

    caller = SimpleNamespace(send_to_apis=lambda *_a, **_k: (True, {"bw": {"status": "success", "msg": copy.deepcopy(list(queued))}}))
    monkeypatch.setitem(sys.modules, "bunkernet", SimpleNamespace(send_reports=send_reports))
    monkeypatch.setitem(sys.modules, "API", SimpleNamespace(API=SimpleNamespace(from_instance=Mock())))
    monkeypatch.setitem(sys.modules, "ApiCaller", SimpleNamespace(ApiCaller=lambda _apis: caller))
    _, status = load_job(monkeypatch, tmp_path, JOB, env=env, cache=cache)
    return batches, status, cache


def test_cached_old_format_report_is_filtered(monkeypatch, tmp_path):
    batches, status, _ = run(monkeypatch, tmp_path, cached=[OLD])
    assert status == 0 and len(batches) == 1
    sent = batches[0][0]
    assert sent["headers"] == {"user-agent": "curl/8", "accept": "*/*"}
    assert sent["data"]["matched_vars"] == ["<script>", "", ""]
    assert sent["data"]["matched_var_names"] == OLD["data"]["matched_var_names"]
    assert sent["data"]["ids"] == ["941100"] and sent["url"] == "/" and sent["ip"] == OLD["ip"]


def test_queued_report_from_an_instance_is_filtered(monkeypatch, tmp_path):
    batches, _, _ = run(monkeypatch, tmp_path, cached=[CLEAN], queued=[OLD])
    assert [r["date"] for r in batches[0]] == [OLD["date"], CLEAN["date"]]
    assert "cookie" not in batches[0][0]["headers"] and "authorization" not in batches[0][0]["headers"]


def test_clean_report_passes_through_unchanged(monkeypatch, tmp_path):
    batches, _, _ = run(monkeypatch, tmp_path, cached=[CLEAN])
    assert batches == [[CLEAN]]


def test_report_without_headers_or_data_passes_through(monkeypatch, tmp_path):
    bare = report()
    batches, _, _ = run(monkeypatch, tmp_path, cached=[bare])
    assert batches == [[bare]]


def test_unaligned_values_are_removed(monkeypatch, tmp_path):
    odd = report(data={"matched_vars": ["v"], "matched_var_names": ["REQUEST_HEADERS:Cookie", "ARGS:a"]})
    batches, _, _ = run(monkeypatch, tmp_path, cached=[odd])
    assert "matched_vars" not in batches[0][0]["data"]


def test_empty_queue_still_works(monkeypatch, tmp_path):
    batches, status, cache = run(monkeypatch, tmp_path)
    assert status == 0 and batches == []
    assert ("", "reports.json") not in cache.data


def test_unsent_reports_are_cached_filtered(monkeypatch, tmp_path):
    cache = Cache(tmp_path / "cache")
    cache.cache_file("instance.id", b"instance-id")
    cache.db.get_metadata.return_value = {"scheduler_first_start": False}
    cache.db.get_instances.return_value = []
    caller = SimpleNamespace(send_to_apis=lambda *_a, **_k: (True, {"bw": {"status": "success", "msg": [copy.deepcopy(OLD)]}}))
    monkeypatch.setitem(sys.modules, "bunkernet", SimpleNamespace(send_reports=Mock(side_effect=AssertionError("below the batch size"))))
    monkeypatch.setitem(sys.modules, "API", SimpleNamespace(API=SimpleNamespace(from_instance=Mock())))
    monkeypatch.setitem(sys.modules, "ApiCaller", SimpleNamespace(ApiCaller=lambda _apis: caller))
    load_job(monkeypatch, tmp_path, JOB, env=FILTER_ON, cache=cache)
    cached = json.loads(cache.data["", "reports.json"])["reports"][0]
    assert "cookie" not in cached["headers"] and cached["data"]["matched_vars"] == ["<script>", "", ""]


def test_default_sends_queued_and_cached_reports_unfiltered(monkeypatch, tmp_path):
    batches, status, _ = run(monkeypatch, tmp_path, cached=[OLD], queued=[CLEAN], env={})
    assert status == 0 and len(batches) == 1
    assert sorted(batches[0], key=lambda r: r["date"]) == [OLD, CLEAN]


def test_default_caches_unsent_reports_unfiltered(monkeypatch, tmp_path):
    cache = Cache(tmp_path / "cache")
    cache.cache_file("instance.id", b"instance-id")
    cache.db.get_metadata.return_value = {"scheduler_first_start": False}
    cache.db.get_instances.return_value = []
    caller = SimpleNamespace(send_to_apis=lambda *_a, **_k: (True, {"bw": {"status": "success", "msg": [copy.deepcopy(OLD)]}}))
    monkeypatch.setitem(sys.modules, "bunkernet", SimpleNamespace(send_reports=Mock(side_effect=AssertionError("below the batch size"))))
    monkeypatch.setitem(sys.modules, "API", SimpleNamespace(API=SimpleNamespace(from_instance=Mock())))
    monkeypatch.setitem(sys.modules, "ApiCaller", SimpleNamespace(ApiCaller=lambda _apis: caller))
    load_job(monkeypatch, tmp_path, JOB, cache=cache)
    assert json.loads(cache.data["", "reports.json"])["reports"] == [OLD]


def test_explicit_no_sends_reports_unfiltered(monkeypatch, tmp_path):
    batches, _, _ = run(monkeypatch, tmp_path, cached=[OLD], env={"BUNKERNET_FILTER_HEADERS": "no"})
    assert batches == [[OLD]]


MULTISITE = {"MULTISITE": "yes", "SERVER_NAME": "a.example b.example"}


def test_multisite_filters_only_the_services_that_set_the_option(monkeypatch, tmp_path):
    env = {**MULTISITE, "a.example_BUNKERNET_FILTER_HEADERS": "yes", "b.example_BUNKERNET_FILTER_HEADERS": "no"}
    a, b = report_for("a.example", OLD, "2026-10-28T10:00:00Z"), report_for("b.example", OLD, "2026-10-28T11:00:00Z")
    batches, _, _ = run(monkeypatch, tmp_path, cached=[a, b], env=env)
    sent = {r["server_name"]: r for r in batches[0]}
    assert sent["a.example"]["headers"] == {"user-agent": "curl/8", "accept": "*/*"}
    assert sent["a.example"]["data"]["matched_vars"] == ["<script>", "", ""]
    assert sent["b.example"] == b


@pytest.mark.parametrize("global_value, filtered", [("yes", True), ("no", False)])
def test_multisite_unknown_service_uses_the_global_value(monkeypatch, tmp_path, global_value, filtered):
    env = {**MULTISITE, "BUNKERNET_FILTER_HEADERS": global_value}
    other = report_for("other.example", OLD, OLD["date"])
    batches, _, _ = run(monkeypatch, tmp_path, cached=[other], env=env)
    assert (batches[0][0]["headers"] != other["headers"]) is filtered


def test_singlesite_global_value_applies_whatever_the_report_service(monkeypatch, tmp_path):
    odd = report_for("any.example", OLD, OLD["date"])
    batches, _, _ = run(monkeypatch, tmp_path, cached=[odd], env={"BUNKERNET_FILTER_HEADERS": "yes", "any.example_BUNKERNET_FILTER_HEADERS": "no"})
    assert batches[0][0]["headers"] == {"user-agent": "curl/8", "accept": "*/*"}


def test_python_and_lua_allowlists_match():
    table = re.search(r"local REPORT_HEADERS = \{(.*?)\n\}", LUA.read_text(), re.S).group(1)
    assert re.findall(r'"([^"]+)"', table) == ALLOWED
    source = (ROOT / "src" / "common" / "core" / JOB).read_text()
    constant = re.search(r"REPORT_HEADERS = \((.*?)\)", source, re.S).group(1)
    assert re.findall(r'"([^"]+)"', constant) == ALLOWED


@pytest.mark.parametrize("value", ["yes", "no"])
def test_database_cached_reports_are_filtered_before_recache(monkeypatch, tmp_path, db, value):
    from fixtures.seed import seed_minimal

    seed_minimal(db)
    created = datetime.now().astimezone().isoformat()
    raw = json.dumps({"created": created, "reports": [OLD]}).encode()
    assert db.upsert_job_cache(None, "reports.json", raw, job_name="testjob", checksum="original") == ""
    get_cache, cache_file = Cache.get_cache, Cache.cache_file

    def read(self, name, **kwargs):
        if name == "reports.json":
            return db.get_job_cache_file("testjob", name)
        return get_cache(self, name, **kwargs)

    def persist(self, name, content):
        if name == "reports.json":
            assert db.upsert_job_cache(None, name, content, job_name="testjob", checksum="rewritten") == ""
        return cache_file(self, name, content)

    monkeypatch.setattr(Cache, "get_cache", read)
    monkeypatch.setattr(Cache, "cache_file", persist)
    batches, status, _ = run(monkeypatch, tmp_path, env={"BUNKERNET_FILTER_HEADERS": value})
    assert status == 0 and batches == []
    stored = json.loads(db.get_job_cache_file("testjob", "reports.json"))["reports"][0]
    if value == "yes":
        assert stored["headers"] == {"user-agent": "curl/8", "accept": "*/*"}
        assert stored["data"]["matched_vars"] == ["<script>", "", ""]
    else:
        assert stored == OLD
