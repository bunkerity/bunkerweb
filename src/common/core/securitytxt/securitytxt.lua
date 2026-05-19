local class = require "middleclass"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"

local ngx = ngx
local ERR = ngx.ERR
local OK = ngx.OK
local get_phase = ngx.get_phase
local subsystem = ngx.config.subsystem
local get_multiple_variables = utils.get_multiple_variables

local template
local render = nil
if subsystem == "http" then
	template = require "resty.template"
	render = template.render
end

local securitytxt = class("securitytxt", plugin)

-- Helper function to convert HTTP URLs to HTTPS
local function convert_http_to_https(urls)
	if type(urls) == "table" then
		local result = {}
		for i, url in ipairs(urls) do
			result[i] = string.gsub(url, "^http://", "https://")
		end
		return result
	elseif type(urls) == "string" then
		return string.gsub(urls, "^http://", "https://")
	end
	return urls
end

function securitytxt:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "securitytxt", ctx)
	-- Load data from internalstore if needed
	if get_phase() ~= "init" and self.ctx.bw.uri == self.variables["SECURITYTXT_URI"] then
		-- Get security policies from internalstore
		local security_policies, err = self.internalstore:get("plugin_securitytxt_security_policies", true)
		if not security_policies then
			self.logger:log(ERR, err)
			return
		end
		self.security_policies = {
			["uri"] = "",
			["acknowledgements"] = {},
			["canonical"] = {},
			["contact"] = {},
			["encryption"] = {},
			["expires"] = "",
			["hiring"] = {},
			["policy"] = {},
			["preferred_lang"] = "",
			["csaf"] = {},
		}
		-- Extract global security policies
		if security_policies.global then
			for k, v in pairs(security_policies.global) do
				self.security_policies[k] = v
			end
		end
		-- Extract and overwrite if needed server security policies
		if security_policies[self.ctx.bw.server_name] then
			for k, v in pairs(security_policies[self.ctx.bw.server_name]) do
				self.security_policies[k] = v
			end
		end
	end
end

function securitytxt:init()
	-- Get variables
	local variables, err = get_multiple_variables({
		"SECURITYTXT_URI",
		"SECURITYTXT_ACKNOWLEDGEMENTS",
		"SECURITYTXT_CANONICAL",
		"SECURITYTXT_CONTACT",
		"SECURITYTXT_ENCRYPTION",
		"SECURITYTXT_EXPIRES",
		"SECURITYTXT_HIRING",
		"SECURITYTXT_POLICY",
		"SECURITYTXT_PREFERRED_LANG",
		"SECURITYTXT_CSAF",
	})
	if variables == nil then
		return self:ret(false, err)
	end
	-- Store security policies name and value
	local data = {}
	local key
	for srv, vars in pairs(variables) do
		if data[srv] == nil then
			data[srv] = {
				["uri"] = "",
				["acknowledgements"] = {},
				["canonical"] = {},
				["contact"] = {},
				["encryption"] = {},
				["expires"] = "",
				["hiring"] = {},
				["policy"] = {},
				["preferred_lang"] = "",
				["csaf"] = {},
			}
		end
		for var, value in pairs(vars) do
			if value ~= "" then
				key = string.lower(string.gsub(string.gsub(var, "^SECURITYTXT_", ""), "_%d+$", ""))
				if key == "uri" or key == "expires" or key == "preferred_lang" then
					data[srv][key] = value
				else
					data[srv][key][#data[srv][key] + 1] = value
				end
			end
		end
	end
	local ok
	ok, err = self.internalstore:set("plugin_securitytxt_security_policies", data, nil, true)
	if not ok then
		return self:ret(false, err)
	end
	return self:ret(true, "successfully loaded security policies")
end

function securitytxt:access()
	if self.ctx.bw.uri ~= self.variables["SECURITYTXT_URI"] and self.ctx.bw.uri ~= "/security.txt" then
		return self:ret(true, "success")
	end
	return self:ret(true, "security.txt requested", OK)
end

function securitytxt:content()
	-- Check if content is needed
	if self.variables["USE_SECURITYTXT"] == "no" then
		return self:ret(true, "securitytxt not activated")
	end

	-- Check if display content is needed
	if self.ctx.bw.uri ~= self.variables["SECURITYTXT_URI"] then
		return self:ret(true, "securitytxt not requested")
	end

	-- Check if a contact key is set
	if self.security_policies["contact"] == nil or #self.security_policies["contact"] == 0 then
		return self:ret(false, "no contact key set")
	end

	local data = {
		server_name = self.ctx.bw.server_name,
	}

	for k, v in pairs(self.security_policies) do
		-- Convert HTTP URLs to HTTPS for URL fields
		if k == "canonical" or k == "contact" or k == "encryption" or k == "hiring" or k == "policy" or k == "csaf" then
			data[k] = convert_http_to_https(v)
		else
			data[k] = v
		end
	end

	-- If expires isn't set, reuse a cached auto-generated value so the file stays stable across requests.
	-- Regenerate 30 days before expiry so the cached value always remains RFC 9116 §2.5.5 compliant.
	if data["expires"] == "" then
		local cache_key = "plugin_securitytxt_auto_expires_" .. (self.ctx.bw.server_name or "")
		local cached = self.internalstore:get(cache_key)
		if cached and cached ~= "" then
			data["expires"] = cached
		else
			data["expires"] = os.date("!%Y-%m-%dT%H:%M:%SZ", os.time() + 31536000)
			local ok, err = self.internalstore:set(cache_key, data["expires"], 31536000 - 30 * 86400)
			if not ok then
				self.logger:log(ERR, "failed to cache auto-generated expires: " .. (err or "unknown"))
			end
		end
	end

	-- Render content
	render("security.txt", data)
	return self:ret(true, "content displayed")
end

return securitytxt
