local class = require "middleclass"
local plugin = require "bunkerweb.plugin"
local ssl = require "ngx.ssl"
local utils = require "bunkerweb.utils"

local certificates = class("certificates", plugin)

local ngx = ngx
local ERR = ngx.ERR
local INFO = ngx.INFO
local io_open = io.open
local parse_pem_cert = ssl.parse_pem_cert
local parse_pem_priv_key = ssl.parse_pem_priv_key
local ssl_server_name = ssl.server_name
local get_variable = utils.get_variable
local get_multiple_variables = utils.get_multiple_variables
local read_files = utils.read_files

local CACHE_PATH = "/var/cache/bunkerweb/certificates/"

function certificates:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "certificates", ctx)
end

local function has_certificate(server_name)
	-- The deploy-certificates job only writes a directory for services that actually have an
	-- attachment, so the presence of the pair is the activation gate: this plugin owns no
	-- setting, the attachment in the inventory is the switch.
	for _, name in ipairs({ "cert.pem", "key.pem" }) do
		local file = io_open(CACHE_PATH .. server_name .. "/" .. name, "r")
		if not file then
			return false
		end
		file:close()
	end
	return true
end

function certificates:set()
	-- A service whose TLS comes only from an inventory attachment has none of the provider
	-- settings set, so without this it would look like plain HTTP to everything that keys off
	-- https_configured (AUTO_REDIRECT_HTTP_TO_HTTPS in ssl.lua, secure-cookie handling in
	-- cors.lua). init() populated one key per name of every covered service, so its presence
	-- is the authoritative answer here.
	local server_name = self.ctx.bw.server_name
	if not server_name then
		return self:ret(true, "no server name in context")
	end
	local data, err = self.internalstore:get("plugin_certificates_" .. server_name, true)
	if not data then
		if err and err ~= "not found" then
			return self:ret(
				false,
				"error while getting plugin_certificates_" .. server_name .. " from internalstore : " .. err
			)
		end
		return self:ret(true, "no certificate attached to this service")
	end
	self.ctx.bw.https_configured = "yes"
	return self:ret(true, "set https_configured to yes")
end

function certificates:init()
	local ret_ok, ret_err = true, "success"
	local servers = {}

	local multisite, err = get_variable("MULTISITE", false)
	if not multisite then
		return self:ret(false, "can't get MULTISITE variable : " .. err)
	end

	if multisite == "yes" then
		local vars
		vars, err = get_multiple_variables({ "SERVER_NAME" })
		if not vars then
			return self:ret(false, "can't get SERVER_NAME variables : " .. err)
		end
		for server_name, multisite_vars in pairs(vars) do
			if server_name ~= "global" then
				servers[server_name] = multisite_vars["SERVER_NAME"] or server_name
			end
		end
	else
		local server_name
		server_name, err = get_variable("SERVER_NAME", false)
		if not server_name then
			return self:ret(false, "can't get SERVER_NAME variable : " .. err)
		end
		-- An instance that has not received its first configuration yet has SERVER_NAME set to
		-- the empty string, which `not server_name` does not catch: the match then yields nil
		-- and indexing the table with it aborts init with "table index is nil" on every cold
		-- boot. Nothing is attached to a service that does not exist yet, so stop here.
		local first_server = server_name:match("%S+")
		if not first_server then
			return self:ret(true, "no server name configured yet")
		end
		servers[first_server] = server_name
	end

	local loaded = 0
	for first_server, server_name in pairs(servers) do
		if has_certificate(first_server) then
			local check, data = read_files({
				CACHE_PATH .. first_server .. "/cert.pem",
				CACHE_PATH .. first_server .. "/key.pem",
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
				else
					loaded = loaded + 1
				end
			end
		end
	end

	if ret_ok and loaded == 0 then
		ret_err = "no certificate attached to a service"
	end
	return self:ret(ret_ok, ret_err)
end

function certificates:ssl_certificate()
	local server_name, err = ssl_server_name()
	if not server_name then
		if err then
			return self:ret(false, "can't get server_name : " .. err)
		end
		return self:ret(true, "no SNI provided")
	end
	local data
	data, err = self.internalstore:get("plugin_certificates_" .. server_name, true)
	if not data and err ~= "not found" then
		return self:ret(
			false,
			"error while getting plugin_certificates_" .. server_name .. " from internalstore : " .. err
		)
	elseif data then
		return self:ret(true, "certificate/key data found", data)
	end
	return self:ret(true, "no certificate attached to this service")
end

function certificates:load_data(data, server_name)
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
	-- Cache data under every name of the service, and under the "plugin_<id>_<host>" key the
	-- ssl_certificate phase runner and the wildcard resolver both expect. Publishing no
	-- "plugin_certificates_wildcard_bases" is deliberate: we resolve exact hosts only, so the
	-- wildcard plugin must serve an inventory wildcard on sub-domains itself rather than defer
	-- to a slot that would return nothing.
	for key in server_name:gmatch("%S+") do
		local cache_key = "plugin_certificates_" .. key
		local ok
		ok, err = self.internalstore:set(cache_key, { cert_chain, priv_key }, nil, true)
		if not ok then
			return false, "error while setting data into internalstore : " .. err
		end
		self.logger:log(INFO, "loaded attached certificate for " .. key)
	end
	return true
end

return certificates
