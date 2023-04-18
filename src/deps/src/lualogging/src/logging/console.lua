-------------------------------------------------------------------------------
-- Prints logging information to console
--
-- @author Thiago Costa Ponte (thiago@ideais.com.br)
--
-- @copyright 2004-2010 Kepler Project, 2011-2013 Neopallium, 2020-2023 Thijs Schreijer
--
-------------------------------------------------------------------------------

local io = require"io"
local logging = require"logging"
local prepareLogMsg = logging.prepareLogMsg


local destinations = setmetatable({
  stdout = "stdout",
  stderr = "stderr",
},
{
  __index = function(self, key)
    if not key then
      return "stdout" -- default value
    end
    error("destination parameter must be either 'stderr' or 'stdout', got: "..tostring(key), 3)
  end
})


local M = setmetatable({}, {
  __call = function(self, ...)
    -- calling on the module instantiates a new logger
    return self.new(...)
  end,
})


function M.new(params, ...)
  params = logging.getDeprecatedParams({ "logPattern" }, params, ...)
  local startLevel = params.logLevel or logging.defaultLevel()
  local timestampPattern = params.timestampPattern or logging.defaultTimestampPattern()
  local destination = destinations[params.destination]
  local logPatterns = logging.buildLogPatterns(params.logPatterns, params.logPattern)

  return logging.new( function(self, level, message)
    io[destination]:write(prepareLogMsg(logPatterns[level], logging.date(timestampPattern), level, message))
    return true
  end, startLevel)
end


logging.console = M
return M

