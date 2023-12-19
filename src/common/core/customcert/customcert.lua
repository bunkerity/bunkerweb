local class = require "middleclass"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"
local ssl = require "ngx.ssl"

local customcert = class("customcert", plugin)

function customcert:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "customcert", ctx)
end

function customcert:init()
	local ret_ok, ret_err = true, "success"
    if utils.has_variable("USE_CUSTOM_SSL", "yes") then
		local multisite, err = utils.get_variable("MULTISITE", false)
		if not multisite then
			return self:ret(false, "can't get MULTISITE variable : " .. err)
		end
		if multisite == "yes" then
			local vars, err = utils.get_multiple_variables({"USE_CUSTOM_SSL"})
			if not vars then
				return self:ret(false, "can't get USE_CUSTOM_SSL variables : " .. err)
			end
			if vars["global"]["USE_CUSTOM_SSL"] == "yes" then
				local check, data = self:read_files()
				if not check then
					self.logger:log(ngx.ERR, "error while reading files : " .. err)
					ret_ok = false
					ret_err = "error reading files"
				else
					local check, err = self:load_data(data)
					if not check then
						self.logger:log(ngx.ERR, "error while loading data : " .. err)
						ret_ok = false
						ret_err = "error loading data"
					end
				end
			end
			for server_name, multisite_vars in pairs(vars) do
				if multisite_vars["USE_CUSTOM_SSL"] == "yes" then
					local check, data = self:read_files(server_name)
					if not check then
						self.logger:log(ngx.ERR, "error while reading files : " .. data)
						ret_ok = false
						ret_err = "error reading files"
					else
						local check, err = self:load_data(data, server_name)
						if not check then
							self.logger:log(ngx.ERR, "error while loading data : " .. err)
							ret_ok = false
							ret_err = "error loading data"
						end
					end
				end
			end
		else
			local check, data = self:read_files()
			if not check then
				self.logger:log(ngx.ERR, "error while reading files : " .. data)
				ret_ok = false
				ret_err = "error reading files"
			else
				local check, err = self:load_data(data)
				if not check then
					self.logger:log(ngx.ERR, "error while loading data : " .. err)
					ret_ok = false
					ret_err = "error loading data"
				end
			end
		end
	else
		ret_err = "custom ssl is not used"
    end
	return self:ret(ret_ok, ret_err)
end

function customcert:ssl_certificate()
	local server_name, err = ssl.server_name()
	if not server_name then
		return self:ret(false, "can't get server_name : " .. err)
	end
    if self.variables["USE_CUSTOM_SSL"] == "yes" then
		local global_data, err = self.datastore:get("plugin_customcert_global", true)
		if not global_data and err ~= "not found" then
			return self:ret(false, "error while getting plugin_customcert_global from datastore : " .. err)
		end
		local site_data, err = self.datastore:get("plugin_customcert_" .. server_name, true)
		if not site_data and err ~= "not found" then
			return self:ret(false, "error while getting plugin_customcert_" .. server_name .. " from datastore : " .. err)
		end
		if not global_data and not site_data then
			return self:ret(false, "both global and site cert are not present in datastore")
		end
        return self:ret(true, "certificate/key data found", site_data or global_data)
    end
    return self:ret(true, "custom certificate is not used")
end

function customcert:read_files(server_name)
	local files = {
		"/var/cache/bunkerweb/customcert/" .. (server_name or "") .. "/cert.pem",
		"/var/cache/bunkerweb/customcert/" .. (server_name or "") .. "/key.pem"
	}
	local data = {}
	for i, file in ipairs(files) do
		local f, err = io.open(file, "r")
		if not f then
			return false, file .. " = " .. err
		end
		table.insert(data, f:read("*a"))
		f:close()
	end
	return true, data
end

function customcert:load_data(data, server_name)
	-- Load certificate
	local cert_chain, err = ssl.parse_pem_cert(data[1])
	if not cert_chain then
		return false, "error while parsing pem cert : " .. err
	end
	-- Load key
	local priv_key, err = ssl.parse_pem_priv_key(data[2])
	if not priv_key then
		return false, "error while parsing pem priv key : " .. err
	end
	local cache_key = "plugin_customcert_" .. (server_name or "global")
	local ok, err = self.datastore:set(cache_key, {cert_chain, priv_key}, nil, true)
	if not ok then
		return false, "error while setting data into datastore : " .. err
	end
	return true
end

return customcert