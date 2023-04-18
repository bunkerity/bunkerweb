-------------------------------------------------------------------------------
-- Configures LuaLogging from the environment
--
-- @author Thijs Schreijer
--
-- @copyright 2004-2010 Kepler Project, 2011-2013 Neopallium, 2020-2023 Thijs Schreijer
--
-------------------------------------------------------------------------------

local ll = require "logging"

local levels = { "DEBUG", "INFO", "WARN", "ERROR", "FATAL", "OFF" }
local default_logger_name = "console"
local default_logger_opts = { destination = "stderr" }
local default_log_level =  ll.defaultLevel()
local default_timestamp_pattern = ll.defaultTimestampPattern()
local default_prefix = "LL"


-- -- Debug code to display environment variable access
-- local getenv = os.getenv
-- os.getenv = function(key)
--   print(key.."="..tostring(getenv(key)))
--   return getenv(key)
-- end

local M = {}

local function validate_prefix(prefix)
  if type(prefix) ~= "string" then
    return nil, "expected prefix to be a string"
  end
  if prefix ~= prefix:gsub("[^0-9a-zA-Z_]", "") then
    return nil, "prefix can contain only A-Z, 0-9, and _"
  end
  if not prefix:match("^[a-zA-Z]") then
    return nil, "prefix must start with A-Z"
  end
  return true
end


--- table that dynamically looks up environment variables.
-- Keys must be strings "A-Z0-9_", and start with "A-Z". The lookup
-- is case-insensitive, the environment variable MUST be in ALL CAPS.
-- Values will be converted to boolean if "true"/"false" (case-insensitive), or
-- to a number if a valid number.
-- @tparam string prefix for the environment variables
-- @return table
local function envloader(prefix)
  assert(validate_prefix(prefix))
  prefix = prefix .. "_"

  -- looking up in this table will fetch from the environment with the proper prefix
  -- will convert bools, numbers, "logLevel" and "logPatterns" to proper format
  --
  -- NOTE: its a meta-method; so cannot return nil+err, must throw errors!
  local env = setmetatable({}, {
    __index = function(self, key)
      if type(key) ~= "string" or
         key ~= key:gsub("[^0-9a-zA-Z_]", "") or
         #key == 0 then
        return nil
      end

      local envvar = (prefix..key):upper()

      -- log patterns table (special case)
      if key:lower() == "logpatterns" then
        local patt = {}
        for _, l in ipairs(levels) do
          local level = ll[l] -- the numeric constant for the level
          patt[level] = os.getenv(envvar.."_"..l)
        end

        if not next(patt) then
          return nil -- none set, so return nil instead of empty table
        end
        return patt
      end

      -- read the value
      local value = os.getenv(envvar)
      if value == nil then
        return value
      end

      -- logLevel constants
      if key:lower() == "loglevel" then
        for _, l in ipairs(levels) do
          if value:upper() == l then
            return ll[value:upper()]
          end
        end
        error(("not a proper loglevel set in env var %s: '%s' (use one of: %s"):
              format(envvar, value, '"DEBUG", "INFO", "WARN", "ERROR", "FATAL", "OFF"'))
      end

      -- check for boolean
      if value:lower() == "true" or value:lower() == "false" then
        return value:lower() == "true"
      end

      -- check for number
      if value:gsub("[1-9%.%-]", "") == "" and
         #value - #value:gsub("[%.]", "") <= 1 and -- zero or 1 "." character
         (#value - #value:gsub("[%-]", "") == 0 or -- zero "-" characters
          #value - #value:gsub("[%-]", "") == 1 and value:match("^%-")) and -- 1 "-" character, at first pos
         #value - #value:gsub("[1-9]", "") >= 1  then  -- at least 1 digit
          return tonumber(value)
      end

      -- return as string
      return value
    end
  })

  return env
end

do
  local base_set = false
  local base_name
  local base_opts

  --- Collects and sets the default logger and its option (does not create the logger).
  -- From an application, this is the first call to make, to set the "prefix" for the
  -- environment variables to use.
  -- @tparam prefix the prefix for env vars to use.
  -- @return true, or nil + err on failure
  function M.set_default_settings(prefix)
    if base_set then
      return nil, "already set a default"
    end
    local ok, err = validate_prefix(prefix)
    if not ok then
      return ok, err
    end
    base_opts = envloader(prefix)
    base_name = base_opts.logger
    if not base_name then
      -- no logger specified, so load options for default, and send defaults if absent
      base_name = default_logger_name
      for k, v in pairs(default_logger_opts) do
        local ev = base_opts[k]
        if ev == nil then -- false is a valid value, so check against nil
          ev = v
        end
        base_opts[k] = ev
      end
    end
    -- load additional standard options
    base_opts.logLevel = base_opts.logLevel or default_log_level
    base_opts.timestampPattern = base_opts.timestampPattern or default_timestamp_pattern
    base_opts.logPatterns = ll.buildLogPatterns(base_opts.logPatterns or {}, base_opts.logPattern)

    base_set = true
    return true
  end

  -- returns the loggername, and the options table for it
  function M.get_default_settings()
    if not base_set then
      assert(M.set_default_settings(default_prefix))
    end
    return base_name, base_opts
  end
end


--- Gets default logger options and then creates and sets the LuaLogging
-- default logger. Should be called once, at application start. Not to be called by
-- libraries, since this is an application global setting.
-- @tparam[opt] string prefix if provided, then the default settings will be set
-- using this prefix. If they were already set, it will return nil+err in that case.
-- return default logger as set
function M.set_default_logger(prefix)
  if prefix then
    local ok, err = M.set_default_settings(prefix)
    if not ok then
      return nil, err
    end
  end
  local name, opts = M.get_default_settings()

  -- create the logger
  local logger = assert(require("logging."..name)(opts))
  -- set default and return it
  return ll.defaultLogger(logger)
end



return M
