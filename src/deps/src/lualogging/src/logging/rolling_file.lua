---------------------------------------------------------------------------
-- RollingFileAppender is a FileAppender that rolls over the logfile
-- once it has reached a certain size limit. It also mantains a
-- maximum number of log files.
--
-- @author Tiago Cesar Katcipis (tiagokatcipis@gmail.com)
--
-- @copyright 2004-2010 Kepler Project, 2011-2013 Neopallium, 2020-2023 Thijs Schreijer
---------------------------------------------------------------------------

local logging = require"logging"


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


local function openFile(self)
  self.file = io.open(self.filename, "a")
  if not self.file then
    return nil, string.format("file `%s' could not be opened for writing", self.filename)
  end
  self.file:setvbuf(buffer_mode)
  return self.file
end


local rollOver = function (self)
  for i = self.maxIndex - 1, 1, -1 do
    -- files may not exist yet, lets ignore the possible errors.
    os.rename(self.filename.."."..tostring(i), self.filename.."."..tostring(i+1))
  end

  self.file:close()
  self.file = nil

  local _, msg = os.rename(self.filename, self.filename..".".."1")

  if msg then
    return nil, string.format("error %s on log rollover", msg)
  end

  return openFile(self)
end


local openRollingFileLogger = function (self)
  if not self.file then
    return openFile(self)
  end

  local filesize = self.file:seek("end", 0)
  if not filesize then
    self.file:close()
    self.file = nil
    return openFile(self)
  end

  if (filesize < self.maxSize) then
    return self.file
  end

  return rollOver(self)
end


local M = setmetatable({}, {
  __call = function(self, ...)
    -- calling on the module instantiates a new logger
    return self.new(...)
  end,
})


function M.new(params, ...)
  params = logging.getDeprecatedParams({ "filename", "maxFileSize", "maxBackupIndex", "logPattern" }, params, ...)
  local logPatterns = logging.buildLogPatterns(params.logPatterns, params.logPattern)
  local timestampPattern = params.timestampPattern or logging.defaultTimestampPattern()
  local startLevel = params.logLevel or logging.defaultLevel()

  local obj = {
    filename = type(params.filename) == "string" and params.filename or "lualogging.log",
    maxSize  = params.maxFileSize,
    maxIndex = params.maxBackupIndex or 1
  }

  return logging.new( function(self, level, message)
    local f, msg = openRollingFileLogger(obj)
    if not f then
      return nil, msg
    end
    local s = logging.prepareLogMsg(logPatterns[level], logging.date(timestampPattern), level, message)
    f:write(s)
    return true
  end, startLevel)
end


logging.rolling_file = M
return M
