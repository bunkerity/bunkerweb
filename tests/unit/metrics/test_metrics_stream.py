"""Unit tests for the Stream (TCP/UDP) half of the metrics plugin and its enforcement path.

Same split as ``test_metrics_timings.py``: what can be executed is executed from the shipped
source, the rest is pinned structurally.

``push_stream_reports`` is module-level and depends only on things that can be stubbed (the
LRU, ``get_variable``, ``resty.http``), so **its real source is extracted and run** — the
drain/keep arithmetic is exactly the kind of off-by-one that silently loses or duplicates
reports, and it is the one piece here that no integration test would localize for you.

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

LUA = shutil.which("lua") or shutil.which("luajit")
needs_lua = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")


def _extract(name: str) -> str:
    """Return the real source of a module-level local function from metrics.lua."""
    source = METRICS_LUA.read_text(encoding="utf-8")
    match = re.search(rf"^local function {name}\(.*?^end$", source, re.S | re.M)
    assert match, f"{name} not found in metrics.lua — did it get renamed?"
    return match.group(0)


# Stubs for everything push_stream_reports() closes over. Kept deliberately dumb: the point is
# to exercise the real control flow, not to reimplement an HTTP client.
PREAMBLE = """
local table_insert = table.insert
local table_remove = table.remove
local buffer = nil
local lru = {
    get = function(_, key) if key == "requests" then return buffer end end,
    set = function(_, key, value) if key == "requests" then buffer = value end end,
}
local VARS = {}
local get_variable = function(name) return VARS[name] end
local encode = function(payload) return "n=" .. tostring(#payload.requests) end
local LAST_REQUEST = nil
local RESPONSE = nil
local RESPONSE_ERR = nil
-- Stands in for the cosocket yielding: whatever this appends happens *while* the POST is in
-- flight, which is exactly when log_stream() can run in the same worker.
local ON_REQUEST = nil
local http = {
    new = function()
        return {
            set_timeout = function() end,
            request_uri = function(_, url, opts)
                LAST_REQUEST = { url = url, opts = opts }
                if ON_REQUEST then ON_REQUEST() end
                return RESPONSE, RESPONSE_ERR
            end,
        }
    end,
}
local function reset(n, vars)
    buffer = {}
    for i = 1, n do
        table_insert(buffer, { id = "req" .. i })
    end
    VARS = vars or { API_LISTEN_HTTP = "yes", API_HTTP_PORT = "5000", API_SERVER_NAME = "bwapi", API_TOKEN = "" }
    LAST_REQUEST = nil
    RESPONSE = { status = 200 }
    RESPONSE_ERR = nil
    ON_REQUEST = nil
end
local function log_a_session(id)
    local pending = lru:get("requests") or {}
    table_insert(pending, { id = id })
    lru:set("requests", pending)
end
"""


def _run_lua(body: str) -> str:
    assert LUA is not None
    script = PREAMBLE + _extract("push_stream_reports") + "\n" + body
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
                body = source[start + 1 : index]
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
        print(tostring(ok) .. "|" .. msg .. "|" .. #buffer .. "|" .. LAST_REQUEST.opts.body)
        """
    )
    ok, msg, remaining, body = out.split("|")
    assert ok == "true"
    assert msg == "pushed 3 stream reports"
    assert remaining == "0"
    assert body == "n=3", "the whole buffer must be sent, not a slice of it"


@needs_lua
def test_reports_logged_while_the_push_is_in_flight_are_not_dropped():
    """The send is not atomic: the cosocket yields, and log_stream() runs in the same worker.

    lru:get() hands back the stored table itself, so a naive "clear what I read" would drop a
    session that was logged mid-flight and never transmitted.
    """
    out = _run_lua(
        """
        reset(2)
        ON_REQUEST = function() log_a_session("late") end
        local ok = push_stream_reports(1000)
        local pending = lru:get("requests")
        print(tostring(ok) .. "|" .. #pending .. "|" .. pending[1].id .. "|" .. LAST_REQUEST.opts.body)
        """
    )
    ok, remaining, first, body = out.split("|")
    assert ok == "true"
    assert remaining == "1", "the mid-flight session must survive"
    assert first == "late"
    assert body == "n=2", "only the batch taken before the send may be transmitted"


@needs_lua
def test_a_refused_batch_is_kept_for_the_next_tick():
    out = _run_lua(
        """
        reset(2)
        RESPONSE = { status = 503 }
        local ok, msg = push_stream_reports()
        print(tostring(ok) .. "|" .. msg .. "|" .. #buffer)
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
        local pending = lru:get("requests")
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
        local pending = lru:get("requests")
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
        print(tostring(ok) .. "|" .. msg .. "|" .. #buffer)
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
def test_reports_are_dropped_rather_than_hoarded_when_no_http_listener_exists():
    """Without an HTTP API there is no handover at all, so retrying forever would only grow."""
    out = _run_lua(
        """
        reset(4, { API_LISTEN_HTTP = "no" })
        local ok, msg = push_stream_reports()
        print(tostring(ok) .. "|" .. msg .. "|" .. #buffer .. "|" .. tostring(LAST_REQUEST))
        """
    )
    ok, msg, remaining, request = out.split("|")
    assert ok == "false"
    assert "API_LISTEN_HTTP" in msg
    assert remaining == "0"
    assert request == "nil"


@needs_lua
def test_the_token_is_sent_as_a_bearer_header_only_when_configured():
    out = _run_lua(
        """
        reset(1, { API_LISTEN_HTTP = "yes", API_HTTP_PORT = "5000", API_SERVER_NAME = "bwapi", API_TOKEN = "s3cret" })
        push_stream_reports()
        local with = LAST_REQUEST.opts.headers["Authorization"]
        reset(1)
        push_stream_reports()
        local without = LAST_REQUEST.opts.headers["Authorization"]
        print(tostring(with) .. "|" .. tostring(without))
        """
    )
    with_token, without_token = out.split("|")
    assert with_token == "Bearer s3cret"
    assert without_token == "nil"


@needs_lua
def test_the_configured_port_and_server_name_are_honoured():
    """The API rejects any request whose Host is not API_SERVER_NAME (api.conf), so a
    hardcoded host or port would make every push fail with a closed connection."""
    out = _run_lua(
        """
        reset(1, { API_LISTEN_HTTP = "yes", API_HTTP_PORT = "9999", API_SERVER_NAME = "custom-api", API_TOKEN = "" })
        push_stream_reports()
        print(LAST_REQUEST.url .. "|" .. LAST_REQUEST.opts.headers["Host"] .. "|" .. LAST_REQUEST.opts.method)
        """
    )
    url, host, method = out.split("|")
    assert url == "http://127.0.0.1:9999/metrics/stream-reports"
    assert host == "custom-api"
    assert method == "POST"


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


def test_a_stream_block_is_pinned_to_a_4xx_so_the_report_survives_the_read_filter():
    """_report_clause() and api_requests_query both keep a row only when it is 4xx or detect.
    get_deny_status() is 444 in stream, which is not an NGINX stream status at all."""
    source = METRICS_LUA.read_text(encoding="utf-8")
    log_body = re.search(r"^function metrics:log\(bypass_checks\)\n(.*?)^end$", source, re.S | re.M)
    assert log_body
    code = "\n".join(line for line in log_body.group(1).split("\n") if not line.strip().startswith("--"))
    assert 'subsystem == "http"' in code, "status must be resolved per subsystem"
    assert "tonumber(ngx.var.status)" in code, "stream carries its session status in $status"
    assert "status = 403" in code, "a stream block must not be persisted with a non-4xx status"


def test_the_baseline_sampler_stays_http_only():
    source = METRICS_LUA.read_text(encoding="utf-8")
    assert 'if not reason and subsystem == "http" then' in source, (
        "the baseline models HTTP shape ($request_time, scheme, content-type); none of it exists for an L4 session"
    )


# --- structural: enforcement --------------------------------------------------------------


def test_the_stream_preread_phase_honours_the_security_mode():
    body = _lua_block(PREREAD_CONF, "preread")
    assert "get_security_mode(ctx)" in body, "detect was ignored on stream: every detection blocked"
    assert 'security_mode == "block"' in body, "the deny must be conditional on the mode"
    assert 'security_mode == "detect"' in body


def test_the_stream_ban_path_records_its_payload_and_mode():
    body = _lua_block(PREREAD_CONF, "preread")
    assert "set_reason(reason, reason_data, ctx, security_mode)" in body, (
        "the stream ban path used to pass an empty table and no mode, losing the report payload"
    )
    assert "set_reason(reason, {}, ctx)" not in body


def test_a_detected_stream_plugin_never_assigns_a_status():
    """status is what closes the session at the end of the block — assigning it in detect mode
    would keep blocking under a configuration that asks not to."""
    body = _lua_block(PREREAD_CONF, "preread")
    detect = body.split('if security_mode == "detect" then')[1].split("elseif")[0]
    assert "set_reason(plugin_id, ret.data, ctx, security_mode)" in detect
    assert "status = ret.status" not in detect
    assert "break" in detect


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
    assert 'subsystem == "http" and ngx.status or tonumber(var.status)' in code, (
        "ngx.status does not exist in stream: the gate matched the literal string 'nil' and never fired"
    )
    assert "tostring(ngx.status)" not in code, "the raw HTTP-only read must be gone"


def test_stream_context_carries_what_reports_requires():
    """method and url are NOT NULL in bw_metrics_requests, and request_id is half the dedup key."""
    source = HELPERS_LUA.read_text(encoding="utf-8")
    stream_branch = source.split("data.scheme = var.scheme")[1].split("-- IP data : global")[0]
    code = "\n".join(line for line in stream_branch.split("\n") if not line.strip().startswith("--"))
    assert "data.request_id = rand(32)" in code
    assert "data.start_time = req.start_time()" in code
    assert "data.request_method = upper(var.protocol" in code
    assert "data.request_uri =" in code
    assert "data.uri =" not in code, (
        "filling uri would change what country/limit match on in stream — country:is_ignored_uri "
        "short-circuits on a nil uri today"
    )
