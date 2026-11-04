"""Harness for the Lua behaviour tests of the country, crowdsec, errors, robotstxt and ssl plugins.

It builds on ``_lua_state_helpers.py`` (read-only): the pure-Lua ``emit`` / SHA-256 base and the
shared ``bunkerweb.plugin`` / ``bunkerweb.utils`` / OpenResty stand-ins. On top it adds what these
five modules need and the shared harness lacks: ``ngx.header`` / ``ngx.say`` / ``ngx.req``, a
per-name ``get_variable``, ``get_country``, ``rand``, ``resty.template`` and a flat ``cjson``.

Every stand-in is driven by a global the test sets, so an assertion is about what the module
decided. ``module_path`` (``BW_L3_<NAME>``) lets a mutation run point a test at a mutated **copy**
of a module, without ever touching ``src/``.
"""

import os
from pathlib import Path

from _lua_state_helpers import BASE_LUA, CORE, LUA, PLUGIN_LUA, last_json, run_lua, to_lua  # type: ignore  # noqa: F401

ROOT = Path(__file__).resolve().parents[3]


def module_path(env_name: str, default: Path) -> Path:
    """The module under test: the real file, or the mutated copy named by ``BW_L3_<env_name>``."""
    return Path(os.environ.get(f"BW_L3_{env_name}", str(default)))


EXTRA_LUA = r"""
SAID, RENDERS, TEMPLATE_CALLS = {}, {}, 0
NOW = 1000000
GETVAR = {}
MULTI_VARS, MULTI_ERR = {}, nil
SECURITY_MODE = "block"
BODY = nil
SUBSYSTEM = SUBSYSTEM or "http"

ngx.HTTP_MOVED_PERMANENTLY = 301
ngx.header = {}
ngx.config = { subsystem = SUBSYSTEM }
ngx.say = function(text) SAID[#SAID + 1] = text end
ngx.time = function() return NOW end
ngx.decode_base64 = function(data)
    local chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    -- like the real one: nil on anything that is not well-formed base64
    if #data % 4 ~= 0 or not data:match("^[A-Za-z0-9+/]*=?=?$") then return nil end
    local bits = data:gsub(".", function(x)
        if x == "=" then return "" end
        local f, r = chars:find(x, 1, true) - 1, ""
        for i = 6, 1, -1 do r = r .. (f % 2 ^ i - f % 2 ^ (i - 1) > 0 and "1" or "0") end
        return r
    end)
    return (bits:gsub("%d%d%d?%d?%d?%d?%d?%d?", function(x)
        if #x ~= 8 then return "" end
        local c = 0
        for i = 1, 8 do c = c + (x:sub(i, i) == "1" and 2 ^ (8 - i) or 0) end
        return string.char(c)
    end))
end
ngx.req = {
    read_body = function() end,
    get_body_data = function() return BODY end,
    get_body_file = function() return nil end,
}

local utils = package.loaded["bunkerweb.utils"]
utils.get_variable = function(name)
    local value = GETVAR[name]
    if value == nil then return nil, "no such variable " .. name end
    return value, "success"
end
utils.get_multiple_variables = function()
    if MULTI_ERR then return nil, MULTI_ERR end
    return MULTI_VARS, "success"
end
utils.get_security_mode = function() return SECURITY_MODE end
utils.get_country = function(ip)
    COUNTRY_CALLS = (COUNTRY_CALLS or 0) + 1
    if COUNTRY == nil then return nil, "country lookup failed" end
    return COUNTRY
end
utils.match_header_rules = function() return HEADER_MATCH end
utils.rand = function(len) return string.rep("n", len) end
utils.parse_duration = function(value) return tonumber(value) end

-- Flat JSON (string values, the only shape these plugins store); decode is the inverse.
local cj = { array_mt = {} }
function cj.encode(t)
    local keys = {}
    for k in pairs(t) do keys[#keys + 1] = k end
    table.sort(keys)
    local parts = {}
    for _, k in ipairs(keys) do parts[#parts + 1] = '"' .. k .. '":"' .. tostring(t[k]) .. '"' end
    return "{" .. table.concat(parts, ",") .. "}"
end
function cj.decode(s)
    if type(s) ~= "string" or s:sub(1, 1) ~= "{" then return nil end
    local t = {}
    for k, v in s:gmatch('"([^"]+)":"([^"]*)"') do t[k] = v end
    return t
end
package.loaded["cjson"] = cj
package.loaded["cjson.safe"] = cj

package.loaded["resty.template"] = {
    render = function(name, data) TEMPLATE_CALLS = TEMPLATE_CALLS + 1 RENDERS[#RENDERS + 1] = { name = name, data = data } end,
}
"""


def build_script(module: Path, body: str, *, fs_root: Path | None = None, preamble: str = "") -> str:
    """Base + shared plugin stubs + this lane's extras + ``preamble`` + the module as ``PLUGIN`` + ``body``."""
    import json

    header = f"BW_FS = {json.dumps(str(fs_root)) if fs_root else 'nil'}\n"
    return BASE_LUA + header + PLUGIN_LUA + EXTRA_LUA + preamble + f"\nPLUGIN = dofile({json.dumps(str(module))})\n" + body


def run_module(module: Path, body: str, *, fs_root: Path | None = None, preamble: str = ""):
    """Run ``body`` against the plugin module and return the value it ``emit``-ted last."""
    return last_json(run_lua(build_script(module, body, fs_root=fs_root, preamble=preamble)))
