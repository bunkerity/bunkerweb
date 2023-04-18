local errlog	= require "ngx.errlog"
local class     = require "middleclass"
local logger	= class("logger")

function logger:initialize(prefix)
	self.prefix = string.upper(prefix)
end

function logger:log(level, msg)
	errlog.raw_log(level, "[" .. self.prefix .. "] " .. msg) 
end

return logger