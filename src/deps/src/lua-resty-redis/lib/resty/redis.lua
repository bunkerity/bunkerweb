-- Copyright (C) Yichun Zhang (agentzh)


local sub = string.sub
local byte = string.byte
local tab_insert = table.insert
local tab_remove = table.remove
local tcp = ngx.socket.tcp
local null = ngx.null
local ipairs = ipairs
local type = type
local pairs = pairs
local unpack = unpack
local setmetatable = setmetatable
local tonumber = tonumber
local tostring = tostring
local rawget = rawget
local select = select
local tb_clear = require "table.clear"
--local error = error


local ok, new_tab = pcall(require, "table.new")
if not ok or type(new_tab) ~= "function" then
    new_tab = function (narr, nrec) return {} end
end

local tab_pool_len = 0
local tab_pool = new_tab(16, 0)
local _M = new_tab(0, 55)

_M._VERSION = '0.30'


local common_cmds = {
    "get",      "set",          "mget",     "mset",
    "del",      "incr",         "decr",                 -- Strings
    "llen",     "lindex",       "lpop",     "lpush",
    "lrange",   "linsert",                              -- Lists
    "hexists",  "hget",         "hset",     "hmget",
    --[[ "hmset", ]]            "hdel",                 -- Hashes
    "smembers", "sismember",    "sadd",     "srem",
    "sdiff",    "sinter",       "sunion",               -- Sets
    "zrange",   "zrangebyscore", "zrank",   "zadd",
    "zrem",     "zincrby",                              -- Sorted Sets
    "auth",     "eval",         "expire",   "script",
    "sort"                                              -- Others
}


local sub_commands = {
    "subscribe", "psubscribe"
}


local unsub_commands = {
    "unsubscribe", "punsubscribe"
}


local mt = { __index = _M }


local function get_tab_from_pool()
    if tab_pool_len > 0 then
        tab_pool_len = tab_pool_len - 1
        return tab_pool[tab_pool_len + 1]
    end

    return new_tab(24, 0) -- one field takes 5 slots
end


local function put_tab_into_pool(tab)
    if tab_pool_len >= 32 then
        return
    end

    tb_clear(tab)
    tab_pool_len = tab_pool_len + 1
    tab_pool[tab_pool_len] = tab
end


function _M.new(self)
    local sock, err = tcp()
    if not sock then
        return nil, err
    end
    return setmetatable({ _sock = sock,
                          _subscribed = false,
                          _n_channel = {
                            unsubscribe = 0,
                            punsubscribe = 0,
                          },
                        }, mt)
end


function _M.register_module_prefix(mod)
    _M[mod] = function(self)
        self._module_prefix = mod
        return self
    end
end


function _M.set_timeout(self, timeout)
    local sock = rawget(self, "_sock")
    if not sock then
        error("not initialized", 2)
        return
    end

    sock:settimeout(timeout)
end


function _M.set_timeouts(self, connect_timeout, send_timeout, read_timeout)
    local sock = rawget(self, "_sock")
    if not sock then
        error("not initialized", 2)
        return
    end

    sock:settimeouts(connect_timeout, send_timeout, read_timeout)
end


function _M.connect(self, host, port_or_opts, opts)
    local sock = rawget(self, "_sock")
    if not sock then
        return nil, "not initialized"
    end

    local unix

    do
        local typ = type(host)
        if typ ~= "string" then
            error("bad argument #1 host: string expected, got " .. typ, 2)
        end

        if sub(host, 1, 5) == "unix:" then
            unix = true
        end

        if unix then
            typ = type(port_or_opts)
            if port_or_opts ~= nil and typ ~= "table" then
                error("bad argument #2 opts: nil or table expected, got " ..
                      typ, 2)
            end

        else
            typ = type(port_or_opts)
            if typ ~= "number" then
                port_or_opts = tonumber(port_or_opts)
                if port_or_opts == nil then
                    error("bad argument #2 port: number expected, got " ..
                          typ, 2)
                end
            end

            if opts ~= nil then
                typ = type(opts)
                if typ ~= "table" then
                    error("bad argument #3 opts: nil or table expected, got " ..
                          typ, 2)
                end
            end
        end

    end

    self._subscribed = false

    local ok, err

    if unix then
         -- second argument of sock:connect() cannot be nil
         if port_or_opts ~= nil then
             ok, err = sock:connect(host, port_or_opts)
             opts = port_or_opts
         else
             ok, err = sock:connect(host)
         end
    else
        ok, err = sock:connect(host, port_or_opts, opts)
    end

    if not ok then
        return ok, err
    end

    if opts and opts.ssl then
        ok, err = sock:sslhandshake(false, opts.server_name, opts.ssl_verify)
        if not ok then
            return ok, "failed to do ssl handshake: " .. err
        end
    end

    return ok, err
end


function _M.set_keepalive(self, ...)
    local sock = rawget(self, "_sock")
    if not sock then
        return nil, "not initialized"
    end

    if rawget(self, "_subscribed") then
        return nil, "subscribed state"
    end

    return sock:setkeepalive(...)
end


function _M.get_reused_times(self)
    local sock = rawget(self, "_sock")
    if not sock then
        return nil, "not initialized"
    end

    return sock:getreusedtimes()
end


local function close(self)
    local sock = rawget(self, "_sock")
    if not sock then
        return nil, "not initialized"
    end

    return sock:close()
end
_M.close = close


local function _read_reply(self, sock)
    local line, err = sock:receive()
    if not line then
        if err == "timeout" and not rawget(self, "_subscribed") then
            sock:close()
        end
        return nil, err
    end

    local prefix = byte(line)

    if prefix == 36 then    -- char '$'
        -- print("bulk reply")

        local size = tonumber(sub(line, 2))
        if size < 0 then
            return null
        end

        local data, err = sock:receive(size)
        if not data then
            if err == "timeout" then
                sock:close()
            end
            return nil, err
        end

        local dummy, err = sock:receive(2) -- ignore CRLF
        if not dummy then
            if err == "timeout" then
                sock:close()
            end
            return nil, err
        end

        return data

    elseif prefix == 43 then    -- char '+'
        -- print("status reply")

        return sub(line, 2)

    elseif prefix == 42 then -- char '*'
        local n = tonumber(sub(line, 2))

        -- print("multi-bulk reply: ", n)
        if n < 0 then
            return null
        end

        local vals = new_tab(n, 0)
        local nvals = 0
        for i = 1, n do
            local res, err = _read_reply(self, sock)
            if res then
                nvals = nvals + 1
                vals[nvals] = res

            elseif res == nil then
                return nil, err

            else
                -- be a valid redis error value
                nvals = nvals + 1
                vals[nvals] = {false, err}
            end
        end

        return vals

    elseif prefix == 58 then    -- char ':'
        -- print("integer reply")
        return tonumber(sub(line, 2))

    elseif prefix == 45 then    -- char '-'
        -- print("error reply: ", n)

        return false, sub(line, 2)

    else
        -- when `line` is an empty string, `prefix` will be equal to nil.
        return nil, "unknown prefix: \"" .. tostring(prefix) .. "\""
    end
end


local function _gen_req(args)
    local nargs = #args

    local req = get_tab_from_pool()
    req[1] = "*"
    req[2] = nargs
    req[3] = "\r\n"
    local nbits = 4

    for i = 1, nargs do
        local arg = args[i]
        if type(arg) ~= "string" then
            arg = tostring(arg)
        end

        req[nbits] = "$"
        req[nbits + 1] = #arg
        req[nbits + 2] = "\r\n"
        req[nbits + 3] = arg
        req[nbits + 4] = "\r\n"

        nbits = nbits + 5
    end

    -- it is much faster to do string concatenation on the C land
    -- in real world (large number of strings in the Lua VM)
    return req
end


local function _check_msg(self, res)
    return rawget(self, "_subscribed") and
        type(res) == "table" and (res[1] == "message" or res[1] == "pmessage")
end


local function _do_cmd(self, ...)
    local args = {...}

    local sock = rawget(self, "_sock")
    if not sock then
        return nil, "not initialized"
    end

    local req = _gen_req(args)

    local reqs = rawget(self, "_reqs")
    if reqs then
        reqs[#reqs + 1] = req
        return
    end

    -- print("request: ", table.concat(req))

    local bytes, err = sock:send(req)
    put_tab_into_pool(req)

    if not bytes then
        return nil, err
    end

    local res, err = _read_reply(self, sock)
    while _check_msg(self, res) do
        if rawget(self, "_buffered_msg") == nil then
            self._buffered_msg = new_tab(1, 0)
        end

        tab_insert(self._buffered_msg, res)
        res, err = _read_reply(self, sock)
    end

    return res, err
end


local function _check_unsubscribed(self, res)
    if type(res) == "table"
       and (res[1] == "unsubscribe" or res[1] == "punsubscribe")
    then
        self._n_channel[res[1]] = self._n_channel[res[1]] - 1

        local buffered_msg = rawget(self, "_buffered_msg")
        if buffered_msg then
            -- remove messages of unsubscribed channel
            local msg_type =
                (res[1] == "punsubscribe") and "pmessage" or "message"
            local j = 1
            for _, msg in ipairs(buffered_msg) do
                if msg[1] == msg_type and msg[2] ~= res[2] then
                    -- move messages to overwrite the removed ones
                    buffered_msg[j] = msg
                    j = j + 1
                end
            end

            -- clear remain messages
            for i = j, #buffered_msg do
                buffered_msg[i] = nil
            end

            if #buffered_msg == 0 then
                self._buffered_msg = nil
            end
        end

        if res[3] == 0 then
            -- all channels are unsubscribed
            self._subscribed = false
        end
    end
end


local function _check_subscribed(self, res)
    if type(res) == "table"
       and (res[1] == "subscribe" or res[1] == "psubscribe")
   then
        if res[1] == "subscribe" then
            self._n_channel.unsubscribe = self._n_channel.unsubscribe + 1

        elseif res[1] == "psubscribe" then
            self._n_channel.punsubscribe = self._n_channel.punsubscribe + 1
        end
    end
end


function _M.read_reply(self)
    local sock = rawget(self, "_sock")
    if not sock then
        return nil, "not initialized"
    end

    if not rawget(self, "_subscribed") then
        return nil, "not subscribed"
    end

    local buffered_msg = rawget(self, "_buffered_msg")
    if buffered_msg then
        local msg = buffered_msg[1]
        tab_remove(buffered_msg, 1)

        if #buffered_msg == 0 then
            self._buffered_msg = nil
        end

        return msg
    end

    local res, err = _read_reply(self, sock)
    _check_unsubscribed(self, res)

    return res, err
end


local function do_cmd(self, cmd, ...)
    local module_prefix = rawget(self, "_module_prefix")
    if module_prefix then
        self._module_prefix = nil
        return _do_cmd(self, module_prefix .. "." .. cmd, ...)
    end

    return _do_cmd(self, cmd, ...)
end


for i = 1, #common_cmds do
    local cmd = common_cmds[i]

    _M[cmd] =
        function (self, ...)
            return do_cmd(self, cmd, ...)
        end
end


local function handle_subscribe_result(self, cmd, nargs, res)
    local err
    _check_subscribed(self, res)

    if nargs <= 1 then
        return res
    end

    local results = new_tab(nargs, 0)
    results[1] = res
    local sock = rawget(self, "_sock")

    for i = 2, nargs do
        res, err = _read_reply(self, sock)
        if not res then
            return nil, err
        end

        _check_subscribed(self, res)
        results[i] = res
    end

    return results
end

for i = 1, #sub_commands do
    local cmd = sub_commands[i]

    _M[cmd] =
        function (self, ...)
            if not rawget(self, "_subscribed") then
                self._subscribed = true
            end

            local nargs = select("#", ...)

            local res, err = _do_cmd(self, cmd, ...)
            if not res then
                return nil, err
            end

            return handle_subscribe_result(self, cmd, nargs, res)
        end
end


local function handle_unsubscribe_result(self, cmd, nargs, res)
    local err
    _check_unsubscribed(self, res)

    if self._n_channel[cmd] == 0 or nargs == 1 then
        return res
    end

    local results = new_tab(nargs, 0)
    results[1] = res
    local sock = rawget(self, "_sock")
    local i = 2

    while nargs == 0 or i <= nargs do
        res, err = _read_reply(self, sock)
        if not res then
            return nil, err
        end

        results[i] = res
        i = i + 1

        _check_unsubscribed(self, res)
        if self._n_channel[cmd] == 0 then
            -- exit the loop for unsubscribe() call
            break
        end
    end

    return results
end

for i = 1, #unsub_commands do
    local cmd = unsub_commands[i]

    _M[cmd] =
        function (self, ...)
            -- assume all channels are unsubscribed by only one time
            if not rawget(self, "_subscribed") then
                return nil, "not subscribed"
            end

            local nargs = select("#", ...)

            local res, err = _do_cmd(self, cmd, ...)
            if not res then
                return nil, err
            end

            return handle_unsubscribe_result(self, cmd, nargs, res)
        end
end


function _M.hmset(self, hashname, ...)
    if select('#', ...) == 1 then
        local t = select(1, ...)

        local n = 0
        for k, v in pairs(t) do
            n = n + 2
        end

        local array = new_tab(n, 0)

        local i = 0
        for k, v in pairs(t) do
            array[i + 1] = k
            array[i + 2] = v
            i = i + 2
        end
        -- print("key", hashname)
        return _do_cmd(self, "hmset", hashname, unpack(array))
    end

    -- backwards compatibility
    return _do_cmd(self, "hmset", hashname, ...)
end


function _M.init_pipeline(self, n)
    self._reqs = new_tab(n or 4, 0)
end


function _M.cancel_pipeline(self)
    self._reqs = nil
end


function _M.commit_pipeline(self)
    local reqs = rawget(self, "_reqs")
    if not reqs then
        return nil, "no pipeline"
    end

    self._reqs = nil

    local sock = rawget(self, "_sock")
    if not sock then
        return nil, "not initialized"
    end

    local bytes, err = sock:send(reqs)
    for _, req in ipairs(reqs) do
        put_tab_into_pool(req)
    end

    if not bytes then
        return nil, err
    end

    local nvals = 0
    local nreqs = #reqs
    local vals = new_tab(nreqs, 0)
    for i = 1, nreqs do
        local res, err = _read_reply(self, sock)
        if res then
            nvals = nvals + 1
            vals[nvals] = res

        elseif res == nil then
            if err == "timeout" then
                close(self)
            end
            return nil, err

        else
            -- be a valid redis error value
            nvals = nvals + 1
            vals[nvals] = {false, err}
        end
    end

    return vals
end


function _M.array_to_hash(self, t)
    local n = #t
    -- print("n = ", n)
    local h = new_tab(0, n / 2)
    for i = 1, n, 2 do
        h[t[i]] = t[i + 1]
    end
    return h
end


-- this method is deperate since we already do lazy method generation.
function _M.add_commands(...)
    local cmds = {...}
    for i = 1, #cmds do
        local cmd = cmds[i]
        _M[cmd] =
            function (self, ...)
                return _do_cmd(self, cmd, ...)
            end
    end
end


setmetatable(_M, {__index = function(self, cmd)
    local method =
        function (self, ...)
            return do_cmd(self, cmd, ...)
        end

    -- cache the lazily generated method in our
    -- module table
    _M[cmd] = method
    return method
end})


return _M
