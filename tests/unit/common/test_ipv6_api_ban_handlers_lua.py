"""``api.lua`` POST /ban and POST /unban: one identity per client IP, refused early when it is not an address.

The shipped handlers are sliced out of ``src/bw/lua/bunkerweb/api.lua`` and run under plain Lua with ``utils`` recording
what it receives. ``ipaddr.lua`` is the real module. The validators the handlers may reach (``normalize_ip`` and the older
``is_ipv4`` / ``is_ipv6``) are all bound in the preamble, so the same slice runs against the tree before and after the
change: the old validators were loose (anything with a colon was an IPv6 address), which is what the RED run shows.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
API_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "api.lua"
LUA = shutil.which("lua") or shutil.which("luajit")

pytestmark = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")


def _handler(route: str) -> str:
    source = API_LUA.read_text(encoding="utf-8")
    match = re.search(rf'^api\.global\.POST\["\^/{route}\$"\] = function\(self\).*?^end$', source, re.M | re.S)
    assert match, f"POST /{route} is gone from api.lua"
    return match.group(0)


PREAMBLE = r"""
package.path = ROOT .. "/src/bw/lua/?.lua;" .. package.path
local ipaddr = require("bunkerweb.ipaddr")
local HTTP_OK, HTTP_BAD_REQUEST, HTTP_INTERNAL_SERVER_ERROR = 200, 400, 500
local ERR = 3
local logger = { log = function() end }
local RESERVED_SERVICE_NAMES = { ["unknown"] = true, ["Web UI"] = true, ["bwcli"] = true, ["default server"] = true, [""] = true }
CALLS = {}
local utils = {
    add_ban = function(...) CALLS[#CALLS + 1] = { "add_ban", ... } return true end,
    remove_ban = function(...) CALLS[#CALLS + 1] = { "remove_ban", ... } return true end,
    remove_lease = function(...) CALLS[#CALLS + 1] = { "remove_lease", ... } return "removed" end,
}
-- what the handler may validate with: the shipped normalizer, and the loose checks the old code relied on
local normalize_ip = ipaddr.normalize
local is_ipv4 = function(ip) return ip:find("^%d+%.%d+%.%d+%.%d+$") ~= nil end
local is_ipv6 = function(ip) return ip:find(":", 1, true) ~= nil end
local get_country = function() return "ZZ" end
local read_body = function() end
local get_body_data = function() return BODY end
local get_body_file = function() return nil end
local open = io.open
local decode = function(value) return value end
local api = { global = { POST = {} } }
local self = {
    ctx = { bw = { remote_addr = "unix:" } },
    response = function(_, http_status, status, msg) return http_status, { status = status, msg = msg } end,
}
"""


def _lua(value) -> str:
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, dict):
        return "{" + ", ".join(f"[{json.dumps(k)}] = {_lua(v)}" for k, v in value.items()) + "}"
    raise TypeError(value)


def run(route: str, body, check: str) -> None:
    assert LUA is not None
    script = (
        f"ROOT = {json.dumps(str(ROOT))}\nBODY = {_lua(body)}\n" + PREAMBLE + _handler(route) + f'\nlocal handler = api.global.POST["^/{route}$"]\n' + check
    )
    result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True, check=False, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr


CANONICAL = [
    ("::FFFF:192.0.2.1", "192.0.2.1"),
    ("::ffff:c000:201", "192.0.2.1"),
    ("2001:DB8:0:0:0:0:0:1", "2001:db8::1"),
    ("2001:db8::1", "2001:db8::1"),
    ("192.0.2.1", "192.0.2.1"),
]
NOT_AN_ADDRESS = ["fe80::1%eth0", "[2001:db8::1]", "2001:db8::/32", "192.0.2.1/32", "2001:db8::1 ", "nope", "1:2:3", ""]


@pytest.mark.parametrize("spelling,canonical", CANONICAL)
def test_ban_stores_and_reports_the_canonical_address(spelling, canonical):
    run(
        "ban",
        {"ip": spelling, "exp": 60},
        f"""
local status, resp = handler(self)
assert(status == 200, tostring(status) .. " " .. tostring(resp and resp.msg))
assert(#CALLS == 1 and CALLS[1][1] == "add_ban", "calls: " .. #CALLS)
assert(CALLS[1][2] == {_lua(canonical)}, "add_ban got " .. tostring(CALLS[1][2]))
assert(resp.msg:find("ip " .. {_lua(canonical)} .. " banned", 1, true), resp.msg)
""",
    )


@pytest.mark.parametrize("bad", NOT_AN_ADDRESS)
def test_ban_refuses_what_is_not_an_address_before_touching_a_store(bad):
    run(
        "ban",
        {"ip": bad, "exp": 60},
        """
local status, resp = handler(self)
assert(status == 400 and resp.msg == "invalid IP address", tostring(status) .. " " .. tostring(resp and resp.msg))
assert(#CALLS == 0, "a ban reached the store for an invalid address")
""",
    )


@pytest.mark.parametrize("bad", [5, True])
def test_ban_refuses_a_non_string_address(bad):
    run(
        "ban",
        {"ip": bad},
        """
local status, resp = handler(self)
assert(status == 400 and resp.msg == "invalid IP address", tostring(status) .. " " .. tostring(resp and resp.msg))
assert(#CALLS == 0)
""",
    )


def test_ban_without_an_address_is_refused():
    run(
        "ban",
        {"exp": 60},
        """
local status, resp = handler(self)
assert(status == 400 and resp.msg == "invalid IP address", tostring(status))
assert(#CALLS == 0)
""",
    )


@pytest.mark.parametrize("spelling,canonical", CANONICAL)
def test_unban_removes_the_canonical_address(spelling, canonical):
    run(
        "unban",
        {"ip": spelling},
        f"""
local status, resp = handler(self)
assert(status == 200, tostring(status) .. " " .. tostring(resp and resp.msg))
assert(#CALLS == 1 and CALLS[1][1] == "remove_ban", "calls: " .. #CALLS)
assert(CALLS[1][2] == {_lua(canonical)}, "remove_ban got " .. tostring(CALLS[1][2]))
assert(resp.msg == "ip " .. {_lua(canonical)} .. " unbanned", resp.msg)
""",
    )


@pytest.mark.parametrize("spelling,canonical", CANONICAL)
def test_unban_of_a_lease_removes_it_under_the_canonical_address(spelling, canonical):
    run(
        "unban",
        {"ip": spelling, "lease_id": "aaaa1111aaaa1111"},
        f"""
local status, resp = handler(self)
assert(status == 200, tostring(status) .. " " .. tostring(resp and resp.msg))
assert(#CALLS == 1 and CALLS[1][1] == "remove_lease", "calls: " .. #CALLS)
assert(CALLS[1][2] == {_lua(canonical)}, "remove_lease got " .. tostring(CALLS[1][2]))
""",
    )


@pytest.mark.parametrize("bad", NOT_AN_ADDRESS)
def test_unban_refuses_what_is_not_an_address_before_touching_a_store(bad):
    run(
        "unban",
        {"ip": bad},
        """
local status, resp = handler(self)
assert(status == 400 and resp.msg == "invalid IP address", tostring(status) .. " " .. tostring(resp and resp.msg))
assert(#CALLS == 0, "an unban reached the store for an invalid address")
""",
    )


@pytest.mark.parametrize("body", [123, "text", True])
def test_unban_with_a_body_that_is_not_an_object_is_a_bad_request(body):
    run(
        "unban",
        body,
        """
local ok, status, resp = pcall(handler, self)
assert(ok, "the handler raised: " .. tostring(status))
assert(status == 400 and resp.msg == "invalid IP address", tostring(status))
assert(#CALLS == 0)
""",
    )
