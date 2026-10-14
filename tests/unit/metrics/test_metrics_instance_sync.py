"""Execute the shipped timer with two worker-local LRUs sharing a Redis model."""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

SOURCE = Path(os.environ.get("METRICS_TEST_SOURCE", Path(__file__).resolve().parents[3] / "src/common/core/metrics/metrics.lua"))
LUA = shutil.which("lua") or shutil.which("luajit")
pytestmark = pytest.mark.skipif(LUA is None, reason="requires Lua")

PRELUDE = r"""
local metrics = {}
local ERR, WARN, INFO = 3, 4, 6
local subsystem = "http"
local stream_requests, stream_restore_pending = {}, false
local worker_id = function() return 0 end
local has_variable = function() return true end
local parse_count = tonumber
local encode = function(v)
  if type(v) == "table" then return v.id or "[]" end
  return tostring(v)
end
local decode = function() error("not JSON") end
local unpack = table.unpack or unpack
local math_min, table_remove = math.min, table.remove
local self_heal_request_facets = function() end
local enforce_redis_requests_cap = function() end
local sync_request_buffer = function() end
local persist_stream_reports = function() return true end
local restore_stream_reports = function() end
local refresh_request_ttls = function() end
local db, writes, calls, replay, oom = {}, 0, 0, false, false
local null = {}
local now, host = 0, "host-1"
local ngx_now = function() return now end
local ngx = {var = {hostname = "nginx-host"}, md5 = function(v) return "md5(" .. v .. ")" end}
local io = {open = function() return {read = function() return host end, close = function() end} end}
local instance_id
local synced_tables, synced_counters = {}, {}
local legacy_cursor, legacy_due, legacy_failures, legacy_done = "0", 0, 0, false
local REDIS_BATCH = 500
local lru
local script_calls, fail_trim, fail_origin, dropped_key = 0, false, false, false
local function command(method, key, ...)
  local args = {...}
  if method == "get" then return db[key] or null end
  if method == "exists" then return db[key] ~= nil and 1 or 0 end
  if method == "scan" then return {"0", {}} end
  if method == "ttl" then return db[key] and -1 or -2 end
  if method == "persist" or method == "expire" then return 1 end
  if method == "del" then db[key] = nil; return 1 end
  if method == "set" then db[key] = args[1]; return "OK" end
  if method == "llen" then return db[key] and #db[key] or 0 end
  if method == "lrange" then
    local out, list = {}, db[key] or {}
    local first, last = args[1], args[2]
    if first < 0 then first = #list + first end
    if last < 0 then last = #list + last end
    for i = first + 1, math.min(last + 1, #list) do out[#out+1] = list[i] end
    return out
  end
  if method == "ltrim" then
    if fail_trim then fail_trim = false; return false, "trim failed" end
    db[key] = command("lrange", key, args[1], args[2]); return "OK"
  end
  if method == "rpush" then
    db[key] = db[key] or {}
    for _, item in ipairs(args) do table.insert(db[key], item) end
    return #db[key]
  end
  if method == "eval" then
    script_calls = script_calls + 1
    local script, redis_key = key, args[2]
    local argv = {}
    for i = 3, #args do argv[#argv+1] = tostring(args[i]) end
    local env = {tonumber = tonumber, unpack = unpack, KEYS = {redis_key}, ARGV = argv,
      redis = {call = function(m, k, ...) return command(string.lower(m), k, ...) end}}
    local fn = assert(load(script, "redis-script", "t", env))
    if dropped_key then db[redis_key] = nil; dropped_key = false end
    local result = fn()
    if replay then replay = false; result = fn() end
    return result
  end
  error("unexpected command " .. method)
end
local function client()
  return {
    connect = function() return true end,
    close = function() end,
    call = function(_, method, key, ...)
      calls = calls + 1
      if method ~= "get" and method ~= "exists" and method ~= "scan" then writes = writes + 1 end
      if oom then return false, "OOM command not allowed" end
      local result = command(method, key, ...)
      if method == "rpush" and replay then
        replay = false; return command(method, key, ...)
      end
      return result
    end,
  }
end
local next_instance = 0
local function instance(counter, history, shm)
  next_instance = next_instance + 1
  local vals = {setup = true, errors_counter_403 = counter, example_history = history}
  local cache = {
    get = function(_, key) return vals[key] end,
    set = function(_, key, value) vals[key] = value end,
    get_keys = function()
      local keys = {}
      for key in pairs(vals) do keys[#keys+1] = key end
      return keys
    end,
  }
  shm = shm or {}
  local obj = setmetatable({
    host = "host-" .. next_instance, tables = {}, counters = {}, shm = shm,
    use_redis = true,
    clusterstore = client(),
    variables = {METRICS_SAVE_TO_REDIS = "yes", METRICS_REDIS_TTL = "0"},
    metrics_datastore = {
      keys = function() local keys = {}; for key in pairs(shm) do keys[#keys+1] = key end; return keys end,
      get = function(_, key) return shm[key], shm[key] == nil and "not found" or nil end,
      set = function(_, key, value)
        if fail_origin then return false, "no memory" end
        shm[key] = value; return true
      end,
      set_with_retries = function(_, key, value) shm[key] = value; return true end,
    },
    logger = {log = function() end},
    log_throttled = function() end,
    flush_log_recaps = function() end,
    ret = function(_, ok, msg) return {ret = ok, msg = msg} end,
    timer = function(self)
      host = self.host; instance_id = nil
      synced_tables, synced_counters = self.tables, self.counters
      return metrics.timer(self)
    end,
  }, {__index = metrics})
  return obj, cache
end
local is_oom_error = function(err) return err:find("OOM", 1, true) ~= nil end
local is_connection_error = function() return false end
local is_protocol_error = function() return false end
"""


def run(body):
    assert LUA is not None
    source = SOURCE.read_text()
    methods = []
    for name in ("APPEND_METRIC_SCRIPT", "LEGACY_TTL_SCRIPT"):
        match = re.search(rf"^local {name} = \[==\[.*?\]==\]", source, re.M | re.S)
        if match:
            methods.append(match.group())
    for name in ("get_instance_id", "metric_redis_key", "refresh_legacy_counters", "sync_table", "sync_counter", "check_synced_keys"):
        match = re.search(rf"^local function {name}\(.*?^end$", source, re.M | re.S)
        if match:
            methods.append(match.group())
    for name in ("redis_call", "timer"):
        match = re.search(rf"^function metrics:{name}\(.*?^end$", source, re.M | re.S)
        assert match, name
        methods.append(match.group())
    result = subprocess.run([LUA, "-"], input=PRELUDE + "\n".join(methods) + body, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_two_instances_do_not_overwrite_worker_zero():
    run("""
local a, ca = instance(3, {{id="a"}})
local b, cb = instance(7, {{id="b"}})
lru = ca; assert(a:timer().ret)
lru = cb; assert(b:timer().ret)
local total = 0
for key, value in pairs(db) do
  if key:match("^metrics:errors_counter_403:") then total = total + value end
end
assert(total == 10, "shared Redis lost an instance counter: " .. total)
""")


def test_unchanged_history_needs_no_second_write():
    run("""
local a, cache = instance(3, {{id="a"}, {id="b"}})
lru = cache; assert(a:timer().ret)
writes = 0; assert(a:timer().ret)
assert(writes == 0, "unchanged metrics rewritten: " .. writes)
""")


def test_replayed_push_does_not_publish_duplicate_history():
    run("""
local a, cache = instance(3, {{id="a"}, {id="b"}})
lru = cache; replay = true; assert(a:timer().ret)
for key, value in pairs(db) do
  if key:match("^metrics:example_history:") then
    assert(#value == 2 and value[1] == "a" and value[2] == "b",
      "replayed RPUSH published duplicate history: " .. #value)
  end
end
""")


def test_oom_stops_writes_for_the_cycle():
    run("""
local a, cache = instance(3, {{id="a"}, {id="b"}})
lru = cache; oom = true; a:timer()
assert(calls == 1, "OOM must trip the cycle breaker: " .. calls)
""")


def test_append_and_head_trim_are_incremental_and_replay_safe():
    run("""
local history = {{id="a"}, {id="b"}}
local a, cache = instance(3, history)
lru = cache; a:timer()
table.remove(history, 1); table.insert(history, {id="c"})
replay = true; script_calls = 0; writes = 0; a:timer()
assert(script_calls == 1 and writes == 2, "must append once and trim once")
local value = db["metrics:example_history:0@host-1~http"]
assert(#value == 2 and value[1] == "b" and value[2] == "c")
""")


def test_lost_individual_keys_are_restored_without_a_marker():
    run("""
local a, cache = instance(3, {{id="a"}, {id="b"}})
lru = cache; a:timer()
db["metrics:example_history:0@host-1~http"] = nil
db["metrics:errors_counter_403:0@host-1~http"] = nil
a:timer()
assert(db["metrics:errors_counter_403:0@host-1~http"] == 3)
assert(#db["metrics:example_history:0@host-1~http"] == 2)
""")


def test_lost_list_during_incremental_append_gets_one_full_fallback():
    run("""
local history = {{id="a"}, {id="b"}}
local a, cache = instance(3, history)
lru = cache; a:timer()
table.insert(history, {id="c"}); dropped_key = true; script_calls = 0
a:timer()
assert(script_calls == 2, "one failed increment and one full append")
local value = db["metrics:example_history:0@host-1~http"]
assert(table.concat(value, ",") == "a,b,c")
""")


def test_failed_trim_rebuilds_instead_of_adopting_wrong_history():
    run("""
local history = {{id="a"}, {id="b"}}
local a, cache = instance(3, history)
lru = cache; a:timer()
table.remove(history, 1); table.insert(history, {id="c"})
fail_trim = true; a:timer(); a:timer()
assert(table.concat(db["metrics:example_history:0@host-1~http"], ",") == "b,c")
""")


def test_large_history_chunks_do_not_duplicate_on_replay():
    run("""
local history = {}
for i=1,1200 do history[i] = {id=tostring(i)} end
local a, cache = instance(3, history)
lru = cache; replay = true; a:timer()
local value = db["metrics:example_history:0@host-1~http"]
assert(#value == 1200)
for i=1,1200 do assert(value[i] == tostring(i)) end
""")


def test_upgrade_and_reload_do_not_count_frozen_legacy_twice():
    run("""
db["metrics:errors_counter_403:0"] = 50
local shm = {errors_counter_403_0 = 50}
local a, cache = instance(53, {{id="a"}}, shm)
lru = cache; a:timer()
local key = "metrics:errors_counter_403:0@host-1~http"
assert(db[key] == 3 and db["metrics:errors_counter_403:0"] == 50)
assert(shm.errors_counter_403_0 == 53, "local API total must stay intact")
local b, cb = instance(55, {{id="b"}}, shm)
b.host = a.host; lru = cb; b:timer()
assert(db[key] == 5, "reload must preserve the counter origin")
""")


def test_redis_baseline_survives_a_restart_with_empty_shm():
    run("""
db["metrics:errors_counter_403:0@host-1~http"] = 70
local a, cache = instance(3, {{id="a"}})
lru = cache; a:timer()
assert(db["metrics:errors_counter_403:0@host-1~http"] == 73)
""")


def test_origin_write_failure_cannot_publish_an_uncertain_counter():
    run("""
local a, cache = instance(3, {{id="a"}})
lru = cache; fail_origin = true; a:timer()
assert(db["metrics:errors_counter_403:0@host-1~http"] == nil)
fail_origin = false; a:timer()
assert(db["metrics:errors_counter_403:0@host-1~http"] == 3)
""")


def test_oom_recovery_keeps_buffered_metrics():
    run("""
local a, cache = instance(3, {{id="a"}, {id="b"}})
lru = cache; oom = true; a:timer()
oom = false; a:timer()
assert(db["metrics:errors_counter_403:0@host-1~http"] == 3)
assert(table.concat(db["metrics:example_history:0@host-1~http"], ",") == "a,b")
""")


def test_stream_and_http_worker_zero_use_distinct_keys():
    run("""
instance_id = "same-host"
subsystem = "http"; local a = metric_redis_key("errors_counter_403", "0")
subsystem = "stream"; local b = metric_redis_key("errors_counter_403", "0")
assert(a ~= b)
""")


def test_hostname_fallback_and_unsafe_names_do_not_share_unknown():
    run("""
host = ""; ngx.var.hostname = "fallback-host"; os.getenv = function() return nil end
assert(get_instance_id() == "fallback-host")
instance_id = nil; host = "bad@host"; assert(get_instance_id() == "~md5(bad@host)")
instance_id = nil; host = nil; ngx.var.hostname = ""; assert(get_instance_id() == nil)
assert(metric_redis_key("errors_counter_403", "0") == nil)
""")


def test_legacy_scan_is_bounded_resumes_and_stops_at_cursor_zero():
    run("""
local a, cache = instance(3, {{id="a"}})
local pages, mutations = 0, 0
a.redis_call = function(_, method, cursor, ...)
  if method == "scan" then
    pages = pages + 1
    assert(cursor == tostring(pages-1))
    return {pages == 12 and "0" or tostring(pages), {"metrics:errors_counter_403:0", "metrics:errors_counter_403:0@foreign"}}
  end
  assert(method == "eval")
  mutations = mutations + 1; return 0
end
refresh_legacy_counters(a, "0", 60); assert(pages == 10)
refresh_legacy_counters(a, "0", 60); assert(pages == 12 and mutations == 12)
refresh_legacy_counters(a, "0", 60); assert(pages == 12)
""")


def test_legacy_scan_failure_backs_off_and_later_recovers():
    run("""
local a = instance(3, {{id="a"}})
local scans = 0
a.redis_call = function()
  scans = scans + 1
  if scans == 1 then return false, "permission denied" end
  return {"0", {}}
end
refresh_legacy_counters(a, "0", 60)
refresh_legacy_counters(a, "0", 60); assert(scans == 1)
now = 60; refresh_legacy_counters(a, "0", 60); assert(scans == 2)
""")


@pytest.mark.parametrize(("existing", "requested", "expected"), [(-1, 60, 60), (20, 60, 20), (20, 0, -1), (-2, 60, -2)])
def test_legacy_expiry_does_not_renew_frozen_history(existing, requested, expected):
    run(f"""
local ttl = {existing}
local env = {{tonumber=tonumber, KEYS={{"legacy"}}, ARGV={{"{requested}"}}, redis={{call=function(method, key, value)
  if method == "TTL" then return ttl end
  if method == "EXPIRE" then ttl=value; return 1 end
  if method == "PERSIST" then if ttl ~= -2 then ttl=-1 end; return 1 end
  error(method)
end}}}}
assert(load(LEGACY_TTL_SCRIPT, "expiry", "t", env))()
assert(ttl == {expected})
""")


def test_first_tick_does_not_overwrite_a_live_counter_with_old_shm():
    run("""
local a, cache = instance(53, {{id="a"}}, {errors_counter_403_0=50})
cache:set("setup", nil)
lru = cache; a:timer()
assert(a.shm.errors_counter_403_0 == 53, "first-tick restore lost fresh increments")
assert(db["metrics:errors_counter_403:0@host-1~http"] == 53)
""")


def test_repeated_values_do_not_lose_history_on_head_trim():
    run("""
local history = {{id="a"}, {id="b"}, {id="a"}}
local a, cache = instance(3, history)
lru = cache; a:timer()
table.remove(history, 1); table.insert(history, {id="b"}); a:timer()
assert(table.concat(db["metrics:example_history:0@host-1~http"], ",") == "b,a,b")
""")


def test_lru_eviction_deletes_only_this_instances_previous_keys():
    run("""
local a, cache = instance(3, {{id="a"}})
lru = cache; a:timer()
local foreign = "metrics:errors_counter_403:0@other~http"
db[foreign] = 7
cache:set("errors_counter_403", nil); cache:set("example_history", nil)
oom = true; a:timer(); oom = false; a:timer()
assert(db["metrics:errors_counter_403:0@host-1~http"] == nil)
assert(db["metrics:example_history:0@host-1~http"] == nil)
assert(db[foreign] == 7, "eviction must not delete a sibling instance")
""")
