-------------------------------------------------------------------------------
-- Forwards logging information to the Nginx log
--
-- @author Thijs Schreijer
--
-- @copyright 2004-2010 Kepler Project, 2011-2013 Neopallium, 2020-2023 Thijs Schreijer
--
-------------------------------------------------------------------------------

local logging = require "logging"
local prepareLogMsg = logging.prepareLogMsg

local ngx_log = assert((ngx or {}).log, "this logger can only be used with OpenResty")


local levels = {
  [logging.FATAL] = ngx.EMERG,
  [logging.ERROR] = ngx.ERR,
  [logging.WARN] = ngx.WARN,
  [logging.INFO] = ngx.INFO,
  [logging.DEBUG] = ngx.DEBUG,
}


local target_level do
  -- set the default lualogging level, based on the detected Nginx level
  local sys_log_level = require("ngx.errlog").get_sys_filter_level()
  for ll_level, ngx_level in pairs(levels) do
    if sys_log_level == ngx_level then
      target_level = ll_level
      ngx_log(ngx.DEBUG, "setting LuaLogging default level '", ll_level, "' to match Nginx level: ", ngx_level)
      break
    end
  end
  assert(target_level, "failed to map ngx log-level '"..tostring(sys_log_level).."' to a LuaLogging level")
end


local M = setmetatable({}, {
  __call = function(self, ...)
    -- calling on the module instantiates a new logger
    return self.new(...)
  end,
})


function M.new(params)
  return logging.new(function(self, level, message)
    return ngx_log(levels[level], prepareLogMsg("%message", "", level, message))
  end, target_level)
end


logging.nginx = M
return M
