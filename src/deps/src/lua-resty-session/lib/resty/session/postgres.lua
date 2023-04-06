---
-- Postgres backend for session library.
--
-- @module resty.session.postgres


---
-- Database
-- @section database


---
-- Sessions table.
--
-- Database table that stores session data.
--
-- @usage
-- CREATE TABLE IF NOT EXISTS sessions (
--   sid  TEXT PRIMARY KEY,
--   name TEXT,
--   data TEXT,
--   exp  TIMESTAMP WITH TIME ZONE
-- );
-- CREATE INDEX ON sessions (exp);
-- @table sessions


---
-- Sessions metadata table.
--
-- This is only needed if you want to store session metadata.
--
-- @usage
-- CREATE TABLE IF NOT EXISTS sessions_meta (
--   aud TEXT,
--   sub TEXT,
--   sid TEXT REFERENCES sessions (sid) ON DELETE CASCADE ON UPDATE CASCADE,
--   PRIMARY KEY (aud, sub, sid)
-- );
-- @table metadata


local buffer = require "string.buffer"
local pgmoon = require "pgmoon"


local setmetatable = setmetatable
local random = math.random
local ipairs = ipairs
local error = error
local fmt = string.format


local DEFAULT_HOST  = "127.0.0.1"
local DEFAULT_PORT  = 5432
local DEFAULT_TABLE = "sessions"


local SET = "INSERT INTO %s (sid, name, data, exp) VALUES ('%s', '%s', '%s', TO_TIMESTAMP(%d) AT TIME ZONE 'UTC') ON CONFLICT (sid) DO UPDATE SET data = EXCLUDED.data, exp = EXCLUDED.exp"
local SET_META_PREFIX = "INSERT INTO %s (aud, sub, sid) VALUES "
local SET_META_VALUES = "('%s', '%s', '%s')"
local SET_META_SUFFIX = " ON CONFLICT DO NOTHING"
local GET_META = "SELECT sid, exp FROM %s JOIN %s USING (sid) WHERE aud = '%s' AND sub = '%s' AND exp >= TO_TIMESTAMP(%d)"
local GET = "SELECT data FROM %s WHERE sid = '%s' AND exp >= TO_TIMESTAMP(%d) AT TIME ZONE 'UTC'"
local EXPIRE = "UPDATE %s SET exp = TO_TIMESTAMP(%d) AT TIME ZONE 'UTC' WHERE sid = '%s' AND exp > TO_TIMESTAMP(%d) AT TIME ZONE 'UTC'"
local DELETE = "DELETE FROM %s WHERE sid = '%s'"
local CLEANUP = "DELETE FROM %s WHERE exp < TO_TIMESTAMP(%d)"


local SQL = buffer.new()
local STM_DELIM = ";\n"
local VAL_DELIM = ", "


local CLEANUP_PROBABILITY = 0.001 -- 1 / 1000


local function exec(self, query)
  local pg = pgmoon.new(self.options)

  local connect_timeout = self.connect_timeout
  local send_timeout = self.send_timeout
  local read_timeout = self.read_timeout
  if connect_timeout or send_timeout or read_timeout then
    if pg.sock and pg.sock.settimeouts then
      pg.sock:settimeouts(connect_timeout, send_timeout, read_timeout)
    else
      pg:settimeout(connect_timeout)
    end
  end

  local ok, err = pg:connect()
  if not ok then
    return nil, err
  end

  ok, err = pg:query(query)

  if not pg:keepalive(self.keepalive_timeout) then
    pg:close()
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
function metatable:set(name, key, value, ttl, current_time, old_key, stale_ttl, metadata, remember)
  local table = self.table
  local exp = ttl + current_time

  if not metadata and not old_key then
    return exec(self, fmt(SET, table, key, name, value, exp))
  end

  SQL:reset():putf(SET, table, key, name, value, exp)

  if old_key then
    if remember then
      SQL:put(STM_DELIM):putf(DELETE, table, old_key)
    else
      local stale_exp = stale_ttl + current_time
      SQL:put(STM_DELIM):putf(EXPIRE, table, stale_exp, old_key, stale_exp)
    end
  end

  local table_meta = self.table_meta
  if metadata then
    local audiences = metadata.audiences
    local subjects  = metadata.subjects
    local count = #audiences

    SQL:put(STM_DELIM):putf(SET_META_PREFIX, table_meta)

    for i = 1, count do
      if i > 1 then
        SQL:put(VAL_DELIM)
      end
      SQL:putf(SET_META_VALUES, audiences[i], subjects[i], key)
    end

    SQL:putf(SET_META_SUFFIX)
  end

  if random() < CLEANUP_PROBABILITY then
    SQL:put(STM_DELIM):putf(CLEANUP, self.table, current_time)
  end

  return exec(self, SQL:get())
end


---
-- Retrieve session data.
--
-- @function instance:get
-- @tparam string name cookie name
-- @tparam string key session key
-- @treturn string|nil session data
-- @treturn string error message
function metatable:get(name, key, current_time) -- luacheck: ignore
  local res, err = exec(self, fmt(GET, self.table, key, current_time))
  if not res then
    return nil, err
  end

  local row = res[1]
  if not row then
    return nil
  end

  local data = row.data
  if not row.data then
    return nil
  end

  return data
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
function metatable:delete(name, key, current_time, metadata) -- luacheck: ignore
  SQL:reset():putf(DELETE, self.table, key)

  if random() < CLEANUP_PROBABILITY then
    SQL:put(STM_DELIM):putf(CLEANUP, self.table, current_time)
  end

  return exec(self, SQL:get())
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
function metatable:read_metadata(name, audience, subject, current_time) -- luacheck: ignore
  local res = {}

  local t = exec(self, fmt(GET_META, self.table_meta, self.table, audience, subject, current_time))
  if not t then
    return nil, "not found"
  end

  for _, v in ipairs(t) do
    local key = v.sid
    if key then
      res[key] = v.exp
    end
  end

  return res
end


local storage = {}


---
-- Configuration
-- @section configuration


---
-- Postgres storage backend configuration
-- @field host The host to connect (defaults to `"127.0.0.1"`).
-- @field port The port to connect (defaults to `5432`).
-- @field application Set the name of the connection as displayed in pg_stat_activity (defaults to `"pgmoon"`).
-- @field username The database username to authenticate (defaults to `"postgres"`).
-- @field password Password for authentication, may be required depending on server configuration.
-- @field database The database name to connect.
-- @field table_name Name of database table to which to store session data (can be `database schema` prefixed) (defaults to `"sessions"`).
-- @field table_name_meta Name of database meta data table to which to store session meta data (can be `database schema` prefixed) (defaults to `"sessions_meta"`).
-- @field connect_timeout Controls the default timeout value used in TCP/unix-domain socket object's `connect` method.
-- @field send_timeout Controls the default timeout value used in TCP/unix-domain socket object's `send` method.
-- @field read_timeout Controls the default timeout value used in TCP/unix-domain socket object's `receive` method.
-- @field keepalive_timeout Controls the default maximal idle time of the connections in the connection pool.
-- @field pool A custom name for the connection pool being used.
-- @field pool_size The size of the connection pool.
-- @field backlog A queue size to use when the connection pool is full (configured with @pool_size).
-- @field ssl Enable SSL (defaults to `false`).
-- @field ssl_verify Verify server certificate (defaults to `nil`).
-- @field ssl_required Abort the connection if the server does not support SSL connections (defaults to `nil`).
-- @table configuration


---
-- Constructors
-- @section constructors


---
-- Create a Postgres storage.
--
-- This creates a new Postgres storage instance.
--
-- @function module.new
-- @tparam[opt] table configuration postgres storage @{configuration}
-- @treturn table postgres storage instance
function storage.new(configuration)
  local host              = configuration and configuration.host or DEFAULT_HOST
  local port              = configuration and configuration.port or DEFAULT_PORT

  local application       = configuration and configuration.application
  local username          = configuration and configuration.username
  local password          = configuration and configuration.password
  local database          = configuration and configuration.database

  local table_name        = configuration and configuration.table or DEFAULT_TABLE
  local table_name_meta   = configuration and configuration.table_meta

  local connect_timeout   = configuration and configuration.connect_timeout
  local send_timeout      = configuration and configuration.send_timeout
  local read_timeout      = configuration and configuration.read_timeout
  local keepalive_timeout = configuration and configuration.keepalive_timeout

  local pool              = configuration and configuration.pool
  local pool_size         = configuration and configuration.pool_size
  local backlog           = configuration and configuration.backlog
  local ssl               = configuration and configuration.ssl
  local ssl_verify        = configuration and configuration.ssl_verify
  local ssl_required      = configuration and configuration.ssl_required

  return setmetatable({
    table = table_name,
    table_meta = table_name_meta or (table_name .. "_meta"),
    connect_timeout = connect_timeout,
    send_timeout = send_timeout,
    read_timeout = read_timeout,
    keepalive_timeout = keepalive_timeout,
    options = {
      host = host,
      port = port,
      application_name = application,
      user = username,
      password = password,
      database = database,
      socket_type = "nginx",
      pool = pool,
      pool_size = pool_size,
      backlog = backlog,
      ssl = ssl,
      ssl_verify = ssl_verify,
      ssl_required = ssl_required,
    }
  }, metatable)
end


return storage
