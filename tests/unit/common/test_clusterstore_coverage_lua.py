"""Connection lifecycle and Cluster primary operations against the complete store module."""

import pytest
from _lua_core_helpers import BW_MODULES, LUA, run_core

pytestmark = pytest.mark.skipif(LUA is None, reason="no Lua interpreter")
MODULE = BW_MODULES / "clusterstore.lua"

SETUP = r"""
local vars = {
    USE_REDIS = "yes", REDIS_HOST = "redis", REDIS_PORT = "6379", REDIS_DATABASE = "0",
    REDIS_TIMEOUT = "1000", REDIS_KEEPALIVE_IDLE = "2000", REDIS_KEEPALIVE_POOL = "10",
    REDIS_SSL = "yes", REDIS_SSL_VERIFY = "yes", TIMERS_LOG_LEVEL = "invalid",
}
for k, v in pairs(VARS or {}) do vars[k] = v end
local connector, client, cluster = {}, {}, {}
CLOSED, POOLED, ROLES, NODE_CLOSED, AUTH = 0, 0, {}, 0, {}
package.loaded["bunkerweb.utils"] = {
    get_variable = function(k)
        if k == MISSING then return nil, "missing " .. k end
        return vars[k] or ""
    end,
    parse_duration = function(v) return tonumber(v) end,
    is_cosocket_available = function() return SOCKETS ~= false end,
    is_connection_error = function(err) return err == "closed" or err == "timeout" end,
}
function client:get_reused_times() if REUSE_ERR then return nil, REUSE_ERR end return 2 end
function client:close() CLOSED = CLOSED + 1 if CLOSE_ERR then return nil, CLOSE_ERR end return true end
function client:get() if CALL_ERR then if RESP_ERROR then return false, CALL_ERR end return nil, CALL_ERR end return "value" end
function connector:connect(opts)
    ROLES[#ROLES + 1] = opts and opts.role or "master"
    if opts and SLAVE_ERR then return nil, SLAVE_ERR, PREVIOUS end
    if CONNECT_ERR then return nil, CONNECT_ERR, PREVIOUS end
    return client
end
function connector:set_keepalive() POOLED = POOLED + 1 if KEEP_ERR then return nil, KEEP_ERR end return true end
package.loaded["resty.redis.connector"] = { new = function()
    if NEW_ERR then return nil, NEW_ERR end
    return connector
end }
function cluster:cluster() if INFO_ERR then return nil, INFO_ERR end return INFO_REPLY or "cluster_state:ok" end
function cluster:masters()
    if MASTERS_ERR then return nil, MASTERS_ERR end
    return MASTERS or { {ip = "node1", port = 7000}, {ip = "node2", port = 7001} }
end
function cluster:get(key) return "cluster:" .. key end
package.loaded["resty.rediscluster"] = { new = function()
    if CLUSTER_ERR then return nil, CLUSTER_ERR end
    return cluster
end }
local node_number = 0
package.loaded["resty.redis"] = { new = function()
    node_number = node_number + 1
    local n, page = node_number, 0
    return {
        set_timeouts = function() end,
        connect = function(_, host, port, opts)
            if NODE_ERR then return nil, NODE_ERR end
            assert(host == "node" .. n and port == 6999 + n)
            assert(opts.ssl and opts.ssl_verify)
            return true
        end,
        auth = function(_, ...) AUTH[#AUTH + 1] = {...} if AUTH_ERR then return nil, AUTH_ERR end return true end,
        close = function() NODE_CLOSED = NODE_CLOSED + 1 return true end,
        dbsize = function() if DBSIZE_ERR then return nil, DBSIZE_ERR end return n * 3 end,
        scan = function(_, cursor, match, pattern, count, size)
            assert(match == "MATCH" and pattern == "ban:*" and count == "COUNT" and size == 100)
            page = page + 1
            if SCAN_ERR then return nil, SCAN_ERR end
            if BAD_SCAN then return {"0", false} end
            if EMPTY_SCAN then return {"7", {}} end
            assert(cursor == (page == 1 and "0" or "1"))
            return {page == 1 and "1" or "0", {"ban:" .. n .. ":" .. page}}
        end,
    }
end }
local function results(...)
    local out = {} for i=1,select("#", ...) do local v=select(i, ...) out[i]=v==nil and json.null or v end return out
end
local store_class = dofile(MODULE)
local store = store_class:new(POOL)
"""


def run(body, **env):
    return run_core(MODULE, SETUP + body, **env)


def test_disabled_and_unavailable_stores_report_missing_connector():
    for env in ({"VARS": {"USE_REDIS": "no"}}, {"SOCKETS": False}):
        assert run("emit(results(store:connect()))", **env) == [False, "connector is not instantiated"]


def test_initialization_failures_are_logged():
    out = run("emit(LOGS)", NEW_ERR="constructor failed", MISSING="REDIS_USERNAME")
    assert ["ERR", "[CLUSTERSTORE] missing REDIS_USERNAME"] in out
    assert ["ERR", "[CLUSTERSTORE] can't instantiate redis object : constructor failed"] in out


def test_cluster_rejects_nonzero_database():
    out = run("emit(results(store:connect()))", VARS={"REDIS_CLUSTER_NODES": "r1", "REDIS_DATABASE": "1"})
    assert out[0] is False
    assert "invalid redis configuration" in out[1]


@pytest.mark.parametrize("username,password", [("", ""), ("user", "pass")])
def test_cluster_options_and_subsystem(username, password):
    out = run(
        "emit(store.options)",
        subsystem="stream",
        VARS={"REDIS_CLUSTER_NODES": "r1 r2:7000", "REDIS_USERNAME": username, "REDIS_PASSWORD": password},
    )
    assert out["dict_name"] == "redis_cluster_locks_stream"
    assert out["serv_list"] == [{"ip": "r1", "port": 6379}, {"ip": "r2", "port": 7000}]
    assert out.get("username") == (username or None)
    assert out.get("password") == (password or None)
    assert out["max_connection_attempts"] == 1
    assert out["connect_opts"] == {"ssl": True, "ssl_verify": True, "pool_size": 10}


def test_sentinel_credentials_and_slave_fallback():
    out = run(
        "local result = results(store:connect(true)) emit({result=result, roles=ROLES, logs=LOGS, sentinels=store.options.sentinels})",
        VARS={"REDIS_SENTINEL_HOSTS": "s1 s2:26380", "REDIS_SENTINEL_USERNAME": "su", "REDIS_SENTINEL_PASSWORD": "sp"},
        SLAVE_ERR="no slave",
        PREVIOUS=["refused", "timeout"],
    )
    assert out["result"] == [True, "success", 2]
    assert out["roles"] == ["slave", "master"]
    assert out["sentinels"] == [
        {"host": "s1", "port": 26379, "username": "su", "password": "sp"},
        {"host": "s2", "port": 26380, "username": "su", "password": "sp"},
    ]
    assert ["WARN", "[CLUSTERSTORE] error while getting redis slave client : no slave ( previous errors : refused, timeout ), fallback to master"] in out[
        "logs"
    ]


def test_connection_error_keeps_previous_errors():
    assert run("emit(results(store:connect()))", CONNECT_ERR="denied", PREVIOUS=["auth failed"]) == [
        False,
        "error while getting redis client : denied ( previous errors : auth failed )",
    ]


def test_reuse_failure_closes_socket_without_pooling():
    out = run("local result=results(store:connect()) emit({result=result, closed=CLOSED, pooled=POOLED, gone=store.redis_client==nil})", REUSE_ERR="closed")
    assert out == {"result": [False, "error while getting reused times : closed"], "closed": 1, "pooled": 0, "gone": True}


def test_reconnect_returns_previous_healthy_socket_to_pool():
    out = run("assert(store:connect()) assert(store:connect()) emit({pooled=POOLED, closed=CLOSED, logs=LOGS})", VARS={"TIMERS_LOG_LEVEL": "warn"})
    assert out["pooled"] == 1
    assert out["closed"] == 0
    assert out["logs"] == [["WARN", "[CLUSTERSTORE] redis reused times = 2"]] * 2


@pytest.mark.parametrize("pool,error,resp,pooled,closed", [(True, "timeout", False, 0, 1), (True, "ERR command", True, 1, 0), (False, None, False, 0, 1)])
def test_only_healthy_pooled_connections_are_reused(pool, error, resp, pooled, closed):
    out = run(
        'assert(store:connect()) local value, err=store:call("get", "k") local ok=store:close() emit({ok=ok, value=value, err=err, pooled=POOLED, closed=CLOSED})',
        POOL=pool,
        CALL_ERR=error,
        RESP_ERROR=resp,
    )
    assert out["ok"] is True
    assert (out["pooled"], out["closed"]) == (pooled, closed)
    assert out.get("err") == error
    assert out.get("value") == (False if resp else None if error else "value")


def test_keepalive_failure_hard_closes_and_reports_error():
    out = run(
        "assert(store:connect()) local result=results(store:close()) emit({result=result, closed=CLOSED, gone=store.redis_client==nil, logs=LOGS})",
        KEEP_ERR="closed",
    )
    assert out["result"] == [False, "closed"]
    assert out["closed"] == 1 and out["gone"]
    assert ["WARN", "[CLUSTERSTORE] set_keepalive failed: closed, closing connection"] in out["logs"]
    assert ["ERR", "[CLUSTERSTORE] error while closing redis_client : closed"] in out["logs"]


def test_nonpooled_close_error_and_disconnected_guards():
    assert run("emit(results(store:close()))") == [False, "client is not instantiated"]
    assert run("emit(results(store:close()))", SOCKETS=False) == [False, "connector is not instantiated"]
    assert run('emit(results(store:call("get", "k")))') == [False, "client is not instantiated"]
    assert run("assert(store:connect()) emit(results(store:close()))", POOL=False, CLOSE_ERR="closed") == [False, "closed"]


@pytest.mark.parametrize(
    "failure,message", [("SOCKETS", "cosocket is not available"), ("CLUSTER_ERR", "error while getting redis cluster client : unavailable")]
)
def test_cluster_connection_failure(failure, message):
    assert run("emit(results(store:connect()))", VARS={"REDIS_CLUSTER_NODES": "r1"}, **{failure: False if failure == "SOCKETS" else "unavailable"}) == [
        False,
        message,
    ]


def test_cluster_ping_routing_and_close():
    out = run(
        'local result=results(store:connect(true)) local ping=store:call("ping") local value=store:call("get", "k") local closed=store:close() emit({result=result,ping=ping,value=value,closed=closed,gone=store.redis_client==nil})',
        VARS={"REDIS_CLUSTER_NODES": "r1"},
    )
    assert out == {"result": [True, "success", 1], "ping": "PONG", "value": "cluster:k", "closed": True, "gone": True}


@pytest.mark.parametrize("env,error", [({"INFO_ERR": "closed"}, "closed"), ({"INFO_REPLY": "cluster_state:fail"}, "cluster_state is not ok")])
def test_cluster_ping_requires_healthy_cluster(env, error):
    assert run('assert(store:connect()) emit(results(store:call("ping")))', VARS={"REDIS_CLUSTER_NODES": "r1"}, **env) == [None, error]


@pytest.mark.parametrize("username,auth", [("user", ["user", "pass"]), ("", ["pass"])])
def test_dbsize_sums_authenticated_primaries_and_closes_them(username, auth):
    out = run(
        'assert(store:connect()) local count=store:call("dbsize") emit({count=count,auth=AUTH,closed=NODE_CLOSED})',
        VARS={"REDIS_CLUSTER_NODES": "r1", "REDIS_USERNAME": username, "REDIS_PASSWORD": "pass"},
    )
    assert out == {"count": 9, "auth": [auth, auth], "closed": 2}


@pytest.mark.parametrize("command", ["dbsize", "scan"])
@pytest.mark.parametrize(
    "env,error,closed",
    [
        ({"MASTERS_ERR": "slots unavailable"}, "slots unavailable", 0),
        ({"NODE_ERR": "refused"}, "node1:7000 refused", 0),
        ({"AUTH_ERR": "denied"}, "node1:7000 denied", 1),
    ],
)
def test_primary_discovery_connection_and_auth_errors(command, env, error, closed):
    expression = 'store:call("dbsize")' if command == "dbsize" else 'store:scan_primaries("ban:*", 1000)'
    out = run(
        f"assert(store:connect()) local result=results({expression}) emit({{result=result,closed=NODE_CLOSED}})",
        VARS={"REDIS_CLUSTER_NODES": "r1", "REDIS_PASSWORD": "pass"},
        **env,
    )
    assert out == {"result": [None, error], "closed": closed}


def test_dbsize_error_closes_primary():
    out = run(
        'assert(store:connect()) local result=results(store:call("dbsize")) emit({result=result,closed=NODE_CLOSED})',
        VARS={"REDIS_CLUSTER_NODES": "r1"},
        DBSIZE_ERR="denied",
    )
    assert out == {"result": [None, "denied"], "closed": 1}


@pytest.mark.parametrize("limit,expected,closed", [(1000, ["ban:1:1", "ban:1:2", "ban:2:1", "ban:2:2"], 2), (1, ["ban:1:1"], 1)])
def test_scan_walks_all_primaries_and_enforces_global_key_limit(limit, expected, closed):
    out = run(
        f'assert(store:connect()) local keys=store:scan_primaries("ban:*", {limit}) emit({{keys=keys,closed=NODE_CLOSED}})', VARS={"REDIS_CLUSTER_NODES": "r1"}
    )
    assert out == {"keys": expected, "closed": closed}


def test_scan_bounds_empty_pages_and_requires_connection():
    assert run('emit(results(store:scan_primaries("ban:*", 10)))') == [None, "not connected to a cluster"]
    out = run(
        'assert(store:connect()) local keys=store:scan_primaries("ban:*", 100) emit({count=#keys,closed=NODE_CLOSED})',
        VARS={"REDIS_CLUSTER_NODES": "r1"},
        EMPTY_SCAN=True,
    )
    assert out == {"count": 0, "closed": 2}


@pytest.mark.parametrize("env,error", [({"SCAN_ERR": "closed"}, "closed"), ({"BAD_SCAN": True}, "unexpected SCAN reply")])
def test_scan_errors_close_primary(env, error):
    out = run(
        'assert(store:connect()) local result=results(store:scan_primaries("ban:*", 100)) emit({result=result,closed=NODE_CLOSED})',
        VARS={"REDIS_CLUSTER_NODES": "r1"},
        **env,
    )
    assert out == {"result": [None, error], "closed": 1}
