local class = require("middleclass")
local plugin = require("bunkerweb.plugin")
local ssl = require("ngx.ssl")
local utils = require("bunkerweb.utils")

local letsencrypt_dns = class("letsencrypt_dns", plugin)

-- luacheck: globals ngx
local ngx = ngx
local ERR = ngx.ERR
local parse_pem_cert = ssl.parse_pem_cert
local parse_pem_priv_key = ssl.parse_pem_priv_key
local ssl_server_name = ssl.server_name
local get_variable = utils.get_variable
local get_multiple_variables = utils.get_multiple_variables
local has_variable = utils.has_variable
local has_not_variable = utils.has_not_variable
local read_files = utils.read_files

function letsencrypt_dns:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "letsencrypt_dns", ctx)
end

function letsencrypt_dns:set()
	local https_configured = self.variables["AUTO_LETS_ENCRYPT_DNS"]
	if https_configured == "yes" then
		self.ctx.bw.https_configured = "yes"
	end
	return self:ret(true, "set https_configured to " .. https_configured)
end

function letsencrypt_dns:init()
	local ret_ok, ret_err = true, "success"
	if has_variable("AUTO_LETS_ENCRYPT_DNS", "yes") and has_not_variable("LETS_ENCRYPT_DNS_PROVIDER", "") then
		local multisite, err = get_variable("MULTISITE", false)
		if not multisite then
			return self:ret(false, "can't get MULTISITE variable : " .. err)
		end
		if multisite == "yes" then
			local vars
			vars, err = get_multiple_variables({
				"AUTO_LETS_ENCRYPT_DNS",
				"LETS_ENCRYPT_DNS_PROVIDER",
				"USE_LETS_ENCRYPT_DNS_WILDCARD",
				"SERVER_NAME",
			})
			if not vars then
				return self:ret(false, "can't get required variables : " .. err)
			end
			local credential_items
			credential_items, err = get_multiple_variables({ "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM" })
			if not credential_items then
				return self:ret(false, "can't get credential items : " .. err)
			end
			for server_name, multisite_vars in pairs(vars) do
				if
					multisite_vars["AUTO_LETS_ENCRYPT_DNS"] == "yes"
					and multisite_vars["LETS_ENCRYPT_DNS_PROVIDER"] ~= ""
					and credential_items[server_name]
					and server_name ~= "global"
				then
					local data
					if multisite_vars["USE_LETS_ENCRYPT_DNS_WILDCARD"] == "yes" then
						local parts = {}
						for part in server_name:gmatch("[^.]+") do
							table.insert(parts, part)
						end
						server_name = table.concat(parts, ".", 2)
						data = self.datastore:get("plugin_letsencrypt_dns_" .. server_name, true)
					end
					if not data then
						-- Load certificate
						local check
						check, data = read_files({
							"/var/cache/bunkerweb/letsencrypt_dns/etc/live/" .. server_name .. "/fullchain.pem",
							"/var/cache/bunkerweb/letsencrypt_dns/etc/live/" .. server_name .. "/privkey.pem",
						})
						if not check then
							self.logger:log(ERR, "error while reading files : " .. data)
							ret_ok = false
							ret_err = "error reading files"
						else
							if multisite_vars["USE_LETS_ENCRYPT_DNS_WILDCARD"] == "yes" then
								check, err = self:load_data(data, server_name)
							else
								check, err = self:load_data(data, multisite_vars["SERVER_NAME"])
							end
							if not check then
								self.logger:log(ERR, "error while loading data : " .. err)
								ret_ok = false
								ret_err = "error loading data"
							end
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
			local use_wildcard
			use_wildcard, err = get_variable("USE_LETS_ENCRYPT_DNS_WILDCARD", false)
			if not use_wildcard then
				return self:ret(false, "can't get USE_LETS_ENCRYPT_DNS_WILDCARD variable : " .. err)
			end
			server_name = server_name:match("%S+")
			if use_wildcard == "yes" then
				local parts = {}
				for part in server_name:gmatch("[^.]+") do
					table.insert(parts, part)
				end
				server_name = table.concat(parts, ".", 2)
			end
			local check, data = read_files({
				"/var/cache/bunkerweb/letsencrypt_dns/etc/live/" .. server_name .. "/fullchain.pem",
				"/var/cache/bunkerweb/letsencrypt_dns/etc/live/" .. server_name .. "/privkey.pem",
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
		ret_err = "let's encrypt dns is not used"
	end
	return self:ret(ret_ok, ret_err)
end

function letsencrypt_dns:ssl_certificate()
	local server_name, err = ssl_server_name()
	if not server_name then
		return self:ret(false, "can't get server_name : " .. err)
	end
	local use_wildcard
	use_wildcard, err = get_variable("USE_LETS_ENCRYPT_DNS_WILDCARD", false)
	if not use_wildcard then
		return self:ret(false, "can't get USE_LETS_ENCRYPT_DNS_WILDCARD variable : " .. err)
	end
	if use_wildcard == "yes" then
		local parts = {}
		for part in server_name:gmatch("[^.]+") do
			table.insert(parts, part)
		end
		server_name = table.concat(parts, ".", 2)
	end
	local data
	data, err = self.datastore:get("plugin_letsencrypt_dns_" .. server_name, true)
	if not data and err ~= "not found" then
		return self:ret(
			false,
			"error while getting plugin_letsencrypt_dns_" .. server_name .. " from datastore : " .. err
		)
	elseif data then
		return self:ret(true, "certificate/key data found", data)
	end
	return self:ret(true, "let's encrypt dns is not used")
end

function letsencrypt_dns:load_data(data, server_name)
	-- Load certificate
	local cert_chain, err = parse_pem_cert(data[1])
	if not cert_chain then
		return false, "error while parsing pem cert : " .. err
	end
	-- Load key
	local priv_key
	priv_key, err = parse_pem_priv_key(data[2])
	if not priv_key then
		return false, "error while parsing pem priv key : " .. err
	end
	-- Cache data
	for key in server_name:gmatch("%S+") do
		local cache_key = "plugin_letsencrypt_dns_" .. key
		local ok
		ok, err = self.datastore:set(cache_key, { cert_chain, priv_key }, nil, true)
		if not ok then
			return false, "error while setting data into datastore : " .. err
		end
	end
	return true
end

return letsencrypt_dns
