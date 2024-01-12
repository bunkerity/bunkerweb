---
-- Memcached backend for session library
--
-- @module resty.session.memcached


local memcached = require "resty.memcached"
local buffer = require "string.buffer"
local utils = require "resty.session.utils"


local meta_get_latest = utils.meta_get_latest
local meta_get_value = utils.meta_get_value
local get_name = utils.get_name
local errmsg = utils.errmsg


local setmetatable = setmetatable
local random = math.random
local error = error
local pairs = pairs
local null = ngx.null
local log = ngx.log
local max = math.max


local WARN = ngx.WARN


local CLEANUP_PROBABILITY = 0.1 -- 1 / 10
local SESSIONS_BUFFER = buffer.new(128)


local function cleanup(memc, meta_key, current_time)
  local res, _, cas_unique, err = memc:gets(meta_key)
  if not res then
    return nil, err
  end

  local sessions = meta_get_latest(res, current_time)

  SESSIONS_BUFFER:reset()

  local max_expiry = current_time
  for key, exp in pairs(sessions) do
    SESSIONS_BUFFER:put(meta_get_value(key, exp))
    max_expiry = max(max_expiry, exp)
  end

  local exp = max_expiry - current_time
  if exp > 0 then
    return memc:cas(meta_key, SESSIONS_BUFFER:get(), cas_unique, exp)
  end

  return memc:delete(meta_key)
end


local function read_metadata(self, memc, name, audience, subject, current_time)
  local meta_key = get_name(self, name, audience, subject)
  local res, _, err = memc:get(meta_key)
  if not res then
    return nil, err
  end

  return meta_get_latest(res, current_time)
end


-- TODO possible improvement: when available in the lib, use pipelines
local function SET(self, memc, name, key, value, ttl, current_time, old_key, stale_ttl, metadata, remember)
  local inferred_key = get_name(self, name, key)

  if not metadata and not old_key then
    return memc:set(inferred_key, value, ttl)
  end

  local ok, err = memc:set(inferred_key, value, ttl)
  if not ok then
    return nil, err
  end

  local old_name = old_key and get_name(self, name, old_key)
  if old_name then
    if remember then
      memc:delete(old_name)
    else
      memc:touch(old_name, stale_ttl)
    end
  end

  if not metadata then
    return true
  end

  local audiences = metadata.audiences
  local subjects = metadata.subjects
  local count = #audiences
  for i = 1, count do
    local meta_key = get_name(self, name, audiences[i], subjects[i])
    local meta_value = meta_get_value(key, current_time + ttl)

    local added, err = memc:add(meta_key, meta_value)
    if not added then
      local appended, err2 = memc:append(meta_key, meta_value)
      if not appended then
        log(WARN, "[session] ", errmsg(err2 or err, "failed to store metadata"))
      end
    end

    if old_key then
      meta_value = meta_get_value(old_key, 0)
      local ok, err = memc:append(meta_key, meta_value)
      if not ok then
        log(WARN, "[session] ", errmsg(err, "failed to update metadata"))
      end
    end

    -- no need to clean up every time we write
    -- it is just beneficial when a key is used a lot
    if random() < CLEANUP_PROBABILITY then
      cleanup(memc, meta_key, current_time)
    end
  end

  return true
end


local function GET(self, memc, name, key)
  local res, _, err = memc:get(get_name(self, name, key))
  if err then
    return nil, err
  end
  return res
end


local function DELETE(self, memc, name, key, current_time, metadata)
  local key_name = get_name(self, name, key)
  local ok, err = memc:delete(key_name)
  if not metadata then
    return ok, err
  end

  local audiences = metadata.audiences
  local subjects = metadata.subjects
  local count = #audiences
  for i = 1, count do
    local meta_key = get_name(self, name, audiences[i], subjects[i])
    local meta_value = meta_get_value(key, 0)
    local ok, err = memc:append(meta_key, meta_value)
    if not ok and err ~= "NOT_STORED" then
      log(WARN, "[session] ", errmsg(err, "failed to update metadata"))
    end

    cleanup(memc, meta_key, current_time)
  end

  return ok, err
end


local DEFAULT_HOST = "127.0.0.1"
local DEFAULT_PORT = 11211


local function exec(self, func, ...)
  local memc = memcached:new()

  local connect_timeout = self.connect_timeout
  local send_timeout = self.send_timeout
  local read_timeout = self.read_timeout
  if connect_timeout or send_timeout or read_timeout then
    memc:set_timeouts(connect_timeout, send_timeout, read_timeout)
  end

  local ok, err do
    local socket = self.socket
    if socket then
      ok, err = memc:connect(socket, self.options)
    else
      ok, err = memc:connect(self.host, self.port, self.options)
    end
  end
  if not ok then
    return nil, err
  end

  if self.ssl and memc:get_reused_times() == 0 then
    ok, err = memc:sslhandshake(false, self.server_name, self.ssl_verify)
    if not ok then
      memc:close()
      return nil, err
    end
  end

  ok, err = func(self, memc, ...)

  if err then
    memc:close()
    return nil, err
  end

  if not memc:set_keepalive(self.keepalive_timeout) then
    memc:close()
  end

  if ok == null then
    ok = nil
  end

  return ok, err
end


---
-- Storage
-- @section instance


local metatable = {}


metatable.__index = metatable


function metatable.__newindex()
  error("attempt to update a read-only table", 2)
end


---
-- Store session data.
--
-- @function instance:set
-- @tparam string name cookie name
-- @tparam string key session key
-- @tparam string value session value
-- @tparam number ttl session ttl
-- @tparam number current_time current time
-- @tparam[opt] string old_key old session id
-- @tparam string stale_ttl stale ttl
-- @tparam[opt] table metadata table of metadata
-- @tparam boolean remember whether storing persistent session or not
-- @treturn true|nil ok
-- @treturn string error message
function metatable:set(...)
  return exec(self, SET, ...)
end


---
-- Retrieve session data.
--
-- @function instance:get
-- @tparam string name cookie name
-- @tparam string key session key
-- @treturn string|nil session data
-- @treturn string error message
function metatable:get(...)
  return exec(self, GET, ...)
end


---
-- Delete session data.
--
-- @function instance:delete
-- @tparam string name cookie name
-- @tparam string key session key
-- @tparam[opt] table metadata session meta data
-- @treturn boolean|nil session data
-- @treturn string error message
function metatable:delete(...)
  return exec(self, DELETE, ...)
end


---
-- Read session metadata.
--
-- @function instance:read_metadata
-- @tparam string name cookie name
-- @tparam string audience session key
-- @tparam string subject session key
-- @tparam number current_time current time
-- @treturn table|nil session metadata
-- @treturn string error message
function metatable:read_metadata(...)
  return exec(self, read_metadata, ...)
end


local storage = {}


---
-- Configuration
-- @section configuration


---
-- Distributed shared memory storage backend configuration
-- @field prefix Prefix for the keys stored in memcached.
-- @field suffix Suffix for the keys stored in memcached.
-- @field host The host to connect (defaults to `"127.0.0.1"`).
-- @field port The port to connect (defaults to `11211`).
-- @field socket The socket file to connect to (defaults to `nil`).
-- @field connect_timeout Controls the default timeout value used in TCP/unix-domain socket object's `connect` method.
-- @field send_timeout Controls the default timeout value used in TCP/unix-domain socket object's `send` method.
-- @field read_timeout Controls the default timeout value used in TCP/unix-domain socket object's `receive` method.
-- @field keepalive_timeout Controls the default maximal idle time of the connections in the connection pool.
-- @field pool A custom name for the connection pool being used.
-- @field pool_size The size of the connection pool.
-- @field backlog A queue size to use when the connection pool is full (configured with @pool_size).
-- @field ssl Enable SSL (defaults to `false`).
-- @field ssl_verify Verify server certificate (defaults to `nil`).
-- @field server_name The server name for the new TLS extension Server Name Indication (SNI).
-- @table configuration


---
-- Constructors
-- @section constructors


---
-- Create a memcached storage.
--
-- This creates a new memcached storage instance.
--
-- @function module.new
-- @tparam[opt] table configuration memcached storage @{configuration}
-- @treturn table memcached storage instance
function storage.new(configuration)
  local prefix            = configuration and configuration.prefix
  local suffix            = configuration and configuration.suffix

  local host              = configuration and configuration.host or DEFAULT_HOST
  local port              = configuration and configuration.port or DEFAULT_PORT
  local socket            = configuration and configuration.socket

  local connect_timeout   = configuration and configuration.connect_timeout
  local send_timeout      = configuration and configuration.send_timeout
  local read_timeout      = configuration and configuration.read_timeout
  local keepalive_timeout = configuration and configuration.keepalive_timeout

  local pool              = configuration and configuration.pool
  local pool_size         = configuration and configuration.pool_size
  local backlog           = configuration and configuration.backlog
  local ssl               = configuration and configuration.ssl
  local ssl_verify        = configuration and configuration.ssl_verify
  local server_name       = configuration and configuration.server_name

  if pool or pool_size or backlog then
    return setmetatable({
      prefix = prefix,
      suffix = suffix,
      host = host,
      port = port,
      socket = socket,
      connect_timeout = connect_timeout,
      send_timeout = send_timeout,
      read_timeout = read_timeout,
      keepalive_timeout = keepalive_timeout,
      ssl = ssl,
      ssl_verify = ssl_verify,
      server_name = server_name,
      options = {
        pool = pool,
        pool_size = pool_size,
        backlog = backlog,
      }
    }, metatable)
  end

  return setmetatable({
    prefix = prefix,
    suffix = suffix,
    host = host,
    port = port,
    socket = socket,
    connect_timeout = connect_timeout,
    send_timeout = send_timeout,
    read_timeout = read_timeout,
    keepalive_timeout = keepalive_timeout,
    ssl = ssl,
    ssl_verify = ssl_verify,
    server_name = server_name,
  }, metatable)
end


return storage
