local cjson = require "cjson"
local class = require "middleclass"
local plugin = require "bunkerweb.plugin"
local ssl = require "ngx.ssl"
local utils = require "bunkerweb.utils"

local letsencrypt = class("letsencrypt", plugin)

local ngx = ngx
local ERR = ngx.ERR
local NOTICE = ngx.NOTICE
local OK = ngx.OK
local HTTP_NOT_FOUND = ngx.HTTP_NOT_FOUND
local HTTP_OK = ngx.HTTP_OK
local HTTP_BAD_REQUEST = ngx.HTTP_BAD_REQUEST
local HTTP_INTERNAL_SERVER_ERROR = ngx.HTTP_INTERNAL_SERVER_ERROR
local parse_pem_cert = ssl.parse_pem_cert
local parse_pem_priv_key = ssl.parse_pem_priv_key
local ssl_server_name = ssl.server_name
local get_variable = utils.get_variable
local get_multiple_variables = utils.get_multiple_variables
local has_variable = utils.has_variable
local read_files = utils.read_files
local open = io.open
local sub = string.sub
local match = string.match
local decode = cjson.decode
local execute = os.execute
local remove = os.remove

function letsencrypt:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "letsencrypt", ctx)
end

function letsencrypt:set()
	local https_configured = self.variables["AUTO_LETS_ENCRYPT"]
	if https_configured == "yes" then
		self.ctx.bw.https_configured = "yes"
	end
	return self:ret(true, "set https_configured to " .. https_configured)
end

function letsencrypt:init()
	local ret_ok, ret_err = true, "success"
	local wildcard_servers = {}

	if has_variable("AUTO_LETS_ENCRYPT", "yes") then
		local multisite, err = get_variable("MULTISITE", false)
		if not multisite then
			return self:ret(false, "can't get MULTISITE variable : " .. err)
		end
		if multisite == "yes" then
			local vars
			vars, err = get_multiple_variables({
				"AUTO_LETS_ENCRYPT",
				"LETS_ENCRYPT_CHALLENGE",
				"LETS_ENCRYPT_DNS_PROVIDER",
				"USE_LETS_ENCRYPT_WILDCARD",
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
					multisite_vars["AUTO_LETS_ENCRYPT"] == "yes"
					and server_name ~= "global"
					and (
						multisite_vars["LETS_ENCRYPT_CHALLENGE"] == "http"
						or (
							multisite_vars["LETS_ENCRYPT_CHALLENGE"] == "dns"
							and multisite_vars["LETS_ENCRYPT_DNS_PROVIDER"] ~= ""
							and credential_items[server_name]
							and credential_items[server_name]["LETS_ENCRYPT_DNS_CREDENTIAL_ITEM"] ~= ""
						)
					)
				then
					local data
					local server_names = multisite_vars["SERVER_NAME"]
					local cert_identifier = server_names:match("%S+")

					if
						multisite_vars["LETS_ENCRYPT_CHALLENGE"] == "dns"
						and multisite_vars["USE_LETS_ENCRYPT_WILDCARD"] == "yes"
					then
						for part in server_names:gmatch("%S+") do
							wildcard_servers[part] = true
						end
						local parts = {}
						for part in cert_identifier:gmatch("[^.]+") do
							table.insert(parts, part)
						end
						cert_identifier = table.concat(parts, ".", 2)
						data = self.datastore:get("plugin_letsencrypt_" .. cert_identifier, true)
					else
						for part in server_names:gmatch("%S+") do
							wildcard_servers[part] = false
						end
					end
					if not data then
						-- Load certificate
						local check
						local cert_path = "/var/cache/bunkerweb/letsencrypt/etc/live/" .. cert_identifier .. "/fullchain.pem"
						local key_path = "/var/cache/bunkerweb/letsencrypt/etc/live/" .. cert_identifier .. "/privkey.pem"
						check, data = read_files({cert_path, key_path})
						if not check then
							self.logger:log(ERR, "error while reading certificate files for " .. server_name .. " : " .. data)
							self.logger:log(ERR, "expected certificate files at: " .. cert_path .. " and " .. key_path)
							self.logger:log(ERR, "please ensure Let's Encrypt certificate generation completed successfully")
							ret_ok = false
							ret_err = "error reading files"
						else
							if
								multisite_vars["LETS_ENCRYPT_CHALLENGE"] == "dns"
								and multisite_vars["USE_LETS_ENCRYPT_WILDCARD"] == "yes"
							then
								check, err = self:load_data(data, cert_identifier)
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
			use_wildcard, err = get_variable("USE_LETS_ENCRYPT_WILDCARD", false)
			if not use_wildcard then
				return self:ret(false, "can't get USE_LETS_ENCRYPT_WILDCARD variable : " .. err)
			end
			local challenge
			challenge, err = get_variable("LETS_ENCRYPT_CHALLENGE", false)
			if not challenge then
				return self:ret(false, "can't get LETS_ENCRYPT_CHALLENGE variable : " .. err)
			end
			local server_names = server_name
			local cert_identifier = server_names:match("%S+")
			local use_wildcard_mode = challenge == "dns" and use_wildcard == "yes"
			if use_wildcard_mode then
				for part in server_names:gmatch("%S+") do
					wildcard_servers[part] = true
				end
				local parts = {}
				for part in cert_identifier:gmatch("[^.]+") do
					table.insert(parts, part)
				end
				cert_identifier = table.concat(parts, ".", 2)
			else
				for part in server_names:gmatch("%S+") do
				wildcard_servers[part] = false
			end
		end
		local cert_path = "/var/cache/bunkerweb/letsencrypt/etc/live/" .. cert_identifier .. "/fullchain.pem"
		local key_path = "/var/cache/bunkerweb/letsencrypt/etc/live/" .. cert_identifier .. "/privkey.pem"
		local check, data = read_files({cert_path, key_path})
		if not check then
			self.logger:log(ERR, "error while reading certificate files for " .. server_name .. " : " .. data)
			self.logger:log(ERR, "expected certificate files at: " .. cert_path .. " and " .. key_path)
			self.logger:log(ERR, "please ensure Let's Encrypt certificate generation completed successfully")
				ret_ok = false
				ret_err = "error reading files"
			else
				local load_key = use_wildcard_mode and cert_identifier or server_names
				check, err = self:load_data(data, load_key)
				if not check then
					self.logger:log(ERR, "error while loading data : " .. err)
					ret_ok = false
					ret_err = "error loading data"
				end
			end
		end
	else
		ret_err = "let's encrypt is not used"
	end

	local ok, err = self.datastore:set("plugin_letsencrypt_wildcard_servers", wildcard_servers, nil, true)
	if not ok then
		return self:ret(false, "error while setting wildcard servers into datastore : " .. err)
	end

	return self:ret(ret_ok, ret_err)
end

function letsencrypt:ssl_certificate()
	local server_name, err = ssl_server_name()
	if not server_name then
		return self:ret(false, "can't get server_name : " .. err)
	end
	local wildcard_servers, err = self.datastore:get("plugin_letsencrypt_wildcard_servers", true)
	if not wildcard_servers then
		return self:ret(false, "can't get wildcard servers : " .. err)
	end
	if wildcard_servers[server_name] then
		local parts = {}
		for part in server_name:gmatch("[^.]+") do
			table.insert(parts, part)
		end
		server_name = table.concat(parts, ".", 2)
	end
	local data
	data, err = self.datastore:get("plugin_letsencrypt_" .. server_name, true)
	if not data and err ~= "not found" then
		return self:ret(false, "error while getting plugin_letsencrypt_" .. server_name .. " from datastore : " .. err)
	elseif data then
		return self:ret(true, "certificate/key data found", data)
	end
	return self:ret(true, "let's encrypt is not used")
end

function letsencrypt:load_data(data, server_name)
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
		local cache_key = "plugin_letsencrypt_" .. key
		local ok
		ok, err = self.datastore:set(cache_key, { cert_chain, priv_key }, nil, true)
		if not ok then
			return false, "error while setting data into datastore : " .. err
		end
	end
	return true
end

function letsencrypt:access()
	if
		self.variables["LETS_ENCRYPT_PASSTHROUGH"] == "no"
		and sub(self.ctx.bw.uri, 1, string.len("/.well-known/acme-challenge/")) == "/.well-known/acme-challenge/"
	then
		self.logger:log(NOTICE, "got a visit from Let's Encrypt, let's whitelist it")
		return self:ret(true, "visit from LE", OK)
	end
	return self:ret(true, "success")
end

-- luacheck: ignore 212
function letsencrypt:api()
	if
		not match(self.ctx.bw.uri, "^/lets%-encrypt/challenge$")
		or (self.ctx.bw.request_method ~= "POST" and self.ctx.bw.request_method ~= "DELETE")
	then
		return self:ret(false, "success")
	end
	local acme_folder = "/var/tmp/bunkerweb/lets-encrypt/.well-known/acme-challenge/"
	local ngx_req = ngx.req
	ngx_req.read_body()
	local ret, data = pcall(decode, ngx_req.get_body_data())
	if not ret then
		return self:ret(true, "json body decoding failed", HTTP_BAD_REQUEST)
	end
	execute("mkdir -p " .. acme_folder)
	if self.ctx.bw.request_method == "POST" then
		local file, err = open(acme_folder .. data.token, "w+")
		if not file then
			return self:ret(true, "can't write validation token : " .. err, HTTP_INTERNAL_SERVER_ERROR)
		end
		file:write(data.validation)
		file:close()
		return self:ret(true, "validation token written", HTTP_OK)
	elseif self.ctx.bw.request_method == "DELETE" then
		local ok, err = remove(acme_folder .. data.token)
		if not ok then
			return self:ret(true, "can't remove validation token : " .. err, HTTP_INTERNAL_SERVER_ERROR)
		end
		return self:ret(true, "validation token removed", HTTP_OK)
	end
	return self:ret(true, "unknown request", HTTP_NOT_FOUND)
end

return letsencrypt
