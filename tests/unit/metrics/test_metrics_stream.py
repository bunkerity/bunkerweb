"""Unit tests for the Stream (TCP/UDP) half of the metrics plugin and its enforcement path.

Same split as ``test_metrics_timings.py``: what can be executed is executed from the shipped
source, the rest is pinned structurally.

The sender, receiver, and query methods depend only on things that can be stubbed, so their
real shipped source is extracted and run. That keeps the retry, validation, and deduplication
checks tied to the Lua that OpenResty executes.

The enforcement wiring lives in nginx ``*_by_lua_block`` confs, which cannot be loaded without
OpenResty, so those are asserted structurally.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
METRICS_LUA = ROOT / "src" / "common" / "core" / "metrics" / "metrics.lua"
HELPERS_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "helpers.lua"
BADBEHAVIOR_LUA = ROOT / "src" / "common" / "core" / "badbehavior" / "badbehavior.lua"
PREREAD_CONF = ROOT / "src" / "common" / "confs" / "server-stream" / "preread-stream-lua.conf"
INIT_STREAM_CONF = ROOT / "src" / "common" / "confs" / "init-stream-lua.conf"
ACCESS_CONF = ROOT / "src" / "common" / "confs" / "server-http" / "access-lua.conf"
ORDER_JSON = ROOT / "src" / "common" / "core" / "order.json"
SETTINGS_JSON = ROOT / "src" / "common" / "settings.json"
METRICS_HTTP_CONF = ROOT / "src" / "common" / "core" / "metrics" / "confs" / "http" / "metrics.conf"
METRICS_STREAM_CONF = ROOT / "src" / "common" / "core" / "metrics" / "confs" / "stream" / "metrics.conf"

LUA = shutil.which("lua") or shutil.which("luajit")
needs_lua = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")
LUA_LRUCACHE = LUA is not None and subprocess.run([LUA, "-e", 'assert(require "resty.lrucache")'], capture_output=True, text=True).returncode == 0
needs_lua_lrucache = pytest.mark.skipif(not LUA_LRUCACHE, reason="no stand-alone resty.lrucache on PATH")


def _extract(name: str) -> str:
    """Return the real source of a module-level local function from metrics.lua."""
    source = METRICS_LUA.read_text(encoding="utf-8")
    match = re.search(rf"^local function {name}\(.*?^end$", source, re.S | re.M)
    assert match, f"{name} not found in metrics.lua — did it get renamed?"
    return match.group(0)


def _extract_method(name: str) -> str:
    """Return the real source of one metrics method."""
    source = METRICS_LUA.read_text(encoding="utf-8")
    match = re.search(rf"^function metrics:{name}\(.*?^end$", source, re.S | re.M)
    assert match, f"metrics:{name}() not found"
    return match.group(0)


def _extract_script(name: str) -> str:
    source = METRICS_LUA.read_text(encoding="utf-8")
    match = re.search(rf"^local {name} = \[==\[\n(.*?)\n\]==\]$", source, re.S | re.M)
    assert match, f"{name} not found"
    return match.group(1)


# Stubs for everything push_stream_reports() closes over. Kept deliberately dumb: the point is
# to exercise the real control flow, not to reimplement the shared internal API helper.
PREAMBLE = """
local table_insert = table.insert
local table_remove = table.remove
local HTTP_OK = 200
local stream_requests = nil
local ENCODE_ERROR = false
local encode = function(payload)
    if ENCODE_ERROR then error("encode failed") end
    return "n=" .. tostring(#payload.requests)
end
local ACK = nil
local ACK_ERROR = false
local decode = function()
    if ACK_ERROR then error("invalid JSON") end
    return ACK
end
local LAST_REQUEST = nil
local RESPONSE = nil
local RESPONSE_ERR = nil
local REQUEST_ERROR = false
-- Stands in for the cosocket yielding: whatever this appends happens *while* the POST is in
-- flight, which is exactly when log_stream() can run in the same worker.
local ON_REQUEST = nil
local internal_api = {
    request = function(path, opts)
        if REQUEST_ERROR then error("helper exploded") end
        LAST_REQUEST = { path = path, opts = opts }
        if ON_REQUEST then ON_REQUEST() end
        return RESPONSE, RESPONSE_ERR
    end,
}
local function reset(n)
    stream_requests = {}
    for i = 1, n do
        table_insert(stream_requests, { id = "req" .. i, synced = false })
    end
    LAST_REQUEST = nil
    RESPONSE = { status = 200, body = "ack" }
    RESPONSE_ERR = nil
    ACK = { status = "success", msg = { accepted = n } }
    ACK_ERROR = false
    ENCODE_ERROR = false
    REQUEST_ERROR = false
    ON_REQUEST = nil
end
local function log_a_session(id)
    table_insert(stream_requests, { id = id, synced = false })
end
"""


def _run_lua(body: str) -> str:
    assert LUA is not None
    script = PREAMBLE + _extract("push_stream_reports") + "\n" + body
    result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    return result.stdout.strip()


METHOD_PREAMBLE = """
local metrics = {}
local table_insert = table.insert
local table_remove = table.remove
local match = string.match
local unescape_uri = function(value) return value end
local HTTP_OK = 200
local HTTP_BAD_REQUEST = 400
local HTTP_FORBIDDEN = 403
local HTTP_INTERNAL_SERVER_ERROR = 500
local HTTP_SERVICE_UNAVAILABLE = 503
local WORKER_ID = 0
local WORKER_PID = 0
local worker_id = function() return WORKER_ID end
local worker_pid = function() return WORKER_PID end
local buffers = { requests = {} }
local stream_requests = {}
local lru = {
    get = function(_, key) return buffers[key] end,
    set = function(_, key, value) buffers[key] = value end,
}
local STORE = {}
local STREAM_STORE = {}
local SET_CALLS = 0
local SET_ERROR = nil
local LOCKED = false
local LOCK_NEW_ERROR = nil
local LOCK_UNLOCK_ERROR = nil
local resty_lock = {
    new = function()
        if LOCK_NEW_ERROR then return nil, LOCK_NEW_ERROR end
        return {
            lock = function()
                if LOCKED then return nil, "timeout" end
                LOCKED = true
                return 0
            end,
            unlock = function()
                if LOCK_UNLOCK_ERROR then return nil, LOCK_UNLOCK_ERROR end
                LOCKED = false
                return true
            end,
        }
    end,
}
local function make_datastore(stream)
    return {
        keys = function()
            local data = stream and STREAM_STORE or STORE
            local keys = {}
            for key in pairs(data) do keys[#keys + 1] = key end
            table.sort(keys)
            return keys
        end,
        get = function(_, key)
            local data = stream and STREAM_STORE or STORE
            return data[key]
        end,
        set = function(_, key, value)
            SET_CALLS = SET_CALLS + 1
            if SET_ERROR then return false, SET_ERROR end
            local data = stream and STREAM_STORE or STORE
            data[key] = value
            return true, "success"
        end,
        delete = function(_, key)
            local data = stream and STREAM_STORE or STORE
            data[key] = nil
            return true, "success"
        end,
    }
end
local metrics_datastore = make_datastore(false)
local stream_reports_datastore = make_datastore(true)
local BODY_DATA = "body"
local BODY_FILE = nil
local FILE_BODY = "body"
local FILE_CLOSED = false
local io = {
    open = function(path)
        if path ~= BODY_FILE then return nil, "not found" end
        return {
            read = function() return FILE_BODY end,
            close = function() FILE_CLOSED = true end,
        }
    end,
}
local DECODED = { requests = {} }
local decode = function(value)
    if value == "body" then return DECODED end
    if type(value) == "table" then return value end
    error("invalid encoded value")
end
local encode = function(value) return value end
local ARGS = { start = "0", length = "-1" }
local ngx = {
    req = {
        read_body = function() end,
        get_body_data = function() return BODY_DATA end,
        get_body_file = function() return BODY_FILE end,
        get_uri_args = function() return ARGS end,
    },
}
local function parse_count(value) return tonumber(value) end
local SELF = {
    variables = { METRICS_MAX_BLOCKED_REQUESTS = "3" },
    use_redis = true,
    metrics_datastore = metrics_datastore,
    stream_reports_datastore = stream_reports_datastore,
    ctx = { bw = { uri = "/metrics/requests", request_method = "GET", remote_addr = "unix:" } },
    ret = function(_, ret, msg, status) return { ret = ret, msg = msg, status = status } end,
}
local function request(id, date)
    return {
        id = id,
        date = date or 1,
        status = 403,
        ip = "127.0.0.1",
        country = "local",
        -- Transport fixture: these tests exercise buffering, dedup and merging, not the
        -- protocol split, so a plain HTTP-shaped record keeps them protocol-agnostic. A real
        -- stream record carries no method and no url at all.
        method = "GET",
        url = "/",
        reason = "test",
        server_name = "service",
        security_mode = "block",
        user_agent = "",
        synced = false,
    }
end
local function reset_method()
    buffers = { requests = {} }
    stream_requests = {}
    STORE = {}
    STREAM_STORE = {}
    SET_CALLS = 0
    SET_ERROR = nil
    LOCKED = false
    LOCK_NEW_ERROR = nil
    LOCK_UNLOCK_ERROR = nil
    BODY_DATA = "body"
    BODY_FILE = nil
    FILE_BODY = "body"
    FILE_CLOSED = false
    DECODED = { requests = {} }
    ARGS = { start = "0", length = "-1" }
    SELF.variables.METRICS_MAX_BLOCKED_REQUESTS = "3"
    SELF.use_redis = true
    SELF.ctx.bw.uri = "/metrics/requests"
    SELF.ctx.bw.request_method = "GET"
    SELF.ctx.bw.remote_addr = "unix:"
end
"""


def _run_metrics_method(name: str, body: str, *helpers: str) -> str:
    assert LUA is not None
    source = METHOD_PREAMBLE + _extract("stream_requests_key") + "\n" + "\n".join(_extract(helper) for helper in helpers)
    script = source + "\n" + _extract_method(name) + "\n" + body
    result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    return result.stdout.strip()


def _lua_block(path: Path, directive: str) -> str:
    """Return the body of one ``<directive>_by_lua_block { ... }`` with comments stripped.

    Comments here quote the very calls the assertions below count, so leaving them in would
    let a test pass on prose after the code itself was removed.
    """
    source = path.read_text(encoding="utf-8")
    start = source.index(f"{directive}_by_lua_block")
    start = source.index("{", start)
    depth = 0
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                body = source[start + 1 : index]  # noqa: E203
                break
    else:  # pragma: no cover - unbalanced braces would be a syntax error anyway
        raise AssertionError(f"unbalanced braces around {directive}_by_lua_block in {path}")
    return "\n".join(line for line in body.split("\n") if not line.strip().startswith("--"))


# --- executed behaviour: the handover to the HTTP subsystem ------------------------------


@needs_lua
def test_an_acknowledged_batch_leaves_the_buffer_empty():
    out = _run_lua(
        """
        reset(3)
        local ok, msg = push_stream_reports()
        print(tostring(ok) .. "|" .. msg .. "|" .. #stream_requests .. "|" .. LAST_REQUEST.opts.body)
        """
    )
    ok, msg, remaining, body = out.split("|")
    assert ok == "true"
    assert msg == "pushed 3 stream reports"
    assert remaining == "0"
    assert body == "n=3", "the whole buffer must be sent, not a slice of it"


@needs_lua_lrucache
def test_stream_reports_survive_a_real_one_slot_lru_eviction():
    """A metric key may evict another metric key, never the Stream report queue."""
    shipped = METRICS_LUA.read_text(encoding="utf-8")
    assert "local stream_requests = {}" in shipped
    assert 'lru:get("stream_requests")' not in shipped
    source = """
        local table_insert = table.insert
        local table_remove = table.remove
        local HTTP_OK = 200
        local stream_requests = { { id = "stream-1", synced = false } }
        local lru = assert(require "resty.lrucache").new(1)
        assert(lru:set("other_metric", true))
        local encode = function(payload) return "n=" .. tostring(#payload.requests) end
        local decode = function() return { status = "success", msg = { accepted = 1 } } end
        local internal_api = {
            request = function(_, opts)
                return { status = 200, body = opts.body }
            end,
        }
    """
    source += _extract("push_stream_reports")
    source += '\nlocal ok, msg = push_stream_reports()\nprint(tostring(ok) .. "|" .. msg)'
    result = subprocess.run([LUA, "-"], input=source, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    assert result.stdout.strip() == "true|pushed 1 stream reports"


@needs_lua
def test_reports_logged_while_the_push_is_in_flight_are_not_dropped():
    """The send is not atomic: the cosocket yields, and log_stream() runs in the same worker.

    A naive "clear what I read" would drop a
    session that was logged mid-flight and never transmitted.
    """
    out = _run_lua(
        """
        reset(2)
        ON_REQUEST = function() log_a_session("late") end
        local ok = push_stream_reports(1000)
        local pending = stream_requests
        print(tostring(ok) .. "|" .. #pending .. "|" .. pending[1].id .. "|" .. LAST_REQUEST.opts.body)
        """
    )
    ok, remaining, first, body = out.split("|")
    assert ok == "true"
    assert remaining == "1", "the mid-flight session must survive"
    assert first == "late"
    assert body == "n=2", "only the batch taken before the send may be transmitted"


@needs_lua
def test_midflight_reports_are_persisted_before_an_immediate_reload():
    source = """
        local table_insert = table.insert
        local table_remove = table.remove
        local HTTP_OK = 200
        local stream_requests = { { id = "sent", synced = false } }
        local worker_pid = function() return 202 end
        local encode = function(value) return value end
        local decode = function() return { status = "success", msg = { accepted = 1 } } end
        local ON_REQUEST
        local internal_api = {
            request = function()
                ON_REQUEST()
                return { status = 200, body = "ack" }
            end,
        }
        local reports = {}
        local store = {
            set = function(_, key, value) reports[key] = value; return true end,
            get = function(_, key) return reports[key] end,
        }
        local self = { stream_reports_datastore = store, metrics_datastore = { delete = function() return true end } }
    """
    source += _extract("stream_requests_key")
    source += "\n" + _extract("push_stream_reports")
    source += "\n" + _extract("persist_stream_reports")
    source += """
        ON_REQUEST = function() table_insert(stream_requests, { id = "late", synced = false }) end
        assert(push_stream_reports(1000))
        assert(persist_stream_reports(self))
        local persisted = assert(store:get("stream_requests_202"))
        stream_requests = {}
        for _, request in ipairs(persisted) do table_insert(stream_requests, request) end
        print(stream_requests[1].id)
    """
    result = subprocess.run([LUA, "-"], input=source, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    assert result.stdout.strip() == "late"


@needs_lua
def test_stream_report_persistence_encode_failure_returns_the_timer_error_key():
    source = """
        local stream_requests = { { id = "pending" } }
        local worker_pid = function() return 202 end
        local encode = function() error("encode failed") end
        local self = {
            stream_reports_datastore = { set = function() error("must not store") end },
            metrics_datastore = { delete = function() error("must not delete") end },
        }
    """
    source += _extract("stream_requests_key")
    source += "\n" + _extract("persist_stream_reports")
    source += """
        local ok, err, key = persist_stream_reports(self)
        print(tostring(ok) .. "|" .. err .. "|" .. key)
    """
    result = subprocess.run([LUA, "-"], input=source, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    ok, error, key = result.stdout.strip().split("|")
    assert ok == "false"
    assert "encode failed" in error
    assert key == "stream_requests_202"


@needs_lua
def test_a_refused_batch_is_kept_for_the_next_tick():
    out = _run_lua(
        """
        reset(2)
        RESPONSE = { status = 503 }
        local ok, msg = push_stream_reports()
        print(tostring(ok) .. "|" .. msg .. "|" .. #stream_requests)
        """
    )
    ok, msg, remaining = out.split("|")
    assert ok == "false"
    assert "503" in msg
    assert remaining == "2", "a failed push must not lose the reports"


@needs_lua
def test_a_failed_push_puts_its_batch_back_in_front():
    """Restoring after the mid-flight arrivals would reorder the buffer, and the drop-oldest
    cap would then evict the newest reports instead of the oldest."""
    out = _run_lua(
        """
        reset(2)
        RESPONSE = { status = 503 }
        ON_REQUEST = function() log_a_session("late") end
        push_stream_reports(1000)
        local pending = stream_requests
        local ids = {}
        for _, request in ipairs(pending) do ids[#ids + 1] = request.id end
        print(table.concat(ids, ","))
        """
    )
    assert out == "req1,req2,late"


@needs_lua
def test_a_permanently_failing_push_stays_bounded():
    out = _run_lua(
        """
        reset(5)
        RESPONSE = { status = 503 }
        push_stream_reports(3)
        local pending = stream_requests
        local ids = {}
        for _, request in ipairs(pending) do ids[#ids + 1] = request.id end
        print(#pending .. "|" .. table.concat(ids, ","))
        """
    )
    remaining, ids = out.split("|")
    assert remaining == "3", "an API that stays down must not grow the buffer without bound"
    assert ids == "req3,req4,req5", "the cap drops the oldest, like every other buffer here"


@needs_lua
def test_an_unreachable_api_keeps_the_batch():
    out = _run_lua(
        """
        reset(2)
        RESPONSE = nil
        RESPONSE_ERR = "connection refused"
        local ok, msg = push_stream_reports()
        print(tostring(ok) .. "|" .. msg .. "|" .. #stream_requests)
        """
    )
    ok, msg, remaining = out.split("|")
    assert ok == "false"
    assert "connection refused" in msg
    assert remaining == "2"


@needs_lua
def test_nothing_is_sent_when_the_buffer_is_empty():
    out = _run_lua(
        """
        reset(0)
        local ok, msg = push_stream_reports()
        print(tostring(ok) .. "|" .. msg .. "|" .. tostring(LAST_REQUEST))
        """
    )
    ok, msg, request = out.split("|")
    assert ok == "true"
    assert msg == "no stream reports to push"
    assert request == "nil", "an empty tick must not cost a loopback request"


@needs_lua
def test_an_internal_api_failure_keeps_the_batch():
    out = _run_lua(
        """
        reset(2)
        REQUEST_ERROR = true
        local ok, msg = push_stream_reports()
        print(tostring(ok) .. "|" .. msg .. "|" .. #stream_requests)
        """
    )
    ok, msg, remaining = out.split("|")
    assert ok == "false"
    assert "helper exploded" in msg
    assert remaining == "2"


@needs_lua
def test_an_encoding_failure_keeps_the_batch_without_calling_the_api():
    out = _run_lua(
        """
        reset(2)
        ENCODE_ERROR = true
        local ok = push_stream_reports()
        print(tostring(ok) .. "|" .. #stream_requests .. "|" .. tostring(LAST_REQUEST))
        """
    )
    assert out.split("|") == ["false", "2", "nil"]


@needs_lua
def test_a_malformed_or_incomplete_ack_keeps_the_batch():
    out = _run_lua(
        """
        reset(2)
        ACK_ERROR = true
        local malformed = push_stream_reports()
        local after_malformed = #stream_requests
        ACK_ERROR = false
        ACK = { status = "success", msg = { accepted = 1 } }
        local incomplete = push_stream_reports()
        print(tostring(malformed) .. "|" .. tostring(incomplete) .. "|" .. after_malformed .. "|" .. #stream_requests)
        """
    )
    malformed, incomplete, after_malformed, remaining = out.split("|")
    assert malformed == "false"
    assert incomplete == "false"
    assert after_malformed == remaining == "2"


@needs_lua
def test_the_shared_internal_api_receives_only_request_specific_options():
    out = _run_lua(
        """
        reset(1)
        push_stream_reports()
        print(LAST_REQUEST.path .. "|" .. LAST_REQUEST.opts.method .. "|"
            .. LAST_REQUEST.opts.headers["Content-Type"] .. "|"
            .. tostring(LAST_REQUEST.opts.headers["Host"]) .. "|"
            .. tostring(LAST_REQUEST.opts.headers["Authorization"]))
        """
    )
    path, method, content_type, host, authorization = out.split("|")
    assert path == "/metrics/stream-reports"
    assert method == "POST"
    assert content_type == "application/json"
    assert host == authorization == "nil", "the shared helper owns transport authentication"


@needs_lua
def test_stream_ingest_reads_a_spooled_body_file_before_acknowledging():
    out = _run_metrics_method(
        "api_ingest_stream_reports",
        """
        reset_method()
        BODY_DATA = nil
        BODY_FILE = "/tmp/request-body"
        DECODED = { requests = { request("stream-1") } }
        local ret = metrics.api_ingest_stream_reports(SELF)
        print(ret.status .. "|" .. tostring(FILE_CLOSED) .. "|" .. ret.msg.accepted .. "|"
            .. ret.msg.installed .. "|" .. stream_requests[1].id .. "|" .. SET_CALLS .. "|"
            .. tostring(STREAM_STORE["stream_requests_0"] ~= nil) .. "|"
            .. tostring(STORE["stream_requests_0"] == nil))
        """,
    )
    status, closed, accepted, installed, request_id, set_calls, dedicated, legacy_empty = out.split("|")
    assert status == "200"
    assert closed == "true"
    assert accepted == installed == set_calls == "1"
    assert request_id == "stream-1"
    assert dedicated == legacy_empty == "true"


@needs_lua
def test_stream_ingest_rejects_a_public_api_caller_before_parsing():
    out = _run_metrics_method(
        "api_ingest_stream_reports",
        """
        reset_method()
        SELF.ctx.bw.remote_addr = "203.0.113.7"
        DECODED = { requests = { request("never-installed") } }
        local ret = metrics.api_ingest_stream_reports(SELF)
        print(ret.status .. "|" .. SET_CALLS .. "|" .. #stream_requests)
        """,
    )
    assert out.split("|") == ["403", "0", "0"]


@needs_lua
def test_stream_ingest_rejects_an_invalid_batch_atomically():
    out = _run_metrics_method(
        "api_ingest_stream_reports",
        """
        reset_method()
        stream_requests = { request("existing") }
        local live = stream_requests
        DECODED = { requests = { request("valid"), "invalid", request("never-installed") } }
        local ret = metrics.api_ingest_stream_reports(SELF)
        print(ret.status .. "|" .. #stream_requests .. "|" .. stream_requests[1].id
            .. "|" .. SET_CALLS .. "|" .. tostring(live == stream_requests))
        """,
    )
    status, remaining, request_id, set_calls, same_table = out.split("|")
    assert status == "400"
    assert (remaining, request_id, set_calls, same_table) == ("1", "existing", "0", "true")


@needs_lua
def test_stream_ingest_rejects_a_non_numeric_status_atomically():
    out = _run_metrics_method(
        "api_ingest_stream_reports",
        """
        reset_method()
        stream_requests = { request("existing") }
        local invalid = request("invalid")
        invalid.status = "403"
        DECODED = { requests = { request("valid"), invalid, request("never-installed") } }
        local ret = metrics.api_ingest_stream_reports(SELF)
        print(ret.status .. "|" .. #stream_requests .. "|" .. stream_requests[1].id
            .. "|" .. SET_CALLS)
        """,
    )
    assert out.split("|") == ["400", "1", "existing", "0"]


@needs_lua
def test_stream_ingest_returns_retryable_error_when_another_worker_holds_the_claim_lock():
    out = _run_metrics_method(
        "api_ingest_stream_reports",
        """
        reset_method()
        stream_requests = { request("existing") }
        LOCKED = true
        DECODED = { requests = { request("stream-1") } }
        local ret = metrics.api_ingest_stream_reports(SELF)
        print(ret.status .. "|" .. #stream_requests .. "|" .. stream_requests[1].id
            .. "|" .. SET_CALLS .. "|" .. tostring(LOCKED))
        """,
    )
    assert out.split("|") == ["503", "1", "existing", "0", "true"]


@needs_lua
def test_stream_ingest_deduplicates_a_lost_ack_replay_after_reload():
    out = _run_metrics_method(
        "api_ingest_stream_reports",
        """
        reset_method()
        DECODED = { requests = { request("stream-1"), request("stream-1"), request("stream-2") } }
        local first = metrics.api_ingest_stream_reports(SELF)
        stream_requests = {} -- worker-local buffer lost on reload; SHM remains
        local replay = metrics.api_ingest_stream_reports(SELF)
        local ids = {}
        for _, item in ipairs(stream_requests) do ids[#ids + 1] = item.id end
        print(first.msg.accepted .. "|" .. first.msg.installed .. "|" .. replay.status .. "|"
            .. replay.msg.accepted .. "|" .. replay.msg.installed .. "|" .. table.concat(ids, ","))
        """,
    )
    first_accepted, first_installed, status, accepted, installed, ids = out.split("|")
    assert (first_accepted, first_installed) == ("3", "2")
    assert (status, accepted, installed) == ("200", "3", "0")
    assert ids == "stream-1,stream-2"


@needs_lua
def test_stream_ingest_merges_old_pid_queue_without_an_old_timer_overwriting_new_generation():
    out = _run_metrics_method(
        "api_ingest_stream_reports",
        """
        reset_method()
        SELF.variables.METRICS_MAX_BLOCKED_REQUESTS = "10"
        WORKER_PID = 101
        STREAM_STORE["stream_requests_101"] = { request("old") }
        WORKER_PID = 202
        stream_requests = { request("live") }
        DECODED = { requests = { request("incoming") } }
        local first = metrics.api_ingest_stream_reports(SELF)
        -- An old timer completing after the handover can only recreate its own PID key.
        STREAM_STORE["stream_requests_101"] = { request("late") }
        DECODED = { requests = {} }
        local second = metrics.api_ingest_stream_reports(SELF)
        local ids = {}
        for _, item in ipairs(stream_requests) do ids[#ids + 1] = item.id end
        print(first.status .. "|" .. first.msg.installed .. "|" .. second.status .. "|"
            .. table.concat(ids, ",") .. "|" .. tostring(STREAM_STORE["stream_requests_101"] == nil))
        """,
    )
    assert out.split("|") == ["200", "1", "200", "late,old,live,incoming", "true"]


@needs_lua
def test_full_http_and_stream_queues_remain_independent():
    out = _run_metrics_method(
        "api_ingest_stream_reports",
        """
        reset_method()
        buffers.requests = { request("http-1"), request("http-2"), request("http-3") }
        stream_requests = { request("stream-1"), request("stream-2"), request("stream-3") }
        local live = stream_requests
        DECODED = { requests = { request("http-2"), request("stream-4") } }
        local ret = metrics.api_ingest_stream_reports(SELF)
        local http_ids, stream_ids = {}, {}
        for _, item in ipairs(buffers.requests) do http_ids[#http_ids + 1] = item.id end
        for _, item in ipairs(stream_requests) do stream_ids[#stream_ids + 1] = item.id end
        print(ret.msg.accepted .. "|" .. ret.msg.installed .. "|" .. table.concat(http_ids, ",")
            .. "|" .. table.concat(stream_ids, ",") .. "|" .. tostring(live == stream_requests))
        """,
    )
    accepted, installed, http_ids, stream_ids, same_table = out.split("|")
    assert (accepted, installed) == ("2", "1")
    assert http_ids == "http-1,http-2,http-3"
    assert stream_ids == "stream-2,stream-3,stream-4"
    assert same_table == "true", "the receiver must update the timer's live table in place"


@needs_lua
def test_stream_ingest_does_not_acknowledge_a_failed_shm_install():
    out = _run_metrics_method(
        "api_ingest_stream_reports",
        """
        reset_method()
        stream_requests = { request("existing") }
        SET_ERROR = "no memory"
        DECODED = { requests = { request("stream-1") } }
        local ret = metrics.api_ingest_stream_reports(SELF)
        print(ret.status .. "|" .. #stream_requests .. "|" .. stream_requests[1].id
            .. "|" .. tostring(LOCKED))
        """,
    )
    status, remaining, request_id, locked = out.split("|")
    assert (status, remaining, request_id, locked) == ("500", "1", "existing", "false")


@needs_lua
def test_request_query_and_legacy_get_merge_both_queues_by_id():
    body = """
        reset_method()
        STORE["requests_0"] = { request("http", 4), request("replay", 3) }
        STORE["stream_requests_0"] = { request("replay", 3), request("stream", 2) }
        STORE["stream_requests_1"] = { request("stream", 2), request("other", 1) }
        local query = metrics.api_requests_query(SELF)
        local legacy = metrics.api(SELF)
        print(query.msg.total .. "|" .. query.msg.filtered .. "|" .. #query.msg.data .. "|"
            .. query.msg.pane_counts.status["403"].total .. "|" .. #legacy.msg.requests)
    """
    # Both real methods share the same extraction helper, pinning legacy and query parity.
    source = METHOD_PREAMBLE + _extract("is_report") + "\n" + _extract("collect_buffered_requests")
    source += "\n" + _extract_method("api_requests_query") + "\n" + _extract_method("api") + "\n" + body
    result = subprocess.run([LUA, "-"], input=source, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    out = result.stdout.strip()
    assert out.split("|") == ["4", "4", "4", "4", "4"]


@needs_lua
def test_dedicated_stream_queue_survives_metrics_store_pressure():
    body = """
        reset_method()
        STREAM_STORE["stream_requests_0"] = { request("stream", 2) }
        STORE["requests_0"] = { request("http", 1) }
        STORE = {} -- unrelated metrics-dict eviction/pressure cannot touch the dedicated zone
        local query = metrics.api_requests_query(SELF)
        print(query.msg.total .. "|" .. #query.msg.data .. "|" .. query.msg.data[1].id)
    """
    source = METHOD_PREAMBLE + _extract("is_report") + "\n" + _extract("collect_buffered_requests")
    source += "\n" + _extract_method("api_requests_query") + "\n" + body
    result = subprocess.run([LUA, "-"], input=source, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    assert result.stdout.strip().split("|") == ["1", "1", "stream"]


def test_stream_handover_uses_dedicated_non_evicting_shared_dicts_in_both_subsystems():
    http_conf = METRICS_HTTP_CONF.read_text(encoding="utf-8")
    stream_conf = METRICS_STREAM_CONF.read_text(encoding="utf-8")
    source = METRICS_LUA.read_text(encoding="utf-8")
    assert "lua_shared_dict metrics_stream_reports " in http_conf
    assert "lua_shared_dict metrics_stream_reports_stream " in stream_conf
    assert "shared.metrics_stream_reports or shared.metrics_stream_reports_stream" in source
    assert "local worker_pid = worker.pid" in source
    assert 'return "stream_requests_" .. tostring(worker_pid())' in source
    assert "local function persist_stream_reports(self)" in source
    assert "self.stream_reports_datastore:set(key, reports)" in source
    assert "self.stream_reports_datastore:set(current_key, encoded_requests)" in source
    assert "self.stream_reports_datastore:set_with_retries" not in source
    assert 'key:match("^stream_requests_[0-9]+$")' in source
    assert "ipairs({ self.metrics_datastore, self.stream_reports_datastore })" in source
    assert 'subsystem == "http" and self.stream_reports_datastore or self.metrics_datastore' not in source


@needs_lua
def test_stream_sender_queue_survives_stream_metrics_store_pressure_and_reload():
    preamble = """
        local plugin = { initialize = function() end }
        local datastore = {
            new = function(_, dict)
                return {
                    dict = dict,
                    get = function(self, key) return self.dict[key] end,
                    set = function(self, key, value) self.dict[key] = value; return true end,
                }
            end,
        }
        local shared = {
            metrics_datastore = {},
            metrics_datastore_stream = {},
            metrics_stream_reports = {},
            metrics_stream_reports_stream = {},
        }
        local subsystem = "stream"
        local metrics = {}
        local SELF = {}
    """
    script = preamble + _extract_method("initialize")
    script += """
        metrics.initialize(SELF, {})
        SELF.stream_reports_datastore:set("stream_requests_0", "pending")
        SELF.metrics_datastore:set("unrelated_stream_metric_0", "pressure")
        for key in pairs(shared.metrics_datastore_stream) do
            shared.metrics_datastore_stream[key] = nil
        end
        print(SELF.stream_reports_datastore:get("stream_requests_0") .. "|"
            .. tostring(next(shared.metrics_datastore_stream) == nil) .. "|"
            .. tostring(SELF.stream_reports_datastore.dict == shared.metrics_stream_reports_stream))
    """
    result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    assert result.stdout.strip().split("|") == ["pending", "true", "true"]


@needs_lua
def test_a_missing_id_does_not_block_the_following_redis_report():
    preamble = """
        local ERR = "error"
        local table_remove = table.remove
        local REQUEST_FACET_FIELDS = {
            "ip", "country", "method", "url", "status", "reason", "server_name", "security_mode",
        }
        local PUSH_SCRIPT = "push"
        local encode = function(value) return value end
        local get_request_facet_value = function(request, field)
            return tostring(request[field] or "N/A")
        end
        local PUSHED = {}
        local SELF = {
            log_throttled = function() end,
            redis_call = function(_, method, script, key_count, list_key, ids_key, payload, id)
                PUSHED[#PUSHED + 1] = id
                return true
            end,
        }
        local rows = {
            { synced = false },
            { id = "valid", synced = false, status = 403 },
        }
    """
    script = preamble + _extract("sync_request_buffer")
    script += '\nsync_request_buffer(SELF, rows)\nprint(#rows .. "|" .. rows[1].id .. "|"'
    script += ' .. tostring(rows[1].synced) .. "|" .. PUSHED[1])'
    result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    assert result.stdout.strip().split("|") == ["1", "valid", "true", "valid"]


@needs_lua
def test_redis_push_deduplicates_ids_and_uses_oom_safe_cleanup_after_failures():
    preamble = """
        local LIST, IDS, FACETS = {}, {}, {}
        local MARKER = "1"
        local SADD_ERROR = false
        local HINCRBY_ERROR_FIELD = nil
        redis = {}
        function redis.call(command, ...)
            local args = { ... }
            if command == "GET" then return MARKER end
            if command == "SISMEMBER" then return IDS[args[2]] and 1 or 0 end
            if command == "RPUSH" then LIST[#LIST + 1] = args[2]; return #LIST end
            if command == "RPOP" then return table.remove(LIST) end
            if command == "SREM" then IDS[args[2]] = nil; return 1 end
            if command == "DEL" then
                for _, key in ipairs(args) do
                    if key == "requests:facets:initialized" then MARKER = nil end
                    if string.match(key, "^requests:facet:") then FACETS = {} end
                end
                return 1
            end
            if command == "SADD" then
                if SADD_ERROR then error("OOM") end
                local added = IDS[args[2]] and 0 or 1
                IDS[args[2]] = true
                return added
            end
            if command == "HINCRBY" then
                if args[1] == "requests:facet:" .. tostring(HINCRBY_ERROR_FIELD) and args[3] > 0 then
                    error("OOM")
                end
                local key = args[1] .. "|" .. args[2]
                FACETS[key] = (FACETS[key] or 0) + args[3]
                return FACETS[key]
            end
            error("unexpected command " .. command)
        end
        function redis.pcall(...)
            local ok, result = pcall(redis.call, ...)
            if ok then return result end
            return { err = result }
        end
        KEYS = { "requests", "requests:ids" }
        ARGV = { "json-1", "id-1", "ip", "country", "method", "url", "403", "reason", "service", "block" }
    """
    source = preamble + "\nlocal run = assert((loadstring or load)([====[\n"
    source += _extract_script("PUSH_SCRIPT") + "\n]====]))\n"
    source += """
        local first = run()
        local duplicate = run()
        ARGV[1], ARGV[2] = "json-2", "id-2"
        SADD_ERROR = true
        local failed_index = run()
        SADD_ERROR = false
        ARGV[1], ARGV[2] = "json-3", "id-3"
        HINCRBY_ERROR_FIELD = "country"
        local failed_facet = run()
        HINCRBY_ERROR_FIELD = nil
        local blocked_until_rebuild = run()
        print(first .. "|" .. duplicate .. "|" .. #LIST .. "|" .. tostring(IDS["id-1"])
            .. "|" .. tostring(IDS["id-2"]) .. "|" .. tostring(IDS["id-3"])
            .. "|" .. tostring(FACETS["requests:facet:ip|ip"])
            .. "|" .. tostring(FACETS["requests:facet:country|country"])
            .. "|" .. tostring(MARKER)
            .. "|" .. tostring(type(failed_index) == "table" and failed_index.err ~= nil)
            .. "|" .. tostring(type(failed_facet) == "table" and failed_facet.err ~= nil)
            .. "|" .. tostring(type(blocked_until_rebuild) == "table"
                and blocked_until_rebuild.err ~= nil))
    """
    result = subprocess.run([LUA, "-"], input=source, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    assert result.stdout.strip().split("|") == [
        "1",
        "0",
        "1",
        "true",
        "nil",
        "nil",
        "nil",
        "nil",
        "nil",
        "true",
        "true",
        "true",
    ]


def test_the_redis_id_index_is_trimmed_rebuilt_and_expired_with_requests():
    source = METRICS_LUA.read_text(encoding="utf-8")
    assert "redis.pcall('SREM', KEYS[2], tostring(req.id))" in _extract_script("TRIM_SCRIPT")
    assert "redis.pcall('SADD', KEYS[2], tostring(id))" in _extract_script("REBUILD_SCRIPT")
    assert 'self.clusterstore:call("expire", "requests:ids", ttl)' in source


@needs_lua
def test_a_malformed_redis_head_is_trimmed_instead_of_wedging_the_cap():
    preamble = """
        local LIST = { "malformed", "json-2", "json-3" }
        local MARKER = "1"
        cjson = {
            null = {},
            decode = function(raw)
                if raw == "malformed" then error("invalid json") end
                return { id = raw }
            end,
        }
        redis = {}
        function redis.call(command, ...)
            local args = { ... }
            if command == "LLEN" then return #LIST end
            if command == "SET" then MARKER = args[2]; return "OK" end
            if command == "DEL" then
                for _, key in ipairs(args) do
                    if key == "requests:facets:initialized" then MARKER = nil end
                end
                return 1
            end
            if command == "LRANGE" then return { LIST[1] } end
            if command == "LTRIM" then
                local kept = {}
                for i = args[2] + 1, #LIST do kept[#kept + 1] = LIST[i] end
                LIST = kept
                return "OK"
            end
            error("unexpected command " .. command)
        end
        function redis.pcall(...)
            local ok, result = pcall(redis.call, ...)
            if ok then return result end
            return { err = result }
        end
        KEYS = { "requests", "requests:ids" }
        ARGV = { "2" }
    """
    source = preamble + "\nlocal run = assert((loadstring or load)([====[\n"
    source += _extract_script("TRIM_SCRIPT") + "\n]====]))\n"
    source += """
        local failed = run()
        print(tostring(type(failed) == "table" and failed.err ~= nil) .. "|" .. #LIST .. "|"
            .. LIST[1] .. "|" .. tostring(MARKER))
    """
    result = subprocess.run([LUA, "-"], input=source, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    assert result.stdout.strip().split("|") == ["true", "2", "json-2", "nil"]


@needs_lua
def test_redis_rebuild_removes_legacy_duplicate_and_malformed_rows():
    preamble = """
        local LIST = { "a-old", "a-new", "b", "bad", "missing-id" }
        local IDS, FACETS, MARKER = {}, {}, nil
        cjson = {
            null = {},
            decode = function(raw)
                if raw == "bad" then error("invalid json") end
                if raw == "missing-id" then return {} end
                return {
                    id = raw:sub(1, 1), ip = raw, country = "country", method = "method",
                    url = "url", status = 403, reason = "reason", server_name = "service",
                    security_mode = "block",
                }
            end,
        }
        redis = {}
        function redis.call(command, ...)
            local args = { ... }
            if command == "DEL" then
                for _, key in ipairs(args) do
                    if key == "requests:ids" then IDS = {} end
                    if key == "requests:facets:initialized" then MARKER = nil end
                    if string.match(key, "^requests:facet:") then FACETS = {} end
                end
                return 1
            end
            if command == "SET" then MARKER = args[2]; return "OK" end
            if command == "LRANGE" then
                local copy = {}
                for i, raw in ipairs(LIST) do copy[i] = raw end
                return copy
            end
            if command == "SADD" then
                if IDS[args[2]] then return 0 end
                IDS[args[2]] = true
                return 1
            end
            if command == "LREM" then
                for i, raw in ipairs(LIST) do
                    if raw == args[3] then table.remove(LIST, i); return 1 end
                end
                return 0
            end
            if command == "HINCRBY" then
                local key = args[1] .. "|" .. args[2]
                FACETS[key] = (FACETS[key] or 0) + args[3]
                return FACETS[key]
            end
            error("unexpected command " .. command)
        end
        function redis.pcall(...)
            local ok, result = pcall(redis.call, ...)
            if ok then return result end
            return { err = result }
        end
        KEYS = { "requests", "requests:ids" }
    """
    source = preamble + "\nlocal run = assert((loadstring or load)([====[\n"
    source += _extract_script("REBUILD_SCRIPT") + "\n]====]))\n"
    source += """
        local kept = run()
        print(kept .. "|" .. table.concat(LIST, ",") .. "|" .. tostring(IDS.a) .. "|"
            .. tostring(IDS.b) .. "|" .. tostring(FACETS["requests:facet:ip|a-old"]) .. "|"
            .. tostring(FACETS["requests:facet:ip|a-new"]) .. "|" .. tostring(MARKER))
    """
    result = subprocess.run([LUA, "-"], input=source, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    assert result.stdout.strip().split("|") == ["2", "a-old,b", "true", "true", "1", "nil", "1"]


@needs_lua
def test_redis_trim_clears_partial_indexes_after_an_oom_failure():
    preamble = """
        local LIST = { "json-1", "json-2" }
        local IDS = { ["id-1"] = true, ["id-2"] = true }
        local FACETS = {
            ["requests:facet:ip|ip"] = 2,
            ["requests:facet:country|country"] = 2,
        }
        local MARKER = "1"
        local TRIMMED = false
        cjson = {
            null = {},
            decode = function()
                return {
                    id = "id-1", ip = "ip", country = "country", method = "method",
                    url = "url", status = 403, reason = "reason", server_name = "service",
                    security_mode = "block",
                }
            end,
        }
        redis = {}
        function redis.call(command, ...)
            local args = { ... }
            if command == "LLEN" then return #LIST end
            if command == "SET" then
                if args[1] == "requests:facets:initialized" then MARKER = args[2] end
                return "OK"
            end
            if command == "DEL" then
                for _, key in ipairs(args) do
                    if key == "requests:facets:initialized" then MARKER = nil end
                    if key == "requests:ids" then IDS = {} end
                    if string.match(key, "^requests:facet:") then FACETS = {} end
                end
                return 1
            end
            if command == "LRANGE" then return { LIST[1] } end
            if command == "SREM" then IDS[args[2]] = nil; return 1 end
            if command == "HINCRBY" then
                if args[1] == "requests:facet:country" and args[3] < 0 then error("OOM") end
                local key = args[1] .. "|" .. args[2]
                FACETS[key] = (FACETS[key] or 0) + args[3]
                return FACETS[key]
            end
            if command == "HDEL" then FACETS[args[1] .. "|" .. args[2]] = nil; return 1 end
            if command == "LTRIM" then TRIMMED = true; return "OK" end
            error("unexpected command " .. command)
        end
        function redis.pcall(...)
            local ok, result = pcall(redis.call, ...)
            if ok then return result end
            return { err = result }
        end
        KEYS = { "requests", "requests:ids" }
        ARGV = { "1" }
    """
    source = preamble + "\nlocal run = assert((loadstring or load)([====[\n"
    source += _extract_script("TRIM_SCRIPT") + "\n]====]))\n"
    source += """
        local failed = run()
        print(tostring(type(failed) == "table" and failed.err ~= nil) .. "|" .. #LIST .. "|"
            .. tostring(IDS["id-1"]) .. "|" .. tostring(IDS["id-2"]) .. "|"
            .. tostring(MARKER) .. "|" .. tostring(FACETS["requests:facet:ip|ip"]) .. "|"
            .. tostring(FACETS["requests:facet:country|country"]) .. "|" .. tostring(TRIMMED))
    """
    result = subprocess.run([LUA, "-"], input=source, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    assert result.stdout.strip().split("|") == ["true", "2", "nil", "nil", "nil", "nil", "nil", "false"]


@needs_lua
def test_redis_rebuild_clears_partial_indexes_after_id_or_facet_failure():
    preamble = """
        local IDS, FACETS = { stale = true }, { stale = 1 }
        local MARKER = "stale"
        local SADD_ERROR = true
        local HINCRBY_ERROR_FIELD = nil
        local ITEMS = { "json-1" }
        cjson = {
            null = {},
            decode = function()
                return {
                    id = "id-1", ip = "ip", country = "country", method = "method",
                    url = "url", status = 403, reason = "reason", server_name = "service",
                    security_mode = "block",
                }
            end,
        }
        redis = {}
        function redis.call(command, ...)
            local args = { ... }
            if command == "DEL" then
                for _, key in ipairs(args) do
                    if key == "requests:ids" then IDS = {} end
                    if key == "requests:facets:initialized" then MARKER = nil end
                    if string.match(key, "^requests:facet:") then FACETS = {} end
                end
                return 1
            end
            if command == "SET" then
                if args[1] == "requests:facets:initialized" then MARKER = args[2] end
                return "OK"
            end
            if command == "LRANGE" then return ITEMS end
            if command == "SADD" then
                if SADD_ERROR then error("OOM") end
                IDS[args[2]] = true
                return 1
            end
            if command == "HINCRBY" then
                if args[1] == "requests:facet:" .. tostring(HINCRBY_ERROR_FIELD) then error("OOM") end
                local key = args[1] .. "|" .. args[2]
                FACETS[key] = (FACETS[key] or 0) + args[3]
                return FACETS[key]
            end
            error("unexpected command " .. command)
        end
        function redis.pcall(...)
            local ok, result = pcall(redis.call, ...)
            if ok then return result end
            return { err = result }
        end
        KEYS = { "requests", "requests:ids" }
    """
    source = preamble + "\nlocal run = assert((loadstring or load)([====[\n"
    source += _extract_script("REBUILD_SCRIPT") + "\n]====]))\n"
    source += """
        local failed_id = run()
        local id_failure_clean = next(IDS) == nil and next(FACETS) == nil and MARKER == nil
        IDS, FACETS, MARKER = { stale = true }, { stale = 1 }, "stale"
        SADD_ERROR = false
        HINCRBY_ERROR_FIELD = "country"
        local failed_facet = run()
        print(tostring(type(failed_id) == "table" and failed_id.err ~= nil) .. "|"
            .. tostring(id_failure_clean) .. "|"
            .. tostring(type(failed_facet) == "table" and failed_facet.err ~= nil) .. "|"
            .. tostring(next(IDS) == nil) .. "|" .. tostring(next(FACETS) == nil) .. "|"
            .. tostring(MARKER))
    """
    result = subprocess.run([LUA, "-"], input=source, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    assert result.stdout.strip().split("|") == ["true", "true", "true", "true", "true", "nil"]


@needs_lua
def test_a_missing_redis_completion_marker_rebuilds_the_indexes():
    preamble = """
        local null = {}
        local ERR = "error"
        local REQUEST_FACET_FIELDS = {
            "ip", "country", "method", "url", "status", "reason", "server_name", "security_mode",
        }
        local TRIM_SCRIPT = "trim"
        local REBUILD_SCRIPT = "rebuild"
        local EVAL = nil
        local SELF = {
            redis_call = function(_, method, ...)
                local args = { ... }
                if method == "llen" then return 2 end
                if method == "get" then return nil end
                if method == "hlen" or method == "scard" then return 2 end
                if method == "eval" then EVAL = args; return true end
                error("unexpected method " .. method)
            end,
            log_throttled = function() end,
        }
    """
    script = preamble + _extract("self_heal_request_facets")
    script += '\nself_heal_request_facets(SELF)\nprint(EVAL[1] .. "|" .. EVAL[2] .. "|" .. EVAL[3] .. "|" .. EVAL[4])'
    result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    assert result.stdout.strip() == "rebuild|2|requests|requests:ids"


@needs_lua
def test_a_legacy_duplicate_id_rebuilds_the_indexes():
    preamble = """
        local null = {}
        local ERR = "error"
        local REQUEST_FACET_FIELDS = {
            "ip", "country", "method", "url", "status", "reason", "server_name", "security_mode",
        }
        local TRIM_SCRIPT = "trim"
        local REBUILD_SCRIPT = "rebuild"
        local EVAL = nil
        local SELF = {
            redis_call = function(_, method, ...)
                local args = { ... }
                if method == "llen" then return 3 end
                if method == "get" then return "1" end
                if method == "hlen" then return 2 end
                if method == "scard" then return 2 end
                if method == "eval" then EVAL = args; return true end
                error("unexpected method " .. method)
            end,
            log_throttled = function() end,
        }
    """
    script = preamble + _extract("self_heal_request_facets")
    script += '\nself_heal_request_facets(SELF)\nprint(EVAL[1] .. "|" .. EVAL[2] .. "|" .. EVAL[3] .. "|" .. EVAL[4])'
    result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    assert result.stdout.strip() == "rebuild|2|requests|requests:ids"


@needs_lua
def test_a_missing_non_ip_redis_facet_rebuilds_every_index():
    preamble = """
        local null = {}
        local ERR = "error"
        local REQUEST_FACET_FIELDS = {
            "ip", "country", "method", "url", "status", "reason", "server_name", "security_mode",
        }
        local TRIM_SCRIPT = "trim"
        local REBUILD_SCRIPT = "rebuild"
        local EVAL = nil
        local SELF = {
            redis_call = function(_, method, ...)
                local args = { ... }
                if method == "llen" then return 2 end
                if method == "get" then return "1" end
                if method == "hlen" then
                    if args[1] == "requests:facet:country" then return 0 end
                    return 2
                end
                if method == "scard" then return 2 end
                if method == "eval" then EVAL = args; return true end
                error("unexpected method " .. method)
            end,
            log_throttled = function() end,
        }
    """
    script = preamble + _extract("self_heal_request_facets")
    script += '\nself_heal_request_facets(SELF)\nprint(EVAL[1] .. "|" .. EVAL[2] .. "|" .. EVAL[3] .. "|" .. EVAL[4])'
    result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    assert result.stdout.strip() == "rebuild|2|requests|requests:ids"


# --- structural: the report path ----------------------------------------------------------


def test_metrics_runs_in_the_log_stream_phase():
    order = json.loads(ORDER_JSON.read_text(encoding="utf-8"))
    assert "metrics" in order["log_stream"], "no metrics in log_stream means no stream reports at all"


def test_the_operative_order_list_agrees_with_order_json():
    """settings.json is consumed *before* order.json in helpers.build_order, so editing only
    order.json leaves the shipped order untouched."""
    settings = json.loads(SETTINGS_JSON.read_text(encoding="utf-8"))
    operative = settings["PLUGINS_ORDER_LOG_STREAM"]["default"].split()
    order = json.loads(ORDER_JSON.read_text(encoding="utf-8"))["log_stream"]
    assert "metrics" in operative
    assert operative == order


def test_log_stream_reuses_the_log_report_path():
    source = METRICS_LUA.read_text(encoding="utf-8")
    match = re.search(r"^function metrics:log_stream\(\)\n(.*?)^end$", source, re.S | re.M)
    assert match, "metrics:log_stream() is gone"
    assert "self:log()" in match.group(1), "log_stream must not fork a second report path"


def test_the_stream_ingest_route_is_reachable_by_post():
    source = METRICS_LUA.read_text(encoding="utf-8")
    api = re.search(r"^function metrics:api\(\)\n(.*?)^end$", source, re.S | re.M)
    assert api, "metrics:api() is gone"
    body = api.group(1)
    assert 'request_method == "POST"' in body, "api() used to accept GET only"
    assert 'filter == "stream-reports"' in body
    assert "api_ingest_stream_reports" in body


def test_a_stream_block_keeps_its_real_session_status():
    """The report filter used to be 4xx-or-detect everywhere, so a stream block had to be pinned
    to 403 to survive it -- an HTTP code stored for a session that never had one. is_report()
    admits any non-HTTP row instead, and the raw session status is what gets persisted."""
    source = METRICS_LUA.read_text(encoding="utf-8")
    log_body = re.search(r"^function metrics:log\(bypass_checks\)\n(.*?)^end$", source, re.S | re.M)
    assert log_body
    code = "\n".join(line for line in log_body.group(1).split("\n") if not line.strip().startswith("--"))
    assert 'subsystem == "http"' in code, "status must be resolved per subsystem"
    assert "tonumber(ngx.var.status)" in code, "stream carries its session status in $status"
    assert "status = 403" not in code, "the 403 pin is what the protocol discriminator replaced"


def test_a_stream_row_is_a_report_whatever_its_status():
    """The read filter must not depend on a fabricated 4xx any more. Mirrors _report_clause()."""
    is_report = _extract("is_report")
    assert 'protocol ~= "http"' in is_report, "a non-HTTP row is a report by construction"
    assert "request.status >= 400 and request.status < 500" in is_report, "the HTTP arm stays 4xx-or-detect"
    assert 'request.security_mode == "detect"' in is_report


def test_stream_rows_carry_their_l4_dimensions_and_no_http_ones():
    """method/url/user_agent are HTTP notions; fill_ctx() still synthesizes them for plugins that
    branch on them in stream, but persisting them put "TCP" in a method column."""
    source = METRICS_LUA.read_text(encoding="utf-8")
    log_body = re.search(r"^function metrics:log\(bypass_checks\)\n(.*?)^end$", source, re.S | re.M)
    assert log_body
    code = log_body.group(1)
    for field, var in (
        ("listen_port", "ngx.var.server_port"),
        ("client_port", "ngx.var.remote_port"),
        ("bytes_sent", "ngx.var.bytes_sent"),
        ("bytes_received", "ngx.var.bytes_received"),
        ("session_time", "ngx.var.session_time"),
    ):
        assert f"request.{field} = tonumber({var})" in code, f"{field} must come from {var}"
    # The HTTP fields are set in the http branch only -- never in the table literal, which every
    # row shares.
    literal = code.split("local request = {")[1].split("}")[0]
    for field in ("method", "url", "user_agent"):
        assert field not in literal, f"{field} is HTTP-only and must not be set for every row"
    assert "request.method = self.ctx.bw.request_method" in code, "HTTP rows keep their method"
    assert 'protocol = subsystem == "http" and "http"' in code, "every row states its protocol"


def test_the_baseline_sampler_stays_http_only():
    source = METRICS_LUA.read_text(encoding="utf-8")
    assert (
        'if not reason and subsystem == "http" then' in source
    ), "the baseline models HTTP shape ($request_time, scheme, content-type); none of it exists for an L4 session"


# --- structural: enforcement --------------------------------------------------------------


def test_the_stream_preread_phase_honours_the_security_mode():
    body = _lua_block(PREREAD_CONF, "preread")
    assert "get_security_mode(ctx)" in body, "detect was ignored on stream: every detection blocked"
    assert 'security_mode == "block"' in body, "the deny must be conditional on the mode"
    assert 'security_mode == "detect"' in body


def test_the_stream_ban_path_records_its_payload_and_mode():
    body = _lua_block(PREREAD_CONF, "preread")
    assert (
        "set_reason(reason, reason_data, ctx, security_mode)" in body
    ), "the stream ban path used to pass an empty table and no mode, losing the report payload"
    assert "set_reason(reason, {}, ctx)" not in body


def test_a_detected_stream_plugin_never_assigns_a_status():
    """status is what closes the session at the end of the block — assigning it in detect mode
    would keep blocking under a configuration that asks not to."""
    body = _lua_block(PREREAD_CONF, "preread")
    detect = body.split('if security_mode == "detect" then')[1].split("elseif")[0]
    assert "set_reason(plugin_id, ret.data, ctx, security_mode)" in detect
    assert "status = ret.status" not in detect
    assert "return true" in detect


def test_the_http_detect_branch_records_a_reason_too():
    """Mode-unaware plugins (blacklist, country, dnsbl, greylist, reversescan) rely on this
    dispatcher branch; without set_reason their detections produced no Reports row at all."""
    body = _lua_block(ACCESS_CONF, "access")
    detect = body.split('if security_mode == "detect" then')[1].split("elseif")[0]
    assert "set_reason(plugin_id, ret.data, ctx, security_mode)" in detect
    assert "status = ret.status" not in detect


def test_stream_has_a_timer_phase():
    """Without init_worker_by_lua the stream subsystem has no timer, so badbehavior's queued
    increments were written to datastore_stream and never drained by anyone."""
    body = _lua_block(INIT_STREAM_CONF, "init_worker")
    assert "order.timer" in body
    assert 'call_plugin(plugin_obj, "timer")' in body
    assert "timer_at(5, recurrent_timer)" in body


def test_the_stream_timer_does_not_replay_the_http_worker_ceremony():
    """Running init_worker()/init_workers() a second time would re-run every plugin's worker
    setup in a subsystem that already has its own."""
    body = _lua_block(INIT_STREAM_CONF, "init_worker")
    assert "init_workers" not in body
    assert "misc_ready" not in body


def test_badbehavior_reads_the_session_status_in_stream():
    source = BADBEHAVIOR_LUA.read_text(encoding="utf-8")
    code = "\n".join(line for line in source.split("\n") if not line.strip().startswith("--"))
    assert (
        'subsystem == "http" and ngx.status or tonumber(var.status)' in code
    ), "ngx.status does not exist in stream: the gate matched the literal string 'nil' and never fired"
    assert "tostring(ngx.status)" not in code, "the raw HTTP-only read must be gone"


def test_stream_context_carries_what_the_plugins_require():
    """request_id is half the dedup key, so it must exist. method and url are synthesized for the
    plugins that branch on them in stream (workflows conditions, badbehavior) -- Reports no longer
    persists either, see test_stream_rows_carry_their_l4_dimensions_and_no_http_ones."""
    source = HELPERS_LUA.read_text(encoding="utf-8")
    stream_branch = source.split("data.scheme = var.scheme")[1].split("-- IP data : global")[0]
    code = "\n".join(line for line in stream_branch.split("\n") if not line.strip().startswith("--"))
    assert "data.request_id = rand(32)" in code
    assert "data.start_time = req.start_time()" in code
    assert "data.request_method = upper(var.protocol" in code
    assert "data.request_uri =" in code
    assert "data.uri =" not in code, (
        "filling uri would change what country/limit match on in stream — country:is_ignored_uri " "short-circuits on a nil uri today"
    )
