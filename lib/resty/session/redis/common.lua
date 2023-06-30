---
-- Common Redis functions shared between Redis,
-- Redis Cluster and Redis Sentinel implementations.
--
-- @module resty.session.redis.common


local utils = require "resty.session.utils"


local get_name = utils.get_name
local ipairs = ipairs


---
-- Store session data.
--
-- @function module.SET
-- @tparam table storage the storage
-- @tparam table red the redis instance
-- @tparam string name the cookie name
-- @tparam string key session key
-- @tparam string value session value
-- @tparam number ttl session ttl
-- @tparam number current_time current time
-- @tparam[opt] string old_key old session id
-- @tparam string stale_ttl stale ttl
-- @tparam[opt] table metadata table of metadata
-- @tparam table remember whether storing persistent session or not
-- @treturn true|nil ok
-- @treturn string error message
local function SET(storage, red, name, key, value, ttl, current_time, old_key, stale_ttl, metadata, remember)
  if not metadata and not old_key then
    return red:set(get_name(storage, name, key), value, "EX", ttl)
  end

  local old_name
  local old_ttl
  if old_key then
    old_name = get_name(storage, name, old_key)
    if not remember then
      -- redis < 7.0
      old_ttl = red:ttl(old_name)
    end
  end

  red:init_pipeline()
  red:set(get_name(storage, name, key), value, "EX", ttl)

  -- redis < 7.0
  if old_name then
    if remember then
      red:unlink(old_name)
    elseif not old_ttl or old_ttl > stale_ttl then
      red:expire(old_name, stale_ttl)
    end
  end

  -- redis >= 7.0
  --if old_key then
  --  if remember then
  --    red:unlink(get_name(storage, name, old_key))
  --  else
  --    red:expire(get_name(storage, name, old_key), stale_ttl, "LT")
  --  end
  --end

  if metadata then
    local audiences = metadata.audiences
    local subjects = metadata.subjects
    local score = current_time - 1
    local new_score = current_time + ttl
    local count = #audiences
    for i = 1, count do
      local meta_key = get_name(storage, name, audiences[i], subjects[i])
      red:zremrangebyscore(meta_key, 0, score)
      red:zadd(meta_key, new_score, key)
      if old_key then
        red:zrem(meta_key, old_key)
      end
      red:expire(meta_key, ttl)
    end
  end

  return red:commit_pipeline()
end


---
-- Retrieve session data.
--
-- @function module.GET
-- @tparam table storage the storage
-- @tparam table red the redis instance
-- @tparam string name cookie name
-- @tparam string key session key
-- @treturn string|nil session data
-- @treturn string error message
local function GET(storage, red, name, key)
  return red:get(get_name(storage, name, key))
end


---
-- Delete session data.
--
-- @function module.UNLINK
-- @tparam table storage the storage
-- @tparam table red the redis instance
-- @tparam string name cookie name
-- @tparam string key session key
-- @tparam number current_time current time
-- @tparam[opt] table metadata session meta data
-- @treturn boolean|nil session data
-- @treturn string error message
local function UNLINK(storage, red, name, key, current_time, metadata)
  if not metadata then
    return red:unlink(get_name(storage, name, key))
  end

  red:init_pipeline()
  red:unlink(get_name(storage, name, key))
  local audiences = metadata.audiences
  local subjects = metadata.subjects
  local score = current_time - 1
  local count = #audiences
  for i = 1, count do
    local meta_key = get_name(storage, name, audiences[i], subjects[i])
    red:zremrangebyscore(meta_key, 0, score)
    red:zrem(meta_key, key)
  end

  return red:commit_pipeline()
end


---
-- Read session metadata.
--
-- @function module.READ_METADATA
-- @tparam table storage the storage
-- @tparam table red the redis instance
-- @tparam string name cookie name
-- @tparam string audience session key
-- @tparam string subject session key
-- @tparam number current_time current time
-- @treturn table|nil session metadata
-- @treturn string error message
local function READ_METADATA(storage, red, name, audience, subject, current_time)
  local sessions = {}
  local meta_key = get_name(storage, name, audience, subject)
  local res, err = red:zrange(meta_key, current_time, "+inf", "BYSCORE", "WITHSCORES")
  if not res then
    return nil, err
  end

  for i, v in ipairs(res) do
    if i % 2 ~= 0 then
      sessions[v] = res[i + 1]
    end
  end

  return sessions
end


return {
  SET = SET,
  GET = GET,
  UNLINK = UNLINK,
  READ_METADATA = READ_METADATA,
}
