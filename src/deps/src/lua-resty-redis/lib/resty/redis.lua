-- Copyright (C) Yichun Zhang (agentzh)


local sub = string.sub
local byte = string.byte
local str_fmt = string.format
local floor = math.floor
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
-- Redis integers are 64-bit; larger values keep tostring()'s form
local MAX_INT = 2^63
local _M = new_tab(0, 55)

_M._VERSION = '0.34'


local common_cmds = {
    "get",      "set",          "mget",     "mset",
    "del",      "incr",         "decr",                 -- Strings
    "llen",     "lindex",       "lpop",     "lpush",
    "lrange",   "linsert",                              -- Lists
    "hexists",  "hget",         "hset",     --[[ "hmget", ]]
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

local blocking_commands = {
    "blpop", "brpop"
}

local unsub_commands = {
    "unsubscribe", "punsubscribe"
}


local mt = { __index = _M }

local _do_cmd


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
    local redis = setmetatable({ _sock = sock,
                          _subscribed = false,
                          _in_multi = false,
                          _n_channel = {
                            unsubscribe = 0,
                            punsubscribe = 0,
                          },
                        }, mt)
    return redis
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

    if unix and port_or_opts ~= nil then
        opts = port_or_opts
    end

    local db, username, password, tcp_keepalive
    if opts then
        db = opts.db
        if db ~= nil then
            local typ = type(db)
            db = tonumber(db)
            if db == nil then
                error("bad option db: number expected, got " .. typ, 2)
            end
        end

        tcp_keepalive = opts.tcp_keepalive

        password = opts.password
        if password == "" then
            password = nil
        end

        username = opts.username
        if not password or username == "" then
            username = nil
        end

        if (db or username) and not opts.pool then
            -- a pool per database / ACL user, otherwise a pooled connection
            -- would carry its SELECT/AUTH state over to the next user (issue #53);
            -- the numeric db comes first so that no user name can impersonate it
            local pool = unix and host or (host .. ":" .. port_or_opts)
            if db then
                pool = pool .. "/db=" .. db
            end
            if username then
                pool = pool .. "/user=" .. username
            end

            local copy = {}
            for k, v in pairs(opts) do
                copy[k] = v
            end
            copy.pool = pool
            opts = copy
        end
    end

    self._subscribed = false
    self._in_multi = false

    local ok, err

    if unix then
         -- second argument of sock:connect() cannot be nil
         if opts ~= nil then
             ok, err = sock:connect(host, opts)
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

    if tcp_keepalive then
        local res, kerr = sock:setoption("keepalive", true)
        if not res then
            sock:close()
            return nil, "failed to enable tcp keepalive: " .. tostring(kerr)
        end
    end

    if (password or db) and sock:getreusedtimes() == 0 then
        -- send AUTH/SELECT directly even if a pipeline was opened before connect()
        local reqs = rawget(self, "_reqs")
        self._reqs = nil

        local res, cerr
        if password then
            if username then
                res, cerr = _do_cmd(self, "auth", username, password)
            else
                res, cerr = _do_cmd(self, "auth", password)
            end

            if not res then
                self._reqs = reqs
                sock:close()
                return nil, "failed to authenticate: " .. tostring(cerr)
            end
        end

        if db then
            res, cerr = _do_cmd(self, "select", db)
            if not res then
                self._reqs = reqs
                sock:close()
                return nil, "failed to select database " .. tostring(db) .. ": "
                            .. tostring(cerr)
            end
        end

        self._reqs = reqs
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

    if rawget(self, "_in_multi") then
        return nil, "in transaction"
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
        if err == "timeout" and not rawget(self, "_subscribed") and not rawget(self, "_blocking") then
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
        local typ = type(arg)
        if typ == "number" and (arg >= 1e14 or arg <= -1e14)
           and arg == floor(arg) and arg <= MAX_INT and arg >= -MAX_INT
        then
            -- tostring() uses %.14g, which turns integers of 15+ digits
            -- into scientific notation (issue #135)
            arg = str_fmt("%.0f", arg)

        elseif typ ~= "string" then
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


_do_cmd = function (self, ...)
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

for i = 1, #blocking_commands do
    local cmd = blocking_commands[i]

    _M[cmd] =
        function (self, ...)
            if not rawget(self, "_blocking") then
                self._blocking = true
            end
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


function _M.hmget(self, hashname, ...)
    if select("#", ...) == 1 and type((...)) == "table" then
        return do_cmd(self, "hmget", hashname, unpack((...)))
    end

    return do_cmd(self, "hmget", hashname, ...)
end


-- the connection must not be put back into the pool while a transaction is
-- open on the server (issue #176): MULTI marks it, and only a confirmed EXEC
-- or DISCARD reply clears it. Pipelined commands are settled when their
-- replies are read in commit_pipeline().
local function update_multi_state(self, cmd, res)
    if cmd == "multi" then
        self._in_multi = true

    elseif res then
        self._in_multi = false
    end
end


local function do_multi_cmd(self, cmd, ...)
    -- Prefixed commands do not change Redis transaction state.
    if rawget(self, "_module_prefix") then
        return do_cmd(self, cmd, ...)
    end

    local reqs = rawget(self, "_reqs")
    if reqs then
        local res, err = do_cmd(self, cmd, ...)

        local txn_reqs = rawget(self, "_txn_reqs")
        if not txn_reqs then
            txn_reqs = {}
            self._txn_reqs = txn_reqs
        end
        txn_reqs[#reqs] = cmd

        return res, err
    end

    local res, err = do_cmd(self, cmd, ...)
    update_multi_state(self, cmd, res)

    return res, err
end


function _M.multi(self, ...)
    return do_multi_cmd(self, "multi", ...)
end


function _M.exec(self, ...)
    return do_multi_cmd(self, "exec", ...)
end


function _M.discard(self, ...)
    return do_multi_cmd(self, "discard", ...)
end


function _M.init_pipeline(self, n)
    self._reqs = new_tab(n or 4, 0)
    self._txn_reqs = nil
end


function _M.cancel_pipeline(self)
    self._reqs = nil
    self._txn_reqs = nil
end


function _M.commit_pipeline(self)
    local reqs = rawget(self, "_reqs")
    if not reqs then
        return nil, "no pipeline"
    end

    self._reqs = nil

    local txn_reqs = rawget(self, "_txn_reqs")
    self._txn_reqs = nil

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
        if txn_reqs and txn_reqs[i] then
            update_multi_state(self, txn_reqs[i], res)
        end

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
