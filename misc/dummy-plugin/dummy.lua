local class = require "middleclass"
local plugin = require "bunkerweb.plugin"

local dummy = class("dummy", plugin)

function dummy:initialize()
	plugin.initialize(self, "dummy")
	self.dummy = "dummy"
end

function dummy:init()
	self.logger:log(ngx.NOTICE, "init called")
	return self:ret(true, "success")
end

function dummy:set()
	self.logger:log(ngx.NOTICE, "set called")
	return self:ret(true, "success")
end

function dummy:access()
	self.logger:log(ngx.NOTICE, "access called")
	return self:ret(true, "success")
end

function dummy:log()
	self.logger:log(ngx.NOTICE, "log called")
	return self:ret(true, "success")
end

function dummy:log_default()
	self.logger:log(ngx.NOTICE, "log_default called")
	return self:ret(true, "success")
end

function dummy:preread()
	self.logger:log(ngx.NOTICE, "preread called")
	return self:ret(true, "success")
end

function dummy:log_stream()
	self.logger:log(ngx.NOTICE, "log_stream called")
	return self:ret(true, "success")
end

return dummy
