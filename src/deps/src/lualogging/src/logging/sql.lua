-------------------------------------------------------------------------------
-- Saves the logging information in a table using luasql
--
-- @author Thiago Costa Ponte (thiago@ideais.com.br)
--
-- @copyright 2004-2010 Kepler Project, 2011-2013 Neopallium, 2020-2023 Thijs Schreijer
--
-------------------------------------------------------------------------------

local logging = require"logging"


local M = setmetatable({}, {
  __call = function(self, ...)
    -- calling on the module instantiates a new logger
    return self.new(...)
  end,
})


function M.new(params)
  params = params or {}
  params.tablename = params.tablename or "LogTable"
  params.logdatefield = params.logdatefield or "LogDate"
  params.loglevelfield = params.loglevelfield or "LogLevel"
  params.logmessagefield = params.logmessagefield or "LogMessage"

  local startLevel = params.logLevel or logging.defaultLevel()

  if params.connectionfactory == nil or type(params.connectionfactory) ~= "function" then
    return nil, "No specified connection factory function"
  end

  local con, err
  if params.keepalive then
    con, err = params.connectionfactory()
  end

  return logging.new( function(self, level, message)
    if (not params.keepalive) or (con == nil) then
      con, err = params.connectionfactory()
      if not con then
        return nil, err
      end
    end

    local logDate = os.date("%Y-%m-%d %H:%M:%S")
    local insert  = string.format("INSERT INTO %s (%s, %s, %s) VALUES ('%s', '%s', '%s')",
      params.tablename, params.logdatefield, params.loglevelfield,
      params.logmessagefield, logDate, level, string.gsub(message, "'", "''"))

    local ret = pcall(con.execute, con, insert)
    if not ret then
      con, err = params.connectionfactory()
      if not con then
        return nil, err
      end
      ret, err = con:execute(insert)
      if not ret then
        return nil, err
      end
    end

    if not params.keepalive then
      con:close()
    end

    return true
  end, startLevel)
end


logging.sql = M
return M

