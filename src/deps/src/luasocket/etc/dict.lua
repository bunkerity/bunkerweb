-----------------------------------------------------------------------------
-- Little program to download DICT word definitions
-- LuaSocket sample files
-- Author: Diego Nehab
-----------------------------------------------------------------------------

-----------------------------------------------------------------------------
-- Load required modules
-----------------------------------------------------------------------------
local base = _G
local string = require("string")
local table = require("table")
local socket = require("socket")
local url = require("socket.url")
local tp = require("socket.tp")
module("socket.dict")

-----------------------------------------------------------------------------
-- Globals
-----------------------------------------------------------------------------
HOST = "dict.org"
PORT = 2628
TIMEOUT = 10

-----------------------------------------------------------------------------
-- Low-level dict API
-----------------------------------------------------------------------------
local metat = { __index = {} }

function open(host, port)
    local tp = socket.try(tp.connect(host or HOST, port or PORT, TIMEOUT))
    return base.setmetatable({tp = tp}, metat)
end

function metat.__index:greet()
    return socket.try(self.tp:check(220))
end

function metat.__index:check(ok)
    local code, status = socket.try(self.tp:check(ok))
    return code,
        base.tonumber(socket.skip(2, string.find(status, "^%d%d%d (%d*)")))
end

function metat.__index:getdef()
    local line = socket.try(self.tp:receive())
    local def = {}
    while line ~= "." do
        table.insert(def, line)
        line = socket.try(self.tp:receive())
    end
    return table.concat(def, "\n")
end

function metat.__index:define(database, word)
    database = database or "!"
      socket.try(self.tp:command("DEFINE",  database .. " " .. word))
    local code, count = self:check(150)
    local defs = {}
    for i = 1, count do
          self:check(151)
        table.insert(defs, self:getdef())
    end
      self:check(250)
    return defs
end

function metat.__index:match(database, strat, word)
    database = database or "!"
    strat = strat or "."
      socket.try(self.tp:command("MATCH",  database .." ".. strat .." ".. word))
    self:check(152)
    local mat = {}
    local line = socket.try(self.tp:receive())
    while line ~= '.' do
        database, word = socket.skip(2, string.find(line, "(%S+) (.*)"))
        if not mat[database] then mat[database] = {} end
        table.insert(mat[database], word)
        line = socket.try(self.tp:receive())
    end
      self:check(250)
    return mat
end

function metat.__index:quit()
    self.tp:command("QUIT")
    return self:check(221)
end

function metat.__index:close()
    return self.tp:close()
end

-----------------------------------------------------------------------------
-- High-level dict API
-----------------------------------------------------------------------------
local default = {
    scheme = "dict",
    host = "dict.org"
}

local function there(f)
    if f == "" then return nil
    else return f end
end

local function parse(u)
    local t = socket.try(url.parse(u, default))
    socket.try(t.scheme == "dict", "invalid scheme '" .. t.scheme .. "'")
    socket.try(t.path, "invalid path in url")
    local cmd, arg = socket.skip(2, string.find(t.path, "^/(.)(.*)$"))
    socket.try(cmd == "d" or cmd == "m", "<command> should be 'm' or 'd'")
    socket.try(arg and arg ~= "", "need at least <word> in URL")
    t.command, t.argument = cmd, arg
    arg = string.gsub(arg, "^:([^:]+)", function(f) t.word = f end)
    socket.try(t.word, "need at least <word> in URL")
    arg = string.gsub(arg, "^:([^:]*)", function(f) t.database = there(f) end)
    if cmd == "m" then
        arg = string.gsub(arg, "^:([^:]*)", function(f) t.strat = there(f) end)
    end
    string.gsub(arg, ":([^:]*)$", function(f) t.n = base.tonumber(f) end)
    return t
end

local function tget(gett)
    local con = open(gett.host, gett.port)
    con:greet()
    if gett.command == "d" then
        local def = con:define(gett.database, gett.word)
        con:quit()
        con:close()
        if gett.n then return def[gett.n]
        else return def end
    elseif gett.command == "m" then
        local mat = con:match(gett.database, gett.strat, gett.word)
        con:quit()
        con:close()
        return mat
    else return nil, "invalid command" end
end

local function sget(u)
    local gett = parse(u)
    return tget(gett)
end

get = socket.protect(function(gett)
    if base.type(gett) == "string" then return sget(gett)
    else return tget(gett) end
end)

