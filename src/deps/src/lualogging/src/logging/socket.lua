-------------------------------------------------------------------------------
-- Sends the logging information through a socket using luasocket
--
-- @author Thiago Costa Ponte (thiago@ideais.com.br)
--
-- @copyright 2004-2010 Kepler Project, 2011-2013 Neopallium, 2020-2023 Thijs Schreijer
--
-------------------------------------------------------------------------------

local logging = require"logging"
local socket = require"socket"


local M = setmetatable({}, {
  __call = function(self, ...)
    -- calling on the module instantiates a new logger
    return self.new(...)
  end,
})


function M.new(params, ...)
  params = logging.getDeprecatedParams({ "hostname", "port", "logPattern" }, params, ...)
  local hostname = params.hostname
  local port = params.port
  local logPatterns = logging.buildLogPatterns(params.logPatterns, params.logPattern)
  local timestampPattern = params.timestampPattern or logging.defaultTimestampPattern()
  local startLevel = params.logLevel or logging.defaultLevel()

  return logging.new( function(self, level, message)
    local s = logging.prepareLogMsg(logPatterns[level], logging.date(timestampPattern), level, message)

    local socket, err = socket.connect(hostname, port)
    if not socket then
      return nil, err
    end

    local cond, err = socket:send(s)
    if not cond then
      return nil, err
    end
    socket:close()

    return true
  end, startLevel)
end


logging.socket = M
return M
