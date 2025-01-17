---
-- Shared Memory (SHM) backend for session library
--
-- @module resty.session.shm


local table_new = require "table.new"
local utils  = require "resty.session.utils"


local meta_get_value = utils.meta_get_value
local meta_get_next = utils.meta_get_next
local get_name = utils.get_name
local errmsg = utils.errmsg


local setmetatable = setmetatable
local shared = ngx.shared
local random = math.random
local assert = assert
local error = error
local pairs = pairs
local max = math.max
local log = ngx.log


local WARN = ngx.WARN


local DEFAULT_ZONE = "sessions"
local CLEANUP_PROBABILITY = 0.1 -- 1 / 10


local function get_and_clean_metadata(dict, meta_key, current_time)
  local size = dict:llen(meta_key)
  if not size or size == 0 then
    return
  end

  local max_expiry = current_time
  local sessions = table_new(0, size)

  for _ = 1, size do
    local meta_value, err = dict:lpop(meta_key)
    if not meta_value then
      log(WARN, "[session] ", errmsg(err, "failed read meta value"))
      break
    end

    local key, err, exp = meta_get_next(meta_value, 1)
    if err then
      return nil, err
    end

    if exp and exp > current_time then
      sessions[key] = exp
      max_expiry = max(max_expiry, exp)

    else
      sessions[key] = nil
    end
  end

  for key, exp in pairs(sessions) do
    local meta_value = meta_get_value(key, exp)
    local ok, err = dict:rpush(meta_key, meta_value)
    if not ok then
      log(WARN, "[session] ", errmsg(err, "failed to update metadata"))
    end
  end

  local exp = max_expiry - current_time
  if exp > 0 then
    local ok, err = dict:expire(meta_key, max_expiry - current_time)
    if not ok and err ~= "not found" then
      log(WARN, "[session] ", errmsg(err, "failed to touch metadata"))
    end

  else
    dict:delete(meta_key)
  end

  return sessions
end


local function cleanup(dict, meta_key, current_time)
  get_and_clean_metadata(dict, meta_key, current_time)
end


local function read_metadata(self, meta_key, current_time)
  return get_and_clean_metadata(self.dict, meta_key, current_time)
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
  local dict = self.dict
  if not metadata and not old_key then
    local ok, err = dict:set(get_name(self, name, key), value, ttl)
    if not ok then
      return nil, err
    end

    return true
  end

  local old_name, old_ttl
  if old_key then
    old_name = get_name(self, name, old_key)
    if not remember then
      old_ttl = dict:ttl(old_name)
    end
  end

  local ok, err = dict:set(get_name(self, name, key), value, ttl)
  if not ok then
    return nil, err
  end

  if old_name then
    if remember then
      dict:delete(old_name)

    elseif (not old_ttl or old_ttl > stale_ttl) then
      local ok, err = dict:expire(old_name, stale_ttl)
      if not ok then
        log(WARN, "[session] ", errmsg(err, "failed to touch old session"))
      end
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

    local ok, err = dict:rpush(meta_key, meta_value)
    if not ok then
      log(WARN, "[session] ", errmsg(err, "failed to update metadata"))
    end

    if old_key then
      meta_value = meta_get_value(old_key, 0)
      local ok, err = dict:rpush(meta_key, meta_value)
      if not ok then
        log(WARN, "[session] ", errmsg(err, "failed to update old metadata"))
      end
    end

    -- no need to clean up every time we write
    -- it is just beneficial when a key is used a lot
    if random() < CLEANUP_PROBABILITY then
      cleanup(dict, meta_key, current_time)
    end
  end

  return true
end


---
-- Retrieve session data.
--
-- @function instance:get
-- @tparam string name cookie name
-- @tparam string key session key
-- @treturn string|nil session data
-- @treturn string error message
function metatable:get(name, key)
  local value, err = self.dict:get(get_name(self, name, key))
  if not value then
    return nil, err
  end

  return value
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
function metatable:delete(name, key, current_time, metadata)
  local dict = self.dict

  dict:delete(get_name(self, name, key))

  if not metadata then
    return true
  end

  local audiences = metadata.audiences
  local subjects = metadata.subjects
  local count = #audiences
  for i = 1, count do
    local meta_key = get_name(self, name, audiences[i], subjects[i])
    local meta_value = meta_get_value(key, 0)

    local ok, err = dict:rpush(meta_key, meta_value)
    if not ok then
      if not ok then
        log(WARN, "[session] ", errmsg(err, "failed to update metadata"))
      end
    end

    cleanup(dict, meta_key, current_time)
  end

  return true
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
function metatable:read_metadata(name, audience, subject, current_time)
  local meta_key = get_name(self, name, audience, subject)
  return read_metadata(self, meta_key, current_time)
end


local storage = {}


---
-- Configuration
-- @section configuration


---
-- Shared memory storage backend configuration
-- @field prefix Prefix for the keys stored in SHM.
-- @field suffix Suffix for the keys stored in SHM.
-- @field zone A name of shared memory zone (defaults to `sessions`).
-- @table configuration


---
-- Constructors
-- @section constructors


---
-- Create a SHM storage.
--
-- This creates a new shared memory storage instance.
--
-- @function module.new
-- @tparam[opt] table configuration shm storage @{configuration}
-- @treturn table shm storage instance
function storage.new(configuration)
  local prefix = configuration and configuration.prefix
  local suffix = configuration and configuration.suffix
  local zone   = configuration and configuration.zone or DEFAULT_ZONE

  local dict = assert(shared[zone], "lua_shared_dict " .. zone .. " is missing")

  return setmetatable({
    prefix = prefix,
    suffix = suffix,
    dict = dict,
  }, metatable)
end


return storage
