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

-- Closed staple_decision codes. Each code is the runbook section key (ssl README).
-- Unknown detail strings normalize to unmet (raw kept as detail=).
local STAPLE_DECISION = {
	ok = true,
	ok_partial = true,
	stapling_off = true,
	skip_slot = true,
	cluster_floor = true,
	not_paged = true,
	aia_uri_mismatch = true,
	aia_uri_unpinned = true,
	aia_uri_missing_on_leaf = true,
	aia_uri_leaf_unavailable = true,
	ssl_use_ocsp_stapling_no = true,
	ngx_ocsp_unavailable = true,
	response_not_found = true,
	response_stale = true,
	serial_blacklisted = true,
	tombstoned = true,
	shared_ligand = true,
	certid_mismatch = true,
	set_staple_failed = true,
	set_staple_exception = true,
	fingerprint_unavailable = true,
	wrong_key_type_staple = true,
	probe_failed = true,
	thisUpdate_future = true,
	thisUpdate_stale = true,
	lifetime_invalid = true,
	lifetime_too_long = true,
	thisUpdate_unreadable = true,
	canary_refused = true,
	peer_refuse = true,
	peer_refuse_bus = true,
	await_sni = true,
	intermediate_must_staple_libssl = true,
	-- Soft ngx.ocsp.validate budget aborted during leaf issuer tries; multi-staple
	-- stack was never attached (not ok_partial — that name is NULL-slot attach only).
	validate_budget = true,
	unmet = true,
}

local STAPLE_DECISION_ALIAS = {
	single_slot_ecdsa_prefer = "skip_slot",
	single_slot_rsa_prefer = "skip_slot",
	wrong_key_type_hint = "skip_slot",
	variables_unavailable = "stapling_off",
	ligand_missing = "shared_ligand",
	ligand_mismatch = "shared_ligand",
}

local function normalize_staple_decision(code)
	local raw = tostring(code or "unmet")
	if STAPLE_DECISION_ALIAS[raw] then
		return STAPLE_DECISION_ALIAS[raw], raw
	end
	if raw:sub(1, 7) == "canary_" then
		return "canary_refused", raw
	end
	if raw:sub(1, 14) == "shared_ligand_" then
		return "shared_ligand", raw
	end
	if STAPLE_DECISION[raw] then
		return raw, nil
	end
	return "unmet", raw
end

-- Emit staple_decision=CODE as the primary machine field (runbook section).
local function format_staple_decision(code, fields)
	local decision, alias_detail = normalize_staple_decision(code)
	local parts = { "staple_decision=" .. decision }
	local f = {}
	if type(fields) == "table" then
		for k, v in pairs(fields) do
			f[k] = v
		end
	end
	if alias_detail then
		if f.detail == nil or f.detail == "" then
			f.detail = alias_detail
		elseif tostring(f.detail) ~= alias_detail then
			f.alias = alias_detail
		end
	end
	local order = { "tag", "action", "mode", "kind", "fp", "detail", "alias", "der_sha256", "epoch", "worker", "server_name", "subsystem", "multi_entries", "stapled_entries", "null_slots" }
	local seen = { staple_decision = true }
	for _, key in ipairs(order) do
		local val = f[key]
		if val ~= nil and val ~= "" then
			parts[#parts + 1] = key .. "=" .. tostring(val)
			seen[key] = true
		end
	end
	for key, val in pairs(f) do
		if not seen[key] and val ~= nil and val ~= "" then
			parts[#parts + 1] = key .. "=" .. tostring(val)
		end
	end
	return table.concat(parts, " ")
end

-- Single source of truth for closed staple_decision=CODE log lines (HTTP + stream).
function _M.format_staple_decision(code, fields)
	return format_staple_decision(code, fields)
end

-- Convert a Must-Staple miss into abort (normal) or soft continue (fuse).
-- Always logs staple_decision=CODE (runbook) with tag=OCSP_MUST_STAPLE_REFUSE.
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
		format_staple_decision(detail or "unmet", {
			tag = "OCSP_MUST_STAPLE_REFUSE",
			action = action,
			mode = mode or "normal",
		})
	)
	if action == "continue" then
		return false
	end
	return false, "must_staple"
end

-- Exported so stream ssl_certificate await_sni can apply the same fuse as staple().
function _M.staple_mode(internalstore, server_name)
	return ocsp_staple_mode(internalstore, server_name)
end

function _M.soften_must_staple(mode, ok, reason, detail)
	return soften_must_staple(mode, ok, reason, detail)
end

-- Optional stapling skipped (no Must-Staple). Distinct from Must-Staple refuse.
local function log_stapling_off(reason)
	log(
		ngx.DEBUG,
		format_staple_decision("stapling_off", {
			tag = "OCSP_STAPLING_OFF",
			detail = tostring(reason or "ssl_use_ocsp_stapling_no"),
		})
	)
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
-- Soft ngx.ocsp.validate budget on the TLS path (match HTTP ssl-certificate-by-lua).
local OCSP_VALIDATE_BUDGET_NS = 700000000 -- 700ms when ngx.hrtime is available
local OCSP_VALIDATE_BUDGET_S = 0.7
local OCSP_VALIDATE_MAX_ISSUERS = 4
-- Signed-window policy; must match ocsp-refresh.py.
local OCSP_MAX_INTRINSIC_LIFETIME_SECONDS = 7 * 24 * 3600
local OCSP_MAX_THIS_UPDATE_AGE_SECONDS = 7 * 24 * 3600

-- One shm value = epoch + optional verified binding + expires_unix + DER.
-- Evicting this key cannot orphan verified from DER (or gen from DER).
-- Layout v2: "bw2\0" .. epoch .. "\0" .. binding .. "\0" .. expires_unix .. "\0" .. der
local L1_MAGIC = "bw2\0"
-- Cap DRAM residence; never longer than remaining OCSP life when known.
local L1_MAX_TTL = 300
-- Transient peer-refuse markers age out (align with L1). Sticky codes stay until canary page.
local PEER_REFUSE_TTL_SECONDS = L1_MAX_TTL
-- Identity / policy poison: keep shared until a new generation is paged.
-- not_paged is omitted: both subsystems already gate on ocsp.json paged; bus-poisoning
-- it sticks against the same der_sha256 after UNKNOWN soft-recall until a re-page lands.
local PEER_REFUSE_STICKY = {
	certid_mismatch = true,
	aia_uri_mismatch = true,
	aia_uri_unpinned = true,
	aia_uri_missing_on_leaf = true,
	aia_uri_leaf_unavailable = true,
	tombstoned = true,
	serial_blacklisted = true,
	cluster_floor = true,
	shared_ligand = true,
	canary_refused = true,
	thisUpdate_future = true,
	thisUpdate_stale = true,
	lifetime_invalid = true,
	lifetime_too_long = true,
	thisUpdate_unreadable = true,
	-- Platform cannot emit CertificateEntry staples (no SSL_set0_tlsext_status_ocsp_resp_ex).
	intermediate_must_staple_libssl = true,
}

local function l1_shm_ttl(expires_unix)
	-- Never park an undated body in L1 (would outlive stripped/legacy meta).
	if type(expires_unix) ~= "number" or expires_unix <= 0 then
		return nil
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
	return nil, nil, nil, nil
end

-- Shared with the HTTP ssl_certificate path: job bumps this file so both
-- internalstore and internalstore_stream drop stale L1 without cross-dict APIs.
-- Always re-read: a mid-handshake bump must not be masked by an ngx.ctx pin.
local OCSP_EPOCH_PATH = "/var/cache/bunkerweb/ssl/.ocsp_epoch"

local function current_ocsp_epoch()
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
	return epoch
end

-- Returns der, verified_binding, epoch, expires_unix (or nil). bw2 composite only.
local function get_l1(internalstore, fingerprint)
	if not internalstore or not fingerprint then
		return nil
	end
	local ok, blob = pcall(function()
		-- Shared dict (not per-worker LRU): one warmer refill serves every worker.
		return internalstore:get(cache_key(fingerprint))
	end)
	if not ok or type(blob) ~= "string" or #blob == 0 then
		return nil
	end

	local epoch, verified, der, expires_unix = unpack_l1(blob)
	if der then
		return der, verified, epoch, expires_unix
	end
	return nil
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
		internalstore:set(cache_key(fingerprint), pack_l1(epoch, binding, resp, expires_unix), ttl)
		-- Drop pre-composite siblings so they cannot outlive / contradict this entry.
		internalstore:delete(verified_key(fingerprint))
		internalstore:delete(gen_key(fingerprint))
		internalstore:delete(cache_key(fingerprint), true)
		internalstore:delete(verified_key(fingerprint), true)
		internalstore:delete(gen_key(fingerprint), true)
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
		internalstore:delete(cache_key(fingerprint), true)
		internalstore:delete(verified_key(fingerprint), true)
		internalstore:delete(l1_disk_check_key(fingerprint), true)
		internalstore:delete(gen_key(fingerprint), true)
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
	local tombstoned = false
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
		-- Mid-tombstone: meta can say tombstoned before DER unlink / epoch bump.
		if raw:find('"tombstoned"%s*:%s*true') then
			tombstoned = true
			return
		end
		local sha = raw:match('"der_sha256"%s*:%s*"([0-9a-fA-F]+)"')
		if sha and #sha == 64 then
			disk_sha = sha:lower()
		end
	end)
	if tombstoned then
		return false
	end

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

-- Colony floor: peers advance ocsp-floor/{fp} on publish/tombstone using CA-signed
-- this_update_unix (not wall-clock published_unix — clocks drift across nodes).
-- Legacy floors with only published_unix still compare published↔ published.
-- Missing local timing is no opinion (do not treat as 0 vs a positive floor).
local function meta_unix_field(meta, key)
	if type(meta) ~= "table" or type(key) ~= "string" then
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

local function parse_floor_rank(raw)
	-- Returns kind ("this_update"|"published"), rank, or nil,nil when absent.
	if type(raw) ~= "string" or raw == "" then
		return nil, nil
	end
	local trimmed = raw:match("^%s*(.-)%s*$") or raw
	if trimmed:sub(1, 1) == "{" then
		local ok, decoded = pcall(function()
			return require("cjson").decode(trimmed)
		end)
		if ok and type(decoded) == "table" then
			local this_u = meta_unix_field(decoded, "this_update_unix")
			if this_u then
				return "this_update", this_u
			end
			local pub = meta_unix_field(decoded, "published_unix")
			if pub then
				return "published", pub
			end
		end
		return nil, nil
	end
	local token = trimmed:match("^(%d+)")
	local n = tonumber(token)
	if n and n > 0 then
		return "published", n
	end
	return nil, nil
end

local function cluster_floor_blocks(fingerprint, meta)
	if not is_fp64(fingerprint) then
		return false
	end
	local raw = read_file("/var/cache/bunkerweb/ssl/ocsp-floor/" .. fingerprint)
	local kind, floor_rank = parse_floor_rank(raw)
	if not kind or not floor_rank or floor_rank <= 0 then
		return false
	end
	local local_key = (kind == "this_update") and "this_update_unix" or "published_unix"
	local local_rank = meta_unix_field(meta, local_key)
	-- Missing local timing: no opinion — never invent 0 vs a positive floor.
	if not local_rank then
		return false
	end
	if local_rank >= floor_rank then
		return false
	end
	log(
		ngx.ERR,
		"OCSP cluster floor ahead of local "
			.. local_key
			.. "; Must-Staple closed fp="
			.. fingerprint:sub(1, 16)
			.. "... floor="
			.. tostring(floor_rank)
			.. " local="
			.. tostring(local_rank)
	)
	return true
end

-- Live shard must be scheduler-paged (canary handshake) before stapling.
-- Require explicit paged=true. Missing field is not canary proof
-- (restore stamps paged=false until canary succeeds).
local function shard_not_paged(meta)
	if type(meta) ~= "table" then
		return true
	end
	return meta.paged ~= true
end

-- Job tombstone writes "tombstoned": true before DER unlink / epoch bump.
-- Handshake must sample this flag (not only .ocsp_epoch), or L1 can keep
-- stapling the last GOOD while the multi-step write is mid-flight.
local function meta_tombstoned(meta)
	return type(meta) == "table" and meta.tombstoned == true
end

-- Cross-subsystem refuse bus (HTTP ↔ stream). Separate lua_shared_dict zones cannot
-- share L1; disk carries "if either would refuse this generation, both refuse."
-- Generation identity is der_sha256 of the body (or ocsp.json pin when body absent).
local function ocsp_refuse_path(fingerprint)
	return "/var/cache/bunkerweb/ssl/ocsp-refuse/" .. fingerprint
end

local function generation_id(meta, resp)
	local body = resp_binding(resp)
	if body then
		return body
	end
	if type(meta) == "table" and type(meta.der_sha256) == "string" then
		local sha = meta.der_sha256:lower()
		if #sha == 64 and sha:match("^[0-9a-f]+$") then
			return sha
		end
	end
	return nil
end

local function read_peer_refuse(fingerprint)
	if not is_fp64(fingerprint) then
		return nil
	end
	local raw = read_file(ocsp_refuse_path(fingerprint))
	if not raw or raw == "" then
		return nil
	end
	local ok, obj = pcall(function()
		return require("cjson").decode(raw)
	end)
	if not ok or type(obj) ~= "table" then
		return nil
	end
	local sha = obj.der_sha256
	if type(sha) ~= "string" then
		return nil
	end
	sha = sha:lower()
	if #sha ~= 64 or not sha:match("^[0-9a-f]+$") then
		return nil
	end
	obj.der_sha256 = sha
	return obj
end

local function write_peer_refuse(fingerprint, der_sha256, decision, refused_by)
	if not is_fp64(fingerprint) or type(der_sha256) ~= "string" then
		return false, "invalid_inputs"
	end
	local sha = der_sha256:lower()
	if #sha ~= 64 or not sha:match("^[0-9a-f]+$") then
		return false, "invalid_der_sha256"
	end
	-- Handshake path: never mkdir/shell here. Dir is provisioned off-path
	-- (L1 warmer init, ocsp-refresh, restore coherence). Missing dir → bus_write_failed.
	local path = ocsp_refuse_path(fingerprint)
	local tmp = path .. ".tmp." .. tostring((ngx.worker and ngx.worker.pid and ngx.worker.pid()) or math.floor(ngx.now() * 1000))
	local payload = require("cjson").encode({
		der_sha256 = sha,
		staple_decision = tostring(decision or "unmet"),
		refused_by = tostring(refused_by or (ngx.config and ngx.config.subsystem) or "unknown"),
		refused_unix = ngx.time(),
	})
	local f, open_err = io.open(tmp, "w")
	if not f then
		return false, "open_tmp:" .. tostring(open_err or "dir_missing")
	end
	local ok_w, write_err = f:write(payload)
	f:flush()
	f:close()
	if not ok_w then
		pcall(os.remove, tmp)
		return false, "write_tmp:" .. tostring(write_err or "nil")
	end
	local ok_r, rename_err = os.rename(tmp, path)
	if not ok_r then
		pcall(os.remove, tmp)
		return false, "rename:" .. tostring(rename_err or "nil")
	end
	return true
end

-- Provision ocsp-refuse/ off the TLS critical path (init_worker / warmer / jobs).
local function ensure_ocsp_refuse_dir()
	local dir = "/var/cache/bunkerweb/ssl/ocsp-refuse"
	local ok = false
	pcall(function()
		local lfs = require("lfs")
		lfs.mkdir("/var/cache/bunkerweb/ssl")
		ok = lfs.mkdir(dir) or (lfs.attributes(dir, "mode") == "directory")
	end)
	if ok then
		return true
	end
	-- Attributes-only check when mkdir is unnecessary (already exists).
	pcall(function()
		local lfs = require("lfs")
		ok = lfs.attributes(dir, "mode") == "directory"
	end)
	return ok
end

function _M.ensure_ocsp_refuse_dir()
	return ensure_ocsp_refuse_dir()
end

-- Transient markers age out; sticky identity/policy codes stay until canary page.
local function peer_refuse_marker_expired(marker)
	local decision = normalize_staple_decision(marker and marker.staple_decision or "peer_refuse")
	if PEER_REFUSE_STICKY[decision] then
		return false
	end
	local t = marker and marker.refused_unix
	if type(t) ~= "number" then
		-- Legacy transient marker without timestamp: heal (soft-fuse poison).
		return true
	end
	return (ngx.time() - t) > PEER_REFUSE_TTL_SECONDS
end

-- If the sibling subsystem refused this generation, both refuse.
-- Returns staple_decision code, or nil when clear / expired.
-- quiet=true: skip ERR log (L1 warmer polls this every rescan).
local function peer_refuse_blocks(fingerprint, meta, resp, quiet)
	local gen = generation_id(meta, resp)
	if not gen then
		return nil
	end
	local marker = read_peer_refuse(fingerprint)
	if not marker or marker.der_sha256 ~= gen then
		return nil
	end
	if peer_refuse_marker_expired(marker) then
		-- Drop stale transient poison so the next handshake does not re-read it.
		pcall(os.remove, ocsp_refuse_path(fingerprint))
		return nil
	end
	local by = marker.refused_by
	local self_sub = (ngx.config and ngx.config.subsystem) or ""
	-- Own prior refuse still applies (L1 may have diverged); peer or self same generation.
	if type(by) == "string" and by ~= "" and by == self_sub then
		-- Same subsystem re-check: still honor (sticky until page / TTL for transient).
	end
	local decision = marker.staple_decision
	if type(decision) ~= "string" or decision == "" then
		decision = "peer_refuse"
	end
	if not quiet then
		log(
			ngx.ERR,
			"OCSP generation peer-refuse bus hit fp="
				.. fingerprint:sub(1, 16)
				.. "... der="
				.. gen:sub(1, 16)
				.. "... decision="
				.. tostring(decision)
				.. " refused_by="
				.. tostring(by)
				.. " subsystem="
				.. tostring(self_sub)
		)
	end
	return decision
end

local function record_peer_refuse(fingerprint, meta, resp, decision)
	local fp_short = (type(fingerprint) == "string" and #fingerprint >= 16) and (fingerprint:sub(1, 16) .. "...") or tostring(fingerprint)
	local by = (ngx.config and ngx.config.subsystem) or "unknown"
	local gen = generation_id(meta, resp)
	if not fingerprint or not is_fp64(fingerprint) then
		log(
			ngx.ERR,
			format_staple_decision("peer_refuse_bus", {
				tag = "OCSP_PEER_REFUSE_BUS",
				action = "bus_write_failed",
				detail = "missing_fingerprint",
				fp = fp_short,
				subsystem = by,
			})
		)
		return false
	end
	if not gen then
		-- Without der_sha256 / body the sibling cannot match a generation — escalate loudly.
		log(
			ngx.ERR,
			format_staple_decision("peer_refuse_bus", {
				tag = "OCSP_PEER_REFUSE_BUS",
				action = "bus_write_failed",
				detail = "missing_generation",
				fp = fp_short,
				mode = tostring(decision or "unmet"),
				subsystem = by,
			})
		)
		return false
	end
	local ok, why = write_peer_refuse(fingerprint, gen, decision, by)
	if ok then
		log(
			ngx.NOTICE,
			"OCSP generation refuse recorded fp="
				.. fingerprint:sub(1, 16)
				.. "... der="
				.. gen:sub(1, 16)
				.. "... staple_decision="
				.. tostring(decision)
				.. " refused_by="
				.. by
		)
		return true
	end
	log(
		ngx.ERR,
		format_staple_decision("peer_refuse_bus", {
			tag = "OCSP_PEER_REFUSE_BUS",
			action = "bus_write_failed",
			detail = tostring(why or "write_failed"),
			fp = fp_short,
			der_sha256 = gen:sub(1, 16) .. "...",
			mode = tostring(decision or "unmet"),
			subsystem = by,
		})
	)
	return false
end

-- Soft fuse (staple_only/open): continue the handshake but do not poison the
-- HTTP↔stream bus — a transient miss must not brick the sibling subsystem.
-- normal (default): record so both subsystems refuse the same generation.
-- Exceptions (skip bus — sibling already sees the same disk/meta gate, or stack mismatch):
--   * set_staple_failed after a canary-paged body — CLI openssl vs ngx.ocsp attach
--   * not_paged — both sides read ocsp.json; sticky bus vs same der_sha256 blocks soft-recall recovery
local function must_staple_refuse(fingerprint, meta, resp, detail, mode)
	if mode ~= "staple_only" and mode ~= "open" then
		local d = detail or "unmet"
		-- Timing / local soft-abort: sibling must not inherit a handshake timeout.
		local skip_bus = d == "not_paged"
			or d == "validate_budget"
			or (
				(d == "set_staple_failed" or d == "set_staple_exception")
				and type(meta) == "table"
				and meta.paged == true
			)
		if not skip_bus then
			record_peer_refuse(fingerprint, meta, resp, d)
		end
	end
	return false, "must_staple", detail or "unmet"
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
-- When meta.certid is present, those bytes are the SingleResponse the job accepted
-- (exactly one CertID match among possibly several in the DER).
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
	-- Must-Staple requires a live AIA re-check against the presented leaf.
	-- Fingerprint-only (no PEM) cannot do that — fail closed rather than trust the pin alone.
	if type(leaf_pem) ~= "string" or leaf_pem == "" then
		if must_staple then
			return false, "aia_uri_leaf_unavailable"
		end
		-- Optional staple: pin + ligand still bind the body when PEM is absent.
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

function _M.aia_uri_pin_ok(leaf_pem, meta, must_staple)
	return aia_uri_pin_ok(leaf_pem, meta, must_staple)
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

-- Job canary already verified this exact body (openssl CLI + ligands) and stamped
-- paged=true. Handshake may skip ngx.ocsp.validate_ocsp_response for that body so
-- CLI vs OpenResty FFI disagreement cannot unpage a live shard; set_ocsp_status_resp
-- and CertID/leaf checks still run.
local function canary_paged_body_ok(meta, fingerprint, resp)
	if type(meta) ~= "table" or meta.paged ~= true or meta.tombstoned == true then
		return false
	end
	if not fingerprint or not is_fp64(fingerprint) then
		return false
	end
	local ok = ocsp_json_ligand_matches(meta, fingerprint, resp)
	return ok and true or false
end

function _M.canary_paged_body_ok(meta, fingerprint, resp)
	return canary_paged_body_ok(meta, fingerprint, resp)
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

-- Absolute unix nextUpdate from job meta. Requires expires_unix (no ISO+Ns fallback).
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
	return nil
end

function _M.meta_expires_unix(meta)
	return meta_expires_unix(meta)
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

-- False at death time (nextUpdate/max_age minus skew).
-- Also enforces intrinsic signed-window policy when this_update_unix is present.
-- Meta must carry a death clock (expires_unix and/or max_age/published). L1's
-- cached expires may only shorten that clock — never keep a stripped-meta DER alive.
local function intrinsic_timing_ok(meta)
	local this_u = meta_unix_field(meta, "this_update_unix")
	if not this_u then
		-- No signed thisUpdate pin: retention/skew checks only (expires_unix / max_age).
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
		return false, why or "unmet"
	end
	local meta_exp = meta_expires_unix(meta)
	local max_age = meta_max_age_unix(meta)
	local exp = meta_exp
	if exp and max_age then
		if max_age < exp then
			exp = max_age
		end
	elseif max_age and not exp then
		exp = max_age
	end
	if not exp then
		log(
			ngx.ERR,
			"OCSP refuse staple: no expires_unix/max_age death clock fp="
				.. tostring(fingerprint and fingerprint:sub(1, 16) or "?")
		)
		return false, "response_stale"
	end
	-- L1 may only tighten the meta death clock, never extend past stripped/legacy meta.
	if type(expires_unix) == "number" and expires_unix > 0 and expires_unix < exp then
		exp = math.floor(expires_unix)
	end
	if ngx.time() >= exp - OCSP_CLOCK_SKEW_SECONDS then
		return false, "response_stale"
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

local attach_ocsp_staple

local function try_staple(ocsp, ssl, resp, leaf_pem, issuers, shard_issuer_spki, probe_only, meta, fingerprint, chain_blocks)
	local ok_id, why = certid_matches_handshake_leaf(leaf_pem, resp, issuers)
	if not ok_id then
		log(ngx.ERR, "OCSP CertID refuse staple reason=" .. tostring(why))
		return false
	end
	local function set_resp()
		if probe_only then
			return true
		end
		local set_ok, set_err
		local ok_set = pcall(function()
			set_ok, set_err = attach_ocsp_staple(ocsp, resp, chain_blocks)
		end)
		if ok_set and set_ok then
			return true
		end
		local detail = tostring(set_err or set_ok)
		log(ngx.ERR, "OCSP failed to set stapling: " .. detail)
		if detail == "intermediate_must_staple_libssl" then
			return false, detail
		end
		return false
	end
	-- Trust scheduler canary (openssl CLI) for crypto verify when paged+ligand match.
	if canary_paged_body_ok(meta, fingerprint, resp) then
		log(ngx.DEBUG, "OCSP trusting canary-paged body; skipping ngx.ocsp.validate_ocsp_response")
		return set_resp()
	end
	if type(issuers) ~= "table" or #issuers == 0 then
		return nil
	end
	local n = #issuers
	if n > OCSP_VALIDATE_MAX_ISSUERS then
		n = OCSP_VALIDATE_MAX_ISSUERS
	end
	local hrtime = ngx.hrtime
	local t0 = hrtime and hrtime() or ngx.now()
	for i = 1, n do
		local over_budget
		if hrtime then
			over_budget = (hrtime() - t0) > OCSP_VALIDATE_BUDGET_NS
		else
			over_budget = (ngx.now() - t0) > OCSP_VALIDATE_BUDGET_S
		end
		if over_budget then
			local fp_s = (type(fingerprint) == "string" and #fingerprint == 64) and fingerprint or nil
			local fp_short = fp_s and (fp_s:sub(1, 16) .. "...") or "?"
			log(
				ngx.ERR,
				format_staple_decision("validate_budget", {
					tag = "OCSP_VALIDATE_BUDGET",
					fp = fp_s or fp_short,
					detail = "leaf_issuers_only",
					issuer_attempts = i - 1,
				})
			)
			-- Named abort: stack never reached attach_ocsp_staple / intermediates.
			-- Do not collapse to nil (looks like unmet/skip) or ok_partial (attach-only).
			return false, "validate_budget"
		end
		if validate(ocsp, ssl, resp, leaf_pem, issuers[i], shard_issuer_spki) then
			return set_resp()
		end
	end
	return nil
end

-- TLS 1.3 multi-staple when libssl exports SSL_set0_tlsext_status_ocsp_resp_ex
-- (upstream OpenSSL 3.6+; do not gate on version_num — distro backports / forks vary).
-- Probe result is published to .multi_staple_attach so ocsp-refresh only fetches
-- intermediate shards when workers can actually attach them.
local MULTI_STAPLE_ATTACH_PATH = "/var/cache/bunkerweb/ssl/.multi_staple_attach"
local _multi_staple_state = nil -- nil=unprobed, false=unavailable, table=ready

local function publish_multi_staple_attach(ready)
	pcall(function()
		local lfs = require "lfs"
		lfs.mkdir("/var/cache/bunkerweb/ssl")
		local tmp = MULTI_STAPLE_ATTACH_PATH .. ".tmp." .. tostring(ngx.worker.id() or 0)
		local f = io.open(tmp, "w")
		if not f then
			return
		end
		f:write(ready and "1\n" or "0\n")
		f:close()
		os.rename(tmp, MULTI_STAPLE_ATTACH_PATH)
	end)
end

local function openssl_multi_staple_ready()
	if _multi_staple_state ~= nil then
		return _multi_staple_state ~= false, _multi_staple_state
	end
	local ok_ffi, ffi = pcall(require, "ffi")
	if not ok_ffi or not ffi then
		_multi_staple_state = false
		publish_multi_staple_attach(false)
		return false, nil
	end
	-- cdef may fail on re-entry (types already declared); symbol probe is the real gate.
	pcall(ffi.cdef, [[
		typedef struct ocsp_response_st OCSP_RESPONSE;
		typedef struct stack_st OPENSSL_STACK;
		OPENSSL_STACK *OPENSSL_sk_new_null(void);
		int OPENSSL_sk_push(OPENSSL_STACK *st, const void *data);
		void OPENSSL_sk_pop_free(OPENSSL_STACK *st, void (*func)(void *));
		OCSP_RESPONSE *d2i_OCSP_RESPONSE(OCSP_RESPONSE **a, const unsigned char **pp, long length);
		void OCSP_RESPONSE_free(OCSP_RESPONSE *r);
		long SSL_set0_tlsext_status_ocsp_resp_ex(void *ssl, OPENSSL_STACK *resp);
		void *SSL_get_SSL_CTX(const void *ssl);
		long SSL_CTX_set_tlsext_status_cb(void *ctx, int (*cb)(void *ssl, void *arg));
	]])
	local ok_sym, sym = pcall(function()
		return ffi.C.SSL_set0_tlsext_status_ocsp_resp_ex
	end)
	if not ok_sym or type(sym) ~= "cdata" then
		_multi_staple_state = false
		publish_multi_staple_attach(false)
		return false, nil
	end
	-- Keep empty status cb alive for the process (OpenSSL requires it to emit staples).
	local cb = ffi.cast("int (*)(void *, void *)", function()
		return 0 -- SSL_TLSEXT_ERR_OK
	end)
	_multi_staple_state = { ffi = ffi, C = ffi.C, empty_cb = cb }
	publish_multi_staple_attach(true)
	return true, _multi_staple_state
end

-- Per-tenant control key for intermediate OCSP negatives (must match Python
-- _intermediate_control_fp). Body stays under inter SPKI; refuse/tombstone/
-- blacklist/floor for one leaf must not brick every site on that CA.
local function intermediate_control_fp(leaf_pem, inter_pem)
	local leaf_fp = spki_fingerprint(leaf_pem)
	local inter_fp = spki_fingerprint(inter_pem)
	if not leaf_fp or not inter_fp then
		return nil
	end
	local out = nil
	pcall(function()
		local digest_lib = require("resty.openssl.digest")
		local digest_ctx = digest_lib.new("sha256")
		digest_ctx:update(leaf_fp .. ":" .. inter_fp)
		out = to_hex(digest_ctx:final())
	end)
	if is_fp64(out) then
		return out
	end
	return nil
end

-- Load a canary-paged, still-fresh OCSP DER for an intermediate SPKI (or nil).
-- Negatives (tombstone / peer-refuse / serial-blacklist / floor) are checked on
-- the tenant control key when leaf_pem is provided — never on the shared SPKI alone.
local function load_paged_intermediate_staple(cert_pem, leaf_pem)
	local body_fp = spki_fingerprint(cert_pem)
	if not body_fp then
		return nil, nil
	end
	local control_fp = nil
	if type(leaf_pem) == "string" and leaf_pem ~= "" then
		control_fp = intermediate_control_fp(leaf_pem, cert_pem)
	end
	if control_fp then
		local cmeta = read_ocsp_json(control_fp)
		if meta_tombstoned(cmeta) then
			return nil, body_fp
		end
		if peer_refuse_blocks(control_fp, cmeta, nil, true) then
			return nil, body_fp
		end
		if cluster_floor_blocks(control_fp, cmeta) then
			return nil, body_fp
		end
	end
	local meta = read_ocsp_json(body_fp)
	-- Legacy shared tombstones still block (pre-isolation); new code never writes them.
	if not meta or meta_tombstoned(meta) or shard_not_paged(meta) then
		return nil, body_fp
	end
	local fresh = resp_still_fresh(nil, body_fp, meta)
	if not fresh then
		return nil, body_fp
	end
	local der = read_file(ocsp_path(body_fp))
	if type(der) ~= "string" or der == "" then
		return nil, body_fp
	end
	if not ocsp_json_ligand_matches(meta, body_fp, der) then
		return nil, body_fp
	end
	if control_fp and serial_blacklist_blocks(control_fp, der) then
		return nil, body_fp
	end
	return der, body_fp
end

-- True when any non-root chain cert carries Must-Staple (PEM TLS Feature or ocsp.json).
local function chain_has_intermediate_must_staple(chain_blocks)
	if type(chain_blocks) ~= "table" or #chain_blocks < 2 then
		return false
	end
	for i = 2, #chain_blocks do
		local pem = chain_blocks[i]
		local self_signed = false
		pcall(function()
			local x509 = require("resty.openssl.x509")
			local c = x509.new(pem)
			if c and c.get_subject_name and c.get_issuer_name then
				local s = tostring(c:get_subject_name() or "")
				local iss = tostring(c:get_issuer_name() or "")
				self_signed = (s ~= "" and s == iss)
			end
		end)
		if self_signed then
			break
		end
		if has_must_staple(pem) then
			return true
		end
		local fp = spki_fingerprint(pem)
		if fp and ocsp_json_must_staple(read_ocsp_json(fp)) then
			return true
		end
	end
	return false
end

-- Build Certificate-message-ordered OCSP DER list: leaf, then each intermediate
-- (skip self-signed / no-AIA). Missing intermediate → nil slot (OpenSSL omits that
-- CertificateEntry's status_request). Intermediate Must-Staple without a GOOD body
-- returns false, "must_staple", detail. Call only when openssl_multi_staple_ready().
local function collect_chain_staple_ders(leaf_resp, chain_blocks)
	if type(leaf_resp) ~= "string" or leaf_resp == "" then
		return nil, "unmet"
	end
	local ders = { leaf_resp }
	if type(chain_blocks) ~= "table" or #chain_blocks < 2 then
		return ders
	end
	local leaf_pem = chain_blocks[1]
	for i = 2, #chain_blocks do
		local pem = chain_blocks[i]
		-- Self-signed / trust-anchor: no status on the root.
		local self_signed = false
		pcall(function()
			local x509 = require("resty.openssl.x509")
			local c = x509.new(pem)
			if c and c.get_subject_name and c.get_issuer_name then
				local s = tostring(c:get_subject_name() or "")
				local iss = tostring(c:get_issuer_name() or "")
				self_signed = (s ~= "" and s == iss)
			end
		end)
		if self_signed then
			break
		end
		local inter_must = has_must_staple(pem)
		local der, fp = load_paged_intermediate_staple(pem, leaf_pem)
		if not der and not inter_must and fp then
			inter_must = ocsp_json_must_staple(read_ocsp_json(fp))
		end
		if not der then
			if inter_must then
				return nil, "must_staple", "response_not_found"
			end
			ders[#ders + 1] = false -- explicit NULL slot
		else
			ders[#ders + 1] = der
		end
	end
	return ders
end

-- Remember multi-staple stack shape for OCSP_STAPLED audit (NULL = legal omission).
local function note_multi_staple_attach(entries, null_slots)
	if not ngx.ctx then
		return
	end
	local n = tonumber(entries) or 0
	local nulls = tonumber(null_slots) or 0
	if n < 1 then
		ngx.ctx.bw_ocsp_multi_entries = nil
		ngx.ctx.bw_ocsp_multi_stapled = nil
		ngx.ctx.bw_ocsp_multi_null_slots = nil
		return
	end
	ngx.ctx.bw_ocsp_multi_entries = n
	ngx.ctx.bw_ocsp_multi_null_slots = nulls
	ngx.ctx.bw_ocsp_multi_stapled = n - nulls
end

local function clear_multi_staple_attach_note()
	note_multi_staple_attach(0, 0)
end

-- Attach leaf OCSP; when SSL_set0_tlsext_status_ocsp_resp_ex is present also attach
-- intermediate responses in chain order. Without that symbol: leaf-only. If an
-- intermediate requires Must-Staple, refuse with intermediate_must_staple_libssl
-- (capability gap) — never log leaf success while a TLS 1.3 client would still
-- abort on the missing CertificateEntry status.
attach_ocsp_staple = function(ocsp, leaf_resp, chain_blocks)
	local ready, st = openssl_multi_staple_ready()
	if not ready then
		clear_multi_staple_attach_note()
		if chain_has_intermediate_must_staple(chain_blocks) then
			return nil, "intermediate_must_staple_libssl"
		end
		return ocsp.set_ocsp_status_resp(leaf_resp)
	end

	local ders, why, detail = collect_chain_staple_ders(leaf_resp, chain_blocks)
	if not ders then
		clear_multi_staple_attach_note()
		if why == "must_staple" then
			return nil, detail or "unmet"
		end
		return nil, why or "unmet"
	end

	local want_multi = #ders > 1
	if not want_multi then
		clear_multi_staple_attach_note()
		return ocsp.set_ocsp_status_resp(leaf_resp)
	end

	local ssl_mod = require "ngx.ssl"
	if not ssl_mod.get_req_ssl_pointer then
		clear_multi_staple_attach_note()
		return ocsp.set_ocsp_status_resp(leaf_resp)
	end
	local ssl_ptr = ssl_mod.get_req_ssl_pointer()
	if not ssl_ptr then
		clear_multi_staple_attach_note()
		return ocsp.set_ocsp_status_resp(leaf_resp)
	end

	-- Ensure status callback is registered (ngx.ocsp leaf path does this).
	local ok_leaf, leaf_ok, leaf_warn = pcall(function()
		return ocsp.set_ocsp_status_resp(leaf_resp)
	end)
	if not ok_leaf or not leaf_ok then
		clear_multi_staple_attach_note()
		return nil, tostring(leaf_warn or leaf_ok or "set_staple_failed")
	end

	local null_slots = 0
	for _, der in ipairs(ders) do
		if der == false or der == nil then
			null_slots = null_slots + 1
		end
	end

	local ffi, C = st.ffi, st.C
	local stack = C.OPENSSL_sk_new_null()
	if stack == nil then
		clear_multi_staple_attach_note()
		return leaf_ok, leaf_warn
	end
	local parsed = {}
	local push_ok = true
	for _, der in ipairs(ders) do
		if der == false or der == nil then
			if C.OPENSSL_sk_push(stack, nil) == 0 then
				push_ok = false
				break
			end
		else
			local buf = ffi.new("unsigned char[?]", #der)
			ffi.copy(buf, der)
			local pp = ffi.new("const unsigned char *[1]")
			pp[0] = buf
			local resp_obj = C.d2i_OCSP_RESPONSE(nil, pp, #der)
			if resp_obj == nil then
				push_ok = false
				break
			end
			parsed[#parsed + 1] = resp_obj
			if C.OPENSSL_sk_push(stack, resp_obj) == 0 then
				push_ok = false
				break
			end
		end
	end
	if not push_ok then
		C.OPENSSL_sk_pop_free(stack, ffi.cast("void (*)(void *)", C.OCSP_RESPONSE_free))
		clear_multi_staple_attach_note()
		log(ngx.ERR, "OCSP multi-staple stack build failed; keeping leaf-only staple")
		return leaf_ok, leaf_warn
	end

	local ctx = C.SSL_get_SSL_CTX(ssl_ptr)
	if ctx ~= nil then
		C.SSL_CTX_set_tlsext_status_cb(ctx, st.empty_cb)
	end
	-- Ownership of stack + responses transfers to SSL on success.
	local rc = C.SSL_set0_tlsext_status_ocsp_resp_ex(ssl_ptr, stack)
	if rc == 0 then
		C.OPENSSL_sk_pop_free(stack, ffi.cast("void (*)(void *)", C.OCSP_RESPONSE_free))
		clear_multi_staple_attach_note()
		log(ngx.ERR, "OCSP SSL_set0_tlsext_status_ocsp_resp_ex failed; keeping leaf-only staple")
		return leaf_ok, leaf_warn
	end
	note_multi_staple_attach(#ders, null_slots)
	log(
		ngx.DEBUG,
		"OCSP multi-staple attached entries="
			.. tostring(#ders)
			.. " stapled="
			.. tostring(#ders - null_slots)
			.. " null_slots="
			.. tostring(null_slots)
	)
	return true
end

-- OpenSSL clears a prior connection staple when resp is NULL (SSL_certs_clear does not).
local _ssl_ocsp_clear_cdef_done = false
local function clear_connection_staple()
	local prev = ngx.ctx and ngx.ctx.bw_ocsp_stapled_fp or nil
	if ngx.ctx then
		ngx.ctx.bw_ocsp_stapled_fp = nil
		ngx.ctx.bw_ocsp_multi_entries = nil
		ngx.ctx.bw_ocsp_multi_stapled = nil
		ngx.ctx.bw_ocsp_multi_null_slots = nil
	end
	local ok_clear = pcall(function()
		local ssl_mod = require "ngx.ssl"
		if not ssl_mod.get_req_ssl_pointer then
			return
		end
		local ptr = ssl_mod.get_req_ssl_pointer()
		if not ptr then
			return
		end
		local ffi = require "ffi"
		if not _ssl_ocsp_clear_cdef_done then
			pcall(ffi.cdef, [[
				int SSL_set_tlsext_status_ocsp_resp(void *ssl, void *resp, long len);
				long SSL_ctrl(void *ssl, int cmd, long larg, void *parg);
			]])
			_ssl_ocsp_clear_cdef_done = true
		end
		-- Prefer the named API; fall back to SSL_CTRL_SET_TLSEXT_STATUS_REQ_OCSP_RESP (71).
		if ffi.C.SSL_set_tlsext_status_ocsp_resp then
			ffi.C.SSL_set_tlsext_status_ocsp_resp(ptr, nil, 0)
		else
			ffi.C.SSL_ctrl(ptr, 71, 0, nil)
		end
	end)
	if prev and ok_clear then
		log(
			ngx.DEBUG,
			"OCSP dropped connection staple on SSL context swap prev_fp="
				.. tostring(prev):sub(1, 16)
				.. "..."
		)
	end
	return ok_clear
end

local function note_connection_staple(fp)
	if ngx.ctx and type(fp) == "string" and #fp == 64 then
		ngx.ctx.bw_ocsp_stapled_fp = fp
	end
end

-- Drop the connection staple (often set from L1) when clear_certs swaps the SSL context.
-- HTTP/2 coalescing / plugin re-entry must not leave leaf A's staple on leaf B.
-- Does not delete the process-wide L1 shared-dict entry (other connections still need it).
function _M.on_ssl_context_swap(internalstore)
	return clear_connection_staple()
end

-- Classify leaf PEM as "ec", "rsa", "ed", or nil (for dual-cert staple selection).
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
		if label:find("ed25519", 1, true) or label:find("ed448", 1, true) then
			kind = "ed"
		elseif label:find("ec", 1, true) or label:find("id-ec", 1, true) then
			kind = "ec"
		elseif label:find("rsa", 1, true) then
			kind = "rsa"
		end
	end)
	return kind
end

-- OpenSSL NIDs for TLS 1.3 CertificateVerify EC/Ed schemes (OBJ_sn2nid when available).
local NID_P256, NID_P384, NID_P521, NID_ED25519, NID_ED448 = 415, 715, 716, 1087, 1088
do
	local ok_obj, objects = pcall(require, "resty.openssl.objects")
	if ok_obj and objects and objects.txtnid2nid then
		local function resolve(name, fallback)
			local n = objects.txtnid2nid(name)
			if type(n) == "number" and n > 0 then
				return n
			end
			return fallback
		end
		NID_P256 = resolve("prime256v1", NID_P256)
		NID_P384 = resolve("secp384r1", NID_P384)
		NID_P521 = resolve("secp521r1", NID_P521)
		NID_ED25519 = resolve("ED25519", NID_ED25519)
		NID_ED448 = resolve("ED448", NID_ED448)
	end
end

-- kind + curve_nid for matching ClientHello signature_algorithms schemes.
local function cert_sig_profile(cert_pem)
	local profile = { kind = nil, curve_nid = nil }
	if type(cert_pem) ~= "string" or cert_pem == "" then
		return profile
	end
	pcall(function()
		local x509 = require("resty.openssl.x509")
		local cert_obj = x509.new(cert_pem)
		local pub = cert_obj and cert_obj:get_pubkey()
		if not pub then
			return
		end
		local key_type = pub.get_key_type and pub:get_key_type() or nil
		local label = key_type
		local nid = nil
		if type(key_type) == "table" then
			label = key_type.sn or key_type.ln or key_type.nid
			nid = key_type.nid
		elseif type(key_type) == "number" then
			nid = key_type
		end
		label = tostring(label or ""):lower()
		if label:find("ed25519", 1, true) or nid == NID_ED25519 then
			profile.kind = "ed"
			profile.curve_nid = NID_ED25519
			return
		end
		if label:find("ed448", 1, true) or nid == NID_ED448 then
			profile.kind = "ed"
			profile.curve_nid = NID_ED448
			return
		end
		if label:find("rsa", 1, true) then
			profile.kind = "rsa"
			return
		end
		if label:find("ec", 1, true) or label:find("id-ec", 1, true) then
			profile.kind = "ec"
			local params = pub.get_parameters and pub:get_parameters() or nil
			if type(params) == "table" and type(params.group) == "number" and params.group > 0 then
				profile.curve_nid = params.group
			end
		end
	end)
	return profile
end

-- True when this leaf can produce a CertificateVerify for the TLS SignatureScheme.
local function leaf_matches_scheme(profile, scheme)
	if type(profile) ~= "table" or type(scheme) ~= "number" then
		return false
	end
	-- ecdsa_secp256r1_sha256 / ecdsa_secp384r1_sha384 / ecdsa_secp521r1_sha512
	if scheme == 0x0403 then
		return profile.kind == "ec" and profile.curve_nid == NID_P256
	end
	if scheme == 0x0503 then
		return profile.kind == "ec" and profile.curve_nid == NID_P384
	end
	if scheme == 0x0603 then
		return profile.kind == "ec" and profile.curve_nid == NID_P521
	end
	-- ed25519 / ed448
	if scheme == 0x0807 then
		return profile.kind == "ed" and profile.curve_nid == NID_ED25519
	end
	if scheme == 0x0808 then
		return profile.kind == "ed" and profile.curve_nid == NID_ED448
	end
	-- rsa_pkcs1_* / rsa_pss_*
	if
		scheme == 0x0401
		or scheme == 0x0501
		or scheme == 0x0601
		or scheme == 0x0804
		or scheme == 0x0805
		or scheme == 0x0806
		or scheme == 0x0809
		or scheme == 0x080a
		or scheme == 0x080b
	then
		return profile.kind == "rsa"
	end
	return false
end

-- Audit which leaf was stapled — kind + SPKI + der_sha256 + epoch this node served.
-- Multi-staple NULL slots are legal omissions: log staple_decision=ok_partial (not hollow ok).
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
	note_connection_staple(fp_s ~= "-" and fp_s or nil)
	local fields = {
		tag = "OCSP_STAPLED",
		kind = kind or "unknown",
		fp = fp_s,
		der_sha256 = der,
		epoch = epoch,
		worker = worker,
		server_name = server_name or "nil",
	}
	local decision = "ok"
	local null_slots = ngx.ctx and tonumber(ngx.ctx.bw_ocsp_multi_null_slots) or nil
	local multi_entries = ngx.ctx and tonumber(ngx.ctx.bw_ocsp_multi_entries) or nil
	local stapled_entries = ngx.ctx and tonumber(ngx.ctx.bw_ocsp_multi_stapled) or nil
	if multi_entries and multi_entries > 0 then
		fields.multi_entries = multi_entries
		fields.stapled_entries = stapled_entries or multi_entries
		fields.null_slots = null_slots or 0
		if (null_slots or 0) > 0 then
			decision = "ok_partial"
			fields.detail = "null_slot_omission"
		end
	end
	log(ngx.INFO, format_staple_decision(decision, fields))
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
		format_staple_decision(reason or "skip_slot", {
			tag = "OCSP_STAPLE_SKIP",
			kind = kind or "unknown",
			fp = fp_s,
			server_name = server_name or "nil",
		})
	)
end

-- Leaves this ClientHello can accept, in preference order (each once).
-- When signature_algorithms is present, only leaves that match an advertised
-- scheme are included — installing any other leaf would break CertificateVerify.
-- Callers try Must-Staple probe in this order so a poisoned first match can fall
-- back to another ClientHello-compatible leaf (not a leaf the client cannot use).
local function ordered_leaves_for_handshake(leaves, sigalgs_ext, prefer_kind)
	local ordered = {}
	if type(leaves) ~= "table" or #leaves == 0 then
		return ordered
	end
	if #leaves == 1 then
		ordered[1] = leaves[1]
		return ordered
	end

	local profiles = {}
	for i, leaf in ipairs(leaves) do
		local pem = leaf
		if type(leaf) == "table" then
			pem = leaf.pem or leaf.ocsp_cert or leaf.cert_pem
		end
		profiles[i] = cert_sig_profile(pem)
	end

	local seen = {}
	local function add(li)
		if seen[li] then
			return
		end
		seen[li] = true
		ordered[#ordered + 1] = leaves[li]
	end

	if type(sigalgs_ext) == "string" and #sigalgs_ext >= 2 then
		local len = sigalgs_ext:byte(1) * 256 + sigalgs_ext:byte(2)
		if len >= 2 then
			local i = 3
			local end_i = 2 + len
			if end_i > #sigalgs_ext then
				end_i = #sigalgs_ext
			end
			local matched = false
			while i + 1 <= end_i do
				local scheme = sigalgs_ext:byte(i) * 256 + sigalgs_ext:byte(i + 1)
				for li = 1, #leaves do
					if leaf_matches_scheme(profiles[li], scheme) then
						matched = true
						add(li)
					end
				end
				i = i + 2
			end
			if matched then
				return ordered
			end
		end
	end

	-- Coarse prefer_kind fallback (no usable sigalgs match).
	if prefer_kind == "rsa" or prefer_kind == "ec" or prefer_kind == "ed" then
		for li = 1, #leaves do
			if profiles[li].kind == prefer_kind then
				add(li)
			end
		end
		if #ordered > 0 then
			return ordered
		end
	end

	-- Typical OpenSSL dual-cert default: ECDSA before RSA.
	for li = 1, #leaves do
		if profiles[li].kind == "ec" or profiles[li].kind == "ed" then
			add(li)
		end
	end
	for li = 1, #leaves do
		add(li)
	end
	return ordered
end

-- First of ordered_leaves_for_handshake (legacy single-pick API).
local function select_leaf_for_handshake(leaves, sigalgs_ext, prefer_kind)
	local ordered = ordered_leaves_for_handshake(leaves, sigalgs_ext, prefer_kind)
	return ordered[1]
end

local function leaf_pem_of(leaf)
	if type(leaf) == "string" then
		return leaf
	end
	if type(leaf) == "table" then
		return leaf.pem or leaf.ocsp_cert or leaf.cert_pem
	end
	return nil
end

local function leaf_fp_of(leaf)
	if type(leaf) ~= "table" then
		return nil
	end
	if type(leaf.fp) == "string" and #leaf.fp == 64 then
		return leaf.fp
	end
	if type(leaf.ocsp_fp_hint) == "string" and #leaf.ocsp_fp_hint == 64 then
		return leaf.ocsp_fp_hint
	end
	local pem = leaf_pem_of(leaf)
	return pem and spki_fingerprint(pem) or nil
end

-- Log siblings not presented on this handshake (single Certificate leaf).
local function log_skipped_sibling_leaves(leaves, chosen, server_name)
	if type(leaves) ~= "table" or not chosen then
		return
	end
	local chosen_pem = leaf_pem_of(chosen)
	local chosen_kind = cert_pubkey_kind(chosen_pem) or "unknown"
	for _, leaf in ipairs(leaves) do
		if leaf ~= chosen then
			local pem = leaf_pem_of(leaf)
			local kind = cert_pubkey_kind(pem) or "unknown"
			local reason = "single_slot_ecdsa_prefer"
			if chosen_kind == "rsa" then
				reason = "single_slot_rsa_prefer"
			end
			log_ocsp_staple_skip(kind, leaf_fp_of(leaf) or spki_fingerprint(pem), reason, server_name)
		end
	end
end

-- Back-compat: PEM-block list + prefer_kind → one PEM string.
local function select_preferred_leaf(blocks, prefer_kind)
	if not blocks or #blocks == 0 then
		return nil
	end
	local leaves = {}
	for _, block in ipairs(blocks) do
		leaves[#leaves + 1] = block
	end
	local sigalgs_ext = ngx.ctx and ngx.ctx.bw_ocsp_sigalgs_ext or nil
	return select_leaf_for_handshake(leaves, sigalgs_ext, prefer_kind)
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

-- Install the single leaf this handshake will present (dual-cert: one of RSA/ECDSA).
-- prefer_kind / ClientHello signature_algorithms select which leaf; only that leaf is
-- set_cert'd so the OCSP staple cannot land on a different CertificateEntry.
-- Returns: true, leaf_pem, leaf_fp  OR  false, err_msg [, detail]
function _M.set_certs_from_pem(cert_pem, key_pem, internalstore, server_name, prefer_kind)
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

	local sigalgs_ext = ngx.ctx and ngx.ctx.bw_ocsp_sigalgs_ext or nil
	local candidates = ordered_leaves_for_handshake(leaves, sigalgs_ext, prefer_kind)
	if #candidates == 0 then
		return false, "no leaf selected"
	end

	local mode = "normal"
	if internalstore then
		mode = ocsp_staple_mode(internalstore, server_name)
	end

	local function install_one(leaf, probe_must)
		local chain_pem = leaf.pem
		for _, intermediate in ipairs(intermediates) do
			chain_pem = chain_pem .. "\n" .. intermediate
		end
		local leaf_must = false
		if probe_must then
			leaf_must = has_must_staple(leaf.pem)
			if not leaf_must and leaf.fp then
				leaf_must = ocsp_json_must_staple(read_ocsp_json(leaf.fp))
			end
			if leaf_must and mode == "open" then
				leaf_must = false
			end
		end
		if leaf_must and internalstore and mode ~= "open" then
			local probe_ok, probe_reason, probe_detail = _M.probe(internalstore, server_name, chain_pem, leaf.fp, false)
			if not probe_ok then
				local detail = probe_detail or probe_reason or "probe_failed"
				if leaf.fp and mode == "normal" then
					record_peer_refuse(leaf.fp, read_ocsp_json(leaf.fp), nil, detail)
				end
				log(
					ngx.ERR,
					format_staple_decision(detail, {
						tag = "OCSP_MUST_STAPLE_REFUSE",
						action = "skip_leaf",
						mode = mode,
						fp = tostring(leaf.fp and leaf.fp:sub(1, 16) or "nil") .. "...",
					})
				)
				return false, "must_staple", detail
			end
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
		return true, leaf.pem, leaf.fp
	end

	-- Try ClientHello-compatible leaves in preference order. A poisoned Must-Staple
	-- shard on the first match must not fail-close when a later match can staple.
	local last_err, last_detail
	local preferred = candidates[1]
	for ci, leaf in ipairs(candidates) do
		local ok_inst, a, b = install_one(leaf, true)
		if ok_inst then
			if ci > 1 then
				log(
					ngx.NOTICE,
					format_staple_decision("skip_slot", {
						tag = "OCSP_STAPLE_HEALTH_FALLBACK",
						detail = "staple_health_fallback",
						fp = tostring(leaf.fp and leaf.fp:sub(1, 16) or "nil") .. "...",
						server_name = server_name or "nil",
					})
				)
			end
			log_skipped_sibling_leaves(leaves, leaf, server_name)
			return true, a, b
		end
		last_err, last_detail = a, b
		if a ~= "must_staple" then
			-- Parse / set_cert failure: do not keep trying siblings for that error class.
			break
		end
	end
	if last_err == "must_staple" and (mode == "staple_only" or mode == "open") then
		-- Soft fuse: present the preferred site leaf unstapled (not a random sibling).
		log(
			ngx.ERR,
			format_staple_decision(last_detail or "probe_failed", {
				tag = "OCSP_MUST_STAPLE_REFUSE",
				action = "continue_install",
				mode = mode,
			})
		)
		local ok_soft, soft_pem, soft_fp = install_one(preferred, false)
		if ok_soft then
			log_skipped_sibling_leaves(leaves, preferred, server_name)
			return true, soft_pem, soft_fp
		end
		return false, soft_pem or "must_staple", soft_fp or last_detail
	end
	return false, last_err, last_detail
end

function _M.select_leaf_for_handshake(leaves, sigalgs_ext, prefer_kind)
	return select_leaf_for_handshake(leaves, sigalgs_ext, prefer_kind)
end

function _M.ordered_leaves_for_handshake(leaves, sigalgs_ext, prefer_kind)
	return ordered_leaves_for_handshake(leaves, sigalgs_ext, prefer_kind)
end

-- Staple using only a precomputed SPKI fingerprint (plugin status[5]) when PEM is unavailable.
-- Acceptance: prior crypto-verified L1 binding, or job meta that binds fingerprint + der_sha256
-- to the exact DER bytes. Never promote fingerprint-only accepts to ocsp_verified.
local function staple_from_fingerprint(internalstore, server_name, fingerprint, probe_only, mode)
	mode = mode or "normal"
	local meta = read_ocsp_json(fingerprint)
	local must_staple = ocsp_json_must_staple(meta)
	if meta_tombstoned(meta) then
		drop_cache(internalstore, fingerprint)
		if must_staple then
			return must_staple_refuse(fingerprint, meta, nil, "tombstoned", mode)
		end
		return false
	end
	do
		local peer_dec = peer_refuse_blocks(fingerprint, meta, nil)
		if peer_dec then
			if must_staple then
				return false, "must_staple", peer_dec
			end
			return false
		end
	end
	if must_staple then
		log(ngx.INFO, "OCSP-Must-Staple from ocsp.json for fp=" .. fingerprint:sub(1, 16) .. "...")
	end

	if must_staple and cluster_floor_blocks(fingerprint, meta) then
		return must_staple_refuse(fingerprint, meta, nil, "cluster_floor", mode)
	end
	if shard_not_paged(meta) then
		if must_staple then
			return must_staple_refuse(fingerprint, meta, nil, "not_paged", mode)
		end
		return false
	end

	local aia_ok, aia_why = aia_uri_pin_ok(nil, meta, must_staple)
	if not aia_ok then
		if must_staple then
			return must_staple_refuse(fingerprint, meta, nil, aia_why or "aia_uri_mismatch", mode)
		end
		return false
	end

	if not stapling_enabled(internalstore, server_name) then
		if must_staple then
			return must_staple_refuse(fingerprint, meta, nil, "ssl_use_ocsp_stapling_no", mode)
		end
		log_stapling_off("ssl_use_ocsp_stapling_no")
		return false
	end

	local ok_ocsp, ocsp = pcall(require, "ngx.ocsp")
	if not ok_ocsp or not ocsp or not ocsp.set_ocsp_status_resp then
		if must_staple then
			return must_staple_refuse(fingerprint, meta, nil, "ngx_ocsp_unavailable", mode)
		end
		log(ngx.DEBUG, format_staple_decision("stapling_off", { tag = "OCSP_STAPLING_OFF", detail = "ngx_ocsp_unavailable" }))
		return false
	end

	local cached, cached_verified, cached_epoch, cached_expires = get_l1(internalstore, fingerprint)
	if cached then
		if not l1_matches_disk(internalstore, fingerprint, cached, cached_epoch) then
			drop_cache(internalstore, fingerprint)
		else
			local fresh, fresh_why = resp_still_fresh(cached_expires, fingerprint, meta)
			if not fresh then
				log(ngx.ERR, "OCSP L1 response past nextUpdate/expires; discarding fp=" .. fingerprint:sub(1, 16) .. "...")
				drop_cache(internalstore, fingerprint)
				if must_staple then
					return must_staple_refuse(fingerprint, meta, nil, fresh_why or "response_stale", mode)
				end
			else
			if serial_blacklist_blocks(fingerprint, cached) then
				drop_cache(internalstore, fingerprint)
				if must_staple then
					return must_staple_refuse(fingerprint, meta, nil, "serial_blacklisted", mode)
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
					return must_staple_refuse(fingerprint, meta, nil, ligand_detail, mode)
				end
				local ok_id, why = certid_consistent_with_meta(meta or read_ocsp_json(fingerprint), cached)
				if not ok_id then
					log(ngx.ERR, "OCSP CertID refuse fingerprint staple reason=" .. tostring(why) .. " fp=" .. fingerprint:sub(1, 16) .. "...")
					drop_cache(internalstore, fingerprint)
					if must_staple then
						return must_staple_refuse(fingerprint, meta, nil, "certid_mismatch", mode)
					end
					return false
				end
				if probe_only then
					return true
				end
				local set_ok, set_err
				local ok_set = pcall(function()
					set_ok, set_err = attach_ocsp_staple(ocsp, cached, nil)
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
	end

	local resp = read_file(ocsp_path(fingerprint))
	if resp then
		local fresh, fresh_why = resp_still_fresh(nil, fingerprint, meta)
		if not fresh then
			log(ngx.ERR, "OCSP disk response past nextUpdate/expires; refusing staple fp=" .. fingerprint:sub(1, 16) .. "...")
			if must_staple then
				return must_staple_refuse(fingerprint, meta, nil, fresh_why or "response_stale", mode)
			end
			return false
		end
		-- Disk path: verified binding only exists in L1; after drop/miss, require meta authorize
		-- or a concurrent warmer rewrite. Re-check composite if rewarmed.
		local _, disk_verified = get_l1(internalstore, fingerprint)
		if serial_blacklist_blocks(fingerprint, resp) then
			if must_staple then
				return must_staple_refuse(fingerprint, meta, nil, "serial_blacklisted", mode)
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
				return must_staple_refuse(fingerprint, meta, nil, ligand_detail, mode)
			end
			local ok_id, why = certid_consistent_with_meta(meta, resp)
			if not ok_id then
				log(ngx.ERR, "OCSP CertID refuse fingerprint staple reason=" .. tostring(why) .. " fp=" .. fingerprint:sub(1, 16) .. "...")
				if must_staple then
					return must_staple_refuse(fingerprint, meta, nil, "certid_mismatch", mode)
				end
				return false
			end
			if probe_only then
				return true
			end
			local set_ok, set_err
			local ok_set = pcall(function()
				set_ok, set_err = attach_ocsp_staple(ocsp, resp, nil)
			end)
			if ok_set and set_ok then
				warm_cache(internalstore, fingerprint, resp, verified, meta_effective_expires_unix(meta))
				log_ocsp_stapled(server_name, nil, fingerprint, resp)
				return true
			end
			log(ngx.ERR, "OCSP failed to set stapling: " .. tostring(set_err or set_ok))
			if must_staple then
				return must_staple_refuse(fingerprint, meta, nil, "set_staple_failed", mode)
			end
			return false
		end
	end

	if must_staple then
		return must_staple_refuse(fingerprint, meta, nil, "response_not_found", mode)
	end
	return false
end

local function staple_one_leaf(internalstore, ocsp, ssl, blocks, leaf_pem, fingerprint, must_staple, server_name, probe_only, mode)
	mode = mode or "normal"
	if not fingerprint then
		return nil
	end
	local issuers = nil
	local shard_issuer_pem = read_file(issuer_path(fingerprint))
	local shard_issuer_spki = shard_issuer_pem and spki_fingerprint(shard_issuer_pem) or nil
	local meta = read_ocsp_json(fingerprint)
	if meta_tombstoned(meta) then
		drop_cache(internalstore, fingerprint)
		if must_staple then
			return must_staple_refuse(fingerprint, meta, nil, "tombstoned", mode)
		end
		return false
	end
	do
		local peer_dec = peer_refuse_blocks(fingerprint, meta, nil)
		if peer_dec then
			if must_staple then
				return false, "must_staple", peer_dec
			end
			return false
		end
	end
	if must_staple and cluster_floor_blocks(fingerprint, meta) then
		return must_staple_refuse(fingerprint, meta, nil, "cluster_floor", mode)
	end
	if shard_not_paged(meta) then
		if must_staple then
			return must_staple_refuse(fingerprint, meta, nil, "not_paged", mode)
		end
		return false
	end
	local aia_ok, aia_why = aia_uri_pin_ok(leaf_pem, meta, must_staple)
	if not aia_ok then
		if must_staple then
			return must_staple_refuse(fingerprint, meta, nil, aia_why or "aia_uri_mismatch", mode)
		end
		return false
	end
	local cached, cached_verified, cached_epoch, cached_expires = get_l1(internalstore, fingerprint)
	if cached then
		if not l1_matches_disk(internalstore, fingerprint, cached, cached_epoch) then
			drop_cache(internalstore, fingerprint)
		else
			local fresh, fresh_why = resp_still_fresh(cached_expires, fingerprint, meta)
			if not fresh then
				log(ngx.ERR, "OCSP L1 response past nextUpdate/expires; discarding fp=" .. fingerprint:sub(1, 16) .. "...")
				drop_cache(internalstore, fingerprint)
				if must_staple then
					return must_staple_refuse(fingerprint, meta, nil, fresh_why or "response_stale", mode)
				end
			elseif entry_verified(cached_verified, cached) then
			if serial_blacklist_blocks(fingerprint, cached) then
				drop_cache(internalstore, fingerprint)
				if must_staple then
					return must_staple_refuse(fingerprint, meta, nil, "serial_blacklisted", mode)
				end
				return false
			end
			issuers = issuer_candidates(blocks, leaf_pem, fingerprint)
			local ok_id, why = certid_matches_handshake_leaf(leaf_pem, cached, issuers)
			if not ok_id then
				log(ngx.ERR, "OCSP CertID refuse L1 staple reason=" .. tostring(why) .. " fp=" .. fingerprint:sub(1, 16) .. "...")
				drop_cache(internalstore, fingerprint)
				if must_staple then
					return must_staple_refuse(fingerprint, meta, nil, "certid_mismatch", mode)
				end
				-- Fall through to disk / re-validate with the current leaf.
			else
			-- Must-Staple: bind shared ocsp.json ligand, not stream-private L1 alone.
			if must_staple then
				meta = meta or read_ocsp_json(fingerprint)
				local ligand_ok, ligand_detail = must_staple_binds_shared_ligand(meta, fingerprint, cached)
				if not ligand_ok then
					drop_cache(internalstore, fingerprint)
					return must_staple_refuse(fingerprint, meta, nil, ligand_detail, mode)
				end
			end
			if probe_only then
				return true
			end
			local set_ok, set_err
			local ok_set = pcall(function()
				set_ok, set_err = attach_ocsp_staple(ocsp, cached, blocks)
			end)
			if ok_set and set_ok then
				log_ocsp_stapled(server_name, cert_pubkey_kind(leaf_pem), fingerprint, cached)
				return true
			end
			local attach_detail = tostring(set_err or set_ok)
			log(ngx.ERR, "OCSP failed to set stapling from L1: " .. attach_detail)
			drop_cache(internalstore, fingerprint)
			if attach_detail == "intermediate_must_staple_libssl" or must_staple then
				local detail = attach_detail
				if detail ~= "intermediate_must_staple_libssl" then
					detail = "set_staple_failed"
				end
				return must_staple_refuse(fingerprint, meta, cached, detail, mode)
			end
			end
		else
			if serial_blacklist_blocks(fingerprint, cached) then
				drop_cache(internalstore, fingerprint)
				if must_staple then
					return must_staple_refuse(fingerprint, meta, nil, "serial_blacklisted", mode)
				end
				return false
			end
			issuers = issuer_candidates(blocks, leaf_pem, fingerprint)
			local result, result_detail = try_staple(ocsp, ssl, cached, leaf_pem, issuers, shard_issuer_spki, probe_only, meta, fingerprint, blocks)
			if result == true then
				if must_staple then
					meta = meta or read_ocsp_json(fingerprint)
					local ligand_ok, ligand_detail = must_staple_binds_shared_ligand(meta, fingerprint, cached)
					if not ligand_ok then
						drop_cache(internalstore, fingerprint)
						return must_staple_refuse(fingerprint, meta, nil, ligand_detail, mode)
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
				if result_detail == "validate_budget" then
					if must_staple then
						return must_staple_refuse(fingerprint, meta, cached, "validate_budget", mode)
					end
					return false
				end
				if result_detail == "intermediate_must_staple_libssl" or must_staple then
					-- CertID fails before canary; false + canary ligand ⇒ set_ocsp_status_resp miss.
					local detail = result_detail
					if detail ~= "intermediate_must_staple_libssl" then
						detail = canary_paged_body_ok(meta, fingerprint, cached) and "set_staple_failed" or "unmet"
					end
					return must_staple_refuse(fingerprint, meta, cached, detail, mode)
				end
				return false
			end
			drop_cache(internalstore, fingerprint)
		end
		end
	end

	local resp = read_file(ocsp_path(fingerprint))
	if resp then
		meta = meta or read_ocsp_json(fingerprint)
		local fresh, fresh_why = resp_still_fresh(nil, fingerprint, meta)
		if not fresh then
			log(ngx.ERR, "OCSP disk response past nextUpdate/expires; refusing staple fp=" .. fingerprint:sub(1, 16) .. "...")
			if must_staple then
				return must_staple_refuse(fingerprint, meta, nil, fresh_why or "response_stale", mode)
			end
			return false
		end
		issuers = issuers or issuer_candidates(blocks, leaf_pem, fingerprint)
		if serial_blacklist_blocks(fingerprint, resp) then
			if must_staple then
				return must_staple_refuse(fingerprint, meta, nil, "serial_blacklisted", mode)
			end
			return false
		end
		local result, result_detail = try_staple(ocsp, ssl, resp, leaf_pem, issuers, shard_issuer_spki, probe_only, meta, fingerprint, blocks)
		if result == true then
			local ligand_ok, ligand_detail = must_staple_binds_shared_ligand(meta, fingerprint, resp)
			if must_staple and not ligand_ok then
				return must_staple_refuse(fingerprint, meta, nil, ligand_detail, mode)
			end
			if probe_only then
				return true
			end
			warm_cache(internalstore, fingerprint, resp, true, meta_effective_expires_unix(meta))
			log_ocsp_stapled(server_name, cert_pubkey_kind(leaf_pem), fingerprint, resp)
			return true
		end
		if result == false then
			if result_detail == "validate_budget" then
				if must_staple then
					return must_staple_refuse(fingerprint, meta, resp, "validate_budget", mode)
				end
				return false
			end
			if result_detail == "intermediate_must_staple_libssl" or must_staple then
				local detail = result_detail
				if detail ~= "intermediate_must_staple_libssl" then
					detail = canary_paged_body_ok(meta, fingerprint, resp) and "set_staple_failed" or "unmet"
				end
				return must_staple_refuse(fingerprint, meta, resp, detail, mode)
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
			return soften_must_staple(mode, staple_from_fingerprint(internalstore, server_name, fp_hint, false, mode))
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
		log(ngx.DEBUG, format_staple_decision("stapling_off", { tag = "OCSP_STAPLING_OFF", detail = "ngx_ocsp_unavailable" }))
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

	local result, reason, detail = staple_one_leaf(internalstore, ocsp, ssl, blocks, leaf_pem, fingerprint, must_staple, server_name, false, mode)
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
-- Must-Staple leaves must pass this before set_cert (normal and staple_only). Soft fuses
-- only affect handshake abort after install fails entirely — not the skip-leaf gate.
-- Pass apply_soften=false for skip-leaf callers that log their own action
-- (e.g. set_certs_from_pem). open mode short-circuits to true (Must-Staple off).
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
			local ok, reason, detail = staple_from_fingerprint(internalstore, server_name, fp_hint, true, mode)
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
	local result, reason, detail = staple_one_leaf(internalstore, ocsp, ssl, blocks, leaf_pem, fingerprint, true, server_name, true, mode)
	if result == true then
		return true
	end
	if result == false then
		return finish(false, reason, detail)
	end
	return finish(false, "must_staple", "response_not_found")
end


-- Cross-subsystem generation refuse bus (HTTP ↔ stream).
function _M.peer_refuse_blocks(fingerprint, der_sha256_or_meta, resp)
	local meta = der_sha256_or_meta
	if type(der_sha256_or_meta) == "string" then
		meta = { der_sha256 = der_sha256_or_meta }
	end
	return peer_refuse_blocks(fingerprint, meta, resp)
end

function _M.record_peer_refuse(fingerprint, der_sha256_or_meta, decision, resp)
	local meta = der_sha256_or_meta
	if type(der_sha256_or_meta) == "string" then
		meta = { der_sha256 = der_sha256_or_meta }
	end
	return record_peer_refuse(fingerprint, meta, resp, decision)
end

function _M.clear_peer_refuse(fingerprint)
	if not is_fp64(fingerprint) then
		return false
	end
	local path = ocsp_refuse_path(fingerprint)
	local ok = os.remove(path)
	return ok and true or false
end

-- True when the leaf PEM or ocsp.json marks Must-Staple (TLS Feature status_request).
function _M.requires_must_staple(cert_pem, cert_fp_hint)
	local fp_hint = normalize_fp_hint(cert_fp_hint)
	if type(cert_pem) == "string" and cert_pem ~= "" then
		local blocks = pem_blocks(cert_pem)
		local leaf_pem = blocks[1]
		if leaf_pem and has_must_staple(leaf_pem) then
			return true
		end
		local leaf_fp = leaf_pem and spki_fingerprint(leaf_pem, nil) or nil
		if leaf_fp and ocsp_json_must_staple(read_ocsp_json(leaf_fp)) then
			return true
		end
	end
	if fp_hint and ocsp_json_must_staple(read_ocsp_json(fp_hint)) then
		return true
	end
	return false
end

-- Parse ClientHello signature_algorithms (ext 13) → "ec", "rsa", "ed", or nil.
-- Coarse kind only; curve-aware selection uses the raw extension via select_leaf_for_handshake.
function _M.prefer_kind_from_sigalgs(ext)
	if type(ext) ~= "string" or #ext < 2 then
		return nil
	end
	local len = ext:byte(1) * 256 + ext:byte(2)
	if len < 2 then
		return nil
	end
	local i = 3
	local end_i = 2 + len
	if end_i > #ext then
		end_i = #ext
	end
	while i + 1 <= end_i do
		local scheme = ext:byte(i) * 256 + ext:byte(i + 1)
		if scheme == 0x0403 or scheme == 0x0503 or scheme == 0x0603 then
			return "ec"
		end
		if scheme == 0x0807 or scheme == 0x0808 then
			return "ed"
		end
		if
			scheme == 0x0401
			or scheme == 0x0501
			or scheme == 0x0601
			or scheme == 0x0804
			or scheme == 0x0805
			or scheme == 0x0806
			or scheme == 0x0809
			or scheme == 0x080a
			or scheme == 0x080b
		then
			return "rsa"
		end
		i = i + 2
	end
	return nil
end

-- Capture SNI + preferred leaf kind during ssl_client_hello (HTTP and stream).
-- Stores on ngx.ctx for the later ssl_certificate leaf pick / staple.
function _M.capture_client_hello()
	local ctx = ngx.ctx
	if not ctx then
		return
	end
	local ok_clt, ssl_clt = pcall(require, "ngx.ssl.clienthello")
	if not ok_clt or not ssl_clt then
		return
	end
	if ssl_clt.get_client_hello_server_name then
		local host = ssl_clt.get_client_hello_server_name()
		if type(host) == "string" and host ~= "" then
			ctx.bw_ocsp_sni = host
		end
	end
	if ssl_clt.get_client_hello_ext then
		local ext = ssl_clt.get_client_hello_ext(13)
		if type(ext) == "string" and #ext >= 2 then
			ctx.bw_ocsp_sigalgs_ext = ext
		end
		local kind = _M.prefer_kind_from_sigalgs(ext)
		if kind then
			ctx.bw_ocsp_prefer_kind = kind
		end
	end
end

-- Back-compat alias used by stream conf before HTTP shared the same capture.
_M.capture_stream_client_hello = _M.capture_client_hello

-- Resolve the handshake SNI for stream stapling (ssl.server_name, else client-hello ctx).
function _M.handshake_sni(fallback)
	local ssl = require "ngx.ssl"
	local sni = ssl.server_name and ssl.server_name() or nil
	if type(sni) == "string" and sni ~= "" then
		return sni
	end
	local ctx = ngx.ctx
	if ctx and type(ctx.bw_ocsp_sni) == "string" and ctx.bw_ocsp_sni ~= "" then
		return ctx.bw_ocsp_sni
	end
	if type(fallback) == "string" and fallback ~= "" then
		return fallback
	end
	return nil
end

-- --- Off-handshake L1 warmer -------------------------------------------------
-- Cold L1 misses used to open ocsp.der (+ often validate) inside ssl_certificate.
-- Worker timers preload paged shards into the subsystem shared dict so the
-- critical path stays on get_l1 whenever possible. HTTP and stream each warm
-- their own zone (dicts are not shared across subsystems).
--
-- Every worker arms a timer; a short shared-dict lease ensures only one scans
-- disk at a time. If the holder dies, the lease expires and another worker
-- takes over before L1_MAX_TTL (300s) empties DRAM onto the TLS path.

local L1_WARMER_INTERVAL = 5
local L1_WARMER_RESCAN = 60
-- Must be well under L1_MAX_TTL so failover re-warms before shm entries expire.
local L1_WARMER_LEASE_TTL = math.max(L1_WARMER_INTERVAL * 3, 20)
local L1_WARMER_LEASE_KEY = "TLS:SSL:ocsp_l1_warmer_lease"
local l1_warmer_started = false
local l1_warmer_last_epoch = nil
local l1_warmer_last_full = 0

local function warmer_lease_token()
	local wid = (ngx.worker and ngx.worker.id and ngx.worker.id()) or 0
	local pid = (ngx.worker and ngx.worker.pid and ngx.worker.pid()) or 0
	return tostring(wid) .. ":" .. tostring(pid)
end

-- True when this worker holds (or just claimed) the scan lease for this subsystem.
local function claim_l1_warmer_lease(internalstore)
	if not internalstore then
		return false
	end
	local token = warmer_lease_token()
	local cur = nil
	pcall(function()
		cur = internalstore:get(L1_WARMER_LEASE_KEY)
	end)
	if cur == token then
		pcall(function()
			internalstore:set(L1_WARMER_LEASE_KEY, token, L1_WARMER_LEASE_TTL)
		end)
		return true
	end
	if cur ~= nil and cur ~= "" then
		return false
	end
	-- Lease free: atomic add when the raw dict is available, else set+recheck.
	local claimed = false
	pcall(function()
		local dict = internalstore.dict
		if dict and dict.add then
			claimed = dict:add(L1_WARMER_LEASE_KEY, token, L1_WARMER_LEASE_TTL) and true or false
			return
		end
		internalstore:set(L1_WARMER_LEASE_KEY, token, L1_WARMER_LEASE_TTL)
		local check = internalstore:get(L1_WARMER_LEASE_KEY)
		claimed = check == token
	end)
	return claimed
end

local function list_ocsp_fingerprints()
	local fps = {}
	local root = "/var/cache/bunkerweb/ssl"
	local ok_lfs, lfs = pcall(require, "lfs")
	if ok_lfs and lfs and lfs.dir then
		local ok_root, iter = pcall(lfs.dir, root)
		if ok_root and iter then
			for a in iter do
				if type(a) == "string" and #a == 1 and a:match("^[0-9a-f]$") then
					local path_a = root .. "/" .. a
					local ok_a, iter_a = pcall(lfs.dir, path_a)
					if ok_a and iter_a then
						for b in iter_a do
							if type(b) == "string" and #b == 1 and b:match("^[0-9a-f]$") then
								local path_b = path_a .. "/" .. b
								local ok_b, iter_b = pcall(lfs.dir, path_b)
								if ok_b and iter_b then
									for fp in iter_b do
										if is_fp64(fp) then
											fps[#fps + 1] = fp
										end
									end
								end
							end
						end
					end
				end
			end
		end
		return fps
	end
	local ok_p, pipe = pcall(io.popen, "find " .. root .. " -mindepth 3 -maxdepth 3 -type d 2>/dev/null")
	if not ok_p or not pipe then
		return fps
	end
	for line in pipe:lines() do
		local fp = line:match("([0-9a-f]+)$")
		if is_fp64(fp) then
			fps[#fps + 1] = fp
		end
	end
	pipe:close()
	return fps
end

-- Load one paged shard into L1 without crypto validate (meta ligand is enough
-- for the handshake authorize path). Runs off the TLS critical path only.
-- Do not re-warm generations the handshake would refuse (peer-refuse bus or
-- serial-blacklist): that churns shm and forces refuse/drop on every hit.
local function warm_one_shard(internalstore, fingerprint)
	if not internalstore or not is_fp64(fingerprint) then
		return false
	end
	local meta = read_ocsp_json(fingerprint)
	if not meta or meta_tombstoned(meta) or shard_not_paged(meta) then
		drop_cache(internalstore, fingerprint)
		return false
	end
	if not resp_still_fresh(nil, fingerprint, meta) then
		drop_cache(internalstore, fingerprint)
		return false
	end
	local resp = read_file(ocsp_path(fingerprint))
	if type(resp) ~= "string" or resp == "" then
		drop_cache(internalstore, fingerprint)
		return false
	end
	local ligand_ok = ocsp_json_ligand_matches(meta, fingerprint, resp)
	if not ligand_ok then
		drop_cache(internalstore, fingerprint)
		return false
	end
	if peer_refuse_blocks(fingerprint, meta, resp, true) then
		drop_cache(internalstore, fingerprint)
		return false
	end
	if serial_blacklist_blocks(fingerprint, resp) then
		drop_cache(internalstore, fingerprint)
		return false
	end
	-- mark_verified=false: no leaf PEM here; handshake may still authorize via meta.
	warm_cache(internalstore, fingerprint, resp, false, meta_effective_expires_unix(meta))
	return true
end

-- Scan the OCSP cache tree and warm every paged GOOD shard into this subsystem's L1.
-- Returns warmed count.
function _M.warm_l1_from_disk(internalstore)
	if not internalstore then
		return 0
	end
	local warmed = 0
	for _, fp in ipairs(list_ocsp_fingerprints()) do
		local ok, did = pcall(warm_one_shard, internalstore, fp)
		if ok and did then
			warmed = warmed + 1
		end
	end
	if warmed > 0 then
		log(ngx.INFO, "OCSP L1 warmer loaded " .. tostring(warmed) .. " shard(s) subsystem=" .. tostring(ngx.config.subsystem))
	end
	return warmed
end

-- Start a recurring timer (once per worker Lua VM). A shared-dict lease picks
-- one scanner so N workers do not all walk disk; lease expiry lets another
-- worker take over if the holder dies before L1_MAX_TTL.
function _M.start_l1_warmer(internalstore)
	if not internalstore then
		return false
	end
	if l1_warmer_started then
		return true
	end
	if not ngx.timer or not ngx.timer.at then
		return false
	end
	-- Off handshake: ensure peer-refuse bus directory exists before any refuse write.
	if not ensure_ocsp_refuse_dir() then
		log(ngx.ERR, "OCSP could not provision ocsp-refuse/ dir; peer-refuse bus writes may fail")
	end
	-- Publish multi-staple attach capability for ocsp-refresh (intermediate fetch gate).
	pcall(openssl_multi_staple_ready)
	l1_warmer_started = true

	local function tick(premature)
		if premature then
			return
		end
		if claim_l1_warmer_lease(internalstore) then
			local epoch = current_ocsp_epoch()
			local now = ngx.time()
			-- Re-warm on publish (epoch bump) or periodically so shm TTL expiry
			-- does not push the next handshake onto a cold ocsp.der read.
			local need = epoch ~= l1_warmer_last_epoch or (now - l1_warmer_last_full) >= L1_WARMER_RESCAN
			if need then
				l1_warmer_last_epoch = epoch
				l1_warmer_last_full = now
				pcall(_M.warm_l1_from_disk, internalstore)
			end
		end
		local ok, err = ngx.timer.at(L1_WARMER_INTERVAL, tick)
		if not ok then
			l1_warmer_started = false
			log(ngx.ERR, "OCSP L1 warmer reschedule failed: " .. tostring(err))
		end
	end

	-- Stagger first tick by worker id so startup claims are not a thundering herd.
	local wid = (ngx.worker and ngx.worker.id and ngx.worker.id()) or 0
	local delay = (tonumber(wid) or 0) * 0.05
	local ok, err = ngx.timer.at(delay, tick)
	if not ok then
		l1_warmer_started = false
		log(ngx.ERR, "OCSP L1 warmer start failed: " .. tostring(err))
		return false
	end
	log(
		ngx.INFO,
		"OCSP L1 warmer armed worker="
			.. tostring(wid)
			.. " lease_ttl="
			.. tostring(L1_WARMER_LEASE_TTL)
			.. "s subsystem="
			.. tostring(ngx.config.subsystem)
	)
	return true
end


function _M.attach_ocsp_staple(leaf_resp, chain_pem_or_blocks)
	local ok_ocsp, ocsp = pcall(require, "ngx.ocsp")
	if not ok_ocsp or not ocsp or not ocsp.set_ocsp_status_resp then
		return nil, "ngx_ocsp_unavailable"
	end
	local blocks = chain_pem_or_blocks
	if type(blocks) == "string" then
		blocks = pem_blocks(blocks)
	end
	return attach_ocsp_staple(ocsp, leaf_resp, blocks)
end

return _M
