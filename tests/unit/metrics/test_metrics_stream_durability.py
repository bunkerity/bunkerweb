"""Stream write-through is durable within its bounded per-window persistence budget.

The Stream buffer lives in the worker's own Lua VM and used to reach shared memory only on the
recurrent 5 s timer tick -- a tick that is explicitly skipped when the worker is exiting
(``premature``). Every NGINX reload therefore threw away the reports of every session blocked
since the last tick, which is exactly what ``example-stream-multisite`` observed: the preread
deny was logged and the report never arrived.

The real shipped source of ``metrics:log()`` and ``persist_stream_reports()`` is extracted and
run, so the write-through cannot be removed without failing here.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
METRICS_LUA = ROOT / "src" / "common" / "core" / "metrics" / "metrics.lua"

LUA = shutil.which("lua") or shutil.which("luajit")
needs_lua = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")


def _extract(name: str) -> str:
    source = METRICS_LUA.read_text(encoding="utf-8")
    match = re.search(rf"^local function {name}\(.*?^end$", source, re.S | re.M)
    assert match, f"{name} not found in metrics.lua — did it get renamed?"
    return match.group(0)


def _extract_block(first: str, last: str) -> str:
    """Return a run of module-level declarations verbatim, so the test tracks the real values."""
    source = METRICS_LUA.read_text(encoding="utf-8")
    match = re.search(rf"^local {first} = .*?^local {last} = .*?$", source, re.S | re.M)
    assert match, f"{first}..{last} not found in metrics.lua"
    return match.group(0)


def _extract_method(name: str) -> str:
    source = METRICS_LUA.read_text(encoding="utf-8")
    match = re.search(rf"^function metrics:{name}\(.*?^end$", source, re.S | re.M)
    assert match, f"metrics:{name}() not found"
    return match.group(0)


# Everything metrics:log() closes over, stubbed as dumbly as possible: the point is to run the
# real control flow of the report branch, not to reimplement any of it.
SNAPSHOT_PREAMBLE = """
local stream_snapshot_key = nil
local stream_snapshot_nonce = nil
local stream_snapshot_sequence = 0
local stream_restore_pending = false
local utils = { rand = function() return "nonce" end }
local LIVE_PIDS = {}
local signal = { kill = function(pid)
    if LIVE_PIDS[pid] then return true end
    return nil, "No such process"
end }
"""

PREAMBLE = """
local table_insert = table.insert
local table_remove = table.remove
local ERR, WARN = "ERR", "WARN"
local time = function() return 1700000000 end
local subsystem = "stream"
local MAX_STORED_URL = 2048
local MAX_STORED_USER_AGENT = 512
local CACHE_STATUS_VALUES = { HIT = true, MISS = true }
local function bound(value, limit) if #value > limit then return value:sub(1, limit) end return value end
local function parse_count(value) return tonumber(value) end
local function should_sample() return false end
local function template_uri(uri) return uri end
local function accumulate_timer(acc) return acc end
local function crc32_short() return 0 end
local PID = 1234
local function worker_pid() return PID end
local STREAM_STORE, METRICS_STORE = {}, {}
local SET_ERROR = nil
local function encode(value)
    if type(value) ~= "table" then error("not a table") end
    local ids = {}
    for _, request in ipairs(value) do ids[#ids + 1] = tostring(request.id) end
    return table.concat(ids, ",")
end
local LRU = {}
local lru = {
    get = function(_, key) return LRU[key] end,
    set = function(_, key, value) LRU[key] = value end,
}
local NGX_VARS = {}
local ngx = { var = setmetatable({}, { __index = function(_, key) return NGX_VARS[key] end }), status = 0 }
local CLOCK = 0
local function ngx_now() return CLOCK end
local REASON = { "blacklist", { id = "ip" }, "detect" }
local function get_reason() return REASON[1], REASON[2], REASON[3] end
local THROTTLED = {}
local SELF = {
    variables = { USE_METRICS = "yes", METRICS_MAX_BLOCKED_REQUESTS = "1000", METRICS_BASELINE_SAMPLE_RATE = "0" },
    use_redis = false,
    ctx = { bw = { request_id = "rid-1", start_time = 1700000000, remote_addr = "192.168.0.1", server_name = "app1.example.com", protocol = "tcp" } },
    ret = function(_, ret, msg) return ret, msg end,
    log_throttled = function(_, level, key, msg) table_insert(THROTTLED, level .. ":" .. key .. ":" .. msg) end,
    metrics_datastore = {
        set = function(_, key, value) METRICS_STORE[key] = value return true, "success" end,
        delete = function(_, key) METRICS_STORE[key] = nil return true, "success" end,
    },
    stream_reports_datastore = {
        delete = function(_, key) STREAM_STORE[key] = nil return true end,
        set = function(_, key, value)
            if SET_ERROR then return false, SET_ERROR end
            STREAM_STORE[key] = value
            return true, "success"
        end,
    },
}
local metrics = {}
local stream_requests = {}
local inflight_stream_requests = nil
"""


def _run(body: str) -> str:
    assert LUA is not None
    script = "\n".join(
        (
            PREAMBLE,
            SNAPSHOT_PREAMBLE,
            _extract("stream_requests_key"),
            _extract("persist_stream_reports"),
            _extract_block("STREAM_PERSIST_BUDGET", "persist_window_writes"),
            _extract("claim_persist_budget"),
            _extract_method("log"),
            body,
        )
    )
    result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    return result.stdout.strip()


@needs_lua
def test_blocked_stream_session_reaches_shm_before_log_returns():
    """The regression: nothing may depend on the next timer tick for durability."""
    output = _run("""
        NGX_VARS.status = "444"
        metrics.log(SELF)
        print("shm=" .. tostring(STREAM_STORE[stream_snapshot_key or "stream_requests_1234"]))
        print("throttled=" .. #THROTTLED)
        """)
    assert output.splitlines() == ["shm=rid-1", "throttled=0"]


@needs_lua
def test_second_blocked_session_rewrites_the_whole_queue():
    """The SHM copy is the queue, not the last report: a reload must restore both."""
    output = _run("""
        NGX_VARS.status = "444"
        metrics.log(SELF)
        SELF.ctx.bw.request_id = "rid-2"
        metrics.log(SELF)
        print("shm=" .. tostring(STREAM_STORE[stream_snapshot_key or "stream_requests_1234"]))
        """)
    assert output == "shm=rid-1,rid-2"


@needs_lua
def test_no_reason_writes_nothing():
    """An ordinary session must not pay for the write-through."""
    output = _run("""
        REASON = { nil, nil, nil }
        metrics.log(SELF)
        print("shm=" .. tostring(STREAM_STORE[stream_snapshot_key or "stream_requests_1234"]))
        """)
    assert output == "shm=nil"


@needs_lua
def test_shm_failure_is_reported_and_does_not_break_logging():
    """A full SHM costs the durability guarantee, never the request."""
    output = _run("""
        NGX_VARS.status = "444"
        SET_ERROR = "no memory"
        local ok, msg = metrics.log(SELF)
        print("ok=" .. tostring(ok) .. " msg=" .. tostring(msg))
        print(THROTTLED[1])
        """)
    assert output.splitlines() == [
        "ok=true msg=success",
        "ERR:stream_reports_store:can't set stream_requests_1234_nonce_1 : no memory",
    ]


@needs_lua
def test_write_through_keeps_an_in_flight_push_batch_durable():
    """The batch push_stream_reports() detached is still the SHM copy's responsibility.

    push_stream_reports() hands the buffer a fresh table and yields on the loopback POST, so the
    only durable record of that batch is the SHM key. A session blocked mid-POST must not
    overwrite it with itself alone -- that is the very loss this whole change exists to close,
    in a narrower window.
    """
    output = _run("""
        inflight_stream_requests = { { id = "batched-1" }, { id = "batched-2" } }
        NGX_VARS.status = "444"
        metrics.log(SELF)
        print("shm=" .. tostring(STREAM_STORE[stream_snapshot_key or "stream_requests_1234"]))
        """)
    assert output == "shm=batched-1,batched-2,rid-1"


@needs_lua
def test_both_probes_of_one_second_persist():
    """The budget must not cost the case it exists for: TCP and UDP land in the same second."""
    output = _run("""
        NGX_VARS.status = "444"
        metrics.log(SELF)
        SELF.ctx.bw.request_id = "rid-2"
        SELF.ctx.bw.protocol = "udp"
        metrics.log(SELF)
        print("shm=" .. tostring(STREAM_STORE[stream_snapshot_key or "stream_requests_1234"]))
        """)
    assert output == "shm=rid-1,rid-2"


@needs_lua
def test_a_flood_defers_reports_after_the_write_through_budget():
    """Past the budget reports remain in Lua; this test does not run the timer."""
    output = _run("""
        NGX_VARS.status = "444"
        for index = 1, 40 do
            SELF.ctx.bw.request_id = "rid-" .. index
            metrics.log(SELF)
        end
        local persisted = 0
        for _ in tostring(STREAM_STORE[stream_snapshot_key or "stream_requests_1234"]):gmatch("[^,]+") do persisted = persisted + 1 end
        print("persisted=" .. persisted)
        print("buffered=" .. #stream_requests)
        """)
    assert output.splitlines() == ["persisted=8", "buffered=40"]


@needs_lua
def test_the_budget_does_not_refill_inside_the_window():
    """Pins STREAM_PERSIST_WINDOW downward: shrinking it would make the ration meaningless."""
    output = _run("""
        NGX_VARS.status = "444"
        for index = 1, 40 do
            SELF.ctx.bw.request_id = "rid-" .. index
            metrics.log(SELF)
        end
        CLOCK = CLOCK + 0.05
        SELF.ctx.bw.request_id = "inside-window"
        metrics.log(SELF)
        print("last=" .. tostring(STREAM_STORE[stream_snapshot_key or "stream_requests_1234"]:match("[^,]+$")))
        """)
    assert output == "last=rid-8"


@needs_lua
def test_a_backwards_clock_step_does_not_wedge_the_ration():
    """ngx.now() is wall clock: an NTP step back must reopen the window, not freeze it."""
    output = _run("""
        NGX_VARS.status = "444"
        for index = 1, 40 do
            SELF.ctx.bw.request_id = "rid-" .. index
            metrics.log(SELF)
        end
        CLOCK = CLOCK - 30
        SELF.ctx.bw.request_id = "after-step-back"
        metrics.log(SELF)
        print("last=" .. tostring(STREAM_STORE[stream_snapshot_key or "stream_requests_1234"]:match("[^,]+$")))
        """)
    assert output == "last=after-step-back"


@needs_lua
def test_the_budget_refills_on_the_next_window():
    output = _run("""
        NGX_VARS.status = "444"
        for index = 1, 40 do
            SELF.ctx.bw.request_id = "rid-" .. index
            metrics.log(SELF)
        end
        CLOCK = CLOCK + 1
        SELF.ctx.bw.request_id = "after-window"
        metrics.log(SELF)
        print("last=" .. tostring(STREAM_STORE[stream_snapshot_key or "stream_requests_1234"]:match("[^,]+$")))
        """)
    assert output == "last=after-window"


# The restore half: a worker adopts the queues its dead predecessors left in SHM, and must
# retire the keys it adopted -- otherwise every later reload replays the same reports long
# after they were pushed and trimmed out of the HTTP-side queue.
RESTORE_PREAMBLE = """
local table_insert = table.insert
local ERR = "ERR"
local PID = 1234
local function worker_pid() return PID end
local SUBSYSTEM = "stream"
local subsystem = setmetatable({}, { __eq = function() return false end })
local STREAM_STORE, METRICS_STORE = {}, {}
local SET_ERROR = nil
local function encode(value)
    local ids = {}
    for _, request in ipairs(value) do ids[#ids + 1] = tostring(request.id) end
    return table.concat(ids, ",")
end
local function decode(value)
    if value == "<bad>" then error("invalid") end
    local requests = {}
    for id in tostring(value):gmatch("[^,]+") do requests[#requests + 1] = { id = id } end
    return requests
end
local BEFORE_SET = nil
local function make_store(data)
    return {
        keys = function()
            local keys = {}
            for key in pairs(data) do keys[#keys + 1] = key end
            table.sort(keys)
            return keys
        end,
        get = function(_, key) return data[key] end,
        set = function(_, key, value)
            if BEFORE_SET then local hook = BEFORE_SET; BEFORE_SET = nil; hook() end
            if SET_ERROR then return false, SET_ERROR end
            data[key] = value
            return true, "success"
        end,
        delete = function(_, key) data[key] = nil return true, "success" end,
    }
end
local THROTTLED = {}
local SELF = {
    metrics_datastore = make_store(METRICS_STORE),
    stream_reports_datastore = make_store(STREAM_STORE),
    log_throttled = function(_, level, key, msg) table_insert(THROTTLED, level .. ":" .. key .. ":" .. msg) end,
}
local stream_requests = {}
local inflight_stream_requests = nil
local function ids()
    local out = {}
    for _, request in ipairs(stream_requests) do out[#out + 1] = request.id end
    return table.concat(out, ",")
end
local function keys_of(data)
    local out = {}
    for key in pairs(data) do out[#out + 1] = key end
    table.sort(out)
    return table.concat(out, " ")
end
"""


def _run_restore(body: str, stream: bool = True) -> str:
    assert LUA is not None
    preamble = RESTORE_PREAMBLE.replace(
        "local subsystem = setmetatable({}, { __eq = function() return false end })",
        f'local subsystem = "{"stream" if stream else "http"}"',
    )
    script = "\n".join(
        (
            preamble,
            SNAPSHOT_PREAMBLE,
            _extract("stream_requests_key"),
            _extract("persist_stream_reports"),
            _extract("restore_stream_reports"),
            body,
        )
    )
    result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    return result.stdout.strip()


@needs_lua
def test_restore_adopts_dead_workers_queues_and_retires_their_keys():
    output = _run_restore("""
        STREAM_STORE["stream_requests_1000"] = "rid-1,rid-2"
        METRICS_STORE["stream_requests_1001"] = "rid-2,rid-3"
        print("ok=" .. tostring(restore_stream_reports(SELF)))
        print("live=" .. ids())
        print("stream_keys=" .. keys_of(STREAM_STORE))
        print("metrics_keys=" .. keys_of(METRICS_STORE))
        """)
    assert output.splitlines() == [
        "ok=true",
        "live=rid-2,rid-3,rid-1",
        "stream_keys=stream_requests_1234_nonce_1",
        "metrics_keys=",
    ]


@needs_lua
def test_restore_keeps_the_stale_keys_when_the_claim_fails():
    """Losing the SHM write must not also lose the reports it failed to claim."""
    output = _run_restore("""
        STREAM_STORE["stream_requests_1000"] = "rid-1"
        SET_ERROR = "no memory"
        print("ok=" .. tostring(restore_stream_reports(SELF)))
        print("stream_keys=" .. keys_of(STREAM_STORE))
        print(THROTTLED[1])
        """)
    assert output.splitlines() == [
        "ok=false",
        "stream_keys=stream_requests_1000",
        "ERR:stream_reports_store:can't set stream_requests_1234_nonce_1 : no memory",
    ]


@needs_lua
def test_http_side_restore_leaves_every_key_in_place():
    """api_ingest_stream_reports() owns the HTTP queue's generations; the timer must not race it."""
    output = _run_restore(
        """
        STREAM_STORE["stream_requests_1000"] = "rid-1"
        print("ok=" .. tostring(restore_stream_reports(SELF)))
        print("stream_keys=" .. keys_of(STREAM_STORE))
        """,
        stream=False,
    )
    assert output.splitlines() == ["ok=true", "stream_keys=stream_requests_1000 stream_requests_1234"]


# The push half: while the POST yields, the detached batch exists nowhere but in SHM.
PUSH_PREAMBLE = """
local table_insert = table.insert
local table_remove = table.remove
local HTTP_OK = 200
local subsystem = "stream"
local STREAM_STORE, METRICS_STORE = {}, {}
local function ids_of(list)
    local out = {}
    for _, request in ipairs(list) do out[#out + 1] = tostring(request.id) end
    return table.concat(out, ",")
end
local function encode(value)
    if value.requests then return "payload:" .. ids_of(value.requests) end
    return ids_of(value)
end
local ACK_COUNT = 0
local function decode() return { status = "success", msg = { accepted = ACK_COUNT } } end
local function make_store(data)
    return {
        get = function(_, key) return data[key] end,
        set = function(_, key, value) data[key] = value return true, "success" end,
        delete = function(_, key) data[key] = nil return true, "success" end,
    }
end
local SELF = {
    metrics_datastore = make_store(METRICS_STORE),
    stream_reports_datastore = make_store(STREAM_STORE),
    log_throttled = function() end,
}
local function worker_pid() return 1234 end
local stream_requests = {}
local inflight_stream_requests = nil
local MID_FLIGHT = nil
local FAIL_POST = false
local internal_api = {
    request = function()
        -- Stands in for the cosocket yielding: this is the window in which the worker can be
        -- replaced by a reload, and in which log_stream() can append to the fresh buffer.
        if MID_FLIGHT then MID_FLIGHT() end
        if FAIL_POST then return nil, "connection refused" end
        return { status = 200, body = "ack" }
    end,
}
"""


def _run_push(body: str) -> str:
    assert LUA is not None
    script = "\n".join(
        (
            PUSH_PREAMBLE,
            SNAPSHOT_PREAMBLE,
            _extract("stream_requests_key"),
            _extract("persist_stream_reports"),
            _extract("push_stream_reports"),
            body,
        )
    )
    result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    return result.stdout.strip()


@needs_lua
def test_a_persist_during_the_post_still_writes_the_detached_batch():
    output = _run_push("""
        stream_requests = { { id = "r1" }, { id = "r2" } }
        ACK_COUNT = 2
        MID_FLIGHT = function()
            table_insert(stream_requests, { id = "mid" })
            persist_stream_reports(SELF)
        end
        print("pushed=" .. tostring((push_stream_reports(1000))))
        print("shm=" .. tostring(STREAM_STORE[stream_snapshot_key or "stream_requests_1234"]))
        """)
    assert output.splitlines() == ["pushed=true", "shm=r1,r2,mid"]


@needs_lua
def test_the_batch_leaves_the_in_flight_slot_once_it_is_acknowledged():
    """Otherwise every later persist would keep re-writing reports the API already holds."""
    output = _run_push("""
        stream_requests = { { id = "r1" } }
        ACK_COUNT = 1
        push_stream_reports(1000)
        persist_stream_reports(SELF)
        print("shm=" .. tostring(STREAM_STORE[stream_snapshot_key or "stream_requests_1234"]))
        """)
    assert output == "shm="


@needs_lua
def test_a_failed_push_leaves_the_batch_in_the_buffer_and_not_in_the_slot():
    output = _run_push("""
        stream_requests = { { id = "r1" } }
        FAIL_POST = true
        print("pushed=" .. tostring((push_stream_reports(1000))))
        persist_stream_reports(SELF)
        print("shm=" .. tostring(STREAM_STORE[stream_snapshot_key or "stream_requests_1234"]))
        """)
    assert output.splitlines() == ["pushed=false", "shm=r1"]


@needs_lua
def test_retirement_preserves_a_sibling_write_between_read_and_delete():
    output = _run_restore("""
        LIVE_PIDS[1000] = true
        STREAM_STORE["stream_requests_1000"] = "r1"
        BEFORE_SET = function()
            STREAM_STORE["stream_requests_1000"] = "r1,r2"
        end
        assert(restore_stream_reports(SELF))
        local reachable = false
        for _, value in pairs(STREAM_STORE) do
            if value:find("r2", 1, true) then reachable = true end
        end
        print("reachable=" .. tostring(reachable))
        """)
    assert output == "reachable=true"


@needs_lua
def test_immutable_retirement_interleaves_two_real_writers():
    sibling = "\n".join(
        (
            "local sibling_persist; do",
            "local worker_pid = function() return 1000 end",
            "local stream_requests = {}; local inflight_stream_requests = nil",
            SNAPSHOT_PREAMBLE,
            _extract("stream_requests_key"),
            _extract("persist_stream_reports"),
            "sibling_persist = function(id) table.insert(stream_requests, { id = id }); assert(persist_stream_reports(SELF)); return stream_snapshot_key or stream_requests_key() end",
            "end",
        )
    )
    output = _run_restore(sibling + """
        local first_key = sibling_persist("r1")
        local second_key
        BEFORE_SET = function() second_key = sibling_persist("r2") end
        assert(restore_stream_reports(SELF))
        assert(STREAM_STORE[first_key] == nil)
        assert(STREAM_STORE[second_key] == "r1,r2")
        assert(STREAM_STORE[stream_snapshot_key] == "r1")
        -- The sibling can now die with no final timer: r2 is already in SHM.
        assert(restore_stream_reports(SELF))
        assert(STREAM_STORE[second_key] == nil)
        assert(STREAM_STORE[stream_snapshot_key]:find("r2", 1, true))
        print("reachable=true")
        """)
    assert output == "reachable=true"


@needs_lua
def test_failed_snapshot_publication_keeps_the_previous_snapshot():
    output = _run_restore("""
        stream_requests = { { id = "r1" } }
        assert(persist_stream_reports(SELF))
        local previous = stream_snapshot_key
        table.insert(stream_requests, { id = "r2" })
        SET_ERROR = "no memory"
        assert(not persist_stream_reports(SELF))
        assert(stream_snapshot_key == previous)
        assert(STREAM_STORE[previous] == "r1")
        SET_ERROR = nil
        assert(persist_stream_reports(SELF))
        assert(STREAM_STORE[previous] == nil)
        assert(STREAM_STORE[stream_snapshot_key] == "r1,r2")
        print("preserved=true")
        """)
    assert output == "preserved=true"


@needs_lua
def test_legacy_writer_is_adopted_only_after_exit_and_retried_by_timer():
    # Run the shipped timer's setup/restore block with setup already complete.
    timer = _extract_method("timer")
    start = timer.index('local setup = lru:get("setup")')
    end = timer.index("self.redis_ok = nil")
    retry = timer[start:end]
    output = _run_restore(
        """
        LIVE_PIDS[1000] = true
        STREAM_STORE["stream_requests_1000"] = "r1"
        assert(restore_stream_reports(SELF))
        assert(stream_restore_pending)
        STREAM_STORE["stream_requests_1000"] = "r1,r2"
        LIVE_PIDS[1000] = nil
        local lru = { get = function() return true end }
        local self = SELF
        """
        + retry
        + """
        assert(not stream_restore_pending)
        assert(STREAM_STORE["stream_requests_1000"] == nil)
        assert(STREAM_STORE[stream_snapshot_key]:find("r2", 1, true))
        print("retried=true")
        """
    )
    assert output == "retried=true"


@needs_lua
def test_legacy_probe_errors_leave_the_owner_key_untouched():
    output = _run_restore("""
        signal.kill = function() return nil, "Operation not permitted" end
        STREAM_STORE["stream_requests_1000"] = "r1"
        assert(restore_stream_reports(SELF))
        assert(stream_restore_pending)
        assert(STREAM_STORE["stream_requests_1000"] == "r1")
        assert(STREAM_STORE[stream_snapshot_key] == "")
        print("deferred=true")
        """)
    assert output == "deferred=true"
