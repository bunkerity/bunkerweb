"""Reports queued before an upgrade get the same filter as new ones before they are sent.

``bunkernet-send.py`` forwards the reports the instances queued (``/bunkernet/reports``) and the ones
it cached in ``reports.json``. Both can predate the Lua filter, so the job keeps only the allowlisted
request headers and blanks the matched header and cookie values before ``send_reports``.
"""

import json
import re
import sys
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

from _other_jobs_helpers import ROOT, Cache, load_job

JOB = "bunkernet/jobs/bunkernet-send.py"
LUA = ROOT / "src" / "common" / "core" / "bunkernet" / "bunkernet.lua"
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


def run(monkeypatch, tmp_path, *, cached=(), queued=()):
    """Load the job with a forced send and return ``(batches, cache)``."""
    cache = Cache(tmp_path / "cache")
    cache.cache_file("instance.id", b"instance-id")
    cache.db.get_metadata.return_value = {"scheduler_first_start": False}
    cache.db.get_instances.return_value = []
    if cached:
        created = (datetime.now().astimezone() - timedelta(hours=25)).isoformat()
        cache.cache_file("reports.json", json.dumps({"created": created, "reports": list(cached)}).encode())
    batches = []

    def send_reports(batch):
        batches.append(json.loads(json.dumps(batch)))
        return True, 200, {}

    caller = SimpleNamespace(send_to_apis=lambda *_a, **_k: (True, {"bw": {"status": "success", "msg": list(queued)}}))
    monkeypatch.setitem(sys.modules, "bunkernet", SimpleNamespace(send_reports=send_reports))
    monkeypatch.setitem(sys.modules, "API", SimpleNamespace(API=SimpleNamespace(from_instance=Mock())))
    monkeypatch.setitem(sys.modules, "ApiCaller", SimpleNamespace(ApiCaller=lambda _apis: caller))
    _, status = load_job(monkeypatch, tmp_path, JOB, cache=cache)
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
    caller = SimpleNamespace(send_to_apis=lambda *_a, **_k: (True, {"bw": {"status": "success", "msg": [OLD]}}))
    monkeypatch.setitem(sys.modules, "bunkernet", SimpleNamespace(send_reports=Mock(side_effect=AssertionError("below the batch size"))))
    monkeypatch.setitem(sys.modules, "API", SimpleNamespace(API=SimpleNamespace(from_instance=Mock())))
    monkeypatch.setitem(sys.modules, "ApiCaller", SimpleNamespace(ApiCaller=lambda _apis: caller))
    load_job(monkeypatch, tmp_path, JOB, cache=cache)
    cached = json.loads(cache.data["", "reports.json"])["reports"][0]
    assert "cookie" not in cached["headers"] and cached["data"]["matched_vars"] == ["<script>", "", ""]


def test_python_and_lua_allowlists_match():
    table = re.search(r"local REPORT_HEADERS = \{(.*?)\n\}", LUA.read_text(), re.S).group(1)
    assert re.findall(r'"([^"]+)"', table) == ALLOWED
    source = (ROOT / "src" / "common" / "core" / JOB).read_text()
    constant = re.search(r"REPORT_HEADERS = \((.*?)\)", source, re.S).group(1)
    assert re.findall(r'"([^"]+)"', constant) == ALLOWED
