local class = require "middleclass"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"

local misc = class("misc", plugin)

function misc:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "misc", ctx)
end

function misc:access()
	-- Check if method is valid
	local method = self.ctx.bw.request_method
	if not method or not utils.regex_match(method, "^[A-Z]+$") then
		return self:ret(true, "method is not valid", ngx.HTTP_BAD_REQUEST)
	end
	-- Check if method is allowed
	for allowed_method in self.variables["ALLOWED_METHODS"]:gmatch("[^|]+") do
		if method == allowed_method then
			return self:ret(true, "method " .. method .. " is allowed")
		end
	end
	return self:ret(true, "method " .. method .. " is not allowed", ngx.HTTP_NOT_ALLOWED)
end

return misc
