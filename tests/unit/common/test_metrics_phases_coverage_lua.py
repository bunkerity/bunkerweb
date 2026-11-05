"""Exercise real metrics phases and request queries at OpenResty/storage boundaries."""

import pytest
from _lua_core_helpers import LUA, ROOT, run_core

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")
MODULE = ROOT / "src/common/core/metrics/metrics.lua"

PRELUDE = r"""
ngx.HTTP_OK, ngx.HTTP_BAD_REQUEST, ngx.HTTP_INTERNAL_SERVER_ERROR = 200, 400, 500
ngx.status = 403
ngx.now = function() return NOW end
ngx.worker = { id = function() return 0 end }
ngx.unescape_uri = function(s) return (s:gsub('%%(%x%x)', function(h) return string.char(tonumber(h, 16)) end)) end
ARGS, LOGS, CALLS, QUEUE, VALUES, TTLS = {}, {}, {}, {}, {}, {}
REASON, COUNTRY, NEEDED = 'blocked', 'FR', true
local function log(_, level, message) LOGS[#LOGS + 1] = level .. ':' .. message end
local plugin = require('middleclass')('plugin')
local methods = {
    initialize = function(self, name, ctx)
        self.ctx, self.variables, self.logger = ctx, {}, { log = log }
    end,
    ret = function(_, ok, message, status) return { ok = ok, message = message, status = status } end,
    log_throttled = function(_, level, key, message) log(nil, level, key .. ':' .. message) end,
    flush_log_recaps = function() end,
}
for key, value in pairs(methods) do plugin[key] = value end
package.loaded['bunkerweb.plugin'] = plugin
package.loaded['bunkerweb.utils'] = {
    get_reason = function() return REASON, { rule = 'test' }, 'block' end,
    get_country = function() return COUNTRY, 'lookup failed' end,
    has_variable = function() return NEEDED, 'settings unavailable' end,
    get_variable = function() return '' end,
    parse_duration = function(s) return tonumber(s) end,
    is_connection_error = function(s) return s == 'closed' end,
    is_oom_error = function(s) return s:find('OOM', 1, true) ~= nil end,
    rand = function(n) return string.rep('a', n) end,
}
ngx.req = { get_uri_args = function() return ARGS end }
local dict = {}
function dict:lpush(_, value)
    if QUEUE_ERROR then return nil, 'queue full' end
    table.insert(QUEUE, 1, value) return #QUEUE
end
function dict:rpush(_, value)
    if QUEUE_ERROR then return nil, 'queue full' end
    QUEUE[#QUEUE + 1] = value return #QUEUE
end
function dict:rpop() return table.remove(QUEUE), POP_ERROR end
ngx.shared.metrics_datastore, ngx.shared.metrics_datastore_stream = dict, {}
package.loaded['bunkerweb.datastore'] = { new = function(_, selected)
    return {
        dict = selected,
        get = function(_, key) return VALUES[key], 'missing value' end,
        keys = function() local keys = {} for key in pairs(VALUES) do keys[#keys + 1] = key end table.sort(keys) return keys end,
        ttl = function(_, key) if TTL_ERROR then return false, 'ttl failed' end return true, TTLS[key] or 0 end,
        set_with_retries = function(_, key, value, ttl)
            if WRITE_ERROR then return false, WRITE_ERROR end
            VALUES[key], TTLS[key] = value, ttl return true
        end,
    }
end }
package.loaded['resty.lrucache'] = { new = function(capacity)
    if RESIZE_ERROR then return nil, 'allocation failed' end
    local values = {}
    LRU = {
        capacity = function() return capacity end,
        get = function(_, key) return values[key] end,
        set = function(_, key, value) values[key] = value end,
        delete = function(_, key) values[key] = nil end,
        get_keys = function() local keys = {} for key in pairs(values) do keys[#keys + 1] = key end table.sort(keys) return keys end,
    }
    return LRU
end }
local metrics = assert(loadfile(MODULE))()
local self = setmetatable({}, { __index = metrics })
self:initialize({ bw = {
    uri = '/metrics/requests/query', request_method = 'GET', request_id = 'live', start_time = 42,
    remote_addr = '192.0.2.1', request_uri = '/test', server_name = 'example.test', ip_is_global = true,
} })
self.variables = { USE_METRICS = 'yes', MAX_LRU_HISTORY = '2', METRICS_MAX_BLOCKED_REQUESTS = '2', METRICS_REDIS_TTL = '60' }
self.clusterstore = {
    connect = function() CONNECTS = (CONNECTS or 0) + 1 if CONNECT_ERROR then return false, 'closed' end return true end,
    close = function() CLOSES = (CLOSES or 0) + 1 end,
    call = function(_, method, ...)
        CALLS[#CALLS + 1] = { method, ... }
        if REPLY then return REPLY(method, ...) end
        return true
    end,
}
"""


def run(body, *, subsystem="http", **env):
    return run_core(MODULE, PRELUDE + body, subsystem=subsystem, **env)


ROWS = r"""
VALUES.requests_0 = json.encode({
    { id = 'a', date = 10, status = 403, country = 'FR', method = 'GET', url = '/a,b;c:d', ip = '192.0.2.1' },
    { id = 'b', date = 30, status = 404, country = 'GB', method = 'POST', url = '/Beta' },
    { id = 'c', date = 20, status = 200, country = 'FR', method = 'GET', security_mode = 'detect' },
    { id = 'd', date = 40, status = 500, country = 'US' },
    { id = 'e', date = 50, status = 399, country = 'US' },
})
VALUES.requests_1 = 'not json'
VALUES.requests_2 = '12'
VALUES.unrelated = 'ignored'
"""


def test_query_default_selection_paging_and_facets():
    out = run(ROWS + "ARGS = {start = '1', length = '1'}; emit(self:api())")
    assert out["status"] == 200
    result = out["message"]
    assert (result["total"], result["filtered"]) == (5, 3)
    assert [row["id"] for row in result["data"]] == ["c"]
    assert result["pane_counts"]["country"] == {"FR": {"total": 2, "count": 2}, "GB": {"total": 1, "count": 1}}


@pytest.mark.parametrize(
    "args,ids",
    [
        ({"search": "bEtA"}, ["b"]),
        ({"search": "404"}, ["b"]),
        ({"search": ".*"}, []),
        ({"search_panes": "country:FR;method:GET", "order_dir": "asc"}, ["a", "c"]),
        ({"search_panes": "country:FR,GB;status:404"}, ["b"]),
        ({"search_panes": "url:%2Fa%2Cb%3Bc%3Ad"}, ["a"]),
        ({"search_panes": "reason:N/A"}, ["b", "c", "a"]),
        ({"order_column": "country", "order_dir": "desc"}, ["b", "a", "c"]),
        ({"order_column": "method", "order_dir": "asc"}, ["a", "c", "b"]),
        ({"length": "-1", "order_dir": "asc"}, ["a", "c", "b"]),
        ({"start": "99"}, []),
        ({"length": "0"}, []),
    ],
)
def test_query_filters_order_and_page_boundaries(args, ids):
    out = run(ROWS + "ARGS = QUERY; emit(self:api_requests_query())", QUERY=args)
    data = out["message"]["data"]
    # Ties have no defined ordering.
    actual = [row["id"] for row in data] if data else []
    if args.get("order_column"):
        assert actual[0 if args.get("order_dir") == "desc" else -1] == "b"
        assert set(actual) == set(ids)
    else:
        assert actual == ids


def test_query_count_only_retains_total_and_filtered_counts():
    out = run(ROWS + "ARGS = {count_only = 'true', search_panes = 'country:FR'}; emit(self:api_requests_query())")
    assert out == {"ok": True, "status": 200, "message": {"total": 5, "filtered": 2}}


@pytest.mark.parametrize(
    "args",
    [
        {"start": "-1"},
        {"length": "-2"},
        {"start": "0.5"},
        {"order_dir": "sideways"},
        {"start": "invalid"},
        {"length": "invalid"},
        {"length": "0.5"},
        {"start": "inf"},
        {"length": "nan"},
        {"start": ["0", "1"]},
        {"length": ["1", "2"]},
    ],
)
def test_query_rejects_invalid_paging_and_order(args):
    assert run(ROWS + "ARGS = QUERY; emit(self:api_requests_query())", QUERY=args)["status"] == 400


def test_api_route_guard_counter_sum_and_table_merge():
    out = run(r"""
self.ctx.bw.request_method = 'POST'
local post = self:api()
self.ctx.bw.request_method, self.ctx.bw.uri = 'GET', '/other'
local other = self:api()
self.ctx.bw.uri = '/metrics/plugin'
VALUES.plugin_counter_hits_0, VALUES.plugin_counter_hits_1 = '2', '3'
VALUES.plugin_table_events_0, VALUES.plugin_table_events_1 = '["old"]', '["new"]'
VALUES.plugin_0 = '7'
emit({ post = post, other = other, metrics = self:api() })
""")
    assert out["post"]["ok"] is False and out["other"]["ok"] is False
    assert out["metrics"] == {"ok": True, "status": 200, "message": {"counter_hits": 5, "table_events": ["old", "new"], "plugin": 7}}


@pytest.mark.parametrize("ban_id,status", [("abc:0@host", 200), ("bad/id", 400), ("x" * 257, 400)])
def test_api_ban_evidence_missing_and_invalid_id(ban_id, status):
    out = run("self.ctx.bw.uri = '/metrics/badbehavior/ban/' .. BAN_ID; emit(self:api())", BAN_ID=ban_id)
    assert out["status"] == status
    if status == 200:
        assert out["message"] == {"ban_id": ban_id, "evidence_missing": True}


@pytest.mark.parametrize("payload,status", [("not json", 500), ('{"events":["proof"]}', 200)])
def test_api_ban_evidence_decode(payload, status):
    out = run("VALUES['ban_evidence:abc:data'] = PAYLOAD; self.ctx.bw.uri = '/metrics/badbehavior/ban/abc'; emit(self:api())", PAYLOAD=payload)
    assert out["status"] == status
    assert out["message"] == ({"events": ["proof"]} if status == 200 else "invalid ban evidence")


def test_log_caps_reports_and_event_history_and_accumulates_counters():
    out = run(r"""
self.use_redis = true
self.ctx.bw.metrics = { plugin = { counters = { hits = 2 }, tables = { events = 'first' } } }
for i = 1, 3 do self.ctx.bw.request_id = tostring(i); self.ctx.bw.metrics.plugin.tables.events = i; assert(self:log().ok) end
emit({ rows = LRU:get('requests'), counter = LRU:get('plugin_counter_hits'), events = LRU:get('plugin_table_events'), logs = LOGS })
""")
    assert [row["id"] for row in out["rows"]] == ["2", "3"]
    assert out["rows"][0]["date"] == 42
    assert out["rows"][0]["synced"] is False
    assert out["counter"]["value"] == out["counter"]["increments"] == 6
    assert out["events"] == [2, 3]
    assert any("buffer_drop" in line for line in out["logs"])


def test_log_preserves_parser_method_and_truncates_url_at_utf8_boundary():
    out = run(r"""
REASON, COUNTRY = 'modsecurity-body', nil
ngx.var.request = 'POST /test HTTP/1.1'
self.ctx.bw.request_uri = string.rep('x', 508) .. string.char(0xc3, 0xa9) .. string.rep('z', 20)
self:log()
local row = LRU:get('requests')[1]
emit({ method = row.method, url = row.url, country = row.country, synced = row.synced, logs = LOGS })
""")
    assert out["method"] == "POST"
    assert out["url"] == "x" * 508 + "..."
    assert out["country"] == "unknown" and out["synced"] is True
    assert "lookup failed" in out["logs"][0]


def test_log_disabled_default_bypass_and_settings_failure():
    out = run(r"""
self.variables.USE_METRICS = 'no'
local disabled = self:log()
local bypass = self:log_default()
NEEDED = false
local unused = self:log_default()
NEEDED = nil
local failed = self:log_default()
emit({ disabled = disabled, bypass = bypass, unused = unused, failed = failed, rows = LRU:get('requests') })
""")
    assert out["disabled"]["message"] == "metrics are disabled"
    assert out["bypass"]["ok"] is True and len(out["rows"]) == 1
    assert out["unused"]["message"] == "metrics not used"
    assert out["failed"]["ok"] is False and "settings unavailable" in out["failed"]["message"]


def test_init_workers_merges_deduplicates_caps_and_restores_only_own_worker():
    out = run(r"""
LRU:set('requests', { {id = 'same', synced = true}, {id = 'new', synced = false} })
VALUES.requests_0 = json.encode({ {id = 'old'}, {id = 'same', synced = false} })
VALUES.other_1, VALUES.setup_0 = 'wrong worker', 'ignored'
VALUES.plugin_counter_hits_0 = '8'
self.variables.MAX_LRU_HISTORY = '4'
local result = self:init_workers()
emit({ result = result, rows = LRU:get('requests'), counter = LRU:get('plugin_counter_hits'), other = LRU:get('other'), setup = LRU:get('setup'), capacity = LRU:capacity() })
""")
    assert out["result"]["ok"] is True and out["capacity"] == 4
    assert [row["id"] for row in out["rows"]] == ["same", "new"]
    assert out["rows"][0]["synced"] is True
    assert out["counter"]["value"] == 8
    assert "other" not in out and "setup" not in out


@pytest.mark.parametrize("cap,error,expected", [("0", False, 1000), ("invalid", False, 1000), ("2", True, 1000), ("2k", False, 2000)])
def test_init_workers_default_resize_and_allocation_failure(cap, error, expected):
    out = run(
        "self.variables.MAX_LRU_HISTORY = CAP; RESIZE_ERROR = FAIL; local r = self:init_workers(); emit({r = r, capacity = LRU:capacity(), logs = LOGS})",
        CAP=cap,
        FAIL=error,
    )
    assert out["capacity"] == expected and out["r"]["ok"] is True
    if error:
        assert "allocation failed" in out["logs"][0]


@pytest.mark.parametrize("failure,reconnect,expected_calls", [("OOM command", False, 1), ("closed", False, 2), ("closed", True, 1), ("ERR denied", False, 2)])
def test_redis_call_oom_breaker_reconnect_and_nonconnection_errors(failure, reconnect, expected_calls):
    out = run(
        r"""
local n = 0
REPLY = function() n = n + 1 if n == 1 then return false, FAILURE end return 'OK' end
CONNECT_ERROR = RECONNECT_FAIL
local first, err = self:redis_call('get', 'key')
local second = self:redis_call('get', 'other')
emit({ first = first, error = err, second = second, calls = #CALLS, connects = CONNECTS or 0, closes = CLOSES or 0 })
""",
        FAILURE=failure,
        RECONNECT_FAIL=reconnect,
    )
    assert out["calls"] == expected_calls + (1 if failure == "closed" and not reconnect else 0)
    if failure.startswith("OOM") or reconnect:
        assert out["first"] is False and out["second"] is False
    elif failure == "closed":
        assert out["first"] == out["second"] == "OK"
        assert out["connects"] == out["closes"] == 1
    else:
        assert out["first"] is False and out["error"] == failure and out["second"] == "OK"


@pytest.mark.parametrize("redis,failure,ban_time,ttl", [(False, False, 30, 90), (True, False, 30, 90), (True, True, 30, 90), (True, False, 0, 0)])
def test_store_ban_evidence_keeps_payload_retention_and_queues_failed_redis(redis, failure, ban_time, ttl):
    out = run(
        r"""
self.use_redis, CONNECT_ERROR = USE_REDIS, FAIL
local summary = self:store_ban_evidence({ { id = 'event' } }, { reason = 'test', ban_time = BAN_TIME })
local key = 'ban_evidence:' .. summary.ban_id .. ':data'
emit({ summary = summary, evidence = json.decode(VALUES[key]), ttl = TTLS[key], queue = QUEUE, calls = CALLS, closes = CLOSES or 0 })
""",
        USE_REDIS=redis,
        FAIL=failure,
        BAN_TIME=ban_time,
    )
    assert out["summary"]["event_count"] == 1
    assert out["evidence"]["events"] == [{"id": "event"}]
    assert out["ttl"] == ttl
    assert bool(out["queue"]) == failure
    if redis and not failure:
        assert out["calls"][0][0] == "set" and out["calls"][0][3] == "NX"
        assert out["calls"][0][4:] == (["EX", ttl] if ttl else [])


def test_ban_evidence_storage_pressure_never_prevents_ban_summary():
    out = run(r"""
self.use_redis, WRITE_ERROR, CONNECT_ERROR = true, 'no memory', true
local summary = self:store_ban_evidence({}, { ban_time = 30 })
emit({ summary = summary, logs = LOGS, queue = QUEUE })
""")
    assert out["summary"]["ban_id"] and out["summary"]["event_count"] == 0
    assert not out["queue"]
    assert any("ban_evidence_local" in line for line in out["logs"])
    assert any("ban_evidence_redis" in line for line in out["logs"])


def test_timer_local_storage_and_errors_keep_observable_state():
    out = run(r"""
LRU:set('plugin_table_events', {'old', 'new'})
local first = self:timer()
local stored = json.decode(VALUES.plugin_table_events_0)
WRITE_ERROR = 'disk failed'
local failed = self:timer()
WRITE_ERROR = 'no memory'
local pressure = self:timer()
emit({ first = first, stored = stored, failed = failed, pressure = pressure, purged = LRU:get('plugin_table_events') == nil, logs = LOGS })
""")
    assert out["first"]["ok"] is True and out["stored"] == ["old", "new"]
    assert out["failed"] == {"ok": False, "message": "disk failed"}
    assert out["pressure"]["ok"] is True and out["purged"] is True
    assert any("halved LRU key" in line for line in out["logs"])
    assert any("purging LRU key" in line for line in out["logs"])


def test_timer_disabled_failed_settings_and_failed_redis_connection():
    out = run(r"""
NEEDED = nil
local missing = self:timer()
NEEDED = false
local disabled = self:timer()
NEEDED, self.use_redis, CONNECT_ERROR = true, true, true
LRU:set('example', 'retained')
local fallback = self:timer()
emit({ missing = missing, disabled = disabled, fallback = fallback, stored = VALUES.example_0, closes = CLOSES, logs = LOGS })
""")
    assert out["missing"]["ok"] is False
    assert out["disabled"]["message"] == "metrics not used"
    assert out["fallback"]["ok"] is True and out["stored"] == "retained" and out["closes"] == 1
    assert "redis_connect" in out["logs"][0]


@pytest.mark.parametrize("ttl_error,redis_error,queue_error", [(False, False, False), (True, False, False), (False, True, False), (False, True, True)])
def test_timer_recovers_ban_evidence_or_requeues_until_redis_recovers(ttl_error, redis_error, queue_error):
    out = run(
        r"""
self.use_redis = true
VALUES['ban_evidence:retry:data'], TTLS['ban_evidence:retry:data'] = '{"event_count":1}', 30.2
QUEUE, TTL_ERROR, QUEUE_ERROR = {'retry'}, FAIL_TTL, FAIL_QUEUE
REPLY = function(method)
    if method == 'set' and FAIL_REDIS then return false, 'ERR denied' end
    if method == 'eval' then return 1 end
    return true
end
local result = self:timer()
emit({ result = result, queue = QUEUE, calls = CALLS, logs = LOGS, closes = CLOSES })
""",
        FAIL_TTL=ttl_error,
        FAIL_REDIS=redis_error,
        FAIL_QUEUE=queue_error,
    )
    assert out["result"]["ok"] is True and out["closes"] == 1
    failed = ttl_error or redis_error
    assert bool(out["queue"]) == (failed and not queue_error)
    if failed:
        assert any("ban_evidence_recovery" in line for line in out["logs"])
    else:
        saved = next(call for call in out["calls"] if call[0] == "set")
        assert saved[3:] == ["NX", "EX", 31]
    if queue_error:
        assert any("Can't requeue" in line for line in out["logs"])


@pytest.mark.parametrize("push_error", [False, True])
def test_timer_syncs_reports_and_keeps_uncertain_payload_for_retry(push_error):
    out = run(
        r"""
self.use_redis = true
LRU:set('requests', { { id = 'report', status = 403, synced = false } })
REPLY = function(method, script)
    if method == 'llen' then return 1 end
    if method == 'eval' and script:find('local nb =', 1, true) then
        if FAIL_PUSH then return false, 'ERR denied' end
        return {1, 0}
    end
    if method == 'eval' then return 1 end
    return true
end
local result = self:timer()
emit({ result = result, row = LRU:get('requests')[1], stored = json.decode(VALUES.requests_0), logs = LOGS, closes = CLOSES })
""",
        FAIL_PUSH=push_error,
    )
    assert out["result"]["ok"] is True and out["closes"] == 1
    assert out["row"]["synced"] == (not push_error)
    assert out["stored"][0]["synced"] == (not push_error)
    if push_error:
        assert '"id":"report"' in out["row"]["redis_retry_json"]
        assert any("sync_request" in line for line in out["logs"])
    else:
        assert "redis_retry_json" not in out["row"]
        assert any("facets require rebuilding" in line for line in out["logs"])


def test_initialize_uses_subsystem_specific_dictionary():
    assert run("emit({ stream = self.metrics_datastore.dict == ngx.shared.metrics_datastore_stream })", subsystem="stream") == {"stream": True}
