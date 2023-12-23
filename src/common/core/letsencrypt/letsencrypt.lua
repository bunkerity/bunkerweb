local cjson = require "cjson"
local class = require "middleclass"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"
local ssl = require "ngx.ssl"

local letsencrypt = class("letsencrypt", plugin)

function letsencrypt:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "letsencrypt", ctx)
end

function letsencrypt:init()
	local ret_ok, ret_err = true, "success"
    if utils.has_variable("AUTO_LETS_ENCRYPT", "yes") then
		local multisite, err = utils.get_variable("MULTISITE", false)
		if not multisite then
			return self:ret(false, "can't get MULTISITE variable : " .. err)
		end
		if multisite == "yes" then
			local vars, err = utils.get_multiple_variables({"AUTO_LETS_ENCRYPT"})
			if not vars then
				return self:ret(false, "can't get AUTO_LETS_ENCRYPT variables : " .. err)
			end
			for server_name, multisite_vars in pairs(vars) do
				if multisite_vars["AUTO_LETS_ENCRYPT"] == "yes" then
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
			local server_name, err = utils.get_variable("SERVER_NAME", false)
			if not server_name then
				return self:ret(false, "can't get SERVER_NAME variable : " .. err)
			end
			local check, data = self:read_files(server_name:match("%S+"))
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
		ret_err = "let's encrypt is not used"
    end
	return self:ret(ret_ok, ret_err)
end

function letsencrypt:ssl_certificate()
	local server_name, err = ssl.server_name()
	if not server_name then
		return self:ret(false, "can't get server_name : " .. err)
	end
    if self.variables["AUTO_LETS_ENCRYPT"] == "yes" then
		local data, err = self.datastore:get("plugin_letsencrypt_" .. server_name, true)
		if not data then
			return self:ret(false, "error while getting plugin_letsencrypt_" .. server_name .. " from datastore : " .. err)
		end
        return self:ret(true, "certificate/key data found", data)
    end
    return self:ret(true, "let's encrypt is not used")
end

function letsencrypt:read_files(server_name)
	local files = {
		"/var/cache/bunkerweb/letsencrypt/etc/live/" .. server_name .. "/fullchain.pem",
		"/var/cache/bunkerweb/letsencrypt/etc/live/" .. server_name .. "/privkey.pem"
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

function letsencrypt:load_data(data, server_name)
	-- Load certificate
	local cert_chain, err = ssl.parse_pem_cert(data[1])
	if not cert_chain then
		return false, "error while parsing pem cert : " .. err
	end
	-- Load key
	local priv_key, err = ssl.pars_pem_priv_key(data[2])
	if not priv_key then
		return false, "error while parsing pem priv key : " .. err
	end
	local cache_key = "plugin_letsencrypt_" .. (server_name or "global")
	local ok, err = self.datastore:set(cache_key, {cert_chain, priv_key}, nil, true)
	if not ok then
		return false, "error while setting data into datastore : " .. err
	end
	return true
end

function letsencrypt:access()
	if string.sub(self.ctx.bw.uri, 1, string.len("/.well-known/acme-challenge/")) == "/.well-known/acme-challenge/" then
		self.logger:log(ngx.NOTICE, "got a visit from Let's Encrypt, let's whitelist it")
		return self:ret(true, "visit from LE", ngx.OK)
	end
	return self:ret(true, "success")
end

-- luacheck: ignore 212
function letsencrypt:api(ctx)
	if
		not string.match(ctx.bw.uri, "^/lets%-encrypt/challenge$")
		or (ctx.bw.request_method ~= "POST" and ctx.bw.request_method ~= "DELETE")
	then
		return false, nil, nil
	end
	local acme_folder = "/var/tmp/bunkerweb/lets-encrypt/.well-known/acme-challenge/"
	ngx.req.read_body()
	local ret, data = pcall(cjson.decode, ngx.req.get_body_data())
	if not ret then
		return true, ngx.HTTP_BAD_REQUEST, { status = "error", msg = "json body decoding failed" }
	end
	os.execute("mkdir -p " .. acme_folder)
	if ctx.bw.request_method == "POST" then
		local file, err = io.open(acme_folder .. data.token, "w+")
		if not file then
			return true,
				ngx.HTTP_INTERNAL_SERVER_ERROR,
				{ status = "error", msg = "can't write validation token : " .. err }
		end
		file:write(data.validation)
		file:close()
		return true, ngx.HTTP_OK, { status = "success", msg = "validation token written" }
	elseif ctx.bw.request_method == "DELETE" then
		local ok, err = os.remove(acme_folder .. data.token)
		if not ok then
			return true,
				ngx.HTTP_INTERNAL_SERVER_ERROR,
				{ status = "error", msg = "can't remove validation token : " .. err }
		end
		return true, ngx.HTTP_OK, { status = "success", msg = "validation token removed" }
	end
	return true, ngx.HTTP_NOT_FOUND, { status = "error", msg = "unknown request" }
end

return letsencrypt
