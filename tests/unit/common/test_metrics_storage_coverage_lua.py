"""Exercise real metrics storage closures with deterministic Redis/OpenResty boundaries."""

import pytest
from _lua_core_helpers import BW_LUA, LUA, run_core

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")
MODULE = BW_LUA.parents[1] / "common/core/metrics/metrics.lua"

PRELUDE = r"""
ngx.worker = { id = function() return 3 end }
ngx.unescape_uri = function(v) return v end
ngx.md5 = function(v) assert(v == HOSTNAME) return "hashed-host" end
local real_open = io.open
io.open = function(path, mode)
    if path ~= "/proc/sys/kernel/hostname" then return real_open(path, mode) end
    HOST_READS = (HOST_READS or 0) + 1
    if HOSTNAME == false then return nil end
    return { read = function() return HOSTNAME or "node-1" end, close = function() HOST_CLOSED = true end }
end
package.loaded["middleclass"] = function() return {} end
package.loaded["bunkerweb.plugin"] = {}
package.loaded["bunkerweb.datastore"] = {}
package.loaded["bunkerweb.logger"] = { new = function() return { log = function(_, level, msg) LOGS[#LOGS + 1] = {level, msg} end } end }
package.loaded["bunkerweb.utils"] = { get_variable = function() return CLUSTER and "node:6379" or "" end }
package.loaded["resty.lrucache"] = { new = function(capacity)
    if LRU_FAIL then return nil, "allocation failed" end
    local values = {}
    LRU = {
        capacity = function() return CAPACITY or capacity end,
        get_keys = function() local keys = {} for k in pairs(values) do keys[#keys + 1] = k end table.sort(keys) return keys end,
        get = function(_, k) return values[k] end,
        set = function(_, k, v) values[k] = v end,
        delete = function(_, k) values[k] = nil end,
    }
    return LRU
end }
local metrics = dofile(MODULE)

-- Inspect existing closures, never rewrite or extract source text.
H, UP = {}, {}
local visited = {}
local function discover(fn)
    if visited[fn] then return end
    visited[fn] = true
    for i = 1, math.huge do
        local name, value = debug.getupvalue(fn, i)
        if not name then break end
        UP[name] = {fn, i}
        if type(value) == "function" and name ~= "_ENV" then
            H[name] = value
            discover(value)
        end
    end
end
for _, fn in pairs(metrics) do if type(fn) == "function" then discover(fn) end end
function state(name)
    local slot = assert(UP[name], name)
    local _, value = debug.getupvalue(slot[1], slot[2])
    return value
end

STRINGS, LISTS, CALLS = {}, {}, {}
HOOK = nil
local function redis_call(_, method, ...)
    local args = {...}
    CALLS[#CALLS + 1] = {method, ...}
    if HOOK then
        local handled, value, err = HOOK(method, ...)
        if handled then return value, err end
    end
    local key = args[1]
    if method == "del" then STRINGS[key], LISTS[key] = nil, nil return 1 end
    if method == "get" then return STRINGS[key] or NULL end
    if method == "rpush" then
        local list = LISTS[key] or {}
        LISTS[key] = list
        for i = 2, #args do list[#list + 1] = args[i] end
        return #list
    end
    if method == "ltrim" then
        local list, out = LISTS[key] or {}, {}
        local first = args[2] < 0 and #list + args[2] + 1 or args[2] + 1
        for i = first, #list do out[#out + 1] = list[i] end
        LISTS[key] = out
        return "OK"
    end
    if method == "exists" then
        local n = 0
        for _, k in ipairs(args) do if STRINGS[k] or LISTS[k] then n = n + 1 end end
        return n
    end
    if method == "llen" then return #(LISTS[key] or {}) end
    if method == "expire" or method == "persist" then return 1 end
    error("unexpected Redis method " .. method)
end
SELF = {
    variables = {}, use_redis = true,
    redis_call = redis_call,
    clusterstore = {call = redis_call},
    metrics_datastore = {get = function(_, key) return SHM and SHM[key] end},
    log_throttled = function(_, level, key, msg) LOGS[#LOGS + 1] = {level, key, msg} end,
}
"""


def run(body, **env):
    return run_core(MODULE, PRELUDE + body, **env)


@pytest.mark.parametrize("hostname,expected", [("node_1.example", "node_1.example"), ("", "unknown"), (False, "unknown"), ("bad:host", "~hashed-host")])
def test_instance_keys_are_stable_and_hostname_safe(hostname, expected):
    out = run(
        """
local first = H.metric_redis_key("hits_counter_x", "3")
local second = H.metric_redis_key("other", "4")
emit({first = first, second = second, reads = HOST_READS, closed = HOST_CLOSED or false})
""",
        HOSTNAME=hostname,
    )
    assert out == {"first": f"metrics:hits_counter_x:3@{expected}", "second": f"metrics:other:4@{expected}", "reads": 1, "closed": hostname is not False}


def test_lru_allocation_failure_is_diagnosed():
    out = run("emit(LOGS)", LRU_FAIL=True)
    assert out == [["ERR", "failed to instantiate LRU cache : allocation failed"]]


@pytest.mark.parametrize(
    "value,expected",
    [(None, None), ("", None), ("bad", None), ("-1", None), ("1.5k", None), ("0", 0), (19, 19), ("2k", 2000), ("3K", 3000), ("4m", 4000000), ("5M", 5000000)],
)
def test_count_caps_accept_only_nonnegative_integer_shorthand(value, expected):
    assert run("emit({value = H.parse_count(VALUE)})", VALUE=value).get("value") == expected


def test_request_facets_normalize_absent_null_empty_and_scalar_values():
    assert run("""
local request = {empty = "", null = NULL, status = 403, flag = false}
emit({H.get_request_facet_value(request, "missing"), H.get_request_facet_value(request, "empty"),
      H.get_request_facet_value(request, "null"), H.get_request_facet_value(request, "status"), H.get_request_facet_value(request, "flag")})
""") == ["N/A", "N/A", "N/A", "403", "false"]


@pytest.mark.parametrize("cluster", [False, True])
def test_cap_eval_uses_all_report_keys_and_invalid_caps_do_not_wipe(cluster):
    out = run(
        """
SELF.variables.METRICS_MAX_BLOCKED_REQUESTS_REDIS = "bad"
H.enforce_redis_requests_cap(SELF)
assert(#CALLS == 0)
HOOK = function(method, script, count, ...)
    assert(method == "eval")
    local args = {...}
    assert(count == 12 and #args == 13)
    assert(args[13] == "2000")
    return true, false, "denied"
end
SELF.variables.METRICS_MAX_BLOCKED_REQUESTS_REDIS = "2k"
H.enforce_redis_requests_cap(SELF)
emit({keys = {table.unpack(CALLS[1], 4, 15)}, log = LOGS[1]})
""",
        CLUSTER=cluster,
    )
    base = "{requests}" if cluster else "requests"
    assert out["keys"] == [base, base + ":facets:initialized", base + ":facets:rebuilding", base + ":facets:oomprobe"] + [
        base + ":facet:" + f for f in ["ip", "country", "method", "url", "status", "reason", "server_name", "security_mode"]
    ]
    assert out["log"] == ["ERR", "cap_enforce", "Can't enforce Redis requests cap: denied"]


@pytest.mark.parametrize(
    "health,error,expected", [(1, None, []), (0, None, []), (0, "health denied", ["facet_check"]), (0, "rebuild denied", ["facet_rebuild"])]
)
def test_facet_health_rebuilds_only_after_definite_unhealthy_reply(health, error, expected):
    out = run(
        """
local evaluations = 0
HOOK = function(method, script, count, ...)
    evaluations = evaluations + 1
    if evaluations == 1 then return true, HEALTH, ERROR == "health denied" and ERROR or nil end
    assert(count == 12 and select(13, ...) == "3")
    return true, 0, ERROR
end
H.self_heal_request_facets(SELF)
local logs = {}
for _, log in ipairs(LOGS) do logs[#logs + 1] = log[2] end
emit({evaluations = evaluations, logs = setmetatable(logs, json.array_mt)})
""",
        HEALTH=health,
        ERROR=error,
    )
    assert out == {"evaluations": 1 if health == 1 or error == "health denied" else 2, "logs": expected}


def test_wipe_recovery_ceiling_resets_only_after_a_live_list():
    assert run("""
for _ = 1, 12 do H.reclaim_wiped_requests(SELF, {{synced = true}}) end
local rows = {{synced = true}, {synced = false}}
H.reclaim_wiped_requests(SELF, rows)
assert(rows[1].synced and LOGS[#LOGS][2] == "requests_reclaim_giveup")
HOOK = function() return true, false, "unreadable" end
H.reclaim_wiped_requests(SELF, rows)
assert(rows[1].synced)
LISTS.requests = {"alive"}
HOOK = nil
H.reclaim_wiped_requests(SELF, rows)
LISTS.requests = nil
H.reclaim_wiped_requests(SELF, rows)
emit({rows[1].synced, rows[2].synced, LOGS[#LOGS][2]})
""") == [False, False, "requests_reclaim"]


def test_zero_report_cap_disables_wipe_refill():
    assert run("""
SELF.variables.METRICS_MAX_BLOCKED_REQUESTS_REDIS = "0"
local requests = {{synced = true}}
H.reclaim_wiped_requests(SELF, requests)
emit({requests[1].synced, #CALLS})
""") == [True, 0]


def test_table_sync_preserves_fifo_on_append_trim_and_array_replacement():
    assert run("""
local a, b, c = {v = 1}, {v = 2}, {v = 3}
local rows = {a, b}
assert(H.sync_table(SELF, "events", "events-key", rows))
local before = #CALLS
assert(H.sync_table(SELF, "events", "events-key", rows))
assert(#CALLS == before)
rows[#rows + 1] = c
assert(H.sync_table(SELF, "events", "events-key", rows))
assert(#LISTS["events-key"] == 3 and json.decode(LISTS["events-key"][3]).v == 3)
table.remove(rows, 1)
assert(H.sync_table(SELF, "events", "events-key", rows))
assert(#LISTS["events-key"] == 2 and json.decode(LISTS["events-key"][1]).v == 2)
assert(H.sync_table(SELF, "events", "events-key", {9, false}))
emit(LISTS["events-key"])
""") == ["9", "false"]


@pytest.mark.parametrize("method,message", [("del", "clear"), ("rpush", "push"), ("ltrim", "trim")])
def test_failed_table_sync_returns_error_and_next_tick_rewrites(method, message):
    out = run(
        """
local rows = {{v = 1}, {v = 2}}
assert(H.sync_table(SELF, "events", "events-key", rows))
table.remove(rows, 1)
rows[#rows + 1] = {v = 3}
if METHOD ~= "ltrim" then rows = {{v = 9}} end
HOOK = function(method) if method == METHOD then return true, false, "denied" end end
local ok, err = H.sync_table(SELF, "events", "events-key", rows)
assert(not ok and state("synced_tables").events == nil)
HOOK = nil
assert(H.sync_table(SELF, "events", "events-key", rows))
local result = {}
for _, row in ipairs(LISTS["events-key"]) do result[#result + 1] = json.decode(row).v end
emit({err = err, rows = result})
""",
        METHOD=method,
    )
    assert out == {
        "err": f"can't {message} metric table events {'to' if method == 'rpush' else 'in'} Redis: denied",
        "rows": [2, 3] if method == "ltrim" else [9],
    }


def test_table_batches_stay_bounded_and_replayed_push_is_rewritten():
    assert run("""
local rows = {}
for i = 1, 501 do rows[i] = {v = i} end
assert(H.sync_table(SELF, "events", "events-key", rows))
assert(#CALLS == 3 and #CALLS[2] == 502 and #CALLS[3] == 3)
local replay = true
HOOK = function(method)
    if method == "rpush" and replay then replay = false return true, 999 end
end
rows[#rows + 1] = {v = 502}
assert(H.sync_table(SELF, "events", "events-key", rows))
assert(#LISTS["events-key"] == 502)
-- A replay during a full rewrite must leave it unsynced until a fresh tick.
rows = {{v = 7}}
replay = true
assert(H.sync_table(SELF, "events", "events-key", rows))
assert(state("synced_tables").events == nil)
HOOK = nil
assert(H.sync_table(SELF, "events", "events-key", rows))
emit({#LISTS["events-key"], json.decode(LISTS["events-key"][1]).v})
""") == [1, 7]


def test_counter_creation_and_restore_merge_live_increments_and_reject_evicted_record():
    assert run("""
SHM = {hits_counter_x_3 = "10"}
local counter = H.new_counter(SELF, "hits_counter_x")
assert(counter.value == 10 and counter.baseline == 10 and not counter.restored)
LRU:set("hits_counter_x", counter)
HOOK = function(method)
    assert(method == "get")
    counter.increments = counter.increments + 4
    return true, "20"
end
assert(H.restore_counter(SELF, "hits_counter_x", counter, "3"))
assert(counter.value == 24 and counter.restored)
local n = #CALLS
assert(H.restore_counter(SELF, "hits_counter_x", counter, "3") and #CALLS == n)
counter.restored = false
HOOK = function() LRU:delete("hits_counter_x") return true, "100" end
assert(not H.restore_counter(SELF, "hits_counter_x", counter, "3"))
SELF.use_redis = false
local local_counter = H.new_counter(SELF, "absent_counter_x")
emit({counter.value, local_counter.value, local_counter.restored})
""") == [24, 0, True]


@pytest.mark.parametrize(
    "stored,expected,restored,log",
    [
        (False, 3, False, "counter_restore"),
        (None, 3, False, "counter_restore"),
        ("invalid", 13, True, "counter_discard"),
        ("null", 13, True, None),
        ("5", 13, True, None),
    ],
)
def test_counter_restore_does_not_lose_local_baseline(stored, expected, restored, log):
    out = run(
        """
local counter = {value = 3, baseline = 10, increments = 3, restored = false}
LRU:set("hits_counter_x", counter)
HOOK = function() return true, STORED == "null" and NULL or STORED, "denied" end
local ok = H.restore_counter(SELF, "hits_counter_x", counter, "3")
emit({ok = ok, value = counter.value, restored = counter.restored, log = LOGS[1] and LOGS[1][2]})
""",
        STORED=stored,
    )
    assert out == {"ok": restored, "value": expected, "restored": restored, **({"log": log} if log else {})}


@pytest.mark.parametrize("cluster", [False, True])
def test_prefill_preserves_active_records_and_skips_invalid_values(cluster):
    assert (
        run(
            """
CAPACITY = 4
local keys = {"metrics:p_counter_a:3@node-1", "metrics:p_counter_b:3@node-1", "metrics:p_counter_bad:3@node-1", "metrics:p_counter_missing:3@node-1"}
local values = {"12", "22", "invalid", NULL}
SELF.clusterstore.scan_primaries = function(_, pattern, budget)
    assert(pattern == "metrics:*_counter_*:3@node-1" and budget == 4)
    return keys
end
local function race() LRU:set("p_counter_b", {value = 7, restored = false}) end
HOOK = function(method, key)
    if method == "scan" then return true, {"0", keys} end
    if method == "mget" then race() return true, values end
    if method == "get" then
        if key == keys[2] then race() end
        for i, k in ipairs(keys) do if k == key then return true, values[i] end end
    end
end
assert(H.prefill_counters(SELF, "3"))
emit({a = LRU:get("p_counter_a"), b = LRU:get("p_counter_b"), bad = LRU:get("p_counter_bad"), missing = LRU:get("p_counter_missing")})
""",
            CLUSTER=cluster,
        )
        == {"a": {"value": 12, "baseline": 12, "increments": 0, "restored": True}, "b": {"value": 7, "restored": False}}
    )


@pytest.mark.parametrize("failure", ["scan", "shape", "mget", "cluster_scan", "cluster_get"])
def test_prefill_failure_stays_retryable(failure):
    assert (
        run(
            """
CLUSTER = FAILURE:find("cluster", 1, true) ~= nil
SELF.clusterstore.scan_primaries = function()
    if FAILURE == "cluster_scan" then return nil end
    return {"metrics:p_counter_x:3@node-1"}
end
HOOK = function(method)
    if method == "scan" then
        if FAILURE == "scan" then return true, false end
        if FAILURE == "shape" then return true, {0, {}} end
        return true, {"0", {"metrics:p_counter_x:3@node-1"}}
    end
    return true, false
end
emit({done = H.prefill_counters(SELF, "3"), keys = #LRU:get_keys()})
""",
            FAILURE=failure,
        )
        == {"done": False, "keys": 0}
    )


def test_prefill_bounds_empty_scan_pages_and_respects_capacity_after_yield():
    assert run("""
CAPACITY = 150
HOOK = function() return true, {"17", {}} end
assert(H.prefill_counters(SELF, "3"))
assert(#CALLS == 2)
CAPACITY = 1
HOOK = function(method)
    if method == "scan" then return true, {"0", {"metrics:p_counter_a:3@node-1", "metrics:p_counter_b:3@node-1"}} end
    return true, {"2", "3"}
end
assert(H.prefill_counters(SELF, "3"))
assert(#LRU:get_keys() == 1 and LRU:get("p_counter_a").value == 2)
CLUSTER = true
local n = #CALLS
assert(H.prefill_counters(SELF, "3") and #CALLS == n)
emit(true)
""") is True


@pytest.mark.parametrize("ttl,method", [(0, "persist"), (30, "expire")])
def test_legacy_counter_sweep_preserves_history_with_requested_retention(ttl, method):
    out = run(
        """
HOOK = function(method, cursor, match, pattern, count, size)
    if method == "scan" then
        assert(cursor == "0" and match == "MATCH" and pattern == "metrics:*_counter_*:3" and count == "COUNT" and size == 1000)
        return true, {"0", {"metrics:p_counter_x:3"}}
    end
    return true, 1
end
local done, failed = H.refresh_legacy_counters(SELF, "3", TTL)
emit({done = done, failed = failed or false, operation = CALLS[2]})
""",
        TTL=ttl,
    )
    assert out == {"done": True, "failed": False, "operation": [method, "metrics:p_counter_x:3"] + ([ttl] if ttl else [])}


def test_legacy_sweep_keeps_cursor_at_bounded_tick_and_reports_failures():
    assert run("""
HOOK = function(method, cursor)
    assert(method == "scan")
    return true, {tostring(tonumber(cursor) + 1), {}}
end
assert(not H.refresh_legacy_counters(SELF, "3", 30))
assert(#CALLS == 10 and state("legacy_cursor") == "10")
HOOK = function(method, cursor)
    if method == "scan" then assert(cursor == "10") return true, {"0", {"old"}} end
    return true, false
end
local done, failed = H.refresh_legacy_counters(SELF, "3", 30)
assert(not done and failed)
HOOK = function() return true, {"0", "bad"} end
done, failed = H.refresh_legacy_counters(SELF, "3", 30)
assert(not done and failed)
CLUSTER = true
local n = #CALLS
assert(H.refresh_legacy_counters(SELF, "3", 30) and #CALLS == n)
emit(true)
""") is True


@pytest.mark.parametrize("cluster", [False, True])
@pytest.mark.parametrize("reply,cleared", [(0, True), (False, False), (1, False)])
def test_missing_synced_keys_force_rewrite_but_errors_preserve_state(cluster, reply, cleared):
    out = run(
        """
local rows = {{v = 1}}
assert(H.sync_table(SELF, "events", "events-key", rows))
assert(H.sync_table(SELF, "empty", "empty-key", {}))
state("synced_counters").p_counter_x = 8
HOOK = function(method, ...)
    assert(method == "exists")
    if CLUSTER then assert(select("#", ...) == 1) end
    return true, REPLY == 1 and select("#", ...) or REPLY
end
H.check_synced_keys(SELF, "3")
emit({table = state("synced_tables").events ~= nil, counter = state("synced_counters").p_counter_x ~= nil})
""",
        CLUSTER=cluster,
        REPLY=reply,
    )
    assert out == {"table": not cleared, "counter": not cleared}


def test_synced_key_checks_batch_below_unpack_limit():
    assert run("""
for i = 1, 501 do state("synced_counters")["p_counter_" .. i] = i end
HOOK = function(method, ...) assert(method == "exists") return true, select("#", ...) end
H.check_synced_keys(SELF, "3")
emit({#CALLS, #CALLS[1] - 1, #CALLS[2] - 1})
""") == [2, 500, 1]


def test_eviction_reaps_table_keys_but_keeps_authoritative_counters_and_logs_errors():
    assert run("""
state("synced_redis_keys").p_table_x = true
state("synced_redis_keys").p_counter_x = true
state("synced_redis_keys").live = true
state("synced_tables").p_table_x = {len = 1}
state("synced_counters").p_counter_x = 8
HOOK = function(method) assert(method == "del") return true, false, "denied" end
H.reap_evicted_redis_keys(SELF, "3", {live = true})
assert(state("synced_tables").p_table_x == nil and state("synced_counters").p_counter_x == nil)
assert(state("synced_redis_keys").live and not state("synced_redis_keys").p_table_x)
emit({#CALLS, CALLS[1][2], LOGS[1][2], LOGS[1][3]})
""") == [1, "metrics:p_table_x:3@node-1", "reap_evicted", "Can't delete evicted metric p_table_x from Redis: denied"]


def test_request_ttl_persist_retries_whole_pass_then_latches_success():
    assert run("""
LRU:set("setup", true)
LRU:set("requests", {})
LRU:set("p_counter_x", 2)
SELF.variables.METRICS_SAVE_TO_REDIS = "yes"
local failure = true
HOOK = function(method, key)
    assert(method == "persist")
    if failure and key == "requests:facet:ip" then return true, false, "denied" end
    return true, 0
end
H.refresh_request_ttls(SELF, 0, "3")
assert(#CALLS == 11 and LOGS[1][2] == "requests_ttl")
failure = false
H.refresh_request_ttls(SELF, 0, "3")
assert(#CALLS == 22)
H.refresh_request_ttls(SELF, 0, "3")
emit({#CALLS, CALLS[11]})
""") == [22, ["persist", "metrics:p_counter_x:3@node-1"]]


def test_expired_metric_keys_drop_synced_state_and_refresh_runs_every_tick():
    assert run("""
LRU:set("p_table_x", {{v = 1}})
LRU:set("p_counter_x", 2)
SELF.variables.METRICS_SAVE_TO_REDIS = "yes"
state("synced_tables").p_table_x = {len = 1}
state("synced_counters").p_counter_x = 2
HOOK = function(method, key, ttl) assert(method == "expire" and ttl == 30) return true, 0 end
H.refresh_request_ttls(SELF, 30, "3")
assert(not state("synced_tables").p_table_x and not state("synced_counters").p_counter_x)
H.refresh_request_ttls(SELF, 30, "3")
emit(#CALLS)
""") == 24
