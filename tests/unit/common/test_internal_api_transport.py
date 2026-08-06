import shutil
import subprocess
from pathlib import Path

import jinja2
import pytest

ROOT = Path(__file__).resolve().parents[3]
API_CONF = ROOT / "src" / "common" / "confs" / "api.conf"
HTTP_CONF = ROOT / "src" / "common" / "confs" / "http.conf"
INTERNAL_API_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "internal_api.lua"
INIT_HTTP_CONF = ROOT / "src" / "common" / "confs" / "init-lua.conf"
INIT_STREAM_CONF = ROOT / "src" / "common" / "confs" / "init-stream-lua.conf"
LUA = shutil.which("lua") or shutil.which("luajit")


def _lua_block(path: Path, directive: str) -> str:
    source = path.read_text(encoding="utf-8")
    start = source.index("{", source.index(f"{directive}_by_lua_block"))
    depth = 0
    for index in range(start, len(source)):
        depth += source[index] == "{"
        depth -= source[index] == "}"
        if depth == 0:
            return source[start + 1 : index]  # noqa: E203
    raise AssertionError(f"unbalanced Lua block in {path}")


def test_private_listener_survives_when_use_api_is_disabled():
    http = (
        jinja2.Environment()
        .from_string(HTTP_CONF.read_text(encoding="utf-8"))
        .render(
            ACCESS_LOG="off",
            USE_API="no",
            USE_IPV6="no",
            DNS_RESOLVERS="127.0.0.1",
            INTERNALSTORE_MEMORY_SIZE="1m",
            DATASTORE_MEMORY_SIZE="1m",
            CACHESTORE_LOCKS_MEMORY_SIZE="1m",
            CACHESTORE_MEMORY_SIZE="1m",
            LOG_LEVEL="notice",
            MULTISITE="no",
            DISABLE_DEFAULT_SERVER="no",
            IS_LOADING="no",
            SERVER_NAME="",
            SERVER_NAMES_HASH_BUCKET_SIZE="",
            all={},
            normalize_memory_size=lambda value: value,
        )
    )
    rendered = (
        jinja2.Environment()
        .from_string(API_CONF.read_text(encoding="utf-8"))
        .render(
            USE_API="no",
            API_SERVER_NAME="bwapi",
            API_LISTEN_HTTP="yes",
            API_LISTEN_HTTPS="yes",
            API_LISTEN_IP="192.0.2.1",
            API_HTTP_PORT="5000",
            API_HTTPS_PORT="5443",
        )
    )

    assert "include /etc/nginx/api.conf;" in http
    assert "listen unix:/var/run/bunkerweb/api-internal.sock;" in rendered
    assert 'ctx.bw.http_host ~= "bwapi"' in rendered
    assert 'ctx.bw.remote_addr == "unix:"' in rendered
    assert 'internalstore:get("internal_api_token", true)' in rendered
    assert "listen 192.0.2.1:" not in rendered
    assert "listen 127.0.0.1:5000" not in rendered
    assert "listen 127.0.0.1:5443" not in rendered


@pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")
def test_internal_client_uses_the_socket_and_injects_internal_authentication():
    script = r"""
local captured = {}
local variables = { global = { API_SERVER_NAME = "bwapi" } }

package.preload["bunkerweb.datastore"] = function()
    return { new = function() return { get = function(_, key) if key == "variables" then return variables end return "internal-secret" end } end }
end
package.preload["resty.http"] = function()
    return {
        new = function()
            return {
                set_timeout = function(_, timeout) captured.timeout = timeout end,
                connect = function(_, options) captured.connect = options return true end,
                request = function(_, options)
                    captured.request = options
                    return { status = 200, read_body = function() return "ack" end }
                end,
                close = function() end,
            }
        end,
    }
end

ngx = { config = { subsystem = "stream" }, shared = { internalstore_stream = {} } }
local internal_api = dofile(arg[1])
local response, err = internal_api.request("/metrics/stream-reports", {
    method = "POST",
    timeout = 1234,
    headers = { Host = "spoofed", authorization = "Bearer spoofed", ["X-BunkerWeb-Internal-Token"] = "spoofed", ["Content-Type"] = "application/json" },
    body = "payload",
})

assert(response and not err and response.status == 200 and response.body == "ack")
assert(captured.timeout == 1234)
assert(captured.connect.host == "unix:/var/run/bunkerweb/api-internal.sock")
assert(captured.request.path == "/metrics/stream-reports" and captured.request.method == "POST")
assert(captured.request.headers.Host == "bwapi")
assert(captured.request.headers.Authorization == nil)
assert(captured.request.headers.authorization == nil)
assert(captured.request.headers["X-BunkerWeb-Internal-Token"] == "internal-secret")
assert(captured.request.headers["Content-Type"] == "application/json")
assert(captured.request.body == "payload")
"""
    result = subprocess.run([LUA, "-", str(INTERNAL_API_LUA)], input=script, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_unix_peer_requires_dedicated_token_and_allowlisted_route():
    nginx = API_CONF.read_text(encoding="utf-8")

    assert 'ctx.bw.remote_addr == "unix:"' in nginx
    assert 'internalstore:get("internal_api_token", true)' in nginx
    assert "provided ~= token or not allowed_route" in nginx
    assert 'ctx.bw.uri == "/metrics/stream-reports"' in nginx
    assert 'ctx.bw.uri == "/ban"' in nginx
    assert 'ctx.bw.uri == "/unban"' in nginx
    assert 'ctx.bw.uri == "/bans"' in nginx
    assert "api:is_allowed_token()" in nginx
    assert "api:is_allowed_ip()" in nginx


def test_internal_transport_does_not_use_the_public_api_token():
    internal_api = INTERNAL_API_LUA.read_text(encoding="utf-8")
    nginx = API_CONF.read_text(encoding="utf-8")

    assert 'get_variable("API_TOKEN")' not in internal_api
    assert 'internalstore:get("internal_api_token", true)' in internal_api
    assert "provided ~= token" in nginx


def test_internal_token_is_reused_and_transport_files_are_private():
    for init_conf in (INIT_HTTP_CONF, INIT_STREAM_CONF):
        source = init_conf.read_text(encoding="utf-8")
        assert 'open(INTERNAL_API_TOKEN_PATH, "r")' in source
        assert "random_bytes(32, true)" in source
        assert "internalstore:set(INTERNAL_API_TOKEN_KEY, internal_api_token, nil, true)" in source
        assert 'chmod 0600 " .. INTERNAL_API_TOKEN_PATH' in source
        assert "chown nginx ' .. INTERNAL_API_SOCKET_PATH" in source
        assert 'chmod 0600 " .. INTERNAL_API_SOCKET_PATH' in source


@pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")
@pytest.mark.parametrize("init_conf", (INIT_HTTP_CONF, INIT_STREAM_CONF))
def test_an_invalid_internal_token_aborts_nginx_initialization(init_conf: Path):
    script = (
        r"""
package.preload["bunkerweb.logger"] = function()
    return { new = function() return { log = function() end } end }
end
package.preload["bunkerweb.helpers"] = function() return {} end
package.preload["bunkerweb.datastore"] = function()
    return { new = function() return {} end }
end
package.preload["cjson"] = function() return { encode = function() return "{}" end } end
package.preload["resty.random"] = function() return { bytes = function() return nil end } end
package.preload["resty.string"] = function() return { to_hex = function(value) return value end } end

ngx = {
    INFO = "INFO", ERR = "ERR", NOTICE = "NOTICE", WARN = "WARN",
    config = { subsystem = "http" },
    shared = { internalstore = {}, internalstore_stream = {} },
}
io.open = function()
    return { read = function() return "invalid" end, close = function() end }
end
os.execute = function() return true, "exit", 0 end

local ok, err = pcall(function()
"""
        + _lua_block(init_conf, "init")
        + r"""
end)
assert(not ok, "init_by_lua returned normally instead of aborting startup")
assert(tostring(err):find("invalid internal API token file", 1, true), tostring(err))
"""
    )
    result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
