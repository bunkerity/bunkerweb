local class = require "middleclass"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"

local cors = class("cors", plugin)

local ngx = ngx
local HTTP_NO_CONTENT = ngx.HTTP_NO_CONTENT
local regex_match = utils.regex_match
local get_deny_status = utils.get_deny_status
local parse_duration = utils.parse_duration
local tostring = tostring
local public_authority = utils.public_authority

function cors:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "cors", ctx)
	self.all_headers = {
		["CORS_EXPOSE_HEADERS"] = "Access-Control-Expose-Headers",
		["CROSS_ORIGIN_OPENER_POLICY"] = "Cross-Origin-Opener-Policy",
		["CROSS_ORIGIN_EMBEDDER_POLICY"] = "Cross-Origin-Embedder-Policy",
		["CROSS_ORIGIN_RESOURCE_POLICY"] = "Cross-Origin-Resource-Policy",
	}
	self.preflight_headers = {
		["CORS_MAX_AGE"] = "Access-Control-Max-Age",
		["CORS_ALLOW_METHODS"] = "Access-Control-Allow-Methods",
		["CORS_ALLOW_HEADERS"] = "Access-Control-Allow-Headers",
	}
end

-- The `self` origin has to be the authority a browser will actually send in `Origin`, port
-- included. It carried none, which is right on a default install (8443 is published as 443) and
-- wrong the moment a service declares ports of its own: the emitted origin then never matches the
-- browser's and CORS silently denies every cross-origin request. public_authority() returns the
-- bare name for every service that did not move, so nothing changes for an existing deployment.
function cors:self_origin()
	local https = self.ctx.bw.https_configured == "yes"
	local authority =
		public_authority(self.ctx.bw.server_name, https and "HTTPS_PORT" or "HTTP_PORT", self.ctx.bw.server_name)
	return (https and "https://" or "http://") .. authority
end

-- One verdict for access() (deny) and header() (Allow-Origin, credentials). `self` compares the
-- origin exactly: SERVER_NAME is a hostname, not a pattern, so a regex match would let a look-alike
-- origin through (example.com matching exampleXcom).
function cors:is_origin_allowed()
	local allow_origin = self.variables["CORS_ALLOW_ORIGIN"]
	if allow_origin == "*" then
		return true
	end
	local origin = self.ctx.bw.http_origin
	if allow_origin == "self" then
		return origin == self:self_origin()
	end
	return regex_match(origin, allow_origin, nil, "CORS_ALLOW_ORIGIN") and true or false
end

function cors:header()
	-- Check if header is needed
	if self.variables["USE_CORS"] ~= "yes" then
		return self:ret(true, "service doesn't use CORS")
	end
	-- Skip if Origin header is not present
	if not self.ctx.bw.http_origin then
		return self:ret(true, "origin header not present")
	end
	-- Always include Vary header to prevent caching
	local ngx_header = ngx.header
	local vary = ngx_header.Vary
	if vary then
		if type(vary) == "string" then
			ngx_header.Vary = { vary, "Origin" }
		else
			table.insert(vary, "Origin")
			ngx_header.Vary = vary
		end
	else
		ngx_header.Vary = "Origin"
	end

	-- Set headers
	local origin_allowed = self:is_origin_allowed()
	if self.variables["CORS_ALLOW_ORIGIN"] == "*" then
		ngx_header["Access-Control-Allow-Origin"] = "*"
	elseif self.variables["CORS_ALLOW_ORIGIN"] == "self" then
		ngx_header["Access-Control-Allow-Origin"] = self:self_origin()
	else
		-- Regex: echo only an origin the pattern allows, and drop any value the upstream sent for the others
		ngx_header["Access-Control-Allow-Origin"] = origin_allowed and self.ctx.bw.http_origin or nil
	end
	for variable, header in pairs(self.all_headers) do
		if self.variables[variable] ~= "" then
			ngx_header[header] = self.variables[variable]
		end
	end
	-- Credentials go to an allowed origin only (preflight and real responses), never with `*`; this
	-- also strips a credentials header the upstream set for any other origin.
	if ngx_header["Access-Control-Allow-Origin"] == "*" or not origin_allowed then
		ngx_header["Access-Control-Allow-Credentials"] = nil
	elseif self.variables["CORS_ALLOW_CREDENTIALS"] == "yes" then
		ngx_header["Access-Control-Allow-Credentials"] = "true"
	end
	if self.ctx.bw.request_method == "OPTIONS" then
		for variable, header in pairs(self.preflight_headers) do
			if self.variables[variable] ~= "" then
				if variable == "CORS_MAX_AGE" then
					-- the header carries seconds, never the suffixed setting value
					local value = parse_duration(self.variables[variable], "s")
					ngx_header[header] = value and tostring(value) or self.variables[variable]
				else
					ngx_header[header] = self.variables[variable]
				end
			end
		end
		ngx_header["Content-Type"] = "text/html; charset=UTF-8"
		ngx_header["Content-Length"] = "0"
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
	if self.ctx.bw.http_origin and self.variables["CORS_DENY_REQUEST"] == "yes" and not self:is_origin_allowed() then
		self:set_metric("counters", "failed_cors", 1)
		return self:ret(
			true,
			"origin " .. self.ctx.bw.http_origin .. " is not allowed, denying access",
			get_deny_status(),
			nil,
			{
				id = "origin",
				origin = self.ctx.bw.http_origin,
			}
		)
	end
	-- Send CORS policy with a 204 (no content) status
	if self.ctx.bw.request_method == "OPTIONS" and self.ctx.bw.http_origin then
		return self:ret(true, "preflight request", HTTP_NO_CONTENT)
	end
	return self:ret(true, "standard request")
end

return cors
