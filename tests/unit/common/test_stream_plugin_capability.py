"""The stream VM must not require a plugin whose plugin.json says ``"stream": "no"``.

``helpers.load_plugin`` used to require every plugin it found, whatever its ``stream`` value and whatever VM it
ran in. An HTTP-only plugin whose module gates on the HTTP ngx_lua version raises at require time in the stream
VM (stream ngx_lua reports 17), and since 1.6.17 the stream init aborts on a failed load: any stream service
stopped nginx from starting. The real ``helpers.lua`` runs under plain ``lua``; ``require_plugin`` is replaced by
a spy, so a test asserts whether the loader tried to import the plugin, not what the plugin does.
"""

import json

import pytest
from _lua_core_helpers import BW_MODULES, LUA, run_core  # type: ignore

pytestmark = pytest.mark.skipif(LUA is None, reason="no Lua interpreter on PATH")

# The spy fails like an HTTP-only module raising on the stream ngx_lua version.
SETUP = r"""
package.loaded["resty.core.base"] = {}
package.loaded["bunkerweb.ctx"] = {}
package.loaded["bunkerweb.utils"] = {
    get_phases = function() return { "init", "init_workers", "timer", "preread" } end,
}
local helpers = dofile(MODULE)
local calls = {}
helpers.require_plugin = function(id)
    calls[#calls + 1] = id
    if FAILING[id] then
        return false, "require error for plugin " .. id .. " : ngx_lua 0.9.5+ required"
    end
    return { init = true, init_workers = true, timer = true, preread = true, new = true }, "ok"
end
"""


def _manifest(tmp_path, plugin_id="http_only", stream: str | None = "no", **overrides):
    path = tmp_path / f"{plugin_id}.json"
    data = {
        "id": plugin_id,
        "name": plugin_id,
        "description": "Regression fixture",
        "version": "1.0",
        "stream": stream,
        "settings": {"TEST_FLAG": {"context": "global"}},
    }
    data.update(overrides)
    path.write_text(json.dumps({k: v for k, v in data.items() if v is not None}))
    return path


def _load(manifest, subsystem, failing=("http_only",)):
    return run_core(
        BW_MODULES / "helpers.lua",
        SETUP + r"""
local ok, metadata = helpers.load_plugin(MANIFEST)
emit({
    ok = ok,
    imports = #calls,
    phases = type(metadata) == "table" and metadata.phases and #metadata.phases or -1,
    kept_settings = type(metadata) == "table" and type(metadata.settings) == "table" and metadata.settings.TEST_FLAG ~= nil or false,
    message = type(metadata) == "string" and metadata or "",
})
""",
        subsystem=subsystem,
        phase="init",
        MANIFEST=str(manifest),
        FAILING={name: True for name in failing},
    )


def test_stream_keeps_http_only_metadata_without_importing_code(tmp_path):
    result = _load(_manifest(tmp_path), "stream")
    assert result["ok"] is True
    assert result["imports"] == 0
    assert result["phases"] == 0
    assert result["kept_settings"] is True


def test_http_still_requires_a_plugin_without_stream_support(tmp_path):
    result = _load(_manifest(tmp_path), "http", failing=())
    assert result["ok"] is True
    assert result["imports"] == 1
    assert result["phases"] == 4


def test_http_failed_require_of_a_plugin_without_stream_support_still_fails(tmp_path):
    result = _load(_manifest(tmp_path), "http")
    assert result["ok"] is False
    assert result["imports"] == 1
    assert "ngx_lua 0.9.5+ required" in result["message"]


@pytest.mark.parametrize("stream", ["yes", "partial"])
def test_stream_still_requires_a_plugin_with_stream_support(tmp_path, stream):
    result = _load(_manifest(tmp_path, "stream_ok", stream), "stream", failing=())
    assert result["ok"] is True
    assert result["imports"] == 1
    assert result["phases"] == 4


@pytest.mark.parametrize("stream", ["yes", "partial"])
def test_stream_failed_require_of_a_supported_plugin_still_fails(tmp_path, stream):
    result = _load(_manifest(tmp_path, "stream_ok", stream), "stream", failing=("stream_ok",))
    assert result["ok"] is False
    assert result["imports"] == 1
    assert "ngx_lua 0.9.5+ required" in result["message"]


@pytest.mark.parametrize("subsystem", ["http", "stream"])
def test_malformed_manifest_still_fails(tmp_path, subsystem):
    result = _load(_manifest(tmp_path, stream=None), subsystem)
    assert result["ok"] is False
    assert result["imports"] == 0
    assert "missing field(s)" in result["message"] and "stream" in result["message"]


def test_stream_orders_exclude_the_plugin_without_stream_support(tmp_path):
    order = tmp_path / "order.json"
    order.write_text(json.dumps({"init": ["http_only", "stream_ok"], "timer": ["http_only"]}))
    http_only = _manifest(tmp_path, "http_only", "no")
    stream_ok = _manifest(tmp_path, "stream_ok", "yes")
    result = run_core(
        BW_MODULES / "helpers.lua",
        r"""
local real_open = io.open
io.open = function(path, mode)
    if path == "/usr/share/bunkerweb/core/order.json" then
        path = ORDER_FILE
    end
    return real_open(path, mode)
end
"""
        + SETUP
        + r"""
local plugins = {}
for _, manifest in ipairs({ HTTP_ONLY, STREAM_OK }) do
    local ok, plugin = helpers.load_plugin(manifest)
    assert(ok, plugin)
    plugins[#plugins + 1] = plugin
end
local ok, orders = helpers.order_plugins(plugins, {})
assert(ok, orders)
emit({ init = orders.init, timer = orders.timer, preread = orders.preread, imports = calls })
""",
        subsystem="stream",
        phase="init",
        ORDER_FILE=str(order),
        HTTP_ONLY=str(http_only),
        STREAM_OK=str(stream_ok),
        FAILING={"http_only": True},
    )
    assert result["init"] == ["stream_ok"]
    assert result["timer"] == ["stream_ok"]
    assert result["preread"] == ["stream_ok"]
    assert result["imports"] == ["stream_ok"]
