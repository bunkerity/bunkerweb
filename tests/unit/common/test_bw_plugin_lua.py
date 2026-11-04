"""Behaviour of ``src/bw/lua/bunkerweb/plugin.lua``, the real file run under plain Lua.

``plugin`` is the base class every first-party plugin inherits. It builds the shared stores, loads the
plugin's settings from the metadata the scheduler stored (per service in a request phase, global
otherwise), and offers ``ret``, request metrics (``set_metric`` / ``get_metric``) and the throttled logger
(``log_throttled`` / ``flush_log_recaps``). ``middleclass`` and ``bunkerweb.logger`` are the real files.
The stores are stand-ins: a ``datastore`` over named dictionaries (``DICTS``), constructors for the cache
and cluster stores that record how they were built, and a ``bunkerweb.utils`` whose ``get_variable`` follows
the real global / multisite rule. ``plugin.lua`` has no ``is_needed`` or deny-status helper: those live in
``utils`` and in each plugin.
"""

import pytest
from _lua_core_helpers import BW_MODULES, LUA, module_path, run_core  # type: ignore

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

MODULE = module_path("PLUGIN", BW_MODULES / "plugin.lua")

SETTINGS = {"USE_LIMIT": {"context": "multisite"}, "LIMIT_RATE": {"context": "global"}}
GLOBAL = {"USE_REDIS": "no", "IS_LOADING": "no", "MULTISITE": "no", "USE_LIMIT": "yes", "LIMIT_RATE": "10r/s"}

SETUP = """
VAR_CALLS = {}
GET_ERR = GET_ERR or {}
METRICS_DS = METRICS_DS or {}
METRICS_DS_STREAM = METRICS_DS_STREAM or {}
ngx.var.server_name = SERVER_NAME or "a.example"
ngx.ctx = { bw = {} }
ngx.shared = {
    internalstore = "internalstore", internalstore_stream = "internalstore_stream",
    metrics_datastore = "metrics_datastore", metrics_datastore_stream = "metrics_datastore_stream",
}
DICTS = {
    internalstore = INTERNAL, internalstore_stream = INTERNAL,
    metrics_datastore = METRICS_DS, metrics_datastore_stream = METRICS_DS_STREAM,
}

local datastore = {}
datastore.__index = datastore
function datastore.new(_, dict) return setmetatable({ kind = "datastore", dict = dict or "datastore" }, datastore) end
function datastore:get(key)
    if GET_ERR[key] then return nil, GET_ERR[key] end
    local value = (DICTS[self.dict] or {})[key]
    if value == nil then return nil, "not found" end
    return value, "success"
end
function datastore:keys()
    USED_DICT = self.dict
    local out = {}
    for key in pairs(DICTS[self.dict] or {}) do out[#out + 1] = key end
    table.sort(out)
    return out
end
package.loaded["bunkerweb.datastore"] = datastore
package.loaded["bunkerweb.cachestore"] = { new = function(_, use_redis, ctx) return { kind = "cachestore", use_redis = use_redis, ctx = ctx } end }
package.loaded["bunkerweb.clusterstore"] = { new = function() return { kind = "clusterstore" } end }
package.loaded["bunkerweb.utils"] = {
    get_ctx_obj = function(obj, ctx) return ctx and ctx.bw and ctx.bw[obj] or nil end,
    -- Same rule as utils.get_variable: the global value, overridden by the service's own entry in multisite.
    get_variable = function(name, site_search, ctx)
        VAR_CALLS[#VAR_CALLS + 1] = { name, site_search }
        if site_search == nil then site_search = true end
        local value = VARIABLES.global[name]
        if site_search and VARIABLES.global.MULTISITE == "yes" then
            local server_name = ctx and ctx.bw and ctx.bw.server_name or ngx.var.server_name
            if VARIABLES[server_name] and VARIABLES[server_name][name] ~= nil then value = VARIABLES[server_name][name] end
        end
        if value == nil then return nil, "not found" end
        return value, "success"
    end,
}
local plugin = dofile(MODULE)
function new(ctx) return plugin:new("limit", ctx) end
"""


def run(body, *, variables=None, settings=SETTINGS, **env):
    values = {"global": {**GLOBAL, **(variables or {}).get("global", {})}}
    values.update({k: v for k, v in (variables or {}).items() if k != "global"})
    internal = {"plugin_limit": {"settings": settings}, "plugin_other": {"settings": {}}} if settings is not None else {}
    return run_core(MODULE, SETUP + body, VARIABLES=values, INTERNAL=internal, **env)


def logs(out):
    return out["logs"] if isinstance(out, dict) and out.get("logs") else []


REQUEST_PHASES = ["set", "rewrite", "access", "content", "header_filter", "body_filter", "log", "preread"]


class TestInitializeStores:
    @pytest.mark.parametrize("phase", REQUEST_PHASES)
    def test_a_request_phase_is_a_request(self, phase):
        out = run("local p = new({ bw = {} }) emit({ is_request = p.is_request, has_ctx = p.ctx ~= nil })", phase=phase)
        assert out == {"is_request": True, "has_ctx": True}

    @pytest.mark.parametrize("phase", ["init", "init_worker", "timer", "ssl_certificate", "ssl_client_hello", "exit_worker"])
    def test_other_phases_are_not_requests_and_keep_no_context(self, phase):
        out = run("local p = new({ bw = {} }) emit({ is_request = p.is_request, has_ctx = p.ctx ~= nil })", phase=phase)
        assert out == {"is_request": False, "has_ctx": False}

    def test_the_given_context_is_the_request_context(self):
        out = run("local ctx = { bw = {} } emit(new(ctx).ctx == ctx)")
        assert out is True

    def test_without_a_context_a_request_uses_ngx_ctx(self):
        assert run("emit(new().ctx == ngx.ctx)") is True

    def test_a_request_reuses_the_stores_already_in_its_context(self):
        out = run("""
local metadata = { get = function() return { settings = {} } end }
local ctx = { bw = { internalstore = metadata, datastore = {}, cachestore = {}, clusterstore = {}, cachestore_local = {} } }
local p = new(ctx)
emit({
    internalstore = p.internalstore == ctx.bw.internalstore, datastore = p.datastore == ctx.bw.datastore,
    cachestore = p.cachestore == ctx.bw.cachestore, clusterstore = p.clusterstore == ctx.bw.clusterstore,
    cachestore_local = p.cachestore_local == ctx.bw.cachestore_local,
})
""")
        assert out == {k: True for k in ("internalstore", "datastore", "cachestore", "clusterstore", "cachestore_local")}

    def test_a_request_builds_the_stores_its_context_lacks(self):
        out = run("""
local ctx = { bw = {} }
local p = new(ctx)
emit({
    internalstore = p.internalstore.dict, datastore = p.datastore.dict, clusterstore = p.clusterstore.kind,
    cachestore_redis = p.cachestore.use_redis, cachestore_ctx = p.cachestore.ctx == ctx,
    local_redis = p.cachestore_local.use_redis, local_ctx = p.cachestore_local.ctx == ctx,
})
""")
        assert out == {
            "internalstore": "internalstore",
            "datastore": "datastore",
            "clusterstore": "clusterstore",
            "cachestore_redis": False,
            "cachestore_ctx": True,
            "local_redis": False,
            "local_ctx": True,
        }

    def test_the_shared_cachestore_follows_use_redis_but_the_local_one_never_does(self):
        out = run(
            "local p = new({ bw = {} }) emit({ shared = p.cachestore.use_redis, local_ = p.cachestore_local.use_redis, flag = p.use_redis })",
            variables={"global": {"USE_REDIS": "yes"}},
        )
        assert out == {"shared": True, "local_": False, "flag": True}

    def test_outside_a_request_the_stores_are_built_fresh_whatever_the_context_holds(self):
        out = run(
            """
local ctx = { bw = { internalstore = { kind = "from ctx" }, cachestore = { kind = "from ctx" } } }
local p = new(ctx)
emit({ internalstore = p.internalstore.kind, cachestore = p.cachestore.kind, ctx_given = p.cachestore.ctx ~= nil })
""",
            phase="timer",
        )
        assert out == {"internalstore": "datastore", "cachestore": "cachestore", "ctx_given": False}

    def test_the_stream_subsystem_reads_the_stream_internalstore(self):
        out = run("local p = new({ bw = {} }) emit({ dict = p.internalstore.dict, kind = p.kind })", subsystem="stream")
        assert out == {"dict": "internalstore_stream", "kind": "stream"}

    def test_the_http_subsystem_reads_the_http_internalstore(self):
        out = run("local p = new({ bw = {} }) emit({ dict = p.internalstore.dict, kind = p.kind })")
        assert out == {"dict": "internalstore", "kind": "http"}

    def test_the_plugin_id_is_exposed(self):
        assert run("emit(new({ bw = {} }):get_id())") == "limit"


class TestInitializeVariables:
    def test_the_settings_declared_in_the_metadata_are_loaded(self):
        out = run("local p = new({ bw = {} }) emit(p.variables)")
        assert out == {"USE_LIMIT": "yes", "LIMIT_RATE": "10r/s"}

    def test_a_request_resolves_a_multisite_setting_for_its_service(self):
        out = run("emit(new({ bw = {} }).variables)", variables={"global": {"MULTISITE": "yes"}, "a.example": {"USE_LIMIT": "no"}})
        assert out == {"USE_LIMIT": "no", "LIMIT_RATE": "10r/s"}

    def test_a_service_without_its_own_value_inherits_the_global_one(self):
        out = run("emit(new({ bw = {} }).variables)", variables={"global": {"MULTISITE": "yes"}, "a.example": {}})
        assert out["USE_LIMIT"] == "yes"

    def test_a_global_setting_ignores_the_service_entry(self):
        out = run("emit(new({ bw = {} }).variables)", variables={"global": {"MULTISITE": "yes"}, "a.example": {"LIMIT_RATE": "1r/s"}})
        assert out["LIMIT_RATE"] == "10r/s"

    def test_outside_a_request_a_multisite_setting_is_the_global_value(self):
        out = run(
            "emit(new({ bw = {} }).variables)",
            variables={"global": {"MULTISITE": "yes"}, "a.example": {"USE_LIMIT": "no"}},
            phase="timer",
        )
        assert out["USE_LIMIT"] == "yes"

    def test_only_a_multisite_setting_in_a_request_asks_for_the_site_value(self):
        out = run("""
local p = new({ bw = {} })
local asked = {}
for _, call in ipairs(VAR_CALLS) do asked[call[1]] = call[2] end
emit(asked)
""")
        assert out["USE_LIMIT"] is True
        assert out["LIMIT_RATE"] is False
        assert out["USE_REDIS"] is False
        assert out["IS_LOADING"] is False

    def test_a_missing_setting_is_nil_and_reported_once_per_window(self):
        out = run("""
VARIABLES.global.LIMIT_RATE = nil
local first, second = new({ bw = {} }), new({ bw = {} })
emit({ value = first.variables.LIMIT_RATE, logs = LOGS })
""")
        assert out.get("value") is None
        assert out["logs"] == [["WARN", "[LIMIT] can't get LIMIT_RATE variable : not found"]]

    def test_a_missing_setting_is_reported_again_after_the_window(self):
        out = run("""
VARIABLES.global.LIMIT_RATE = nil
new({ bw = {} })
NOW = NOW + 61
new({ bw = {} })
emit(#LOGS)
""")
        assert out == 2

    def test_is_loading_follows_the_variable(self):
        assert run("emit(new({ bw = {} }).is_loading)", variables={"global": {"IS_LOADING": "yes"}}) is True
        assert run("emit(new({ bw = {} }).is_loading)") is False

    def test_a_missing_is_loading_is_logged_and_means_not_loading(self):
        out = run("VARIABLES.global.IS_LOADING = nil local p = new({ bw = {} }) emit({ loading = p.is_loading, logs = LOGS })")
        assert out == {"loading": False, "logs": [["ERR", "[LIMIT] can't get IS_LOADING variable : not found"]]}

    def test_a_missing_use_redis_is_logged_and_means_no_redis(self):
        out = run("VARIABLES.global.USE_REDIS = nil local p = new({ bw = {} }) emit({ redis = p.use_redis, logs = LOGS })")
        assert out == {"redis": False, "logs": [["ERR", "[LIMIT] not found"]]}

    def test_without_metadata_the_error_is_logged_and_no_variables_are_loaded(self):
        out = run("local p = new({ bw = {} }) emit({ variables = p.variables == nil, is_loading = p.is_loading, kind = p.kind, logs = LOGS })", settings=None)
        assert out == {"variables": True, "logs": [["ERR", "[LIMIT] not found"]]}


class TestRet:
    def test_ret_packs_the_decision(self):
        out = run('emit(new({ bw = {} }):ret(true, "ok", 200, "/next", { a = 1 }))')
        assert out == {"ret": True, "msg": "ok", "status": 200, "redirect": "/next", "data": {"a": 1}}

    def test_ret_leaves_unused_fields_nil(self):
        assert run('emit(new({ bw = {} }):ret(false, "denied"))') == {"ret": False, "msg": "denied"}


class TestSetMetric:
    def test_a_metric_is_recorded_in_the_request_context_under_the_plugin_id(self):
        out = run('local ctx = { bw = {} } new(ctx):set_metric("counters", "failed_limit", 1) emit(ctx.bw.metrics)')
        assert out == {"limit": {"counters": {"failed_limit": 1}}}

    def test_a_later_value_replaces_the_earlier_one_and_kinds_stay_apart(self):
        out = run("""
local ctx = { bw = {} }
local p = new(ctx)
p:set_metric("counters", "a", 1)
p:set_metric("counters", "a", 2)
p:set_metric("counters", "b", 3)
p:set_metric("tables", "t", { "x" })
emit(ctx.bw.metrics.limit)
""")
        assert out == {"counters": {"a": 2, "b": 3}, "tables": {"t": ["x"]}}

    def test_two_plugins_share_the_metrics_table_without_mixing(self):
        out = run("""
local ctx = { bw = {} }
new(ctx):set_metric("counters", "a", 1)
plugin:new("other", ctx):set_metric("counters", "a", 5)
emit(ctx.bw.metrics)
""")
        assert out == {"limit": {"counters": {"a": 1}}, "other": {"counters": {"a": 5}}}

    def test_outside_a_request_nothing_is_recorded_and_nothing_fails(self):
        assert run('local p = new({ bw = {} }) p:set_metric("counters", "a", 1) emit(p.ctx == nil)', phase="timer") is True

    def test_a_context_without_bw_is_left_untouched(self):
        assert run('local ctx = {} new(ctx):set_metric("counters", "a", 1) emit(ctx.bw == nil)') is True


class TestGetMetric:
    @staticmethod
    def metrics(**ds):
        return {"METRICS_DS": ds}

    def test_counters_are_summed_across_workers(self):
        out = run('emit(new({ bw = {} }):get_metric("counters", "req"))', **self.metrics(limit_counter_req_1="3", limit_counter_req_2="4"))
        assert out == 7

    def test_only_the_asked_counter_of_this_plugin_is_counted(self):
        out = run(
            'emit(new({ bw = {} }):get_metric("counters", "req"))',
            **self.metrics(
                limit_counter_req_1="3", limit_counter_req2_1="100", limit_counter_req_x_1="100", other_counter_req_1="100", limit_table_req_1="100"
            ),
        )
        assert out == 3

    def test_a_counter_that_is_not_a_number_counts_as_zero(self):
        out = run('emit(new({ bw = {} }):get_metric("counters", "req"))', **self.metrics(limit_counter_req_1="abc", limit_counter_req_2="2"))
        assert out == 2

    def test_tables_are_concatenated_across_workers(self):
        out = run(
            'emit(new({ bw = {} }):get_metric("tables", "hits"))',
            **self.metrics(limit_table_hits_1='["a","b"]', limit_table_hits_2='["c"]'),
        )
        assert out == ["a", "b", "c"]

    def test_a_table_wins_over_numbers_stored_under_the_same_name(self):
        out = run(
            'emit(new({ bw = {} }):get_metric("tables", "hits"))',
            **self.metrics(limit_table_hits_1="5", limit_table_hits_2='["c"]'),
        )
        assert out == ["c"]

    def test_no_matching_key_is_nil(self):
        out = run('emit({ value = new({ bw = {} }):get_metric("counters", "req") })', **self.metrics(other_counter_req_1="1"))
        assert out == {}

    def test_an_unknown_kind_is_nil_without_reading_any_key(self):
        out = run('emit({ value = new({ bw = {} }):get_metric("gauges", "req"), used = USED_DICT })', **self.metrics(limit_counter_req_1="1"))
        assert out == {}

    def test_the_http_subsystem_reads_the_http_metrics_dictionary(self):
        out = run('new({ bw = {} }):get_metric("counters", "req") emit(USED_DICT)', **self.metrics(limit_counter_req_1="1"))
        assert out == "metrics_datastore"

    def test_the_stream_subsystem_reads_the_stream_metrics_dictionary(self):
        out = run(
            'emit({ value = new({ bw = {} }):get_metric("counters", "req"), used = USED_DICT })',
            subsystem="stream",
            METRICS_DS_STREAM={"limit_counter_req_1": "9"},
        )
        assert out == {"value": 9, "used": "metrics_datastore_stream"}

    def test_a_read_error_is_logged_and_the_other_workers_still_count(self):
        out = run(
            'emit({ value = new({ bw = {} }):get_metric("counters", "req"), logs = LOGS })',
            GET_ERR={"limit_counter_req_2": "boom"},
            **self.metrics(limit_counter_req_1="3", limit_counter_req_2="4"),
        )
        assert out == {"value": 3, "logs": [["ERR", "[LIMIT] error while fetching metric limit_counter_req_2 : boom"]]}


class TestLogThrottled:
    def test_the_first_occurrence_is_logged_immediately(self):
        out = run('new({ bw = {} }):log_throttled(ngx.WARN, "k", "m1") emit(LOGS)')
        assert out == [["WARN", "[LIMIT] m1"]]

    def test_repeats_inside_the_window_are_counted_silently(self):
        out = run("""
local p = new({ bw = {} })
for _, delta in ipairs({ 0, 10, 20, 59 }) do NOW = 1000000 + delta p:log_throttled(ngx.WARN, "k", "m") end
emit(LOGS)
""")
        assert out == [["WARN", "[LIMIT] m"]]

    def test_the_first_call_after_the_window_recaps_the_last_message_then_logs_the_new_one(self):
        out = run("""
local p = new({ bw = {} })
p:log_throttled(ngx.WARN, "k", "m1")
NOW = NOW + 10 p:log_throttled(ngx.ERR, "k", "m2")
NOW = NOW + 10 p:log_throttled(ngx.ERR, "k", "m3")
NOW = NOW + 40 p:log_throttled(ngx.WARN, "k", "m4")
emit(LOGS)
""")
        assert out == [
            ["WARN", "[LIMIT] m1"],
            ["ERR", "[LIMIT] m3 (repeated 3 times in the last 60s)"],
            ["WARN", "[LIMIT] m4"],
        ]

    def test_a_single_occurrence_gets_no_recap(self):
        out = run("""
local p = new({ bw = {} })
p:log_throttled(ngx.WARN, "k", "m1")
NOW = NOW + 120 p:log_throttled(ngx.WARN, "k", "m2")
emit(LOGS)
""")
        assert out == [["WARN", "[LIMIT] m1"], ["WARN", "[LIMIT] m2"]]

    def test_the_window_is_a_minute_by_default_and_closes_at_exactly_sixty_seconds(self):
        out = run("""
local p = new({ bw = {} })
p:log_throttled(ngx.WARN, "k", "a")
NOW = NOW + 59 p:log_throttled(ngx.WARN, "k", "b")
local silent = #LOGS
NOW = NOW + 1 p:log_throttled(ngx.WARN, "k", "c")
emit({ silent = silent, total = #LOGS })
""")
        assert out == {"silent": 1, "total": 3}

    def test_a_custom_interval_is_honoured(self):
        out = run("""
local p = new({ bw = {} })
p:log_throttled(ngx.WARN, "k", "a", 5)
NOW = NOW + 4 p:log_throttled(ngx.WARN, "k", "b", 5)
local silent = #LOGS
NOW = NOW + 1 p:log_throttled(ngx.WARN, "k", "c", 5)
emit({ silent = silent, logs = LOGS })
""")
        assert out["silent"] == 1
        assert out["logs"][1:] == [["WARN", "[LIMIT] b (repeated 2 times in the last 5s)"], ["WARN", "[LIMIT] c"]]

    def test_keys_are_independent(self):
        out = run('local p = new({ bw = {} }) p:log_throttled(ngx.WARN, "a", "x") p:log_throttled(ngx.WARN, "b", "y") emit(LOGS)')
        assert out == [["WARN", "[LIMIT] x"], ["WARN", "[LIMIT] y"]]

    def test_plugins_do_not_share_throttle_state(self):
        out = run("""
new({ bw = {} }):log_throttled(ngx.WARN, "k", "mine")
plugin:new("other", { bw = {} }):log_throttled(ngx.WARN, "k", "theirs")
emit(LOGS)
""")
        assert out == [["WARN", "[LIMIT] mine"], ["WARN", "[OTHER] theirs"]]


class TestFlushLogRecaps:
    def test_an_expired_window_with_repeats_emits_its_recap_once(self):
        out = run("""
local p = new({ bw = {} })
p:log_throttled(ngx.WARN, "k", "m1")
NOW = NOW + 10 p:log_throttled(ngx.ERR, "k", "m2")
NOW = NOW + 50 p:flush_log_recaps()
p:flush_log_recaps()
emit(LOGS)
""")
        assert out == [["WARN", "[LIMIT] m1"], ["ERR", "[LIMIT] m2 (repeated 2 times in the last 60s)"]]

    def test_a_window_still_open_is_left_alone(self):
        out = run("""
local p = new({ bw = {} })
p:log_throttled(ngx.WARN, "k", "m1")
NOW = NOW + 10 p:log_throttled(ngx.WARN, "k", "m2")
NOW = NOW + 20 p:flush_log_recaps()
emit(#LOGS)
""")
        assert out == 1

    def test_a_flushed_key_starts_a_new_window(self):
        out = run("""
local p = new({ bw = {} })
p:log_throttled(ngx.WARN, "k", "m1")
p:log_throttled(ngx.WARN, "k", "m2")
NOW = NOW + 60 p:flush_log_recaps()
p:log_throttled(ngx.WARN, "k", "m3")
emit(LOGS)
""")
        assert out == [
            ["WARN", "[LIMIT] m1"],
            ["WARN", "[LIMIT] m2 (repeated 2 times in the last 60s)"],
            ["WARN", "[LIMIT] m3"],
        ]

    def test_an_expired_entry_without_repeats_is_dropped_silently(self):
        out = run("""
local p = new({ bw = {} })
p:log_throttled(ngx.WARN, "k", "m1")
NOW = NOW + 60 p:flush_log_recaps()
emit(#LOGS)
""")
        assert out == 1

    def test_the_interval_given_to_log_throttled_decides_when_the_flush_emits(self):
        out = run("""
local p = new({ bw = {} })
p:log_throttled(ngx.WARN, "k", "m1", 5)
p:log_throttled(ngx.WARN, "k", "m2", 5)
NOW = NOW + 5 p:flush_log_recaps()
emit(LOGS)
""")
        assert out == [["WARN", "[LIMIT] m1"], ["WARN", "[LIMIT] m2 (repeated 2 times in the last 5s)"]]

    def test_a_plugin_only_flushes_its_own_keys(self):
        out = run("""
local mine, other = new({ bw = {} }), plugin:new("other", { bw = {} })
mine:log_throttled(ngx.WARN, "k", "mine1") mine:log_throttled(ngx.WARN, "k", "mine2")
other:log_throttled(ngx.WARN, "k", "theirs1") other:log_throttled(ngx.WARN, "k", "theirs2")
NOW = NOW + 60 mine:flush_log_recaps()
local after_mine = #LOGS
other:flush_log_recaps()
emit({ after_mine = after_mine, logs = LOGS })
""")
        assert out["after_mine"] == 3
        assert out["logs"] == [
            ["WARN", "[LIMIT] mine1"],
            ["WARN", "[OTHER] theirs1"],
            ["WARN", "[LIMIT] mine2 (repeated 2 times in the last 60s)"],
            ["WARN", "[OTHER] theirs2 (repeated 2 times in the last 60s)"],
        ]
