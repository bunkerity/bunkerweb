local class = require "middleclass"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"
local ssl = require "ngx.ssl"

local selfsigned = class("selfsigned", plugin)

function selfsigned:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "selfsigned", ctx)
end

function selfsigned:init()
	local ok, err = true, "success"
    if utils.has_variable("GENERATE_SELF_SIGNED_SSL", "yes") then
		local multisite, err = utils.get_variable("MULTISITE")
		if not multisite then
			return self:ret(false, "can't get MULTISITE variable : " .. err)
		end
		if multisite == "yes" then
			local vars, err = utils.get_multiple_variables({"GENERATE_SELF_SIGNED_SSL"})
			if not vars then
				return self:ret(false, "can't get GENERATE_SELF_SIGNED_SSL variables : " .. err)
			end
			for server_name, multisite_vars in pairs(vars) do
				if multisite_vars["GENERATE_SELF_SIGNED_SSL"] == "yes" then
					local check, data = self:read_files(server_name)
					if not check then
						self.logger:log(ngx.ERR, "error while reading files : " .. err)
						ok = false
						err = "error reading files"
					else
						local check, err = self:load_data(data, server_name)
						if not check then
							self.logger:log(ngx.ERR, "error while loading data : " .. err)
							ok = false
							err = "error loading data"
						end
					end
				end
			end
		else
			local server_name, err = utils.get_variable("SERVER_NAME")
			if not server_name then
				return self:ret(false, "can't get SERVER_NAME variable : " .. err)
			end
			local check, data = self:read_files(server_name:gmatch("%S+")[1])
			if not check then
				self.logger:log(ngx.ERR, "error while reading files : " .. err)
				ok = false
				err = "error reading files"
			else
				local check, err = self:load_data(data)
				if not check then
					self.logger:log(ngx.ERR, "error while loading data : " .. err)
					ok = false
					err = "error loading data"
				end
			end
		end
	else
		err = "self signed is not used"
    end
	return self:ret(ok, err)
end

function selfsigned:ssl_certificate()
    if self.variables["GENERATE_SELF_SIGNED_SSL"] == "yes" then
		local data, err = self.datastore:get("plugin_selfsigned_" .. self.ctx.bw.server_name, true)
		if not data then
			return self:ret(false, "error while getting plugin_selfsigned_" .. self.ctx.bw.server_name .. " from datastore : " .. err)
		end
        return self:ret(true, "certificate/key data found", data)
    end
    return self:ret(true, "selfsigned is not used")
end

function selfsigned:read_files(server_name)
	local files = {
		"/var/cache/bunkerweb/selfsigned/" .. server_name .. "/cert.pem",
		"/var/cache/bunkerweb/selfsigned/" .. server_name .. "/key.pem"
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

function selfsigned:load_data(data, server_name)
	-- Load certificate
	local cert_chain, err = ssl.parse_pem_cert(data[1])
	if not cert_chain then
		return false, "error while parsing pem cert : " .. err
	end
	-- Load key
	local priv_key, err = ssl.parse_priv_key(data[2])
	if not priv_key then
		return false, "error while parsing pem priv key : " .. err
	end
	local cache_key = "plugin_selfsigned_" .. (server_name or "global")
	local ok, err = self.datastore:set(cache_key, {cert_chain, priv_key}, nil, true)
	if not ok then
		return false, "error while setting data into datastore : " .. err
	end
	return true
end

return selfsigned
