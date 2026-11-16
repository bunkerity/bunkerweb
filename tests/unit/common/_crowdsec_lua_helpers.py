"""Plain Lua JSON/SHA-256 boundaries for CrowdSec checkpoint and bouncer tests."""

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "src" / "common" / "core"
LUA = shutil.which("lua") or shutil.which("lua5.4")


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
