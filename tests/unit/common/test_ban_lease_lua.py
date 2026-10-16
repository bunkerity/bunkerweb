"""Lease primitives in the instance Lua (CrowdSec port, lane C).

A CrowdSec lease is an ordinary ban (`reason == "crowdsec"`, `reason_data.lease == true`, a fresh
`reason_data.lease_id`). Three things in `utils.lua` and `api.lua` have to know that, and each is a
way to silently remove or hide a manual ban:

* `utils.remove_lease` touches ONE key and only while the stored lease still carries the caller's
  `lease_id`. The generic `remove_ban` of a global ban also deletes every `bans_service_*_ip_<ip>`
  key, which is how a global lease removal used to take a manual service ban with it.
* `utils.add_ban(..., {keep_existing = true})` is SET NX, in the shared dict and in Redis, so a
  promoted lease can never overwrite an explicit ban.
* `utils.is_banned` ranks explicit bans before leases, so a service lease no longer hides an
  explicit global ban (the reason shown and the TLS drop decision both follow it).

The harness runs the shipped `utils.lua` under stand-alone Lua. Redis is a small in-memory model that
executes the EVAL scripts the Lua actually sends, so the compare-and-delete is proven by running it,
not by matching its text.

`LEASE_PREAMBLE` / `run_lease` are reused by `test_tlsdrop_lua.py`.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
LUA_DIR = ROOT / "src" / "bw" / "lua"
UTILS_LUA = LUA_DIR / "bunkerweb" / "utils.lua"
API_LUA = LUA_DIR / "bunkerweb" / "api.lua"
CACHESTORE_LUA = LUA_DIR / "bunkerweb" / "cachestore.lua"

LUA = shutil.which("lua") or shutil.which("luajit")
needs_lua = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")

LEASE_PREAMBLE = r"""
local subsystem = arg[2] or "http"
local encoded, next_json = {}, 0
local json = {
    encode = function(value)
        next_json = next_json + 1
        local key = "json:" .. next_json
        encoded[key] = value
        return key
    end,
    decode = function(value)
        if encoded[value] == nil then error("invalid json") end
        return encoded[value]
    end,
}
package.preload["cjson"] = function() return json end

local now = 100
local lock_held = false
local lock_calls = 0
local main_store, main_ttls = {}, {}
local epoch_store, sync_store = {}, {}
local internal_store = { variables = { global = { USE_REDIS = "no" } } }

ngx = {
    var = {},
    ERR = 3, INFO = 6, WARN = 4, NOTICE = 5,
    HTTP_FORBIDDEN = 403,
    HTTP_CLOSE = 444,
    null = {},
    re = { match = function() return nil end },
    config = { subsystem = subsystem },
    get_phase = function() return "timer" end,
    thread = { kill = function() return true end },
    shared = {
        datastore = {}, datastore_stream = {}, internalstore = {}, internalstore_stream = {},
        ban_sync = {}, ban_sync_stream = {},
    },
    now = function() return now end,
    time = function() return now end,
}

local function choose_store(dict)
    if dict == ngx.shared.ban_sync_stream then return sync_store, {} end
    if dict == ngx.shared.ban_sync then return epoch_store, {} end
    if dict == ngx.shared.internalstore or dict == ngx.shared.internalstore_stream then
        return internal_store, {}
    end
    return main_store, main_ttls
end

-- Shared dict model. `add` is the real SET NX: it refuses an existing key with "exists".
local add_calls = {}
local datastore_get_error = nil
package.preload["bunkerweb.datastore"] = function()
    return {
        new = function(_, dict)
            local values, ttls = choose_store(dict)
            return {
                dict = {
                    safe_add = function(_, key, value)
                        if values[key] ~= nil then return false, "exists" end
                        values[key] = value
                        return true
                    end,
                    add = function(_, key, value, ttl)
                        add_calls[#add_calls + 1] = { key = key, ttl = ttl }
                        if values[key] ~= nil then return false, "exists" end
                        values[key], ttls[key] = value, ttl
                        return true
                    end,
                    incr = function(_, key, amount)
                        if values[key] == nil then return nil, "not found" end
                        values[key] = values[key] + amount
                        return values[key]
                    end,
                },
                get = function(_, key)
                    if datastore_get_error and values == main_store then return nil, datastore_get_error end
                    if values[key] == nil then return nil, "not found" end
                    return values[key]
                end,
                set = function(_, key, value, ttl)
                    values[key], ttls[key] = value, ttl
                    return true, "success"
                end,
                set_with_retries = function(_, key, value, ttl)
                    values[key], ttls[key] = value, ttl
                    return true, "success"
                end,
                delete = function(_, key)
                    values[key], ttls[key] = nil, nil
                    return true, "success"
                end,
                keys = function()
                    local keys = {}
                    for key in pairs(values) do keys[#keys + 1] = key end
                    return keys
                end,
                ttl = function(_, key) return true, ttls[key] or 0 end,
            }
        end,
    }
end

local logs = {}
package.preload["bunkerweb.logger"] = function()
    return { new = function() return { log = function(_, level, message) logs[#logs + 1] = { level, message } end } end }
end
package.preload["bunkerweb.mmdb"] = function() return {} end
package.preload["resty.ipmatcher"] = function()
    return {
        -- Exact-string matcher: enough to tell a listed address from an unlisted one.
        new = function(networks)
            local set = {}
            for _, network in ipairs(networks) do set[network] = true end
            return { match = function(_, ip) return set[ip] == true end }
        end,
        parse_ipv4 = function(ip) return type(ip) == "string" and ip:find(".", 1, true) end,
        parse_ipv6 = function(ip) return type(ip) == "string" and ip:find(":", 1, true) end,
    }
end
package.preload["resty.random"] = function() return { bytes = function(size) return string.rep("x", size) end } end
package.preload["resty.dns.resolver"] = function() return { new = function() return {} end } end
package.preload["resty.session"] = function() return { start = function() return {} end } end
package.preload["resty.lock"] = function()
    return {
        new = function()
            return {
                lock = function()
                    assert(not lock_held, "snapshot lock taken twice")
                    lock_held = true
                    lock_calls = lock_calls + 1
                    return 0
                end,
                unlock = function() assert(lock_held) lock_held = false return true end,
            }
        end,
    }
end
package.preload["bunkerweb.internal_api"] = function() return { request = function() return { status = 200 } end } end

-- A faithful enough Redis: it EXECUTES the scripts the Lua sends. Lua false is a nil reply, exactly
-- as in Redis, so a missing key reads as `false` inside a script and as ngx.null outside.
local redis_kv, redis_ttl = {}, {}
local redis_calls = {}
local redis_connect_ok, redis_fail_command = true, nil
local function to_reply(value)
    if value == false then return ngx.null end
    if type(value) == "table" then
        local out = {}
        for i = 1, #value do out[i] = to_reply(value[i]) end
        for k, v in pairs(value) do if type(k) ~= "number" then out[k] = to_reply(v) end end
        return out
    end
    return value
end
local function redis_command(name, ...)
    name = name:lower()
    local a = { ... }
    if name == "get" then
        if redis_kv[a[1]] == nil then return false end
        return redis_kv[a[1]]
    elseif name == "ttl" then
        if redis_kv[a[1]] == nil then return -2 end
        return redis_ttl[a[1]] or -1
    elseif name == "del" then
        local n = 0
        for _, key in ipairs(a) do
            if redis_kv[key] ~= nil then n = n + 1 end
            redis_kv[key], redis_ttl[key] = nil, nil
        end
        return n
    elseif name == "set" then
        local nx, ex = false, nil
        local i = 3
        while a[i] do
            local opt = tostring(a[i]):upper()
            if opt == "NX" then nx = true elseif opt == "EX" then i = i + 1 ex = a[i] end
            i = i + 1
        end
        if nx and redis_kv[a[1]] ~= nil then return false end
        redis_kv[a[1]], redis_ttl[a[1]] = a[2], ex
        return "OK"
    end
    error("unmodelled redis command " .. name)
end
local function redis_eval(script, keys, argv)
    local env = {
        KEYS = keys, ARGV = argv, ipairs = ipairs, pairs = pairs, type = type, tostring = tostring,
        tonumber = tonumber, pcall = pcall, string = string, math = math, table = table,
        cjson = json,
        redis = {
            call = function(...) return redis_command(...) end,
            pcall = function(...) return redis_command(...) end,
            log = function() end, LOG_WARNING = 1,
        },
    }
    local chunk, err = load(script, "redis-script", "t", env)
    assert(chunk, err)
    return to_reply(chunk())
end
package.preload["bunkerweb.clusterstore"] = function()
    return {
        new = function()
            return {
                connect = function()
                    if redis_connect_ok then return true end
                    return false, "redis unavailable"
                end,
                call = function(_, ...)
                    local arguments = { ... }
                    redis_calls[#redis_calls + 1] = arguments
                    if redis_fail_command == arguments[1] then return nil, "boom" end
                    if arguments[1] == "eval" then
                        local keys, argv = {}, {}
                        local nkeys = arguments[3]
                        for i = 1, nkeys do keys[i] = arguments[3 + i] end
                        for i = nkeys + 4, #arguments do argv[#argv + 1] = arguments[i] end
                        return redis_eval(arguments[2], keys, argv)
                    end
                    local reply = redis_command(table.unpack(arguments))
                    return to_reply(reply)
                end,
                close = function() return true end,
            }
        end,
    }
end

-- Convenience: a stored ban/lease value, built through the same encode the code uses
local function ban_value(reason, reason_data, extra)
    local value = { reason = reason, service = "svc", date = now, country = "local", ban_scope = "global",
        reason_data = reason_data or {}, permanent = false, expires_at = now + 60 }
    for k, v in pairs(extra or {}) do value[k] = v end
    return json.encode(value)
end
local function lease_data(lease_id, extra)
    local data = { lease = true, version = 1, lease_id = lease_id, source = "lapi", remediation = "ban" }
    for k, v in pairs(extra or {}) do data[k] = v end
    return data
end

local utils = dofile(arg[1])
"""


def run_lease(body: str, subsystem: str = "http", preamble: str = LEASE_PREAMBLE, extra_path: str = "") -> str:
    assert LUA is not None
    result = subprocess.run(
        [LUA, "-", str(UTILS_LUA), subsystem],
        input=f'package.path = "{LUA_DIR}/?.lua;{extra_path}" .. package.path\n' + preamble + body,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    return result.stdout


IP = "192.0.2.1"


# ------------------------------------------------------------------ remove_lease (amendment 1 R1)


@needs_lua
def test_remove_lease_removes_a_global_lease_and_leaves_a_manual_service_ban():
    run_lease(r"""
main_store["bans_ip_192.0.2.1"] = ban_value("crowdsec", lease_data("aaaa1111aaaa1111"))
main_store["bans_service_www_ip_192.0.2.1"] = ban_value("manual", {}, { ban_scope = "service" })

local result = assert(utils.remove_lease("192.0.2.1", "global", nil, "aaaa1111aaaa1111"))

assert(result == "removed", "got " .. tostring(result))
assert(main_store["bans_ip_192.0.2.1"] == nil, "the lease survived")
assert(main_store["bans_service_www_ip_192.0.2.1"] ~= nil, "the manual service ban was taken along")
""")


@needs_lua
def test_remove_lease_touches_only_the_key_of_its_own_scope():
    run_lease(r"""
main_store["bans_ip_192.0.2.1"] = ban_value("crowdsec", lease_data("aaaa1111aaaa1111"))
main_store["bans_service_www_ip_192.0.2.1"] = ban_value("crowdsec", lease_data("aaaa1111aaaa1111"), { ban_scope = "service" })

assert(utils.remove_lease("192.0.2.1", "service", "www", "aaaa1111aaaa1111") == "removed")

assert(main_store["bans_service_www_ip_192.0.2.1"] == nil)
assert(main_store["bans_ip_192.0.2.1"] ~= nil, "a service removal reached the global key")
""")


@needs_lua
def test_remove_lease_refuses_an_explicit_ban_on_the_same_key():
    run_lease(r"""
main_store["bans_ip_192.0.2.1"] = ban_value("manual", { lease_id = "aaaa1111aaaa1111" })
assert(utils.remove_lease("192.0.2.1", "global", nil, "aaaa1111aaaa1111") == "changed")
assert(main_store["bans_ip_192.0.2.1"] ~= nil, "an explicit ban was removed through the lease path")

-- reason crowdsec without reason_data.lease_id (an operator ban with that reason) is not a lease either
main_store["bans_ip_192.0.2.2"] = ban_value("crowdsec", {})
assert(utils.remove_lease("192.0.2.2", "global", nil, "aaaa1111aaaa1111") == "changed")
assert(main_store["bans_ip_192.0.2.2"] ~= nil)
""")


@needs_lua
def test_remove_lease_refuses_a_newer_lease():
    run_lease(r"""
main_store["bans_ip_192.0.2.1"] = ban_value("crowdsec", lease_data("bbbb2222bbbb2222"))
assert(utils.remove_lease("192.0.2.1", "global", nil, "aaaa1111aaaa1111") == "changed")
assert(main_store["bans_ip_192.0.2.1"] ~= nil, "a renewed lease was removed by the old lease_id")
""")


@needs_lua
def test_remove_lease_reports_absent_when_nothing_is_stored():
    run_lease(r"""assert(utils.remove_lease("192.0.2.1", "global", nil, "aaaa1111aaaa1111") == "absent")""")


@needs_lua
def test_remove_lease_runs_under_the_snapshot_lock_and_moves_the_epoch_only_when_it_deletes():
    run_lease(r"""
epoch_store.ban_snapshot_epoch = 0
main_store["bans_ip_192.0.2.1"] = ban_value("crowdsec", lease_data("aaaa1111aaaa1111"))

assert(utils.remove_lease("192.0.2.1", "global", nil, "bbbb2222bbbb2222") == "changed")
assert(lock_calls >= 1, "the shm check did not run under the snapshot lock")
local epoch_after_miss = epoch_store.ban_snapshot_epoch

assert(utils.remove_lease("192.0.2.1", "global", nil, "aaaa1111aaaa1111") == "removed")
assert(epoch_store.ban_snapshot_epoch > epoch_after_miss, "a deletion must advance the ban epoch like remove_ban does")
""")


@needs_lua
def test_remove_lease_rejects_bad_arguments_without_touching_anything():
    run_lease(r"""
main_store["bans_ip_192.0.2.1"] = ban_value("crowdsec", lease_data("aaaa1111aaaa1111"))
for _, bad in ipairs({ "", 12, {}, string.rep("a", 65), "a b" }) do
    local result, err = utils.remove_lease("192.0.2.1", "global", nil, bad)
    assert(result == nil and err, "accepted lease_id " .. tostring(bad))
end
assert(utils.remove_lease("not-an-ip", "global", nil, "aaaa1111aaaa1111") == nil)
assert(utils.remove_lease("192.0.2.1", "service", nil, "aaaa1111aaaa1111") == nil, "a service removal needs a service")
assert(main_store["bans_ip_192.0.2.1"] ~= nil)
""")


@needs_lua
def test_remove_lease_honours_the_internal_deadline():
    run_lease(r"""
main_store["bans_ip_192.0.2.1"] = ban_value("crowdsec", lease_data("aaaa1111aaaa1111"))
local result, err = utils.remove_lease("192.0.2.1", "global", nil, "aaaa1111aaaa1111", now - 1)
assert(result == nil and err:find("deadline"), tostring(err))
assert(main_store["bans_ip_192.0.2.1"] ~= nil)
""")


@needs_lua
def test_remove_lease_is_http_only():
    run_lease(
        r"""
local result, err = utils.remove_lease("192.0.2.1", "global", nil, "aaaa1111aaaa1111")
assert(result == nil and err:find("HTTP"), tostring(err))
""",
        subsystem="stream",
    )


# ---- Redis: one EVAL on one key, compare and delete


@needs_lua
def test_remove_lease_redis_is_one_compare_and_delete_eval_on_one_key():
    run_lease(r"""
internal_store.variables.global.USE_REDIS = "yes"
redis_kv["bans_ip_192.0.2.1"] = ban_value("crowdsec", lease_data("aaaa1111aaaa1111"))
redis_kv["bans_service_www_ip_192.0.2.1"] = ban_value("manual", {}, { ban_scope = "service" })

assert(utils.remove_lease("192.0.2.1", "global", nil, "aaaa1111aaaa1111") == "removed")

assert(redis_kv["bans_ip_192.0.2.1"] == nil, "the Redis lease survived")
assert(redis_kv["bans_service_www_ip_192.0.2.1"] ~= nil, "the manual service ban was removed from Redis")
local evals, others = 0, {}
for _, call in ipairs(redis_calls) do
    if call[1] == "eval" then
        evals = evals + 1
        assert(call[3] == 1, "the script must declare exactly one key")
        assert(call[4] == "bans_ip_192.0.2.1")
    else
        others[#others + 1] = call[1]
    end
end
assert(evals == 1, "expected one EVAL, got " .. evals)
assert(#others == 0, "plain commands were used next to the EVAL: " .. table.concat(others, ","))
""")


@needs_lua
def test_remove_lease_redis_keeps_an_explicit_ban_and_a_newer_lease():
    run_lease(r"""
internal_store.variables.global.USE_REDIS = "yes"
redis_kv["bans_ip_192.0.2.1"] = ban_value("manual", { lease_id = "aaaa1111aaaa1111" })
assert(utils.remove_lease("192.0.2.1", "global", nil, "aaaa1111aaaa1111") == "changed")
assert(redis_kv["bans_ip_192.0.2.1"] ~= nil, "an explicit ban was deleted from Redis")

redis_kv["bans_ip_192.0.2.1"] = ban_value("crowdsec", lease_data("bbbb2222bbbb2222"))
assert(utils.remove_lease("192.0.2.1", "global", nil, "aaaa1111aaaa1111") == "changed")
assert(redis_kv["bans_ip_192.0.2.1"] ~= nil, "a newer lease was deleted from Redis")
""")


@needs_lua
def test_remove_lease_redis_deletes_before_the_local_copy_so_a_request_cannot_recache_it():
    run_lease(r"""
internal_store.variables.global.USE_REDIS = "yes"
local value = ban_value("crowdsec", lease_data("aaaa1111aaaa1111"))
redis_kv["bans_ip_192.0.2.1"] = value
main_store["bans_ip_192.0.2.1"] = value

assert(utils.remove_lease("192.0.2.1", "global", nil, "aaaa1111aaaa1111") == "removed")
assert(redis_kv["bans_ip_192.0.2.1"] == nil and main_store["bans_ip_192.0.2.1"] == nil)
""")


@needs_lua
def test_remove_lease_combines_the_two_stores_changed_wins_then_removed_then_absent():
    run_lease(r"""
internal_store.variables.global.USE_REDIS = "yes"
-- Redis already cleaned by another instance, this instance still holds the copy: removed
main_store["bans_ip_192.0.2.1"] = ban_value("crowdsec", lease_data("aaaa1111aaaa1111"))
assert(utils.remove_lease("192.0.2.1", "global", nil, "aaaa1111aaaa1111") == "removed")

-- Redis removed, but the local copy is a different lease: something is left, so changed
redis_kv["bans_ip_192.0.2.1"] = ban_value("crowdsec", lease_data("aaaa1111aaaa1111"))
main_store["bans_ip_192.0.2.1"] = ban_value("crowdsec", lease_data("bbbb2222bbbb2222"))
assert(utils.remove_lease("192.0.2.1", "global", nil, "aaaa1111aaaa1111") == "changed")
assert(redis_kv["bans_ip_192.0.2.1"] == nil, "the matching Redis lease should still be deleted")
assert(main_store["bans_ip_192.0.2.1"] ~= nil)

assert(utils.remove_lease("192.0.2.9", "global", nil, "aaaa1111aaaa1111") == "absent")
""")


@needs_lua
def test_remove_lease_redis_failure_is_reported_and_the_local_copy_is_still_cleared():
    run_lease(r"""
internal_store.variables.global.USE_REDIS = "yes"
main_store["bans_ip_192.0.2.1"] = ban_value("crowdsec", lease_data("aaaa1111aaaa1111"))
redis_fail_command = "eval"
local result, err = utils.remove_lease("192.0.2.1", "global", nil, "aaaa1111aaaa1111")
assert(result == nil and err:find("redis"), tostring(err))
assert(main_store["bans_ip_192.0.2.1"] == nil, "a Redis outage must not keep the local copy alive")
""")


@needs_lua
def test_the_redis_script_is_exported_for_its_python_twin():
    # Lane A writes the Python twin (sync-bans replay) and pins its text equal to this one.
    run_lease(r"""
local script = utils.REMOVE_LEASE_SCRIPT
assert(type(script) == "string" and script:find("ARGV%[1%]") and script:find('"DEL"'))
-- Run it directly: the contract is the reply words
redis_kv["k"] = ban_value("crowdsec", lease_data("aaaa1111aaaa1111"))
assert(redis_eval(script, { "k" }, { "bbbb2222bbbb2222" }) == "changed")
assert(redis_eval(script, { "k" }, { "aaaa1111aaaa1111" }) == "removed")
assert(redis_eval(script, { "k" }, { "aaaa1111aaaa1111" }) == "absent")
redis_kv["k"] = "not json at all"
encoded["not json at all"] = nil
assert(redis_eval(script, { "k" }, { "aaaa1111aaaa1111" }) == "changed", "an undecodable value must not be deleted")
assert(redis_kv["k"] ~= nil)
""")


# ------------------------------------------------------------------ add_ban keep_existing


@needs_lua
def test_keep_existing_refuses_to_overwrite_an_explicit_ban_in_shm():
    run_lease(r"""
assert(utils.add_ban("192.0.2.1", "manual", 600, nil, "FR", "global", {}))
local original = main_store["bans_ip_192.0.2.1"]

local ok, msg = utils.add_ban("192.0.2.1", "crowdsec", 30, nil, "FR", "global", lease_data("aaaa1111aaaa1111"), nil, { keep_existing = true })

assert(ok == true and msg == "exists", tostring(ok) .. " " .. tostring(msg))
assert(main_store["bans_ip_192.0.2.1"] == original, "the explicit ban was overwritten")
""")


@needs_lua
def test_keep_existing_writes_when_the_key_is_free_and_without_the_option_overwrites_as_before():
    run_lease(r"""
local ok, msg = utils.add_ban("192.0.2.1", "crowdsec", 30, nil, "FR", "global", lease_data("aaaa1111aaaa1111"), nil, { keep_existing = true })
assert(ok == true and msg == "success", tostring(msg))
assert(main_store["bans_ip_192.0.2.1"] ~= nil and main_ttls["bans_ip_192.0.2.1"] == 30)

-- no option: the historical overwrite, untouched
assert(utils.add_ban("192.0.2.1", "manual", 600, nil, "FR", "global", {}))
assert(encoded[main_store["bans_ip_192.0.2.1"]].reason == "manual")
""")


@needs_lua
def test_keep_existing_is_also_accepted_in_the_not_after_slot():
    # Lane D's brief spells the call add_ban(..., {keep_existing = true}): a table in the 8th slot
    # is the options table, not a deadline.
    run_lease(r"""
assert(utils.add_ban("192.0.2.1", "manual", 600, nil, "FR", "global", {}))
local ok, msg = utils.add_ban("192.0.2.1", "crowdsec", 30, nil, "FR", "global", lease_data("aaaa1111aaaa1111"), { keep_existing = true })
assert(ok == true and msg == "exists", tostring(msg))
assert(encoded[main_store["bans_ip_192.0.2.1"]].reason == "manual")
""")


@needs_lua
def test_keep_existing_uses_a_single_shm_add_not_a_read_then_write():
    run_lease(r"""
utils.add_ban("192.0.2.1", "crowdsec", 30, "www", "FR", "service", lease_data("aaaa1111aaaa1111"), nil, { keep_existing = true })
assert(#add_calls == 1 and add_calls[1].key == "bans_service_www_ip_192.0.2.1" and add_calls[1].ttl == 30, "NX must be the shared dict's own add")
""")


@needs_lua
def test_keep_existing_permanent_ban_has_no_ttl():
    run_lease(r"""
local ok = utils.add_ban("192.0.2.1", "crowdsec", 0, nil, "FR", "global", lease_data("aaaa1111aaaa1111"), nil, { keep_existing = true })
assert(ok == true)
assert((main_ttls["bans_ip_192.0.2.1"] or 0) == 0, "a permanent ban must not carry a TTL (0 means no expiry in a shared dict)")
""")


@needs_lua
def test_keep_existing_redis_is_set_nx_with_the_ttl():
    run_lease(r"""
internal_store.variables.global.USE_REDIS = "yes"
assert(utils.add_ban("192.0.2.1", "crowdsec", 30, nil, "FR", "global", lease_data("aaaa1111aaaa1111"), nil, { keep_existing = true }))
local call = redis_calls[1]
assert(call[1] == "set" and call[2] == "bans_ip_192.0.2.1")
local args = table.concat({ table.unpack(call, 4) }, " ")
assert(args:find("NX") and args:find("EX 30"), args)
assert(redis_kv["bans_ip_192.0.2.1"] ~= nil)
""")


@needs_lua
def test_keep_existing_redis_leaves_an_explicit_ban_and_drops_the_local_copy_it_just_wrote():
    run_lease(r"""
internal_store.variables.global.USE_REDIS = "yes"
-- Only Redis holds the explicit ban (another instance created it)
redis_kv["bans_ip_192.0.2.1"] = ban_value("manual", {})
local explicit = redis_kv["bans_ip_192.0.2.1"]

local ok, msg = utils.add_ban("192.0.2.1", "crowdsec", 30, nil, "FR", "global", lease_data("aaaa1111aaaa1111"), nil, { keep_existing = true })

assert(ok == true and msg == "exists", tostring(msg))
assert(redis_kv["bans_ip_192.0.2.1"] == explicit, "Redis SET NX overwrote the explicit ban")
assert(main_store["bans_ip_192.0.2.1"] == nil, "a lease copy stayed in shm next to an explicit ban in Redis")
""")


@needs_lua
def test_keep_existing_redis_permanent_ban_has_no_ex():
    run_lease(r"""
internal_store.variables.global.USE_REDIS = "yes"
assert(utils.add_ban("192.0.2.1", "crowdsec", 0, nil, "FR", "global", lease_data("aaaa1111aaaa1111"), nil, { keep_existing = true }))
local args = table.concat({ table.unpack(redis_calls[1], 4) }, " ")
assert(args:find("NX") and not args:find("EX"), args)
""")


# ------------------------------------------------------------------ is_banned precedence (amendment 1 M1)


@needs_lua
def test_a_service_lease_does_not_hide_an_explicit_global_ban():
    run_lease(r"""
main_store["bans_service_www_ip_192.0.2.1"] = ban_value("crowdsec", lease_data("aaaa1111aaaa1111"), { ban_scope = "service" })
main_store["bans_ip_192.0.2.1"] = ban_value("manual", {})

local banned, reason = utils.is_banned("192.0.2.1", "www")
assert(banned == true and reason == "manual", "reason shown: " .. tostring(reason))
""")


@needs_lua
def test_a_lease_alone_reports_the_lease():
    run_lease(r"""
main_store["bans_service_www_ip_192.0.2.1"] = ban_value("crowdsec", lease_data("aaaa1111aaaa1111"), { ban_scope = "service" })
local banned, reason, _, reason_data = utils.is_banned("192.0.2.1", "www")
assert(banned == true and reason == "crowdsec" and reason_data.lease_id == "aaaa1111aaaa1111")

-- service lease over a global lease: the more specific one
main_store["bans_ip_192.0.2.1"] = ban_value("crowdsec", lease_data("bbbb2222bbbb2222"))
local _, _, _, rd = utils.is_banned("192.0.2.1", "www")
assert(rd.lease_id == "aaaa1111aaaa1111", "service lease must outrank global lease")
""")


@needs_lua
def test_an_explicit_service_ban_still_wins_over_everything():
    run_lease(r"""
main_store["bans_service_www_ip_192.0.2.1"] = ban_value("bad behavior", {}, { ban_scope = "service" })
main_store["bans_ip_192.0.2.1"] = ban_value("manual", {})
local _, reason = utils.is_banned("192.0.2.1", "www")
assert(reason == "bad behavior", reason)
""")


@needs_lua
def test_a_service_lease_over_an_explicit_global_ban_costs_no_extra_read_for_a_plain_service_ban():
    # The extra shm get is paid only when the service key holds a lease.
    run_lease(r"""
main_store["bans_service_www_ip_192.0.2.1"] = ban_value("bad behavior", {}, { ban_scope = "service" })
local reads = 0
local real_get = main_store
setmetatable(main_store, { __index = function(_, key) reads = reads + 1 return nil end })
utils.is_banned("192.0.2.1", "www")
assert(reads == 0, "a plain service ban triggered extra lookups: " .. reads)
""")


@needs_lua
def test_redis_is_still_asked_only_when_every_scope_missed_locally():
    run_lease(r"""
internal_store.variables.global.USE_REDIS = "yes"
main_store["bans_service_www_ip_192.0.2.1"] = ban_value("crowdsec", lease_data("aaaa1111aaaa1111"), { ban_scope = "service" })
redis_kv["bans_ip_192.0.2.1"] = ban_value("manual", {})
local banned, reason = utils.is_banned("192.0.2.1", "www")
assert(banned and reason == "crowdsec", "1.7 keeps a cached local hit authoritative: " .. tostring(reason))
assert(#redis_calls == 0, "Redis was consulted although the local scope answered")
""")


@needs_lua
def test_redis_path_a_service_lease_does_not_hide_an_explicit_global_ban():
    # Cold local caches: only the one Redis EVAL answers, and it must rank like the local pass.
    run_lease(r"""
internal_store.variables.global.USE_REDIS = "yes"
redis_kv["bans_service_www_ip_192.0.2.1"] = ban_value("crowdsec", lease_data("abc"), { ban_scope = "service" })
redis_ttl["bans_service_www_ip_192.0.2.1"] = 45
redis_kv["bans_ip_192.0.2.1"] = ban_value("manual", {})
redis_ttl["bans_ip_192.0.2.1"] = 600

local banned, reason, ttl = utils.is_banned("192.0.2.1", "www")
assert(banned == true and reason == "manual", "reason shown: " .. tostring(reason))
assert(ttl == 600, "ttl of the selected ban: " .. tostring(ttl))
local evals = 0
for _, call in ipairs(redis_calls) do if call[1] == "eval" then evals = evals + 1 end end
assert(evals == 1, "still one round trip: " .. evals)

-- the selected entry, not the masked lease, is what the local cache keeps (30 s cap)
assert(main_store["bans_ip_192.0.2.1"] ~= nil and main_ttls["bans_ip_192.0.2.1"] == 30)
assert(main_store["bans_service_www_ip_192.0.2.1"] == nil)
local calls_before = #redis_calls
local _, again = utils.is_banned("192.0.2.1", "www")
assert(again == "manual" and #redis_calls == calls_before, "second look: " .. tostring(again))
""")


@needs_lua
def test_redis_path_an_explicit_service_ban_wins_over_a_global_lease():
    run_lease(r"""
internal_store.variables.global.USE_REDIS = "yes"
redis_kv["bans_service_www_ip_192.0.2.1"] = ban_value("manual", {}, { ban_scope = "service" })
redis_kv["bans_ip_192.0.2.1"] = ban_value("crowdsec", lease_data("abc"))
local banned, reason = utils.is_banned("192.0.2.1", "www")
assert(banned == true and reason == "manual", "reason shown: " .. tostring(reason))
assert(main_store["bans_service_www_ip_192.0.2.1"] ~= nil and main_store["bans_ip_192.0.2.1"] == nil)
""")


@needs_lua
def test_redis_path_leases_alone_keep_the_service_before_the_global_order():
    run_lease(r"""
internal_store.variables.global.USE_REDIS = "yes"
redis_kv["bans_ip_192.0.2.1"] = ban_value("crowdsec", lease_data("gggg7777gggg7777"))
local banned, reason, _, reason_data = utils.is_banned("192.0.2.1", "www")
assert(banned == true and reason == "crowdsec" and reason_data.lease_id == "gggg7777gggg7777")

-- service lease over a global lease: the more specific one
redis_kv["bans_service_www_ip_192.0.2.2"] = ban_value("crowdsec", lease_data("ssss8888ssss8888"), { ban_scope = "service" })
redis_kv["bans_ip_192.0.2.2"] = ban_value("crowdsec", lease_data("gggg7777gggg7777"))
banned, reason, _, reason_data = utils.is_banned("192.0.2.2", "www")
assert(banned and reason_data.lease_id == "ssss8888ssss8888", tostring(reason_data and reason_data.lease_id))

-- nothing stored: not banned, nothing cached
banned, reason = utils.is_banned("192.0.2.3", "www")
assert(banned == false and reason == "not banned")
""")


@needs_lua
def test_the_stream_snapshot_applies_the_same_precedence():
    run_lease(
        r"""
sync_store.ban_snapshot = json.encode({
    generation_epoch = 1,
    bans = {
        ["bans_service_www_ip_192.0.2.1"] = { reason = "crowdsec", expires_at = now + 60, reason_data = lease_data("aaaa1111aaaa1111") },
        ["bans_ip_192.0.2.1"] = { reason = "manual", expires_at = now + 60, reason_data = {} },
    },
})
local banned, reason = utils.is_banned("192.0.2.1", "www")
assert(banned == true and reason == "manual", tostring(reason))
""",
        subsystem="stream",
    )


# ------------------------------------------------------------------ is_banned_local (handshake selector)


@needs_lua
def test_is_banned_local_ranks_explicit_service_global_lease_service_lease_global():
    run_lease(r"""
local function rank_of(ip, service)
    local banned, reason, rank = utils.is_banned_local(ip, service)
    return banned, reason, rank
end

assert(select(1, rank_of("192.0.2.9", "www")) == false)

main_store["bans_ip_192.0.2.1"] = ban_value("crowdsec", lease_data("aaaa1111aaaa1111"))
local banned, reason, rank = rank_of("192.0.2.1", "www")
assert(banned == true and reason == "crowdsec" and rank == 4, tostring(rank))

main_store["bans_service_www_ip_192.0.2.1"] = ban_value("crowdsec", lease_data("bbbb2222bbbb2222"), { ban_scope = "service" })
banned, reason, rank = rank_of("192.0.2.1", "www")
assert(banned and rank == 3, "service lease " .. tostring(rank))

main_store["bans_ip_192.0.2.1"] = ban_value("manual", {})
banned, reason, rank = rank_of("192.0.2.1", "www")
assert(banned and reason == "manual" and rank == 2, "explicit global must beat a service lease: " .. tostring(reason) .. tostring(rank))

main_store["bans_service_www_ip_192.0.2.1"] = ban_value("bad behavior", {}, { ban_scope = "service" })
banned, reason, rank = rank_of("192.0.2.1", "www")
assert(banned and reason == "bad behavior" and rank == 1)
""")


@needs_lua
def test_is_banned_local_without_a_service_reads_only_the_global_key():
    run_lease(r"""
main_store["bans_service_www_ip_192.0.2.1"] = ban_value("manual", {}, { ban_scope = "service" })
local banned = utils.is_banned_local("192.0.2.1", nil)
assert(banned == false, "the default server must not read a service key")
main_store["bans_ip_192.0.2.1"] = ban_value("ui", {})
local banned2, reason, rank = utils.is_banned_local("192.0.2.1", nil)
assert(banned2 and reason == "ui" and rank == 2)
""")


@needs_lua
def test_is_banned_local_never_touches_redis_the_lock_or_ngx_var():
    run_lease(r"""
internal_store.variables.global.USE_REDIS = "yes"
ngx.var = setmetatable({}, { __index = function() error("ngx.var read in the handshake") end })
main_store["bans_ip_192.0.2.1"] = ban_value("manual", {})
assert(utils.is_banned_local("192.0.2.1", "www"))
assert(utils.is_banned_local("192.0.2.2", "www") == false)
assert(#redis_calls == 0 and lock_calls == 0)
""")


@needs_lua
def test_is_banned_local_reports_a_dict_error_instead_of_guessing():
    run_lease(r"""
datastore_get_error = "boom"
local banned, err = utils.is_banned_local("192.0.2.1", "www")
assert(banned == nil and err:find("boom"), tostring(err))
""")


# ------------------------------------------------------------------ is_ip_whitelisted local only


WHITELIST_PREAMBLE_PATCH = r"""
local cache_calls = { get = 0, get_local_nolock = 0 }
local cache_values = {}
package.preload["bunkerweb.cachestore"] = function()
    return {
        new = function()
            return {
                get = function(_, key) cache_calls.get = cache_calls.get + 1 return true, cache_values[key] end,
                get_local_nolock = function(_, key) cache_calls.get_local_nolock = cache_calls.get_local_nolock + 1 return true, cache_values[key] end,
            }
        end,
    }
end
internal_store.variables.global.SERVER_NAME = "www other"
internal_store.variables.global.USE_WHITELIST = "yes"
internal_store.variables.www = { USE_WHITELIST = "yes" }
internal_store.plugin_whitelist_lists_www = { IP = { "203.0.113.7" } }
"""


@needs_lua
def test_local_only_whitelist_reads_the_cache_without_callback_or_lock_and_matches_the_list():
    run_lease(WHITELIST_PREAMBLE_PATCH + r"""
local ok = utils.is_ip_whitelisted("203.0.113.7", "www", { local_only = true })
assert(ok == true)
assert(cache_calls.get == 0 and cache_calls.get_local_nolock >= 1, "local_only must use get_local_nolock only")
assert(utils.is_ip_whitelisted("198.51.100.1", "www", { local_only = true }) == false)
assert(cache_calls.get == 0)

-- the historical call is unchanged
utils.is_ip_whitelisted("203.0.113.7", "www")
assert(cache_calls.get >= 1)
""")


@needs_lua
def test_local_only_whitelist_never_reads_ngx_var_even_without_a_service():
    run_lease(WHITELIST_PREAMBLE_PATCH + r"""
ngx.var = setmetatable({}, { __index = function() error("ngx.var read in the handshake") end })
package.loaded["bunkerweb.utils"] = nil
utils = dofile(arg[1])
-- default server: no service name, the global list is the last resort
internal_store.variables.global.WHITELIST_IP = "203.0.113.50"
internal_store.plugin_whitelist_lists_other = { IP = {} }
local ok = utils.is_ip_whitelisted("203.0.113.50", nil, { local_only = true })
assert(ok == true, tostring(ok))
""")


@needs_lua
def test_local_only_whitelist_returns_the_error_instead_of_falling_through():
    run_lease(WHITELIST_PREAMBLE_PATCH + r"""
-- the service list cannot be read: fail closed to "unknown", never to "not whitelisted"
internal_store.plugin_whitelist_lists_www = nil
local ok, err = utils.is_ip_whitelisted("198.51.100.1", "www", { local_only = true })
assert(ok == nil and err, "expected nil, err; got " .. tostring(ok))
""")


# ------------------------------------------------------------------ cachestore.get_local_nolock


CACHESTORE_HARNESS = r"""
local calls = {}
ngx = { ERR = 3, INFO = 6, null = {}, config = { subsystem = "http" } }
package.preload["middleclass"] = function()
    return function(name)
        local class = { name = name, static = {} }
        class.__index = class
        class.new = function(self, ...) local o = setmetatable({}, class) if o.initialize then o:initialize(...) end return o end
        return class
    end
end
package.preload["bunkerweb.logger"] = function() return { new = function() return { log = function() end } end } end
package.preload["bunkerweb.clusterstore"] = function() return { new = function() return {} end } end
package.preload["bunkerweb.rediskeys"] = function() return { cluster_mode = function() return false end } end
package.preload["bunkerweb.utils"] = function()
    return { get_ctx_obj = function() end, is_cosocket_available = function() return true end }
end
local miss_error
package.preload["resty.mlcache"] = function()
    return {
        new = function()
            return {
                get = function(_, key, opts, callback, ...)
                    calls[#calls + 1] = { key = key, opts = opts, callback = callback }
                    if miss_error then return nil, miss_error end
                    return "value-of-" .. key, nil, 1
                end,
            }
        end,
    }
end
local cachestore = dofile(arg[1])
"""


@needs_lua
def test_get_local_nolock_reads_without_a_callback_even_when_cosockets_are_available():
    assert LUA is not None
    body = r"""
local store = cachestore:new(true)
local ok, value = store:get_local_nolock("k")
assert(ok == true and value == "value-of-k")
assert(#calls == 1 and calls[1].callback == nil, "a callback would take a lock and may yield")

miss_error = "shm broke"
local ok2, err = store:get_local_nolock("k")
assert(ok2 == false and err == "shm broke")
"""
    result = subprocess.run(
        [LUA, "-", str(CACHESTORE_LUA)],
        input=f'package.path = "{LUA_DIR}/?.lua;" .. package.path\n' + CACHESTORE_HARNESS + body,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout


# ------------------------------------------------------------------ api.lua POST /unban with lease_id


def _unban_handler() -> str:
    source = API_LUA.read_text(encoding="utf-8")
    match = re.search(r'^api\.global\.POST\["\^/unban\$"\] = function\(self\).*?^end$', source, re.M | re.S)
    assert match, "POST /unban is gone from api.lua"
    return match.group(0)


UNBAN_HARNESS = r"""
local json = require("cjson")
local HTTP_OK, HTTP_BAD_REQUEST, HTTP_INTERNAL_SERVER_ERROR = 200, 400, 500
local ERR = 3
local logger = { log = function() end }
local RESERVED_SERVICE_NAMES = { ["unknown"] = true, ["Web UI"] = true, ["bwcli"] = true, ["default server"] = true, [""] = true }
local calls = {}
local lease_result, lease_error = "removed", nil
local utils = {
    remove_ban = function(...) calls[#calls + 1] = { "remove_ban", ... } return true, "success" end,
    remove_lease = function(...) calls[#calls + 1] = { "remove_lease", ... } if lease_error then return nil, lease_error end return lease_result end,
}
local is_ipv4 = function(ip) return ip:find("^%d+%.%d+%.%d+%.%d+$") ~= nil end
local is_ipv6 = function(ip) return ip:find(":", 1, true) ~= nil end
local body
local read_body = function() end
local get_body_data = function() return body end
local get_body_file = function() return nil end
local open = io.open
local decode = json.decode
local api = { global = { POST = {} } }
local self = {
    ctx = { bw = { remote_addr = "unix:" } },
    response = function(_, http_status, status, msg) return http_status, { status = status, msg = msg } end,
}
"""


def _run_unban(request: dict, body_script: str) -> None:
    assert LUA is not None
    handler = _unban_handler()
    encode_calls = r"""
package.preload["cjson"] = function()
    return {
        decode = function(value) return value end,
        encode = function(value) return value end,
    }
end
"""
    request_lua = "{" + ", ".join(f"[{k!r}] = {v!r}" if not isinstance(v, (int, float)) else f"[{k!r}] = {v}" for k, v in request.items()) + "}"
    script = encode_calls + UNBAN_HARNESS + f"body = {request_lua}\n" + handler + '\nlocal handler = api.global.POST["^/unban$"]\n' + body_script
    result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr + result.stdout


@needs_lua
def test_unban_with_a_lease_id_goes_to_remove_lease_and_never_to_remove_ban():
    _run_unban(
        {"ip": "192.0.2.1", "ban_scope": "global", "lease_id": "aaaa1111aaaa1111"},
        r"""
local status, resp = handler(self)
assert(status == 200 and resp.status == "success", tostring(status))
assert(#calls == 1 and calls[1][1] == "remove_lease", "calls: " .. #calls .. " " .. tostring(calls[1] and calls[1][1]))
assert(calls[1][2] == "192.0.2.1" and calls[1][3] == "global" and calls[1][5] == "aaaa1111aaaa1111")
assert(resp.result == "removed", "the instance must say what happened: " .. tostring(resp.result))
""",
    )


@needs_lua
def test_unban_reports_changed_and_absent_as_a_result_not_an_error():
    for outcome in ("changed", "absent"):
        _run_unban(
            {"ip": "192.0.2.1", "ban_scope": "service", "service": "www", "lease_id": "aaaa1111aaaa1111"},
            f"""
lease_result = "{outcome}"
local status, resp = handler(self)
assert(status == 200 and resp.result == "{outcome}", tostring(status) .. tostring(resp.result))
assert(calls[1][3] == "service" and calls[1][4] == "www")
""",
        )


@needs_lua
def test_unban_without_a_lease_id_is_the_unchanged_generic_path():
    _run_unban(
        {"ip": "192.0.2.1", "ban_scope": "global"},
        r"""
local status = handler(self)
assert(status == 200)
assert(#calls == 1 and calls[1][1] == "remove_ban", "the generic unban must not change")
""",
    )


@needs_lua
def test_unban_rejects_a_malformed_lease_id_and_reports_an_instance_error():
    _run_unban(
        {"ip": "192.0.2.1", "ban_scope": "global", "lease_id": ""},
        r"""
local status = handler(self)
assert(status == 400 and #calls == 0, tostring(status))
""",
    )
    _run_unban(
        {"ip": "192.0.2.1", "ban_scope": "global", "lease_id": "aaaa1111aaaa1111"},
        r"""
lease_error = "redis down"
local status, resp = handler(self)
assert(status == 500 and resp.status == "error" and resp.msg:find("redis down"))
""",
    )


@needs_lua
def test_unban_passes_the_internal_deadline_to_remove_lease():
    _run_unban(
        {"ip": "192.0.2.1", "ban_scope": "global", "lease_id": "aaaa1111aaaa1111", "not_after": 12345},
        r"""
handler(self)
assert(calls[1][6] == 12345, "not_after must reach the locked mutation")
""",
    )
