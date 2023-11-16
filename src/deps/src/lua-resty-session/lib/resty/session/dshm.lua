---
-- Distributed Shared Memory (DSHM) backend for session library
--
-- @module resty.session.dshm


local buffer = require "string.buffer"
local utils = require "resty.session.utils"
local dshm = require "resty.dshm"


local meta_get_latest = utils.meta_get_latest
local meta_get_value = utils.meta_get_value
local get_name = utils.get_name


local setmetatable = setmetatable
local error = error
local pairs = pairs
local null = ngx.null
local max = math.max


local DEFAULT_HOST = "127.0.0.1"
local DEFAULT_PORT = 4321


local SESSIONS_BUFFER = buffer.new(128)


-- not safe for concurrent access
local function update_meta(dshmc, meta_key, key, exp, current_time)
  local metadata = dshmc:get(meta_key)
  local sessions = metadata and meta_get_latest(metadata, current_time) or {}

  SESSIONS_BUFFER:reset()

  sessions[key] = exp > 0 and exp or nil

  local max_expiry = current_time
  for s, e in pairs(sessions) do
    SESSIONS_BUFFER:put(meta_get_value(s, e))
    max_expiry = max(max_expiry, e)
  end

  local ser = SESSIONS_BUFFER:get()

  if #ser > 0 then
    return dshmc:set(meta_key, ser, max_expiry - current_time)
  end

  return dshmc:delete(meta_key)
end


local function READ_METADATA(self, dshmc, name, audience, subject, current_time)
  local meta_key = get_name(self, name, audience, subject)
  local res = dshmc:get(meta_key)
  if not res then
    return nil, "not found"
  end

  return meta_get_latest(res, current_time)
end


local function SET(self, dshmc, name, key, value, ttl, current_time, old_key, stale_ttl, metadata, remember)
  local inferred_key = get_name(self, name, key)

  if not metadata and not old_key then
    return dshmc:set(inferred_key, value, ttl)
  end

  local ok, err = dshmc:set(inferred_key, value, ttl)
  if err then
    return nil, err
  end

  local old_name = old_key and get_name(self, name, old_key)
  if old_name then
    if remember then
      dshmc:delete(old_name)
    else
      dshmc:touch(old_name, stale_ttl)
    end
  end

  if metadata then
    local audiences = metadata.audiences
    local subjects = metadata.subjects
    local count = #audiences
    for i = 1, count do
      local meta_key = get_name(self, name, audiences[i], subjects[i])
      update_meta(dshmc, meta_key, key, current_time + ttl, current_time)

      if old_key then
        update_meta(dshmc, meta_key, old_key, 0, current_time)
      end
    end
  end
  return ok
end


local function GET(self, dshmc, name, key)
  local res, err = dshmc:get(get_name(self, name, key))
  if err then
    return nil, err
  end
  return res
end


local function DELETE(self, dshmc, name, key, current_time, metadata)
  local key_name = get_name(self, name, key)
  local ok, err = dshmc:delete(key_name)

  if not metadata then
    return ok, err
  end

  local audiences = metadata.audiences
  local subjects = metadata.subjects
  local count = #audiences
  for i = 1, count do
    local meta_key = get_name(self, name, audiences[i], subjects[i])
    update_meta(dshmc, meta_key, key, 0, current_time)
  end

  return ok, err
end


local function exec(self, func, ...)
  local dshmc = dshm:new()
  local connect_timeout = self.connect_timeout
  local send_timeout = self.send_timeout
  local read_timeout = self.read_timeout
  if connect_timeout or send_timeout or read_timeout then
    dshmc.sock:settimeouts(connect_timeout, send_timeout, read_timeout)
  end

  local ok, err = dshmc:connect(self.host, self.port, self.options)
  if not ok then
    return nil, err
  end

  if self.ssl and dshmc:get_reused_times() == 0 then
    ok, err = dshmc.sock:sslhandshake(false, self.server_name, self.ssl_verify)
    if not ok then
      dshmc:close()
      return nil, err
    end
  end

  ok, err = func(self, dshmc, ...)
  if err then
    dshmc:close()
    return nil, err
  end

  if not dshmc:set_keepalive(self.keepalive_timeout) then
    dshmc:close()
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
  return exec(self, READ_METADATA, ...)
end


local storage = {}


---
-- Configuration
-- @section configuration


---
-- Distributed shared memory storage backend configuration
-- @field prefix The prefix for the keys stored in DSHM.
-- @field suffix The suffix for the keys stored in DSHM.
-- @field host The host to connect (defaults to `"127.0.0.1"`).
-- @field port The port to connect (defaults to `4321`).
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
-- Create a distributed shared memory storage.
--
-- This creates a new distributed shared memory storage instance.
--
-- @function module.new
-- @tparam[opt] table configuration DSHM storage @{configuration}
-- @treturn table DSHM storage instance
function storage.new(configuration)
  local prefix            = configuration and configuration.prefix
  local suffix            = configuration and configuration.suffix

  local host              = configuration and configuration.host or DEFAULT_HOST
  local port              = configuration and configuration.port or DEFAULT_PORT

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
