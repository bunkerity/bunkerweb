"""Limit counter failures and Redis fallback through the real Lua request path."""

import pytest
from _lua_request_helpers import requires_lua, run

pytestmark = requires_lua

SETUP = r"""
VARIABLES = { USE_LIMIT_REQ = "yes", USE_LIMIT_REQ_GLOBAL = "yes" }
STORE["plugin_limit_rules"] = { global = { ["/"] = "1r/s" } }
STORE["plugin_limit_global_rules"] = {}
local p = PLUGIN:new(ctx())
"""

REDIS = r"""
p.use_redis = true
local closed = 0
p.clusterstore = {
    connect = function() if CONNECT_ERROR then return nil, CONNECT_ERROR end return true end,
    close = function() closed = closed + 1 end,
    call = function(_, method, script, count, key, ...)
        assert(method == "eval" and count == 1)
        if EVAL_ERROR then return nil, EVAL_ERROR end
        return REDIS_RESULT
    end,
}
"""


@pytest.mark.parametrize("failure", ["connect", "eval"])
@pytest.mark.parametrize("scope", ["uri", "global"])
def test_redis_failure_falls_back_to_local_and_still_limits(failure, scope):
    out = run(
        "limit",
        SETUP + REDIS + f"""
{'CONNECT_ERROR' if failure == 'connect' else 'EVAL_ERROR'} = "redis unavailable"
{'p.global_rate = "1r/s"; p.rules = {}' if scope == 'global' else ''}
local first = p:access()
local second = p:access()
emit("first", first.status) emit("second", second.status)
emit("rate", second.data and second.data.current_rate) emit("scope", second.data and second.data.scope)
emit("logs", table.concat(LOGS, "|")) emit("closed", closed)
""",
    )
    assert (out["first"], out["second"], out["rate"]) == ("nil", "429", "2")
    assert out["scope"] == ("global" if scope == "global" else "nil")
    function = "limit_req_global_redis" if scope == "global" else "limit_req_redis"
    assert f"{function} failed, falling back to local : redis unavailable" in out["logs"]
    assert out["closed"] == ("0" if failure == "connect" else "2")


@pytest.mark.parametrize("scope", ["uri", "global"])
def test_successful_redis_count_drives_the_access_decision(scope):
    out = run(
        "limit",
        SETUP + REDIS + f"""
REDIS_RESULT = {'2' if scope == 'global' else '{ NOW, NOW }'}
{'p.global_rate = "1r/s"; p.rules = {}' if scope == 'global' else ''}
DS_ERR = "local read must not be used"
local r = p:access()
emit("ret", r.ret) emit("status", r.status) emit("rate", r.data and r.data.current_rate)
emit("closed", closed) emit("saved", DS["plugin_limit_www.example.com1.2.3.4/"])
""",
    )
    assert (out["ret"], out["status"], out["rate"], out["closed"]) == ("true", "429", "2", "1")
    assert out["saved"] == ("nil" if scope == "global" else "[1000000,1000000]")


def test_redis_timestamp_write_failure_returns_error():
    out = run(
        "limit",
        SETUP + REDIS + r"""
REDIS_RESULT = { NOW }
p.datastore.set_with_retries = function() return nil, "no memory" end
local r = p:access()
emit("ret", r.ret) emit("msg", r.msg) emit("status", r.status)
""",
    )
    assert out == {"ret": "false", "msg": "can't update timestamps : no memory", "status": "nil"}


@pytest.mark.parametrize("scope", ["uri", "global"])
@pytest.mark.parametrize("failure", ["read", "write"])
def test_local_counter_failure_is_reported_without_a_successful_decision(scope, failure):
    out = run(
        "limit",
        SETUP + f"""
{'p.global_rate = "1r/s"; p.rules = {}' if scope == 'global' else ''}
{'DS_ERR = "broken"' if failure == 'read' else 'p.datastore.set_with_retries = function() return nil, "broken" end'}
local r = p:access()
emit("ret", r.ret) emit("msg", r.msg) emit("status", r.status)
""",
    )
    function = "limit_req_global_local" if scope == "global" else "limit_req_local"
    assert out == {"ret": "false", "msg": f"{function} failed : broken", "status": "nil"}


def test_global_detect_mode_records_scope_and_metric():
    out = run(
        "limit",
        SETUP + r"""
SECURITY_MODE = "detect"
p.global_rate = "1r/m"
p:access()
local r = p:access()
emit("msg", r.msg) emit("status", r.status) emit("scope", r.data.scope)
emit("metrics", metric_keys())
""",
    )
    assert out["msg"] == "detected client IP 1.2.3.4 would be limited by global rate limit (current rate = 2r/m and max rate = 1r/m)"
    assert (out["status"], out["scope"], out["metrics"]) == ("429", "global", "counters:limited_global")


@pytest.mark.parametrize("unit,seconds", [("s", 1), ("m", 60), ("h", 3600), ("d", 86400)])
def test_local_global_counter_has_window_ttl_and_resets(unit, seconds):
    out = run(
        "limit",
        SETUP + f"""
local ttl
p.datastore.set_with_retries = function(_, key, value, delay) DS[key] = value; ttl = delay; return true end
local first = p:limit_req_global(1, "{unit}")
local second = p:limit_req_global(1, "{unit}")
NOW = NOW + {seconds}
local third, _, count = p:limit_req_global(1, "{unit}")
emit("first", first) emit("second", second) emit("third", third) emit("count", count) emit("ttl", ttl)
""",
    )
    assert out == {"first": "false", "second": "true", "third": "false", "count": "1", "ttl": str(seconds)}


def test_service_rules_override_global_rules_without_mutating_them():
    out = run(
        "limit",
        SETUP + r"""
STORE["plugin_limit_rules"]["www.example.com"] = { ["/"] = "2r/s" }
STORE["plugin_limit_global_rules"] = { global = "100r/s", ["www.example.com"] = "50r/s" }
local service = PLUGIN:new(ctx())
emit("rate", service.rules["/"]) emit("global_rate", service.global_rate)
emit("shared", STORE["plugin_limit_rules"].global["/"])
""",
    )
    assert out == {"rate": "2r/s", "global_rate": "50r/s", "shared": "1r/s"}


@pytest.mark.parametrize("failure", ["variables", "rules", "global_rules"])
def test_init_surfaces_variable_and_store_failures(failure):
    out = run(
        "limit",
        SETUP + f"""
{'MULTI_ERR = "broken"' if failure == 'variables' else ''}
{'SET_FAIL = "broken"' if failure == 'rules' else ''}
{'p.internalstore.set = function(_, key, value) if key == "plugin_limit_global_rules" then return nil, "broken" end STORE[key] = value; return true end' if failure == 'global_rules' else ''}
local r = p:init()
emit("ret", r.ret) emit("msg", r.msg)
""",
    )
    assert out == {"ret": "false", "msg": "broken"}
