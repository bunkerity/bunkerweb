"""``METRICS_REDIS_TTL=0`` is documented as pinning metrics keys permanently in Redis.

Port of dev 9520495e4: ``refresh_request_ttls`` used to treat ``ttl <= 0`` as "do nothing",
so a key that already carried a TTL from a prior non-zero setting kept expiring on schedule
under a ``volatile-lru`` eviction policy — the operator who set ``0`` to pin the reports list
still lost it. The fix is PERSIST, issued once per worker (``persisted_redis``) since every
writer after that uses bare SET/RPUSH/HINCRBY and nothing re-adds a TTL.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
METRICS_LUA = ROOT / "src" / "common" / "core" / "metrics" / "metrics.lua"

LUA = shutil.which("lua") or shutil.which("luajit")
needs_lua = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")


def _source() -> str:
    return METRICS_LUA.read_text(encoding="utf-8")


def _extract(name: str) -> str:
    match = re.search(rf"^local function {name}\(.*?^end$", _source(), re.S | re.M)
    assert match, f"{name} not found in metrics.lua — did it get renamed?"
    return match.group(0)


# `refresh_request_ttls` batches its touches through init_pipeline/commit_pipeline, so the
# individual calls answer nil with no error by construction and the whole pass is judged on
# the commit. The stub therefore has to model the commit reply: a table with one entry per
# queued command, where a per-command Redis error is a `{false, err}` entry and a socket
# failure is a nil reply set (`commit_reply` below drives both).
_STUB = """
    local ERR = 1
    local REQUEST_FACET_FIELDS = { "ip", "country", "method", "url", "status", "reason", "server_name", "security_mode" }
    -- METRICS_SAVE_TO_REDIS is "no" below, so lru:get_keys() is never reached; no real
    -- resty.lrucache needed (not on the standalone-lua LUA_PATH in this environment).
    local lru = { get_keys = function() error("must not be called when METRICS_SAVE_TO_REDIS is 'no'") end }
    local calls = {}
    local logs = {}
    local queued = 0
    -- Overridable by a test: nil means "every queued command succeeded".
    local commit_reply, commit_err = nil, nil
    local store = {
        call = function(_, method, key, ttl)
            if method == "init_pipeline" then
                queued = 0
                return
            end
            if method == "commit_pipeline" then
                if commit_reply ~= nil or commit_err ~= nil then
                    return commit_reply, commit_err
                end
                local replies = {}
                for i = 1, queued do replies[i] = true end
                return replies
            end
            queued = queued + 1
            table.insert(calls, method .. (key and (":" .. key) or "") .. (ttl and (":" .. tostring(ttl)) or ""))
        end,
    }
    local self = {
        clusterstore = store,
        variables = { METRICS_SAVE_TO_REDIS = "no" },
        log_throttled = function(_, _, id, msg) table.insert(logs, id .. "|" .. msg) end,
    }
"""


@needs_lua
def test_ttl_zero_persists_instead_of_no_op():
    """The regression this ports: ttl<=0 must PERSIST the pinning keys, not skip them."""
    source = _STUB + _extract("refresh_request_ttls")
    source += """
        refresh_request_ttls(self, 0, 202)
        for _, c in ipairs(calls) do print(c) end
    """
    result = subprocess.run([LUA, "-"], input=source, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    lines = result.stdout.strip().splitlines()
    assert "persist:requests" in lines
    assert "persist:requests:ids" in lines
    assert "persist:requests:facets:initialized" in lines
    assert not any(c.startswith("expire:") for c in lines), f"ttl<=0 must never EXPIRE, got {lines}"


@needs_lua
def test_ttl_zero_persist_is_one_shot_per_worker():
    """Persisting is a one-shot migration: a later cycle in persist mode must not re-issue it."""
    source = _STUB + _extract("refresh_request_ttls")
    source += """
        refresh_request_ttls(self, 0, 202)
        local after_first = #calls
        refresh_request_ttls(self, 0, 202)
        print(after_first .. "|" .. #calls)
    """
    result = subprocess.run([LUA, "-"], input=source, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    after_first, after_second = result.stdout.strip().split("|")
    assert int(after_first) > 0
    assert after_first == after_second, "a second persist-mode cycle must be a pure no-op"


@needs_lua
def test_positive_ttl_still_expires_as_before():
    """The non-zero path is unchanged: it must EXPIRE with the configured ttl, never PERSIST."""
    source = _STUB + _extract("refresh_request_ttls")
    source += """
        refresh_request_ttls(self, 3600, 202)
        for _, c in ipairs(calls) do print(c) end
    """
    result = subprocess.run([LUA, "-"], input=source, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    lines = result.stdout.strip().splitlines()
    assert "expire:requests:3600" in lines
    assert not any(c.startswith("persist:") for c in lines), f"a positive ttl must never PERSIST, got {lines}"


# --------------------------------------------------------------------------------------
# Port of dev 27a8aa150: silence on the pipeline commit is a deferred loss, and the one-shot
# latch may only close on a pass that actually completed.
# --------------------------------------------------------------------------------------
@needs_lua
def test_a_failed_persist_pass_is_logged_and_retried():
    """A half-done strip leaves keys carrying a TTL, so it has to run again next cycle."""
    source = _STUB + _extract("refresh_request_ttls")
    source += """
        commit_err = "connection refused"
        refresh_request_ttls(self, 0, 202)
        local after_failure = #calls
        commit_reply, commit_err = nil, nil
        refresh_request_ttls(self, 0, 202)
        print(after_failure .. "|" .. #calls)
        print(#logs > 0 and logs[1] or "no-log")
    """
    result = subprocess.run([LUA, "-"], input=source, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    lines = result.stdout.strip().splitlines()
    after_failure, after_retry = (int(part) for part in lines[0].split("|"))
    assert after_failure > 0
    assert after_retry == after_failure * 2, "a failed pass must not latch persisted_redis"
    assert lines[1].startswith("requests_ttl|"), lines[1]
    assert "connection refused" in lines[1]


@needs_lua
def test_a_per_command_redis_error_inside_the_pipeline_also_counts_as_failed():
    """The commit succeeds as a socket operation and still reports `{false, err}` per command."""
    source = _STUB + _extract("refresh_request_ttls")
    source += """
        commit_reply = { true, { false, "OOM command not allowed" }, true }
        refresh_request_ttls(self, 0, 202)
        local after_failure = #calls
        commit_reply = nil
        refresh_request_ttls(self, 0, 202)
        print(after_failure .. "|" .. #calls)
        print(#logs > 0 and logs[1] or "no-log")
    """
    result = subprocess.run([LUA, "-"], input=source, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    lines = result.stdout.strip().splitlines()
    after_failure, after_retry = (int(part) for part in lines[0].split("|"))
    assert after_retry == after_failure * 2, "a per-command error must not latch persisted_redis"
    assert "OOM command not allowed" in lines[1]


@needs_lua
def test_a_failed_expire_pass_is_reported_too():
    """Non-persist mode has no latch to protect, but silence there is still a deferred loss:
    the key keeps the TTL it already carries for another full period."""
    source = _STUB + _extract("refresh_request_ttls")
    source += """
        commit_err = "timeout"
        refresh_request_ttls(self, 60, 202)
        print(#logs > 0 and logs[1] or "no-log")
    """
    result = subprocess.run([LUA, "-"], input=source, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    line = result.stdout.strip().splitlines()[0]
    assert line.startswith("requests_ttl|"), line
    assert "refresh the TTL of" in line and "timeout" in line
