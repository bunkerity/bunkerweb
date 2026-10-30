"""Shared harness for the Lua behaviour tests of the list plugins, redis and the CrowdSec state helpers.

Every test runs the **real** module under plain ``lua`` with OpenResty stubbed at its boundary
(``ngx``, ``resty.*``, ``bunkerweb.utils``). The stand-ins are deliberately small and driven by
globals the test sets, so an assertion is about what the module decided, not about the stub.

``module_path`` lets a mutation run point a test at a mutated **copy** of a module through an
environment variable (``BW_L2_<NAME>``), without ever touching ``src/``.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "src" / "common" / "core"

LUA = shutil.which("lua") or shutil.which("lua5.4") or shutil.which("luajit")


def module_path(env_name: str, default: Path) -> Path:
    """The module under test: the real file, or the mutated copy named by ``BW_L2_<env_name>``."""
    return Path(os.environ.get(f"BW_L2_{env_name}", str(default)))


def run_lua(script: str, *, timeout: int = 60) -> str:
    assert LUA is not None
    result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True, check=False, timeout=timeout)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def last_json(output: str):
    """The value of the last line the script ``emit``-ted."""
    return json.loads(output.strip().splitlines()[-1])


# Pure Lua 5.4: JSON codec (cjson stand-in), SHA-256 (resty.sha256 stand-in), ``emit``.
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

-- SHA-256, so the real cache_partition.hash can be compared with hashlib.
local function sha256(msg)
    local M = 0xffffffff
    local primes, n = {}, 2
    while #primes < 64 do
        local is_prime = true
        for _, p in ipairs(primes) do
            if p * p > n then break end
            if n % p == 0 then is_prime = false break end
        end
        if is_prime then primes[#primes + 1] = n end
        n = n + 1
    end
    local function frac32(x) return math.floor((x - math.floor(x)) * 2 ^ 32) end
    local k, h = {}, {}
    for i = 1, 64 do k[i] = frac32(primes[i] ^ (1 / 3)) end
    for i = 1, 8 do h[i] = frac32(primes[i] ^ 0.5) end
    local function rrot(x, c) return ((x >> c) | (x << (32 - c))) & M end
    local len = #msg
    msg = msg .. "\128" .. string.rep("\0", (55 - len) % 64) .. string.pack(">I8", len * 8)
    for chunk = 1, #msg, 64 do
        local w = {}
        for i = 0, 15 do w[i] = string.unpack(">I4", msg, chunk + i * 4) end
        for i = 16, 63 do
            local s0 = rrot(w[i - 15], 7) ~ rrot(w[i - 15], 18) ~ (w[i - 15] >> 3)
            local s1 = rrot(w[i - 2], 17) ~ rrot(w[i - 2], 19) ~ (w[i - 2] >> 10)
            w[i] = (w[i - 16] + s0 + w[i - 7] + s1) & M
        end
        local a, b, c, d, e, f, g, hh = table.unpack(h)
        for i = 0, 63 do
            local S1 = rrot(e, 6) ~ rrot(e, 11) ~ rrot(e, 25)
            local ch = (e & f) ~ ((~e) & g)
            local t1 = (hh + S1 + ch + k[i + 1] + w[i]) & M
            local S0 = rrot(a, 2) ~ rrot(a, 13) ~ rrot(a, 22)
            local maj = (a & b) ~ (a & c) ~ (b & c)
            local t2 = (S0 + maj) & M
            hh, g, f, e, d, c, b, a = g, f, e, (d + t1) & M, c, b, a, (t1 + t2) & M
        end
        local v = { a, b, c, d, e, f, g, hh }
        for i = 1, 8 do h[i] = (h[i] + v[i]) & M end
    end
    return string.pack(">I4I4I4I4I4I4I4I4", table.unpack(h))
end
SHA256 = sha256
"""

# OpenResty / plugin boundary shared by the blacklist, greylist, dnsbl and redis tests.
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

-- Redirect the cache directory the plugins read at init() into the test's temp dir.
local real_open = io.open
io.open = function(path, mode)
    if FS_ROOT and path:sub(1, 21) == "/var/cache/bunkerweb/" then
        path = FS_ROOT .. "/" .. path:sub(22)
    end
    return real_open(path, mode)
end

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

-- Real IPv4/CIDR matching: the decision the plugins delegate to resty.ipmatcher.
local function ip_to_int(ip)
    local a, b, c, d = tostring(ip):match("^(%d+)%.(%d+)%.(%d+)%.(%d+)$")
    if not a then return nil end
    return ((tonumber(a) * 256 + tonumber(b)) * 256 + tonumber(c)) * 256 + tonumber(d)
end
package.loaded["resty.ipmatcher"] = {
    new = function(list)
        local nets = {}
        for _, entry in ipairs(list) do
            local base, bits = entry:match("^([^/]+)/(%d+)$")
            base, bits = base or entry, tonumber(bits) or 32
            local int = ip_to_int(base)
            if not int then return nil, "invalid address " .. entry end
            nets[#nets + 1] = { int, bits }
        end
        return {
            match = function(_, ip)
                local int = ip_to_int(ip)
                if not int then return nil, "invalid client address" end
                for _, net in ipairs(nets) do
                    local shift = 32 - net[2]
                    if (int >> shift) == (net[1] >> shift) then return true end
                end
                return false
            end,
        }
    end,
}

-- Light threads run to completion at spawn; ``wait`` hands back the one with the lowest server name.
WAIT_ERROR = nil
function WAIT(...)
    if WAIT_ERROR then return false, WAIT_ERROR end
    local threads = { ... }
    table.sort(threads, function(a, b) return a.results[2] < b.results[2] end)
    local first = threads[1]
    return true, table.unpack(first.results, 1, first.results.n)
end

DNS = {}          -- query name -> list of A records, or nil to fail
DNS_QUERIES = {}
package.loaded["resty.dns.resolver"] = {
    arpa_str = function(addr)
        local a, b, c, d = addr:match("^(%d+)%.(%d+)%.(%d+)%.(%d+)$")
        return d .. "." .. c .. "." .. b .. "." .. a .. ".in-addr.arpa"
    end,
}

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
    get_variable = function()
        if SERVER_NAME == nil then return nil, "no such variable" end
        return SERVER_NAME, "success"
    end,
    get_header_rules = function(name)
        if HEADER_RULES_ERROR then return nil, HEADER_RULES_ERROR end
        return { name = name }
    end,
    pick_header_rules = function(rules) return rules or {} end,
    match_header_rules = function() return nil end,
    deduplicate_list = function(list)
        local seen, out = {}, {}
        for _, item in ipairs(list) do
            if not seen[item] then seen[item] = true out[#out + 1] = item end
        end
        return out
    end,
    -- PCRE is not available in plain Lua: Lua patterns agree on the simple expressions the tests use.
    regex_match = function(subject, regex) return subject:find(regex) and true or nil end,
    get_rdns = function()
        if RDNS == nil then return nil, "rdns lookup failed" end
        RDNS_CALLS = (RDNS_CALLS or 0) + 1
        return RDNS
    end,
    -- Stand-in for forward confirmation: the suffix is honoured only when FCRDNS says the name resolves back.
    rdns_forward_confirmed = function(rdns_list, suffixes)
        if not FCRDNS then return nil end
        for _, rdns in ipairs(rdns_list) do
            for _, suffix in ipairs(suffixes) do
                if rdns:sub(-#suffix) == suffix then return suffix end
            end
        end
        return nil
    end,
    get_asn = function()
        ASN_CALLS = (ASN_CALLS or 0) + 1
        if ASN == nil then return nil, "asn lookup failed" end
        return ASN
    end,
    get_ips = function(name)
        DNS_QUERIES[#DNS_QUERIES + 1] = name
        local answer = DNS[name]
        if answer == nil then return nil, "dns failure for " .. name end
        return answer
    end,
    kill_all_threads = function(threads) KILLED = threads end,
}

-- A fresh plugin instance built through the real ``initialize``; ``ctx`` fields can be overridden.
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

function summary(result)
    return { ret = result.ret, msg = result.msg, status = result.status, data = result.data }
end
"""


def build_script(module: Path, body: str, *, fs_root: Path | None = None) -> str:
    """``BASE_LUA`` + ``PLUGIN_LUA`` + the module as ``PLUGIN`` + the test body, in one chunk."""
    header = f"BW_FS = {json.dumps(str(fs_root)) if fs_root else 'nil'}\n"
    plugin = BASE_LUA + header + PLUGIN_LUA
    return plugin + f"\nPLUGIN = dofile({json.dumps(str(module))})\n" + body


def run_plugin(module: Path, body: str, *, fs_root: Path | None = None):
    """Run ``body`` against the plugin module and return the value it ``emit``-ted."""
    return last_json(run_lua(build_script(module, body, fs_root=fs_root)))


def sha256_hex(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode()).hexdigest()


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
