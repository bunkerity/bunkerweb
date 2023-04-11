local errlog	= require "ngx.errlog"
local class     = require "middleclass"
local logger	= class("logger")

function logger:new(prefix)
	self.prefix = prefix
end

function logger:log(level, msg)
	errlog.raw_log(level, "[" .. self.prefix .. "] " .. msg) 
end

return logger