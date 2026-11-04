"""Exercise the real helpers module; fake only filesystem and OpenResty boundaries."""

import json
from pathlib import Path

import pytest
from _lua_core_helpers import BW_MODULES, LUA, run_core  # type: ignore

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")
MODULE = BW_MODULES / "helpers.lua"
ROOT = Path(__file__).resolve().parents[3]

SETUP = r"""
FILES = FILES or {}
local real_open = io.open
io.open = function(path, mode)
    local f = FILES[path]
    if f then
        if f.errno then return nil, f.error, f.errno end
        return {
            read = function() return f.content, f.error end,
            close = function() f.closed = true end,
        }
    end
    return real_open(path, mode)
end
ngx.ctx = {}
ngx.var = { remote_addr = "192.0.2.1", server_name = "app.example", uri = "/path", request_id = "id",
    request_uri = "/path?q=1", request_method = "GET", http_user_agent = "agent", http_host = "app.example",
    http_content_type = "text/plain", http_content_length = "3", http_origin = "https://app.example",
    time_local = "now", scheme = "https" }
ngx.req = { http_version = function() return 1.1 end, start_time = function() return 42 end }
ngx.shared = { internalstore = "http-store", internalstore_stream = "stream-store" }
local applied, saved = 0, nil
package.loaded["resty.core.base"] = { get_request = function() return not NO_REQUEST end }
package.loaded["bunkerweb.ctx"] = {
    apply_ref = function() applied = applied + 1 end,
    stash_ref = function(ctx) saved = ctx end,
}
package.loaded["bunkerweb.utils"] = {
    get_phases = function() return { "init", "access", "header", "preread" } end,
    ip_is_global = function() return IP_GLOBAL, "invalid address" end,
    is_ipv4 = function() return true end,
    is_ipv6 = function() return false end,
    get_variable = function() return REDIS, "unavailable" end,
}
package.loaded["bunkerweb.datastore"] = { new = function(_, dict) return { dict = dict } end }
package.loaded["bunkerweb.clusterstore"] = { new = function() return {} end }
package.loaded["bunkerweb.cachestore"] = {
    new = function(_, redis, ctx) return { redis = redis, context = ctx } end,
}
local helpers = dofile(MODULE)
"""


def run(body, **env):
    return run_core(MODULE, SETUP + body, **env)


def manifest(**values):
    return dict(id="sample", name="Sample", description="Fixture", version="1", settings={}, stream="yes", **values)


@pytest.mark.parametrize(
    ("file", "expected", "message"),
    [
        ({"errno": 2, "error": "missing"}, None, "no plugin.json at"),
        ({"errno": 13, "error": "Permission denied"}, False, "Permission denied (nb = 13)"),
        ({"error": "read failed"}, False, "can't read JSON at"),
        ({"content": "{"}, False, "invalid JSON at"),
        ({"content": "false"}, False, "expected an object"),
        ({"content": "{}"}, False, "missing field(s)"),
    ],
)
def test_manifest_failures_return_diagnostics(file, expected, message):
    out = run('local ok, msg = helpers.load_plugin("fixture") emit({ok=ok, msg=msg, closed=FILES.fixture.closed})', FILES={"fixture": file})
    assert out.get("ok") is expected
    assert message in out["msg"]
    if "errno" not in file:
        assert out["closed"] is True


@pytest.mark.parametrize("subsystem", ["http", "stream"])
def test_http_only_code_is_skipped_only_in_stream(subsystem):
    out = run(
        r"""
FILES.fixture = { content = json.encode(METADATA) }
package.preload["sample/sample"] = function() error("HTTP API unavailable") end
local ok, result = helpers.load_plugin("fixture")
emit({ ok=ok, result=result })
""",
        subsystem=subsystem,
        METADATA={**manifest(), "stream": "no"},
    )
    assert out["ok"] is (subsystem == "stream")
    if subsystem == "stream":
        assert out["result"]["settings"] == {}
        assert out["result"]["phases"] == {}
    else:
        assert "HTTP API unavailable" in out["result"]


@pytest.mark.parametrize("code", [True, False])
def test_manifest_phases_follow_real_module_methods(code):
    out = run(
        r"""
FILES.fixture = { content=json.encode(METADATA) }
if HAS_CODE then package.preload["sample/sample"] = function()
    return { new=function() end, access=function() end, header=function() end, ignored=function() end }
end end
local ok, metadata = helpers.load_plugin("fixture")
assert(ok, metadata)
emit(metadata.phases)
""",
        METADATA=manifest(),
        HAS_CODE=code,
    )
    assert out == (["access", "header"] if code else {})


@pytest.mark.parametrize(
    ("definition", "expected", "message"),
    [
        ("", None, "doesn't have LUA code"),
        ('error("broken module")', False, "broken module"),
        ("return {}", False, "missing new() method"),
        ("return {new=function() end}", True, "require() call successful"),
    ],
)
def test_require_failures_are_distinct(definition, expected, message):
    out = run(
        (f'package.preload["sample/sample"] = function() {definition} end\n' if definition else "")
        + 'local obj, msg = helpers.require_plugin("sample") emit({ok=type(obj)=="table" and true or obj, msg=msg})'
    )
    assert out.get("ok") is expected
    assert message in out["msg"]


def test_constructor_passes_context_and_returns_errors():
    out = run(r"""
local ctx = {}
local ok, obj = helpers.new_plugin({ new=function(self, c) return { ctx=c, owner=self } end }, ctx)
assert(ok and obj.ctx == ctx and obj.owner.new)
local failed, err = helpers.new_plugin({ name="sample", new=function() error("constructor broke") end }, ctx)
emit({ok=failed, err=err})
""")
    assert out["ok"] is False
    assert "new error for plugin sample" in out["err"] and "constructor broke" in out["err"]


@pytest.mark.parametrize(
    ("method", "expected", "message"),
    [
        ("nil", None, "missing access() method for plugin sample"),
        ('function() error("dispatch broke") end', False, "sample:access() failed"),
        ("function() end", False, "returned nil value"),
        ("function() return {} end", False, 'missing required return value(s) : ["ret","msg"]'),
    ],
)
def test_dispatch_rejects_missing_or_broken_results(method, expected, message):
    out = run(
        'local p = {get_id=function() return "sample" end, access=' + method + "}\n" 'local ok, msg = helpers.call_plugin(p, "access") emit({ok=ok,msg=msg})'
    )
    assert out.get("ok") is expected
    assert message in out["msg"]


def test_dispatch_preserves_negative_plugin_decision():
    assert run(r"""
local p = { get_id=function() return "sample" end, access=function(self)
    assert(self.get_id() == "sample") return { ret=false, msg="denied", status=403 }
end }
local ok, result = helpers.call_plugin(p, "access")
emit({ok=ok, result=result})
""") == {"ok": True, "result": {"ret": False, "msg": "denied", "status": 403}}


def test_orders_apply_overrides_aliases_deduplication_and_sorted_fallback():
    out = run(
        r"""
local plugins = {
    {id="z",phases={"access","header"}}, {id="a",phases={"access","header"}},
    {id="b",phases={"access"}}, {id="c",phases={"access"}}, {id="d",phases={"access"}},
}
local ok, orders, missing = helpers.order_plugins(plugins, {
    global={ PLUGINS_ORDER_ACCESS=" z z unknown a ", PLUGINS_ORDER_HEADER=7 },
    ["app.example"]={ PLUGINS_ORDER_ACCESS="c", PLUGINS_ORDER_HEADER="b" },
})
assert(ok, orders)
emit({root=orders.access, global=orders.global, site=orders.per_site["app.example"], missing=missing})
""",
        FILES={"/usr/share/bunkerweb/core/order.json": {"content": '{"access":["b","a"],"headers":["z"],"unknown":["x"]}'}},
    )
    assert out["root"] == ["z", "a", "b", "c", "d"]
    assert out["global"]["header"] == ["z", "a"]
    assert out["site"]["access"] == ["c", "b", "a", "d", "z"]
    assert out["site"]["header"] == ["z", "a"]
    assert out["missing"]["global"]["access"] == {"unknown": True}
    assert out["missing"]["per_site"]["app.example"]["header"] == {"b": True}


@pytest.mark.parametrize("file, message", [({"errno": 13, "error": "denied"}, "denied (nb = 13)"), ({"content": "{"}, "invalid order.json")])
def test_order_file_failure_is_returned(file, message):
    out = run("local ok, msg=helpers.order_plugins({}, nil) emit({ok=ok,msg=msg})", FILES={"/usr/share/bunkerweb/core/order.json": file})
    assert out["ok"] is False
    assert message in out["msg"]


@pytest.mark.parametrize("subsystem", ["http", "stream"])
def test_context_reports_failures_and_refreshes_stores(subsystem):
    out = run(
        r"""
local ok, msg, errors, ctx = helpers.fill_ctx()
local before = ctx.bw.cachestore
local data = {kind=ctx.bw.kind, addr=ctx.bw.remote_addr, errors=errors, dict=ctx.bw.internalstore.dict,
    method=ctx.bw.request_method, version=ctx.bw.http_version, start=ctx.bw.start_time,
    global=ctx.bw.ip_is_global, ipv4=ctx.bw.ip_is_ipv4, ipv6=ctx.bw.ip_is_ipv6}
assert(ok and msg == "ctx filled")
assert(ctx.bw.cachestore.redis == false and ctx.bw.cachestore.context == ctx)
ngx.var.remote_addr = "192.0.2.2"
helpers.fill_ctx(true)
assert(ctx.bw.remote_addr == "192.0.2.1" and ctx.bw.cachestore ~= before)
helpers.save_ctx(ctx)
data.applied = applied
data.saved = saved == ctx
emit(data)
""",
        subsystem=subsystem,
    )
    assert out["errors"] == ["can't check if IP is global : invalid address", "can't get variable from datastore : unavailable"]
    assert out["addr"] == "192.0.2.1" and out["kind"] == subsystem
    assert out["dict"] == ("http-store" if subsystem == "http" else "stream-store")
    assert out["applied"] == 1 and out["saved"] is True
    assert out["ipv4"] is True and out["ipv6"] is False
    if subsystem == "http":
        assert (out["method"], out["version"], out["start"]) == ("GET", 1.1, 42)
    else:
        assert "method" not in out


@pytest.mark.parametrize("has_request", [True, False])
def test_context_success_and_outside_request(has_request):
    out = run(
        r"""
local _, _, errors, ctx = helpers.fill_ctx()
helpers.save_ctx(ctx)
emit({errors=errors, redis=ctx.bw.cachestore.redis, global=ctx.bw.ip_is_global,
    has_address=ctx.bw.remote_addr ~= nil, saved=saved == ctx, applied=applied})
""",
        NO_REQUEST=not has_request,
        IP_GLOBAL=False,
        REDIS="yes",
    )
    assert out["errors"] == {} and out["redis"] is True
    assert out["has_address"] is has_request and out["saved"] is has_request
    assert out["applied"] == int(has_request)
    if has_request:
        assert out["global"] is False


@pytest.mark.parametrize("multisite", [True, False])
def test_variable_loading_filters_unknowns_and_multiple_settings(multisite):
    out = run(
        r"""
local ok, variables = helpers.load_variables(VALUES, {{settings={FLAG={}, LIST={multiple=true}}}, {}})
assert(ok, variables)
emit(variables)
""",
        FILES={"/usr/share/bunkerweb/settings.json": {"content": '{"GLOBAL":{},"MULTISITE":{},"SERVER_NAME":{}}'}},
        VALUES={
            "MULTISITE": "yes" if multisite else "no",
            "SERVER_NAME": "app.example appXexample",
            "GLOBAL": "value",
            "FLAG": "global",
            "LIST_2": "global-list",
            "FLAG_2": "not-multiple",
            "UNKNOWN": "ignored",
            "app.example_FLAG": "site",
            "app.example_LIST_3": "site-list",
            "app.example_FLAG_2": "ignored",
            "app.example_UNKNOWN_1": "ignored",
            "appXexample_FLAG": "other",
        },
    )
    assert out["global"]["GLOBAL"] == "value" and out["global"]["LIST_2"] == "global-list"
    assert "UNKNOWN" not in out["global"] and "FLAG_2" not in out["global"]
    if multisite:
        assert out["app.example"] == {"FLAG": "site", "LIST_3": "site-list"}
        assert out["appXexample"] == {"FLAG": "other"}
    else:
        assert set(out) == {"global"}


@pytest.mark.parametrize("file, message", [({"errno": 2, "error": "missing"}, "can't open settings.json"), ({"content": "{"}, "invalid settings.json")])
def test_variable_settings_failures_return_diagnostics(file, message):
    out = run("local ok,msg=helpers.load_variables({}, {}) emit({ok=ok,msg=msg})", FILES={"/usr/share/bunkerweb/settings.json": file})
    assert out["ok"] is False
    assert message in out["msg"]


def test_stream_init_logs_broken_plugin_and_dispatches_next():
    out = run(
        r"""
package.loaded["bunkerweb.helpers"] = helpers
local store = {flush_lru=function() return true end, delete_all=function() return true end,
    set=function() return true end}
package.loaded["bunkerweb.datastore"] = {new=function() return store end}
package.loaded["bunkerweb.cachestore"] = {new=function() return {purge=function() return true end} end}
local completed = false
package.preload["a_broken/a_broken"] = function()
    local p = {get_id=function() return "a_broken" end, init=function() error("broken init") end}
    p.new = function() return p end
    return p
end
package.preload["z_good/z_good"] = function()
    local p = {get_id=function() return "z_good" end, init=function()
        completed=true return {ret=true,msg="healthy"}
    end}
    p.new = function() return p end
    return p
end
local count = 0
io.popen = function()
    count = count + 1
    local names = count == 1 and {"/fixture/a_broken", "/fixture/z_good"} or {}
    return {lines=function() local n=0 return function() n=n+1 return names[n] end end, close=function() end}
end
io.lines = function() return function() return nil end end
local file = assert(io.open(INIT_FILE))
local config = file:read("*a")
file:close()
-- Execute the entire nginx Lua block, removing only its nginx directive wrapper.
local block = assert(config:match("^init_by_lua_block%s*{(.*)}%s*$"))
assert(load(block, "@" .. INIT_FILE))()
emit({completed=completed, logs=LOGS})
""",
        subsystem="stream",
        INIT_FILE=str(ROOT / "src/common/confs/init-stream-lua.conf"),
        FILES={
            "/var/tmp/bunkerweb/reloading": {"errno": 2, "error": "missing"},
            "/etc/nginx/variables.env": {"content": ""},
            "/usr/share/bunkerweb/settings.json": {"content": "{}"},
            "/usr/share/bunkerweb/core/order.json": {"content": "{}"},
            **{f"/fixture/{name}/plugin.json": {"content": json.dumps({**manifest(), "id": name})} for name in ("a_broken", "z_good")},
        },
    )
    assert out["completed"] is True
    errors = [message for level, message in out["logs"] if level == "ERR"]
    assert len(errors) == 1
    assert "a_broken:init() failed" in errors[0] and "broken init" in errors[0]
    assert any("z_good:init() call successful : healthy" in message for _, message in out["logs"])
