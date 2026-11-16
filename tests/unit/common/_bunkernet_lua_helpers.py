"""BunkerNet real-Lua harness; adapted from dev list-plugin harness, unused boundaries removed."""

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "src" / "common" / "core"

LUA = shutil.which("lua") or shutil.which("lua5.4") or shutil.which("luajit")


def run_lua(script: str, *, timeout: int = 60) -> str:
    assert LUA is not None
    result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True, check=False, timeout=timeout)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def last_json(output: str):
    """The value of the last line the script ``emit``-ted."""
    return json.loads(output.strip().splitlines()[-1])


BASE_LUA = r"""
local json = {}
json.array_mt = {}
json.null = setmetatable({}, { __tostring = function() return "null" end })
local function encode(v)
    local t = type(v)
    if v == nil or v == json.null then
        return "null"
    elseif t == "table" then
        if getmetatable(v) == json.array_mt or (#v > 0 and next(v, #v) == nil) then
            local parts = {}
            for _, item in ipairs(v) do parts[#parts + 1] = encode(item) end
            return "[" .. table.concat(parts, ",") .. "]"
        end
        local keys = {}
        for k in pairs(v) do keys[#keys + 1] = tostring(k) end
        table.sort(keys)
        local parts = {}
        for _, k in ipairs(keys) do
            local value = v[k]
            if value == nil then value = v[tonumber(k)] end
            parts[#parts + 1] = encode(k) .. ":" .. encode(value)
        end
        return "{" .. table.concat(parts, ",") .. "}"
    elseif t == "string" then
        return '"' .. v:gsub('[%c"\\]', function(c) return string.format("\\u%04x", c:byte()) end) .. '"'
    elseif t == "number" then
        if v ~= v or v == math.huge or v == -math.huge then error("cannot encode number") end
        if math.type(v) == "integer" or v == math.floor(v) then return string.format("%d", v) end
        return string.format("%.14g", v)
    end
    return tostring(v)
end
local function decode(s)
    local pos = 1
    local value
    local function skip() pos = s:find("%S", pos) or #s + 1 end
    local function parse_string()
        pos = pos + 1
        local out = {}
        while true do
            local c = s:sub(pos, pos)
            if c == "" then error("unterminated string") end
            if c == '"' then pos = pos + 1 return table.concat(out) end
            if c == "\\" then
                local n = s:sub(pos + 1, pos + 1)
                if n == "u" then
                    out[#out + 1] = string.char(tonumber(s:sub(pos + 2, pos + 5), 16))
                    pos = pos + 6
                else
                    out[#out + 1] = ({ n = "\n", t = "\t", r = "\r" })[n] or n
                    pos = pos + 2
                end
            else
                out[#out + 1] = c
                pos = pos + 1
            end
        end
    end
    function value()
        skip()
        local c = s:sub(pos, pos)
        if c == "{" then
            pos = pos + 1
            local obj = {}
            skip()
            if s:sub(pos, pos) == "}" then pos = pos + 1 return obj end
            while true do
                skip()
                local k = parse_string()
                skip()
                if s:sub(pos, pos) ~= ":" then error("invalid json at " .. pos) end
                pos = pos + 1
                obj[k] = value()
                skip()
                local d = s:sub(pos, pos)
                pos = pos + 1
                if d == "}" then return obj end
                if d ~= "," then error("invalid json at " .. pos) end
            end
        elseif c == "[" then
            pos = pos + 1
            local arr = setmetatable({}, json.array_mt)
            skip()
            if s:sub(pos, pos) == "]" then pos = pos + 1 return arr end
            while true do
                arr[#arr + 1] = value()
                skip()
                local d = s:sub(pos, pos)
                pos = pos + 1
                if d == "]" then return arr end
                if d ~= "," then error("invalid json at " .. pos) end
            end
        elseif c == '"' then
            return parse_string()
        end
        local lit = s:match("^[%w%.%-%+]+", pos)
        if not lit then error("invalid json at " .. pos) end
        pos = pos + #lit
        if lit == "true" then return true end
        if lit == "false" then return false end
        if lit == "null" then return json.null end
        return tonumber(lit) or error("invalid literal " .. lit)
    end
    local result = value()
    skip()
    if pos <= #s then error("trailing data at " .. pos) end
    return result
end
json.encode, json.decode = encode, decode
function emit(v) print(encode(v)) end

"""

PLUGIN_LUA = r"""
unpack = unpack or table.unpack   -- LuaJIT has a global ``unpack``; dnsbl.lua relies on it

PHASE = "access"
DENY_STATUS = 403
HAS_VARIABLE = true
LOGS = {}
METRICS = {}
CACHE = {}
STORE = {}
STORE_SET_LOG = {}
HEADER_RULES, IGNORE_HEADER_RULES, HEADERS = {}, {}, {}
VARIABLES, LISTS = {}, {}
SERVER_NAME = "www.example.com"
FS_ROOT = BW_FS

ngx = {
    ERR = "ERR", INFO = "INFO", WARN = "WARN", NOTICE = "NOTICE", OK = "OK",
    HTTP_OK = 200, HTTP_INTERNAL_SERVER_ERROR = 500,
    var = {},
    get_phase = function() return PHASE end,
    thread = {
        spawn = function(fn, ...) return { results = table.pack(fn(...)) } end,
        wait = function(...) return WAIT(...) end,
    },
}

package.loaded["middleclass"] = function(name, parent)
    local klass = { name = name }
    klass.__index = klass
    setmetatable(klass, {
        __index = parent,
        __call = function(cls, ...) return cls:new(...) end,
    })
    function klass.new(cls, ...)
        local obj = setmetatable({}, cls)
        cls.initialize(obj, ...)
        return obj
    end
    return klass
end

package.loaded["bunkerweb.plugin"] = {
    initialize = function(self, name, ctx)
        self.name = name
        self.ctx = ctx
        self.variables = VARIABLES
        self.is_loading = IS_LOADING or false
        self.is_request = IS_REQUEST ~= false
        self.logger = { log = function(_, level, msg) LOGS[#LOGS + 1] = { level, msg } end }
        self.cachestore_local = {
            get = function(_, key) if CACHE_ERROR then return false, CACHE_ERROR end return true, CACHE[key] end,
            set = function(_, key, value, ttl)
                if CACHE_SET_ERROR then return false, CACHE_SET_ERROR end
                CACHE[key] = value
                CACHE_TTL = ttl
                return true
            end,
        }
        self.internalstore = {
            get = function(_, key) if STORE[key] == nil then return nil, "no such key " .. key end return STORE[key], "ok" end,
            set = function(_, key, value)
                if STORE_SET_ERROR then return false, STORE_SET_ERROR end
                STORE[key] = value
                STORE_SET_LOG[#STORE_SET_LOG + 1] = key
                return true
            end,
        }
        self.clusterstore = CLUSTERSTORE
        self.set_metric = function(_, kind, key, value) METRICS[key] = (METRICS[key] or 0) + value end
    end,
    ret = function(_, ok, msg, status, redirect, data)
        return { ret = ok, msg = msg, status = status, redirect = redirect, data = data }
    end,
}

package.loaded["bunkerweb.utils"] = {
    has_variable = function()
        if HAS_VARIABLE == nil then return nil, "lookup failed" end
        return HAS_VARIABLE
    end,
    get_deny_status = function() return DENY_STATUS end,
}
function new_plugin(plugin, ctx_overrides)
    local ctx = {
        bw = {
            server_name = SERVER_NAME or "www.example.com",
            remote_addr = "1.2.3.4",
            uri = "/",
            http_user_agent = nil,
            ip_is_global = false,
            http_headers = HEADERS,
        },
    }
    for k, v in pairs(ctx_overrides or {}) do ctx.bw[k] = v end
    return plugin:new(ctx)
end

"""


def to_lua(value) -> str:
    """A Python value as a Lua literal (dict -> table, list -> sequence)."""
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, (list, tuple)):
        return "{" + ", ".join(to_lua(v) for v in value) + "}"
    return "{" + ", ".join(f"[{to_lua(k)}] = {to_lua(v)}" for k, v in value.items()) + "}"
