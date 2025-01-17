-----------------------------------------------------------------------------
-- A hacked dispatcher module
-- LuaSocket sample files
-- Author: Diego Nehab
-----------------------------------------------------------------------------
local base = _G
local table = require("table")
local string = require("string")
local socket = require("socket")
local coroutine = require("coroutine")
module("dispatch")

-- if too much time goes by without any activity in one of our sockets, we
-- just kill it
TIMEOUT = 60

-----------------------------------------------------------------------------
-- We implement 3 types of dispatchers:
--     sequential
--     coroutine
--     threaded
-- The user can choose whatever one is needed
-----------------------------------------------------------------------------
local handlert = {}

-- default handler is coroutine
function newhandler(mode)
    mode = mode or "coroutine"
    return handlert[mode]()
end

local function seqstart(self, func)
    return func()
end

-- sequential handler simply calls the functions and doesn't wrap I/O
function handlert.sequential()
    return {
        tcp = socket.tcp,
        start = seqstart
    }
end

-----------------------------------------------------------------------------
-- Mega hack. Don't try to do this at home.
-----------------------------------------------------------------------------
-- we can't yield across calls to protect on Lua 5.1, so we rewrite it with
-- coroutines
-- make sure you don't require any module that uses socket.protect before
-- loading our hack
if string.sub(base._VERSION, -3) == "5.1" then
  local function _protect(co, status, ...)
    if not status then
      local msg = ...
      if base.type(msg) == 'table' then
        return nil, msg[1]
      else
        base.error(msg, 0)
      end
    end
    if coroutine.status(co) == "suspended" then
      return _protect(co, coroutine.resume(co, coroutine.yield(...)))
    else
      return ...
    end
  end

  function socket.protect(f)
    return function(...)
      local co = coroutine.create(f)
      return _protect(co, coroutine.resume(co, ...))
    end
  end
end

-----------------------------------------------------------------------------
-- Simple set data structure. O(1) everything.
-----------------------------------------------------------------------------
local function newset()
    local reverse = {}
    local set = {}
    return base.setmetatable(set, {__index = {
        insert = function(set, value)
            if not reverse[value] then
                table.insert(set, value)
                reverse[value] = #set
            end
        end,
        remove = function(set, value)
            local index = reverse[value]
            if index then
                reverse[value] = nil
                local top = table.remove(set)
                if top ~= value then
                    reverse[top] = index
                    set[index] = top
                end
            end
        end
    }})
end

-----------------------------------------------------------------------------
-- socket.tcp() wrapper for the coroutine dispatcher
-----------------------------------------------------------------------------
local function cowrap(dispatcher, tcp, error)
    if not tcp then return nil, error end
    -- put it in non-blocking mode right away
    tcp:settimeout(0)
    -- metatable for wrap produces new methods on demand for those that we
    -- don't override explicitly.
    local metat = { __index = function(table, key)
        table[key] = function(...)
            return tcp[key](tcp,select(2,...))
        end
        return table[key]
    end}
    -- does our user want to do his own non-blocking I/O?
    local zero = false
    -- create a wrap object that will behave just like a real socket object
    local wrap = {  }
    -- we ignore settimeout to preserve our 0 timeout, but record whether
    -- the user wants to do his own non-blocking I/O
    function wrap:settimeout(value, mode)
        if value == 0 then zero = true
        else zero = false end
        return 1
    end
    -- send in non-blocking mode and yield on timeout
    function wrap:send(data, first, last)
        first = (first or 1) - 1
        local result, error
        while true do
            -- return control to dispatcher and tell it we want to send
            -- if upon return the dispatcher tells us we timed out,
            -- return an error to whoever called us
            if coroutine.yield(dispatcher.sending, tcp) == "timeout" then
                return nil, "timeout"
            end
            -- try sending
            result, error, first = tcp:send(data, first+1, last)
            -- if we are done, or there was an unexpected error,
            -- break away from loop
            if error ~= "timeout" then return result, error, first end
        end
    end
    -- receive in non-blocking mode and yield on timeout
    -- or simply return partial read, if user requested timeout = 0
    function wrap:receive(pattern, partial)
        local error = "timeout"
        local value
        while true do
            -- return control to dispatcher and tell it we want to receive
            -- if upon return the dispatcher tells us we timed out,
            -- return an error to whoever called us
            if coroutine.yield(dispatcher.receiving, tcp) == "timeout" then
                return nil, "timeout"
            end
            -- try receiving
            value, error, partial = tcp:receive(pattern, partial)
            -- if we are done, or there was an unexpected error,
            -- break away from loop. also, if the user requested
            -- zero timeout, return all we got
            if (error ~= "timeout") or zero then
                return value, error, partial
            end
        end
    end
    -- connect in non-blocking mode and yield on timeout
    function wrap:connect(host, port)
        local result, error = tcp:connect(host, port)
        if error == "timeout" then
            -- return control to dispatcher. we will be writable when
            -- connection succeeds.
            -- if upon return the dispatcher tells us we have a
            -- timeout, just abort
            if coroutine.yield(dispatcher.sending, tcp) == "timeout" then
                return nil, "timeout"
            end
            -- when we come back, check if connection was successful
            result, error = tcp:connect(host, port)
            if result or error == "already connected" then return 1
            else return nil, "non-blocking connect failed" end
        else return result, error end
    end
    -- accept in non-blocking mode and yield on timeout
    function wrap:accept()
        while 1 do
            -- return control to dispatcher. we will be readable when a
            -- connection arrives.
            -- if upon return the dispatcher tells us we have a
            -- timeout, just abort
            if coroutine.yield(dispatcher.receiving, tcp) == "timeout" then
                return nil, "timeout"
            end
            local client, error = tcp:accept()
            if error ~= "timeout" then
                return cowrap(dispatcher, client, error)
            end
        end
    end
    -- remove cortn from context
    function wrap:close()
        dispatcher.stamp[tcp] = nil
        dispatcher.sending.set:remove(tcp)
        dispatcher.sending.cortn[tcp] = nil
        dispatcher.receiving.set:remove(tcp)
        dispatcher.receiving.cortn[tcp] = nil
        return tcp:close()
    end
    return base.setmetatable(wrap, metat)
end


-----------------------------------------------------------------------------
-- Our coroutine dispatcher
-----------------------------------------------------------------------------
local cometat = { __index = {} }

function schedule(cortn, status, operation, tcp)
    if status then
        if cortn and operation then
            operation.set:insert(tcp)
            operation.cortn[tcp] = cortn
            operation.stamp[tcp] = socket.gettime()
        end
    else base.error(operation) end
end

function kick(operation, tcp)
    operation.cortn[tcp] = nil
    operation.set:remove(tcp)
end

function wakeup(operation, tcp)
    local cortn = operation.cortn[tcp]
    -- if cortn is still valid, wake it up
    if cortn then
        kick(operation, tcp)
        return cortn, coroutine.resume(cortn)
    -- othrewise, just get scheduler not to do anything
    else
        return nil, true
    end
end

function abort(operation, tcp)
    local cortn = operation.cortn[tcp]
    if cortn then
        kick(operation, tcp)
        coroutine.resume(cortn, "timeout")
    end
end

-- step through all active cortns
function cometat.__index:step()
    -- check which sockets are interesting and act on them
    local readable, writable = socket.select(self.receiving.set,
        self.sending.set, 1)
    -- for all readable connections, resume their cortns and reschedule
    -- when they yield back to us
    for _, tcp in base.ipairs(readable) do
        schedule(wakeup(self.receiving, tcp))
    end
    -- for all writable connections, do the same
    for _, tcp in base.ipairs(writable) do
        schedule(wakeup(self.sending, tcp))
    end
    -- politely ask replacement I/O functions in idle cortns to
    -- return reporting a timeout
    local now = socket.gettime()
    for tcp, stamp in base.pairs(self.stamp) do
        if tcp.class == "tcp{client}" and now - stamp > TIMEOUT then
            abort(self.sending, tcp)
            abort(self.receiving, tcp)
        end
    end
end

function cometat.__index:start(func)
    local cortn = coroutine.create(func)
    schedule(cortn, coroutine.resume(cortn))
end

function handlert.coroutine()
    local stamp = {}
    local dispatcher = {
        stamp = stamp,
        sending  = {
            name = "sending",
            set = newset(),
            cortn = {},
            stamp = stamp
        },
        receiving = {
            name = "receiving",
            set = newset(),
            cortn = {},
            stamp = stamp
        },
    }
    function dispatcher.tcp()
        return cowrap(dispatcher, socket.tcp())
    end
    return base.setmetatable(dispatcher, cometat)
end

