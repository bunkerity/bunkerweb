"""Real CrowdSec control validation, bounded responses and sanitized management results."""

import json
from pathlib import Path

import pytest
from _lua_state_helpers import BASE_LUA, LUA, last_json, run_lua, to_lua  # type: ignore

CONTROL = Path(__file__).resolve().parents[3] / "src/common/core/crowdsec/control.lua"
pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

HARNESS = r"""
local safe = { array_mt = json.array_mt, null = json.null, encode = json.encode,
    decode_array_with_array_mt = function() end,
    decode = function(body) local ok, value = pcall(json.decode, body); if ok then return value end end }
package.loaded['cjson.safe'] = { new = function() return safe end }
local clock, index = 1000, 0
local calls, closed = {}, 0
ngx = { time = function() return 1000 end, now = function() return clock end,
    encode_args = function(values)
        local keys, out = {}, {}
        for key in pairs(values) do keys[#keys+1] = key end
        table.sort(keys)
        for _, key in ipairs(keys) do out[#out+1] = key .. '=' .. tostring(values[key]) end
        return table.concat(out, '&')
    end }
package.loaded['resty.http'] = { new = function()
    index = index + 1
    local reply = REPLIES[index] or {}
    return {
        set_timeout = function() end,
        parse_uri = function(_, uri)
            if reply.parse_fail then return nil end
            local path, query = uri:match('^https?://[^/]+(/[^?]*)%??(.*)$')
            return { 'https', 'lapi.example', 443, path, query }
        end,
        connect = function() return not reply.connect_fail end,
        close = function() closed = closed + 1 end,
        request = function(_, opts)
            calls[#calls+1] = opts
            if reply.request_fail then return nil end
            local sent = false
            return { status = reply.status or 200, headers = reply.headers or {}, body_reader = function()
                if reply.read_fail then return nil, 'read failed' end
                if reply.timeout then clock = clock + 6 end
                if sent then return nil end
                sent = true
                if reply.oversize then return string.rep('x', 16*1024*1024+1) end
                return reply.body or '[]'
            end }
        end,
    }
end }
local control = dofile(CONTROL_PATH)
local conf = { API_URL = 'https://lapi.example/', API_KEY = 'bouncer-key',
    MANAGEMENT_LOGIN = 'machine', MANAGEMENT_PASSWORD = 'password',
    BOUNCING_ON_TYPE = 'all', FALLBACK_REMEDIATION = 'ban', MODE = 'stream', UPDATE_FREQUENCY = 30 }
"""


def run(action="decisions", params=None, replies=None, setup=""):
    script = (
        BASE_LUA
        + f"\nCONTROL_PATH = {to_lua(str(CONTROL))}\nREPLIES = {to_lua(replies or [])}\n"
        + HARNESS
        + setup
        + f"\nlocal result, err, status = control.run(conf, nil, {to_lua(action)}, {to_lua(params)})\n"
        + "emit({ result = result, error = err, status = status, calls = calls, closed = closed })"
    )
    return last_json(run_lua(script))


def reply(value):
    return {"body": json.dumps(value)}


LOGIN = reply({"token": "management-token"})
DECISION = {"id": 7, "scope": "Ip", "value": "192.0.2.1", "type": "ban"}
SELECTED = {"decision_id": 7, "scope": "Ip", "value": "192.0.2.1", "decision_type": "ban"}


@pytest.mark.parametrize(
    "action,params,setup,status,error",
    [
        ("decisions", "bad", "", 400, "Invalid CrowdSec request"),
        ("decisions", {}, "conf.API_URL = 'https://user@host'", 409, "No valid CrowdSec Local API configured"),
        ("decisions", {}, "conf.API_URL = 'https://host?query'", 409, "No valid CrowdSec Local API configured"),
        ("decisions", {"limit": 201}, "", 400, "Invalid decision pagination"),
        ("decisions", {"offset": -1}, "", 400, "Invalid decision pagination"),
        ("decisions", {"ip": "bad\n"}, "", 400, "Invalid decision filter"),
        ("unknown", {}, "", 400, "Unknown CrowdSec operation"),
        ("alerts", {}, "conf.MANAGEMENT_PASSWORD = ''", 403, "Set CROWDSEC_MANAGEMENT_LOGIN"),
        ("alerts", {"alert_id": 0}, "", 400, "Invalid alert ID"),
        ("alerts", {"ip": "host/path"}, "", 400, "An IP is required to investigate alerts"),
        ("allowlists", {"offset": 0.5}, "", 400, "Invalid allowlist pagination"),
        ("allowlistcheck", {"ip": "host/path"}, "", 400, "An IP is required to check allowlists"),
        ("unban", {**SELECTED, "scope": "Country"}, "", 400, "A decision ID"),
    ],
)
def test_invalid_requests_fail_before_contacting_lapi(action, params, setup, status, error):
    out = run(action, params, setup=setup)
    assert out["status"] == status
    assert out["error"].startswith(error)
    assert "result" not in out and out["closed"] == 0


@pytest.mark.parametrize(
    "response,error",
    [
        ({"parse_fail": True}, "Invalid CrowdSec Local API URL"),
        ({"connect_fail": True}, "CrowdSec Local API is unreachable"),
        ({"request_fail": True}, "CrowdSec Local API is unreachable"),
        ({"status": 503}, "CrowdSec GET decisions returned HTTP 503"),
        ({"headers": {"Content-Length": "16777217"}}, "CrowdSec response exceeds the supported size"),
        ({"oversize": True}, "CrowdSec response exceeds the supported size"),
        ({"read_fail": True}, "Unable to read the CrowdSec response"),
        ({"timeout": True}, "CrowdSec response timed out"),
        ({"body": "broken"}, "CrowdSec returned invalid JSON"),
        (reply({}), "CrowdSec returned invalid decisions"),
        (reply([{"id": 0}]), "CrowdSec returned invalid decisions"),
        (reply([{"id": 1, "scope": "Ip"}]), "CrowdSec returned invalid decisions"),
    ],
)
def test_lapi_failures_return_502_and_close_connection(response, error):
    out = run(replies=[response])
    assert (out["status"], out["error"], out["closed"]) == (502, error, 1)
    assert "result" not in out


def test_decision_filters_sort_pagination_and_safe_fields():
    out = run(
        params={"ip": "192.0.2.1", "origin": "cscli", "scenario": "ssh", "limit": 1, "offset": 1},
        replies=[
            reply(
                [
                    {**DECISION, "id": 2, "secret": "hidden", "scenario": "x" * 600},
                    {**DECISION, "id": 9},
                ]
            )
        ],
    )
    assert out["result"] == {
        "decisions": [{**DECISION, "id": 2, "scenario": "x" * 512, "remediation": "ban"}],
        "total": 2,
        "offset": 1,
        "limit": 1,
        "observed_at": 1000,
    }
    call = out["calls"][0]
    assert call["query"] == "contains=true&ip=192.0.2.1&origins=cscli&scenarios_containing=ssh"
    assert call["headers"]["X-Api-Key"] == "bouncer-key" and call["ssl_verify"] is True


@pytest.mark.parametrize("token", [None, 5, "x" * 16385, "bad\nheader"])
def test_invalid_management_tokens_are_rejected(token):
    out = run("alerts", {"alert_id": 7}, [reply({"token": token})])
    assert (out["status"], out["error"]) == (502, "CrowdSec returned an invalid management token")
    assert len(out["calls"]) == 1


@pytest.mark.parametrize("action,params", [("alerts", {"ip": "192.0.2.1"}), ("allowlists", {})])
def test_machine_login_failure_is_actionable(action, params):
    out = run(action, params, [{"status": 401}])
    assert out["status"] == 502
    assert "machine authentication failed (HTTP 401)" in out["error"]


def test_alert_detail_sanitizes_metadata_and_caps_events():
    event = {"timestamp": "t" * 70, "meta": [{"key": "http_path", "value": "x" * 1100}, {"key": "password", "value": "hidden"}]}
    alert = {
        "id": 7,
        "message": "m" * 2100,
        "source": {"ip": "192.0.2.1", "secret": "hidden"},
        "decisions": [DECISION],
        "events": [event] * 51,
        "secret": "hidden",
    }
    out = run("alerts", {"alert_id": 7}, [LOGIN, reply(alert)])
    safe = out["result"]["alert"]
    assert out["status"] == 200 and len(safe["events"]) == 50
    assert safe["message"] == "m" * 2048 and safe["source"] == {"ip": "192.0.2.1"}
    assert safe["events"][0] == {"timestamp": "t" * 64, "meta": [{"key": "http_path", "value": "x" * 1024}]}
    assert safe["decisions"] == [DECISION] and "hidden" not in json.dumps(safe)
    call = out["calls"][1]
    assert call["path"] == "/v1/alerts/7" and call["headers"]["Authorization"] == "Bearer management-token"
    assert "X-Api-Key" not in call["headers"]


@pytest.mark.parametrize(
    "alert", [{"id": 0}, {"id": 1, "source": "bad"}, {"id": 1, "decisions": {}}, {"id": 1, "events": {}}, {"id": 1, "events": [{"meta": {}}]}]
)
def test_invalid_alert_details_are_rejected(alert):
    out = run("alerts", {"alert_id": 1}, [LOGIN, reply(alert)])
    assert (out["status"], out["error"]) == (502, "CrowdSec returned an invalid alert")


def test_alert_listing_is_bounded_and_uses_ip_query():
    out = run("alerts", {"ip": "192.0.2.1"}, [LOGIN, reply([{"id": i} for i in range(1, 52)])])
    assert out["status"] == 200 and len(out["result"]["alerts"]) == 50
    assert out["calls"][1]["query"] == "ip=192.0.2.1&limit=50"


@pytest.mark.parametrize("payload,error", [({}, "CrowdSec returned invalid alerts"), ([{"id": 0}], "CrowdSec returned an invalid alert")])
def test_invalid_alert_listing_is_rejected(payload, error):
    out = run("alerts", {"ip": "192.0.2.1"}, [LOGIN, reply(payload)])
    assert (out["status"], out["error"]) == (502, error)


def test_allowlists_sort_paginate_and_bound_items():
    items = [{"value": "192.0.2.1", "expiration": None, "secret": "hidden"}] * 201
    out = run(
        "allowlists",
        {"limit": 1, "offset": 1},
        [
            LOGIN,
            reply(
                [
                    {"name": "z", "items": items, "console_managed": True, "description": "d" * 600},
                    {"name": "a", "items": []},
                ]
            ),
        ],
    )
    data = out["result"]
    assert (out["status"], data["total"], data["offset"], data["limit"]) == (200, 2, 1, 1)
    [safe] = data["allowlists"]
    assert (safe["name"], safe["total"], safe["limit"], len(safe["items"])) == ("z", 201, 200, 200)
    assert safe["console_managed"] is True and safe["description"] == "d" * 512
    assert safe["items"][0] == {"value": "192.0.2.1"} and "hidden" not in json.dumps(safe)
    assert out["calls"][1]["query"] == "with_content=true"


@pytest.mark.parametrize(
    "payload,error",
    [
        ({}, "CrowdSec returned invalid allowlists"),
        ([{"name": "", "items": []}], "CrowdSec returned invalid allowlist data"),
        ([{"name": "a", "console_managed": "yes", "items": []}], "CrowdSec returned invalid allowlist data"),
        ([{"name": "a", "items": {}}], "CrowdSec returned invalid allowlist data"),
        ([{"name": "a", "items": [{"value": ""}]}], "CrowdSec returned invalid allowlist data"),
        ([{"name": "a", "items": [{"value": "192.0.2.1", "expiration": 4}]}], "CrowdSec returned invalid allowlist data"),
    ],
)
def test_invalid_allowlists_are_rejected(payload, error):
    out = run("allowlists", replies=[LOGIN, reply(payload)])
    assert (out["status"], out["error"]) == (502, error)


@pytest.mark.parametrize("payload,expected", [({}, False), ({"allowlisted": False}, False), ({"allowlisted": True, "reason": "r" * 2100}, True)])
def test_allowlist_check_handles_empty_negative_and_positive(payload, expected):
    out = run("allowlistcheck", {"ip": "2001:db8::1"}, [LOGIN, reply(payload)])
    assert out["status"] == 200 and out["result"]["allowlisted"] is expected
    assert out["result"]["ip"] == "2001:db8::1"
    if expected:
        assert out["result"]["reason"] == "r" * 2048


@pytest.mark.parametrize("payload", [[], {"allowlisted": "yes"}, {"reason": "missing flag"}])
def test_invalid_allowlist_check_is_rejected(payload):
    out = run("allowlistcheck", {"ip": "192.0.2.1"}, [LOGIN, reply(payload)])
    assert (out["status"], out["error"]) == (502, "CrowdSec returned an invalid allowlist check")


@pytest.mark.parametrize(
    "replies,error",
    [
        ([reply({})], "CrowdSec returned invalid decisions"),
        ([reply([DECISION]), {"status": 401}], "machine authentication failed"),
        ([reply([DECISION]), LOGIN, {"status": 503}], "removal outcome is unknown"),
        ([reply([DECISION]), LOGIN, reply({"nbDeleted": 2})], "did not confirm removal"),
        ([reply([DECISION]), LOGIN, reply({"nbDeleted": 1}), {"request_fail": True}], "verification failed"),
        ([reply([DECISION]), LOGIN, reply({"nbDeleted": 1}), reply([DECISION])], "still reports the selected decision as active"),
    ],
)
def test_unban_failures_preserve_uncertain_removal_outcome(replies, error):
    out = run("unban", SELECTED, replies)
    assert out["status"] == 502 and error in out["error"] and "result" not in out
