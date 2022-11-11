local memcached    = require "resty.memcached"
local setmetatable = setmetatable
local tonumber     = tonumber
local concat       = table.concat
local sleep        = ngx.sleep
local null         = ngx.null
local var          = ngx.var

local function enabled(value)
    if value == nil then
        return nil
    end

    return value == true
        or value == "1"
        or value == "true"
        or value == "on"
end

local function ifnil(value, default)
    if value == nil then
        return default
    end

    return enabled(value)
end

local defaults = {
    prefix          = var.session_memcache_prefix                         or "sessions",
    socket          = var.session_memcache_socket,
    host            = var.session_memcache_host                           or "127.0.0.1",
    uselocking      = enabled(var.session_memcache_uselocking             or true),
    connect_timeout = tonumber(var.session_memcache_connect_timeout, 10),
    read_timeout    = tonumber(var.session_memcache_read_timeout,    10),
    send_timeout    = tonumber(var.session_memcache_send_timeout,    10),
    port            = tonumber(var.session_memcache_port,            10)  or 11211,
    spinlockwait    = tonumber(var.session_memcache_spinlockwait,    10)  or 150,
    maxlockwait     = tonumber(var.session_memcache_maxlockwait,     10)  or 30,
    pool = {
        name        = var.session_memcache_pool_name,
        timeout     = tonumber(var.session_memcache_pool_timeout,    10),
        size        = tonumber(var.session_memcache_pool_size,       10),
        backlog     = tonumber(var.session_memcache_pool_backlog,    10),
    },
}

local storage = {}

storage.__index = storage

function storage.new(session)
    local config  = session.memcache      or defaults
    local pool    = config.pool           or defaults.pool
    local locking = ifnil(config.uselocking, defaults.uselocking)

    local connect_timeout = tonumber(config.connect_timeout, 10) or defaults.connect_timeout

    local memcache = memcached:new()
    if memcache.set_timeouts then
        local send_timeout = tonumber(config.send_timeout, 10) or defaults.send_timeout
        local read_timeout = tonumber(config.read_timeout, 10) or defaults.read_timeout

        if connect_timeout then
            if send_timeout and read_timeout then
                memcache:set_timeouts(connect_timeout, send_timeout, read_timeout)
            else
                memcache:set_timeout(connect_timeout)
            end
        end

    elseif memcache.set_timeout and connect_timeout then
        memcache:set_timeout(connect_timeout)
    end

    local self = {
        memcache     = memcache,
        prefix       = config.prefix                     or defaults.prefix,
        uselocking   = locking,
        spinlockwait = tonumber(config.spinlockwait, 10) or defaults.spinlockwait,
        maxlockwait  = tonumber(config.maxlockwait,  10) or defaults.maxlockwait,
        pool_timeout = tonumber(pool.timeout,        10) or defaults.pool.timeout,
        connect_opts = {
            pool      = pool.name                        or defaults.pool.name,
            pool_size = tonumber(pool.size,   10)        or defaults.pool.size,
            backlog   = tonumber(pool.backlog, 10)       or defaults.pool.backlog,
        },
    }

    local socket = config.socket or defaults.socket
    if socket and socket ~= "" then
        self.socket = socket
    else
        self.host = config.host or defaults.host
        self.port = config.port or defaults.port
    end

    return setmetatable(self, storage)
end

function storage:connect()
    local socket = self.socket
    if socket then
        return self.memcache:connect(socket, self.connect_opts)
    end
    return self.memcache:connect(self.host, self.port, self.connect_opts)
end

function storage:set_keepalive()
    return self.memcache:set_keepalive(self.pool_timeout)
end

function storage:key(id)
    return concat({ self.prefix, id }, ":" )
end

function storage:lock(key)
    if not self.uselocking or self.locked then
        return true
    end

    if not self.token then
        self.token = var.request_id
    end

    local lock_key = concat({ key, "lock" }, "." )
    local lock_ttl = self.maxlockwait + 1
    local attempts = (1000 / self.spinlockwait) * self.maxlockwait
    local waittime = self.spinlockwait / 1000

    for _ = 1, attempts do
        local ok = self.memcache:add(lock_key, self.token, lock_ttl)
        if ok then
            self.locked = true
            return true
        end

        sleep(waittime)
    end

    return false, "unable to acquire a session lock"
end

function storage:unlock(key)
    if not self.uselocking or not self.locked then
        return true
    end

    local lock_key = concat({ key, "lock" }, "." )
    local token = self:get(lock_key)

    if token == self.token then
        self.memcache:delete(lock_key)
        self.locked = nil
    end
end

function storage:get(key)
    local data, err = self.memcache:get(key)
    if not data then
        return nil, err
    end

    if data == null then
        return nil
    end

    return data
end

function storage:set(key, data, ttl)
    return self.memcache:set(key, data, ttl)
end

function storage:expire(key, ttl)
    return self.memcache:touch(key, ttl)
end

function storage:delete(key)
    return self.memcache:delete(key)
end

function storage:open(id, keep_lock)
    local ok, err = self:connect()
    if not ok then
        return nil, err
    end

    local key = self:key(id)

    ok, err = self:lock(key)
    if not ok then
        self:set_keepalive()
        return nil, err
    end

    local data
    data, err = self:get(key)

    if err or not data or not keep_lock then
        self:unlock(key)
    end

    self:set_keepalive()

    return data, err
end

function storage:start(id)
    if not self.uselocking or not self.locked then
        return true
    end

    local ok, err = self:connect()
    if not ok then
        return nil, err
    end

    local key = self:key(id)

    ok, err = self:lock(key)

    self:set_keepalive()

    return ok, err
end

function storage:save(id, ttl, data, close)
    local ok, err = self:connect()
    if not ok then
        return nil, err
    end

    local key = self:key(id)

    ok, err = self:set(key, data, ttl)

    if close then
        self:unlock(key)
    end

    self:set_keepalive()

    if not ok then
        return nil, err
    end

    return true
end

function storage:close(id)
    if not self.uselocking or not self.locked then
        return true
    end

    local ok, err = self:connect()
    if not ok then
        return nil, err
    end

    local key = self:key(id)

    self:unlock(key)
    self:set_keepalive()

    return true
end

function storage:destroy(id)
    local ok, err = self:connect()
    if not ok then
        return nil, err
    end

    local key = self:key(id)

    ok, err = self:delete(key)

    self:unlock(key)
    self:set_keepalive()

    return ok, err
end

function storage:ttl(id, ttl, close)
    local ok, err = self:connect()
    if not ok then
        return nil, err
    end

    local key = self:key(id)

    ok, err = self:expire(key, ttl)

    if close then
        self:unlock(key)
    end

    self:set_keepalive()

    return ok, err
end

return storage
