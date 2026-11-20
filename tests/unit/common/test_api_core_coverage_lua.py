"""Exercise the complete instance API module across authentication and read/dispatch paths."""

import json

import pytest

from _lua_core_helpers import BW_MODULES, LUA, run_core

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

API = BW_MODULES / "api.lua"

PRELUDE = r"""
ngx.HTTP_OK = 200
ngx.HTTP_BAD_REQUEST = 400
ngx.HTTP_NOT_FOUND = 404
ngx.HTTP_INTERNAL_SERVER_ERROR = 500
ngx.HTTP_BAD_GATEWAY = 502
ngx.HTTP_SERVICE_UNAVAILABLE = 503
ngx.shared.internalstore = {}
HEADERS = HEADERS or {}
VARIABLES = VARIABLES or { API_WHITELIST_IP = "127.0.0.1", API_TOKEN = "", IS_LOADING = "no" }
STORE = STORE or { plugins = {} }
FILES = FILES or {}
ngx.req = { get_headers = function(limit) HEADER_LIMIT = limit; return HEADERS end }

-- Files and processes are isolated boundaries: no host configuration or command is touched.
local real_open = io.open
local coverage_dir = os.getenv("BW_LUA_COVERAGE_DIR")
io.open = function(path, mode)
    -- LuaCov writes stats during shutdown through this same global IO boundary.
    if coverage_dir and path:sub(1, #coverage_dir + 1) == coverage_dir .. "/" then
        return real_open(path, mode)
    end
    local contents = FILES[path]
    if contents == nil then return nil, "No such file" end
    return { read = function() return contents end, close = function() end }
end
os.remove = function(path)
    if REMOVE_ERROR then return nil, REMOVE_ERROR end
    if FILES[path] == nil then return nil, "No such file" end
    FILES[path] = nil
    return true
end
os.execute = function() error("unexpected shell command") end
io.popen = function() error("unexpected shell command") end

package.loaded["bunkerweb.datastore"] = {
    new = function() return { get = function(_, key) return STORE[key], "not found" end } end,
}
package.loaded["bunkerweb.utils"] = {
    get_variable = function(key) return VARIABLES[key], "not found" end,
    is_ip_in_networks = function(ip, networks)
        for _, network in ipairs(networks) do if ip == network then return true end end
        return false
    end,
}
package.loaded["bit"] = {
    bor = function(a, b) return a | b end,
    bxor = function(a, b) return a ~ b end,
}
package.loaded["ffi"] = { cdef = function() end, os = "Linux" }
package.loaded["ngx.process"] = {}
package.loaded["resty.lock"] = {}
package.loaded["resty.signal"] = {}
package.loaded["resty.upload"] = {}
package.loaded["bunkerweb.banlease"] = {}
package.loaded["bunkerweb.pushswap"] = {}
PLUGINS = PLUGINS or {}
package.loaded["bunkerweb.helpers"] = {
    require_plugin = function(id) return PLUGINS[id] end,
    new_plugin = function(plugin, ctx)
        if plugin.init_error then return false, plugin.init_error end
        return true, { spec = plugin, ctx = ctx }
    end,
    call_plugin = function(plugin)
        if plugin.spec.call_error then return false, plugin.spec.call_error end
        return true, plugin.spec.result
    end,
}
local api = dofile(MODULE)
local ctx = { bw = { remote_addr = "127.0.0.1", request_method = "GET", uri = "/ping" } }
local instance = api:new(ctx)
"""


def run(body, **env):
    return run_core(API, PRELUDE + body, **env)


@pytest.mark.parametrize(
    ("token", "headers", "expected"),
    [
        (None, {}, [True, "ok"]),
        ("", {}, [True, "ok"]),
        ("secret", {}, [False, "missing API token"]),
        ("secret", {"authorization": "Basic secret"}, [False, "missing API token"]),
        ("secret", {"authorization": "Bearer"}, [False, "missing API token"]),
        ("secret", {"authorization": "Bearer secrex"}, [False, "invalid API token"]),
        ("secret", {"authorization": "Bearer short"}, [False, "invalid API token"]),
        ("secret", {"authorization": "Bearer secret"}, [True, "ok"]),
        ("secret", {"Authorization": "bearer\tsecret"}, [True, "ok"]),
        ("secret", {"authorization": "Bearer secret "}, [False, "invalid API token"]),
    ],
)
def test_token_decisions(token, headers, expected):
    assert run("emit({ instance:is_allowed_token() })", VARIABLES={"API_WHITELIST_IP": "127.0.0.1", "API_TOKEN": token}, HEADERS=headers) == expected


@pytest.mark.parametrize(("limit", "expected"), [("23", 23), ("invalid", 100)])
def test_token_header_limit(limit, expected):
    result = run(
        "instance:is_allowed_token(); emit(HEADER_LIMIT)",
        VARIABLES={"API_WHITELIST_IP": "127.0.0.1", "API_TOKEN": "secret", "MAX_HEADERS": limit},
    )
    assert result == expected


@pytest.mark.parametrize(
    ("variables", "disk", "ips", "token"),
    [
        ({"API_WHITELIST_IP": "127.0.0.1  ::1\t192.0.2.1", "API_TOKEN": "live"}, "API_TOKEN=disk\n", ["127.0.0.1", "::1", "192.0.2.1"], "live"),
        ({}, "API_WHITELIST_IP=127.0.0.1\nAPI_TOKEN=disk=token\n", ["127.0.0.1"], "disk=token"),
        ({"API_TOKEN": "live"}, "ignored\nOTHER=x\nAPI_WHITELIST_IP=::1\nAPI_TOKEN=disk\n", ["::1"], "live"),
        ({}, "API_WHITELIST_IP=127.0.0.1\nAPI_TOKEN=\n", ["127.0.0.1"], None),
        ({}, "API_WHITELIST_IP=127.0.0.1\n", [], None),
        ({}, "API_WHITELIST_IP=127.0.0.1\nAPI_TOKEN=partial", [], None),
        ({}, None, [], None),
    ],
)
def test_initialize_live_and_disk_credentials(variables, disk, ips, token):
    result = run(
        "emit({ ips = instance.ips, token = instance.api_token, logs = LOGS, same_ctx = instance.ctx == ctx })",
        VARIABLES=variables,
        FILES={} if disk is None else {"/etc/nginx/variables.env": disk},
    )
    assert result["ips"] == (ips or {})
    assert result.get("token") == token
    assert result["same_ctx"] is True
    if "API_WHITELIST_IP" not in variables:
        assert result["logs"][0][0] == "ERR"
        assert ("falling back" if ips else "can't get API_WHITELIST_IP") in result["logs"][0][1]


@pytest.mark.parametrize(("ip", "allowed"), [("127.0.0.1", True), ("::1", True), ("192.0.2.2", False)])
def test_ip_decisions(ip, allowed):
    assert run(
        "ctx.bw.remote_addr = REMOTE; emit({ instance:is_allowed_ip() })",
        REMOTE=ip,
        VARIABLES={"API_WHITELIST_IP": "127.0.0.1 ::1"},
    ) == [allowed, "ok" if allowed else "IP is not in API_WHITELIST_IP"]


@pytest.mark.parametrize(
    ("loading", "files", "message"),
    [
        (None, {}, "loading"),
        ("yes", {"/var/tmp/bunkerweb/reloading": "", "/var/tmp/bunkerweb_needs_config": ""}, "loading"),
        ("no", {"/var/tmp/bunkerweb/reloading": "", "/var/tmp/bunkerweb_needs_config": ""}, "reloading"),
        ("no", {"/var/tmp/bunkerweb_needs_config": ""}, "needs_config"),
        ("no", {}, "ok"),
    ],
)
def test_health_state_priority(loading, files, message):
    result = run(
        'ctx.bw.uri = "/health"; emit({ result = { instance:do_api_call() }, logs = LOGS })',
        VARIABLES={"API_WHITELIST_IP": "127.0.0.1", "IS_LOADING": loading},
        FILES=files,
    )
    assert result["result"][:3] == [True, message, 200]
    assert json.loads(result["result"][3]) == {"status": "success", "msg": message}
    if loading is None:
        assert "can't get IS_LOADING variable" in result["logs"][0][1]


@pytest.mark.parametrize(
    ("uri", "exists", "error", "removed", "logged"),
    [
        ("/cache", True, None, False, False),
        ("/confs", True, None, True, False),
        ("/confs", False, None, False, False),
        ("/confs", True, "Permission denied", False, True),
    ],
)
def test_only_main_configuration_clears_request(uri, exists, error, removed, logged):
    result = run(
        "local removed = api.clear_needs_config(URI); emit({ removed = removed, exists = FILES[api.NEEDS_CONFIG_PATH] ~= nil, logs = LOGS })",
        URI=uri,
        FILES={"/var/tmp/bunkerweb_needs_config": "requested"} if exists else {},
        REMOVE_ERROR=error,
    )
    assert result["removed"] is removed
    assert result["exists"] is (exists and not removed)
    assert bool(result["logs"]) is logged
    if logged:
        assert result["logs"][0][0] == "ERR"
        assert "Permission denied" in result["logs"][0][1]


@pytest.mark.parametrize(("ok", "status", "reason"), [(True, 0, "exit"), (False, 7, "exit"), (False, 9, "signal"), (None, -1, "timeout")])
def test_command_results_and_logs(ok, status, reason):
    result = run(
        r"""
run = function() return COMMAND_OK, "output", "diagnostic", REASON, STATUS end
local ok, reason, status = instance:cmd("fixture-command")
emit({ ok = ok, reason = reason, status = status, logs = LOGS })
""",
        COMMAND_OK=ok,
        STATUS=status,
        REASON=reason,
    )
    assert result.get("ok") == (None if ok is None else status == 0)
    assert result["reason"] == reason
    assert result.get("status") == (None if ok is None else status)
    assert result["logs"] == [
        ["NOTICE" if status == 0 else "ERR", f"[API] {'success' if status == 0 else 'error'} while running command fixture-command"],
        ["NOTICE" if status == 0 else "ERR", "[API] stdout = output"],
        ["NOTICE" if status == 0 else "ERR", "[API] stdout = diagnostic"],
    ]


@pytest.mark.parametrize(
    ("variables", "status", "message"), [(None, 500, "can't access variables from internalstore : not found"), (["one", "two"], 200, "success"), ([], 200, "")]
)
def test_variables_response(variables, status, message):
    result = run('ctx.bw.uri = "/variables"; emit({ instance:do_api_call() })', STORE={"variables": variables, "plugins": []})
    assert result[:3] == [status == 200, message, status]
    body = json.loads(result[3])
    assert body["msg"] == message
    assert body["status"] == ("success" if status == 200 else "error")
    if variables:
        assert body["data"] == variables


@pytest.mark.parametrize(("method", "uri"), [("GET", "/ping"), ("GET", "/ping/"), ("PATCH", "/ping"), ("POST", "/ping"), ("GET", "/missing")])
def test_dispatch_method_and_anchored_path(method, uri):
    result = run("ctx.bw.request_method = METHOD; ctx.bw.uri = URI; emit({ instance:do_api_call() })", METHOD=method, URI=uri)
    found = method == "GET" and uri == "/ping"
    assert result[:3] == ([True, "pong", 200] if found else [False, "error", 404])
    assert json.loads(result[3]) == {"status": "success" if found else "error", "msg": "pong" if found else "not found"}


def test_missing_plugin_inventory_returns_server_error():
    result = run('ctx.bw.uri = "/missing"; emit({ instance:do_api_call() })', STORE={})
    assert result[:3] == [False, "can't list loaded plugins : not found", 500]
    assert json.loads(result[3]) == {"status": "error", "msg": result[1]}


@pytest.mark.parametrize("status", [200, 400])
def test_plugin_dispatch_skips_failures_and_preserves_response(status):
    plugins = {
        "no_api": {},
        "bad_init": {"api": True, "init_error": "initialization failed"},
        "bad_call": {"api": True, "call_error": "execution failed"},
        "declined": {"api": True, "result": {"ret": False}},
        "handled": {"api": True, "result": {"ret": True, "status": status, "msg": "plugin response", "data": {"answer": 42}}},
    }
    result = run(
        'ctx.bw.uri = "/plugin"; emit({ result = { instance:do_api_call() }, logs = LOGS })',
        PLUGINS=plugins,
        STORE={"plugins": [{"id": name} for name in ["missing", *plugins]]},
    )
    level = "success" if status == 200 else "error"
    assert result["result"][:3] == [status == 200, level, status]
    assert json.loads(result["result"][3]) == {"status": level, "msg": "plugin response", "data": {"answer": 42}}
    assert result["logs"] == [
        ["ERR", "[API] can't instantiate bad_init : initialization failed"],
        ["ERR", "[API] error while executing bad_call:api() : execution failed"],
    ]


def test_plugin_without_data_does_not_invent_payload():
    result = run(
        'ctx.bw.uri = "/plugin"; emit({ instance:do_api_call() })',
        PLUGINS={"handled": {"api": True, "result": {"ret": True, "status": 200, "msg": "done"}}},
        STORE={"plugins": [{"id": "handled"}]},
    )
    assert result[:3] == [True, "success", 200]
    assert json.loads(result[3]) == {"status": "success", "msg": "done"}
