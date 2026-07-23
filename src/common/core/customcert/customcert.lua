local class = require "middleclass"
local pkey = require "resty.openssl.pkey"
local plugin = require "bunkerweb.plugin"
local ssl = require "ngx.ssl"
local utils = require "bunkerweb.utils"
local x509 = require "resty.openssl.x509"

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
local lower = string.lower
local sort = table.sort
local time = os.time

local function normalize_hostname(hostname)
	if not hostname then
		return nil
	end
	return lower(hostname:gsub("%.$", ""))
end

local function get_certificate_dns_names(cert)
	local names = {}
	local subject_alt_names, err = cert:get_subject_alt_name()
	if err then
		return nil, err
	end
	if subject_alt_names then
		for name_type, name in subject_alt_names:each() do
			if name_type == "DNS" then
				names[normalize_hostname(name)] = true
			end
		end
		if next(names) then
			return names
		end
	end

	local subject = cert:get_subject_name()
	if not subject then
		return names
	end
	local common_name = subject:find("CN")
	if common_name and common_name.blob then
		names[normalize_hostname(common_name.blob)] = true
	end
	return names
end

local function get_wildcard_bases(cert_pem, key_pem, server_names)
	local cert, err = x509.new(cert_pem)
	if not cert then
		return nil, "can't parse certificate metadata : " .. err
	end

	local not_before = cert:get_not_before()
	local not_after = cert:get_not_after()
	local now = time()
	if not not_before or not_before > now or not not_after or not_after <= now then
		return nil, "certificate is not currently valid"
	end

	local private_key
	private_key, err = pkey.new(key_pem)
	if not private_key then
		return nil, "can't parse private key metadata : " .. err
	end
	local public_key = cert:get_pubkey()
	if not public_key then
		return nil, "can't read certificate public key"
	end
	local cert_public_der
	cert_public_der, err = public_key:tostring("public", "DER")
	if not cert_public_der then
		return nil, "can't export certificate public key : " .. err
	end
	local key_public_der
	key_public_der, err = private_key:tostring("public", "DER")
	if not key_public_der then
		return nil, "can't export private key public component : " .. err
	end
	if cert_public_der ~= key_public_der then
		return nil, "certificate and private key do not match"
	end

	local dns_names
	dns_names, err = get_certificate_dns_names(cert)
	if not dns_names then
		return nil, "can't read certificate DNS names : " .. err
	end

	local bases = {}
	for server_name in server_names:gmatch("%S+") do
		local base = normalize_hostname(server_name)
		if dns_names["*." .. base] then
			bases[base] = true
		end
	end
	return bases
end

local function resolve_wildcard_base(hostname, bases)
	local host = normalize_hostname(hostname)
	for _, base in ipairs(bases) do
		local suffix = "." .. base
		if #host > #suffix and host:sub(-#suffix) == suffix then
			local wildcard_label = host:sub(1, #host - #suffix)
			if wildcard_label ~= "" and not wildcard_label:find(".", 1, true) then
				return base
			end
		end
	end
	return nil
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
	local wildcard_certificates = {}
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
						check, err = self:load_data(data, multisite_vars["SERVER_NAME"], wildcard_certificates)
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
				check, err = self:load_data(data, server_name, wildcard_certificates)
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

	local wildcard_bases = {}
	for base in pairs(wildcard_certificates) do
		table.insert(wildcard_bases, base)
	end
	sort(wildcard_bases, function(a, b)
		if #a == #b then
			return a < b
		end
		return #a > #b
	end)

	local ok, err = self.internalstore:set("plugin_customcert_wildcard_bases", wildcard_bases, nil, true)
	if not ok then
		return self:ret(false, "error while caching custom certificate wildcard bases : " .. err)
	end
	ok, err = self.internalstore:set("plugin_customcert_wildcard_certificates", wildcard_certificates, nil, true)
	if not ok then
		return self:ret(false, "error while caching custom wildcard certificates : " .. err)
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
	local normalized_server_name = normalize_hostname(server_name)
	local data
	data, err = self.internalstore:get("plugin_customcert_" .. normalized_server_name, true)
	if not data and err ~= "not found" then
		return self:ret(
			false,
			"error while getting plugin_customcert_" .. normalized_server_name .. " from internalstore : " .. err
		)
	elseif data then
		return self:ret(true, "certificate/key data found", data)
	end

	local wildcard_bases, bases_err = self.internalstore:get("plugin_customcert_wildcard_bases", true)
	if not wildcard_bases and bases_err ~= "not found" then
		return self:ret(false, "can't get custom certificate wildcard bases : " .. bases_err)
	end
	if wildcard_bases then
		local base = resolve_wildcard_base(normalized_server_name, wildcard_bases)
		if base then
			local wildcard_certificates, wildcard_err = self.internalstore:get("plugin_customcert_wildcard_certificates", true)
			if not wildcard_certificates then
				if wildcard_err ~= "not found" then
					return self:ret(false, "can't get custom wildcard certificates : " .. wildcard_err)
				end
			elseif wildcard_certificates[base] then
				return self:ret(true, "wildcard certificate/key data found for " .. base, wildcard_certificates[base])
			end
		end
	end
	return self:ret(true, "custom certificate is not used")
end

function customcert:load_data(data, server_name, wildcard_certificates)
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
		local cache_key = "plugin_customcert_" .. normalize_hostname(key)
		local ok
		ok, err = self.internalstore:set(cache_key, { cert_chain, priv_key }, nil, true)
		if not ok then
			return false, "error while setting data into internalstore : " .. err
		end
	end

	if wildcard_certificates then
		local wildcard_bases, wildcard_err = get_wildcard_bases(data[1], data[2], server_name)
		if not wildcard_bases then
			self.logger:log(WARN, "custom certificate is not eligible for wildcard SNI fallback : " .. wildcard_err)
		else
			for base in pairs(wildcard_bases) do
				wildcard_certificates[base] = { cert_chain, priv_key }
			end
		end
	end
	return true
end

return customcert
