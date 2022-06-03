local M			= {}
local errlog	= require "ngx.errlog"

function M.log (level, prefix, msg)
	errlog.raw_log(level, "[" .. prefix .. "] " .. msg) 
end

return M

