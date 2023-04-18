-------------------------------------------------------------------------------
-- Saves logging information in a file
--
-- @author Thiago Costa Ponte (thiago@ideais.com.br)
--
-- @copyright 2004-2010 Kepler Project, 2011-2013 Neopallium, 2020-2023 Thijs Schreijer
--
-------------------------------------------------------------------------------

local logging = require"logging"

local lastFileNameDatePattern
local lastFileHandler


local buffer_mode do
  local dir_separator = _G.package.config:sub(1,1)
  local is_windows = dir_separator == '\\'
  if is_windows then
    -- Windows does not support "line" buffered mode, see
    -- https://github.com/lunarmodules/lualogging/pull/9
    buffer_mode = "no"
  else
    buffer_mode = "line"
  end
end


local openFileLogger = function (filename, datePattern)
  local filename = string.format(filename, logging.date(datePattern))
  if (lastFileNameDatePattern ~= filename) then
    local f = io.open(filename, "a")
    if (f) then
      f:setvbuf(buffer_mode)
      lastFileNameDatePattern = filename
      lastFileHandler = f
      return f
    else
      return nil, string.format("file `%s' could not be opened for writing", filename)
    end
  else
    return lastFileHandler
  end
end


local M = setmetatable({}, {
  __call = function(self, ...)
    -- calling on the module instantiates a new logger
    return self.new(...)
  end,
})


function M.new(params, ...)
  params = logging.getDeprecatedParams({ "filename", "datePattern", "logPattern" }, params, ...)
  local filename = params.filename
  local datePattern = params.datePattern
  local logPatterns = logging.buildLogPatterns(params.logPatterns, params.logPattern)
  local timestampPattern = params.timestampPattern or logging.defaultTimestampPattern()
  local startLevel = params.logLevel or logging.defaultLevel()

  if type(filename) ~= "string" then
    filename = "lualogging.log"
  end

  return logging.new( function(self, level, message)
    local f, msg = openFileLogger(filename, datePattern)
    if not f then
      return nil, msg
    end
    local s = logging.prepareLogMsg(logPatterns[level], logging.date(timestampPattern), level, message)
    f:write(s)
    return true
  end, startLevel)
end


logging.file = M
return M
