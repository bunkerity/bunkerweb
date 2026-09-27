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

local function is_fp64(fp)
	return type(fp) == "string" and #fp == 64 and fp:match("^%x+$") ~= nil
end

local function to_hex(bin)
	local hex = {}
	for i = 1, #bin do
		hex[i] = string.format("%02x", string.byte(bin, i))
	end
	return table.concat(hex)
end

-- SHA256 of SubjectPublicKeyInfo DER, matching ocsp-refresh.py.
local function spki_fingerprint(cert_pem, internalstore)
	local md5 = ngx.md5 and ngx.md5(cert_pem) or nil
	local cache_key = md5 and ("TLS:SSL:ocsp_spki:" .. md5) or nil
	if cache_key then
		local ok, cached = pcall(function()
			return internalstore:get(cache_key, true)
		end)
		if ok and is_fp64(cached) then
			return cached:lower()
		end
	end

	local fingerprint = nil
	local ok_fp, err = pcall(function()
		local x509 = require("resty.openssl.x509")
		local digest_lib = require("resty.openssl.digest")
		local cert_obj = x509.new(cert_pem)
		if not cert_obj then
			return
		end
		local pub = cert_obj:get_pubkey()
		local spki = pub and pub:tostring("public", "DER")
		if not spki then
			return
		end
		local digest_ctx = digest_lib.new("sha256")
		digest_ctx:update(spki)
		fingerprint = to_hex(digest_ctx:final())
	end)
	if not ok_fp then
		log(ngx.DEBUG, "OCSP SPKI fingerprint failed: " .. tostring(err))
	end

	if cache_key and is_fp64(fingerprint) then
		pcall(function()
			internalstore:set(cache_key, fingerprint, 86400, true)
		end)
		return fingerprint
	end
	return nil
end

local function read_file(path)
	local f = io.open(path, "rb")
	if not f then
		return nil
	end
	local data = f:read("*a")
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

local function cache_key(fingerprint)
	return "TLS:SSL:ocsp:" .. fingerprint
end

local function verified_key(fingerprint)
	return "TLS:SSL:ocsp_verified:" .. fingerprint
end

-- Bind verified flag to OCSP DER bytes (not SPKI alone). Same-key renewals keep the fingerprint.
local function resp_binding(resp)
	if type(resp) ~= "string" or #resp == 0 then
		return nil
	end
	local ok, digest = pcall(function()
		local digest_lib = require("resty.openssl.digest")
		local ctx = digest_lib.new("sha256")
		ctx:update(resp)
		return to_hex(ctx:final())
	end)
	if ok and type(digest) == "string" and #digest == 64 then
		return digest
	end
	return nil
end

local function get_cached_resp(internalstore, fingerprint)
	local ok, resp = pcall(function()
		return internalstore:get(cache_key(fingerprint), true)
	end)
	if ok and type(resp) == "string" and #resp > 0 then
		return resp
	end
	return nil
end

local function is_verified(internalstore, fingerprint, resp)
	local binding = resp_binding(resp)
	if not binding then
		return false
	end
	local ok, stored = pcall(function()
		return internalstore:get(verified_key(fingerprint), true)
	end)
	return ok and stored == binding
end

local function warm_cache(internalstore, fingerprint, resp)
	local binding = resp_binding(resp)
	pcall(function()
		internalstore:set(cache_key(fingerprint), resp, 300, true)
		if binding then
			internalstore:set(verified_key(fingerprint), binding, 300, true)
		end
	end)
end

local function drop_cache(internalstore, fingerprint)
	pcall(function()
		internalstore:delete(cache_key(fingerprint))
		internalstore:delete(verified_key(fingerprint))
	end)
end

-- True when L1 DER still matches on-disk ocsp.der (job may have replaced the file).
local function l1_matches_disk(fingerprint, resp)
	local binding = resp_binding(resp)
	if not binding then
		return false
	end

	local disk_sha = nil
	pcall(function()
		local meta_path = "/var/cache/bunkerweb/ssl/"
			.. fingerprint:sub(1, 1)
			.. "/"
			.. fingerprint:sub(2, 2)
			.. "/"
			.. fingerprint
			.. "/ocsp.json"
		local f = io.open(meta_path, "r")
		if not f then
			return
		end
		local raw = f:read("*a")
		f:close()
		if type(raw) ~= "string" then
			return
		end
		local sha = raw:match('"der_sha256"%s*:%s*"([0-9a-fA-F]+)"')
		if sha and #sha == 64 then
			disk_sha = sha:lower()
		end
	end)

	if disk_sha then
		return disk_sha == binding
	end

	local data = read_file(ocsp_path(fingerprint))
	if not data then
		return false
	end
	return resp_binding(data) == binding
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

local function issuer_candidates(blocks, leaf_pem, fingerprint)
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
	return issuers
end

-- True when TLS Feature text asserts status_request (Must-Staple / feature id 5).
-- Do not substring-match "5": that false-positives on OIDs and other digits.
local function tls_feature_is_must_staple(text)
	if type(text) ~= "string" or text == "" then
		return false
	end
	if text:find("OCSP status request", 1, true) then
		return true
	end
	-- Named forms; exclude status_request_v2 / statusRequestV2
	if text:find("status_request%f[^%w_]") or text:match("status_request%s*$") then
		return true
	end
	if text:find("statusRequest%f[^%w]") or text:match("%.?statusRequest%s*$") then
		return true
	end
	-- Feature id 5 as a whole decimal token (e.g. "5", "5, 17") — callers must pass
	-- extension text or TLS Feature value line(s), never a full openssl dump.
	for token in text:gmatch("%d+") do
		if token == "5" then
			return true
		end
	end
	return false
end

local function has_must_staple(cert_pem)
	local must = false
	pcall(function()
		local x509 = require("resty.openssl.x509")
		local cert_obj = x509.new(cert_pem)
		if not cert_obj then
			return
		end
		local tls_feature_ext = cert_obj:get_extension("tlsfeature")
		if not tls_feature_ext then
			return
		end
		must = tls_feature_is_must_staple(tls_feature_ext:text() or "")
	end)
	return must
end

local function try_staple(ocsp, ssl, resp, leaf_pem, issuers)
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
	return nil
end

-- Staple a cached OCSP response for cert_pem. Used by the stream TLS handshake.
-- HTTP uses ngx.shared.internalstore; stream uses internalstore_stream. Same key layout
-- (TLS:SSL:ocsp: / ocsp_verified:) so each subsystem warms its own L1 for 300s.
-- ocsp_verified stores sha256(DER); L1 is dropped when on-disk der_sha256 (or file hash) diverges.
-- Returns: true on success; false, "must_staple" when Must-Staple is unmet; false otherwise.
function _M.staple(internalstore, server_name, cert_pem)
	if type(cert_pem) ~= "string" or cert_pem == "" or not internalstore then
		return false
	end

	local blocks = pem_blocks(cert_pem)
	local leaf_pem = blocks[1]
	local must_staple = has_must_staple(leaf_pem)

	if not stapling_enabled(internalstore, server_name) then
		if must_staple then
			log(ngx.ERR, "OCSP-Must-Staple required but OCSP stapling is disabled")
			return false, "must_staple"
		end
		return false
	end

	local ok_ocsp, ocsp = pcall(require, "ngx.ocsp")
	if not ok_ocsp or not ocsp or not ocsp.set_ocsp_status_resp then
		log(ngx.ERR, "OCSP ngx.ocsp is not available, skipping stapling")
		if must_staple then
			return false, "must_staple"
		end
		return false
	end
	local ssl = require "ngx.ssl"

	for _, block_pem in ipairs(blocks) do
		local fingerprint = spki_fingerprint(block_pem, internalstore)
		if fingerprint then
			local issuers = nil
			local cached = get_cached_resp(internalstore, fingerprint)
			if cached then
				if not l1_matches_disk(fingerprint, cached) then
					drop_cache(internalstore, fingerprint)
				elseif is_verified(internalstore, fingerprint, cached) then
					local ok_set, set_ok, set_err = pcall(function()
						return ocsp.set_ocsp_status_resp(cached)
					end)
					if ok_set and set_ok then
						return true
					end
					log(ngx.ERR, "OCSP failed to set stapling from L1: " .. tostring(set_err or set_ok))
					drop_cache(internalstore, fingerprint)
				else
					issuers = issuer_candidates(blocks, block_pem, fingerprint)
					local result = try_staple(ocsp, ssl, cached, block_pem, issuers)
					if result == true then
						warm_cache(internalstore, fingerprint, cached)
						return true
					end
					if result == false then
						if must_staple then
							return false, "must_staple"
						end
						return false
					end
					drop_cache(internalstore, fingerprint)
				end
			end

			local resp = read_file(ocsp_path(fingerprint))
			if resp then
				issuers = issuers or issuer_candidates(blocks, block_pem, fingerprint)
				local result = try_staple(ocsp, ssl, resp, block_pem, issuers)
				if result == true then
					warm_cache(internalstore, fingerprint, resp)
					return true
				end
				if result == false then
					if must_staple then
						return false, "must_staple"
					end
					return false
				end
			end
		end
	end

	if must_staple then
		log(ngx.ERR, "OCSP-Must-Staple required but OCSP response not found")
		return false, "must_staple"
	end
	return false
end

return _M
