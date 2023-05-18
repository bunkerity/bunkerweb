local class  = require "middleclass"
local plugin = require "bunkerweb.plugin"
local utils  = require "bunkerweb.utils"

local misc = class("misc", plugin)

function misc:initialize()
	-- Call parent initialize
	plugin.initialize(self, "misc")
end

function misc:set()
    -- Check if method is allowed
    local method = ngx.ctx.bw.request_method
    for allowed_method in self.variables["ALLOWED_METHODS"]:gmatch("[^|]+") do
        if method == allowed_method then
            return self:ret(true, "method " .. method .. " is allowed")
        end
    end
    ngx.ctx.bw.plugin_misc_method_not_allowed = true
    return self:ret(true, "method " .. method .. " not is allowed")
end

function misc:access()
    -- Check if method is allowed
    if ngx.ctx.bw.plugin_misc_method_not_allowed then
        return self:ret(true, "method " .. ngx.ctx.bw.request_method .. " is not allowed", ngx.HTTP_NOT_ALLOWED)
    end
    return self:ret(true, "method " .. ngx.ctx.bw.request_method .. " is allowed")
end

return misc