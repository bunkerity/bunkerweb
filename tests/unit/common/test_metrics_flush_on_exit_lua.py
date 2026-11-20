"""A worker that exits on a reload flushes what ``metrics:log()`` still holds in its LRU.

``metrics:log()`` keeps blocked requests and counters in the worker LRU and the recurrent timer copies them to
the shared dict. On a reload the old workers' timer runs once with ``premature=true``, and
``init-worker-lua.conf`` used to return at once, so anything logged since the last tick never reached
``/metrics/requests``.

Real ``metrics.lua`` and the real ``init_worker_by_lua_block`` run here; OpenResty, the plugin loader and the
shared dict are stubs. A worker is one ``dofile`` of the module (one Lua VM per nginx worker means one set of
upvalues, LRU included), and two workers share one fake dict, which is how two generations of the same worker
id share one zone across a reload.
"""

import os
from pathlib import Path

import pytest
from _lua_core_helpers import BW_LUA, LUA, module_path, run_core

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")
ROOT = BW_LUA.parents[1]
# Mutation runs point these at a copy of the unfixed files.
MODULE = module_path("METRICS_FLUSH", ROOT / "common/core/metrics/metrics.lua")
CONF = Path(os.environ.get("BW_L14_CONF", str(ROOT / "common/confs/init-worker-lua.conf")))

PRELUDE = r"""
CUR_ID = 0
ngx.worker = { id = function() return CUR_ID end, pid = function() return CUR_PID or 4242 end }
ngx.now = function() return NOW end
ngx.status = 403
ngx.unescape_uri = function(v) return v end
ngx.md5 = function(v) return "md5" end
ngx.INFO, ngx.ERR, ngx.WARN, ngx.NOTICE = 7, 4, 5, 6
package.loaded["middleclass"] = function() return {} end
package.loaded["bunkerweb.plugin"] = {}
package.loaded["bunkerweb.rediskeys"] = {}
package.loaded["bunkerweb.logger"] = { new = function() return { log = function(_, level, msg) LOGS[#LOGS + 1] = { level, msg } end } end }
package.loaded["resty.lrucache"] = { new = function(capacity)
    local values = {}
    return {
        capacity = function() return capacity end,
        get_keys = function() local keys = {} for k in pairs(values) do keys[#keys + 1] = k end table.sort(keys) return keys end,
        get = function(_, k) return values[k] end,
        set = function(_, k, v) values[k] = v end,
        delete = function(_, k) values[k] = nil end,
    }
end }
VARS = { USE_METRICS = "yes" }
package.loaded["bunkerweb.utils"] = {
    has_variable = function(name, value) return VARS[name] == value end,
    get_variable = function(name) return VARS[name] end,
    get_reason = function(ctx) return ctx.reason, ctx.data, ctx.mode end,
    get_country = function() return "FR" end,
    is_connection_error = function() return false end,
    is_oom_error = function() return false end,
    parse_duration = function() return nil end,
}

-- The shared dict, and the datastore wrapper metrics.lua talks to.
local function new_dict()
    local d = { data = {}, sets = {}, ttls = {} }
    function d:get(k) return self.data[k] end
    function d:set(k, v) self.data[k] = v self.sets[k] = (self.sets[k] or 0) + 1 return true end
    function d:delete(k) self.data[k] = nil end
    function d:get_keys() local keys = {} for k in pairs(self.data) do keys[#keys + 1] = k end table.sort(keys) return keys end
    return d
end
local DS = {}
DS.__index = DS
function DS:get(k) local v = self.dict:get(k) if v == nil then return nil, "not found" end return v, nil end
function DS:set(k, v) self.dict:set(k, v) return true, "success" end
function DS:set_with_retries(k, v, ttl) self.dict:set(k, v) self.dict.ttls[k] = ttl return true, "success" end
function DS:delete(k) self.dict:delete(k) return true end
function DS:keys() return self.dict:get_keys(0) end
package.loaded["bunkerweb.datastore"] = { new = function(_, dict) return setmetatable({ dict = dict }, DS) end }
ngx.shared = { metrics_datastore = new_dict(), internalstore = new_dict() }
SHM = ngx.shared.metrics_datastore

-- One worker: a fresh load of the module, hence a fresh LRU and fresh upvalues.
local forbidden = setmetatable({}, { __index = function(_, k) error("Redis touched: " .. tostring(k)) end })
function new_worker(id, use_redis)
    local mod = dofile(MODULE)
    mod.ret = function(_, ok, msg) return { ret = ok, msg = msg } end
    mod.log_throttled = function() end
    mod.flush_log_recaps = function() end
    local w = { id = id, mod = mod }
    function w.obj(vars)
        local o = setmetatable({
            variables = vars or {}, use_redis = use_redis or false, metrics_datastore = setmetatable({ dict = SHM }, DS),
            ctx = { bw = { remote_addr = "1.2.3.4", request_method = "GET", request_uri = "/", http_user_agent = "ua", server_name = "a.test" } },
        }, { __index = mod })
        if use_redis then o.clusterstore, o.redis_call = forbidden, function() error("Redis touched") end end
        return o
    end
    function w.call(method, o, ...) CUR_ID = id return o[method](o, ...) end
    function w.block(o, request_id, metrics)
        o.ctx.reason, o.ctx.data, o.ctx.mode = "antibot", {}, "block"
        o.ctx.bw.request_id, o.ctx.bw.start_time, o.ctx.bw.metrics = request_id, NOW, metrics
        return w.call("log", o, true)
    end
    function w.init(o) return w.call("init_workers", o) end
    return w
end

function requests_in_dict()
    local ids = {}
    for _, key in ipairs(SHM:get_keys()) do
        if key:match("^requests_[0-9]+$") then
            for _, r in ipairs(json.decode(SHM:get(key))) do ids[#ids + 1] = r.id end
        end
    end
    table.sort(ids)
    return ids
end
function handoff_keys()
    local keys = {}
    for _, key in ipairs(SHM:get_keys()) do
        if key:find("^handoff:") then keys[#keys + 1] = key end
    end
    return keys
end
-- Runs fn() right after the first lookup of the handoff marker by the tick of o: the exact point between
-- "adopt_exit_requests() found nothing" and flush_lru() rewriting requests_<id>.
function after_marker_lookup(o, fn)
    local fired = false
    function o.metrics_datastore:get(k)
        local v, err = DS.get(self, k)
        if not fired and k:find("^handoff:requests:[0-9]+$") then
            fired = true
            fn()
        end
        return v, err
    end
end
function api_view(o, uri)
    o.ctx.bw.uri, o.ctx.bw.request_method = uri, "GET"
    return o.mod_api(o).msg
end
"""


def run(body, **env):
    return run_core(MODULE, PRELUDE + body, CONF=str(CONF), **env)


def test_blocked_request_logged_before_the_exit_reaches_the_requests_view():
    out = run("""
local w = new_worker(1)
local o = w.obj()
w.block(o, "r1")
local before = requests_in_dict()
local res = w.call("flush_on_exit", o)
-- what GET /metrics/requests walks: every "requests_<id>" key, per worker
o.ctx.bw.uri = "/metrics/requests"
local view = w.call("api", o).msg
emit({ before_count = #before, ret = res.ret, ids = requests_in_dict(), view = view.requests })
""")
    assert out["before_count"] == 0
    assert out["ret"] is True
    assert out["ids"] == ["r1"]
    assert [r["id"] for r in out["view"]] == ["r1"]


def test_counters_and_tables_are_flushed_and_the_next_worker_does_not_count_them_twice():
    out = run("""
local old = new_worker(1)
local o = old.obj()
old.block(o, "r1", { antibot = { counters = { hits = 5 }, tables = { seen = "a" } } })
old.call("flush_on_exit", o)
local after_exit = { hits = SHM:get("antibot_counter_hits_1"), seen = SHM:get("antibot_table_seen_1") }

-- the new worker of the same id restores from the dict, logs one more hit and ticks
local new = new_worker(1)
local n = new.obj()
new.init(n)
new.block(n, "r2", { antibot = { counters = { hits = 1 }, tables = { seen = "b" } } })
new.call("timer", n)
emit({ after_exit = after_exit, hits = SHM:get("antibot_counter_hits_1"), seen = SHM:get("antibot_table_seen_1"), ids = requests_in_dict() })
""")
    assert out["after_exit"]["hits"] == 5
    assert out["after_exit"]["seen"] == '["a"]'
    assert out["hits"] == 6
    assert out["seen"] == '["a","b"]'
    assert out["ids"] == ["r1", "r2"]


def test_new_worker_of_the_same_id_adopts_reports_the_old_one_flushed_after_its_first_tick():
    """The old worker exits after the new one restored the dict and ticked: its late report must survive."""
    out = run("""
local old = new_worker(1)
local po = old.obj()
old.block(po, "r1")
old.call("timer", po)                      -- regular tick: r1 is in the dict

local new = new_worker(1)                  -- reload: same id, same zone
local pn = new.obj()
new.init(pn)
new.block(pn, "n1")
new.call("timer", pn)                      -- its first tick rewrites requests_1 from its own LRU
local mid = requests_in_dict()

old.block(po, "r2")                        -- served by the draining worker
local exit = old.call("flush_on_exit", po)
local after_exit = requests_in_dict()      -- the exit flush must not drop what the new worker flushed

new.call("timer", pn)                      -- next tick of the new worker
local after_tick = requests_in_dict()
new.call("timer", pn)
emit({ mid = mid, after_exit = after_exit, after_tick = after_tick, final = requests_in_dict(), handoff_left = SHM:get("handoff:requests:1") ~= nil, handoff_keys = handoff_keys() })
""")
    assert out["mid"] == ["n1", "r1"]
    assert out["after_exit"] == ["n1", "r1", "r2"]
    assert out["after_tick"] == ["n1", "r1", "r2"]
    assert out["final"] == ["n1", "r1", "r2"]
    assert out["handoff_left"] is False, "the handoff marker must be consumed by the first tick"
    assert not out["handoff_keys"], "a consumed handoff leaves no key behind"


def test_no_handoff_marker_means_the_regular_tick_is_untouched():
    out = run("""
local w = new_worker(1)
local o = w.obj()
w.block(o, "r1")
w.call("timer", o)
w.block(o, "r2")
w.call("timer", o)
emit({ ids = requests_in_dict(), keys = SHM:get_keys() })
""")
    assert out["ids"] == ["r1", "r2"]
    assert not [k for k in out["keys"] if k.startswith("handoff")]


def test_metrics_disabled_writes_nothing_on_exit():
    out = run("""
local w = new_worker(1)
local o = w.obj()
w.block(o, "r1")
VARS.USE_METRICS = "no"
local res = w.call("flush_on_exit", o)
emit({ ret = res.ret, msg = res.msg, key_count = #SHM:get_keys() })
""")
    assert out == {"ret": True, "msg": "metrics not used", "key_count": 0}


def test_redis_mode_flushes_locally_and_leaves_reports_for_a_replay_by_the_next_worker():
    out = run("""
local old = new_worker(2, true)
local o = old.obj({ METRICS_SAVE_TO_REDIS = "yes" })
old.block(o, "r1")                          -- forbidden Redis stand-ins raise if the exit path touches them
local res = old.call("flush_on_exit", o)
local stored = json.decode(SHM:get("requests_2"))

local new = new_worker(2, true)
local n = new.obj({ METRICS_SAVE_TO_REDIS = "yes" })
new.init(n)
emit({ ret = res.ret, synced = stored[1].synced, id = stored[1].id })
""")
    assert out == {"ret": True, "synced": False, "id": "r1"}


def test_restored_unsynced_row_is_flagged_for_a_redis_replay():
    """What lets the Redis sync pick the exit-flushed report up on the next worker's first tick."""
    out = run("""
SHM:set("requests_2", json.encode({ { id = "r1", synced = false } }))
local new = new_worker(2, true)
local n = new.obj()
new.init(n)
local lru_row
for _, fn in pairs(new.mod) do
    if type(fn) == "function" then
        for i = 1, math.huge do
            local name, value = debug.getupvalue(fn, i)
            if not name then break end
            if name == "lru" then lru_row = value:get("requests")[1] end
        end
    end
end
emit({ retry = lru_row.redis_retry_json ~= nil })
""")
    assert out["retry"] is True


INTERLEAVED_PRELUDE = """
local old = new_worker(1)
local po = old.obj()
old.block(po, "r1")
old.call("timer", po)                      -- r1 is in the dict

local new = new_worker(1)                  -- reload: same id, same zone
local pn = new.obj()
new.init(pn)                               -- restores r1
new.block(pn, "n1")
old.block(po, "r2")                        -- late report of the draining worker
"""


def test_exit_flush_landing_between_the_marker_lookup_and_the_flush_of_the_new_tick_is_kept():
    """Old worker exits after the new tick looked for a handoff and before it rewrites requests_<id>."""
    out = run(INTERLEAVED_PRELUDE + """
CUR_PID = 1001
after_marker_lookup(pn, function() old.call("flush_on_exit", po) end)
new.call("timer", pn)                      -- adopt finds nothing, the exit lands, flush_lru rewrites the key
local after_tick = requests_in_dict()
new.call("timer", pn)                      -- the next tick must adopt the exit snapshot
local second = requests_in_dict()
new.call("timer", pn)
emit({ after_tick = after_tick, second = second, final = requests_in_dict(), handoff_keys = handoff_keys() })
""")
    assert out["second"] == ["n1", "r1", "r2"], "the exit flush was overwritten by the new worker's own tick"
    assert out["final"] == ["n1", "r1", "r2"]
    assert not out["handoff_keys"]


def test_sequential_exit_then_tick_keeps_the_old_workers_reports():
    out = run(INTERLEAVED_PRELUDE + """
CUR_PID = 1001
old.call("flush_on_exit", po)              -- completes before the tick
new.call("timer", pn)
local first = requests_in_dict()
new.call("timer", pn)
emit({ first = first, final = requests_in_dict(), handoff_keys = handoff_keys() })
""")
    assert out["first"] == ["n1", "r1", "r2"]
    assert out["final"] == ["n1", "r1", "r2"]
    assert not out["handoff_keys"]


def test_exit_landing_after_the_flush_of_the_tick_is_adopted_by_the_next_tick():
    out = run(INTERLEAVED_PRELUDE + """
CUR_PID = 1001
new.call("timer", pn)                      -- flushes first
local mid = requests_in_dict()
old.call("flush_on_exit", po)
new.call("timer", pn)
emit({ mid = mid, final = requests_in_dict(), handoff_keys = handoff_keys() })
""")
    assert out["mid"] == ["n1", "r1"]
    assert out["final"] == ["n1", "r1", "r2"]
    assert not out["handoff_keys"]


def test_two_exits_of_the_same_id_before_one_adoption_both_survive():
    out = run("""
local new = new_worker(1)
local pn = new.obj()
new.init(pn)
new.block(pn, "n1")
local a = new_worker(1)
local pa = a.obj()
a.block(pa, "a1")
local b = new_worker(1)
local pb = b.obj()
b.block(pb, "b1")
after_marker_lookup(pn, function()
    CUR_PID = 1001
    a.call("flush_on_exit", pa)
    CUR_PID = 1002
    b.call("flush_on_exit", pb)            -- two reloads in a row, both old workers still draining
end)
new.call("timer", pn)
new.call("timer", pn)
emit({ final = requests_in_dict(), handoff_keys = handoff_keys() })
""")
    assert out["final"] == ["a1", "b1", "n1"]
    assert not out["handoff_keys"]


def test_handoff_stays_out_of_the_scans_and_is_bounded_with_a_ttl():
    out = run("""
local old = new_worker(1)
local o = old.obj({ METRICS_MAX_BLOCKED_REQUESTS = "3" })
for i = 1, 5 do old.block(o, "r" .. i) end
CUR_PID = 1001
old.call("flush_on_exit", o)
local snapshots, ttls = {}, {}
for _, key in ipairs(handoff_keys()) do
    ttls[key] = SHM.ttls[key]
    local ok, rows = pcall(json.decode, SHM:get(key))
    if ok and type(rows) == "table" then snapshots[key] = #rows end
end
emit({ keys = handoff_keys(), snapshots = snapshots, ttls = ttls, all = SHM:get_keys() })
""")
    assert out["keys"], "the exit left no handoff"
    for key in out["keys"]:
        assert not key.startswith("requests_"), "the API scans requests_*"
        assert not key.endswith("_1"), "init_workers() restores *_<id>"
        assert out["ttls"][key] and out["ttls"][key] > 0
    assert out["snapshots"] and all(n <= 3 for n in out["snapshots"].values()), "the snapshot is capped like the LRU"


def test_corrupt_handoff_is_dropped_once_and_does_not_break_the_tick():
    out = run("""
local w = new_worker(1)
local o = w.obj()
w.block(o, "r1")
SHM:set("handoff:requests:1", "1")
SHM:set("handoff:requests:1:999", "{not json")
local res = w.call("timer", o)
local left = handoff_keys()
local sets = SHM.sets["handoff:requests:1:999"]
w.call("timer", o)
emit({ ret = res.ret, left = left, sets_after = SHM.sets["handoff:requests:1:999"], sets = sets, ids = requests_in_dict() })
""")
    assert out["ret"] is True
    assert not out["left"]
    assert out["ids"] == ["r1"]


CONF_HARNESS = r"""
local source = assert(io.open(CONF, "r")):read("*a")
local body = assert(source:match("\ninit_worker_by_lua_block {\n(.*)}%s*$"), "unexpected layout")
local calls = {}
local order = { init_workers = {}, init_worker = {}, timer = TIMER_ORDER }
ngx.shared.internalstore:set("plugins_order", order)
package.loaded["resty.lock"] = { new = function() return { lock = function() return 0 end, unlock = function() return true end } end }
local timers = {}
ngx.timer = { at = function(delay, fn) timers[#timers + 1] = { delay = delay, fn = fn } return true end }
VARS.IS_LOADING, VARS.TIMERS_LOG_LEVEL = "no", "info"

local worker = new_worker(1)
local metrics_obj = worker.obj()
local plugins = {
    metrics = { new = function() return metrics_obj end, mod = worker.mod },
}
for _, id in ipairs({ "badbehavior", "sessions" }) do
    plugins[id] = { mod = { timer = function() calls[#calls + 1] = id .. ":timer" return { ret = true, msg = "ok" } end,
                            flush_on_exit = function() calls[#calls + 1] = id .. ":flush_on_exit" return { ret = true, msg = "ok" } end } }
end
package.loaded["bunkerweb.helpers"] = {
    require_plugin = function(id) return plugins[id] and plugins[id].mod or nil, "no plugin " .. id end,
    new_plugin = function(mod)
        for id, p in pairs(plugins) do
            if p.mod == mod then return true, p.new and p.new() or setmetatable({}, { __index = mod }) end
        end
    end,
    call_plugin = function(obj, method)
        local ok, ret = pcall(obj[method], obj)
        if not ok then return false, ret end
        return true, ret
    end,
}
-- count the timer() of metrics too, without replacing it
local real_timer = worker.mod.timer
worker.mod.timer = function(self) calls[#calls + 1] = "metrics:timer" CUR_ID = 1 return real_timer(self) end
local real_exit = worker.mod.flush_on_exit
worker.mod.flush_on_exit = function(self) calls[#calls + 1] = "metrics:flush_on_exit" CUR_ID = 1 return real_exit(self) end

assert(load(body, "=init-worker-lua.conf"))()
local ready
for _, t in ipairs(timers) do if t.delay == 5 then ready = t end end
timers = {}
ready.fn(false)                                  -- the ready timer registers the recurrent one
local recurrent
for _, t in ipairs(timers) do if t.delay == 0 then recurrent = t.fn end end
assert(recurrent, "the recurrent timer was not registered")
"""


def test_exit_run_of_the_recurrent_timer_flushes_metrics_and_runs_no_other_timer():
    out = run(
        CONF_HARNESS + """
worker.block(metrics_obj, "r1")
calls = {}
recurrent(true)
emit({ calls = calls, n = #calls, ids = requests_in_dict(), n_ids = #requests_in_dict() })
""",
        TIMER_ORDER=["metrics", "badbehavior", "sessions"],
    )
    assert out["calls"] == ["metrics:flush_on_exit"], "only the metrics flush may run on the exit path"
    assert out["ids"] == ["r1"]


def test_regular_tick_still_runs_every_timer_and_no_exit_flush():
    out = run(
        CONF_HARNESS + """
calls = {}
recurrent(false)
emit({ calls = calls, n = #calls })
""",
        TIMER_ORDER=["metrics", "badbehavior", "sessions"],
    )
    assert out["calls"] == ["metrics:timer", "badbehavior:timer", "sessions:timer"]


def test_no_metrics_in_the_timer_order_runs_nothing_on_exit():
    out = run(
        CONF_HARNESS + """
calls = {}
recurrent(true)
emit({ calls = calls, n = #calls })
""",
        TIMER_ORDER=["badbehavior", "sessions"],
    )
    assert out["n"] == 0


def test_exit_path_with_metrics_disabled_writes_nothing():
    out = run(
        CONF_HARNESS + """
worker.block(metrics_obj, "r1")
VARS.USE_METRICS = "no"
calls = {}
recurrent(true)
emit({ calls = calls, n = #calls, ids = requests_in_dict(), n_ids = #requests_in_dict() })
""",
        TIMER_ORDER=["metrics"],
    )
    assert out["calls"] == ["metrics:flush_on_exit"]
    assert out["n_ids"] == 0


def test_conf_source_has_no_other_work_in_the_premature_branch():
    source = Path(CONF).read_text(encoding="utf-8")
    branch = source.split("if premature then", 1)[1].split("return", 1)[0]
    assert "timer" not in branch.replace("disabling timer", "").replace("flush_metrics_on_exit", "")
