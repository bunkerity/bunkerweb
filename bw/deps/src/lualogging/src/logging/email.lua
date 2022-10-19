-------------------------------------------------------------------------------
-- Emails logging information to the given recipient
--
-- @author Thiago Costa Ponte (thiago@ideais.com.br)
--
-- @copyright 2004-2021 Kepler Project
--
-------------------------------------------------------------------------------

local logging = require"logging"
local smtp = require"socket.smtp"

function logging.email(params)
  params = params or {}
  params.headers = params.headers or {}

  if params.from == nil then
    return nil, "'from' parameter is required"
  end
  if params.rcpt == nil then
    return nil, "'rcpt' parameter is required"
  end

  local timestampPattern = params.timestampPattern or logging.defaultTimestampPattern()
  local logPatterns = logging.buildLogPatterns(params.logPatterns, params.logPattern)
  local startLevel = params.logLevel or logging.defaultLevel()

  return logging.new( function(self, level, message)
    local dt = os.date(timestampPattern)
    local s = logging.prepareLogMsg(logPatterns[level], dt, level, message)
    if params.headers.subject then
      params.headers.subject =
        logging.prepareLogMsg(params.headers.subject, dt, level, message)
    end
    local msg = { headers = params.headers, body = s }
    params.source = smtp.message(msg)

    local r, e = smtp.send(params)
    if not r then
      return nil, e
    end

    return true
  end, startLevel)
end

return logging.email

