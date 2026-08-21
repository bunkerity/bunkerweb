"""Banning an IP must delete the Bad Behavior counter the ban was derived from (issue #3818).

Complement to `test_remove_ban_clears_badbehavior_state.py` (the `utils.remove_ban` purge, commit
`b47ccf824`). That purge runs in the VM that owns the *ban*; this one runs in the VM that owns the
*counter*, at the moment the ban is created. It closes two cases `remove_ban` structurally cannot:

* a Stream service without Redis -- `utils.add_ban` forwards Stream to the HTTP zone, so the ban
  lives in the HTTP datastore while the counter stays in `datastore_stream`, out of the HTTP-side
  unban's reach. `badbehavior:timer()` runs in the Stream VM, on the Stream dict;
* sub-threshold per-service Redis counters, which never exist at ban time.

Why the counter may go at ban time: once banned, `log()` returns early (`badbehavior.lua:61-68`)
and the timer skips banned IPs before `increase()` (`:211`), so nothing reads the key again until
the ban is lifted -- which is exactly when the issue says it must be zero. Pending
`plugin_badbehavior_decr` entries floor at 0 and delete on both paths (`:488-490` local,
`:573-579` Redis), so they cannot resurrect it.

The security hazard this file exists to pin: the delete must sit in the **success** branch
(`:345`), never before the `if not ok` check (`:342`). A delete on a failed `add_ban` resets an
attacker's progress on every failure -- the IP would need the full threshold again, forever, while
the ban never sticks. `test_a_failed_add_ban_leaves_the_counter_intact` is that test.

Harness: pytest driving stand-alone PUC Lua 5.4 (no `luajit`, no `ffi`, no OpenResty on this host).
`badbehavior.lua` had no fixture, so `PREAMBLE` below builds the smallest one that lets both
branches of the `add_ban` call run: real `middleclass`, a stub `bunkerweb.plugin` base class, and
mocks for `cjson`, `bunkerweb.utils`, the datastore and the clusterstore. `increase()` and the two
key spellings are the module's own code, not re-implemented here -- the counter a test asserts on
is the one `increase()` actually wrote.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
BADBEHAVIOR_LUA = ROOT / "src" / "common" / "core" / "badbehavior" / "badbehavior.lua"
MIDDLECLASS_LUA = ROOT / "src" / "bw" / "lua" / "middleclass.lua"

LUA = shutil.which("lua") or shutil.which("luajit")
needs_lua = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")


PREAMBLE = r"""
local BADBEHAVIOR, MIDDLECLASS, subsystem = arg[1], arg[2], arg[3]

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
local datastore_writes = 0
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
        datastore_writes = datastore_writes + 1
        return true, "success"
    end,
    delete = function(_, key)
        deletes[#deletes + 1] = key
        store[key], ttls[key] = nil, nil
        return true, "success"
    end,
}

-- Clusterstore: records every call verbatim; `redis_counters` feeds the INCR/DECR eval scripts.
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
            redis_counters[key] = (redis_counters[key] or 0) + 1
            return redis_counters[key]
        end
        if arguments[1] == "del" then
            if redis_del_error then return false, redis_del_error end
            redis_counters[arguments[2]] = nil
            -- Redis answers 0 when the key was not there. 0 is TRUTHY in Lua, which is exactly the
            -- trap wave 2 hit in `remove_ban`, so a test must be able to produce it.
            if redis_del_returns_zero then return 0 end
            return 1
        end
        return true
    end,
    close = function() return true end,
}

-- utils: only the six symbols `badbehavior.lua` localises at load time.
local add_ban_ok, add_ban_err = true, nil
local add_ban_calls, remove_ban_calls = {}, {}
local banned = {}
local whitelisted = {}
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
    }
end

-- Plugin base class: the five methods `badbehavior.lua` inherits, no more.
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

-- Queue one increment operation, shaped exactly like `badbehavior:log()` builds it (`:81-96`).
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
"""


def _run(body: str, subsystem: str = "http") -> None:
    assert LUA is not None
    result = subprocess.run(
        [LUA, "-", str(BADBEHAVIOR_LUA), str(MIDDLECLASS_LUA), subsystem],
        input=PREAMBLE + body,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


# ------------------------------------------------------------------ local datastore


@needs_lua
def test_the_reported_scenario_a_global_ban_deletes_the_counter_it_was_derived_from():
    # #3818 verbatim, from the other end: BAD_BEHAVIOR_THRESHOLD=5, the 5th offence bans, and the
    # counter that reached 5 must not be sitting there waiting for the unban.
    _run(
        r"""
local bb = new_plugin()
store["plugin_badbehavior_count_192.0.2.1"] = 4
queue_offence({ threshold = 5, ban_scope = "global" })

assert(bb:timer())

assert(#add_ban_calls == 1, "the 5th offence did not ban")
assert(
    store["plugin_badbehavior_count_192.0.2.1"] == nil,
    "counter survived its own ban: the unban hands the IP a threshold-1 head start"
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
    # Same scope semantics as the ban keys, and as `increase()` builds them (`:400-403`).
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
    # The mirror of the test above: global scope owns the unsuffixed key only. The per-service
    # leftovers are `utils.remove_ban`'s job (it sweeps by prefix); the ban-time delete knows one key.
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
    # THE hazard (report `badbehavior-unban-alternative.md` section (h), last paragraph). A delete
    # placed above the `if not ok` check at `:342` resets an attacker's progress on every FAILED
    # ban: the IP needs the full threshold again, forever, while the ban never sticks.
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


# ------------------------------------------------------------------------- Redis


@needs_lua
def test_a_global_ban_deletes_the_global_redis_counter():
    # Not optional: `increase()` prefers the Redis counter and overwrites the local one with it
    # (`:405-428`), so deleting the local key alone re-bans on the first request after the unban.
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
    # `plugin_bad_behavior_<server_name>_<ip>`, the spelling `redis_increase` writes (`:519-522`).
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
def test_the_redis_connection_is_closed_and_a_failure_does_not_break_the_ban():
    # Mirrors `redis_decrease`'s connect/call/close shape (`:582-593`): an unreachable Redis must
    # not turn a successful ban into a timer failure, and must not leak the connection.
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
    # The other half of `redis_delete_counter`'s error contract: the connection opened, the DEL came
    # back refused. The counter genuinely survives in Redis -- that is worth a log line, not a
    # rolled-back ban, and the local key must still be gone.
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
    # Redis returns 0 from DEL when the key was already gone -- routine here, since the local
    # decrease path may have floored and deleted the shared counter moments earlier. 0 is TRUTHY in
    # Lua, so `if not deleted` is the correct guard and `deleted == 0` must NOT be folded into it;
    # that conflation is the trap wave 2 hit in `remove_ban`. Nothing is wrong, so nothing is logged.
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
    # RULE 17: `use_redis` is set explicitly here, never inherited from the fixture's default.
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


# ------------------------------------------------------------- Stream / metrics / scope


@needs_lua
def test_the_stream_vm_deletes_its_own_counter():
    # The case only this complement closes. `utils.add_ban` forwards Stream to the HTTP zone, so an
    # HTTP-side unban cannot address `datastore_stream`; this delete runs in the Stream VM itself.
    # In-process the harness cannot tell the two zones apart -- what it pins is that the Stream
    # subsystem reaches the delete at all, rather than short-circuiting like `remove_ban` does.
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
    # Issue #3818 also asks for the `badbehavior_*` metrics to be reset. They are history, not
    # state (conception 2UuqIAeeha): the timer only READS the ring to build `reason_data`. Scope
    # guard, not a behaviour claim.
    _run(
        r"""
local bb = new_plugin()
metric_tables.increments = { { ip = "192.0.2.1", status = "403" } }
store["plugin_badbehavior_count_192.0.2.1"] = 4
queue_offence({ threshold = 5, ban_scope = "global" })

assert(bb:timer())

assert(#add_ban_calls == 1)
assert(metric_writes == 0, "the timer wrote a metric while banning")
assert(#metric_tables.increments == 1, "the increments ring was mutated by the ban")
assert(add_ban_calls[1].reason_data[1].ip == "192.0.2.1", "reason_data lost its event")
""",
    )


@needs_lua
def test_the_pending_decrement_queue_is_left_alone_by_the_ban():
    # The decrement loop has no ban check (`:151-182`), so entries queued before the ban still fire
    # afterwards, on a key that no longer exists. Both floor paths delete rather than resurrect --
    # but the ban must not drop other clients' queued work to get there.
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


def test_the_delete_sits_inside_the_add_ban_success_branch():
    # Static backstop for the hazard above: even if the behavioural test were ever weakened, the
    # ordering itself is pinned. `if not ok` must be reached before any counter delete.
    source = BADBEHAVIOR_LUA.read_text()
    timer = source.partition("function badbehavior:timer()")[2].partition("function badbehavior:increase(")[0]

    failure_check = timer.index('ret_err = "can\'t save ban : " .. err')
    assert "delete_counter" in timer, "the ban-time counter delete is missing from the timer"
    assert failure_check < timer.index("delete_counter"), "the counter delete runs before the add_ban success check"


def test_both_counter_key_spellings_are_covered_by_the_ban_time_delete():
    # The naming drift between the two stores is the trap this row exists for: the local datastore
    # says `plugin_badbehavior_count_`, Redis says `plugin_bad_behavior_`. Handling one shape only
    # fixes half the deployments, and which half depends on whether Redis is configured.
    source = BADBEHAVIOR_LUA.read_text()
    delete_counter = source.partition("function badbehavior:delete_counter(")[2].partition("\nfunction ")[0]
    redis_delete = source.partition("function badbehavior:redis_delete_counter(")[2].partition("\nend\n")[0]

    assert '"plugin_badbehavior_count_"' in delete_counter, "the local counter spelling is not deleted"
    assert "self:redis_delete_counter(" in delete_counter, "the Redis half was dropped"
    assert '"plugin_bad_behavior_"' in redis_delete, "the Redis counter spelling is not deleted"
    assert '"del"' in redis_delete, "redis_delete_counter issues no DEL"
    # Same scope split as `increase()` builds (`:400-403` / `:519-522`), in both spellings.
    assert delete_counter.count('server_name .. "_" .. ip') == 1
    assert redis_delete.count('server_name .. "_" .. ip') == 1
