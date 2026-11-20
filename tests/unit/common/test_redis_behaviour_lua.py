"""Behaviour of ``src/common/core/redis/redis.lua``, the real file run under plain Lua.

The plugin has two entry points: ``init_worker`` (a connectivity probe at worker start) and the
``api`` hooks ``POST /redis/ping`` and ``GET /redis/stats``. Each is exercised for the disabled path,
a reachable server and an unreachable one. The cluster store is a stand-in driven by globals
(``tests/unit/common/_lua_state_helpers.py`` provides the OpenResty boundary).
"""

import pytest
from _lua_state_helpers import CORE, LUA, module_path, run_plugin, to_lua  # type: ignore

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

MODULE = module_path("REDIS", CORE / "redis" / "redis.lua")

STORE_LUA = """
CALLS = {}
CONNECT = { true }       -- what clusterstore:connect(true) returns
REPLIES = { ping = { true }, dbsize = { 42 } }
CLOSED = 0
CLUSTERSTORE = {
    connect = function(_, ...) CALLS[#CALLS + 1] = "connect" return table.unpack(CONNECT, 1, 2) end,
    call = function(_, command) CALLS[#CALLS + 1] = command return table.unpack(REPLIES[command], 1, 2) end,
    close = function() CLOSED = CLOSED + 1 end,
}
"""


def variables(**overrides):
    return {"USE_REDIS": "yes", "REDIS_HOST": "redis.example", "REDIS_CLUSTER_NODES": "", **overrides}


def run(method, *, extra_variables=None, setup="", uri="/redis/ping", request_method="POST"):
    body = f"""
{STORE_LUA}
VARIABLES = {to_lua(variables(**(extra_variables or {})))}
{setup}
local plugin = new_plugin(PLUGIN, {to_lua({"uri": uri, "request_method": request_method})})
local result = plugin:{method}()
local out = summary(result)
out.calls, out.closed, out.logs = CALLS, CLOSED, LOGS
emit(out)
"""
    out = {"status": None, "data": None, **run_plugin(MODULE, body)}
    out["calls"], out["logs"] = out["calls"] or [], out["logs"] or []
    return out


class TestInitWorker:
    def test_a_service_without_redis_is_not_probed(self):
        out = run("init_worker", extra_variables={"USE_REDIS": "no"})
        assert (out["ret"], out["msg"], out["calls"]) == (True, "init_worker not needed", [])

    def test_nothing_is_probed_while_loading(self):
        out = run("init_worker", setup="IS_LOADING = true")
        assert (out["ret"], out["msg"], out["calls"]) == (True, "init_worker not needed", [])

    def test_a_reachable_server_is_pinged_closed_and_logged(self):
        out = run("init_worker")
        assert (out["ret"], out["msg"]) == (True, "success")
        assert out["calls"] == ["connect", "ping"]
        assert out["closed"] == 1
        assert out["logs"] == [["NOTICE", "connectivity with redis server redis.example is successful"]]

    def test_a_cluster_is_reported_by_its_nodes(self):
        out = run("init_worker", extra_variables={"REDIS_CLUSTER_NODES": "n1:7000 n2:7000"})
        assert out["logs"] == [["NOTICE", "connectivity with redis cluster n1:7000 n2:7000 is successful"]]

    def test_an_unreachable_server_fails_without_sending_a_ping(self):
        out = run("init_worker", setup='CONNECT = { nil, "connection refused" }')
        assert (out["ret"], out["msg"]) == (False, "redis connect error : connection refused")
        assert out["calls"] == ["connect"]

    def test_a_ping_error_fails_and_still_closes_the_connection(self):
        out = run("init_worker", setup='REPLIES.ping = { nil, "timeout" }')
        assert (out["ret"], out["msg"]) == (False, "error while sending ping command to redis server : timeout")
        assert out["closed"] == 1

    def test_a_falsy_ping_reply_fails(self):
        out = run("init_worker", setup="REPLIES.ping = { false }")
        assert (out["ret"], out["msg"]) == (False, "redis ping command failed")


class TestApiPing:
    def test_a_disabled_redis_answers_200_without_connecting(self):
        out = run("api", extra_variables={"USE_REDIS": "no"})
        assert (out["ret"], out["msg"], out["status"], out["calls"]) == (True, "redis is not enabled", 200, [])

    def test_a_reachable_server_answers_200(self):
        out = run("api")
        assert (out["ret"], out["msg"], out["status"]) == (True, "success", 200)
        assert out["calls"] == ["connect", "ping"]
        assert out["closed"] == 1

    def test_an_unreachable_server_answers_500(self):
        out = run("api", setup='CONNECT = { nil, "connection refused" }')
        assert (out["msg"], out["status"]) == ("redis connect error : connection refused", 500)

    def test_a_ping_error_answers_500_and_closes(self):
        out = run("api", setup='REPLIES.ping = { nil, "timeout" }')
        assert (out["msg"], out["status"], out["closed"]) == (
            "error while sending ping command to redis server : timeout",
            500,
            1,
        )

    def test_a_falsy_ping_reply_answers_500(self):
        out = run("api", setup="REPLIES.ping = { false }")
        assert (out["msg"], out["status"]) == ("redis ping command failed", 500)


class TestApiStats:
    def test_a_reachable_server_reports_the_key_count(self):
        out = run("api", uri="/redis/stats", request_method="GET")
        assert (out["ret"], out["status"], out["msg"]) == (True, 200, {"redis_nb_keys": 42})
        assert out["calls"] == ["connect", "dbsize"]
        assert out["closed"] == 1

    def test_an_empty_database_reports_zero_keys(self):
        out = run("api", uri="/redis/stats", request_method="GET", setup="REPLIES.dbsize = { 0 }")
        assert (out["status"], out["msg"]) == (200, {"redis_nb_keys": 0})

    def test_a_disabled_redis_answers_200_without_connecting(self):
        out = run("api", uri="/redis/stats", request_method="GET", extra_variables={"USE_REDIS": "no"})
        assert (out["msg"], out["status"], out["calls"]) == ("redis is not enabled", 200, [])

    def test_an_unreachable_server_answers_500(self):
        out = run("api", uri="/redis/stats", request_method="GET", setup='CONNECT = { nil, "connection refused" }')
        assert (out["msg"], out["status"]) == ("redis connect error : connection refused", 500)

    def test_a_dbsize_error_answers_500_and_closes(self):
        out = run("api", uri="/redis/stats", request_method="GET", setup='REPLIES.dbsize = { nil, "timeout" }')
        assert (out["msg"], out["status"], out["closed"]) == (
            "error while sending dbsize command to redis server : timeout",
            500,
            1,
        )

    def test_a_dbsize_reply_without_a_value_answers_500(self):
        out = run("api", uri="/redis/stats", request_method="GET", setup="REPLIES.dbsize = { nil }")
        assert (out["msg"], out["status"]) == ("redis dbsize command failed", 500)


class TestApiRouting:
    @pytest.mark.parametrize(
        ("uri", "method"),
        [
            ("/redis/ping", "GET"),
            ("/redis/stats", "POST"),
            ("/redis/other", "GET"),
            ("/", "POST"),
        ],
    )
    def test_any_other_route_is_left_to_the_next_plugin(self, uri, method):
        out = run("api", uri=uri, request_method=method)
        assert (out["ret"], out["msg"], out["status"], out["calls"]) == (False, "success", None, [])
