-----------------------------------------------------------------------------
-- TFTP support for the Lua language
-- LuaSocket toolkit.
-- Author: Diego Nehab
-----------------------------------------------------------------------------

-----------------------------------------------------------------------------
-- Load required files
-----------------------------------------------------------------------------
local base = _G
local table = require("table")
local math = require("math")
local string = require("string")
local socket = require("socket")
local ltn12 = require("ltn12")
local url = require("socket.url")
module("socket.tftp")

-----------------------------------------------------------------------------
-- Program constants
-----------------------------------------------------------------------------
local char = string.char
local byte = string.byte

PORT = 69
local OP_RRQ = 1
local OP_WRQ = 2
local OP_DATA = 3
local OP_ACK = 4
local OP_ERROR = 5
local OP_INV = {"RRQ", "WRQ", "DATA", "ACK", "ERROR"}

-----------------------------------------------------------------------------
-- Packet creation functions
-----------------------------------------------------------------------------
local function RRQ(source, mode)
    return char(0, OP_RRQ) .. source .. char(0) .. mode .. char(0)
end

local function WRQ(source, mode)
    return char(0, OP_RRQ) .. source .. char(0) .. mode .. char(0)
end

local function ACK(block)
    local low, high
    low = math.mod(block, 256)
    high = (block - low)/256
    return char(0, OP_ACK, high, low)
end

local function get_OP(dgram)
    local op = byte(dgram, 1)*256 + byte(dgram, 2)
    return op
end

-----------------------------------------------------------------------------
-- Packet analysis functions
-----------------------------------------------------------------------------
local function split_DATA(dgram)
    local block = byte(dgram, 3)*256 + byte(dgram, 4)
    local data = string.sub(dgram, 5)
    return block, data
end

local function get_ERROR(dgram)
    local code = byte(dgram, 3)*256 + byte(dgram, 4)
    local msg
    _,_, msg = string.find(dgram, "(.*)\000", 5)
    return string.format("error code %d: %s", code, msg)
end

-----------------------------------------------------------------------------
-- The real work
-----------------------------------------------------------------------------
local function tget(gett)
    local retries, dgram, sent, datahost, dataport, code
    local last = 0
    socket.try(gett.host, "missing host")
    local con = socket.try(socket.udp())
    local try = socket.newtry(function() con:close() end)
    -- convert from name to ip if needed
    gett.host = try(socket.dns.toip(gett.host))
    con:settimeout(1)
    -- first packet gives data host/port to be used for data transfers
    local path = string.gsub(gett.path or "", "^/", "")
    path = url.unescape(path)
    retries = 0
    repeat
        sent = try(con:sendto(RRQ(path, "octet"), gett.host, gett.port))
        dgram, datahost, dataport = con:receivefrom()
        retries = retries + 1
    until dgram or datahost ~= "timeout" or retries > 5
    try(dgram, datahost)
    -- associate socket with data host/port
    try(con:setpeername(datahost, dataport))
    -- default sink
    local sink = gett.sink or ltn12.sink.null()
    -- process all data packets
    while 1 do
        -- decode packet
        code = get_OP(dgram)
        try(code ~= OP_ERROR, get_ERROR(dgram))
        try(code == OP_DATA, "unhandled opcode " .. code)
        -- get data packet parts
        local block, data = split_DATA(dgram)
        -- if not repeated, write
        if block == last+1 then
            try(sink(data))
            last = block
        end
        -- last packet brings less than 512 bytes of data
        if string.len(data) < 512 then
            try(con:send(ACK(block)))
            try(con:close())
            try(sink(nil))
            return 1
        end
        -- get the next packet
        retries = 0
        repeat
            sent = try(con:send(ACK(last)))
            dgram, err = con:receive()
            retries = retries + 1
        until dgram or err ~= "timeout" or retries > 5
        try(dgram, err)
    end
end

local default = {
    port = PORT,
    path ="/",
    scheme = "tftp"
}

local function parse(u)
    local t = socket.try(url.parse(u, default))
    socket.try(t.scheme == "tftp", "invalid scheme '" .. t.scheme .. "'")
    socket.try(t.host, "invalid host")
    return t
end

local function sget(u)
    local gett = parse(u)
    local t = {}
    gett.sink = ltn12.sink.table(t)
    tget(gett)
    return table.concat(t)
end

get = socket.protect(function(gett)
    if base.type(gett) == "string" then return sget(gett)
    else return tget(gett) end
end)

