"""Reverse scan of an IPv6 client: the port is dialled as ``[addr]``, and "could not try" is not "closed".

``src/common/core/reversescan/reversescan.lua`` is run as shipped under plain Lua with the OpenResty socket
replaced by a recorder. The socket layer parses ``host:port`` like a URL, so a bare IPv6 literal fails there.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
LUA = shutil.which("lua") or shutil.which("luajit")
MODULE = Path(os.environ.get("BW_I3A_REVERSESCAN", str(ROOT / "src" / "common" / "core" / "reversescan" / "reversescan.lua")))

pytestmark = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")

PREAMBLE = r"""
package.path = ROOT .. "/src/bw/lua/?.lua;" .. package.path
local class = dofile(ROOT .. "/src/bw/lua/middleclass.lua")
package.preload["middleclass"] = function() return class end
local plugin = class("plugin")
PLUGIN_VARS = {}
LOGS = {}
function plugin:initialize(id, ctx)
    self.id, self.ctx = id, ctx
    self.variables = PLUGIN_VARS
    self.logger = { log = function(_, level, msg) LOGS[#LOGS + 1] = msg end }
end
function plugin:ret(ok, msg, status) return { ok = ok, msg = msg, status = status } end
function plugin:set_metric() end
package.preload["bunkerweb.plugin"] = function() return plugin end
package.preload["bunkerweb.utils"] = function()
    return { kill_all_threads = function() end, get_deny_status = function() return 403 end, parse_duration = function() return 1000 end }
end
DIALLED = {}
CONNECT_ANSWER = {true}
ngx = { ERR = 3, WARN = 4, config = { subsystem = "http" } }
-- the module keeps ngx.thread.spawn / wait as upvalues: they run the scan at once and hand its results back
ngx.thread = {
    spawn = function(fn, ip, port, timeout) return { results = { fn(ip, port, timeout) } } end,
    wait = function(thread) return true, table.unpack(thread.results) end,
}
ngx.socket = { tcp = function()
    return {
        settimeout = function() end,
        connect = function(_, host, port) DIALLED[#DIALLED + 1] = host .. "|" .. port; return CONNECT_ANSWER[1], CONNECT_ANSWER[2] end,
        close = function() end,
    }
end }
unpack = unpack or table.unpack
REVERSESCAN = dofile(MODULE)
"""


def run(body: str) -> str:
    script = f"ROOT = {str(ROOT)!r}\nMODULE = {str(MODULE)!r}\n" + PREAMBLE + body
    result = subprocess.run([str(LUA), "-"], input=script, capture_output=True, text=True, check=False, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


def test_an_ipv6_client_is_dialled_with_brackets_and_an_ipv4_one_without():
    out = run("""
REVERSESCAN.scan("2001:db8::1", 8080, 1000)
REVERSESCAN.scan("192.0.2.1", 22, 1000)
print(table.concat(DIALLED, ","))
""")
    assert out == "[2001:db8::1]|8080,192.0.2.1|22"


def test_an_open_port_is_open_and_a_refused_or_timed_out_one_is_closed():
    out = run("""
local function scan(answer_ok, answer_err)
    CONNECT_ANSWER = {answer_ok, answer_err}
    local open, port, err = REVERSESCAN.scan("2001:db8::1", 8080, 1000)
    return tostring(open) .. "/" .. tostring(port) .. "/" .. tostring(err)
end
print(scan(true), scan(nil, "connection refused"), scan(nil, "timeout"))
""")
    assert out.split("\t") == ["true/8080/nil", "false/8080/nil", "false/8080/nil"]


def test_a_port_that_could_not_be_tried_reports_the_error_and_is_not_called_closed():
    out = run("""
CONNECT_ANSWER = {nil, "no route to host"}
local open, port, err = REVERSESCAN.scan("2001:db8::1", 8080, 1000)
print(tostring(open), port, err)
""")
    assert out.split("\t") == ["false", "8080", "no route to host"]


def test_access_does_not_cache_a_port_it_could_not_try():
    out = run("""
PLUGIN_VARS = { USE_REVERSE_SCAN = "yes", REVERSE_SCAN_PORTS = "8080", REVERSE_SCAN_TIMEOUT = "1s" }
CONNECT_ANSWER = {nil, "no route to host"}
local scanner = REVERSESCAN:new({ bw = { remote_addr = "2001:db8::1" } })
local cached = {}
scanner.is_in_cache = function() return true, nil end
scanner.add_to_cache = function(_, key, value) cached[#cached + 1] = key .. "=" .. value; return true end
local result = scanner:access()
print(tostring(result.ok), #cached, #LOGS)
""")
    assert out.split("\t") == ["true", "0", "1"]


def test_an_open_port_is_denied_even_when_the_cache_write_fails():
    out = run("""
PLUGIN_VARS = { USE_REVERSE_SCAN = "yes", REVERSE_SCAN_PORTS = "8080", REVERSE_SCAN_TIMEOUT = "1s" }
CONNECT_ANSWER = {true}
local scanner = REVERSESCAN:new({ bw = { remote_addr = "192.0.2.1" } })
scanner.is_in_cache = function() return true, nil end
scanner.add_to_cache = function() return false, "no memory" end
local result = scanner:access()
print(tostring(result.ok), result.status, #LOGS, LOGS[1])
""")
    assert out.split("\t") == ["true", "403", "1", "error while adding element to cache : no memory"]


def test_a_cache_write_failure_does_not_skip_the_other_ports_results():
    out = run("""
PLUGIN_VARS = { USE_REVERSE_SCAN = "yes", REVERSE_SCAN_PORTS = "22 80", REVERSE_SCAN_TIMEOUT = "1s" }
CONNECT_ANSWER = {nil, "connection refused"}
local scanner = REVERSESCAN:new({ bw = { remote_addr = "192.0.2.1" } })
scanner.is_in_cache = function() return true, nil end
local attempts = 0
scanner.add_to_cache = function() attempts = attempts + 1; return false, "no memory" end
local result = scanner:access()
print(tostring(result.ok), result.status, attempts, #LOGS)
""")
    assert out.split("\t") == ["false", "nil", "2", "2"]
