"""Execute the shipped HTTP/Stream dispatchers around detect-mode plugin statuses."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
HTTP = ROOT / "src" / "common" / "confs" / "server-http" / "access-lua.conf"
STREAM = ROOT / "src" / "common" / "confs" / "server-stream" / "preread-stream-lua.conf"
LUA = shutil.which("lua") or shutil.which("luajit")

pytestmark = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")

TARGETS = (
    (HTTP, "access", "access"),
    (STREAM, "preread", "preread"),
)
DENY_TARGETS = (
    (HTTP, "access", "access", 444),
    (STREAM, "preread", "preread", 444),
    (HTTP, "access", "access", 429),
)


def _lua_block(path: Path, directive: str) -> str:
    source = path.read_text(encoding="utf-8")
    start = source.index("{", source.index(f"{directive}_by_lua_block"))
    body_start = start + 1
    depth = 0
    for index in range(start, len(source)):
        depth += source[index] == "{"
        depth -= source[index] == "}"
        if depth == 0:
            return source[body_start:index]
    raise AssertionError(f"unbalanced Lua block in {path}")


PREAMBLE = r"""
local plugin_calls, whitelist_calls, ban_calls, reason_calls, exit_calls = 0, 0, 0, 0, 0
local reason_id, reason_mode, reason_marker, exit_status = nil, nil, nil, nil
local ctx = {
    bw = {
        remote_addr = "192.0.2.1",
        server_name = "example.test",
        is_whitelisted = INITIAL_WHITELISTED and "yes" or "no",
    },
}
local results = {
    first = { ret = true, msg = "first result", status = RETURN_STATUS, data = { marker = "real-data" } },
    second = { ret = true, msg = "must not run", status = 444, data = {} },
    whitelist = { ret = true, msg = "whitelist result", status = WHITELISTED and 0 or nil, data = {} },
}

ngx = {
    ERR = "ERR",
    INFO = "INFO",
    WARN = "WARN",
    NOTICE = "NOTICE",
    OK = 0,
    HTTP_MOVED_TEMPORARILY = 302,
    HTTP_BAD_REQUEST = 400,
    HTTP_TOO_MANY_REQUESTS = 429,
    HTTP_NOT_ALLOWED = 405,
    req = { is_internal = function() return false end },
    var = { server_name = "example.test" },
    shared = { internalstore = {}, internalstore_stream = {} },
    exit = function(status)
        exit_calls = exit_calls + 1
        exit_status = status
        return status
    end,
    redirect = function() error("unexpected redirect") end,
}

package.loaded["bunkerweb.logger"] = {
    new = function() return { log = function() end } end,
}
package.loaded["bunkerweb.helpers"] = {
    fill_ctx = function() return true, "ok", nil, ctx end,
    export_ctx_vars = function() return true end,
    save_ctx = function() return true end,
    require_plugin = function(id)
        local loaded = { id = id }
        loaded[PHASE] = function() end
        return loaded
    end,
    new_plugin = function(plugin) return true, plugin end,
    call_plugin = function(plugin)
        plugin_calls = plugin_calls + 1
        if plugin.id == "whitelist" then
            whitelist_calls = whitelist_calls + 1
            if WHITELISTED then ctx.bw.is_whitelisted = "yes" end
        end
        return true, results[plugin.id]
    end,
}
package.loaded["bunkerweb.utils"] = {
    is_whitelisted = function(context) return context.bw.is_whitelisted == "yes" end,
    is_banned = function()
        ban_calls = ban_calls + 1
        return BANNED, "ban", 60, {}
    end,
    set_reason = function(id, data, _, mode)
        reason_calls = reason_calls + 1
        reason_id = id
        reason_mode = mode
        reason_marker = data.marker
    end,
    get_deny_status = function() return 444 end,
    save_session = function() return true, "saved" end,
    get_security_mode = function() return SECURITY_MODE end,
}
package.loaded["bunkerweb.datastore"] = {
    new = function()
        return { get = function() return { [PHASE] = HAS_WHITELIST and { "whitelist", "first", "second" } or { "first", "second" } } end }
    end,
}
package.loaded["bunkerweb.cachestore"] = {
    new = function() return { update = function() return true end } end,
}
"""


def _run(
    path: Path,
    directive: str,
    phase: str,
    status: int,
    *,
    whitelisted: bool,
    banned: bool = False,
    security_mode: str = "detect",
) -> list[str]:
    settings = (
        f'local PHASE = "{phase}"\n'
        f"local RETURN_STATUS = {status}\n"
        f"local WHITELISTED = {str(whitelisted).lower()}\n"
        f"local INITIAL_WHITELISTED = {str(whitelisted and path == HTTP).lower()}\n"
        f"local HAS_WHITELIST = {str(path == STREAM).lower()}\n"
        f"local BANNED = {str(banned).lower()}\n"
        f'local SECURITY_MODE = "{security_mode}"\n'
    )
    script = (
        settings
        + PREAMBLE
        + "\nlocal function run()\n"
        + _lua_block(path, directive)
        + "\nend\n"
        + r"""
local result = run()
print(table.concat({
    tostring(plugin_calls), tostring(whitelist_calls), tostring(ban_calls), tostring(reason_calls), tostring(reason_id),
    tostring(reason_mode), tostring(reason_marker), tostring(exit_calls),
    tostring(exit_status), tostring(result),
}, "|"))
"""
    )
    result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip().split("|")


@pytest.mark.parametrize(("path", "directive", "phase"), TARGETS)
def test_detect_whitelist_is_a_terminal_allow_without_a_reason(path: Path, directive: str, phase: str):
    output = _run(path, directive, phase, 0, whitelisted=True)
    assert output == (["1", "0", "0", "0", "nil", "nil", "nil", "1", "0", "0"] if path == HTTP else ["1", "1", "0", "0", "nil", "nil", "nil", "1", "0", "0"])


@pytest.mark.parametrize(
    ("path", "directive", "phase", "status"),
    DENY_TARGETS,
)
def test_detect_denies_report_once_without_blocking(path: Path, directive: str, phase: str, status: int):
    output = _run(path, directive, phase, status, whitelisted=False)
    assert output == (
        ["1", "0", "1", "1", "first", "detect", "real-data", "0", "nil", "true"]
        if path == HTTP
        else ["2", "1", "1", "1", "first", "detect", "real-data", "0", "nil", "true"]
    )


def test_stream_whitelist_skips_ban_lookup_and_block():
    output = _run(STREAM, "preread", "preread", 0, whitelisted=True, banned=True, security_mode="block")
    assert output == ["1", "1", "0", "0", "nil", "nil", "nil", "1", "0", "0"]


def test_stream_ban_blocks_when_whitelist_does_not_allow():
    output = _run(STREAM, "preread", "preread", 0, whitelisted=False, banned=True, security_mode="block")
    assert output == ["1", "1", "1", "1", "ban", "block", "nil", "1", "444", "444"]
