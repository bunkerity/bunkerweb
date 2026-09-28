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

-- Read a multisite setting: per-site (primary service id) wins over global.
local function get_site_variable(internalstore, server_name, name)
	local ok, vars = pcall(function()
		return internalstore:get("variables", true)
	end)
	if not ok or type(vars) ~= "table" or type(vars["global"]) ~= "table" then
		return nil
	end
	local value = vars["global"][name]
	if vars["global"]["MULTISITE"] == "yes" and server_name then
		local service_id = resolve_multisite_service_id(vars, server_name)
		if service_id and type(vars[service_id]) == "table" then
			local site_value = vars[service_id][name]
			if site_value ~= nil then
				value = site_value
			end
		end
	end
	return value
end

-- A per-site value wins. The plugin default is "no".
local function stapling_enabled(internalstore, server_name)
	local value = get_site_variable(internalstore, server_name, "SSL_USE_OCSP_STAPLING")
	if type(value) == "boolean" then
		return value
	end
	if value == nil then
		return false
	end
	local str = tostring(value):lower()
	return str == "1" or str == "true" or str == "on" or str == "yes"
end

-- Must-Staple fuse both HTTP and stream read. Default "normal" (fail-close).
-- staple_only / open soft-continue instead of aborting the handshake.
local function ocsp_staple_mode(internalstore, server_name)
	local value = get_site_variable(internalstore, server_name, "OCSP_STAPLE_MODE")
	if value == nil or value == "" then
		return "normal"
	end
	local str = tostring(value):lower()
	if str == "staple_only" or str == "open" or str == "normal" then
		return str
	end
	return "normal"
end

-- Convert a Must-Staple miss into abort (normal) or soft continue (fuse).
-- Always logs OCSP_MUST_STAPLE_REFUSE (never the optional OCSP_STAPLING_OFF wording).
local function soften_must_staple(mode, ok, reason, detail)
	if reason ~= "must_staple" then
		return ok, reason
	end
	local action = "abort"
	if mode == "staple_only" or mode == "open" then
		action = "continue"
	end
	log(
		ngx.ERR,
		"OCSP_MUST_STAPLE_REFUSE reason="
			.. tostring(detail or "unmet")
			.. " action="
			.. action
			.. " mode="
			.. tostring(mode or "normal")
	)
	if action == "continue" then
		return false
	end
	return false, "must_staple"
end

-- Optional stapling skipped (no Must-Staple). Distinct from OCSP_MUST_STAPLE_REFUSE.
local function log_stapling_off(reason)
	log(ngx.DEBUG, "OCSP_STAPLING_OFF reason=" .. tostring(reason or "ssl_use_ocsp_stapling_no"))
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

-- Declared clock-skew budget. Must match ocsp-refresh.py OCSP_CLOCK_SKEW_SECONDS.
-- Death time = expires_unix/max_age minus skew: stop stapling before the CA's
-- advertised nextUpdate so a lagging worker clock cannot serve a dead response.
local OCSP_CLOCK_SKEW_SECONDS = 300
-- Signed-window policy; must match ocsp-refresh.py.
local OCSP_MAX_INTRINSIC_LIFETIME_SECONDS = 7 * 24 * 3600
local OCSP_MAX_THIS_UPDATE_AGE_SECONDS = 7 * 24 * 3600

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
	-- Drop L1 at death time (expires_unix - skew), same as resp_still_fresh.
	local remaining = expires_unix - OCSP_CLOCK_SKEW_SECONDS - ngx.time()
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

-- Legacy diskcheck key (pre-fix throttle). Still deleted on drop so old entries vanish.
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
-- Always re-read ocsp.json der_sha256 (or hash the file). A 5s "last OK" short-circuit
-- stapled pre-replace DER after a job swap; epoch alone does not cover no-bump writes.
local function l1_matches_disk(internalstore, fingerprint, resp, stored_epoch)
	local binding = resp_binding(resp)
	if not binding then
		return false
	end

	-- Cross-zone coherence: job cannot delete the other lua_shared_dict; epoch is the bus.
	if (stored_epoch or "") ~= current_ocsp_epoch() then
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

local function issuer_candidates(blocks, leaf_pem, fingerprint)
	-- When the shard has issuer.pem, only accept that issuer SPKI (or an identical
	-- re-encoding from the chain). Do not let validate succeed against a different CA.
	local stored = nil
	if fingerprint then
		stored = read_file(issuer_path(fingerprint))
	end
	local want_spki = stored and spki_fingerprint(stored) or nil

	local issuers = {}
	local seen = {}
	local function add(pem)
		if type(pem) ~= "string" or pem == "" or seen[pem] then
			return
		end
		if want_spki then
			local got = spki_fingerprint(pem)
			if not got or got ~= want_spki then
				return
			end
		end
		seen[pem] = true
		issuers[#issuers + 1] = pem
	end

	add(stored)
	for _, other in ipairs(blocks) do
		if other ~= leaf_pem then
			add(other)
		end
	end
	return issuers
end

local function validate(ocsp, ssl, ocsp_der, leaf_pem, issuer_pem, shard_issuer_spki)
	if not issuer_pem or issuer_pem == "" or not ssl.cert_pem_to_der then
		return false
	end
	-- Explicit pin: candidate issuer SPKI must match the shard's issuer.pem.
	if type(shard_issuer_spki) == "string" and #shard_issuer_spki == 64 then
		local got = spki_fingerprint(issuer_pem)
		if not got or got ~= shard_issuer_spki then
			log(ngx.ERR, "OCSP validate refuse: issuer SPKI does not match shard issuer")
			return false
		end
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
	-- Death time = nextUpdate - skew.
	if type(next_update) == "number" and next_update > 0 and next_update - OCSP_CLOCK_SKEW_SECONDS <= ngx.time() then
		log(ngx.DEBUG, "OCSP validate rejected: past death time (nextUpdate - skew)")
		return false
	end
	return true
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
	-- extension text only (never a full openssl dump).
	for token in text:gmatch("%d+") do
		if token == "5" then
			return true
		end
	end
	return false
end

-- Handshake path: resty.openssl only — no /tmp + openssl CLI. Callers also consult
-- ocsp.json (written by ocsp-refresh) when resty cannot see Must-Staple.
local function has_must_staple(cert_pem)
	if type(cert_pem) ~= "string" or cert_pem == "" then
		return false
	end
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

-- Colony floor: peers advance ocsp-floor/{fp} on publish/tombstone using wall-clock
-- published_unix (not job_run_id — pid.time_ns is not colony-comparable).
-- Must-Staple stays closed while local ocsp.json published_unix is below the floor.
local function meta_published_unix(meta)
	if type(meta) ~= "table" then
		return 0
	end
	local u = meta.published_unix
	if type(u) == "number" and u > 0 then
		return math.floor(u)
	end
	if type(u) == "string" then
		local n = tonumber(u)
		if n and n > 0 then
			return math.floor(n)
		end
	end
	return 0
end

local function parse_floor_published_unix(raw)
	if type(raw) ~= "string" or raw == "" then
		return 0
	end
	local trimmed = raw:match("^%s*(.-)%s*$") or raw
	if trimmed:sub(1, 1) == "{" then
		local ok, decoded = pcall(function()
			return require("cjson").decode(trimmed)
		end)
		if ok and type(decoded) == "table" then
			return meta_published_unix(decoded)
		end
		return 0
	end
	local token = trimmed:match("^(%d+)")
	return tonumber(token) or 0
end

local function cluster_floor_blocks(fingerprint, meta)
	if not is_fp64(fingerprint) then
		return false
	end
	local raw = read_file("/var/cache/bunkerweb/ssl/ocsp-floor/" .. fingerprint)
	local floor_pub = parse_floor_published_unix(raw)
	if floor_pub <= 0 then
		return false
	end
	local local_pub = meta_published_unix(meta)
	if local_pub >= floor_pub then
		return false
	end
	log(
		ngx.ERR,
		"OCSP cluster floor ahead of local published_unix; Must-Staple closed fp="
			.. fingerprint:sub(1, 16)
			.. "... floor="
			.. tostring(floor_pub)
			.. " local="
			.. tostring(local_pub)
	)
	return true
end

-- Live shard must be scheduler-paged (canary handshake) before stapling.
-- Legacy meta without the field is treated as already paged.
local function shard_not_paged(meta)
	if type(meta) ~= "table" then
		return false
	end
	return meta.paged == false
end

-- serial-blacklist.json bans one leaf serial until a newer GOOD is published.
-- A different serial (reissue on the same key) is allowed. Unreadable serial
-- while the file exists fails closed.
local function serial_blacklist_blocks(fingerprint, resp)
	if not is_fp64(fingerprint) or type(resp) ~= "string" or resp == "" then
		return false
	end
	local raw = read_file(
		"/var/cache/bunkerweb/ssl/"
			.. fingerprint:sub(1, 1)
			.. "/"
			.. fingerprint:sub(2, 2)
			.. "/"
			.. fingerprint
			.. "/serial-blacklist.json"
	)
	if not raw or raw == "" then
		return false
	end
	local banned_hex = raw:match('"serial_hex"%s*:%s*"([0-9A-Fa-f]+)"')
	if not banned_hex then
		log(ngx.ERR, "OCSP serial blacklist unreadable; refusing staple fp=" .. fingerprint:sub(1, 16) .. "...")
		return true
	end
	banned_hex = banned_hex:upper():gsub("^0+", "")
	if banned_hex == "" then
		banned_hex = "0"
	end
	local got_hex = nil
	pcall(function()
		local ocsp_lib = require("resty.openssl.ocsp")
		local parsed = ocsp_lib.new(resp)
		if not parsed then
			return
		end
		local serial = parsed:get_serial()
		if type(serial) == "table" and serial.to_hex then
			got_hex = serial:to_hex()
		elseif serial ~= nil then
			got_hex = tostring(serial)
		end
	end)
	if type(got_hex) ~= "string" then
		log(ngx.ERR, "OCSP serial blacklist present but response serial unreadable; refusing staple fp=" .. fingerprint:sub(1, 16) .. "...")
		return true
	end
	got_hex = got_hex:upper():gsub("%s+", ""):gsub("^0X", ""):gsub("^0+", "")
	if got_hex == "" then
		got_hex = "0"
	end
	if not got_hex:match("^[0-9A-F]+$") then
		log(ngx.ERR, "OCSP serial blacklist present but response serial unreadable; refusing staple fp=" .. fingerprint:sub(1, 16) .. "...")
		return true
	end
	if got_hex == banned_hex then
		log(ngx.ERR, "OCSP serial blacklist refuse staple fp=" .. fingerprint:sub(1, 16) .. "... serial_hex=" .. banned_hex:sub(1, 16))
		return true
	end
	return false
end

-- Canonical uppercase hex serial without leading zeros (decimal BN → hex when needed).
local function canonical_serial_hex(serial)
	if serial == nil then
		return nil
	end
	if type(serial) == "table" then
		if serial.to_hex then
			local ok_hex, hex = pcall(function()
				return serial:to_hex()
			end)
			if ok_hex and type(hex) == "string" and #hex > 0 then
				hex = hex:upper():gsub("^0+", "")
				return hex == "" and "0" or hex
			end
		end
		if serial.to_number then
			local ok_n, n = pcall(function()
				return serial:to_number()
			end)
			if ok_n and type(n) == "number" then
				serial = n
			end
		end
	end
	if type(serial) == "number" then
		-- Format as hex without 0x; strip leading zeros.
		local hex = string.format("%X", serial)
		hex = hex:gsub("^0+", "")
		return hex == "" and "0" or hex
	end
	if type(serial) ~= "string" then
		serial = tostring(serial)
	end
	if serial == "" then
		return nil
	end
	serial = serial:upper():gsub("%s+", ""):gsub("^0X", "")
	-- Decimal digit-only strings from some BN tostring paths.
	if serial:match("^[0-9]+$") and not serial:match("^[0-9A-F]*[A-F]") then
		-- Pure decimal: convert via resty BN when available.
		local converted = nil
		pcall(function()
			local bn = require("resty.openssl.bn")
			local obj = bn.from_dec(serial)
			if obj and obj.to_hex then
				converted = obj:to_hex()
			end
		end)
		if type(converted) == "string" and #converted > 0 then
			serial = converted:upper()
		end
	end
	if not serial:match("^[0-9A-F]+$") then
		return nil
	end
	serial = serial:gsub("^0+", "")
	return serial == "" and "0" or serial
end

local function leaf_serial_hex(cert_pem)
	if type(cert_pem) ~= "string" or cert_pem == "" then
		return nil
	end
	local hex = nil
	pcall(function()
		local x509 = require("resty.openssl.x509")
		local cert = x509.new(cert_pem)
		if not cert then
			return
		end
		hex = canonical_serial_hex(cert:get_serial_number())
	end)
	return hex
end

local function ocsp_resp_serial_hex(ocsp_der)
	if type(ocsp_der) ~= "string" or ocsp_der == "" then
		return nil
	end
	local hex = nil
	pcall(function()
		local ocsp_lib = require("resty.openssl.ocsp")
		local parsed = ocsp_lib.new(ocsp_der)
		if not parsed then
			return
		end
		hex = canonical_serial_hex(parsed:get_serial())
	end)
	return hex
end

local function pem_dn_str(cert_pem, which)
	if type(cert_pem) ~= "string" or cert_pem == "" then
		return nil
	end
	local out = nil
	pcall(function()
		local x509 = require("resty.openssl.x509")
		local cert = x509.new(cert_pem)
		if not cert then
			return
		end
		local name = nil
		if which == "issuer" then
			name = cert:get_issuer_name()
		else
			name = cert:get_subject_name()
		end
		if name then
			out = tostring(name)
		end
	end)
	if type(out) == "string" and #out > 0 then
		return out
	end
	return nil
end

-- CertID must name this handshake leaf: serial match + issuer DN binds to a candidate
-- issuer PEM (subject == leaf.issuer). Fail closed when either side is unreadable.
-- ngx.ocsp.validate_ocsp_response also binds CertID; this gate covers verified-L1
-- paths that skip re-validate after a same-key renew left a stale body under the SPKI.
local function certid_matches_handshake_leaf(leaf_pem, ocsp_der, issuer_pems)
	if type(leaf_pem) ~= "string" or leaf_pem == "" or type(ocsp_der) ~= "string" or ocsp_der == "" then
		return false, "missing_leaf_or_resp"
	end
	local leaf_serial = leaf_serial_hex(leaf_pem)
	local resp_serial = ocsp_resp_serial_hex(ocsp_der)
	if not leaf_serial or not resp_serial then
		return false, "serial_unreadable"
	end
	if leaf_serial ~= resp_serial then
		return false, "serial_mismatch"
	end
	local leaf_issuer = pem_dn_str(leaf_pem, "issuer")
	if not leaf_issuer then
		return false, "leaf_issuer_unreadable"
	end
	if type(issuer_pems) ~= "table" or #issuer_pems == 0 then
		return false, "no_issuer_candidates"
	end
	for _, iss in ipairs(issuer_pems) do
		local subj = pem_dn_str(iss, "subject")
		if subj and subj == leaf_issuer then
			return true, nil
		end
	end
	return false, "issuer_mismatch"
end

-- Fingerprint-only path has no handshake leaf PEM: require response CertID serial
-- to match the job-published pin (meta.certid.serial, else meta.serial).
-- When meta.certid is present, those bytes are the single SingleResponse the job accepted.
local function certid_consistent_with_meta(meta, ocsp_der)
	if type(meta) ~= "table" then
		return false, "no_meta"
	end
	local pin = meta.certid
	local meta_serial = nil
	if type(pin) == "table" then
		meta_serial = canonical_serial_hex(pin.serial)
		if not meta_serial then
			return false, "certid_serial_unreadable"
		end
	else
		meta_serial = canonical_serial_hex(meta.serial)
	end
	local resp_serial = ocsp_resp_serial_hex(ocsp_der)
	if not meta_serial or not resp_serial then
		return false, "serial_unreadable"
	end
	if meta_serial ~= resp_serial then
		return false, "serial_mismatch"
	end
	return true, nil
end

-- Canonical AIA OCSP URI for comparison (scheme+host lowercased; path preserved).
local function normalize_ocsp_aia_uri(url)
	if type(url) ~= "string" then
		return nil
	end
	url = url:match("^%s*(.-)%s*$") or ""
	if url == "" then
		return nil
	end
	local scheme, rest = url:match("^([Hh][Tt][Tt][Pp][Ss]?)://(.+)$")
	if not scheme or not rest then
		return nil
	end
	scheme = scheme:lower()
	local hostport, pathquery = rest:match("^([^/?#]+)(.*)$")
	if not hostport or hostport == "" then
		return nil
	end
	return scheme .. "://" .. hostport:lower() .. (pathquery or "")
end

-- All OCSP URIs from leaf AIA (authorityInfoAccess), normalized.
local function leaf_aia_ocsp_uris(cert_pem)
	local out = {}
	local seen = {}
	if type(cert_pem) ~= "string" or cert_pem == "" then
		return out
	end
	pcall(function()
		local x509 = require("resty.openssl.x509")
		local cert = x509.new(cert_pem)
		if not cert then
			return
		end
		local aia_ext = cert:get_extension("authorityInfoAccess")
		if not aia_ext then
			return
		end
		local aia_text = aia_ext:text() or ""
		for uri in aia_text:gmatch("1%.3%.6%.1%.5%.5%.7%.48%.1%s*=%s*URI:([%w%p]+)") do
			local n = normalize_ocsp_aia_uri(uri)
			if n and not seen[n] then
				seen[n] = true
				out[#out + 1] = n
			end
		end
		if #out == 0 then
			for uri in aia_text:gmatch("OCSP%s*%-?%s*URI:([%w%p]+)") do
				local n = normalize_ocsp_aia_uri(uri)
				if n and not seen[n] then
					seen[n] = true
					out[#out + 1] = n
				end
			end
		end
	end)
	return out
end

-- Published staple must name the leaf AIA OCSP URI the job fetched.
-- Returns true, or false, detail for refuse_must_staple / skip.
local function aia_uri_pin_ok(leaf_pem, meta, must_staple)
	if type(meta) ~= "table" then
		if must_staple then
			return false, "aia_uri_unpinned"
		end
		return true, nil
	end
	local pin = normalize_ocsp_aia_uri(meta.aia_ocsp_uri or meta.ocsp_url)
	if not pin then
		if must_staple then
			return false, "aia_uri_unpinned"
		end
		return true, nil
	end
	-- Fingerprint-only path: cannot re-check live AIA; pin + ligand still bind the body.
	if type(leaf_pem) ~= "string" or leaf_pem == "" then
		return true, nil
	end
	local leaf_uris = leaf_aia_ocsp_uris(leaf_pem)
	if #leaf_uris == 0 then
		log(ngx.ERR, "OCSP leaf has no AIA OCSP URI; refusing staple pinned to " .. pin)
		return false, "aia_uri_missing_on_leaf"
	end
	for _, u in ipairs(leaf_uris) do
		if u == pin then
			return true, nil
		end
	end
	log(ngx.ERR, "OCSP AIA URI pin mismatch pin=" .. pin .. " leaf_aia_count=" .. tostring(#leaf_uris))
	return false, "aia_uri_mismatch"
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

-- Shared ligand: job-published ocsp.json der_sha256. HTTP (internalstore) and
-- stream (internalstore_stream) cannot share L1 shm; this disk binding is the
-- cross-zone stand-in for "the ligand HTTP would accept."
-- Returns ok, reason, meta_sha, body_sha (sha values only on mismatch / accept).
local function ocsp_json_ligand_matches(meta, fingerprint, resp)
	if not ocsp_json_fingerprint_matches(meta, fingerprint) then
		return false, "fingerprint_mismatch_or_missing_meta", nil, nil
	end
	if type(meta.der_sha256) ~= "string" then
		return false, "missing_der_sha256", nil, nil
	end
	local meta_sha = meta.der_sha256:lower()
	if #meta_sha ~= 64 or not meta_sha:match("^[0-9a-f]+$") then
		return false, "invalid_der_sha256", nil, nil
	end
	local body_sha = resp_binding(resp)
	if body_sha == nil or body_sha ~= meta_sha then
		return false, "der_sha256_mismatch", meta_sha, body_sha
	end
	return true, nil, meta_sha, body_sha
end

-- Fingerprint-hint path cannot call validate_ocsp_response (no leaf PEM).
-- Require meta.fingerprint match AND der_sha256 == sha256(body) so a swapped
-- ocsp.der under matching SPKI meta cannot be stapled.
-- Logs accept/refuse with truncated expected vs observed digests for audit.
local function ocsp_json_authorizes_resp(meta, fingerprint, resp)
	local fp_short = (type(fingerprint) == "string" and fingerprint:sub(1, 16)) or "?"
	local ok, reason, meta_sha, body_sha = ocsp_json_ligand_matches(meta, fingerprint, resp)
	if not ok then
		local level = ngx.ERR
		if reason == "fingerprint_mismatch_or_missing_meta" then
			level = ngx.DEBUG
		end
		if reason == "der_sha256_mismatch" then
			local meta_short = (type(meta_sha) == "string" and meta_sha:sub(1, 16)) or "nil"
			local body_short = (type(body_sha) == "string" and body_sha:sub(1, 16)) or "nil"
			log(
				level,
				"OCSP meta der_sha256 refuse fp="
					.. fp_short
					.. "... expected="
					.. meta_short
					.. "... observed="
					.. body_short
					.. "..."
			)
		else
			log(level, "OCSP meta der_sha256 refuse fp=" .. fp_short .. "... reason=" .. tostring(reason))
		end
		return false
	end
	log(
		ngx.INFO,
		"OCSP meta der_sha256 accept fp=" .. fp_short .. "... der_sha256=" .. meta_sha:sub(1, 16) .. "..."
	)
	return true
end

-- Must-Staple may not rely on stream-private crypto-verified L1 alone.
-- Returns true, or false, detail_code for OCSP_MUST_STAPLE_REFUSE (logged by soften).
local function must_staple_binds_shared_ligand(meta, fingerprint, resp)
	local ok, reason = ocsp_json_ligand_matches(meta, fingerprint, resp)
	if ok then
		return true
	end
	return false, "shared_ligand_" .. tostring(reason or "mismatch")
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

-- Wall-clock stop from published_unix + max age (independent of nextUpdate).
local function meta_max_age_unix(meta)
	if type(meta) ~= "table" then
		return nil
	end
	local u = meta.max_age_unix
	if type(u) == "number" and u > 0 then
		return math.floor(u)
	end
	if type(u) == "string" then
		local n = tonumber(u)
		if n and n > 0 then
			return math.floor(n)
		end
	end
	local published = meta.published_unix
	if type(published) == "string" then
		published = tonumber(published)
	end
	if type(published) == "number" and published > 0 then
		-- Match PREVIOUS_GOOD_MAX_AGE_SECONDS in ocsp-refresh.py (24h).
		return math.floor(published) + 86400
	end
	return nil
end

-- False at death time (nextUpdate/max_age minus skew). Unknown → true.
-- Also enforces intrinsic signed-window policy when this_update_unix is present.
local function meta_unix_field(meta, key)
	if type(meta) ~= "table" then
		return nil
	end
	local u = meta[key]
	if type(u) == "number" and u > 0 then
		return math.floor(u)
	end
	if type(u) == "string" then
		local n = tonumber(u)
		if n and n > 0 then
			return math.floor(n)
		end
	end
	return nil
end

local function intrinsic_timing_ok(meta)
	local this_u = meta_unix_field(meta, "this_update_unix")
	if not this_u then
		-- Legacy meta without signed timing: retention/skew checks only.
		return true, nil
	end
	local now = ngx.time()
	if this_u > now + OCSP_CLOCK_SKEW_SECONDS then
		return false, "thisUpdate_future"
	end
	if this_u < now - OCSP_MAX_THIS_UPDATE_AGE_SECONDS then
		return false, "thisUpdate_stale"
	end
	local next_u = meta_unix_field(meta, "next_update_unix") or meta_expires_unix(meta)
	if not next_u then
		return false, "thisUpdate_unreadable"
	end
	local lifetime = next_u - this_u
	if lifetime <= 0 then
		return false, "lifetime_invalid"
	end
	if lifetime > OCSP_MAX_INTRINSIC_LIFETIME_SECONDS then
		return false, "lifetime_too_long"
	end
	return true, nil
end

local function resp_still_fresh(expires_unix, fingerprint, meta)
	meta = meta or (fingerprint and read_ocsp_json(fingerprint)) or nil
	local ok_intrinsic, why = intrinsic_timing_ok(meta)
	if not ok_intrinsic then
		log(ngx.ERR, "OCSP intrinsic timing refuse reason=" .. tostring(why) .. " fp=" .. tostring(fingerprint and fingerprint:sub(1, 16) or "?"))
		return false
	end
	local exp = expires_unix
	if not exp then
		exp = meta_expires_unix(meta)
	end
	local max_age = meta_max_age_unix(meta)
	if exp and max_age then
		if max_age < exp then
			exp = max_age
		end
	elseif max_age and not exp then
		exp = max_age
	end
	if not exp then
		return true
	end
	if ngx.time() >= exp - OCSP_CLOCK_SKEW_SECONDS then
		return false
	end
	return true
end

local function meta_effective_expires_unix(meta, expires_unix)
	local exp = expires_unix or meta_expires_unix(meta)
	local max_age = meta_max_age_unix(meta)
	if exp and max_age then
		if max_age < exp then
			return max_age
		end
		return exp
	end
	return exp or max_age
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

local function try_staple(ocsp, ssl, resp, leaf_pem, issuers, shard_issuer_spki, probe_only)
	local ok_id, why = certid_matches_handshake_leaf(leaf_pem, resp, issuers)
	if not ok_id then
		log(ngx.ERR, "OCSP CertID refuse staple reason=" .. tostring(why))
		return false
	end
	for _, issuer_pem in ipairs(issuers) do
		if validate(ocsp, ssl, resp, leaf_pem, issuer_pem, shard_issuer_spki) then
			if probe_only then
				return true
			end
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

-- Audit which leaf was stapled — kind + SPKI + der_sha256 + epoch this node served.
local function log_ocsp_stapled(server_name, kind, fp, resp)
	local der = resp_binding(resp) or "-"
	local fp_s = (type(fp) == "string" and #fp == 64) and fp or "-"
	local epoch = current_ocsp_epoch() or "0"
	local worker = "-"
	pcall(function()
		if ngx.worker and ngx.worker.id then
			worker = tostring(ngx.worker.id())
		end
	end)
	log(
		ngx.INFO,
		"OCSP_STAPLED kind="
			.. tostring(kind or "unknown")
			.. " fp="
			.. fp_s
			.. " der_sha256="
			.. der
			.. " epoch="
			.. tostring(epoch)
			.. " worker="
			.. worker
			.. " server_name="
			.. tostring(server_name or "nil")
	)
end

local function log_ocsp_staple_skip(kind, fp, reason, server_name)
	local fp_s = "-"
	if type(fp) == "string" and #fp == 64 then
		fp_s = fp
	elseif type(fp) == "string" and #fp > 0 then
		fp_s = fp
	end
	log(
		ngx.NOTICE,
		"OCSP_STAPLE_SKIP kind="
			.. tostring(kind or "unknown")
			.. " fp="
			.. fp_s
			.. " reason="
			.. tostring(reason or "unknown")
			.. " server_name="
			.. tostring(server_name or "nil")
	)
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
		log_ocsp_staple_skip("rsa", spki_fingerprint(rsa_leaf), "single_slot_ecdsa_prefer", nil)
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
function _M.set_certs_from_pem(cert_pem, key_pem, internalstore, server_name)
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

	local mode = "normal"
	if internalstore then
		mode = ocsp_staple_mode(internalstore, server_name)
	end

	local installed = {}
	local must_staple_refused = false
	local refuse_detail = nil
	for _, leaf in ipairs(leaves) do
		local chain_pem = leaf.pem
		for _, intermediate in ipairs(intermediates) do
			chain_pem = chain_pem .. "\n" .. intermediate
		end
		-- Must-Staple leaves require a live shard probe before set_cert (normal mode).
		local leaf_must = has_must_staple(leaf.pem)
		if not leaf_must and leaf.fp then
			leaf_must = ocsp_json_must_staple(read_ocsp_json(leaf.fp))
		end
		if leaf_must and mode == "open" then
			leaf_must = false
		end
		local skip_leaf = false
		if leaf_must and internalstore and mode == "normal" then
			-- apply_soften=false: log skip_leaf here (dual-cert may still install another leaf).
			local probe_ok, probe_reason, probe_detail = _M.probe(internalstore, server_name, chain_pem, leaf.fp, false)
			if not probe_ok then
				must_staple_refused = true
				refuse_detail = probe_detail or probe_reason or "probe_failed"
				log(
					ngx.ERR,
					"OCSP_MUST_STAPLE_REFUSE reason="
						.. tostring(refuse_detail)
						.. " action=skip_leaf mode=normal fp="
						.. tostring(leaf.fp and leaf.fp:sub(1, 16) or "nil")
						.. "..."
				)
				skip_leaf = true
			end
		end
		if not skip_leaf then
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
	end

	if #installed == 0 then
		if must_staple_refused then
			return false, "must_staple", refuse_detail or "probe_failed"
		end
		return false, "no certificates installed"
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
local function staple_from_fingerprint(internalstore, server_name, fingerprint, probe_only)
	local meta = read_ocsp_json(fingerprint)
	local must_staple = ocsp_json_must_staple(meta)
	if must_staple then
		log(ngx.INFO, "OCSP-Must-Staple from ocsp.json for fp=" .. fingerprint:sub(1, 16) .. "...")
	end

	if must_staple and cluster_floor_blocks(fingerprint, meta) then
		return false, "must_staple", "cluster_floor"
	end
	if shard_not_paged(meta) then
		if must_staple then
			return false, "must_staple", "not_paged"
		end
		return false
	end

	local aia_ok, aia_why = aia_uri_pin_ok(nil, meta, must_staple)
	if not aia_ok then
		if must_staple then
			return false, "must_staple", aia_why or "aia_uri_mismatch"
		end
		return false
	end

	if not stapling_enabled(internalstore, server_name) then
		if must_staple then
			return false, "must_staple", "ssl_use_ocsp_stapling_no"
		end
		log_stapling_off("ssl_use_ocsp_stapling_no")
		return false
	end

	local ok_ocsp, ocsp = pcall(require, "ngx.ocsp")
	if not ok_ocsp or not ocsp or not ocsp.set_ocsp_status_resp then
		if must_staple then
			return false, "must_staple", "ngx_ocsp_unavailable"
		end
		log(ngx.DEBUG, "OCSP_STAPLING_OFF reason=ngx_ocsp_unavailable")
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
			if serial_blacklist_blocks(fingerprint, cached) then
				drop_cache(internalstore, fingerprint)
				if must_staple then
					return false, "must_staple", "serial_blacklisted"
				end
				return false
			end
			local verified = entry_verified(cached_verified, cached)
			-- Only consult meta when L1 is not already crypto-verified (avoids refuse noise).
			local authorized = false
			if not verified then
				authorized = ocsp_json_authorizes_resp(meta, fingerprint, cached)
			end
			if verified or authorized then
				-- Must-Staple: stream-private verified L1 is not enough; bind shared ligand.
				local ligand_ok, ligand_detail = must_staple_binds_shared_ligand(meta, fingerprint, cached)
				if must_staple and not ligand_ok then
					drop_cache(internalstore, fingerprint)
					return false, "must_staple", ligand_detail
				end
				local ok_id, why = certid_consistent_with_meta(meta or read_ocsp_json(fingerprint), cached)
				if not ok_id then
					log(ngx.ERR, "OCSP CertID refuse fingerprint staple reason=" .. tostring(why) .. " fp=" .. fingerprint:sub(1, 16) .. "...")
					drop_cache(internalstore, fingerprint)
					if must_staple then
						return false, "must_staple", "certid_mismatch"
					end
					return false
				end
				if probe_only then
					return true
				end
				local ok_set, set_ok, set_err = pcall(function()
					return ocsp.set_ocsp_status_resp(cached)
				end)
				if ok_set and set_ok then
					local exp = meta_effective_expires_unix(meta, cached_expires)
					-- Only re-warm verified if crypto already proved this body.
					if verified then
						warm_cache(internalstore, fingerprint, cached, true, exp)
					else
						warm_cache(internalstore, fingerprint, cached, false, exp)
					end
					log_ocsp_stapled(server_name, nil, fingerprint, cached)
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
				return false, "must_staple", "response_stale"
			end
			return false
		end
		-- Disk path: verified binding only exists in L1; after drop/miss, require meta authorize
		-- or a leftover legacy sibling (get_l1 already promoted). Re-check composite if rewarmed.
		local _, disk_verified = get_l1(internalstore, fingerprint)
		if serial_blacklist_blocks(fingerprint, resp) then
			if must_staple then
				return false, "must_staple", "serial_blacklisted"
			end
			return false
		end
		local verified = entry_verified(disk_verified, resp)
		local authorized = false
		if not verified then
			authorized = ocsp_json_authorizes_resp(meta, fingerprint, resp)
		end
		if verified or authorized then
			local ligand_ok, ligand_detail = must_staple_binds_shared_ligand(meta, fingerprint, resp)
			if must_staple and not ligand_ok then
				return false, "must_staple", ligand_detail
			end
			local ok_id, why = certid_consistent_with_meta(meta, resp)
			if not ok_id then
				log(ngx.ERR, "OCSP CertID refuse fingerprint staple reason=" .. tostring(why) .. " fp=" .. fingerprint:sub(1, 16) .. "...")
				if must_staple then
					return false, "must_staple", "certid_mismatch"
				end
				return false
			end
			if probe_only then
				return true
			end
			local ok_set, set_ok, set_err = pcall(function()
				return ocsp.set_ocsp_status_resp(resp)
			end)
			if ok_set and set_ok then
				warm_cache(internalstore, fingerprint, resp, verified, meta_effective_expires_unix(meta))
				log_ocsp_stapled(server_name, nil, fingerprint, resp)
				return true
			end
			log(ngx.ERR, "OCSP failed to set stapling: " .. tostring(set_err or set_ok))
			if must_staple then
				return false, "must_staple", "set_staple_failed"
			end
			return false
		end
	end

	if must_staple then
		return false, "must_staple", "response_not_found"
	end
	return false
end

local function staple_one_leaf(internalstore, ocsp, ssl, blocks, leaf_pem, fingerprint, must_staple, server_name, probe_only)
	if not fingerprint then
		return nil
	end
	local issuers = nil
	local shard_issuer_pem = read_file(issuer_path(fingerprint))
	local shard_issuer_spki = shard_issuer_pem and spki_fingerprint(shard_issuer_pem) or nil
	local meta = read_ocsp_json(fingerprint)
	if must_staple and cluster_floor_blocks(fingerprint, meta) then
		return false, "must_staple", "cluster_floor"
	end
	if shard_not_paged(meta) then
		if must_staple then
			return false, "must_staple", "not_paged"
		end
		return false
	end
	local aia_ok, aia_why = aia_uri_pin_ok(leaf_pem, meta, must_staple)
	if not aia_ok then
		if must_staple then
			return false, "must_staple", aia_why or "aia_uri_mismatch"
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
		elseif entry_verified(cached_verified, cached) then
			if serial_blacklist_blocks(fingerprint, cached) then
				drop_cache(internalstore, fingerprint)
				if must_staple then
					return false, "must_staple", "serial_blacklisted"
				end
				return false
			end
			issuers = issuer_candidates(blocks, leaf_pem, fingerprint)
			local ok_id, why = certid_matches_handshake_leaf(leaf_pem, cached, issuers)
			if not ok_id then
				log(ngx.ERR, "OCSP CertID refuse L1 staple reason=" .. tostring(why) .. " fp=" .. fingerprint:sub(1, 16) .. "...")
				drop_cache(internalstore, fingerprint)
				if must_staple then
					return false, "must_staple", "certid_mismatch"
				end
				-- Fall through to disk / re-validate with the current leaf.
			else
			-- Must-Staple: bind shared ocsp.json ligand, not stream-private L1 alone.
			if must_staple then
				meta = meta or read_ocsp_json(fingerprint)
				local ligand_ok, ligand_detail = must_staple_binds_shared_ligand(meta, fingerprint, cached)
				if not ligand_ok then
					drop_cache(internalstore, fingerprint)
					return false, "must_staple", ligand_detail
				end
			end
			if probe_only then
				return true
			end
			local ok_set, set_ok, set_err = pcall(function()
				return ocsp.set_ocsp_status_resp(cached)
			end)
			if ok_set and set_ok then
				log_ocsp_stapled(server_name, cert_pubkey_kind(leaf_pem), fingerprint, cached)
				return true
			end
			log(ngx.ERR, "OCSP failed to set stapling from L1: " .. tostring(set_err or set_ok))
			drop_cache(internalstore, fingerprint)
			end
		else
			if serial_blacklist_blocks(fingerprint, cached) then
				drop_cache(internalstore, fingerprint)
				if must_staple then
					return false, "must_staple", "serial_blacklisted"
				end
				return false
			end
			issuers = issuer_candidates(blocks, leaf_pem, fingerprint)
			local result = try_staple(ocsp, ssl, cached, leaf_pem, issuers, shard_issuer_spki, probe_only)
			if result == true then
				if must_staple then
					meta = meta or read_ocsp_json(fingerprint)
					local ligand_ok, ligand_detail = must_staple_binds_shared_ligand(meta, fingerprint, cached)
					if not ligand_ok then
						drop_cache(internalstore, fingerprint)
						return false, "must_staple", ligand_detail
					end
				end
				if probe_only then
					return true
				end
				warm_cache(internalstore, fingerprint, cached, true, meta_effective_expires_unix(meta or read_ocsp_json(fingerprint), cached_expires))
				log_ocsp_stapled(server_name, cert_pubkey_kind(leaf_pem), fingerprint, cached)
				return true
			end
			if result == false then
				if must_staple then
					return false, "must_staple", "validate_failed"
				end
				return false
			end
			drop_cache(internalstore, fingerprint)
		end
	end

	local resp = read_file(ocsp_path(fingerprint))
	if resp then
		meta = meta or read_ocsp_json(fingerprint)
		if not resp_still_fresh(nil, fingerprint, meta) then
			log(ngx.ERR, "OCSP disk response past nextUpdate/expires; refusing staple fp=" .. fingerprint:sub(1, 16) .. "...")
			if must_staple then
				return false, "must_staple", "response_stale"
			end
			return false
		end
		issuers = issuers or issuer_candidates(blocks, leaf_pem, fingerprint)
		if serial_blacklist_blocks(fingerprint, resp) then
			if must_staple then
				return false, "must_staple", "serial_blacklisted"
			end
			return false
		end
		local result = try_staple(ocsp, ssl, resp, leaf_pem, issuers, shard_issuer_spki, probe_only)
		if result == true then
			local ligand_ok, ligand_detail = must_staple_binds_shared_ligand(meta, fingerprint, resp)
			if must_staple and not ligand_ok then
				return false, "must_staple", ligand_detail
			end
			if probe_only then
				return true
			end
			warm_cache(internalstore, fingerprint, resp, true, meta_effective_expires_unix(meta))
			log_ocsp_stapled(server_name, cert_pubkey_kind(leaf_pem), fingerprint, resp)
			return true
		end
		if result == false then
			if must_staple then
				return false, "must_staple", "validate_failed"
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
-- Must-Staple also requires the shared ocsp.json der_sha256 ligand (cross-zone stand-in for
-- HTTP's L1 entry); stream-private crypto-verified L1 alone is refused.
-- Optional cert_fp_hint (plugin status[5]) enforces Must-Staple via ocsp.json when PEM is absent.
-- Dual-cert PEMs staple the ECDSA leaf only (one ngx.ocsp status slot).
-- Returns: true on success; false, "must_staple" when Must-Staple is unmet; false otherwise.
function _M.staple(internalstore, server_name, cert_pem, cert_fp_hint)
	if not internalstore then
		return false
	end

	local mode = ocsp_staple_mode(internalstore, server_name)
	local pem_ok = type(cert_pem) == "string" and cert_pem ~= ""
	local fp_hint = normalize_fp_hint(cert_fp_hint)

	if not pem_ok then
		if fp_hint then
			return soften_must_staple(mode, staple_from_fingerprint(internalstore, server_name, fp_hint, false))
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
	-- When resty cannot see TLS Feature, honor Must-Staple from job-written ocsp.json.
	if not must_staple and fp_hint then
		must_staple = ocsp_json_must_staple(read_ocsp_json(fp_hint))
	end

	-- open: disable Must-Staple enforcement entirely (still staple when possible).
	if must_staple and mode == "open" then
		log(ngx.NOTICE, "OCSP_STAPLE_MODE=open - Must-Staple enforcement disabled for " .. (server_name or "unknown"))
		must_staple = false
	end

	if not stapling_enabled(internalstore, server_name) then
		if must_staple then
			return soften_must_staple(mode, false, "must_staple", "ssl_use_ocsp_stapling_no")
		end
		log_stapling_off("ssl_use_ocsp_stapling_no")
		return false
	end

	local ok_ocsp, ocsp = pcall(require, "ngx.ocsp")
	if not ok_ocsp or not ocsp or not ocsp.set_ocsp_status_resp then
		if must_staple then
			return soften_must_staple(mode, false, "must_staple", "ngx_ocsp_unavailable")
		end
		log(ngx.DEBUG, "OCSP_STAPLING_OFF reason=ngx_ocsp_unavailable")
		return false
	end
	local ssl = require "ngx.ssl"

	-- Staple only this leaf's SPKI. Never use a dual-cert sibling hint (RSA hint on ECDSA leaf).
	local leaf_fp = spki_fingerprint(leaf_pem, internalstore)
	if fp_hint and leaf_fp and fp_hint ~= leaf_fp then
		log_ocsp_staple_skip(cert_pubkey_kind(leaf_pem) == "ec" and "rsa" or "ec", fp_hint, "wrong_key_type_hint", server_name)
		fp_hint = nil
	end
	local fingerprint = leaf_fp
	if not fingerprint and fp_hint then
		-- No SPKI from PEM; fingerprint-only path (no sibling borrow possible without a second leaf).
		fingerprint = fp_hint
	end
	if not must_staple and fingerprint then
		must_staple = ocsp_json_must_staple(read_ocsp_json(fingerprint))
		if must_staple then
			log(ngx.INFO, "OCSP-Must-Staple from ocsp.json for fp=" .. fingerprint:sub(1, 16) .. "...")
			if mode == "open" then
				log(ngx.NOTICE, "OCSP_STAPLE_MODE=open - Must-Staple enforcement disabled for " .. (server_name or "unknown"))
				must_staple = false
			end
		end
	end

	local result, reason, detail = staple_one_leaf(internalstore, ocsp, ssl, blocks, leaf_pem, fingerprint, must_staple, server_name, false)
	if result == true then
		return true
	end
	if result == false then
		return soften_must_staple(mode, false, reason, detail)
	end

	if must_staple then
		return soften_must_staple(mode, false, "must_staple", "response_not_found")
	end
	return false
end

-- Live staple probe for a leaf/shard without installing the cert or setting the staple.
-- Must-Staple leaves must pass this before set_cert (normal mode). Soft fuses continue
-- when apply_soften is not false (default). Pass apply_soften=false for skip-leaf callers
-- that log their own action (e.g. set_certs_from_pem).
-- Returns true, or false, "must_staple", detail (abort), or false (soft continue without abort tag).
function _M.probe(internalstore, server_name, cert_pem, cert_fp_hint, apply_soften)
	if not internalstore then
		return false
	end
	local mode = ocsp_staple_mode(internalstore, server_name)
	-- open disables Must-Staple entirely: leaf may load without a live staple.
	if mode == "open" then
		return true
	end
	local soften = apply_soften ~= false
	local function finish(ok, reason, detail)
		if ok then
			return true
		end
		if soften then
			return soften_must_staple(mode, false, reason, detail)
		end
		return false, reason, detail
	end
	local pem_ok = type(cert_pem) == "string" and cert_pem ~= ""
	local fp_hint = normalize_fp_hint(cert_fp_hint)
	if not pem_ok then
		if fp_hint then
			local ok, reason, detail = staple_from_fingerprint(internalstore, server_name, fp_hint, true)
			return finish(ok, reason, detail)
		end
		return true
	end
	local blocks = pem_blocks(cert_pem)
	local leaf_pem = blocks[1]
	if not leaf_pem then
		return false
	end
	local must_staple = has_must_staple(leaf_pem)
	if not must_staple and fp_hint then
		must_staple = ocsp_json_must_staple(read_ocsp_json(fp_hint))
	end
	if not must_staple then
		-- Optional stapling: leaf may load without a live probe.
		return true
	end
	if not stapling_enabled(internalstore, server_name) then
		return finish(false, "must_staple", "ssl_use_ocsp_stapling_no")
	end
	local ok_ocsp, ocsp = pcall(require, "ngx.ocsp")
	if not ok_ocsp or not ocsp or not ocsp.set_ocsp_status_resp then
		return finish(false, "must_staple", "ngx_ocsp_unavailable")
	end
	local ssl = require "ngx.ssl"
	local leaf_fp = spki_fingerprint(leaf_pem, internalstore)
	if fp_hint and leaf_fp and fp_hint ~= leaf_fp then
		fp_hint = nil
	end
	local fingerprint = leaf_fp or fp_hint
	if not fingerprint then
		return finish(false, "must_staple", "fingerprint_unavailable")
	end
	if not must_staple then
		must_staple = ocsp_json_must_staple(read_ocsp_json(fingerprint))
	end
	if not must_staple then
		return true
	end
	local result, reason, detail = staple_one_leaf(internalstore, ocsp, ssl, blocks, leaf_pem, fingerprint, true, server_name, true)
	if result == true then
		return true
	end
	if result == false then
		return finish(false, reason, detail)
	end
	return finish(false, "must_staple", "response_not_found")
end


return _M
