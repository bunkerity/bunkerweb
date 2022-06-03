local dummy = {}

local logger = require "logger"

dummy.init = function(self)
	logger.log(ngx.NOTICE, "DUMMY", "init() called")
	return true, "success"
end

dummy.access = function(self)
	logger.log(ngx.NOTICE, "DUMMY", "access() called")
	return true, "success", false, nil
end

dummy.log = function(self)
	logger.log(ngx.NOTICE, "DUMMY", "log() called")
	return true, "success"
end

return dummy
