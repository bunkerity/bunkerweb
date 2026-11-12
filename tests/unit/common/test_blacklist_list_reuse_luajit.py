"""The blacklist IP decisions with the real ``blacklist.lua``, ``middleclass`` and the shipped patched ``resty.ipmatcher``.

``initialize()`` hands the stored, already deduplicated arrays to the matcher without copying them when a kind has no
inline entries. The plain-Lua file ``test_blacklist_behaviour_lua.py`` stubs the matcher with an IPv4-only one, so the
IPv6 and IPv4-mapped decisions are checked here, under LuaJIT (``luajit`` on PATH, or ``BW_LUAJIT``).
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
IPMATCHER = ROOT / "src" / "deps" / "src" / "lua-resty-ipmatcher" / "resty" / "ipmatcher.lua"
MIDDLECLASS = ROOT / "src" / "bw" / "lua" / "middleclass.lua"
BLACKLIST = ROOT / "src" / "common" / "core" / "blacklist" / "blacklist.lua"
LUAJIT = os.environ.get("BW_LUAJIT") or shutil.which("luajit")

pytestmark = pytest.mark.skipif(not LUAJIT, reason="no LuaJIT on PATH (BW_LUAJIT)")

KINDS = ["IP", "RDNS", "ASN", "USER_AGENT", "URI", "IGNORE_IP", "IGNORE_RDNS", "IGNORE_ASN", "IGNORE_USER_AGENT", "IGNORE_URI"]

PRELUDE = r"""
package.preload["resty.core.base"] = function() return {new_tab = function() return {} end} end
package.preload["table.clear"] = function() return function(t) for k in pairs(t) do t[k] = nil end end end
package.preload["table.nkeys"] = function() return function(t) local n = 0; for _ in pairs(t) do n = n + 1 end; return n end end
package.preload["ngx.errlog"] = function() return {get_sys_filter_level = function() return 8 end} end
ngx = {config = {subsystem = "http"}, WARN = 5, DEBUG = 8, INFO = 7, ERR = 4, log = function() end, get_phase = function() return "access" end}
package.loaded["middleclass"] = dofile(MIDDLECLASS_PATH)
package.loaded["resty.ipmatcher"] = dofile(IPMATCHER_PATH)
STORE, CACHE = {}, {}
local class = package.loaded["middleclass"]
local base = class("plugin")
function base:initialize(name, ctx)
    self.ctx, self.variables, self.logger = ctx, VARIABLES, {log = function() end}
    self.internalstore = {get = function(_, key) return STORE[key], "ok" end}
    self.cachestore_local = {
        get = function(_, key) return true, CACHE[key] end,
        set = function(_, key, value) CACHE[key] = value; return true end,
    }
    self.set_metric = function() end
    self.is_loading, self.is_request = false, true
end
function base:ret(ok, msg, status) return {ret = ok, msg = msg, status = status} end
package.loaded["bunkerweb.plugin"] = base
package.loaded["bunkerweb.utils"] = {
    has_variable = function() return true end,
    get_deny_status = function() return 403 end,
    deduplicate_list = function(list)
        local seen, out = {}, {}
        for _, v in ipairs(list) do if not seen[v] then seen[v] = true; out[#out + 1] = v end end
        return out
    end,
    pick_header_rules = function() return {} end,
    match_header_rules = function() return nil end,
}
local blacklist = dofile(BLACKLIST_PATH)
local function plugin(client)
    return blacklist:new({bw = {server_name = "www.example.com", remote_addr = client, uri = "/", ip_is_global = false}})
end
"""


def run(stored: dict, inline: dict, body: str):
    variables = {"USE_BLACKLIST": "yes", "BLACKLIST_RDNS_GLOBAL": "no", **{f"BLACKLIST_{k}": "" for k in KINDS}, **inline}
    script = (
        f"MIDDLECLASS_PATH, IPMATCHER_PATH, BLACKLIST_PATH = {json.dumps(str(MIDDLECLASS))}, {json.dumps(str(IPMATCHER))}, {json.dumps(str(BLACKLIST))}\n"
        + f"VARIABLES = {_lua(variables)}\n"
        + PRELUDE
        + f"STORE['plugin_blacklist_lists_www.example.com'] = {_lua({k: [] for k in KINDS} | stored)}\n"
        + body
    )
    result = subprocess.run([str(LUAJIT), "-"], input=script, capture_output=True, text=True, check=False, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip().splitlines()[-1]


def _lua(value) -> str:
    if isinstance(value, dict):
        return "{" + ", ".join(f"[{json.dumps(k)}] = {_lua(v)}" for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "{" + ", ".join(_lua(v) for v in value) + "}"
    return json.dumps(value)


def verdict(client: str, stored: dict, inline: dict | None = None) -> str:
    body = f"""
CACHE = {{}}
local p = plugin({json.dumps(client)})
local result = p:access()
print(tostring(result.status) .. "|" .. result.msg)
"""
    return run(stored, inline or {}, body)


STORED = {"IP": ["192.0.2.0/24", "2001:db8::/32", "::ffff:198.51.100.0/120"], "IGNORE_IP": ["192.0.2.7", "2001:db8::7"]}


@pytest.mark.parametrize(
    ("client", "expected"),
    [
        ("192.0.2.55", "403|IP is blacklisted (info : ip)"),
        ("192.0.2.7", "nil|not blacklisted"),
        ("192.0.3.1", "nil|not blacklisted"),
        ("2001:db8::55", "403|IP is blacklisted (info : ip)"),
        ("2001:db8::7", "nil|not blacklisted"),
        ("2001:db9::1", "nil|not blacklisted"),
        ("::ffff:192.0.2.55", "403|IP is blacklisted (info : ip)"),
        ("::ffff:192.0.2.7", "nil|not blacklisted"),
        ("198.51.100.9", "403|IP is blacklisted (info : ip)"),
        ("203.0.113.1", "nil|not blacklisted"),
    ],
)
def test_ip_decisions_with_the_shared_stored_arrays(client, expected):
    assert verdict(client, STORED) == expected


def test_an_inline_entry_is_merged_for_ipv6_and_the_stored_arrays_stay_untouched():
    out = run(
        STORED,
        {"BLACKLIST_IP": "2001:db8:1::/48 192.0.2.0/24 203.0.113.0/24"},
        """
local before = {}
for kind, list in pairs(STORE["plugin_blacklist_lists_www.example.com"]) do before[kind] = table.concat(list, ",") end
local out = {}
for _, client in ipairs({"203.0.113.9", "2001:db8:1::9", "192.0.2.55", "192.0.2.7", "8.8.8.8"}) do
    CACHE = {}
    out[#out + 1] = tostring(plugin(client):access().status)
end
local p = plugin("8.8.8.8")
local same = p.lists.IGNORE_IP == STORE["plugin_blacklist_lists_www.example.com"].IGNORE_IP
local untouched = true
for kind, list in pairs(STORE["plugin_blacklist_lists_www.example.com"]) do
    if before[kind] ~= table.concat(list, ",") then untouched = false end
end
print(table.concat(out, ",") .. "|" .. tostring(same) .. "|" .. tostring(untouched) .. "|" .. #p.lists.IP)
""",
    )
    assert out == "403,403,403,nil,nil|true|true|5"
