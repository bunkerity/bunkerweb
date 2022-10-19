-------------------------------------------------------------------------------
-- Sends the logging information through a socket using luasocket
--
-- @author Thiago Costa Ponte (thiago@ideais.com.br)
--
-- @copyright 2004-2021 Kepler Project
--
-------------------------------------------------------------------------------

local logging = require"logging"
local socket = require"socket"

function logging.socket(params, ...)
  params = logging.getDeprecatedParams({ "hostname", "port", "logPattern" }, params, ...)
  local hostname = params.hostname
  local port = params.port
  local logPatterns = logging.buildLogPatterns(params.logPatterns, params.logPattern)
  local timestampPattern = params.timestampPattern or logging.defaultTimestampPattern()
  local startLevel = params.logLevel or logging.defaultLevel()

  return logging.new( function(self, level, message)
    local s = logging.prepareLogMsg(logPatterns[level], os.date(timestampPattern), level, message)

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

return logging.socket

