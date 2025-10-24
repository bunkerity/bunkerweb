local class = require "middleclass"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"

local headers = class("headers", plugin)

local ngx = ngx
local ERR = ngx.ERR
local get_phase = ngx.get_phase
local regex_match = utils.regex_match
local get_multiple_variables = utils.get_multiple_variables
local tostring = tostring

function headers:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "headers", ctx)
	self.all_headers = {
		["STRICT_TRANSPORT_SECURITY"] = "Strict-Transport-Security",
		["CONTENT_SECURITY_POLICY"] = "Content-Security-Policy",
		["REFERRER_POLICY"] = "Referrer-Policy",
		["PERMISSIONS_POLICY"] = "Permissions-Policy",
		["X_FRAME_OPTIONS"] = "X-Frame-Options",
		["X_CONTENT_TYPE_OPTIONS"] = "X-Content-Type-Options",
		["X_DNS_PREFETCH_CONTROL"] = "X-DNS-Prefetch-Control",
	}
	-- Load data from internalstore if needed
	if get_phase() ~= "init" then
		-- Get custom headers from internalstore
		local custom_headers, err = self.internalstore:get("plugin_headers_custom_headers", true)
		if not custom_headers then
			self.logger:log(ERR, err)
			return
		end
		self.custom_headers = {}
		-- Extract global headers
		if custom_headers.global then
			for k, v in pairs(custom_headers.global) do
				self.custom_headers[k] = v
			end
		end
		-- Extract and overwrite if needed server headers
		if custom_headers[self.ctx.bw.server_name] then
			for k, v in pairs(custom_headers[self.ctx.bw.server_name]) do
				self.custom_headers[k] = v
			end
		end
	end
end

function headers:init()
	-- Get variables
	local variables, err = get_multiple_variables({ "CUSTOM_HEADER" })
	if variables == nil then
		return self:ret(false, err)
	end
	-- Store custom headers name and value
	local data = {}
	local i = 0
	for srv, vars in pairs(variables) do
		for _, value in pairs(vars) do
			if data[srv] == nil then
				data[srv] = {}
			end
			local m = regex_match(value, "([\\w-]+): (.+)")
			if m then
				data[srv][m[1]] = m[2]
			end
			i = i + 1
		end
	end
	local ok
	ok, err = self.internalstore:set("plugin_headers_custom_headers", data, nil, true)
	if not ok then
		return self:ret(false, err)
	end
	return self:ret(true, "successfully loaded " .. tostring(i) .. " custom headers")
end

function headers:header()
	-- Override upstream headers if needed
	local ngx_header = ngx.header
	local ssl = self.ctx.bw.scheme == "https"
	for variable, header in pairs(self.all_headers) do
		-- Check if upstream header exists and should be kept
		local should_keep = self.variables["KEEP_UPSTREAM_HEADERS"] == "*"
			or regex_match(self.variables["KEEP_UPSTREAM_HEADERS"], "(^| )" .. header .. "($| )") ~= nil

		-- Only modify header if it shouldn't be kept or doesn't exist upstream
		if not (ngx_header[header] ~= nil and should_keep) then
			if self.variables[variable] == "" then
				-- Remove header if value is empty
				ngx_header[header] = nil
			else
				if header ~= "Strict-Transport-Security" or ssl then
					if
						header == "Content-Security-Policy"
						and self.variables["CONTENT_SECURITY_POLICY_REPORT_ONLY"] == "yes"
					then
						ngx_header["Content-Security-Policy"] = nil
						ngx_header["Content-Security-Policy-Report-Only"] = self.variables[variable]
					else
						ngx_header[header] = self.variables[variable]
					end
				end
			end
		end
	end
	-- Add custom headers
	for header, value in pairs(self.custom_headers) do
		if value == "" then
			ngx_header[header] = nil
		else
			ngx_header[header] = value
		end
	end
	-- Remove headers
	if self.variables["REMOVE_HEADERS"] ~= "" then
		for header in self.variables["REMOVE_HEADERS"]:gmatch("%S+") do
			ngx_header[header] = nil
		end
	end
	-- Set secure flag
	local set_cookie = ngx_header["Set-Cookie"]
	if self.ctx.bw.scheme == "https" and self.variables["COOKIE_AUTO_SECURE_FLAG"] == "yes" and set_cookie ~= nil then
		local new_set_cookie = nil
		if type(set_cookie) == "string" then
			new_set_cookie = set_cookie
			if not set_cookie:find("[Ss]ecure") then
				new_set_cookie = new_set_cookie .. "; Secure"
			end
		elseif type(set_cookie) == "table" then
			new_set_cookie = {}
			for _, single_set_cookie in ipairs(set_cookie) do
				local check_set_cookie = single_set_cookie
				if not check_set_cookie:find("[Ss]ecure") then
					check_set_cookie = check_set_cookie .. "; Secure"
				end
				table.insert(new_set_cookie, check_set_cookie)
			end
		end
		ngx_header["Set-Cookie"] = new_set_cookie
	end
	return self:ret(true, "edited headers for request")
end

return headers
