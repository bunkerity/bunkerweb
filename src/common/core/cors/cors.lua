local class  = require "middleclass"
local plugin = require "bunkerweb.plugin"
local utils  = require "bunkerweb.utils"

local cors   = class("cors", plugin)

function cors:initialize()
	-- Call parent initialize
	plugin.initialize(self, "cors")
	self.all_headers = {
		["CORS_ALLOW_ORIGIN"] = "Access-Control-Allow-Origin",
		["CORS_EXPOSE_HEADERS"] = "Access-Control-Expose-Headers"
	}
	self.preflight_headers = {
		["CORS_MAX_AGE"] = "Access-Control-Max-Age",
		["CORS_ALLOW_CREDENTIALS"] = "Access-Control-Allow-Credentials",
		["CORS_ALLOW_METHODS"] = "Access-Control-Allow-Methods",
		["CORS_ALLOW_HEADERS"] = "Access-Control-Allow-Headers"
	}
end

function cors:header()
	-- Check if header is needed
	if self.variables["USE_CORS"] ~= "yes" then
		return self:ret(true, "service doesn't use CORS")
	end
	-- Standard headers
	for variable, header in pairs(self.all_headers) do
		if self.variables[variable] ~= "" then
			ngx.header[header] = self.variables[variable]
		end
	end
	-- Preflight request
	if ngx.ctx.bw.request_method == "OPTIONS" then
		for variable, header in pairs(self.preflight_headers) do
			if variable == "CORS_ALLOW_CREDENTIALS" and self.variables["CORS_ALLOW_CREDENTIALS"] == "yes" then
				ngx.header[header] = "true"
			elseif self.variables[variable] ~= "" then
				ngx.header[header] = self.variables[variable]
			end
		end
		ngx.header["Content-Type"] = "text/html"
		ngx.header["Content-Length"] = "0"
		return self:ret(true, "edited headers for preflight request")
	end
	return self:ret(true, "edited headers for standard request")
end

function cors:access()
	-- Check if access is needed
	if self.variables["USE_CORS"] ~= "yes" then
		return self:ret(true, "service doesn't use CORS")
	end
	-- Send CORS policy with a 204 (no content) status
	if ngx.ctx.bw.request_method == "OPTIONS" then
		return self:ret(true, "preflight request", ngx.HTTP_NO_CONTENT)
	end
	return self:ret(true, "standard request")
end

return cors
