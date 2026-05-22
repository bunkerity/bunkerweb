local class = require "middleclass"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"

local misc = class("misc", plugin)

local ngx = ngx
local HTTP_NOT_ALLOWED = ngx.HTTP_NOT_ALLOWED
local HTTP_BAD_REQUEST = ngx.HTTP_BAD_REQUEST
local HTTP_CLOSE = ngx.HTTP_CLOSE
local get_variable = utils.get_variable
local get_security_mode = utils.get_security_mode
local regex_match = utils.regex_match

function misc:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "misc", ctx)
end

function misc:access()
	-- Check if method is valid
	local method = self.ctx.bw.request_method
	if not method or not regex_match(method, "^[A-Z][A-Z_-]{2,}$") then
		return self:ret(true, "method is not valid", HTTP_BAD_REQUEST)
	end
	-- Check if method is allowed
	for allowed_method in self.variables["ALLOWED_METHODS"]:gmatch("[^|]+") do
		if method == allowed_method then
			return self:ret(true, "method " .. method .. " is allowed")
		end
	end
	self:set_metric("counters", "failed_method", 1)
	local security_mode = get_security_mode(self.ctx)
	if security_mode == "block" then
		return self:ret(true, "method " .. method .. " is not allowed", HTTP_NOT_ALLOWED)
	end
	return self:ret(true, "detected method " .. method .. " not allowed")
end

function misc:header()
	-- Add Location header if needed
	if self.ctx.bw.location_header then
		ngx.header["Location"] = self.ctx.bw.location_header
		return self:ret(true, "edited location header")
	end
	return self:ret(true, "no location header needed")
end

function misc:ssl_client_hello_default()
	local strict_sni, err = get_variable("DISABLE_DEFAULT_SERVER_STRICT_SNI", false)
	if strict_sni == nil then
		return self:ret(false, "can't get DISABLE_DEFAULT_SERVER_STRICT_SNI variable : " .. err)
	end
	if strict_sni ~= "yes" then
		return self:ret(true, "strict SNI disabled")
	end

	local ssl_clt = require "ngx.ssl.clienthello"
	local host, err = ssl_clt.get_client_hello_server_name()
	if not host then
		return self:ret(true, "can't get SNI host, denying access : " .. (err or "no SNI"), HTTP_CLOSE)
	end

	local multisite, err = get_variable("MULTISITE", false)
	if multisite == nil then
		return self:ret(false, "can't get MULTISITE variable : " .. err)
	end

	if multisite == "no" then
		local domains, err = get_variable("SERVER_NAME", false)
		if domains == nil then
			return self:ret(false, "can't get SERVER_NAME variable : " .. err)
		end
		for domain in domains:gmatch("%S+") do
			if host == domain then
				return self:ret(true, "SNI host " .. host .. " is allowed")
			end
		end
	else
		local variables, err = self.internalstore:get("variables", true)
		if not variables then
			return self:ret(false, "can't get variables : " .. err)
		end
		for _, server_vars in pairs(variables) do
			local domains = server_vars["SERVER_NAME"]
			if domains then
				for domain in domains:gmatch("%S+") do
					if host == domain then
						return self:ret(true, "SNI host " .. host .. " is allowed")
					end
				end
			end
		end
	end

	return self:ret(true, "unknown SNI host " .. host .. ", denying access", HTTP_CLOSE)
end

function misc:log_default()
	if self.variables["DISABLE_DEFAULT_SERVER"] == "yes" then
		self:set_metric("counters", "failed_default", 1)
	end
	return self:ret(true, "success")
end

return misc
