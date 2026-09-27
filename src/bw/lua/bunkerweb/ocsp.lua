local _M = {}

local ngx = ngx

local function log(level, msg)
	ngx.log(level, msg)
end

-- variables["global"] and variables["<server name>"], same layout as utils.get_variable.
-- Per-site keys are the primary service id (first SERVER_NAME token). SNI may be a
-- secondary name on that service — resolve before looking up site overrides.
local function resolve_multisite_service_id(vars, sni)
	if not sni or type(vars) ~= "table" then
		return nil
	end
	if type(vars[sni]) == "table" then
		return sni
	end
	local sni_lower = tostring(sni):lower()
	for primary, site_vars in pairs(vars) do
		if primary ~= "global" and type(primary) == "string" and type(site_vars) == "table" then
			if primary:lower() == sni_lower then
				return primary
			end
		end
	end
	for primary, site_vars in pairs(vars) do
		if primary ~= "global" and type(site_vars) == "table" then
			local names = site_vars["SERVER_NAME"]
			if type(names) == "string" then
				for name in names:gmatch("%S+") do
					if name == sni or name:lower() == sni_lower then
						return primary
					end
				end
			end
		end
	end
	return nil
end

-- A per-site value wins. The plugin default is "no".
local function stapling_enabled(internalstore, server_name)
	local ok, vars = pcall(function()
		return internalstore:get("variables", true)
	end)
	if not ok or type(vars) ~= "table" or type(vars["global"]) ~= "table" then
		return false
	end
	local value = vars["global"]["SSL_USE_OCSP_STAPLING"]
	if vars["global"]["MULTISITE"] == "yes" and server_name then
		local service_id = resolve_multisite_service_id(vars, server_name)
		if service_id and type(vars[service_id]) == "table" then
			local site_value = vars[service_id]["SSL_USE_OCSP_STAPLING"]
			if site_value ~= nil then
				value = site_value
			end
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
-- Do not memoize by ngx.md5(cert_pem): PEM whitespace/rewrap changes the key while
-- the SPKI is identical, which caused cache misses and path skew vs the job.
local function spki_fingerprint(cert_pem, _internalstore)
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
	if is_fp64(fingerprint) then
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

-- Legacy sibling keys (pre-composite L1). Still deleted on write/drop for upgrades.
local function verified_key(fingerprint)
	return "TLS:SSL:ocsp_verified:" .. fingerprint
end

local function gen_key(fingerprint)
	return "TLS:SSL:ocsp_gen:" .. fingerprint
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

-- One shm value = epoch + optional verified binding + expires_unix + DER.
-- Evicting this key cannot orphan verified from DER (or gen from DER).
-- Layout v2: "bw2\0" .. epoch .. "\0" .. binding .. "\0" .. expires_unix .. "\0" .. der
-- Layout v1 (legacy): "bw1\0" .. epoch .. "\0" .. binding .. "\0" .. der
local L1_MAGIC = "bw2\0"
local L1_MAGIC_V1 = "bw1\0"
-- Cap DRAM residence; never longer than remaining OCSP life when known.
local L1_MAX_TTL = 300

local function l1_shm_ttl(expires_unix)
	if type(expires_unix) ~= "number" or expires_unix <= 0 then
		return L1_MAX_TTL
	end
	local remaining = expires_unix - ngx.time()
	if remaining <= 0 then
		return nil
	end
	if remaining > L1_MAX_TTL then
		return L1_MAX_TTL
	end
	return remaining
end

local function pack_l1(epoch, verified_binding, der, expires_unix)
	local exp = ""
	if type(expires_unix) == "number" and expires_unix > 0 then
		exp = tostring(math.floor(expires_unix))
	elseif type(expires_unix) == "string" and expires_unix:match("^%d+$") then
		exp = expires_unix
	end
	return L1_MAGIC .. (epoch or "0") .. "\0" .. (verified_binding or "") .. "\0" .. exp .. "\0" .. der
end

local function unpack_l1(blob)
	if type(blob) ~= "string" or #blob < 4 then
		return nil, nil, nil, nil
	end
	local magic = blob:sub(1, 4)
	if magic == L1_MAGIC then
		local epoch, binding, exp, der = blob:sub(5):match("^([^\0]*)\0([^\0]*)\0([^\0]*)\0(.*)$")
		if type(der) ~= "string" or #der == 0 then
			return nil, nil, nil, nil
		end
		if binding == "" then
			binding = nil
		end
		local expires_unix = nil
		if type(exp) == "string" and exp:match("^%d+$") then
			expires_unix = tonumber(exp)
		end
		return epoch or "0", binding, der, expires_unix
	end
	if magic == L1_MAGIC_V1 then
		local epoch, binding, der = blob:sub(5):match("^([^\0]*)\0([^\0]*)\0(.*)$")
		if type(der) ~= "string" or #der == 0 then
			return nil, nil, nil, nil
		end
		if binding == "" then
			binding = nil
		end
		return epoch or "0", binding, der, nil
	end
	return nil, nil, nil, nil
end

-- Shared with the HTTP ssl_certificate path: job bumps this file so both
-- internalstore and internalstore_stream drop stale L1 without cross-dict APIs.
local OCSP_EPOCH_PATH = "/var/cache/bunkerweb/ssl/.ocsp_epoch"

local function current_ocsp_epoch()
	if ngx.ctx.bw_ocsp_epoch ~= nil then
		return ngx.ctx.bw_ocsp_epoch
	end
	local epoch = "0"
	pcall(function()
		local f = io.open(OCSP_EPOCH_PATH, "r")
		if not f then
			return
		end
		local raw = f:read("*l")
		f:close()
		if type(raw) == "string" and #raw > 0 then
			epoch = raw:match("^%S+") or "0"
		end
	end)
	ngx.ctx.bw_ocsp_epoch = epoch
	return epoch
end

-- Returns der, verified_binding, epoch, expires_unix (or nil).
-- Legacy raw-DER (+ sibling verified/gen keys) is promoted to the composite once.
local function get_l1(internalstore, fingerprint)
	if not internalstore or not fingerprint then
		return nil
	end
	local ok, blob = pcall(function()
		return internalstore:get(cache_key(fingerprint), true)
	end)
	if not ok or type(blob) ~= "string" or #blob == 0 then
		return nil
	end

	local epoch, verified, der, expires_unix = unpack_l1(blob)
	if der then
		return der, verified, epoch, expires_unix
	end

	-- Legacy: bare DER body under the same key.
	der = blob
	local binding = nil
	pcall(function()
		local stored = internalstore:get(verified_key(fingerprint), true)
		if type(stored) == "string" and stored == resp_binding(der) then
			binding = stored
		end
	end)
	epoch = "0"
	pcall(function()
		local stored_gen = internalstore:get(gen_key(fingerprint), true)
		if type(stored_gen) == "string" and #stored_gen > 0 then
			epoch = stored_gen
		end
	end)
	pcall(function()
		local ttl = l1_shm_ttl(nil)
		if ttl then
			internalstore:set(cache_key(fingerprint), pack_l1(epoch, binding, der, nil), ttl, true)
		end
		internalstore:delete(verified_key(fingerprint))
		internalstore:delete(gen_key(fingerprint))
	end)
	return der, binding, epoch, nil
end

local function entry_verified(stored_binding, resp)
	local binding = resp_binding(resp)
	return binding ~= nil and stored_binding == binding
end

local function warm_cache(internalstore, fingerprint, resp, mark_verified, expires_unix)
	-- mark_verified=false: cache DER for reuse but do not skip crypto on later hits.
	-- Only PEM + validate_ocsp_response (or a prior verified binding) may set verified.
	if mark_verified == nil then
		mark_verified = true
	end
	if type(resp) ~= "string" or #resp == 0 then
		return
	end
	local ttl = l1_shm_ttl(expires_unix)
	if not ttl then
		-- Response already past nextUpdate; do not park it in L1.
		return
	end
	local binding = nil
	if mark_verified then
		binding = resp_binding(resp)
	end
	local epoch = current_ocsp_epoch()
	pcall(function()
		internalstore:set(cache_key(fingerprint), pack_l1(epoch, binding, resp, expires_unix), ttl, true)
		-- Drop pre-composite siblings so they cannot outlive / contradict this entry.
		internalstore:delete(verified_key(fingerprint))
		internalstore:delete(gen_key(fingerprint))
	end)
end

-- Throttle L1 disk freshness checks (re-read ocsp.json at most this often per fp).
local L1_DISK_CHECK_SECONDS = 5

local function l1_disk_check_key(fingerprint)
	return "TLS:SSL:ocsp_diskcheck:" .. fingerprint
end

local function drop_cache(internalstore, fingerprint)
	pcall(function()
		internalstore:delete(cache_key(fingerprint))
		internalstore:delete(verified_key(fingerprint))
		internalstore:delete(l1_disk_check_key(fingerprint))
		internalstore:delete(gen_key(fingerprint))
	end)
end

-- True when L1 DER still matches on-disk ocsp.der (job may have replaced the file).
local function l1_matches_disk(internalstore, fingerprint, resp, stored_epoch)
	local binding = resp_binding(resp)
	if not binding then
		return false
	end

	-- Cross-zone coherence: job cannot delete the other lua_shared_dict; epoch is the bus.
	if (stored_epoch or "") ~= current_ocsp_epoch() then
		return false
	end

	-- Skip repeated disk I/O within the throttle window when last check said OK.
	if internalstore then
		local ok_cached, cached_binding = pcall(function()
			return internalstore:get(l1_disk_check_key(fingerprint), true)
		end)
		if ok_cached and cached_binding == binding then
			return true
		end
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

	local matches
	if disk_sha then
		matches = disk_sha == binding
	else
		local data = read_file(ocsp_path(fingerprint))
		if not data then
			matches = false
		else
			matches = resp_binding(data) == binding
		end
	end

	if matches and internalstore then
		pcall(function()
			internalstore:set(l1_disk_check_key(fingerprint), binding, L1_DISK_CHECK_SECONDS, true)
		end)
	end
	return matches
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
	-- Newer OpenResty returns true, next_update; older returns true only.
	-- Some builds already reject past nextUpdate inside the FFI call.
	local ok_call, validate_ok, next_update = pcall(function()
		return ocsp.validate_ocsp_response(ocsp_der, der_chain)
	end)
	if not ok_call or validate_ok ~= true then
		return false
	end
	if type(next_update) == "number" and next_update > 0 and next_update <= ngx.time() then
		log(ngx.DEBUG, "OCSP validate rejected: nextUpdate in the past")
		return false
	end
	return true
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

local function read_ocsp_json(fingerprint)
	if not is_fp64(fingerprint) then
		return nil
	end
	local raw = read_file(
		"/var/cache/bunkerweb/ssl/"
			.. fingerprint:sub(1, 1)
			.. "/"
			.. fingerprint:sub(2, 2)
			.. "/"
			.. fingerprint
			.. "/ocsp.json"
	)
	if not raw then
		return nil
	end
	local ok, decoded = pcall(function()
		return require("cjson").decode(raw)
	end)
	if ok and type(decoded) == "table" then
		return decoded
	end
	return nil
end

local function ocsp_json_must_staple(meta)
	return meta ~= nil and meta.must_staple == true
end

local function ocsp_json_fingerprint_matches(meta, fingerprint)
	if not meta or type(meta.fingerprint) ~= "string" then
		return false
	end
	return meta.fingerprint:lower() == fingerprint
end

-- Fingerprint-hint path cannot call validate_ocsp_response (no leaf PEM).
-- Require meta.fingerprint match AND der_sha256 == sha256(body) so a swapped
-- ocsp.der under matching SPKI meta cannot be stapled.
local function ocsp_json_authorizes_resp(meta, fingerprint, resp)
	if not ocsp_json_fingerprint_matches(meta, fingerprint) then
		return false
	end
	if type(meta.der_sha256) ~= "string" then
		return false
	end
	local meta_sha = meta.der_sha256:lower()
	if #meta_sha ~= 64 or not meta_sha:match("^[0-9a-f]+$") then
		return false
	end
	local body_sha = resp_binding(resp)
	return body_sha ~= nil and body_sha == meta_sha
end

-- Absolute unix nextUpdate from job meta (preferred) or legacy "iso + Ns" expires.
local function meta_expires_unix(meta)
	if type(meta) ~= "table" then
		return nil
	end
	local u = meta.expires_unix
	if type(u) == "number" and u > 0 then
		return math.floor(u)
	end
	if type(u) == "string" then
		local n = tonumber(u)
		if n and n > 0 then
			return math.floor(n)
		end
	end
	local raw = meta.expires
	if type(raw) ~= "string" then
		return nil
	end
	local base_str, ttl_str = raw:match("^(.-) %+ (%d+)%s*s%s*$")
	if not base_str or not ttl_str then
		return nil
	end
	local y, mo, d, H, M, S = base_str:match("^(%d%d%d%d)%-(%d%d)%-(%d%d)T(%d%d):(%d%d):(%d%d)")
	if not y then
		return nil
	end
	-- Treat components as UTC (job writes timezone.utc isoformat).
	local ok_ts, ts = pcall(os.time, {
		year = tonumber(y),
		month = tonumber(mo),
		day = tonumber(d),
		hour = tonumber(H),
		min = tonumber(M),
		sec = tonumber(S),
		isdst = false,
	})
	if not ok_ts or type(ts) ~= "number" then
		return nil
	end
	local ok_off, offset = pcall(function()
		return os.difftime(os.time(), os.time(os.date("!*t", os.time())))
	end)
	if ok_off and type(offset) == "number" then
		ts = ts - offset
	end
	return ts + tonumber(ttl_str)
end

-- False when we know nextUpdate/expires is past. Unknown expiry → true (PEM validate may still enforce).
local function resp_still_fresh(expires_unix, fingerprint, meta)
	local exp = expires_unix
	if not exp then
		meta = meta or read_ocsp_json(fingerprint)
		exp = meta_expires_unix(meta)
	end
	if not exp then
		return true
	end
	if ngx.time() >= exp then
		return false
	end
	return true
end

local function normalize_fp_hint(cert_fp_hint)
	if type(cert_fp_hint) ~= "string" then
		return nil
	end
	local fp = cert_fp_hint:lower()
	if is_fp64(fp) then
		return fp
	end
	return nil
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

-- Classify leaf PEM as "ec", "rsa", or nil (for dual-cert staple selection).
local function cert_pubkey_kind(cert_pem)
	if type(cert_pem) ~= "string" or cert_pem == "" then
		return nil
	end
	local kind = nil
	pcall(function()
		local x509 = require("resty.openssl.x509")
		local cert_obj = x509.new(cert_pem)
		local pub = cert_obj and cert_obj:get_pubkey()
		if not pub then
			return
		end
		local key_type = pub.get_key_type and pub:get_key_type() or nil
		local label = key_type
		if type(key_type) == "table" then
			label = key_type.sn or key_type.ln or key_type.nid
		end
		label = tostring(label or ""):lower()
		if label:find("ec", 1, true) or label:find("id-ec", 1, true) then
			kind = "ec"
		elseif label:find("rsa", 1, true) then
			kind = "rsa"
		end
	end)
	return kind
end

-- ngx.ocsp has one status slot. Prefer ECDSA when RSA+ECDSA leaves are both present.
local function select_preferred_leaf(blocks)
	-- Prefer ECDSA among *leaves* (key-matched PEMs from set_certs_from_pem).
	-- Callers that pass a fullchain must use the first block only — see staple().
	if not blocks or #blocks == 0 then
		return nil
	end
	if #blocks == 1 then
		return blocks[1]
	end
	local ec_leaf, rsa_leaf, other_leaf = nil, nil, nil
	for _, block in ipairs(blocks) do
		local kind = cert_pubkey_kind(block)
		if kind == "ec" and not ec_leaf then
			ec_leaf = block
		elseif kind == "rsa" and not rsa_leaf then
			rsa_leaf = block
		elseif not other_leaf then
			other_leaf = block
		end
	end
	if ec_leaf and rsa_leaf then
		log(
			ngx.NOTICE,
			"OCSP multi-certificate PEM: stapling ECDSA leaf only "
				.. "(ngx.ocsp has one status slot; RSA leaf will not be stapled)"
		)
		return ec_leaf
	end
	return ec_leaf or rsa_leaf or other_leaf or blocks[1]
end

local function parse_pem_keys(pem_data)
	local keys = {}
	if type(pem_data) ~= "string" or pem_data == "" then
		return keys
	end
	local current_key = nil
	local in_key = false
	for line in pem_data:gmatch("[^\n]+") do
		if line:find("-----BEGIN", 1, true) and line:find("PRIVATE KEY", 1, true) then
			in_key = true
			current_key = line
		elseif in_key and current_key then
			current_key = current_key .. "\n" .. line
			if line:find("-----END", 1, true) and line:find("PRIVATE KEY", 1, true) then
				keys[#keys + 1] = current_key
				current_key = nil
				in_key = false
			end
		end
	end
	return keys
end

local function key_spki_fingerprint(key_pem)
	local fingerprint = nil
	pcall(function()
		local pkey = require("resty.openssl.pkey")
		local digest_lib = require("resty.openssl.digest")
		local key_obj = pkey.new(key_pem)
		if not key_obj then
			return
		end
		local pubkey_der = key_obj:tostring(false, "DER")
		if not pubkey_der then
			return
		end
		local digest_ctx = digest_lib.new("sha256")
		digest_ctx:update(pubkey_der)
		fingerprint = to_hex(digest_ctx:final())
	end)
	return fingerprint
end

local function cert_spki_fingerprint(cert_pem)
	local fingerprint = nil
	pcall(function()
		local x509 = require("resty.openssl.x509")
		local digest_lib = require("resty.openssl.digest")
		local cert_obj = x509.new(cert_pem)
		local pub = cert_obj and cert_obj:get_pubkey()
		local spki = pub and pub:tostring("public", "DER")
		if not spki then
			return
		end
		local digest_ctx = digest_lib.new("sha256")
		digest_ctx:update(spki)
		fingerprint = to_hex(digest_ctx:final())
	end)
	return fingerprint
end

-- Install all leaf/key pairs from PEM (dual-cert aware). Returns preferred leaf PEM + SPKI fp
-- for OCSP (ECDSA preferred when both RSA and ECDSA leaves are present).
-- Returns: true, leaf_pem, leaf_fp  OR  false, err_msg
function _M.set_certs_from_pem(cert_pem, key_pem)
	if type(cert_pem) ~= "string" or cert_pem == "" or type(key_pem) ~= "string" or key_pem == "" then
		return false, "cert_pem and key_pem strings are required"
	end
	local ssl = require "ngx.ssl"
	if not ssl.parse_pem_cert or not ssl.parse_pem_priv_key or not ssl.set_cert or not ssl.set_priv_key then
		return false, "ngx.ssl PEM helpers are unavailable"
	end

	local certs = pem_blocks(cert_pem)
	local keys = parse_pem_keys(key_pem)
	if #certs == 0 then
		return false, "no certificates found in PEM"
	end
	if #keys == 0 then
		return false, "no private keys found in PEM"
	end

	local key_fps = {}
	for i, key in ipairs(keys) do
		key_fps[i] = key_spki_fingerprint(key)
	end

	local leaves = {}
	local intermediates = {}
	for _, block in ipairs(certs) do
		local fp = cert_spki_fingerprint(block)
		local matched_key = nil
		if fp then
			for key_idx, key_fp in ipairs(key_fps) do
				if key_fp and key_fp == fp then
					matched_key = keys[key_idx]
					break
				end
			end
		end
		if matched_key then
			leaves[#leaves + 1] = { pem = block, key = matched_key, fp = fp }
		else
			intermediates[#intermediates + 1] = block
		end
	end

	if #leaves == 0 then
		return false, "no certificate matched any private key"
	end

	local installed = {}
	for _, leaf in ipairs(leaves) do
		local chain_pem = leaf.pem
		for _, intermediate in ipairs(intermediates) do
			chain_pem = chain_pem .. "\n" .. intermediate
		end
		local parsed_cert, cert_err = ssl.parse_pem_cert(chain_pem)
		local parsed_key, key_err = ssl.parse_pem_priv_key(leaf.key)
		if not parsed_cert or not parsed_key then
			return false, "failed to parse cert/key: " .. tostring(cert_err or key_err)
		end
		local ok_cert, err_cert = ssl.set_cert(parsed_cert)
		if not ok_cert then
			return false, "set_cert failed: " .. tostring(err_cert)
		end
		local ok_key, err_key = ssl.set_priv_key(parsed_key)
		if not ok_key then
			return false, "set_priv_key failed: " .. tostring(err_key)
		end
		installed[#installed + 1] = leaf
	end

	local leaf_pems = {}
	for _, leaf in ipairs(installed) do
		leaf_pems[#leaf_pems + 1] = leaf.pem
	end
	local preferred_pem = select_preferred_leaf(leaf_pems)
	local preferred_fp = nil
	for _, leaf in ipairs(installed) do
		if leaf.pem == preferred_pem then
			preferred_fp = leaf.fp
			break
		end
	end
	return true, preferred_pem, preferred_fp
end

-- Staple using only a precomputed SPKI fingerprint (plugin status[5]) when PEM is unavailable.
-- Acceptance: prior crypto-verified L1 binding, or job meta that binds fingerprint + der_sha256
-- to the exact DER bytes. Never promote fingerprint-only accepts to ocsp_verified.
local function staple_from_fingerprint(internalstore, server_name, fingerprint)
	local meta = read_ocsp_json(fingerprint)
	local must_staple = ocsp_json_must_staple(meta)
	if must_staple then
		log(ngx.INFO, "OCSP-Must-Staple from ocsp.json for fp=" .. fingerprint:sub(1, 16) .. "...")
	end

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

	local cached, cached_verified, cached_epoch, cached_expires = get_l1(internalstore, fingerprint)
	if cached then
		if not l1_matches_disk(internalstore, fingerprint, cached, cached_epoch) then
			drop_cache(internalstore, fingerprint)
		elseif not resp_still_fresh(cached_expires, fingerprint, meta) then
			log(ngx.ERR, "OCSP L1 response past nextUpdate/expires; discarding fp=" .. fingerprint:sub(1, 16) .. "...")
			drop_cache(internalstore, fingerprint)
		else
			local verified = entry_verified(cached_verified, cached)
			local authorized = ocsp_json_authorizes_resp(meta, fingerprint, cached)
			if verified or authorized then
				local ok_set, set_ok, set_err = pcall(function()
					return ocsp.set_ocsp_status_resp(cached)
				end)
				if ok_set and set_ok then
					local exp = cached_expires or meta_expires_unix(meta)
					-- Only re-warm verified if crypto already proved this body.
					if verified then
						warm_cache(internalstore, fingerprint, cached, true, exp)
					else
						warm_cache(internalstore, fingerprint, cached, false, exp)
					end
					return true
				end
				log(ngx.ERR, "OCSP failed to set stapling from L1: " .. tostring(set_err or set_ok))
				drop_cache(internalstore, fingerprint)
			end
		end
	end

	local resp = read_file(ocsp_path(fingerprint))
	if resp then
		if not resp_still_fresh(nil, fingerprint, meta) then
			log(ngx.ERR, "OCSP disk response past nextUpdate/expires; refusing staple fp=" .. fingerprint:sub(1, 16) .. "...")
			if must_staple then
				return false, "must_staple"
			end
			return false
		end
		-- Disk path: verified binding only exists in L1; after drop/miss, require meta authorize
		-- or a leftover legacy sibling (get_l1 already promoted). Re-check composite if rewarmed.
		local _, disk_verified = get_l1(internalstore, fingerprint)
		local verified = entry_verified(disk_verified, resp)
		local authorized = ocsp_json_authorizes_resp(meta, fingerprint, resp)
		if verified or authorized then
			local ok_set, set_ok, set_err = pcall(function()
				return ocsp.set_ocsp_status_resp(resp)
			end)
			if ok_set and set_ok then
				warm_cache(internalstore, fingerprint, resp, verified, meta_expires_unix(meta))
				return true
			end
			log(ngx.ERR, "OCSP failed to set stapling: " .. tostring(set_err or set_ok))
			if must_staple then
				return false, "must_staple"
			end
			return false
		end
	end

	if must_staple then
		log(ngx.ERR, "OCSP-Must-Staple required but OCSP response not found")
		return false, "must_staple"
	end
	return false
end

local function staple_one_leaf(internalstore, ocsp, ssl, blocks, leaf_pem, fingerprint, must_staple)
	if not fingerprint then
		return nil
	end
	local issuers = nil
	local cached, cached_verified, cached_epoch, cached_expires = get_l1(internalstore, fingerprint)
	if cached then
		if not l1_matches_disk(internalstore, fingerprint, cached, cached_epoch) then
			drop_cache(internalstore, fingerprint)
		elseif not resp_still_fresh(cached_expires, fingerprint, nil) then
			log(ngx.ERR, "OCSP L1 response past nextUpdate/expires; discarding fp=" .. fingerprint:sub(1, 16) .. "...")
			drop_cache(internalstore, fingerprint)
		elseif entry_verified(cached_verified, cached) then
			local ok_set, set_ok, set_err = pcall(function()
				return ocsp.set_ocsp_status_resp(cached)
			end)
			if ok_set and set_ok then
				return true
			end
			log(ngx.ERR, "OCSP failed to set stapling from L1: " .. tostring(set_err or set_ok))
			drop_cache(internalstore, fingerprint)
		else
			issuers = issuer_candidates(blocks, leaf_pem, fingerprint)
			local result = try_staple(ocsp, ssl, cached, leaf_pem, issuers)
			if result == true then
				warm_cache(internalstore, fingerprint, cached, true, cached_expires or meta_expires_unix(read_ocsp_json(fingerprint)))
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
		local meta = read_ocsp_json(fingerprint)
		if not resp_still_fresh(nil, fingerprint, meta) then
			log(ngx.ERR, "OCSP disk response past nextUpdate/expires; refusing staple fp=" .. fingerprint:sub(1, 16) .. "...")
			if must_staple then
				return false, "must_staple"
			end
			return false
		end
		issuers = issuers or issuer_candidates(blocks, leaf_pem, fingerprint)
		local result = try_staple(ocsp, ssl, resp, leaf_pem, issuers)
		if result == true then
			warm_cache(internalstore, fingerprint, resp, true, meta_expires_unix(meta))
			return true
		end
		if result == false then
			if must_staple then
				return false, "must_staple"
			end
			return false
		end
	end
	return nil
end

-- Staple a cached OCSP response for cert_pem. Used by the stream TLS handshake.
-- HTTP uses ngx.shared.internalstore; stream uses internalstore_stream. Same key layout
-- (TLS:SSL:ocsp: composite of epoch|verified|expires|DER) so each subsystem warms its own L1.
-- Shm TTL is min(300s, remaining until expires_unix) so DRAM cannot outlive nextUpdate.
-- Verified binding is sha256(DER) packed with the body; L1 drops when epoch or der_sha256 diverges.
-- Optional cert_fp_hint (plugin status[5]) enforces Must-Staple via ocsp.json when PEM is absent.
-- Dual-cert PEMs staple the ECDSA leaf only (one ngx.ocsp status slot).
-- Returns: true on success; false, "must_staple" when Must-Staple is unmet; false otherwise.
function _M.staple(internalstore, server_name, cert_pem, cert_fp_hint)
	if not internalstore then
		return false
	end

	local pem_ok = type(cert_pem) == "string" and cert_pem ~= ""
	local fp_hint = normalize_fp_hint(cert_fp_hint)

	if not pem_ok then
		if fp_hint then
			return staple_from_fingerprint(internalstore, server_name, fp_hint)
		end
		return false
	end

	local blocks = pem_blocks(cert_pem)
	-- Fullchain order: first block is the leaf. Do not scan intermediates for key type
	-- (an ECDSA intermediate would steal the staple from an RSA leaf).
	local leaf_pem = blocks[1]
	if not leaf_pem then
		return false
	end
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

	-- Prefer fingerprint of the selected leaf; fall back to plugin hint only if it matches that leaf.
	local leaf_fp = spki_fingerprint(leaf_pem, internalstore)
	if fp_hint and leaf_fp and fp_hint ~= leaf_fp then
		-- Plugin hint is often the first PEM block (may be RSA). Ignore it for dual-cert ECDSA prefer.
		fp_hint = nil
	end
	local fingerprint = leaf_fp or fp_hint

	local result, reason = staple_one_leaf(internalstore, ocsp, ssl, blocks, leaf_pem, fingerprint, must_staple)
	if result == true then
		return true
	end
	if result == false then
		return false, reason
	end

	if must_staple then
		log(ngx.ERR, "OCSP-Must-Staple required but OCSP response not found")
		return false, "must_staple"
	end
	return false
end

return _M
