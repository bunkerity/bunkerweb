local setmetatable  = setmetatable
local tonumber      = tonumber
local type          = type
local reverse       = string.reverse
local gmatch        = string.gmatch
local find          = string.find
local byte          = string.byte
local sub           = string.sub
local concat        = table.concat
local sleep         = ngx.sleep
local null          = ngx.null
local var           = ngx.var

local LB = byte("[")
local RB = byte("]")

local function parse_cluster_nodes(nodes)
    if not nodes or nodes == "" then
        return nil
    end

    if type(nodes) == "table" then
        return nodes
    end

    local addrs
    local i
    for node in gmatch(nodes, "%S+") do
        local ip   = node
        local port = 6379
        local pos = find(reverse(ip), ":", 2, true)
        if pos then
            local p = tonumber(sub(ip, -pos + 1), 10)
            if p >= 1 and p <= 65535 then
                local addr = sub(ip, 1, -pos - 1)
                if find(addr, ":", 1, true) then
                    if byte(addr, -1) == RB then
                        ip   = addr
                        port = p
                    end

                else
                    ip   = addr
                    port = p
                end
            end
        end

        if byte(ip, 1, 1) == LB then
            ip = sub(ip, 2)
        end

        if byte(ip, -1) == RB then
            ip = sub(ip, 1, -2)
        end

        if not addrs then
            i = 1
            addrs = {{
              ip   = ip,
              port = port,
            }}
        else
            i = i + 1
            addrs[i] = {
                ip   = ip,
                port = port,
            }
        end
    end

    if not i then
        return
    end

    return addrs
end

local redis_single = require "resty.redis"
local redis_cluster
do
    local pcall   = pcall
    local require = require
    local ok
    ok, redis_cluster = pcall(require, "resty.rediscluster")
    if not ok then
        ok, redis_cluster = pcall(require, "rediscluster")
        if not ok then
            redis_cluster = nil
        end
    end
end

local UNLOCK = [[
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
]]

local function enabled(value)
    if value == nil then return nil end
    return value == true or (value == "1" or value == "true" or value == "on")
end

local function ifnil(value, default)
    if value == nil then
        return default
    end

    return enabled(value)
end

local defaults = {
    prefix          = var.session_redis_prefix                         or "sessions",
    socket          = var.session_redis_socket,
    host            = var.session_redis_host                           or "127.0.0.1",
    username        = var.session_redis_username,
    password        = var.session_redis_password                       or var.session_redis_auth,
    server_name     = var.session_redis_server_name,
    ssl             = enabled(var.session_redis_ssl)                   or false,
    ssl_verify      = enabled(var.session_redis_ssl_verify)            or false,
    uselocking      = enabled(var.session_redis_uselocking             or true),
    port            = tonumber(var.session_redis_port,            10)  or 6379,
    database        = tonumber(var.session_redis_database,        10)  or 0,
    connect_timeout = tonumber(var.session_redis_connect_timeout, 10),
    read_timeout    = tonumber(var.session_redis_read_timeout,    10),
    send_timeout    = tonumber(var.session_redis_send_timeout,    10),
    spinlockwait    = tonumber(var.session_redis_spinlockwait,    10)  or 150,
    maxlockwait     = tonumber(var.session_redis_maxlockwait,     10)  or 30,
    pool = {
        name        = var.session_redis_pool_name,
        timeout     = tonumber(var.session_redis_pool_timeout,    10),
        size        = tonumber(var.session_redis_pool_size,       10),
        backlog     = tonumber(var.session_redis_pool_backlog,    10),
    },
}


if redis_cluster then
    defaults.cluster = {
        name            = var.session_redis_cluster_name,
        dict            = var.session_redis_cluster_dict,
        maxredirections = tonumber(var.session_redis_cluster_maxredirections, 10),
        nodes           = parse_cluster_nodes(var.session_redis_cluster_nodes),
    }
end

local storage = {}

storage.__index = storage

function storage.new(session)
    local config  = session.redis         or defaults
    local pool    = config.pool           or defaults.pool
    local cluster = config.cluster        or defaults.cluster
    local locking = ifnil(config.uselocking, defaults.uselocking)

    local self = {
        prefix          = config.prefix                     or defaults.prefix,
        uselocking      = locking,
        spinlockwait    = tonumber(config.spinlockwait, 10) or defaults.spinlockwait,
        maxlockwait     = tonumber(config.maxlockwait,  10) or defaults.maxlockwait,
    }

    local username = config.username or defaults.username
    if username == "" then
      username = nil
    end
    local password = config.password or config.auth or defaults.password
    if password == "" then
        password = nil
    end

    local connect_timeout = tonumber(config.connect_timeout, 10) or defaults.connect_timeout

    local cluster_nodes
    if redis_cluster then
        cluster_nodes = parse_cluster_nodes(cluster.nodes or defaults.cluster.nodes)
    end

    local connect_opts = {
        pool             = pool.name                         or defaults.pool.name,
        pool_size        = tonumber(pool.size,           10) or defaults.pool.size,
        backlog          = tonumber(pool.backlog,        10) or defaults.pool.backlog,
        server_name      = config.server_name                or defaults.server_name,
        ssl              = ifnil(config.ssl,                    defaults.ssl),
        ssl_verify       = ifnil(config.ssl_verify,             defaults.ssl_verify),
    }

    if cluster_nodes then
        self.redis = redis_cluster:new({
            name               = cluster.name                          or defaults.cluster.name,
            dict_name          = cluster.dict                          or defaults.cluster.dict,
            username           = var.session_redis_username,
            password           = var.session_redis_password            or defaults.password,
            connection_timout  = connect_timeout, -- typo in library
            connection_timeout = connect_timeout,
            keepalive_timeout  = tonumber(pool.timeout,            10) or defaults.pool.timeout,
            keepalive_cons     = tonumber(pool.size,               10) or defaults.pool.size,
            max_redirection    = tonumber(cluster.maxredirections, 10) or defaults.cluster.maxredirections,
            serv_list          = cluster_nodes,
            connect_opts       = connect_opts,
        })
        self.cluster = true

    else
        local redis = redis_single:new()

        if redis.set_timeouts then
            local send_timeout = tonumber(config.send_timeout, 10) or defaults.send_timeout
            local read_timeout = tonumber(config.read_timeout, 10) or defaults.read_timeout

            if connect_timeout then
                if send_timeout and read_timeout then
                    redis:set_timeouts(connect_timeout, send_timeout, read_timeout)
                else
                    redis:set_timeout(connect_timeout)
                end
            end

        elseif redis.set_timeout and connect_timeout then
            redis:set_timeout(connect_timeout)
        end

        self.redis           = redis
        self.username        = username
        self.password        = password
        self.database        = tonumber(config.database,     10) or defaults.database
        self.pool_timeout    = tonumber(pool.timeout,        10) or defaults.pool.timeout
        self.connect_opts    = connect_opts

        local socket = config.socket or defaults.socket
        if socket and socket ~= "" then
            self.socket = socket
        else
            self.host = config.host or defaults.host
            self.port = config.port or defaults.port
        end
    end

    return setmetatable(self, storage)
end

function storage:connect()
    if self.cluster then
        return true -- cluster handles this on its own
    end

    local ok, err
    if self.socket then
        ok, err = self.redis:connect(self.socket, self.connect_opts)
    else
        ok, err = self.redis:connect(self.host, self.port, self.connect_opts)
    end

    if not ok then
        return nil, err
    end

    if self.password and self.redis:get_reused_times() == 0 then
        -- usernames are supported only on Redis 6+, so use new AUTH form only when absolutely necessary
        if self.username then
            ok, err = self.redis:auth(self.username, self.password)
        else
            ok, err = self.redis:auth(self.password)
        end
        if not ok then
            self.redis:close()
            return nil, err
        end
    end

    if self.database ~= 0 then
        ok, err = self.redis:select(self.database)
        if not ok then
            self.redis:close()
        end
    end

    return ok, err
end

function storage:set_keepalive()
    if self.cluster then
        return true -- cluster handles this on its own
    end

    return self.redis:set_keepalive(self.pool_timeout)
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
        local ok = self.redis:set(lock_key, self.token, "EX", lock_ttl, "NX")
        if ok ~= null then
            self.locked = true
            return true
        end

        sleep(waittime)
    end

    return false, "unable to acquire a session lock"
end

function storage:unlock(key)
    if not self.uselocking or not self.locked then
        return
    end

    local lock_key = concat({ key, "lock" }, "." )

    self.redis:eval(UNLOCK, 1, lock_key, self.token)
    self.locked = nil
end

function storage:get(key)
    local data, err = self.redis:get(key)
    if not data then
        return nil, err
    end

    if data == null then
        return nil
    end

    return data
end

function storage:set(key, data, lifetime)
    return self.redis:setex(key, lifetime, data)
end

function storage:expire(key, lifetime)
    return self.redis:expire(key, lifetime)
end

function storage:delete(key)
    return self.redis:del(key)
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

    ok, err = self:lock(self:key(id))

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
