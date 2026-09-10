"""A ban check that missed locally paid two Redis EVALs, one per scope.

Port of dev c58b69e07. `utils.is_banned` already checked the local datastore for both scopes
before opening a Redis connection, but the Redis fallback then ran the single-key script once
for the service key and again for the global one — two round trips on the request hot path,
on every request from an IP that is not locally cached.

The script now walks `KEYS` itself and reports which one hit, so both scopes cost one EVAL.
Priority has to survive that: the service ban still wins over the global one, because the
script returns the first key that hits and the keys are handed to it in that order.

The Redis-side script is executed here for real (it is plain Lua), against a stubbed
`redis.pcall` — a restated copy would let this file keep passing while the shipped script
drifted.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
UTILS = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "utils.lua"

LUA = shutil.which("lua")
needs_lua = pytest.mark.skipif(LUA is None, reason="no stand-alone lua on PATH")


def _extract(pattern: str, what: str) -> str:
    match = re.search(pattern, UTILS.read_text(encoding="utf-8"), re.M | re.S)
    assert match, f"{what} is gone from utils.lua"
    return match.group(0)


HARNESS = """
local logs = {}
local subsystem = "http"
local null = setmetatable({}, { __tostring = function() return "NULL" end })
local WARN = 4
local math_min, math_max = math.min, math.max
local BAN_LOCAL_CACHE_TTL = 30
local unpack = unpack or table.unpack
local logger = { log = function(_, _, msg) table.insert(logs, msg) end }

local decoded = {}
local function decode(value)
    local d = decoded[value]
    if d == nil then error("not json") end
    return d
end

local function get_stream_snapshot() error("http subsystem only") end

-- What the node-local shared dict holds.
local local_store = {}
local local_ttls = {}
local cache_writes = {}
local datastore = {
    get = function(_, key)
        local v = local_store[key]
        if v == nil then return nil, "not found" end
        return v, nil
    end,
    ttl = function(_, key) return true, local_ttls[key] or 0 end,
    set_with_retries = function(_, key, value, ttl)
        table.insert(cache_writes, key .. "|" .. tostring(ttl))
        return true, nil
    end,
}

-- What Redis holds.
local redis_store = {}
local redis_ttls = {}
local eval_count = 0
local last_keys = {}
local connects = 0

local clusterstore_stub = {
    connect = function() connects = connects + 1 return true, nil end,
    close = function() return true end,
    call = function(_, method, script, nkeys, ...)
        assert(method == "eval", "unexpected redis method " .. tostring(method))
        eval_count = eval_count + 1
        last_keys = { ... }
        assert(nkeys == #last_keys, "declared key count must match the arguments")
        local env = {
            KEYS = last_keys,
            ipairs = ipairs,
            type = type,
            tostring = tostring,
            redis = {
                pcall = function(cmd, key)
                    if cmd == "GET" then
                        local v = redis_store[key]
                        if v == nil then return false end
                        return v
                    elseif cmd == "TTL" then
                        if redis_store[key] == nil then return -2 end
                        return redis_ttls[key] or -1
                    end
                    return { err = "unknown command " .. tostring(cmd) }
                end,
            },
        }
        local fn = assert(load(script, "ban_script", "t", env))
        local res = fn()
        if type(res) ~= "table" then return res end
        if res.err then return res end
        -- Redis turns a Lua `false` into a nil bulk reply, which lua-resty-redis surfaces
        -- as ngx.null. Model that, or the caller's `data[1] ~= null` guard is untested.
        local out = {}
        for i, v in ipairs(res) do out[i] = (v == false) and null or v end
        return out
    end,
}
package.loaded["bunkerweb.clusterstore"] = { new = function() return clusterstore_stub end }

local USE_REDIS = "yes"
local utils = { get_variable = function() return USE_REDIS, nil end }
"""


def _run(body: str) -> subprocess.CompletedProcess:
    source = (
        HARNESS
        + "\n"
        + _extract(r"^local function local_ban_key\(.*?^end$", "local_ban_key")
        + "\n"
        + _extract(r"^utils\.is_banned = function\(.*?^end$", "utils.is_banned")
        + "\n"
        + body
    )
    return subprocess.run([LUA, "-"], input=source, capture_output=True, text=True)


def _lines(result):
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    return result.stdout.strip().splitlines()


# --------------------------------------------------------------------------------------
# The round trips
# --------------------------------------------------------------------------------------
@needs_lua
def test_both_scopes_are_looked_up_in_one_eval():
    result = _run("""
        local banned, reason = utils.is_banned("10.0.0.1", "www.example.com")
        print(eval_count)
        print(#last_keys)
        print(last_keys[1])
        print(last_keys[2])
        print(tostring(banned) .. "|" .. tostring(reason))
    """)
    lines = _lines(result)
    assert lines[0] == "1", "two EVALs is exactly what this port removes"
    assert lines[1] == "2"
    assert lines[2] == "bans_service_www.example.com_ip_10.0.0.1"
    assert lines[3] == "bans_ip_10.0.0.1"
    assert lines[4] == "false|not banned"


@needs_lua
def test_a_request_without_a_server_name_only_asks_for_the_global_key():
    result = _run("""
        utils.is_banned("10.0.0.1")
        print(#last_keys)
        print(last_keys[1])
    """)
    lines = _lines(result)
    assert lines[0] == "1"
    assert lines[1] == "bans_ip_10.0.0.1"


@needs_lua
def test_a_local_hit_on_the_only_key_never_opens_a_redis_connection():
    result = _run("""
        local_store["bans_ip_10.0.0.1"] = "manual"
        local banned, reason = utils.is_banned("10.0.0.1")
        print(connects .. "|" .. eval_count)
        print(tostring(banned) .. "|" .. reason)
    """)
    lines = _lines(result)
    assert lines[0] == "0|0", "a locally cached ban must not cost a Redis connection"
    assert lines[1] == "true|manual"


@needs_lua
def test_a_local_service_hit_short_circuits_the_lower_priority_key_too():
    """The service scope wins outright, so nothing below it is worth a round trip."""
    result = _run("""
        local_store["bans_service_www.example.com_ip_10.0.0.1"] = "service-local"
        local banned, reason = utils.is_banned("10.0.0.1", "www.example.com")
        print(connects .. "|" .. eval_count)
        print(tostring(banned) .. "|" .. reason)
    """)
    lines = _lines(result)
    assert lines[0] == "0|0"
    assert lines[1] == "true|service-local"


@needs_lua
def test_any_local_verdict_keeps_redis_out_of_the_request():
    """Deliberately narrower than dev c58b69e07, which asks Redis for the higher-priority
    scopes even after a lower-priority local hit. 1.7 keeps a cached ban authoritative
    through a Redis outage — see `test_ban_sync.py`'s local-cache-before-outage cases — and
    dev's ordering would turn that request into an error instead of a ban. The cost is a
    service ban that only Redis knows about waiting out `BAN_LOCAL_CACHE_TTL` (30 s) behind
    a cached global one, which bans the request either way.
    """
    result = _run("""
        local_store["bans_ip_10.0.0.1"] = "global-local"
        redis_store["bans_service_www.example.com_ip_10.0.0.1"] = "service-redis"
        redis_ttls["bans_service_www.example.com_ip_10.0.0.1"] = 60
        local banned, reason = utils.is_banned("10.0.0.1", "www.example.com")
        print(connects .. "|" .. eval_count)
        print(tostring(banned) .. "|" .. reason)
    """)
    lines = _lines(result)
    assert lines[0] == "0|0"
    assert lines[1] == "true|global-local"


@needs_lua
def test_a_cached_ban_survives_a_dead_redis():
    """The invariant the narrowing protects, stated on its own."""
    result = _run("""
        clusterstore_stub.connect = function() return false, "connection refused" end
        local_store["bans_ip_10.0.0.1"] = "global-local"
        local banned, reason = utils.is_banned("10.0.0.1", "www.example.com")
        print(tostring(banned) .. "|" .. reason)
    """)
    assert _lines(result)[0] == "true|global-local"


# --------------------------------------------------------------------------------------
# Priority and the reported key
# --------------------------------------------------------------------------------------
@needs_lua
def test_the_service_ban_wins_when_redis_holds_both():
    result = _run("""
        redis_store["bans_service_www.example.com_ip_10.0.0.1"] = "service-reason"
        redis_ttls["bans_service_www.example.com_ip_10.0.0.1"] = 60
        redis_store["bans_ip_10.0.0.1"] = "global-reason"
        redis_ttls["bans_ip_10.0.0.1"] = 120
        local banned, reason, ttl = utils.is_banned("10.0.0.1", "www.example.com")
        print(tostring(banned) .. "|" .. reason .. "|" .. tostring(ttl))
        print(cache_writes[1])
    """)
    lines = _lines(result)
    assert lines[0] == "true|service-reason|60"
    assert lines[1].startswith("bans_service_www.example.com_ip_10.0.0.1|"), lines[1]


@needs_lua
def test_the_global_ban_is_reported_when_only_it_hits():
    result = _run("""
        redis_store["bans_ip_10.0.0.1"] = "global-reason"
        redis_ttls["bans_ip_10.0.0.1"] = 120
        local banned, reason, ttl = utils.is_banned("10.0.0.1", "www.example.com")
        print(tostring(banned) .. "|" .. reason .. "|" .. tostring(ttl))
        print(cache_writes[1])
    """)
    lines = _lines(result)
    assert lines[0] == "true|global-reason|120"
    assert lines[1].startswith("bans_ip_10.0.0.1|30"), "the local copy is capped at BAN_LOCAL_CACHE_TTL"


@needs_lua
def test_a_permanent_redis_ban_normalises_its_negative_ttl():
    """Redis answers -1 for a key with no expiry; the caller contract is 0."""
    result = _run("""
        redis_store["bans_ip_10.0.0.1"] = "forever"
        redis_ttls["bans_ip_10.0.0.1"] = -1
        local banned, _, ttl = utils.is_banned("10.0.0.1")
        print(tostring(banned) .. "|" .. tostring(ttl))
    """)
    assert _lines(result)[0] == "true|0"


@needs_lua
def test_the_cache_write_never_trusts_the_returned_index_blindly():
    """A key index the script did not mean would be written as the cache entry."""
    source = UTILS.read_text(encoding="utf-8")
    assert "local hit_key = keys[data[3]]" in source
    assert "if hit_key then" in source


# --------------------------------------------------------------------------------------
# Failure modes
# --------------------------------------------------------------------------------------
@needs_lua
def test_a_dead_redis_is_reported_rather_than_read_as_not_banned():
    result = _run("""
        clusterstore_stub.connect = function() return false, "connection refused" end
        local banned, reason = utils.is_banned("10.0.0.1")
        print(tostring(banned) .. "|" .. reason)
    """)
    assert _lines(result)[0] == "nil|can't connect to redis: connection refused"


@needs_lua
def test_a_script_error_is_reported_rather_than_read_as_not_banned():
    result = _run("""
        clusterstore_stub.call = function() return { err = "OOM command not allowed" } end
        local banned, reason = utils.is_banned("10.0.0.1")
        print(tostring(banned) .. "|" .. reason)
    """)
    assert _lines(result)[0] == "nil|redis script error: OOM command not allowed"


@needs_lua
def test_redis_is_never_opened_when_use_redis_is_off():
    result = _run("""
        USE_REDIS = "no"
        local banned, reason = utils.is_banned("10.0.0.1", "www.example.com")
        print(connects .. "|" .. eval_count)
        print(tostring(banned) .. "|" .. reason)
    """)
    lines = _lines(result)
    assert lines[0] == "0|0"
    assert lines[1] == "false|not banned"
