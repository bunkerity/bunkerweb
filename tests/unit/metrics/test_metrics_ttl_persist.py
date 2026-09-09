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


_STUB = """
    local REQUEST_FACET_FIELDS = { "ip", "country", "method", "url", "status", "reason", "server_name", "security_mode" }
    -- METRICS_SAVE_TO_REDIS is "no" below, so lru:get_keys() is never reached; no real
    -- resty.lrucache needed (not on the standalone-lua LUA_PATH in this environment).
    local lru = { get_keys = function() error("must not be called when METRICS_SAVE_TO_REDIS is 'no'") end }
    local calls = {}
    local store = {
        call = function(_, method, key, ttl)
            table.insert(calls, method .. (key and (":" .. key) or "") .. (ttl and (":" .. tostring(ttl)) or ""))
        end,
    }
    local self = { clusterstore = store, variables = { METRICS_SAVE_TO_REDIS = "no" } }
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
