local class = require "middleclass"
local plugin = require "bunkerweb.plugin"
local ssl = require "ngx.ssl"
local utils = require "bunkerweb.utils"

local customcert = class("customcert", plugin)

local ngx = ngx
local ERR = ngx.ERR
local WARN = ngx.WARN
local parse_pem_cert = ssl.parse_pem_cert
local parse_pem_priv_key = ssl.parse_pem_priv_key
local ssl_server_name = ssl.server_name
local get_variable = utils.get_variable
local get_multiple_variables = utils.get_multiple_variables
local has_variable = utils.has_variable
local read_files = utils.read_files

local customcert_prefix = "/var/cache/bunkerweb/customcert/"

-- Wildcard certs stored under this prefix (matches custom-cert.py). e.g. *.example.com -> _wildcard_.example.com
local WILDCARD_CERT_NAME_PREFIX = "_wildcard_."

-- TTL thresholds (seconds); match custom-cert.py semantics.
local TTL_ONE_DAY = 86400
local TTL_THREE_DAYS = 259200

-- Log certificate TTL on service restart (init). Uses resty.openssl.x509 if available.
local function check_cert_ttl(cert_pem, server_name, logger)
	if type(cert_pem) ~= "string" or cert_pem == "" then
		return
	end
	local ok, x509 = pcall(require, "resty.openssl.x509")
	if not ok or not x509 then
		return
	end
	-- Extract first PEM cert (leaf) from chain
	local begin = cert_pem:find("-----BEGIN CERTIFICATE-----", 1, true)
	local end_marker = cert_pem:find("-----END CERTIFICATE-----", 1, true)
	if not begin or not end_marker or end_marker <= begin then
		return
	end
	local end_len = #("-----END CERTIFICATE-----")
	local first_cert = cert_pem:sub(begin, end_marker + end_len)
	local cert_obj, _ = x509.new(first_cert, "PEM")
	if not cert_obj then
		return
	end
	local not_after, _ = cert_obj:get_not_after()
	if not not_after or type(not_after) ~= "number" then
		return
	end
	local now = os.time()
	local ttl_seconds = not_after - now
	local ttl_days = ttl_seconds / 86400.0
	local name = tostring(server_name)
	if ttl_seconds <= 0 then
		local msg = "customcert: certificate expired for " .. name .. " (expired "
			.. string.format("%.1f", -ttl_days) .. " days ago)"
		logger:log(ERR, msg)
	elseif ttl_seconds <= TTL_ONE_DAY then
		local msg = "customcert: certificate TTL below 1 day (" .. string.format("%.2f", ttl_days)
			.. " days) for " .. name .. ". Consider renewal."
		logger:log(ERR, msg)
	elseif ttl_seconds < TTL_THREE_DAYS then
		local msg = "customcert: certificate TTL below 3 days (" .. string.format("%.2f", ttl_days)
			.. " days) for " .. name .. ". Consider renewal."
		logger:log(WARN, msg)
	end
end

-- Try key-type suffixes (ecdsa, rsa, ML-DSA, SLH-DSA, pqc), then no suffix. Order matches custom-cert.
local function read_cert_files_by_identifier(identifier)
	if not identifier or identifier == "" then
		return false, "empty identifier", nil
	end
	if identifier:sub(1, 2) == "*." then
		identifier = WILDCARD_CERT_NAME_PREFIX .. identifier:sub(3)
	end
	local candidates = {
		identifier .. "-ecdsa",
		identifier .. "-rsa",
		identifier .. "-ML-DSA",
		identifier .. "-SLH-DSA",
		identifier .. "-pqc",
		identifier,
	}
	for _, name in ipairs(candidates) do
		local paths = { customcert_prefix .. name .. "/cert.pem", customcert_prefix .. name .. "/key.pem" }
		local check, data = read_files(paths)
		if check then
			return check, data, name
		end
	end
	return false, "no cert found for " .. identifier, nil
end

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
					local check, data = read_cert_files_by_identifier(server_name)
					if not check then
						self.logger:log(ERR, "error while reading files : " .. data)
						ret_ok = false
						ret_err = "error reading files"
					else
						pcall(check_cert_ttl, data[1], multisite_vars["SERVER_NAME"] or server_name, self.logger)
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
			local check, data = read_cert_files_by_identifier(server_name:match("%S+"))
			if not check then
				self.logger:log(ERR, "error while reading files : " .. data)
				ret_ok = false
				ret_err = "error reading files"
			else
				pcall(check_cert_ttl, data[1], server_name, self.logger)
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
		if err then
			return self:ret(false, "can't get server_name : " .. err)
		end
		return self:ret(true, "no SNI provided")
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
