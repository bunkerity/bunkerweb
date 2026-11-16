"""Only workers from the requested reload can confirm it; syntax checks cannot."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
API = ROOT / "src/bw/lua/bunkerweb/api.lua"
pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="lua is not installed")


def function(name):
    found = re.search(rf"^local function {name}\(.*?^end$", API.read_text(), re.M | re.S)
    assert found, name
    return found.group(0)


def run_lua(script):
    result = subprocess.run(["lua", "-"], input=script, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.mark.parametrize("ready", ["none", "stale", "current"])
@pytest.mark.parametrize("exiting", [False, True])
def test_confirmation_requires_current_readiness(ready, exiting):
    # A clean nginx -t and even an exiting worker cannot certify this token's init.
    script = r"""
local now, marker = 0, "current"
local data = { misc_ready = "ok", misc_ready_stale = "ok" }
local ready = "%s"
local tests = 0
ngx = {
    now = function() return now end,
    update_time = function() end,
    sleep = function(seconds)
        now = now + seconds
        if ready == "current" then data.misc_ready_current = "ok"; marker = nil end
    end,
    worker = { exiting = function() return %s end },
}
internalstore = { get = function(_, key) return data[key] end }
shared = { internalstore = internalstore }
RELOAD_CONFIRM_TIMEOUT = 2
read_reload_marker = function() return marker end
test_nginx_conf = function() tests = tests + 1; return true, "syntax is ok" end
%s
local ok, detail = confirm_reload("current")
assert(ok == %s, tostring(ok) .. ": " .. tostring(detail))
assert(tests == 0, "nginx -t cannot confirm init_by_lua")
if not ok then assert(now >= 2, "timeout returned before its deadline") end
"""
    run_lua(script % (ready, str(exiting).lower(), function("confirm_reload"), str(ready == "current").lower()))


def test_rejected_init_returns_http_failure_even_when_syntax_passes():
    script = r"""
local now, marker, written = 0, nil, nil
local data = {}
ngx = {
    now = function() return now end, update_time = function() end,
    sleep = function(seconds) now = now + seconds; marker = nil end,
    worker = { exiting = function() return false end },
}
shared = { internalstore = { get = function(_, key) return data[key] end } }
internalstore = shared.internalstore
RELOAD_CONFIRM_TIMEOUT = 2
HTTP_INTERNAL_SERVER_ERROR, HTTP_OK, ERR, NOTICE = 500, 200, 1, 2
VARIABLES_PATH = "/etc/nginx/variables.env"
logger = { log = function() end }
check_audit_storage = function() return true end
test_nginx_conf = function() return true, "syntax is ok" end
new_swap_token = function() return "current" end
read_reload_marker = function() return marker end
clear_reload_marker = function(token) if marker == token then marker = nil end end
get_variable = function() return "10s" end
utils = { parse_duration = function() return 10000 end }
open = function(_, mode)
    if mode == "w" then
        return { write = function(_, value) marker, written = value, value; return true end,
                 close = function() return true end }
    end
    if marker then return { read = function() return marker end, close = function() end } end
end
get_master_pid = function() return 1 end
kill = function() return true end
execute = function() error("unexpected fallback") end
%s
%s
local status, level, detail = reload_locked("yes")
assert(status == 500 and level == "error", tostring(status) .. ": " .. tostring(detail))
assert(written == "current", "marker must carry this reload's token")
"""
    run_lua(script % (function("confirm_reload"), function("reload_locked")))


@pytest.mark.parametrize("loading", ["no", "yes"])
@pytest.mark.parametrize("token,marker", [("current", "current"), ("stale", "current")])
def test_worker_publishes_captured_token_only(loading, token, marker):
    source = (ROOT / "src/common/confs/init-worker-lua.conf").read_text()
    body = source.split("init_worker_by_lua_block {", 1)[1].rsplit("\n}", 1)[0]
    script = r"""
local marker, captured = "%s", "%s"
local data = { misc_ready = "ok" }
local timers = {}
local store = {
    get = function(_, key)
        if key == "plugins_order" then return { init_workers = {}, init_worker = {}, timer = {} } end
        if data[key] then return data[key] end
        return nil, "not found"
    end,
    set = function(_, key, value) data[key] = value; return true end,
}
package.loaded["bunkerweb.reload_marker_token"] = captured
package.preload["bunkerweb.helpers"] = function() return {} end
package.preload["bunkerweb.utils"] = function() return {
    get_variable = function(key) if key == "IS_LOADING" then return "%s" end; return "info" end,
} end
package.preload["bunkerweb.logger"] = function() return { new = function() return { log = function() end } end } end
package.preload["bunkerweb.datastore"] = function() return { new = function() return store end } end
package.preload["resty.lock"] = function() return {
    new = function() return { lock = function() return 0 end, unlock = function() return true end } end,
} end
ngx = {
    ERR = 1, INFO = 2, WARN = 3, NOTICE = 4, config = { subsystem = "http" }, shared = {},
    worker = { id = function() return 0 end, pid = function() return 1 end, exiting = function() return false end },
    timer = { at = function(_, callback) timers[#timers+1] = callback; return true end },
}
io.open = function() if marker then return { read = function() return marker end, close = function() end } end end
os.remove = function() marker = nil; return true end
local function init_worker()
%s
end
init_worker()
if timers[1] then timers[1](false) end
assert(data["misc_ready_" .. captured] == "ok", "captured readiness was not published")
if captured == "current" then
    assert(marker == nil, "matching marker not cleared")
else
    assert(data.misc_ready_current == nil, "old worker confirmed a new reload")
    assert(marker == "current", "old worker cleared a new marker")
end
"""
    run_lua(script % (marker, token, loading, body))
