"""The shared fixed-window counter extracted from Limit.

Limit's global rate limit and the workflow rate gates now share one implementation, so the
key it derives is the thing that must not drift: a changed key silently resets every live
counter and, worse, would make an upgraded instance stop seeing the counts its peers write.
Runs through the ``lua`` binary — the module is pure Lua with no OpenResty dependency
beyond ``ngx.ERR``, which the harness stubs.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "ratelimit.lua"

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")

HARNESS = """
ngx = { ERR = 1 }
local ratelimit = dofile("%s")

local function new_owner(opts)
    opts = opts or {}
    local store = {}
    local logged = {}
    return {
        store = store,
        logged = logged,
        use_redis = opts.use_redis or false,
        clusterstore = {
            connect = function() return nil, "connection refused" end,
            call = function() return nil, "unreachable" end,
            close = function() end,
        },
        datastore = {
            get = function(_, key)
                if store[key] then return store[key] end
                return nil, "not found"
            end,
            set_with_retries = function(_, key, value, ttl)
                store[key] = value
                store[key .. "#ttl"] = ttl
                return true
            end,
        },
        logger = { log = function(_, _, message) logged[#logged + 1] = message end },
    }
end

local function expected_key(prefix, window)
    return prefix .. "_" .. tostring(math.floor(os.time(os.date("!*t")) / window))
end

-- 1. The key is byte-for-byte the one limit.lua built before the extraction.
local owner = new_owner()
local prefix = "plugin_limit_global_app.example.com"
local count = ratelimit.incr(owner, prefix, 60)
assert(count == 1, "first request should count 1, got " .. tostring(count))
assert(owner.store[expected_key(prefix, 60)] == "1", "unexpected key: " .. tostring(next(owner.store)))

-- 2. The counter accumulates inside the window and expires with it.
assert(ratelimit.incr(owner, prefix, 60) == 2, "second request should count 2")
assert(owner.store[expected_key(prefix, 60) .. "#ttl"] == 60, "the key must expire with its window")

-- 3. Distinct prefixes never share a bucket (a workflow gate vs Limit's global cap).
local other = ratelimit.incr(owner, "plugin_workflow_wf-1/r1_1.2.3.4", 60)
assert(other == 1, "a different prefix must start its own counter")

-- 4. A Redis failure logs once and falls back to the local dict rather than failing open
--    or blocking the request.
local failing = new_owner({ use_redis = true })
assert(ratelimit.incr(failing, prefix, 60) == 1, "the local fallback must still count")
assert(#failing.logged == 1, "expected exactly one fallback log, got " .. tostring(#failing.logged))
assert(failing.logged[1]:find("falling back to local", 1, true), "unexpected log: " .. failing.logged[1])

print("OK")
"""


def test_the_counter_key_and_fallback_are_unchanged():
    result = subprocess.run(["lua", "-e", HARNESS % MODULE.as_posix()], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"
