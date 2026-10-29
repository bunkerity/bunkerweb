"""Shared bits of the T2 regression tests (Lua core and core plugins).

``BW_UNIT_T2_SRC`` points every T2 test at another ``src`` tree (``bw/lua`` and ``common/core``) so a copy with a fix
reverted can prove the test red; it defaults to the real ``src``.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SRC = Path(os.environ.get("BW_UNIT_T2_SRC") or ROOT / "src")
CORE = SRC / "common" / "core"
BW_LUA = SRC / "bw" / "lua"
BW_MODULES = BW_LUA / "bunkerweb"

LUA = shutil.which("lua") or shutil.which("lua5.4") or shutil.which("luajit")
requires_lua = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

# Plain-Lua JSON-ish ``emit``: one JSON-encoded value per line, the last line is the result.
EMIT = r"""
local function enc(v)
    local t = type(v)
    if t == "table" then
        local n, keys = 0, {}
        for k in pairs(v) do n = n + 1 keys[#keys + 1] = k end
        if n == #v then
            local p = {}
            for _, x in ipairs(v) do p[#p + 1] = enc(x) end
            return "[" .. table.concat(p, ",") .. "]"
        end
        table.sort(keys, function(a, b) return tostring(a) < tostring(b) end)
        local p = {}
        for _, k in ipairs(keys) do p[#p + 1] = enc(tostring(k)) .. ":" .. enc(v[k]) end
        return "{" .. table.concat(p, ",") .. "}"
    elseif t == "string" then
        return '"' .. v:gsub('[%c"\\]', function(c) return string.format("\\u%04x", c:byte()) end) .. '"'
    elseif t == "nil" then
        return "null"
    end
    return tostring(v)
end
function emit(v) print(enc(v)) end
unpack = unpack or table.unpack
"""


def run_script(script: str, *, timeout: int = 60):
    """Run a Lua script (``emit`` is predefined) and return the JSON value of its last emitted line."""
    assert LUA is not None
    result = subprocess.run([LUA, "-"], input=EMIT + script, capture_output=True, text=True, check=False, timeout=timeout)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def lua_str(path: Path) -> str:
    return json.dumps(str(path))


# The real ``bunkerweb/utils.lua`` with everything it requires stubbed at the OpenResty / sibling-module boundary.
# ``SUBSYSTEM`` and ``SHARED`` (name -> table-backed dict) are set by the caller before ``UTILS_LUA`` runs.
UTILS_PRELUDE = r"""
LOGS = {}
NULL = setmetatable({}, { __tostring = function() return "ngx.null" end })
SUBSYSTEM = SUBSYSTEM or "http"
VARIABLES = VARIABLES or { global = {} }

local function new_dict()
    local d = { data = {} }
    function d:get(k) return self.data[k] end
    function d:set(k, v) self.data[k] = v return true end
    function d:safe_set(k, v) self.data[k] = v return true end
    function d:delete(k) self.data[k] = nil end
    function d:get_keys() local ks = {} for k in pairs(self.data) do ks[#ks + 1] = k end table.sort(ks) return ks end
    return d
end
SHARED = SHARED or {}
for _, n in ipairs({ "datastore", "datastore_stream", "internalstore", "internalstore_stream" }) do SHARED[n] = SHARED[n] or new_dict() end

ngx = {
    ERR = "ERR", WARN = "WARN", INFO = "INFO", NOTICE = "NOTICE", DEBUG = "DEBUG", OK = 0,
    HTTP_FORBIDDEN = 403, null = NULL, var = {},
    config = { subsystem = SUBSYSTEM },
    shared = SHARED,
    get_phase = function() return "access" end,
    thread = { kill = function() end },
    re = { match = function() return nil end },
    ctx = {},
}

-- Datastore stand-in: dict-backed, ``get(key, true)`` on ``variables`` returns the scenario's variables.
local datastore = {}
datastore.__index = datastore
function datastore:new(dict) return setmetatable({ dict = dict or SHARED[SUBSYSTEM == "http" and "datastore" or "datastore_stream"] }, datastore) end
function datastore:get(key)
    if key == "variables" then return VARIABLES, "success" end
    if not self.dict then return nil, "no dict" end
    local v = self.dict:get(key)
    if v == nil then return nil, "not found" end
    return v, "success"
end
function datastore:set(key, value) self.dict:set(key, value) return true, "success" end
function datastore:set_with_retries(key, value) self.dict:set(key, value) return true, "success" end
function datastore:delete(key) self.dict:delete(key) return true, "success" end
function datastore:keys() return self.dict:get_keys() end
package.loaded["bunkerweb.datastore"] = datastore
package.loaded["bunkerweb.logger"] = { new = function() return { log = function(_, level, msg) LOGS[#LOGS + 1] = level .. ": " .. tostring(msg) end } end }
package.loaded["bunkerweb.mmdb"] = {}
package.loaded["bunkerweb.rediskeys"] = { cluster_mode = function() return false end, ban = function(k) return k end }
package.loaded["bunkerweb.duration"] = { parse_duration = function(v) return tonumber(v) end }
BUMPS = {}
package.loaded["bunkerweb.banlease"] = {
    RANK = { explicit_service = 4, explicit_global = 3, lease_service = 2, lease_global = 1 },
    meta = function() return nil end,
    lease_key = function(ip, service) return "lease_" .. (service or "") .. ip end,
    lease_epoch = function() return nil end,
    marker_epoch = function() return nil end,
    bump_marker_epoch_if_present = function(ip) BUMPS[#BUMPS + 1] = ip end,
}
package.loaded["cjson"] = { encode = function() return "{}" end, decode = function() return {} end }
package.loaded["resty.ipmatcher"] = {
    new = function() return { match = function() return false end } end,
    parse_ipv4 = function(ip) return type(ip) == "string" and ip:match("^%d+%.%d+%.%d+%.%d+$") ~= nil end,
    parse_ipv6 = function(ip) return type(ip) == "string" and ip:find(":", 1, true) ~= nil end,
}
package.loaded["resty.random"] = { bytes = function(n) return string.rep("\1", n) end }
package.loaded["resty.dns.resolver"] = {}
SESSION_STARTS = {}
package.loaded["resty.session"] = {
    start = function(config)
        SESSION_STARTS[#SESSION_STARTS + 1] = config or false
        return NEXT_SESSION()
    end,
}
local utils = dofile(UTILS_FILE)
"""


def utils_script(body: str, *, subsystem: str = "http") -> str:
    """A Lua script: the stubbed environment, the real ``utils`` as a local, then ``body``."""
    return f'UTILS_FILE = {lua_str(BW_MODULES / "utils.lua")}\nSUBSYSTEM = {json.dumps(subsystem)}\n' + UTILS_PRELUDE + body


def run_plugin(plugin: str, body: str, *, subsystem: str = "http") -> dict[str, str]:
    """``_lua_request_helpers.run`` pointed at this tree's ``common/core`` (the real one unless ``BW_UNIT_T2_SRC`` is set)."""
    from _lua_request_helpers import run  # type: ignore

    previous = os.environ.get("BW_UNIT_LUA_CORE_DIR")
    os.environ["BW_UNIT_LUA_CORE_DIR"] = str(CORE)
    try:
        return run(plugin, body, subsystem=subsystem)
    finally:
        if previous is None:
            os.environ.pop("BW_UNIT_LUA_CORE_DIR", None)
        else:
            os.environ["BW_UNIT_LUA_CORE_DIR"] = previous


# A generic first-party plugin environment: the base ``plugin`` class, ``utils`` and OpenResty stubbed, driven by globals
# the scenario sets. ``PLUGIN`` is the module under test (``dofile(MODULE)``).
PLUGIN_PRELUDE = r"""
unpack = unpack or table.unpack
NULL = setmetatable({}, { __tostring = function() return "ngx.null" end })
LOGS, METRICS, RPUSHES, DICT = {}, {}, {}, { incr = {}, decr = {} }
STORE = STORE or {}
VARIABLES = VARIABLES or {}
UTILS = UTILS or {}
BANS, WL_CALLS, BANNED_CALLS = {}, {}, {}
ngx = {
    ERR = "ERR", WARN = "WARN", INFO = "INFO", NOTICE = "NOTICE", OK = 0, HTTP_OK = 200,
    HTTP_MOVED_PERMANENTLY = 301, HTTP_NOT_ALLOWED = 405, HTTP_BAD_REQUEST = 400, HTTP_FORBIDDEN = 403, HTTP_NO_CONTENT = 204,
    null = NULL, var = {}, header = {}, status = STATUS or 403,
    config = { subsystem = SUBSYSTEM or "http" },
    get_phase = function() return PHASE or "log" end,
    worker = { id = function() return 0 end },
    thread = { spawn = function() end, wait = function() end, kill = function() end },
    req = { get_headers = function() return HEADERS or {} end },
}
package.loaded["middleclass"] = function(name, parent)
    local klass = { name = name }
    klass.__index = klass
    setmetatable(klass, { __index = parent, __call = function(cls, ...) return cls:new(...) end })
    klass.new = function(cls, ...)
        local obj = setmetatable({}, cls)
        obj:initialize(...)
        return obj
    end
    return klass
end
package.loaded["cjson"] = json
package.loaded["bunkerweb.rediskeys"] = { cluster_mode = function() return false end, escape = function(k) return k end }
package.loaded["bunkerweb.plugin"] = {
    initialize = function(self, name, ctx)
        self.ctx = ctx
        self.variables = VARIABLES
        self.use_redis = false
        self.logger = { log = function(_, level, msg) LOGS[#LOGS + 1] = level .. ": " .. tostring(msg) end }
        self.internalstore = {
            get = function(_, key) local v = STORE[key] if v == nil then return nil, "not found" end return v, "success" end,
            set = function(_, key, value) STORE[key] = value return true end,
        }
        self.datastore = {
            dict = { rpush = function(_, key, value) RPUSHES[#RPUSHES + 1] = { key = key, value = value } return 1 end },
            get = function(_, key) local v = DS and DS[key] if v == nil then return nil, "not found" end return v, "success" end,
            set_with_retries = function(_, key, value) DS = DS or {} DS[key] = value return true end,
            llen = function(_, key) return #(DICT[key == "plugin_badbehavior_incr" and "incr" or "decr"]) end,
            lpop = function(_, key) return table.remove(DICT[key == "plugin_badbehavior_incr" and "incr" or "decr"], 1) end,
        }
    end,
    ret = function(_, ok, msg, status, redirect, data) return { ret = ok, msg = msg, status = status, redirect = redirect, data = data } end,
    set_metric = function(_, kind, key, value) METRICS[#METRICS + 1] = { kind = kind, key = key, value = value } end,
    get_metric = function() return nil end,
    is_needed = function() return true end,
    flush_log_recaps = function() end,
    log_throttled = function(_, level, _, msg) LOGS[#LOGS + 1] = level .. ": " .. tostring(msg) end,
}
local utils = {
    is_whitelisted = function(ctx) return WHITELISTED == true end,
    is_ip_whitelisted = function(ip, server) WL_CALLS[#WL_CALLS + 1] = ip if IP_WL_ERR then return nil, IP_WL_ERR end return IP_WL == true, "ip" end,
    is_banned = function(ip, server) BANNED_CALLS[#BANNED_CALLS + 1] = ip return BANNED == true end,
    get_country = function() return "FR" end,
    get_security_mode = function() return "block" end,
    parse_duration = function(v) return tonumber(v) end,
    add_ban = function(ip, reason, ttl, service) BANS[#BANS + 1] = { ip = ip, reason = reason, ttl = ttl, service = service } return true, "ok" end,
    remove_ban = function() return true end,
    get_deny_status = function() return 403 end,
    regex_match = function(subject, pattern) return subject ~= nil and subject:find(pattern) and { subject } or nil end,
    get_variable = function(name) return VARIABLES[name] end,
    has_variable = function() return true end,
    deduplicate_list = function(list) local seen, out = {}, {} for _, v in ipairs(list) do if not seen[v] then seen[v] = true out[#out + 1] = v end end return out end,
    pick_header_rules = function() return {} end,
    get_multiple_variables = function() return MULTI_VARS or {}, "success" end,
}
for k, v in pairs(UTILS) do utils[k] = v end
package.loaded["bunkerweb.utils"] = utils
-- Libraries only some plugins load (antibot): driven by HTTP_BODY / URI_ARGS / POST_ARGS.
ngx.now = function() return 1000 end
ngx.escape_uri = function(v) return (tostring(v):gsub("[^%w%-%._~]", function(c) return string.format("%%%02X", c:byte()) end)) end
ngx.req.read_body = function() end
ngx.req.get_uri_args = function() return URI_ARGS or {} end
ngx.req.get_post_args = function() return POST_ARGS or {} end
HTTP_CALLS = {}
package.loaded["resty.env"] = package.loaded["resty.env"] or { get = function() return nil end }
package.loaded["resty.dns.resolver"] = package.loaded["resty.dns.resolver"] or {}
package.loaded["resty.template"] = { render = function() end }
package.loaded["base64"] = { encode = function(v) return v end }
package.loaded["antibot.captcha"] = { new = function() return {} end }
package.loaded["resty.sha256"] = { new = function() return { update = function() end, final = function() return "" end } end }
package.loaded["resty.string"] = { to_hex = function(v) return v end }
package.loaded["resty.http"] = {
    new = function()
        return {
            set_timeouts = function() end,
            close = function() end,
            request_uri = function(_, url, opts) HTTP_CALLS[#HTTP_CALLS + 1] = { url = url, body = opts.body } return { body = HTTP_BODY or "{}" } end,
        }
    end,
}
package.loaded["resty.ipmatcher"] = package.loaded["resty.ipmatcher"] or { new = function() return { match = function() return false end } end }
PLUGIN = dofile(MODULE)
function metric_keys()
    local keys = {}
    for _, m in ipairs(METRICS) do keys[#keys + 1] = m.kind .. ":" .. m.key end
    return keys
end
"""


def plugin_script(plugin: str, body: str, *, header: str = "") -> str:
    """Base Lua (JSON/``emit``), scenario ``header`` globals, the plugin environment, then ``body``."""
    from _lua_state_helpers import BASE_LUA  # type: ignore

    return BASE_LUA + f"\nMODULE = {lua_str(CORE / plugin / (plugin + '.lua'))}\n" + header + PLUGIN_PRELUDE + body


def run_plugin_script(plugin: str, body: str, *, header: str = ""):
    from _lua_state_helpers import last_json, run_lua  # type: ignore

    return last_json(run_lua(plugin_script(plugin, body, header=header)))
