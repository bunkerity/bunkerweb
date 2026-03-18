local class = require "middleclass"
local plugin = require "bunkerweb.plugin"
local ssl = require "ngx.ssl"
local utils = require "bunkerweb.utils"

local customcert = class("customcert", plugin)

local ngx = ngx
local ERR = ngx.ERR
local parse_pem_cert = ssl.parse_pem_cert
local parse_pem_priv_key = ssl.parse_pem_priv_key
local ssl_server_name = ssl.server_name
local get_variable = utils.get_variable
local get_multiple_variables = utils.get_multiple_variables
local has_variable = utils.has_variable
local read_files = utils.read_files

function customcert:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "customcert", ctx)
end

function customcert:set()
	local https_configured = self.variables["USE_CUSTOM_SSL"]
	if https_configured == "yes" then
		self.ctx.bw.https_configured = "yes"
	end
	return self:ret(true, "set https_configured to " .. https_configured)
end

function customcert:init()
	local ret_ok, ret_err = true, "success"
	if has_variable("USE_CUSTOM_SSL", "yes") then
		local multisite, err = get_variable("MULTISITE", false)
		if not multisite then
			return self:ret(false, "can't get MULTISITE variable : " .. err)
		end
		if multisite == "yes" then
			local vars
			vars, err = get_multiple_variables({ "USE_CUSTOM_SSL", "SERVER_NAME" })
			if not vars then
				return self:ret(false, "can't get USE_CUSTOM_SSL variables : " .. err)
			end
			for server_name, multisite_vars in pairs(vars) do
				if multisite_vars["USE_CUSTOM_SSL"] == "yes" and server_name ~= "global" then
					local check, data = read_files({
						"/var/cache/bunkerweb/customcert/" .. server_name .. "/cert.pem",
						"/var/cache/bunkerweb/customcert/" .. server_name .. "/key.pem",
					})
					if not check then
						self.logger:log(ERR, "error while reading files : " .. data)
						ret_ok = false
						ret_err = "error reading files"
					else
						check, err = self:load_data(data, multisite_vars["SERVER_NAME"])
						if not check then
							self.logger:log(ERR, "error while loading data : " .. err)
							ret_ok = false
							ret_err = "error loading data"
						end
					end
				end
			end
		else
			local server_name
			server_name, err = get_variable("SERVER_NAME", false)
			if not server_name then
				return self:ret(false, "can't get SERVER_NAME variable : " .. err)
			end
			local check, data = read_files({
				"/var/cache/bunkerweb/customcert/" .. server_name:match("%S+") .. "/cert.pem",
				"/var/cache/bunkerweb/customcert/" .. server_name:match("%S+") .. "/key.pem",
			})
			if not check then
				self.logger:log(ERR, "error while reading files : " .. data)
				ret_ok = false
				ret_err = "error reading files"
			else
				check, err = self:load_data(data, server_name)
				if not check then
					self.logger:log(ERR, "error while loading data : " .. err)
					ret_ok = false
					ret_err = "error loading data"
				end
			end
		end
	else
		ret_err = "custom cert is not used"
	end
	return self:ret(ret_ok, ret_err)
end

function customcert:ssl_certificate()
	local server_name, err = ssl_server_name()
	if not server_name then
		return self:ret(false, "can't get server_name : " .. err)
	end
	local data
	data, err = self.internalstore:get("plugin_customcert_" .. server_name, true)
	if not data and err ~= "not found" then
		return self:ret(
			false,
			"error while getting plugin_customcert_" .. server_name .. " from internalstore : " .. err
		)
	elseif data then
		return self:ret(true, "certificate/key data found", data)
	end
	return self:ret(true, "custom certificate is not used")
end

function customcert:load_data(data, server_name)
	-- Load certificate
	local cert_chain, err = parse_pem_cert(data[1])
	if not cert_chain then
		return false, "error while parsing pem cert : " .. err
	end
	-- Load key
	local priv_key, err = parse_pem_priv_key(data[2])
	if not priv_key then
		return false, "error while parsing pem priv key : " .. err
	end
	-- Cache data
	for key in server_name:gmatch("%S+") do
		local cache_key = "plugin_customcert_" .. key
		local ok
		ok, err = self.internalstore:set(cache_key, { cert_chain, priv_key }, nil, true)
		if not ok then
			return false, "error while setting data into internalstore : " .. err
		end
	end
	return true
end

return customcert
