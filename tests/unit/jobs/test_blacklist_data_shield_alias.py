"""The retired Data-Shield "critical" community list id keeps resolving, to the merged upstream list."""

import json
import logging
import os
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

ROOT = Path(os.environ.get("BW_LISTS_PORT_ROOT", Path(__file__).resolve().parents[3]))
JOB = ROOT / "src/common/core/blacklist/jobs/blacklist-download.py"
BASE = "https://raw.githubusercontent.com/duggytuxy/Data-Shield_IPv4_Blocklist/refs/heads/main/"
MERGED_URL = BASE + "prod_data-shield_ipv4_blocklist.txt"
AGGRESSIVE = "ip:laurent-minne-data-shield-aggressive"
CRITICAL = "ip:laurent-minne-data-shield-critical"


class Cache:
    def __init__(self, path):
        self.job_path = path
        self.data = {}

    def get_cache(self, name, **kwargs):
        return None

    def cache_file(self, name, data, service_id="", **kwargs):
        self.data[service_id, name] = data
        return True, ""

    def cache_hash(self, name, service_id=""):
        return None

    def del_cache(self, name, service_id="", **kwargs):
        return True, ""


def run_job(tmp_path, monkeypatch, **env):
    for key in list(os.environ):
        if key.startswith("BLACKLIST_") or key.endswith(("_USE_BLACKLIST", "_BLACKLIST_COMMUNITY_LISTS")):
            monkeypatch.delenv(key)
    for key, value in {"SERVER_NAME": "a.example", "MULTISITE": "no", "USE_BLACKLIST": "yes", **env}.items():
        monkeypatch.setenv(key, value)
    cache = Cache(tmp_path / "cache")
    requested = []

    def fake_get(url, **kwargs):
        requested.append(url)
        return SimpleNamespace(status_code=200, content=b"192.0.2.1\n", headers={})

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setitem(sys.modules, "jobs", SimpleNamespace(Job=lambda *args: cache))
    monkeypatch.setitem(sys.modules, "logger", SimpleNamespace(getLogger=logging.getLogger))
    with pytest.raises(SystemExit) as result:
        runpy.run_path(str(JOB))
    return result.value.code, requested, cache


def test_retired_critical_option_stays_in_plugin_json():
    options = json.loads((ROOT / "src/common/core/blacklist/plugin.json").read_text())["settings"]["BLACKLIST_COMMUNITY_LISTS"]["multiselect"]
    by_id = {option["id"]: option for option in options}
    assert list(by_id).index(CRITICAL) == list(by_id).index(AGGRESSIVE) + 1
    assert "retired" in by_id[CRITICAL]["label"]
    assert by_id[CRITICAL]["value"] == MERGED_URL


def notices(caplog):
    return [r for r in caplog.records if "deprecated" in r.getMessage().lower()]


def test_critical_id_uses_merged_list_globally(tmp_path, monkeypatch, caplog):
    code, requested, cache = run_job(tmp_path, monkeypatch, BLACKLIST_COMMUNITY_LISTS=CRITICAL)
    assert code == 1
    assert requested == [MERGED_URL]
    assert cache.data["a.example", "IP.list"] == b"192.0.2.1\n"
    (notice,) = notices(caplog)
    assert "paid Data-Shield Pro" in notice.getMessage()
    assert "free Community Standard" in notice.getMessage()


def test_both_ids_download_once(tmp_path, monkeypatch, caplog):
    code, requested, _ = run_job(tmp_path, monkeypatch, BLACKLIST_COMMUNITY_LISTS=f"{AGGRESSIVE} {CRITICAL}")
    assert code == 1
    assert requested == [MERGED_URL]
    assert len(notices(caplog)) == 1


def test_unknown_id_is_still_skipped(tmp_path, monkeypatch, caplog):
    run_job(tmp_path, monkeypatch, BLACKLIST_COMMUNITY_LISTS="ip:does-not-exist")
    assert not requested_any(caplog)
    assert any("ip:does-not-exist not found" in r.getMessage() for r in caplog.records)
    assert not notices(caplog)


def requested_any(caplog):
    return [r for r in caplog.records if "Downloading blacklist data" in r.getMessage()]


def test_per_service_values_resolve_and_notice_once(tmp_path, monkeypatch, caplog):
    code, requested, cache = run_job(
        tmp_path,
        monkeypatch,
        MULTISITE="yes",
        SERVER_NAME="a.example b.example c.example",
        **{
            "a.example_BLACKLIST_COMMUNITY_LISTS": CRITICAL,
            "b.example_BLACKLIST_COMMUNITY_LISTS": f"{AGGRESSIVE} {CRITICAL}",
            "c.example_BLACKLIST_COMMUNITY_LISTS": "ip:does-not-exist",
        },
    )
    assert code == 1
    assert set(requested) == {MERGED_URL}
    assert {s for s, n in cache.data if n == "IP.list"} == {"a.example", "b.example"}
    assert len(notices(caplog)) == 1
