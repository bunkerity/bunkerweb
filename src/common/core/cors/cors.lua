local class		= require "middleclass"
local plugin	= require "bunkerweb.plugin"
local utils     = require "bunkerweb.utils"

local cors		= class("cors", plugin)

function cors:initialize()
	-- Call parent initialize
	plugin.initialize(self, "cors")
end

function cors:header()
	-- Check if header is needed
	if self.variables["USE_CORS"] ~= "yes" then
		return self:ret(true, "service doesn't use CORS")
	end
	if ngx.var.request_method ~= "OPTIONS" then
		return self:ret(true, "method is not OPTIONS")
	end
	-- Add headers
	local cors_headers = {
		["CORS_MAX_AGE"] = "Access-Control-Max-Age",
		["CORS_ALLOW_METHODS"] = "Access-Control-Allow-Methods",
		["CORS_ALLOW_HEADERS"] = "Access-Control-Allow-Headers"
	}
	for variable, header in pairs(cors_headers) do
		local value = self.variables[variable]
		if value ~= "" then
			ngx.header[header] = value
		end
	end
	ngx.header["Content-Type"] = "text/html"
	ngx.header["Content-Length"] = "0"
	
	-- Send CORS policy with a 204 (no content) status
	return self:ret(true, "sent CORS policy")
end

return cors