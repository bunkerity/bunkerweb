local class = require "middleclass"
local errlog = require "ngx.errlog"
local logger = class("logger")

local upper = string.upper
local raw_log = errlog.raw_log

function logger:initialize(prefix)
	self.prefix = upper(prefix)
end

function logger:log(level, msg)
	raw_log(level, "[" .. self.prefix .. "] " .. msg)
end

return logger
