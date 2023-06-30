---
-- File storage backend for session library.
--
-- @module resty.session.file


local file_utils = require "resty.session.file.utils"


local run_worker_thread = file_utils.run_worker_thread


local setmetatable = setmetatable
local error = error
local byte = string.byte


local SLASH_BYTE = byte("/")


local THREAD_MODULE = "resty.session.file.thread"


local DEFAULT_POOL = "default"
local DEFAULT_PATH do
  local path = os.tmpname()
  local pos
  for i = #path, 1, -1 do
    if byte(path, i) == SLASH_BYTE then
      pos = i
      break
    end
  end

  DEFAULT_PATH = path:sub(1, pos)
end


local function run_thread(self, func, ...)
  local ok, res, err = run_worker_thread(self.pool, THREAD_MODULE, func, self.path, self.prefix, self.suffix, ...)
  if not ok then
    return nil, res
  end

  return res, err
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
  return run_thread(self, "set", ...)
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
  return run_thread(self, "get", ...)
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
  return run_thread(self, "delete", ...)
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
  return run_thread(self, "read_metadata", ...)
end


local storage = {}


---
-- Configuration
-- @section configuration


---
-- File storage backend configuration
-- @field prefix File prefix for session file.
-- @field suffix File suffix (or extension without `.`) for session file.
-- @field pool Name of the thread pool under which file writing happens (available on Linux only).
-- @field path Path (or directory) under which session files are created.
-- @table configuration


---
-- Constructors
-- @section constructors


---
-- Create a file storage.
--
-- This creates a new file storage instance.
--
-- @function module.new
-- @tparam[opt] table configuration file storage @{configuration}
-- @treturn table file storage instance
function storage.new(configuration)
  local prefix = configuration and configuration.prefix
  local suffix = configuration and configuration.suffix

  local pool   = configuration and configuration.pool or DEFAULT_POOL
  local path   = configuration and configuration.path or DEFAULT_PATH

  if byte(path, -1) ~= SLASH_BYTE then
    path = path .. "/"
  end

  return setmetatable({
    prefix = prefix ~= "" and prefix or nil,
    suffix = suffix ~= "" and suffix or nil,
    pool = pool,
    path = path,
  }, metatable)
end


return storage
