local _M = {}

local ngx = ngx

local function log(level, msg)
	ngx.log(level, msg)
end

-- variables["global"] and variables["<server name>"], same layout as utils.get_variable.
-- A per-site value wins. The plugin default is "no".
local function stapling_enabled(internalstore, server_name)
	local ok, vars = pcall(function()
		return internalstore:get("variables", true)
	end)
	if not ok or type(vars) ~= "table" or type(vars["global"]) ~= "table" then
		return false
	end
	local value = vars["global"]["SSL_USE_OCSP_STAPLING"]
	if vars["global"]["MULTISITE"] == "yes" and server_name and type(vars[server_name]) == "table" then
		local site_value = vars[server_name]["SSL_USE_OCSP_STAPLING"]
		if site_value ~= nil then
			value = site_value
		end
	end
	if type(value) == "boolean" then
		return value
	end
	if value == nil then
		return false
	end
	local str = tostring(value):lower()
	return str == "1" or str == "true" or str == "on" or str == "yes"
end

local function pem_blocks(cert_pem)
	local blocks = {}
	for block in cert_pem:gmatch("(%-%-%-%-%-BEGIN CERTIFICATE%-%-%-%-%-.-%-%-%-%-%-END CERTIFICATE%-%-%-%-%-)") do
		blocks[#blocks + 1] = block
	end
	if #blocks == 0 then
		blocks[1] = cert_pem
	end
	return blocks
end

-- SHA256 of SubjectPublicKeyInfo DER, matching ocsp-refresh.py.
-- Cached so later handshakes for the same PEM do not spawn openssl.
local function spki_fingerprint(cert_pem, internalstore)
	local md5 = ngx.md5 and ngx.md5(cert_pem) or nil
	local cache_key = md5 and ("TLS:SSL:ocsp_spki:" .. md5) or nil
	if cache_key then
		local ok, cached = pcall(function()
			return internalstore:get(cache_key, true)
		end)
		if ok and type(cached) == "string" and cached:match("^[0-9a-f]{64}$") then
			return cached
		end
	end

	local fingerprint = nil
	pcall(function()
		local tmp = "/tmp/ocsp_spki_" .. tostring(ngx.worker.pid()) .. ".pem"
		local f = io.open(tmp, "w")
		if not f then
			return
		end
		f:write(cert_pem)
		f:close()
		local cmd = "openssl x509 -pubkey -noout -in " .. tmp .. " 2>/dev/null"
			.. " | openssl pkey -pubin -outform DER 2>/dev/null"
			.. " | openssl dgst -sha256 2>/dev/null"
		local handle = io.popen(cmd, "r")
		if handle then
			local out = handle:read("*a")
			handle:close()
			if out then
				local fp = out:match("=%s*([0-9A-Fa-f]{64})")
				if fp then
					fingerprint = fp:lower()
				end
			end
		end
		os.remove(tmp)
	end)

	if cache_key and fingerprint then
		pcall(function()
			internalstore:set(cache_key, fingerprint, 86400, true)
		end)
	end
	return fingerprint
end

local function read_file(path)
	local data = nil
	local f = io.open(path, "rb")
	if not f then
		return nil
	end
	data = f:read("*a")
	f:close()
	if data and #data > 0 then
		return data
	end
	return nil
end

local function ocsp_path(fingerprint)
	return "/var/cache/bunkerweb/ssl/" .. fingerprint:sub(1, 1) .. "/" .. fingerprint:sub(2, 2) .. "/" .. fingerprint .. "/ocsp.der"
end

local function issuer_path(fingerprint)
	return "/var/cache/bunkerweb/ssl/" .. fingerprint:sub(1, 1) .. "/" .. fingerprint:sub(2, 2) .. "/" .. fingerprint .. "/issuer.pem"
end

local function validate(ocsp, ssl, ocsp_der, leaf_pem, issuer_pem)
	if not issuer_pem or issuer_pem == "" or not ssl.cert_pem_to_der then
		return false
	end
	local der_chain, err = ssl.cert_pem_to_der(leaf_pem .. "\n" .. issuer_pem)
	if not der_chain then
		log(ngx.DEBUG, "OCSP cert_pem_to_der failed: " .. tostring(err))
		return false
	end
	local ok_call, validate_ok = pcall(function()
		return ocsp.validate_ocsp_response(ocsp_der, der_chain)
	end)
	return ok_call and validate_ok == true
end

-- Staple a cached OCSP response for cert_pem. Used by the stream TLS handshake.
-- HTTP keeps its own callback; both read the same ocsp.der / issuer.pem cache.
function _M.staple(internalstore, server_name, cert_pem)
	if type(cert_pem) ~= "string" or cert_pem == "" or not internalstore then
		return false
	end
	if not stapling_enabled(internalstore, server_name) then
		return false
	end

	local ok_ocsp, ocsp = pcall(require, "ngx.ocsp")
	if not ok_ocsp or not ocsp or not ocsp.set_ocsp_status_resp then
		log(ngx.ERR, "OCSP ngx.ocsp is not available, skipping stapling")
		return false
	end
	local ssl = require "ngx.ssl"
	local blocks = pem_blocks(cert_pem)

	for _, leaf_pem in ipairs(blocks) do
		local fingerprint = spki_fingerprint(leaf_pem, internalstore)
		if fingerprint then
			local resp = read_file(ocsp_path(fingerprint))
			if resp then
				local issuers = {}
				for _, other in ipairs(blocks) do
					if other ~= leaf_pem then
						issuers[#issuers + 1] = other
					end
				end
				local stored = read_file(issuer_path(fingerprint))
				if stored then
					issuers[#issuers + 1] = stored
				end
				for _, issuer_pem in ipairs(issuers) do
					if validate(ocsp, ssl, resp, leaf_pem, issuer_pem) then
						local ok_set, set_ok, set_err = pcall(function()
							return ocsp.set_ocsp_status_resp(resp)
						end)
						if ok_set and set_ok then
							return true
						end
						log(ngx.ERR, "OCSP failed to set stapling: " .. tostring(set_err or set_ok))
						return false
					end
				end
			end
		end
	end
	return false
end

return _M
