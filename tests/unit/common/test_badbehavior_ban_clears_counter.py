"""Banning an IP must delete the Bad Behavior counter the ban was derived from (issue #3818).

Complement to ``test_remove_ban_clears_badbehavior_state.py`` (the ``utils.remove_ban`` purge). That purge runs in the VM that
owns the *ban*; this one runs in the VM that owns the *counter*, at the moment the ban is created. It covers what an unban can
never do: when a ban simply lapses nothing calls ``remove_ban``, so the counter that produced it is still at the threshold and
the first offence after the expiry re-bans at once (``expiry_one_offence_is_not_enough`` in ``tests/core/badbehavior.yml``). It
also reaches a Stream service without Redis, whose counter lives in ``datastore_stream`` where the HTTP-side unban cannot go.

Why the counter may go at ban time: once banned, ``log()`` returns early and the timer skips banned IPs before ``increase()``,
so nothing reads the key again until the ban is lifted. Pending ``plugin_badbehavior_decr`` entries floor at 0 and delete on
both paths, so they cannot resurrect it (pinned below, local and Redis).

The hazard this file pins: the delete must sit in the **success** branch of ``add_ban``. A delete on a failed ``add_ban``
resets an attacker's progress on every failure, while the ban never sticks.

Harness: pytest driving stand-alone Lua. The real ``badbehavior.lua``, ``middleclass.lua`` and ``rediskeys.lua`` run; the
plugin base class, ``cjson``, ``bunkerweb.utils``, the metrics module, the datastore and the clusterstore are stubs. The
counter a test asserts on is the one ``increase()`` really wrote, and the Redis key is the one ``rediskeys`` really spells.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
BADBEHAVIOR_LUA = ROOT / "src" / "common" / "core" / "badbehavior" / "badbehavior.lua"
MIDDLECLASS_LUA = ROOT / "src" / "bw" / "lua" / "middleclass.lua"
REDISKEYS_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "rediskeys.lua"

LUA = shutil.which("lua") or shutil.which("luajit")
needs_lua = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")


PREAMBLE = r"""
local BADBEHAVIOR, MIDDLECLASS, REDISKEYS, subsystem = arg[1], arg[2], arg[3], arg[4]

-- cjson: opaque round-trip tokens, so a test can never accidentally depend on the JSON text.
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

local class = dofile(MIDDLECLASS)
package.preload["middleclass"] = function() return class end

ngx = {
    var = {},
    ERR = 3,
    WARN = 4,
    NOTICE = 5,
    null = {},
    config = { subsystem = subsystem },
    worker = { id = function() return 0 end },
    shared = { datastore = {}, datastore_stream = {} },
}

-- Datastore: `store` holds the counters, `lists` the incr/decr work queues, `deletes` every key
-- the module asked to remove (so a test can tell "never written" from "written then deleted").
local store, ttls, lists, deletes = {}, {}, {}, {}
local datastore = {
    dict = {
        rpush = function(_, key, value)
            lists[key] = lists[key] or {}
            lists[key][#lists[key] + 1] = value
            return true
        end,
    },
    llen = function(_, key) return #(lists[key] or {}) end,
    lpop = function(_, key)
        local list = lists[key] or {}
        if #list == 0 then return nil, "empty list" end
        return table.remove(list, 1)
    end,
    get = function(_, key)
        if store[key] == nil then return nil, "not found" end
        return store[key]
    end,
    set_with_retries = function(_, key, value, ttl)
        store[key], ttls[key] = value, ttl
        return true, "success"
    end,
    delete = function(_, key)
        deletes[#deletes + 1] = key
        store[key], ttls[key] = nil, nil
        return true, "success"
    end,
}

-- Clusterstore: records every call verbatim. `redis_counters` models the two eval scripts the
-- module sends: the INCR one raises the counter, the DECR one lowers it and deletes it at 0 or less.
local redis_calls, redis_counters = {}, {}
local redis_connect_ok, redis_connect_calls = true, 0
local redis_del_error = nil
local redis_del_returns_zero = false
local clusterstore = {
    connect = function()
        redis_connect_calls = redis_connect_calls + 1
        if redis_connect_ok then return true end
        return false, "redis unavailable"
    end,
    call = function(_, ...)
        local arguments = { ... }
        redis_calls[#redis_calls + 1] = arguments
        if arguments[1] == "eval" then
            local key = arguments[4]
            if arguments[2]:find("DECR", 1, true) then
                local value = (redis_counters[key] or 0) - 1
                redis_counters[key] = value > 0 and value or nil
                return value
            end
            redis_counters[key] = (redis_counters[key] or 0) + 1
            return redis_counters[key]
        end
        if arguments[1] == "del" then
            if redis_del_error then return false, redis_del_error end
            redis_counters[arguments[2]] = nil
            -- Redis answers 0 when the key was not there. 0 is TRUTHY in Lua, so a test must be able
            -- to produce it: `if not deleted` is the right guard, `deleted == 0` is not a failure.
            if redis_del_returns_zero then return 0 end
            return 1
        end
        return true
    end,
    close = function() return true end,
}

-- utils: the symbols `badbehavior.lua` localises at load time, plus `get_variable` for the real rediskeys.
local add_ban_ok, add_ban_err = true, nil
local add_ban_calls, remove_ban_calls = {}, {}
local banned, whitelisted = {}, {}
local cluster_nodes = nil
package.preload["bunkerweb.utils"] = function()
    return {
        add_ban = function(ip, reason, ban_time, server_name, country, ban_scope, reason_data)
            add_ban_calls[#add_ban_calls + 1] = {
                ip = ip,
                reason = reason,
                ban_time = ban_time,
                server_name = server_name,
                country = country,
                ban_scope = ban_scope,
                reason_data = reason_data,
            }
            if not add_ban_ok then return false, add_ban_err or "can't save ban" end
            return true, "success"
        end,
        remove_ban = function(ip, server_name, ban_scope)
            remove_ban_calls[#remove_ban_calls + 1] = { ip = ip, server_name = server_name, ban_scope = ban_scope }
            return true, "success"
        end,
        is_whitelisted = function() return false end,
        is_ip_whitelisted = function(ip) return whitelisted[ip] or false, "ip" end,
        is_banned = function(ip, server_name) return banned[server_name .. "/" .. ip] or banned[ip] or false end,
        get_security_mode = function() return "block" end,
        get_variable = function(name)
            if name == "REDIS_CLUSTER_NODES" then return cluster_nodes end
            return nil
        end,
    }
end

-- The real key spelling: local datastore keys and Redis keys differ, and cluster mode hash-tags the IP.
package.preload["bunkerweb.rediskeys"] = function() return dofile(REDISKEYS) end

-- The ban evidence store is a separate module with its own tests; keep what the timer hands it.
local evidence = {}
package.preload["metrics/metrics"] = function()
    return {
        new = function()
            return {
                store_ban_evidence = function(_, events, meta)
                    evidence[#evidence + 1] = { events = events, meta = meta }
                    return { stored = #events }
                end,
            }
        end,
    }
end

-- Plugin base class: the methods `badbehavior.lua` inherits, no more.
local logs, metric_writes, metric_tables = {}, 0, { increments = {} }
local plugin = class("plugin")
function plugin:initialize(id, ctx)
    self.id = id
    self.ctx = ctx
end
function plugin:ret(ret, msg) return ret, msg end
function plugin:set_metric(_, _, _) metric_writes = metric_writes + 1 end
function plugin:get_metric(_, key) return metric_tables[key] end
function plugin:log_throttled(_, _, msg) logs[#logs + 1] = msg end
function plugin:flush_log_recaps() return true end
package.preload["bunkerweb.plugin"] = function() return plugin end

local badbehavior = dofile(BADBEHAVIOR)

local function new_plugin()
    local instance = badbehavior:new({ bw = {} })
    instance.datastore = datastore
    instance.clusterstore = clusterstore
    instance.logger = { log = function(_, _, message) logs[#logs + 1] = message end }
    instance.variables = {}
    instance.use_redis = false
    return instance
end

-- Queue one increment operation, shaped exactly like `badbehavior:log()` builds it.
local function queue_offence(options)
    lists["plugin_badbehavior_incr"] = lists["plugin_badbehavior_incr"] or {}
    local queue = lists["plugin_badbehavior_incr"]
    queue[#queue + 1] = json.encode({
        ip = options.ip or "192.0.2.1",
        count_time = options.count_time or 60,
        ban_time = options.ban_time or 86400,
        threshold = options.threshold or 5,
        use_redis = options.use_redis or false,
        server_name = options.server_name or "www.example.com",
        security_mode = options.security_mode or "block",
        country = options.country or "FR",
        timestamp = 100,
        status = options.status or "403",
        ban_scope = options.ban_scope or "global",
    })
end

local function redis_del_keys()
    local keys = {}
    for _, call in ipairs(redis_calls) do
        if call[1] == "del" then
            for index = 2, #call do keys[#keys + 1] = call[index] end
        end
    end
    return keys
end

local function deleted_once(key)
    local seen = 0
    for _, deleted in ipairs(deletes) do
        if deleted == key then seen = seen + 1 end
    end
    return seen
end

-- Make every queued decrement due now, as it is once COUNT_TIME has elapsed.
local function make_decrements_due()
    for _, token in ipairs(lists["plugin_badbehavior_decr"] or {}) do encoded[token].timestamp = 1 end
end
"""


def _run(body: str, subsystem: str = "http") -> None:
    assert LUA is not None
    result = subprocess.run(
        [LUA, "-", str(BADBEHAVIOR_LUA), str(MIDDLECLASS_LUA), str(REDISKEYS_LUA), subsystem],
        input=PREAMBLE + body,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


# ------------------------------------------------------------------ local datastore


@needs_lua
def test_the_reported_scenario_a_global_ban_deletes_the_counter_it_was_derived_from():
    # #3818 from the expiry end: BAD_BEHAVIOR_THRESHOLD=5, the 5th offence bans, and the counter that
    # reached 5 must not be sitting there when the ban lapses.
    _run(
        r"""
local bb = new_plugin()
store["plugin_badbehavior_count_192.0.2.1"] = 4
queue_offence({ threshold = 5, ban_scope = "global" })

assert(bb:timer())

assert(#add_ban_calls == 1, "the 5th offence did not ban")
assert(
    store["plugin_badbehavior_count_192.0.2.1"] == nil,
    "counter survived its own ban: the lapsed ban hands the IP a threshold-1 head start"
)
assert(deleted_once("plugin_badbehavior_count_192.0.2.1") == 1, "counter was never written then deleted")
""",
    )


@needs_lua
def test_a_below_threshold_offence_bans_nothing_and_keeps_the_counter():
    # The delete is tied to the ban, not to every timer pass: a counter still climbing must climb.
    _run(
        r"""
local bb = new_plugin()
store["plugin_badbehavior_count_192.0.2.1"] = 2
queue_offence({ threshold = 5, ban_scope = "global" })

assert(bb:timer())

assert(#add_ban_calls == 0, "banned below the threshold")
assert(store["plugin_badbehavior_count_192.0.2.1"] == 3, "counter was cleared without a ban")
""",
    )


@needs_lua
def test_a_service_ban_deletes_that_services_counter_and_no_other():
    _run(
        r"""
local bb = new_plugin()
store["plugin_badbehavior_count_smtp_192.0.2.1"] = 4
store["plugin_badbehavior_count_192.0.2.1"] = 7
store["plugin_badbehavior_count_web_192.0.2.1"] = 3
store["plugin_badbehavior_count_smtp_198.51.100.9"] = 4
queue_offence({ threshold = 5, ban_scope = "service", server_name = "smtp" })

assert(bb:timer())

assert(#add_ban_calls == 1 and add_ban_calls[1].ban_scope == "service")
assert(store["plugin_badbehavior_count_smtp_192.0.2.1"] == nil, "target counter survived")
assert(store["plugin_badbehavior_count_192.0.2.1"] == 7, "a service ban cleared the global counter")
assert(store["plugin_badbehavior_count_web_192.0.2.1"] == 3, "another service's counter was cleared")
assert(store["plugin_badbehavior_count_smtp_198.51.100.9"] == 4, "another IP's counter was cleared")
""",
    )


@needs_lua
def test_a_global_ban_does_not_reach_into_another_services_counter():
    # Global scope owns the unsuffixed key only. The per-service leftovers are `utils.remove_ban`'s
    # job (it sweeps by prefix); the ban-time delete knows one key.
    _run(
        r"""
local bb = new_plugin()
store["plugin_badbehavior_count_192.0.2.1"] = 4
store["plugin_badbehavior_count_smtp_192.0.2.1"] = 3
queue_offence({ threshold = 5, ban_scope = "global", server_name = "www.example.com" })

assert(bb:timer())

assert(store["plugin_badbehavior_count_192.0.2.1"] == nil, "global counter survived")
assert(store["plugin_badbehavior_count_smtp_192.0.2.1"] == 3, "a global ban swept a per-service counter")
""",
    )


@needs_lua
def test_a_failed_add_ban_leaves_the_counter_intact():
    # THE hazard. A delete placed above the `if not ok` check resets an attacker's progress on every
    # FAILED ban: the IP needs the full threshold again, forever, while the ban never sticks.
    _run(
        r"""
local bb = new_plugin()
add_ban_ok, add_ban_err = false, "datastore full"
store["plugin_badbehavior_count_192.0.2.1"] = 4
queue_offence({ threshold = 5, ban_scope = "global" })

local ok, err = bb:timer()

assert(#add_ban_calls == 1, "add_ban was not attempted")
assert(not ok and err:find("can't save ban", 1, true), "the timer swallowed the ban failure: " .. tostring(err))
assert(
    store["plugin_badbehavior_count_192.0.2.1"] == 5,
    "counter was reset by a ban that FAILED: every failure gives the attacker a clean slate"
)
assert(deleted_once("plugin_badbehavior_count_192.0.2.1") == 0, "delete was issued on the failure path")
""",
    )


@needs_lua
def test_a_failed_add_ban_issues_no_redis_delete_either():
    # Same hazard, Redis half: a `DEL` on the failure path resets the shared counter fleet-wide.
    _run(
        r"""
local bb = new_plugin()
add_ban_ok = false
redis_counters["plugin_bad_behavior_192.0.2.1"] = 4
queue_offence({ threshold = 5, ban_scope = "global", use_redis = true })

local ok = bb:timer()

assert(not ok)
assert(#redis_del_keys() == 0, "a failed ban still issued a Redis DEL")
assert(redis_counters["plugin_bad_behavior_192.0.2.1"] == 5, "the Redis counter was reset by a failed ban")
""",
    )


@needs_lua
def test_a_whitelisted_ip_at_the_threshold_is_not_banned_and_its_counter_is_not_deleted_here():
    # The whitelist branch never reaches add_ban, so the new delete must not run there: that path
    # clears state through `remove_ban`, which is covered by its own test file.
    _run(
        r"""
local bb = new_plugin()
whitelisted["192.0.2.1"] = true
store["plugin_badbehavior_count_192.0.2.1"] = 4
queue_offence({ threshold = 5, ban_scope = "global" })

assert(bb:timer())

assert(#add_ban_calls == 0, "a whitelisted IP was banned")
assert(#remove_ban_calls == 1, "the whitelist branch no longer calls remove_ban")
assert(deleted_once("plugin_badbehavior_count_192.0.2.1") == 0, "the ban-time delete ran without a ban")
""",
    )


# ------------------------------------------------------------------------- Redis


@needs_lua
def test_a_global_ban_deletes_the_global_redis_counter():
    # Not optional: `increase()` prefers the Redis counter and overwrites the local one with it, so
    # deleting the local key alone re-bans on the first request after the expiry.
    _run(
        r"""
local bb = new_plugin()
redis_counters["plugin_bad_behavior_192.0.2.1"] = 4
queue_offence({ threshold = 5, ban_scope = "global", use_redis = true })

assert(bb:timer())

assert(#add_ban_calls == 1)
local keys = redis_del_keys()
assert(#keys == 1, "expected exactly one DEL, got " .. #keys)
assert(keys[1] == "plugin_bad_behavior_192.0.2.1", "wrong Redis key deleted: " .. tostring(keys[1]))
assert(redis_counters["plugin_bad_behavior_192.0.2.1"] == nil, "the Redis counter survived the ban")
assert(store["plugin_badbehavior_count_192.0.2.1"] == nil, "the local mirror survived the ban")
""",
    )


@needs_lua
def test_a_service_ban_deletes_the_service_spelling_of_the_redis_key():
    _run(
        r"""
local bb = new_plugin()
redis_counters["plugin_bad_behavior_smtp_192.0.2.1"] = 4
redis_counters["plugin_bad_behavior_192.0.2.1"] = 9
queue_offence({ threshold = 5, ban_scope = "service", server_name = "smtp", use_redis = true })

assert(bb:timer())

local keys = redis_del_keys()
assert(#keys == 1 and keys[1] == "plugin_bad_behavior_smtp_192.0.2.1", "wrong key: " .. table.concat(keys, ","))
assert(redis_counters["plugin_bad_behavior_192.0.2.1"] == 9, "a service ban deleted the global Redis counter")
""",
    )


@needs_lua
def test_redis_cluster_mode_deletes_the_hash_tagged_counter_keys():
    # Dev differs from 1.7 here: in cluster mode `rediskeys.badbehavior` tags the IP, and the counter
    # lives under that spelling. A hard-coded `plugin_bad_behavior_<ip>` DEL would miss it entirely.
    _run(
        r"""
cluster_nodes = "n1:7000 n2:7000"
local bb = new_plugin()
queue_offence({ threshold = 5, ban_scope = "service", server_name = "smtp", use_redis = true, ip = "192.0.2.1" })
queue_offence({ threshold = 1, ban_scope = "global", use_redis = true, ip = "192.0.2.2" })
redis_counters["plugin_bad_behavior_smtp_{192.0.2.1}"] = 4
redis_counters["plugin_bad_behavior_{192.0.2.2}"] = 0

assert(bb:timer())

assert(#add_ban_calls == 2, "expected two bans, got " .. #add_ban_calls)
local keys = redis_del_keys()
table.sort(keys)
assert(
    table.concat(keys, ",") == "plugin_bad_behavior_smtp_{192.0.2.1},plugin_bad_behavior_{192.0.2.2}",
    "wrong cluster keys deleted: " .. table.concat(keys, ",")
)
assert(next(redis_counters) == nil, "a hash-tagged Redis counter survived the ban")
""",
    )


@needs_lua
def test_the_redis_connection_failure_does_not_break_the_ban():
    # An unreachable Redis must not turn a successful ban into a timer failure.
    _run(
        r"""
local bb = new_plugin()
redis_connect_ok = false
store["plugin_badbehavior_count_192.0.2.1"] = 4
queue_offence({ threshold = 5, ban_scope = "global", use_redis = true })

local ok, err = bb:timer()

assert(#add_ban_calls == 1, "the ban did not happen")
assert(ok, "a Redis outage failed the whole timer pass : " .. tostring(err))
assert(store["plugin_badbehavior_count_192.0.2.1"] == nil, "the local counter survived a Redis outage")
""",
    )


@needs_lua
def test_a_refused_redis_del_is_logged_and_leaves_the_ban_and_the_local_purge_standing():
    # The connection opened, the DEL came back refused. The counter genuinely survives in Redis: that
    # is worth a log line, not a rolled-back ban, and the local key must still be gone.
    _run(
        r"""
local bb = new_plugin()
redis_del_error = "READONLY You can't write against a read only replica"
redis_counters["plugin_bad_behavior_192.0.2.1"] = 4
queue_offence({ threshold = 5, ban_scope = "global", use_redis = true })

local ok, err = bb:timer()

assert(#add_ban_calls == 1, "the ban did not happen")
assert(ok, "a refused Redis DEL failed the whole timer pass : " .. tostring(err))
assert(#redis_del_keys() == 1, "no DEL was attempted")
assert(store["plugin_badbehavior_count_192.0.2.1"] == nil, "the local counter was not purged")

local logged = false
for _, message in ipairs(logs) do
    if message:find("can't delete redis counter", 1, true) and message:find("READONLY", 1, true) then
        logged = true
    end
end
assert(logged, "the refused DEL was swallowed silently")
""",
    )


@needs_lua
def test_a_del_that_answers_zero_is_a_success_not_a_failure():
    # Redis returns 0 from DEL when the key was already gone (routine: a decrement may have floored and
    # deleted it moments earlier). 0 is TRUTHY in Lua, so nothing is wrong and nothing is logged.
    _run(
        r"""
local bb = new_plugin()
redis_del_returns_zero = true
redis_counters["plugin_bad_behavior_192.0.2.1"] = 4
queue_offence({ threshold = 5, ban_scope = "global", use_redis = true })

local ok, err = bb:timer()

assert(#add_ban_calls == 1, "the ban did not happen")
assert(ok, "a DEL that answered 0 failed the whole timer pass : " .. tostring(err))
assert(#redis_del_keys() == 1, "no DEL was attempted")

for _, message in ipairs(logs) do
    assert(
        not message:find("can't delete redis counter", 1, true),
        "an absent Redis key was reported as a failure : " .. message
    )
end

-- Direct call too, so the return value is pinned and not only its logging side effect.
local del_ok, del_err = bb:redis_delete_counter("192.0.2.1", "www.example.com", "global")
assert(del_ok == true, "redis_delete_counter returned " .. tostring(del_ok) .. " / " .. tostring(del_err))
""",
    )


@needs_lua
def test_no_redis_call_is_made_when_redis_is_off():
    _run(
        r"""
local bb = new_plugin()
store["plugin_badbehavior_count_192.0.2.1"] = 4
queue_offence({ threshold = 5, ban_scope = "global", use_redis = false })

assert(bb:timer())

assert(store["plugin_badbehavior_count_192.0.2.1"] == nil, "the local counter survived")
assert(redis_connect_calls == 0, "Redis was contacted with use_redis=false")
assert(#redis_calls == 0, "Redis was called with use_redis=false")
""",
    )


# ------------------------------------------------------------- Stream / metrics / queues


@needs_lua
def test_the_stream_vm_deletes_its_own_counter():
    # `utils.add_ban` forwards Stream to the HTTP zone, so an HTTP-side unban cannot address
    # `datastore_stream`; this delete runs in the Stream VM itself. In-process the harness cannot tell
    # the zones apart: it pins that the Stream subsystem reaches the delete at all.
    _run(
        r"""
local bb = new_plugin()
store["plugin_badbehavior_count_192.0.2.1"] = 4
queue_offence({ threshold = 5, ban_scope = "global" })

assert(bb:timer())

assert(#add_ban_calls == 1, "the stream VM did not ban")
assert(store["plugin_badbehavior_count_192.0.2.1"] == nil, "the stream VM left its own counter behind")
""",
        subsystem="stream",
    )


@needs_lua
def test_the_ban_writes_no_metric_and_leaves_the_increments_ring_alone():
    # Issue #3818 also asks for the `badbehavior_*` metrics to be reset. They are history, not state:
    # the timer only READS the ring to build the ban's evidence. Scope guard, not a behaviour claim.
    _run(
        r"""
local bb = new_plugin()
metric_tables.increments = { { ip = "192.0.2.1", status = "403", server_name = "www.example.com", date = 100 } }
store["plugin_badbehavior_count_192.0.2.1"] = 4
queue_offence({ threshold = 5, ban_scope = "global" })

assert(bb:timer())

assert(#add_ban_calls == 1)
assert(metric_writes == 0, "the timer wrote a metric while banning")
assert(#metric_tables.increments == 1, "the increments ring was mutated by the ban")
assert(evidence[1].events[1].ip == "192.0.2.1", "the ban's evidence lost its event")
""",
    )


@needs_lua
def test_the_pending_decrement_queue_is_left_alone_by_the_ban():
    # The decrement loop has no ban check, so entries queued before the ban still fire afterwards, on a
    # key that no longer exists. The ban must not drop other IPs' queued work.
    _run(
        r"""
local bb = new_plugin()
lists["plugin_badbehavior_decr"] = { json.encode({
    ip = "198.51.100.9", count_time = 60, threshold = 5, use_redis = false,
    server_name = "www.example.com", status = "403", old_counter = 2,
    ban_scope = "global", timestamp = 2 ^ 40,
}) }
store["plugin_badbehavior_count_198.51.100.9"] = 2
store["plugin_badbehavior_count_192.0.2.1"] = 4
queue_offence({ threshold = 5, ban_scope = "global" })

assert(bb:timer())

assert(store["plugin_badbehavior_count_192.0.2.1"] == nil, "the banned IP's counter survived")
assert(#lists["plugin_badbehavior_decr"] >= 1, "another IP's queued decrement was dropped")
assert(store["plugin_badbehavior_count_198.51.100.9"] == 2, "another IP's counter was touched")
""",
    )


@needs_lua
def test_a_pending_local_decrement_after_the_ban_does_not_recreate_or_drive_the_counter_negative():
    # The offences that led to the ban each queued a decrement. They come due after the ban-time delete
    # and must find nothing to lower: the key stays absent and nothing is logged as an error.
    _run(
        r"""
local bb = new_plugin()
for _ = 1, 5 do queue_offence({ threshold = 5, ban_scope = "global" }) end
assert(bb:timer())
assert(#add_ban_calls == 1, "the 5th offence did not ban")
assert(store["plugin_badbehavior_count_192.0.2.1"] == nil, "counter survived its own ban")
assert(#lists["plugin_badbehavior_decr"] == 5, "the offences queued no decrement")

make_decrements_due()
assert(bb:timer(), "a decrement after the ban failed the timer")

assert(store["plugin_badbehavior_count_192.0.2.1"] == nil, "a stale decrement recreated the counter")
assert(#lists["plugin_badbehavior_decr"] == 0, "the decrements did not run")
for _, message in ipairs(logs) do
    assert(not message:find("can't ", 1, true), "a stale decrement logged a failure : " .. message)
end
""",
    )


@needs_lua
def test_a_pending_redis_decrement_after_the_ban_leaves_no_counter_behind():
    # Redis half: DECR on the deleted key goes to -1, and the script DELs anything at 0 or less, so the
    # key is never left negative. The local mirror is floored to 0 and deleted, not recreated.
    _run(
        r"""
local bb = new_plugin()
for _ = 1, 5 do queue_offence({ threshold = 5, ban_scope = "service", server_name = "smtp", use_redis = true }) end
assert(bb:timer())
assert(#add_ban_calls == 1, "the 5th offence did not ban")
assert(redis_counters["plugin_bad_behavior_smtp_192.0.2.1"] == nil, "the Redis counter survived its own ban")

make_decrements_due()
assert(bb:timer(), "a decrement after the ban failed the timer")

assert(redis_counters["plugin_bad_behavior_smtp_192.0.2.1"] == nil, "a stale decrement left a Redis counter behind")
assert(store["plugin_badbehavior_count_smtp_192.0.2.1"] == nil, "a stale decrement recreated the local counter")
for _, message in ipairs(logs) do
    assert(not message:find("can't ", 1, true), "a stale decrement logged a failure : " .. message)
end
""",
    )


@needs_lua
def test_deleting_the_counter_twice_is_harmless():
    # The ban-time delete and `remove_ban`'s purge overlap on an unban of a banned IP. The second one
    # finds nothing: no error, no log, no Redis failure.
    _run(
        r"""
local bb = new_plugin()
store["plugin_badbehavior_count_192.0.2.1"] = 5
redis_counters["plugin_bad_behavior_192.0.2.1"] = 5

bb:delete_counter("192.0.2.1", "www.example.com", "global", true)
local logged = #logs
bb:delete_counter("192.0.2.1", "www.example.com", "global", true)

assert(store["plugin_badbehavior_count_192.0.2.1"] == nil)
assert(redis_counters["plugin_bad_behavior_192.0.2.1"] == nil)
assert(#logs == logged, "the second delete logged : " .. tostring(logs[#logs]))
""",
    )


# ------------------------------------------------------------------ static backstops


def test_the_delete_sits_inside_the_add_ban_success_branch():
    # Static backstop for the hazard above: even if the behavioural test were ever weakened, the
    # ordering itself is pinned. The failure check must be reached before any counter delete.
    source = BADBEHAVIOR_LUA.read_text()
    timer = source.partition("function badbehavior:timer()")[2].partition("function badbehavior:increase(")[0]

    failure_check = timer.index("""ret_err = "can't save ban : " .. err""")
    assert "delete_counter" in timer, "the ban-time counter delete is missing from the timer"
    assert failure_check < timer.index("delete_counter"), "the counter delete runs before the add_ban success check"


def test_both_counter_key_spellings_are_covered_by_the_ban_time_delete():
    # The naming drift between the two stores is the trap: the local datastore says
    # `plugin_badbehavior_count_`, Redis says `plugin_bad_behavior_` (owned by `rediskeys.badbehavior`,
    # hash-tagged in cluster mode). Handling one shape only fixes half the deployments.
    source = BADBEHAVIOR_LUA.read_text()
    delete_counter = source.partition("function badbehavior:delete_counter(")[2].partition("\nfunction ")[0]
    redis_delete = source.partition("function badbehavior:redis_delete_counter(")[2].partition("\nend\n")[0]

    assert '"plugin_badbehavior_count_"' in delete_counter, "the local counter spelling is not deleted"
    assert "self:redis_delete_counter(" in delete_counter, "the Redis half was dropped"
    assert "rediskeys.badbehavior(" in redis_delete, "the Redis counter key does not come from rediskeys"
    assert "rediskeys.cluster_mode()" in redis_delete, "the Redis counter key ignores cluster mode"
    assert '"del"' in redis_delete, "redis_delete_counter issues no DEL"
    # Same scope split as `increase()` builds, local spelling.
    assert delete_counter.count('server_name .. "_" .. ip') == 1
