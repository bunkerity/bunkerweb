"""Metrics must recover from Redis losing data it believed it held: wiped report lists, evicted counters, cold counters.

Buffered reports stayed latched as synced after Redis lost the whole requests list, so reports never came back in the UI;
locally evicted counters stayed in Redis forever (unbounded key growth); and a counter restarted at zero overwrote the value
Redis had kept. This test loads the real ``metrics.lua`` with its module-local helpers exposed and drives them against
recording Redis stand-ins.
Refs: #3758, #3775.
"""

import re

import pytest
from _lua_state_helpers import BASE_LUA  # type: ignore
from _t2_helpers import CORE, LUA, run_script

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

SOURCE = (CORE / "metrics" / "metrics.lua").read_text()
# Expose the module-local helpers; the file's behaviour is untouched.
EXPOSED = re.sub(
    r"\nreturn metrics\s*$",
    "\nreturn metrics, { reclaim = reclaim_wiped_requests, reap = reap_evicted_redis_keys, restore = restore_counter,"
    " set_lru = function(l) lru = l end, synced = function(v) synced_redis_keys = v end }\n",
    SOURCE,
)

LOADER = r"""
unpack = unpack or table.unpack
local NULL = setmetatable({}, { __tostring = function() return "ngx.null" end })
ngx = { ERR = "ERR", WARN = "WARN", HTTP_OK = 200, status = 403, null = NULL, shared = {}, var = {}, config = { subsystem = "http" },
        worker = { id = function() return 0 end }, unescape_uri = function(v) return v end }
package.loaded["cjson"] = json
package.loaded["middleclass"] = function() return {} end
package.loaded["bunkerweb.datastore"] = {}
package.loaded["bunkerweb.plugin"] = {}
package.loaded["bunkerweb.rediskeys"] = { cluster_mode = function() return false end, escape = function(k) return k end,
    reports = function() return { "requests", "requests:facets:initialized", "requests:facets:rebuilding", "requests:facets:oomprobe" } end }
package.loaded["bunkerweb.utils"] = { get_reason = function() return "x", {}, "block" end, has_variable = function() return true end, parse_duration = function() return nil end }
LRU = nil
package.loaded["resty.lrucache"] = { new = function(capacity)
    local values = {}
    LRU = { capacity = function() return capacity end, get_keys = function() local ks = {} for k in pairs(values) do ks[#ks + 1] = k end return ks end,
            get = function(_, k) return values[k] end, set = function(_, k, v) values[k] = v end, delete = function(_, k) values[k] = nil end }
    return LRU
end }
local metrics, exposed = assert(load(SOURCE, "metrics.lua"))()
local function instance(calls, replies)
    local self = { variables = {}, logger = { log = function() end } }
    self.log_throttled = function(_, level, key, msg) LOGS[#LOGS + 1] = level .. ":" .. key .. ":" .. msg end
    self.redis_call = function(_, method, ...)
        calls[#calls + 1] = { method, ... }
        local reply = replies[method]
        if type(reply) == "function" then return reply(...) end
        return reply
    end
    return self
end
LOGS = {}
"""


def run(body):
    header = f"SOURCE = {lua_str_text(EXPOSED)}\n"
    return run_script(BASE_LUA + "\n" + header + LOADER + body)


def lua_str_text(text):
    return "[=====[" + text + "]=====]"


def reclaim(llen_reply, rows, variables="{}"):
    return run(f"""
local calls = {{}}
local self = instance(calls, {{ llen = {llen_reply} }})
self.variables = {variables}
local requests = {{}}
for i, synced in ipairs({{ {rows} }}) do requests[i] = {{ id = "r" .. i, synced = synced }} end
exposed.reclaim(self, requests)
local flags = {{}}
for i, r in ipairs(requests) do flags[i] = r.synced end
emit({{ flags = flags, logged = #LOGS }})
""")


def test_a_wiped_requests_list_unlatches_the_buffered_reports_so_they_sync_again():
    out = reclaim(0, "true, true, false")
    assert out["flags"] == [False, False, False]
    assert out["logged"] == 1


def test_a_live_list_leaves_synced_reports_alone():
    assert reclaim(5, "true, true")["flags"] == [True, True]


def test_an_unreadable_reply_proves_nothing_and_changes_nothing():
    assert reclaim("false", "true")["flags"] == [True]


def test_a_zero_redis_cap_means_no_reports_in_redis_and_no_refill():
    assert reclaim(0, "true", '{ METRICS_MAX_BLOCKED_REQUESTS_REDIS = "0" }')["flags"] == [True]


def test_the_refill_gives_up_after_repeated_wipes():
    out = run("""
local calls = {}
local self = instance(calls, { llen = 0 })
local flags = {}
for _ = 1, 20 do
    local requests = { { id = "r", synced = true } }
    exposed.reclaim(self, requests)
    flags[#flags + 1] = requests[1].synced
end
local reclaimed = 0
for _, f in ipairs(flags) do if f == false then reclaimed = reclaimed + 1 end end
emit({ reclaimed = reclaimed })
""")
    assert out["reclaimed"] == 12


def test_a_locally_evicted_table_metric_is_deleted_from_redis_but_a_counter_is_kept():
    out = run("""
local calls = {}
local self = instance(calls, { del = 1 })
exposed.synced({ requests_table = true, hits_counter_a = true, kept = true })
exposed.reap(self, "0", { kept = true })
local deleted = {}
for _, c in ipairs(calls) do deleted[#deleted + 1] = c[2] end
emit({ deleted = deleted, n = #calls })
""")
    assert out["n"] == 1
    assert out["deleted"][0].startswith("metrics:requests_table:0")


@pytest.mark.parametrize(
    "stored, increments, expected, restored",
    [("42", 3, 45, True), ("7", 0, 7, True), ("nil", 2, 2, True), (None, 1, 1, False)],
)
def test_a_cold_counter_resumes_from_the_value_redis_kept_instead_of_overwriting_it_with_zero(stored, increments, expected, restored):
    reply = "false" if stored is None else lua_str_text(stored)
    out = run(f"""
local calls = {{}}
local self = instance(calls, {{ get = {reply} }})
local counter = {{ value = {increments}, baseline = 0, increments = {increments}, restored = false }}
LRU:set("hits_counter", counter)
local done = exposed.restore(self, "hits_counter", counter, "0")
emit({{ value = counter.value, restored = counter.restored, done = done }})
""")
    assert out["value"] == expected
    assert out["restored"] is restored
