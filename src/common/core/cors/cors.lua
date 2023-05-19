local class  = require "middleclass"
local plugin = require "bunkerweb.plugin"
local utils  = require "bunkerweb.utils"

local cors   = class("cors", plugin)

function cors:initialize()
	-- Call parent initialize
	plugin.initialize(self, "cors")
	self.all_headers = {
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
	-- Skip if Origin header is not present
	if not ngx.ctx.bw.http_origin then
		return self:ret(true, "origin header not present")
	end
	-- Always include Vary header to prevent caching
	local vary = ngx.header.Vary
	if vary then
		if type(vary) == "string" then
			ngx.header.Vary = { vary, "Origin" }
		else
			table.insert(vary, "Origin")
			ngx.header.Vary = vary
		end
	else
		ngx.header.Vary = "Origin"
	end
	-- Check if Origin is allowed
	if ngx.ctx.bw.http_origin and self.variables["CORS_DENY_REQUEST"] == "yes" and self.variables["CORS_ALLOW_ORIGIN"] ~= "*" and not utils.regex_match(ngx.ctx.bw.http_origin, self.variables["CORS_ALLOW_ORIGIN"]) then
		self.logger:log(ngx.WARN, "origin " .. ngx.ctx.bw.http_origin .. " is not allowed")
		return self:ret(true, "origin " .. ngx.ctx.bw.http_origin .. " is not allowed")
	end
	-- Set headers
	if self.variables["CORS_ALLOW_ORIGIN"] == "*" then
		ngx.header["Access-Control-Allow-Origin"] = "*"
	else
		ngx.header["Access-Control-Allow-Origin"] = ngx.ctx.bw.http_origin
	end
	for variable, header in pairs(self.all_headers) do
		if self.variables[variable] ~= "" then
			ngx.header[header] = self.variables[variable]
		end
	end
	if ngx.ctx.bw.request_method == "OPTIONS" then
		for variable, header in pairs(self.preflight_headers) do
			if variable == "CORS_ALLOW_CREDENTIALS" then
				if self.variables["CORS_ALLOW_CREDENTIALS"] == "yes" then
					ngx.header[header] = "true"
				end
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
	-- Deny as soon as possible if needed
	if ngx.ctx.bw.http_origin and self.variables["CORS_DENY_REQUEST"] == "yes" and self.variables["CORS_ALLOW_ORIGIN"] ~= "*" and not utils.regex_match(ngx.ctx.bw.http_origin, self.variables["CORS_ALLOW_ORIGIN"]) then
		return self:ret(true, "origin " .. ngx.ctx.bw.http_origin .. " is not allowed, denying access", utils.get_deny_status())
	end
	-- Send CORS policy with a 204 (no content) status
	if ngx.ctx.bw.request_method == "OPTIONS" and ngx.ctx.bw.http_origin then
		return self:ret(true, "preflight request", ngx.HTTP_NO_CONTENT)
	end
	return self:ret(true, "standard request")
end

return cors
