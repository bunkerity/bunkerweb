"""The vendored resty.ipmatcher as BunkerWeb ships it (patched by ``src/deps/misc/ipmatcher.patch``), under LuaJIT.

The module reads addresses through ``ffi`` and libc ``inet_pton``, which plain Lua 5.4 cannot run, so this file
needs a LuaJIT binary (``luajit`` on PATH, or ``BW_LUAJIT``) and skips without one. The OpenResty modules it requires
are stubbed.

Covered: one invalid list entry (a zone id, garbage, a prefix out of range) is skipped and never disables the valid
entries around it, and an IPv4-mapped IPv6 address is the IPv4 address, both as client and as rule.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
IPMATCHER = Path(os.environ.get("BW_I3A_IPMATCHER", str(ROOT / "src" / "deps" / "src" / "lua-resty-ipmatcher" / "resty" / "ipmatcher.lua")))
LUAJIT = os.environ.get("BW_LUAJIT") or shutil.which("luajit")

pytestmark = pytest.mark.skipif(not LUAJIT, reason="no LuaJIT on PATH (BW_LUAJIT)")

PRELUDE = r"""
package.preload["resty.core.base"] = function() return {new_tab = function() return {} end} end
package.preload["table.clear"] = function() return function(t) for k in pairs(t) do t[k] = nil end end end
package.preload["table.nkeys"] = function() return function(t) local n = 0; for _ in pairs(t) do n = n + 1 end; return n end end
package.preload["ngx.errlog"] = function() return {get_sys_filter_level = function() return 8 end} end
LOGS = {}
ngx = {config = {subsystem = "http"}, WARN = 5, DEBUG = 8, INFO = 7, log = function(level, ...) LOGS[#LOGS + 1] = table.concat({...}) end}
local ipmatcher = dofile(IPMATCHER_PATH)
local function matcher(list)
    local m, err = ipmatcher.new(list)
    assert(m, "new() failed: " .. tostring(err))
    return m
end
local function matches(list, ip)
    local result, err = matcher(list):match(ip)
    assert(err == nil, tostring(err))
    return result
end
"""


def run(body: str) -> str:
    script = f"IPMATCHER_PATH = {str(IPMATCHER)!r}\n" + PRELUDE + body + "\nprint('OK')\n"
    result = subprocess.run([str(LUAJIT), "-"], input=script, capture_output=True, text=True, check=False, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def test_one_invalid_entry_does_not_disable_the_valid_ones():
    run("""
local list = {"2001:db8::/32", "fe80::1%eth0", "192.0.2.0/24", "not-an-ip", "1.2.3.4/33", "::1/129"}
assert(matches(list, "2001:db8::1") == true, "valid IPv6 rule lost")
assert(matches(list, "192.0.2.77") == true, "valid IPv4 rule lost")
assert(matches(list, "2001:db9::1") == false)
assert(matches({"fe80::1%eth0"}, "fe80::1") == false, "a zone id entry must match nothing")
assert(matches({"fe80::1%eth0"}, "198.51.100.1") == false)
""")


def test_each_invalid_entry_is_logged_once():
    out = run("""
local list = {"2001:db8::/32", "fe80::1%eth0", "junk"}
matcher(list); matcher(list); matcher(list)
local seen = {}
for _, line in ipairs(LOGS) do seen[line] = (seen[line] or 0) + 1 end
for line, count in pairs(seen) do
    if line:find("ignoring invalid IP list entry", 1, true) then assert(count == 1, line .. " logged " .. count .. " times") end
end
local n = 0
for line in pairs(seen) do if line:find("ignoring invalid", 1, true) then n = n + 1 end end
assert(n == 2, "expected 2 distinct log lines, got " .. n)
""")
    assert out.strip().endswith("OK")


def test_a_mapped_client_matches_the_ipv4_rule():
    run("""
assert(matches({"192.0.2.0/24"}, "::ffff:192.0.2.1") == true)
assert(matches({"192.0.2.0/24"}, "::FFFF:C000:201") == true)
assert(matches({"192.0.2.0/24"}, "::ffff:192.0.3.1") == false)
assert(matches({"192.0.2.1"}, "::ffff:192.0.2.1") == true)
""")


def test_a_mapped_rule_still_matches_and_covers_the_ipv4_clients_it_names():
    run("""
local rule = {"::ffff:192.0.2.0/120"}
assert(matches(rule, "::ffff:192.0.2.9") == true)
assert(matches(rule, "192.0.2.9") == true)
assert(matches(rule, "192.0.3.9") == false)
assert(matches({"::ffff:192.0.2.1/128"}, "192.0.2.1") == true)
""")


def test_an_ipv6_rule_does_not_swallow_ipv4_clients():
    run("""
assert(matches({"::/0"}, "2001:db8::1") == true)
assert(matches({"::/0"}, "10.1.1.1") == false)
assert(matches({"2001:db8::/32"}, "2001:0DB8:0:0:0:0:0:1") == true)
assert(matches({"2001:db8::1"}, "2001:0DB8:0:0:0:0:0:1") == true)
""")
