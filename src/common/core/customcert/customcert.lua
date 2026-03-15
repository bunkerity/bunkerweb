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

-- Candidate dir names per identifier; order matches custom-cert.py CERT_DIR_SUFFIXES then no suffix.
local function build_candidates(identifier)
	return {
		identifier .. "-ecdsa",
		identifier .. "-rsa",
		identifier .. "-ML-DSA",
		identifier .. "-SLH-DSA",
		identifier .. "-pqc",
		identifier,
	}
end

-- Only two layouts: identifier/cert.pem, key.pem and identifier-TYPE/cert.pem, key.pem.
-- For a service like mirror.example.com, also try _wildcard_.example.com (wildcard cert for *.example.com).
-- On failure returns (false, err_msg, nil, searched_dirs) so callers can log all dirs searched.
local function read_cert_files_by_identifier(identifier)
	if not identifier or identifier == "" then
		return false, "empty identifier", nil, {}
	end
	local function try_identifier(id, searched_dirs)
		for _, name in ipairs(build_candidates(id)) do
			local dir = customcert_prefix .. name
			searched_dirs[#searched_dirs + 1] = dir
			local paths = { dir .. "/cert.pem", dir .. "/key.pem" }
			-- Use pcall to suppress errors during search phase (files may not exist for some candidates)
			local ok, check, data = pcall(read_files, paths)
			if ok and check then
				ngx.log(ngx.DEBUG, "customcert: ✓ found cert files in " .. dir)
				return check, data, name
			else
				ngx.log(ngx.DEBUG, "customcert: cert files not found in " .. dir)
			end
		end
		return nil
	end
	local searched_dirs = {}
	if identifier:sub(1, 2) == "*." then
		identifier = WILDCARD_CERT_NAME_PREFIX .. identifier:sub(3)
	end
	local check, data, name = try_identifier(identifier, searched_dirs)
	if check then
		return check, data, name
	end
	-- Fallback: wildcard cert for this domain (e.g. mirror.example.com -> _wildcard_.example.com)
	if identifier:sub(1, #WILDCARD_CERT_NAME_PREFIX) ~= WILDCARD_CERT_NAME_PREFIX then
		local parent_domain = identifier:match("^[^%.]+%.(.+)$")
		if parent_domain and parent_domain ~= "" then
			local wildcard_id = WILDCARD_CERT_NAME_PREFIX .. parent_domain
			check, data, name = try_identifier(wildcard_id, searched_dirs)
			if check then
				return check, data, name
			end
		end
	end
	return false, "no cert found for " .. identifier, nil, searched_dirs
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

-- Load custom certs from disk into internalstore. Used by init() (master) and init_worker() (workers).
-- Workers run init_worker after cache is synced, so certs are available on reload.
function customcert:load_certs_from_disk()
	local ret_ok, ret_err = true, "success"
	local any_service_with_certs = false  -- Track if any service had USE_CUSTOM_SSL=yes
	local any_service_loaded = false      -- Track if at least one service successfully loaded certs
	self.logger:log(ngx.DEBUG, "customcert: load_certs_from_disk() called")
	local multisite, err = get_variable("MULTISITE", false)
	if not multisite then
		return self:ret(false, "can't get MULTISITE variable : " .. err)
	end
	-- In multisite mode, allow processing if any service has USE_CUSTOM_SSL=yes
	-- In single-site mode, require global USE_CUSTOM_SSL=yes
	if multisite ~= "yes" and not has_variable("USE_CUSTOM_SSL", "yes") then
		self.logger:log(ngx.DEBUG, "customcert: custom cert is not used (single-site mode, global USE_CUSTOM_SSL is not yes)")
		return self:ret(true, "custom cert is not used")
	end
	if multisite == "yes" then
		local vars
		vars, err = get_multiple_variables({ "USE_CUSTOM_SSL", "SERVER_NAME" })
		if not vars then
			return self:ret(false, "can't get USE_CUSTOM_SSL variables : " .. err)
		end
		self.logger:log(ngx.DEBUG, "customcert: processing " .. tostring(#vars) .. " services in multisite mode")
		for server_name, multisite_vars in pairs(vars) do
			if server_name ~= "global" then
				if multisite_vars["USE_CUSTOM_SSL"] == "yes" then
					any_service_with_certs = true
					self.logger:log(ngx.INFO, "customcert: loading custom cert for service " .. server_name)
				else
					self.logger:log(ngx.DEBUG, "customcert: skipping service " .. server_name .. " (USE_CUSTOM_SSL is not yes)")
				end
			end
			if multisite_vars["USE_CUSTOM_SSL"] == "yes" and server_name ~= "global" then
				local check, data, cert_dir, searched_dirs = read_cert_files_by_identifier(server_name)
				if not check then
					local msg = "customcert: ⚠️ " .. data
					if searched_dirs and #searched_dirs > 0 then
						msg = msg .. " (directories searched: " .. table.concat(searched_dirs, ", ") .. ")"
					end
					self.logger:log(WARN, msg)
					-- Don't fail init() if one service's cert is missing - just warn
					-- But track that we had at least one service with certs enabled
				else
					any_service_loaded = true
					self.logger:log(ngx.INFO, "customcert: ✓ found cert in " .. (cert_dir or "?") .. " for " .. server_name)
					pcall(check_cert_ttl, data[1], multisite_vars["SERVER_NAME"] or server_name, self.logger)
					check, err = self:load_data(data, multisite_vars["SERVER_NAME"])
					if not check then
						self.logger:log(ERR, "customcert: ❌ error while loading data into internalstore : " .. err)
						ret_ok = false
						ret_err = "error loading data"
					else
						self.logger:log(ngx.INFO, "customcert: ✓ loaded custom cert into internalstore for " .. server_name)
					end
				end
			end
		end
		-- In multisite mode, only fail if we expected certs but couldn't load ANY of them
		if any_service_with_certs and not any_service_loaded then
			ret_ok = false
			ret_err = "no custom certificates could be loaded"
		end
	else
		local server_name
		server_name, err = get_variable("SERVER_NAME", false)
		if not server_name then
			return self:ret(false, "can't get SERVER_NAME variable : " .. err)
		end
		local check, data, _, searched_dirs = read_cert_files_by_identifier(server_name:match("%S+"))
		if not check then
			local msg = "customcert: " .. data
			if searched_dirs and #searched_dirs > 0 then
				msg = msg .. " (directories searched: " .. table.concat(searched_dirs, ", ") .. ")"
			end
			self.logger:log(ERR, msg)
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
	return self:ret(ret_ok, ret_err)
end

function customcert:init()
	return self:load_certs_from_disk()
end

-- Load certs from disk in each worker so custom certs are available after cache sync and reload.
-- Master init() may run before cache is present on this instance; init_worker runs after workers start.
function customcert:init_worker()
	return self:load_certs_from_disk()
end

function customcert:ssl_certificate()
	local server_name, err = ssl_server_name()
	if not server_name then
		if err then
			return self:ret(false, "can't get server_name : " .. err)
		end
		return self:ret(true, "no SNI provided")
	end
	-- Normalize SNI (e.g. strip trailing dot) so lookup matches what we stored
	server_name = server_name:gsub("%.$", ""):match("^%s*(.-)%s*$") or server_name
	self.logger:log(ngx.DEBUG, "customcert: ssl_certificate() called for SNI=" .. server_name)

	local cert_pem, key_pem
	cert_pem = self.internalstore:get("plugin_customcert_" .. server_name .. "_cert", false)
	if not cert_pem or cert_pem == "" then
		self.logger:log(ngx.DEBUG, "customcert: no cert found in internalstore for " .. server_name .. ", checking LE...")
		return self:ret(true, "custom certificate is not used")
	end
	self.logger:log(ngx.DEBUG, "customcert: found cert in internalstore for " .. server_name)

	key_pem = self.internalstore:get("plugin_customcert_" .. server_name .. "_key", false)
	if not key_pem or key_pem == "" then
		self.logger:log(ngx.DEBUG, "customcert: found cert but no key in internalstore for " .. server_name)
		return self:ret(true, "custom certificate is not used")
	end

	-- Worker-local cache of parsed cert/key to avoid repeated PEM parsing on every handshake
	local parsed_cache_key = "plugin_customcert_" .. server_name .. "_parsed"
	local cached_parsed = self.internalstore:get(parsed_cache_key, true)
	if cached_parsed
		and type(cached_parsed) == "table"
		and cached_parsed.cert_pem == cert_pem
		and cached_parsed.key_pem == key_pem
		and cached_parsed.cert_chain
		and cached_parsed.priv_key
	then
		self.logger:log(ngx.DEBUG, "customcert: using cached parsed certificate for " .. server_name)
		return self:ret(true, "certificate/key data found (cached)", { cached_parsed.cert_chain, cached_parsed.priv_key })
	end

	local cert_chain, _ = parse_pem_cert(cert_pem)
	local priv_key, _ = parse_pem_priv_key(key_pem)
	if not cert_chain or not priv_key then
		self.logger:log(ngx.DEBUG, "customcert: found cert/key but failed to parse for " .. server_name)
		return self:ret(true, "custom certificate is not used")
	end

	local ok_cache, cache_err = self.internalstore:set(parsed_cache_key, {
		cert_chain = cert_chain,
		priv_key = priv_key,
		cert_pem = cert_pem,
		key_pem = key_pem,
	}, nil, true)
	if not ok_cache then
		self.logger:log(WARN, "customcert: failed to cache parsed cert " .. server_name .. " : " .. (cache_err or "?"))
	end
	self.logger:log(ngx.DEBUG, "✓ customcert: using custom certificate for " .. server_name)
	return self:ret(true, "certificate/key data found", { cert_chain, priv_key })
end

function customcert:load_data(data, server_name)
	-- Store raw PEM strings in shared dict (worker=false); set_with_retries overwrites on rotation
	for key in server_name:gmatch("%S+") do
		local key_trim = key:gsub("%.$", ""):match("^%s*(.-)%s*$") or key
		local cert_key = "plugin_customcert_" .. key_trim .. "_cert"
		local key_key = "plugin_customcert_" .. key_trim .. "_key"
		local ok, set_err
		ok, set_err = self.internalstore:set_with_retries(cert_key, data[1], nil)
		if not ok then
			return false, "error while setting data into internalstore : " .. (set_err or "")
		end
		ok, set_err = self.internalstore:set_with_retries(key_key, data[2], nil)
		if not ok then
			return false, "error while setting data into internalstore : " .. (set_err or "")
		end
	end
	return true
end

return customcert
