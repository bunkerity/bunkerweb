-------------------------------------------------------------------------------
-- Prints logging information to console
--
-- @author Thiago Costa Ponte (thiago@ideais.com.br)
--
-- @copyright 2004-2021 Kepler Project
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

function logging.console(params, ...)
  params = logging.getDeprecatedParams({ "logPattern" }, params, ...)
  local startLevel = params.logLevel or logging.defaultLevel()
  local timestampPattern = params.timestampPattern or logging.defaultTimestampPattern()
  local destination = destinations[params.destination]
  local logPatterns = logging.buildLogPatterns(params.logPatterns, params.logPattern)

  return logging.new( function(self, level, message)
    io[destination]:write(prepareLogMsg(logPatterns[level], os.date(timestampPattern), level, message))
    return true
  end, startLevel)
end

return logging.console

