"""Shared Lua harness for the behaviour tests of the request-path core plugins.

Runs the **real** ``src/common/core/<plugin>/<plugin>.lua`` under plain ``lua`` with OpenResty
stubbed. A test body is Lua appended to :data:`HARNESS`; it reports observable results with
``emit(key, value)`` and :func:`run` hands them back as a ``dict[str, str]``.

``BW_UNIT_LUA_CORE_DIR`` points the harness at another tree with the same
``<plugin>/<plugin>.lua`` layout. It exists for the mutation checks (a flipped copy of a module
must make a test fail); it defaults to the real ``src/common/core``.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "src" / "common" / "core"

LUA = shutil.which("lua") or shutil.which("lua5.4") or shutil.which("luajit")
requires_lua = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

HARNESS = r"""
-- ---------------------------------------------------------------- scenario state (tests override)
PHASE = "access"
NOW = 1000000
VARIABLES = {}      -- self.variables of the plugin
STORE = {}          -- internalstore
DS = {}             -- datastore (limit counters)
DS_ERR = nil
SET_FAIL = nil
METRICS, LOGS, SET_CALLS, RENDERED = {}, {}, {}, {}
HEADERS = {}        -- request headers
MULTI_VARS, MULTI_ERR = {}, nil
GETVAR = { MAX_HEADERS = "100" }
WHITELISTED, SECURITY_MODE, DENY_STATUS = false, "block", 403
SNI, SNI_ERR = nil, "no SNI"
RE_ERR_PATTERN = "("

local real_time = os.time
os.time = function(t) if t then return NOW end return real_time() end

local function b64(data)
    local chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    return ((data:gsub(".", function(x)
        local r, byte = "", x:byte()
        for i = 8, 1, -1 do r = r .. (byte % 2 ^ i - byte % 2 ^ (i - 1) > 0 and "1" or "0") end
        return r
    end) .. "0000"):gsub("%d%d%d?%d?%d?%d?", function(x)
        if #x < 6 then return "" end
        local c = 0
        for i = 1, 6 do c = c + (x:sub(i, i) == "1" and 2 ^ (6 - i) or 0) end
        return chars:sub(c + 1, c + 1)
    end) .. ({ "", "==", "=" })[#data % 3 + 1])
end
local function unb64(data)
    local chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    data = data:gsub("[^" .. chars .. "=]", "")
    return (data:gsub(".", function(x)
        if x == "=" then return "" end
        local r, f = "", (chars:find(x, 1, true) - 1)
        for i = 6, 1, -1 do r = r .. (f % 2 ^ i - f % 2 ^ (i - 1) > 0 and "1" or "0") end
        return r
    end):gsub("%d%d%d?%d?%d?%d?%d?%d?", function(x)
        if #x ~= 8 then return "" end
        local c = 0
        for i = 1, 8 do c = c + (x:sub(i, i) == "1" and 2 ^ (8 - i) or 0) end
        return string.char(c)
    end))
end
function basic_auth(user, pass) return "Basic " .. b64(user .. ":" .. pass) end

function emit(key, value) print(key .. "\t" .. tostring(value)) end

-- ---------------------------------------------------------------- ngx
ngx = {
    ERR = "ERR", WARN = "WARN", INFO = "INFO", OK = 0,
    HTTP_UNAUTHORIZED = 401, HTTP_BAD_REQUEST = 400, HTTP_NOT_ALLOWED = 405,
    HTTP_TOO_MANY_REQUESTS = 429, HTTP_CLOSE = 444,
    var = {}, header = {},
    config = { subsystem = "__SUBSYSTEM__" },
    get_phase = function() return PHASE end,
    req = { get_headers = function() return HEADERS end },
    decode_base64 = unb64,
    encode_base64 = b64,
    re = { match = function(subject, pattern, options)
        if pattern == RE_ERR_PATTERN then return nil, "bad pattern" end
        if subject:find(pattern) then return { subject } end
        return nil
    end },
}

-- ---------------------------------------------------------------- libraries
package.loaded["middleclass"] = function(name, parent)
    local klass = { name = name }
    klass.__index = klass
    setmetatable(klass, { __index = parent })
    klass.new = function(cls, ...)
        local obj = setmetatable({}, cls)
        obj:initialize(...)
        return obj
    end
    return klass
end

package.loaded["bunkerweb.plugin"] = {
    initialize = function(self, name, ctx)
        self.ctx = ctx
        self.variables = VARIABLES
        self.is_loading = false
        self.is_request = true
        self.logger = { log = function(_, level, msg) LOGS[#LOGS + 1] = level .. ": " .. tostring(msg) end }
        self.internalstore = {
            get = function(_, key)
                local value = STORE[key]
                if value == nil then return nil, "not found" end
                return value, "success"
            end,
            set = function(_, key, value, ttl)
                if SET_FAIL then return nil, SET_FAIL end
                STORE[key] = value
                SET_CALLS[#SET_CALLS + 1] = { key = key, value = value, ttl = ttl }
                return true
            end,
        }
        self.datastore = {
            get = function(_, key)
                if DS_ERR then return nil, DS_ERR end
                local value = DS[key]
                if value == nil then return nil, "not found" end
                return value, "success"
            end,
            set_with_retries = function(_, key, value) DS[key] = value return true end,
        }
    end,
    ret = function(_, ok, msg, status, redirect, data)
        return { ret = ok, msg = msg, status = status, redirect = redirect, data = data }
    end,
    set_metric = function(_, kind, key, value) METRICS[#METRICS + 1] = { kind = kind, key = key, value = value } end,
    log_throttled = function(_, level, key, msg) LOGS[#LOGS + 1] = level .. ": " .. tostring(msg) end,
}

-- Faithful enough for the patterns the plugins in this lane feed it (PCRE in the real utils).
package.loaded["bunkerweb.utils"] = {
    has_variable = function() return true end,
    get_multiple_variables = function()
        if MULTI_ERR then return nil, MULTI_ERR end
        return MULTI_VARS, "success"
    end,
    get_variable = function(name)
        local value = GETVAR[name]
        if value == nil then return nil, "unset" end
        return value, "success"
    end,
    get_deny_status = function() return DENY_STATUS end,
    get_security_mode = function() return SECURITY_MODE end,
    is_whitelisted = function() return WHITELISTED end,
    regex_match = function(subject, pattern)
        if subject == nil then return nil end
        if pattern == "^[A-Z][A-Z_-]{2,}$" then
            return subject:match("^[A-Z][A-Z_%-][A-Z_%-]+$") and { subject } or nil
        end
        if pattern == "([\\w-]+): (.+)" then
            local name, value = subject:match("^([%w_%-]+): (.+)$")
            return name and { name, value } or nil
        end
        local word = pattern:match("^%(%^| %)(.-)%(%$| %)$")
        if word then
            return (" " .. subject .. " "):find(" " .. word .. " ", 1, true) and { subject } or nil
        end
        return subject:find(pattern) and { subject } or nil
    end,
}

package.loaded["bunkerweb.rediskeys"] = { cluster_mode = function() return false end, escape = function(k) return k end }

package.loaded["cjson"] = {
    encode = function(t)
        local parts = {}
        for _, v in ipairs(t) do parts[#parts + 1] = tostring(v) end
        return "[" .. table.concat(parts, ",") .. "]"
    end,
    decode = function(s)
        local t = {}
        for n in s:gmatch("%d+") do t[#t + 1] = tonumber(n) end
        return t
    end,
}

if load("return 1 | 2") then
    package.loaded["bit"] = { bor = load("return function(a, b) return a | b end")(), bxor = load("return function(a, b) return a ~ b end")() }
end
package.loaded["resty.openssl.kdf"] = {
    SCRYPT = "scrypt",
    derive = function(opts) return "D:" .. opts.pass .. ":" .. opts.salt end,
}
package.loaded["resty.random"] = { bytes = function(len) return string.rep("\1", len) end }
package.loaded["resty.template"] = { render = function(name, data) RENDERED = { name = name, data = data } end }
package.loaded["ngx.ssl.clienthello"] = { get_client_hello_server_name = function() return SNI, SNI_ERR end }

PLUGIN = dofile("__MODULE__")

-- Request context; `over` patches ctx.bw.
function ctx(over)
    local bw = { server_name = "www.example.com", remote_addr = "1.2.3.4", uri = "/", scheme = "http", request_method = "GET" }
    for k, v in pairs(over or {}) do bw[k] = v end
    return { bw = bw }
end
function metric_keys()
    local keys = {}
    for _, m in ipairs(METRICS) do keys[#keys + 1] = m.kind .. ":" .. m.key end
    return table.concat(keys, ",")
end
"""


def run(plugin: str, body: str, *, subsystem: str = "http") -> dict[str, str]:
    assert LUA is not None
    base = Path(os.environ.get("BW_UNIT_LUA_CORE_DIR") or CORE)
    script = HARNESS.replace("__MODULE__", str(base / plugin / f"{plugin}.lua")).replace("__SUBSYSTEM__", subsystem) + "\n" + body
    result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    out = {}
    for line in result.stdout.splitlines():
        key, _, value = line.partition("\t")
        out[key] = value
    return out
