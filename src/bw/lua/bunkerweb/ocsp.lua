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
-- Stapling off (SSL_USE_OCSP_STAPLING=no, the default) → effective "open": no
-- staple can be served, so Must-Staple is not enforced (upstream served unstapled).
local function ocsp_staple_mode(internalstore, server_name)
	if not stapling_enabled(internalstore, server_name) then
		return "open"
	end
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
	allow_pin_missing = true,
	allow_pin_expired = true,
	allow_pin_mismatch = true,
	await_sni = true,
	intermediate_must_staple_libssl = true,
	-- Colony min is leaf-only (a live peer lacks multi-staple); not a local libssl gap.
	-- Transient: must not stick after the leaf-only worker leaves.
	intermediate_must_staple_colony = true,
	-- Fingerprint-only attach/probe with no PEM chain: intermediate Must-Staple unprovable.
	fingerprint_chain_unavailable = true,
	-- Multi-staple stack build / SSL_set0 failed after leaf set; intermediate MS refused.
	multi_staple_attach_failed = true,
	-- Issuer DN in the bag did not resolve, and Must-Staple intermediates were
	-- omitted from the presented chain. Refuse so leaf-only attach cannot
	-- succeed while those intermediates were in the bag.
	issuer_unresolved_must_staple = true,
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
	-- Raw ligand_verdict reasons stay on refuse_cause=; runbook staple_decision=
	-- collapses to shared_ligand so ops still land on one README section.
	ligand_missing = "shared_ligand",
	ligand_mismatch = "shared_ligand",
	der_sha256_mismatch = "shared_ligand",
	missing_der_sha256 = "shared_ligand",
	invalid_der_sha256 = "shared_ligand",
	fingerprint_mismatch_or_missing_meta = "shared_ligand",
	peer_refuse_unavailable = "peer_refuse",
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
	local order = {
		"tag",
		"action",
		"mode",
		"kind",
		"fp",
		"detail",
		"alias",
		"refuse_cause",
		"der_sha256",
		"epoch",
		"worker",
		"server_name",
		"subsystem",
		"multi_entries",
		"stapled_entries",
		"null_slots",
	}
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

-- Exported for the HTTP stapling-off fast path (one parser for SSL_USE_OCSP_STAPLING).
function _M.stapling_enabled(internalstore, server_name)
	return stapling_enabled(internalstore, server_name)
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

-- Per-worker memo of pure PEM-derived facts (SPKI, DNs, Must-Staple bit, serial, key
-- kind). One handshake used to re-parse the same PEM ~20 times. Keyed by the exact
-- PEM bytes, so a rewrapped PEM is only a miss, never a wrong answer. Wiped when full.
-- Main-chunk locals are capped at 200 by LuaJIT, so memo state lives in this block
-- and the uncached computations in one table.
local pem_memo_fetch
local uncached = {}
do
	local PEM_MEMO_MAX = 512
	local MEMO_NIL = {}
	local pem_memo = {}
	local pem_memo_count = 0

	pem_memo_fetch = function(kind, pem, compute)
		if type(pem) ~= "string" or pem == "" then
			return compute(pem)
		end
		local entry = pem_memo[pem]
		if entry then
			local v = entry[kind]
			if v == MEMO_NIL then
				return nil
			end
			if v ~= nil then
				return v
			end
		else
			if pem_memo_count >= PEM_MEMO_MAX then
				pem_memo = {}
				pem_memo_count = 0
			end
			entry = {}
			pem_memo[pem] = entry
			pem_memo_count = pem_memo_count + 1
		end
		local v = compute(pem)
		if v == nil then
			entry[kind] = MEMO_NIL
		else
			entry[kind] = v
		end
		return v
	end
end

-- SHA256 of SubjectPublicKeyInfo DER, matching ocsp-refresh.py.
-- Never key anything by ngx.md5(cert_pem) as a stand-in for the SPKI: PEM rewrap
-- changes that hash while the SPKI is identical (path skew vs the job).
function uncached.spki_fingerprint(cert_pem)
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

local function spki_fingerprint(cert_pem)
	return pem_memo_fetch("spki", cert_pem, uncached.spki_fingerprint)
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
	return "/var/cache/bunkerweb/ssl/"
		.. fingerprint:sub(1, 1)
		.. "/"
		.. fingerprint:sub(2, 2)
		.. "/"
		.. fingerprint
		.. "/ocsp.der"
end

local function issuer_path(fingerprint)
	return "/var/cache/bunkerweb/ssl/"
		.. fingerprint:sub(1, 1)
		.. "/"
		.. fingerprint:sub(2, 2)
		.. "/"
		.. fingerprint
		.. "/issuer.pem"
end

local function cache_key(fingerprint)
	return "TLS:SSL:ocsp:" .. fingerprint
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
-- Transient allow-pin TTL when expires_unix is absent (align with L1).
local ALLOW_PIN_TTL_SECONDS = L1_MAX_TTL

-- Handshake refuse causes that DROP the allow pin (sibling Must-Staple fails until re-canary).
-- Never-write / keep-pin causes leave the canary allow in place (timing/colony/soft-recall).
-- Keys are raw refuse_cause strings BEFORE runbook alias collapse.
--
-- DROP = semantic poison about this body vs leaf / colony / canary (sibling must
--   fail closed until a new generation is canary-paged).
-- KEEP = this worker's view of pin state or its own clock. Must not erase a pin
--   every zone shares (stale reader / skewed clock → fleet Must-Staple outage).
--   Local handshake still refuses; only the shared pin survives.
local DROP_ALLOW_ON_REFUSE = {
	certid_mismatch = true,
	aia_uri_mismatch = true,
	aia_uri_unpinned = true,
	aia_uri_missing_on_leaf = true,
	aia_uri_leaf_unavailable = true,
	tombstoned = true,
	serial_blacklisted = true,
	cluster_floor = true,
	-- Bare "shared_ligand" is the runbook ALIAS — KEEP (see below). Only concrete
	-- binding failures DROP. ligand_missing stays KEEP (promote-tear ENOENT).
	ligand_mismatch = true,
	-- Raw ligand_verdict binding failures (HTTP/stream pass these without prefix).
	der_sha256_mismatch = true,
	missing_der_sha256 = true,
	invalid_der_sha256 = true,
	fingerprint_mismatch_or_missing_meta = true,
	canary_refused = true,
	-- intermediate_must_staple_libssl is KEEP (aligned with colony): a single
	-- OpenSSL 3.5 worker must not compare-and-delete the fleet allow-pin during
	-- mixed-version rollouts. Local handshake still refuses.
}
-- Keep allow pin (do not revoke) — sibling may still staple; local-only / temporary.
-- Invariant: every cause should_skip_peer_bus returns true for must also be KEEP
-- (or the skip arm never reaches record_peer_refuse). skip ⊆ KEEP.
local KEEP_ALLOW_ON_REFUSE = {
	not_paged = true,
	validate_budget = true,
	intermediate_must_staple_colony = true,
	intermediate_must_staple_libssl = true,
	set_staple_failed = true,
	set_staple_exception = true,
	response_not_found = true,
	response_stale = true,
	await_sni = true,
	probe_failed = true,
	allow_pin_missing = true,
	allow_pin_expired = true,
	allow_pin_mismatch = true,
	ligand_missing = true,
	-- Runbook alias collapse of ligand_* — callers must pass raw ligand_verdict;
	-- if they pass normalize_staple_decision output, KEEP (do not DROP on ENOENT).
	shared_ligand = true,
	peer_refuse_unavailable = true,
	fingerprint_chain_unavailable = true,
	multi_staple_attach_failed = true,
	-- Local chain-presentation defect. Do not DROP a pin the sibling may still staple.
	issuer_unresolved_must_staple = true,
	thisUpdate_future = true,
	thisUpdate_stale = true,
	lifetime_invalid = true,
	lifetime_too_long = true,
	thisUpdate_unreadable = true,
}

local function l1_shm_ttl(expires_unix)
	-- Never park an undated body in L1 (would outlive stripped meta).
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

-- Pack one L1 shm entry: epoch | verified sha256 binding | expires_unix | DER.
-- Single composite key so eviction cannot orphan verified from the body.
local function pack_l1(epoch, verified_binding, der, expires_unix)
	local exp = ""
	if type(expires_unix) == "number" and expires_unix > 0 then
		exp = tostring(math.floor(expires_unix))
	elseif type(expires_unix) == "string" and expires_unix:match("^%d+$") then
		exp = expires_unix
	end
	return L1_MAGIC .. (epoch or "0") .. "\0" .. (verified_binding or "") .. "\0" .. exp .. "\0" .. der
end

-- Unpack a bw2 L1 blob. Returns epoch, binding, der, expires_unix (or all nil).
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

-- Read .ocsp_epoch (job coherence bus). HTTP and stream L1 must match this string.
-- First non-space token on the first line — never require the whole file to be a
-- single token (extra lines / comments must not desync HTTP vs stream readers).
--
-- Why one parser: a prior HTTP-only reader used ^%s*(%S+)%s*$ over the whole file
-- and rejected multi-line epochs that stream accepted → HTTP L1 miss / stream hit
-- on the same body. Both call sites must use this function (or the export below).
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

-- Public: HTTP ssl-certificate-by-lua.conf delegates here so the handshake never
-- reimplements epoch tokenization. Returns "0" when the file is missing/unreadable.
function _M.current_ocsp_epoch()
	return current_ocsp_epoch()
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

-- True when L1's stored binding is still sha256(resp) — verified flag bound to these bytes.
local function entry_verified(stored_binding, resp)
	local binding = resp_binding(resp)
	return binding ~= nil and stored_binding == binding
end

-- Write DER into stream/HTTP L1 (bw2 composite).
-- packed_epoch: when re-parking a body that already passed l1_matches_disk, pass
-- the epoch from that get — never stamp "now's" epoch over an old body (that would
-- make a stale DER look current until the next ligand check). Matches HTTP
-- ocsp_l1_put(..., packed_epoch) in ssl-certificate-by-lua.conf.
-- mark_verified=false: cache DER for reuse but do not skip crypto on later hits.
local function warm_cache(internalstore, fingerprint, resp, mark_verified, expires_unix, packed_epoch)
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
	local epoch = packed_epoch
	if type(epoch) ~= "string" or #epoch == 0 then
		epoch = current_ocsp_epoch()
	end
	pcall(function()
		internalstore:set(cache_key(fingerprint), pack_l1(epoch, binding, resp, expires_unix), ttl)
		-- Also clear the zone-scoped key so a prior put without the zone flag cannot linger.
		internalstore:delete(cache_key(fingerprint), true)
	end)
end

local function drop_cache(internalstore, fingerprint)
	pcall(function()
		internalstore:delete(cache_key(fingerprint))
		internalstore:delete(cache_key(fingerprint), true)
	end)
end

-- True when this L1 body is still coherent with disk + .ocsp_epoch.
-- Implemented after ligand_effective_sha (shared with HTTP); see l1_body_matches_disk.
local l1_matches_disk

-- stored_pem: the shard issuer.pem the caller already read (false = known absent),
-- or nil to read it here.
local function issuer_candidates(blocks, leaf_pem, fingerprint, stored_pem)
	-- When the shard has issuer.pem, only accept that issuer SPKI (or an identical
	-- re-encoding from the chain). Do not let validate succeed against a different CA.
	local stored = nil
	if stored_pem ~= nil then
		stored = stored_pem or nil
	elseif fingerprint then
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

-- Handshake path: resty.openssl only — no /tmp + openssl CLI.
-- Returns true | false | nil (unknown). Unknown must stay fail-closed at call sites
-- that decide whether Must-Staple enforcement applies (never invent false on throw).
-- Callers also consult ocsp.json (written by ocsp-refresh) when resty cannot see
-- Must-Staple — see resolve_leaf_must_staple.
function uncached.has_must_staple(cert_pem)
	if type(cert_pem) ~= "string" or cert_pem == "" then
		return nil
	end
	local known = false
	local must = false
	local ok = pcall(function()
		local x509 = require("resty.openssl.x509")
		local cert_obj = x509.new(cert_pem)
		if not cert_obj then
			return
		end
		known = true
		local tls_feature_ext = cert_obj:get_extension("tlsfeature")
		if not tls_feature_ext then
			return
		end
		must = tls_feature_is_must_staple(tls_feature_ext:text() or "")
	end)
	if not ok or not known then
		return nil
	end
	return must
end

local function has_must_staple(cert_pem)
	return pem_memo_fetch("must", cert_pem, uncached.has_must_staple)
end

-- { subject_dn, issuer_dn } strings (either may be nil on parse failure).
function uncached.pem_names(pem)
	local names = {}
	pcall(function()
		local x509 = require("resty.openssl.x509")
		local c = x509.new(pem)
		if c and c.get_subject_name and c.get_issuer_name then
			names[1] = tostring(c:get_subject_name() or "")
			names[2] = tostring(c:get_issuer_name() or "")
		end
	end)
	return names
end

local function pem_names(pem)
	local names = pem_memo_fetch("names", pem, uncached.pem_names)
	if type(names) ~= "table" then
		return nil, nil
	end
	return names[1], names[2]
end

-- Trust anchor (subject == issuer): never a stapled CertificateEntry.
local function is_self_signed(pem)
	local s, iss = pem_names(pem)
	return s ~= nil and s ~= "" and s == iss
end

-- Job-written shard metadata ({fp[1]}/{fp[2]}/{fp}/ocsp.json), or nil when absent/invalid.
-- Must stay above resolve_leaf_must_staple / cert_must_staple_bool: a local
-- referenced before its definition compiles to a nil global in LuaJIT.
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

-- True only when the job recorded must_staple=true in ocsp.json (resty-invisible TLS Feature).
local function ocsp_json_must_staple(meta)
	return meta ~= nil and meta.must_staple == true
end

-- Tri-state leaf Must-Staple: TLS Feature, then ocsp.json, then unknown→nil.
-- Fail-closed gate: resolve_leaf_must_staple(...) ~= false.
local function resolve_leaf_must_staple(cert_pem, fingerprint)
	local tls = has_must_staple(cert_pem)
	if tls == true then
		return true
	end
	local meta = nil
	if type(fingerprint) == "string" and is_fp64(fingerprint) then
		meta = read_ocsp_json(fingerprint)
	elseif type(cert_pem) == "string" and cert_pem ~= "" then
		local fp = spki_fingerprint(cert_pem)
		if fp then
			meta = read_ocsp_json(fp)
		end
	end
	if ocsp_json_must_staple(meta) then
		return true
	end
	if tls == false then
		return false
	end
	if meta ~= nil then
		-- Job wrote meta without must_staple=true → not Must-Staple.
		return false
	end
	return nil
end

-- Boolean Must-Staple for a PEM block (leaf or intermediate).
-- fail_closed_unknown=true → treat resty miss + no ocsp.json as Must-Staple
-- (intermediate path / bag filtering). false → unknown returns false (rare).
local function cert_must_staple_bool(pem, fail_closed_unknown)
	local tls = has_must_staple(pem)
	if tls == true then
		return true
	end
	local fp = spki_fingerprint(pem)
	local meta = fp and read_ocsp_json(fp) or nil
	if ocsp_json_must_staple(meta) then
		return true
	end
	if tls == false or meta ~= nil then
		return false
	end
	return fail_closed_unknown == true
end

-- Colony floor: peers advance ocsp-floor/{fp} on publish/tombstone using CA-signed
-- this_update_unix only (not wall-clock published_unix — clocks drift across nodes).
-- Missing local this_update_unix is no opinion (do not treat as 0 vs a positive floor).
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

-- Parse ocsp-floor/{fp} JSON to CA-signed this_update_unix (colony rank), or nil.
local function parse_floor_rank(raw)
	if type(raw) ~= "string" or raw == "" then
		return nil
	end
	local trimmed = raw:match("^%s*(.-)%s*$") or raw
	if trimmed:sub(1, 1) ~= "{" then
		return nil
	end
	local ok, decoded = pcall(function()
		return require("cjson").decode(trimmed)
	end)
	if not ok or type(decoded) ~= "table" then
		return nil
	end
	return meta_unix_field(decoded, "this_update_unix")
end

-- True when colony floor this_update_unix is ahead of local ocsp.json — Must-Staple closed.
-- Missing local this_update_unix is no opinion (never invent 0 vs a positive floor).
local function cluster_floor_blocks(fingerprint, meta)
	if not is_fp64(fingerprint) then
		return false
	end
	local floor_rank = parse_floor_rank(read_file("/var/cache/bunkerweb/ssl/ocsp-floor/" .. fingerprint))
	if not floor_rank or floor_rank <= 0 then
		return false
	end
	local local_rank = meta_unix_field(meta, "this_update_unix")
	-- Missing local timing: no opinion — never invent 0 vs a positive floor.
	if not local_rank then
		return false
	end
	if local_rank >= floor_rank then
		return false
	end
	log(
		ngx.ERR,
		"OCSP cluster floor ahead of local this_update_unix; Must-Staple closed fp="
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

-- =============================================================================
-- Cross-zone ligand + allow-pin bus (HTTP ↔ stream; separate lua_shared_dict)
-- =============================================================================
-- Why disk (not shm): HTTP uses ngx.shared.internalstore; stream uses
-- internalstore_stream. They cannot read each other's L1. The job-published
-- files below are the stand-in for "the generation the sibling would accept."
--
-- Outside-shard ligand  /var/cache/bunkerweb/ssl/ocsp-ligand/{fp}
--   Compact JSON: der_sha256, soft_recall_gen, paged, expires_unix, fingerprint.
--   Lives BESIDE the SPKI directory (like ocsp-floor / ocsp-allow) so in-place
--   promote of issuer.pem + ocsp.der + ocsp.json cannot half-expose the binding.
--   Handshake Must-Staple / canary trust prefer this over in-shard ocsp.json.
--   Fat meta (AIA, CertID, tombstone details) stays in the shard.
--
-- Allow-pin            /var/cache/bunkerweb/ssl/ocsp-allow/{fp}
--   Polarity inverted from the old sticky refuse bus: MISSING pin refuses
--   Must-Staple. Only the scheduler canary (and per-run restamp) writes pins.
--   Handshake deletes only via compare-and-delete (revoke_allow_pin) when the
--   pin still holds the refused (der_sha256, soft_recall_gen). Soft fuse never
--   revokes. Pin-state / clock causes are KEEP_ALLOW (local view ≠ fleet wipe).
--
-- Legacy refuse        /var/cache/bunkerweb/ssl/ocsp-refuse/{fp}
--   Pre-invert sticky poison. Job cleans it; handshake does not mkdir or unlink
--   on the read path (except admin clear_peer_refuse).
--
-- Generation identity: der_sha256 + soft_recall_gen (bumped on soft-recall so
-- the same kept DER can be re-paged without a leftover pin re-matching).
-- Death clocks: pin / L1 / freshness all die at expires_unix − OCSP_CLOCK_SKEW.
-- =============================================================================

local function ocsp_ligand_path(fingerprint)
	return "/var/cache/bunkerweb/ssl/ocsp-ligand/" .. fingerprint
end

local function ocsp_allow_path(fingerprint)
	return "/var/cache/bunkerweb/ssl/ocsp-allow/" .. fingerprint
end

-- Legacy refuse path — job-side cleanup only after the allow-pin invert.
local function ocsp_refuse_path_legacy(fingerprint)
	return "/var/cache/bunkerweb/ssl/ocsp-refuse/" .. fingerprint
end

-- Integer soft_recall_gen from ligand or ocsp.json (0 if absent).
-- Job-minted counter: bumps on soft-recall so peer-refuse / allow identity
-- (der_sha256, soft_recall_gen) cannot re-match a leftover pin after re-page.
local function soft_recall_gen_of(meta)
	if type(meta) ~= "table" then
		return 0
	end
	local g = tonumber(meta.soft_recall_gen)
	if not g or g < 0 then
		return 0
	end
	return math.floor(g)
end

-- Load ocsp-ligand/{fp}. Prefer this over in-shard ocsp.json for der_sha256 binding.
-- Reject when ligand.fingerprint disagrees with the path fingerprint (a self-asserted
-- fingerprint inside the file must not bless a different SPKI directory).
local function read_ocsp_ligand(fingerprint)
	if not is_fp64(fingerprint) then
		return nil
	end
	local raw = read_file(ocsp_ligand_path(fingerprint))
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
	if type(obj.fingerprint) == "string" and obj.fingerprint:lower() ~= fingerprint then
		return nil
	end
	obj.der_sha256 = sha
	obj.soft_recall_gen = soft_recall_gen_of(obj)
	return obj
end

-- Merge already-read ligand with shard meta (caller reads ligand once per decision).
-- Rules (load-bearing — HTTP and stream must agree):
--   * ligand wins der_sha256 + soft_recall_gen
--   * tombstone from EITHER side forces tombstoned + paged=false
--   * paged=true only when shard meta exists AND both sides say paged
--     (missing shard meta never grants canary trust)
--   * expires_unix = min of positive values (generation authority pairs with
--     the tighter death clock, not a stale looser shard deadline)
--   * fingerprint is the path fp (never trust a self-assert alone)
local function merge_ligand(shard_meta, ligand, fingerprint)
	if not ligand then
		return shard_meta
	end
	local merged = {}
	if type(shard_meta) == "table" then
		for k, v in pairs(shard_meta) do
			merged[k] = v
		end
	end
	merged.der_sha256 = ligand.der_sha256
	merged.soft_recall_gen = ligand.soft_recall_gen
	local shard_tomb = type(shard_meta) == "table" and shard_meta.tombstoned == true
	local ligand_tomb = ligand.tombstoned == true
	if shard_tomb or ligand_tomb then
		merged.tombstoned = true
		merged.paged = false
	elseif type(shard_meta) ~= "table" then
		-- Missing shard meta cannot grant canary trust.
		merged.paged = false
	elseif shard_meta.paged ~= true then
		merged.paged = false
	elseif ligand.paged == true then
		merged.paged = true
	else
		merged.paged = false
	end
	local shard_exp = type(shard_meta) == "table" and tonumber(shard_meta.expires_unix) or nil
	local ligand_exp = tonumber(ligand.expires_unix)
	if shard_exp and shard_exp > 0 and ligand_exp and ligand_exp > 0 then
		merged.expires_unix = math.min(math.floor(shard_exp), math.floor(ligand_exp))
	elseif ligand_exp and ligand_exp > 0 then
		merged.expires_unix = math.floor(ligand_exp)
	elseif shard_exp and shard_exp > 0 then
		merged.expires_unix = math.floor(shard_exp)
	end
	if type(fingerprint) == "string" then
		merged.fingerprint = fingerprint
	elseif type(ligand.fingerprint) == "string" then
		merged.fingerprint = ligand.fingerprint
	end
	return merged
end

-- Effective generation meta: read ligand once then merge.
local function ligand_or_meta(meta, fingerprint)
	return merge_ligand(meta, read_ocsp_ligand(fingerprint), fingerprint)
end

-- Peer-refuse / allow generation: (der_sha256, soft_recall_gen).
-- When resp bytes are present, body SHA wins. Meta/ligand der_sha256 is only a
-- fallback for meta-only DROP causes (tombstone / serial / canary) — never for
-- probe paths that pass resp=nil after CertID/ligand refuses (that would
-- compare-and-delete the GOOD generation using meta alone).
local function generation_tuple(meta, resp)
	local body = resp_binding(resp)
	if not body and type(meta) == "table" and type(meta.der_sha256) == "string" then
		local sha = meta.der_sha256:lower()
		if #sha == 64 and sha:match("^[0-9a-f]+$") then
			body = sha
		end
	end
	if not body then
		return nil, nil
	end
	return body, soft_recall_gen_of(meta)
end

-- DROP causes that may revoke using meta.der_sha256 when resp is nil (meta names
-- the poisoned generation). Body-poison causes require resp bytes so a probe
-- refuse cannot CAS-delete the live pin via meta alone.
local META_ONLY_DROP_ALLOW = {
	tombstoned = true,
	serial_blacklisted = true,
	cluster_floor = true,
	canary_refused = true,
}

-- Handshake is read-only on the pin directory (except compare-and-delete revoke).
-- Do NOT unlink legacy refuse or gen-less pins here: that was a DoS lever on the
-- hot path and turned mixed-version rollouts into synchronized Must-Staple outages.
-- Missing soft_recall_gen → treat as 0 (one-release upgrade grace); job restamp
-- rewrites proper gen on the next run.
-- Decode allow-pin JSON bytes; nil unless der_sha256 is 64 lowercase-normalized hex.
local function decode_allow_pin(raw)
	if type(raw) ~= "string" or raw == "" then
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
	obj.soft_recall_gen = soft_recall_gen_of(obj)
	return obj
end

local function read_allow_pin(fingerprint)
	if not is_fp64(fingerprint) then
		return nil
	end
	return decode_allow_pin(read_file(ocsp_allow_path(fingerprint)))
end

-- True when the pin names exactly this generation (der_sha256, soft_recall_gen).
local function allow_pin_matches(pin, want_sha, want_g)
	return type(pin) == "table" and pin.der_sha256 == want_sha and (tonumber(pin.soft_recall_gen) or 0) == want_g
end

local function path_exists(path)
	local f = io.open(path, "rb")
	if f then
		f:close()
		return true
	end
	return false
end

-- Claim files match the job's stale-temp sweep (**/.ocsp_*.tmp, >5 min) so a
-- worker that dies mid-revoke cannot leave litter behind indefinitely.
local revoke_claim_seq = 0
local function allow_pin_claim_path(fingerprint)
	revoke_claim_seq = revoke_claim_seq + 1
	local pid = (ngx.worker and ngx.worker.pid and ngx.worker.pid()) or 0
	return "/var/cache/bunkerweb/ssl/ocsp-allow/.ocsp_revoke."
		.. fingerprint
		.. "."
		.. tostring(pid)
		.. "."
		.. tostring(revoke_claim_seq)
		.. ".tmp"
end

-- Put a claimed pin back at `path` without clobbering a newer one the job may have
-- published meanwhile. Hard link fails with EEXIST when path is occupied; without
-- lfs.link, rename only into an empty slot. Returns true when the pin was restored.
local function restore_claimed_pin(claim, path)
	local ok_lfs, lfs = pcall(require, "lfs")
	if ok_lfs and type(lfs) == "table" and lfs.link and lfs.link(claim, path) then
		os.remove(claim)
		return true
	end
	if not path_exists(path) and os.rename(claim, path) then
		return true
	end
	os.remove(claim)
	return false
end

-- Unconditional drop (job / admin / soft-recall cleanup that already knows the
-- generation is gone). Handshake refuse paths must use revoke_allow_pin instead.
-- Checks os.remove's nil,err return — pcall alone never sees EACCES.
local function drop_allow_pin(fingerprint)
	if not is_fp64(fingerprint) then
		return false, "invalid_fingerprint"
	end
	local path = ocsp_allow_path(fingerprint)
	local ok, err = os.remove(path)
	if not ok and err and not tostring(err):find("No such file", 1, true) then
		return false, tostring(err)
	end
	-- Legacy refuse cleanup is job-side; best-effort here for admin clear.
	os.remove(ocsp_refuse_path_legacy(fingerprint))
	return true
end

-- Compare-and-delete: unlink only when the pin still holds the refused generation.
-- Without this, a lagging worker holding gen N that sees allow_pin_mismatch
-- (or any DROP cause) would erase the gen N+1 pin the canary just wrote — the
-- consensus ADHD finding across five frames. Soft-recall unpaged cleanup also
-- uses this so "same DER, older gen" cannot wipe a re-canaried pin.
--
-- Atomicity: the job restamps pins via tmp+rename from another process, so a plain
-- read-then-unlink could delete a pin written between the two calls. Instead the
-- pin is renamed to a private claim file (atomic), re-verified there, and only then
-- unlinked; a claim that no longer matches is restored with restore_claimed_pin.
-- Readers may see the pin missing for the microseconds between claim and restore
-- (a local allow_pin_missing refuse, KEEP) — never a persistent fleet-wide loss.
-- Returns outcome: "allow_dropped" | "allow_kept_gen_moved" | "allow_absent"
--   | "allow_drop_eacces" | "allow_drop_failed"
local function revoke_allow_pin(fingerprint, want_sha, want_gen, refuse_cause, quiet)
	if not is_fp64(fingerprint) then
		return "allow_drop_failed"
	end
	if type(want_sha) ~= "string" or #want_sha ~= 64 then
		return "allow_drop_failed"
	end
	local want_g = tonumber(want_gen) or 0
	-- Read-only fast path: most mismatches never touch the directory.
	local pin = read_allow_pin(fingerprint)
	if not pin then
		return "allow_absent"
	end
	if not allow_pin_matches(pin, want_sha, want_g) then
		if not quiet then
			log(
				ngx.NOTICE,
				format_staple_decision("peer_refuse_bus", {
					tag = "OCSP_PEER_REFUSE_BUS",
					action = "allow_kept_gen_moved",
					refuse_cause = tostring(refuse_cause or ""),
					fp = fingerprint:sub(1, 16) .. "...",
					der_sha256 = want_sha:sub(1, 16) .. "...",
					detail = "pin_gen=" .. tostring(pin.soft_recall_gen) .. " want_gen=" .. tostring(want_g),
				})
			)
		end
		return "allow_kept_gen_moved"
	end
	local path = ocsp_allow_path(fingerprint)
	local claim = allow_pin_claim_path(fingerprint)
	local ok, err = os.rename(path, claim)
	if not ok then
		if err and not tostring(err):find("No such file", 1, true) then
			if not quiet then
				log(
					ngx.ERR,
					format_staple_decision("peer_refuse_bus", {
						tag = "OCSP_PEER_REFUSE_BUS",
						action = "allow_drop_eacces",
						refuse_cause = tostring(refuse_cause or ""),
						fp = fingerprint:sub(1, 16) .. "...",
						detail = tostring(err),
					})
				)
			end
			return "allow_drop_eacces"
		end
		return "allow_absent"
	end
	-- We now exclusively own what was at `path` at rename time. If the job restamped
	-- between the read above and the rename, this is the newer pin: put it back.
	if not allow_pin_matches(decode_allow_pin(read_file(claim)), want_sha, want_g) then
		local restored = restore_claimed_pin(claim, path)
		if not quiet then
			log(
				ngx.NOTICE,
				format_staple_decision("peer_refuse_bus", {
					tag = "OCSP_PEER_REFUSE_BUS",
					action = "allow_kept_gen_moved",
					refuse_cause = tostring(refuse_cause or ""),
					fp = fingerprint:sub(1, 16) .. "...",
					der_sha256 = want_sha:sub(1, 16) .. "...",
					detail = restored and "race_restored" or "race_newer_present",
				})
			)
		end
		return "allow_kept_gen_moved"
	end
	os.remove(claim)
	if not quiet then
		log(
			ngx.NOTICE,
			"OCSP allow-pin revoked fp="
				.. fingerprint:sub(1, 16)
				.. "... refuse_cause="
				.. tostring(refuse_cause or "")
				.. " der="
				.. want_sha:sub(1, 16)
				.. "... soft_recall_gen="
				.. tostring(want_g)
				.. " refused_by="
				.. tostring((ngx.config and ngx.config.subsystem) or "unknown")
		)
	end
	return "allow_dropped"
end

-- Job/canary only — never call from handshake refuse paths.
local function write_allow_pin(fingerprint, der_sha256, soft_recall_gen, expires_unix)
	if not is_fp64(fingerprint) or type(der_sha256) ~= "string" then
		return false, "invalid_inputs"
	end
	local sha = der_sha256:lower()
	if #sha ~= 64 or not sha:match("^[0-9a-f]+$") then
		return false, "invalid_der_sha256"
	end
	local gen = tonumber(soft_recall_gen) or 0
	if gen < 0 then
		gen = 0
	end
	gen = math.floor(gen)
	local path = ocsp_allow_path(fingerprint)
	local tmp = path
		.. ".tmp."
		.. tostring((ngx.worker and ngx.worker.pid and ngx.worker.pid()) or math.floor(ngx.now() * 1000))
	local payload_obj = {
		der_sha256 = sha,
		soft_recall_gen = gen,
		allowed_unix = ngx.time(),
		allowed_by = tostring((ngx.config and ngx.config.subsystem) or "job"),
	}
	if type(expires_unix) == "number" and expires_unix > 0 then
		payload_obj.expires_unix = math.floor(expires_unix)
	end
	local payload = require("cjson").encode(payload_obj)
	local f, open_err = io.open(tmp, "w")
	if not f then
		return false, "open_tmp:" .. tostring(open_err or "dir_missing")
	end
	local ok_w, write_err = f:write(payload)
	f:flush()
	f:close()
	if not ok_w then
		os.remove(tmp)
		return false, "write_tmp:" .. tostring(write_err or "nil")
	end
	local ok_r, rename_err = os.rename(tmp, path)
	if not ok_r then
		os.remove(tmp)
		return false, "rename:" .. tostring(rename_err or "nil")
	end
	-- Legacy refuse must not shadow allow polarity (job write path only).
	os.remove(ocsp_refuse_path_legacy(fingerprint))
	return true
end

local function ensure_ocsp_bus_dirs()
	local ok_all = true
	for _, dir in ipairs({
		"/var/cache/bunkerweb/ssl/ocsp-allow",
		"/var/cache/bunkerweb/ssl/ocsp-ligand",
		"/var/cache/bunkerweb/ssl/ocsp-refuse",
	}) do
		local ok = false
		pcall(function()
			local lfs = require("lfs")
			lfs.mkdir("/var/cache/bunkerweb/ssl")
			ok = lfs.mkdir(dir) or (lfs.attributes(dir, "mode") == "directory")
		end)
		if not ok then
			pcall(function()
				local lfs = require("lfs")
				ok = lfs.attributes(dir, "mode") == "directory"
			end)
		end
		if not ok then
			ok_all = false
		end
	end
	return ok_all
end

-- Back-compat export name used by warmer / jobs.
local function ensure_ocsp_refuse_dir()
	return ensure_ocsp_bus_dirs()
end

function _M.ensure_ocsp_refuse_dir()
	return ensure_ocsp_refuse_dir()
end

function _M.ensure_ocsp_bus_dirs()
	return ensure_ocsp_bus_dirs()
end

-- Pin dies at expires_unix - skew (same death clock as L1 / resp_still_fresh).
local function allow_pin_expired(pin)
	if type(pin) ~= "table" then
		return true
	end
	local exp = pin.expires_unix
	if type(exp) == "number" and exp > 0 then
		return ngx.time() >= (exp - OCSP_CLOCK_SKEW_SECONDS)
	end
	local t = pin.allowed_unix
	if type(t) ~= "number" then
		return true
	end
	return (ngx.time() - t) > ALLOW_PIN_TTL_SECONDS
end

-- Allow-pin gate (inverted refuse bus). Returns a staple_decision when the
-- caller must not staple; nil when the pin matches this generation (or the
-- optional staple path has no pin — caller still enforces ligand).
-- quiet=true: skip ERR log (L1 warmer).
--
-- Soft-recall / unpaged: revoke leftover allow for THIS (sha, gen) only — a
-- worker still holding soft-recalled meta must not erase a re-canaried pin
-- for the same DER at a newer soft_recall_gen — then return "not_paged".
-- Callers that only test this return value (and do not also call
-- shard_not_paged) still refuse. "not_paged" is KEEP_ALLOW, so a later
-- record_peer_refuse does not DROP again.
-- Expired pin: refuse locally (KEEP) but do not unlink (race with job restamp).
local function peer_refuse_blocks(fingerprint, meta, resp, quiet)
	meta = ligand_or_meta(meta, fingerprint)
	local sha, recall_gen = generation_tuple(meta, resp)
	if not sha then
		-- Must-Staple without a generation cannot prove allow — fail closed.
		if type(meta) == "table" and (meta.must_staple == true or meta.paged == true) then
			return "allow_pin_missing"
		end
		return nil
	end
	-- Soft-recall / unpaged: revoke leftover allow for THIS (sha, gen) only so
	-- a lagging worker cannot erase a re-canaried pin (same DER, newer gen).
	if type(meta) == "table" and (shard_not_paged(meta) or meta.unpaged_after_nongood == true) then
		revoke_allow_pin(fingerprint, sha, recall_gen, "not_paged", quiet)
		-- Non-nil so a caller that skips shard_not_paged cannot staple this generation.
		return "not_paged"
	end
	local pin = read_allow_pin(fingerprint)
	if not pin then
		if not quiet then
			log(
				ngx.ERR,
				"OCSP allow-pin missing fp="
					.. fingerprint:sub(1, 16)
					.. "... der="
					.. sha:sub(1, 16)
					.. "... soft_recall_gen="
					.. tostring(recall_gen)
			)
		end
		return "allow_pin_missing"
	end
	if pin.der_sha256 ~= sha or (tonumber(pin.soft_recall_gen) or 0) ~= recall_gen then
		if not quiet then
			log(
				ngx.ERR,
				"OCSP allow-pin mismatch fp="
					.. fingerprint:sub(1, 16)
					.. "... want_der="
					.. sha:sub(1, 16)
					.. "... soft_recall_gen="
					.. tostring(recall_gen)
			)
		end
		return "allow_pin_mismatch"
	end
	if allow_pin_expired(pin) then
		-- KEEP: expired pin is already inert; do not unlink (race with re-stamp).
		if not quiet then
			log(ngx.ERR, "OCSP allow-pin expired fp=" .. fingerprint:sub(1, 16) .. "...")
		end
		return "allow_pin_expired"
	end
	return nil
end

-- Handshake refuse: DROP allow pin for DROP_ALLOW causes via compare-and-delete.
-- refuse_cause is the raw pre-alias detail (logged); runbook staple_decision=
-- stays separate. Pin-state / clock causes are KEEP — this worker's view must
-- not revoke a pin HTTP, stream, and every sibling rely on.
local function record_peer_refuse(fingerprint, meta, resp, decision)
	local fp_short = (type(fingerprint) == "string" and #fingerprint >= 16) and (fingerprint:sub(1, 16) .. "...")
		or tostring(fingerprint)
	local by = (ngx.config and ngx.config.subsystem) or "unknown"
	local refuse_cause = tostring(decision or "unmet")
	-- Prefix variants (canary_*, legacy shared_ligand_*) drop like their buckets,
	-- but KEEP exact-match on the full string OR the stripped suffix wins so a
	-- leftover shared_ligand_ligand_missing cannot revoke (ligand_missing is KEEP).
	local drop = DROP_ALLOW_ON_REFUSE[refuse_cause] or (refuse_cause:sub(1, 7) == "canary_")
	local suffix = nil
	if refuse_cause:sub(1, 14) == "shared_ligand_" then
		drop = true
		suffix = refuse_cause:sub(15)
	end
	if KEEP_ALLOW_ON_REFUSE[refuse_cause] or (suffix and KEEP_ALLOW_ON_REFUSE[suffix]) then
		drop = false
	elseif suffix and DROP_ALLOW_ON_REFUSE[suffix] then
		drop = true
	end
	if not drop then
		log(
			ngx.DEBUG,
			"OCSP allow-pin keep on refuse_cause=" .. refuse_cause .. " fp=" .. fp_short .. " subsystem=" .. by
		)
		return false
	end
	if not fingerprint or not is_fp64(fingerprint) then
		log(
			ngx.ERR,
			format_staple_decision("peer_refuse_bus", {
				tag = "OCSP_PEER_REFUSE_BUS",
				action = "allow_drop_failed",
				detail = "missing_fingerprint",
				refuse_cause = refuse_cause,
				fp = fp_short,
				subsystem = by,
			})
		)
		return false
	end
	meta = ligand_or_meta(meta, fingerprint)
	-- Body-poison DROPs require the refused DER bytes. Probe paths pass resp=nil
	-- and would otherwise revoke via meta.der_sha256 (wrong generation CAS).
	if not META_ONLY_DROP_ALLOW[refuse_cause] and (type(resp) ~= "string" or #resp == 0) then
		log(
			ngx.DEBUG,
			"OCSP allow-pin keep (no resp body for compare-and-delete) refuse_cause="
				.. refuse_cause
				.. " fp="
				.. fp_short
		)
		return false
	end
	local sha, recall_gen = generation_tuple(meta, resp)
	if not sha then
		log(
			ngx.DEBUG,
			"OCSP allow-pin keep (no generation for compare-and-delete) refuse_cause="
				.. refuse_cause
				.. " fp="
				.. fp_short
		)
		return false
	end
	local outcome = revoke_allow_pin(fingerprint, sha, recall_gen, refuse_cause, false)
	return outcome == "allow_dropped"
end

-- Soft fuse: continue without touching the allow pin.
-- normal: revoke allow for DROP_ALLOW refuse_cause so sibling Must-Staple fails closed.
--
-- Transient causes must not enter the peer bus (HTTP↔stream). skip ⊆ KEEP_ALLOW:
-- every arm here is also KEEP so a future list drift that forgets KEEP still cannot
-- drop the shared pin via record_peer_refuse if skip somehow regresses.
local function should_skip_peer_bus(detail, meta, fingerprint)
	local d = tostring(detail or "unmet")
	local eff = meta
	if type(fingerprint) == "string" and is_fp64(fingerprint) then
		eff = ligand_or_meta(meta, fingerprint)
	end
	return d == "not_paged"
		or d == "validate_budget"
		or d == "intermediate_must_staple_colony"
		or d == "intermediate_must_staple_libssl"
		or d == "fingerprint_chain_unavailable"
		or d == "multi_staple_attach_failed"
		or d == "issuer_unresolved_must_staple"
		or d == "peer_refuse_unavailable"
		or (type(eff) == "table" and eff.paged ~= true)
		or ((d == "set_staple_failed" or d == "set_staple_exception") and type(eff) == "table" and eff.paged == true)
end

local function must_staple_refuse(fingerprint, meta, resp, detail, mode)
	if mode ~= "staple_only" and mode ~= "open" then
		local d = detail or "unmet"
		if not should_skip_peer_bus(d, meta, fingerprint) then
			record_peer_refuse(fingerprint, meta, resp, d)
		end
	end
	return false, "must_staple", detail or "unmet"
end

-- Keep old name for warmer compatibility.
local function ocsp_refuse_path(fingerprint)
	return ocsp_allow_path(fingerprint)
end

-- Minimal DER walk for OCSP CertID serials. lua-resty-openssl has no OCSP module, so
-- the former require("resty.openssl.ocsp") always failed and every CertID check
-- refused. Returns tag, content_start, content_end, next_pos (or nil if malformed).
local function der_read(der, pos, limit)
	if not pos or pos + 1 > limit then
		return nil
	end
	local tag = der:byte(pos)
	local len = der:byte(pos + 1)
	local cs = pos + 2
	if len >= 0x80 then
		local n = len - 0x80
		if n < 1 or n > 4 or cs + n - 1 > limit then
			return nil
		end
		len = 0
		for i = 0, n - 1 do
			len = len * 256 + der:byte(cs + i)
		end
		cs = cs + n
	end
	local ce = cs + len - 1
	if ce > limit then
		return nil
	end
	return tag, cs, ce, ce + 1
end

-- id-pkix-ocsp-basic (1.3.6.1.5.5.7.48.1.1) OID content bytes.
local OID_OCSP_BASIC = "\43\6\1\5\5\7\48\1\1"

-- Canonical uppercase hex serial of every SingleResponse CertID (RFC 6960 4.2.1),
-- in response order. nil when the DER is not a successful basic OCSP response.
local function ocsp_der_serials(der)
	if type(der) ~= "string" or #der < 2 then
		return nil
	end
	local n = #der
	local t, s, e, nx = der_read(der, 1, n)
	if t ~= 0x30 then
		return nil
	end
	local top_end = e
	-- responseStatus ENUMERATED must be successful (0).
	t, s, e, nx = der_read(der, s, top_end)
	if t ~= 0x0A or e ~= s or der:byte(s) ~= 0 then
		return nil
	end
	-- responseBytes [0] EXPLICIT ResponseBytes
	t, s, e = der_read(der, nx, top_end)
	if t ~= 0xA0 then
		return nil
	end
	t, s, e = der_read(der, s, e)
	if t ~= 0x30 then
		return nil
	end
	local rb_end = e
	t, s, e, nx = der_read(der, s, rb_end)
	if t ~= 0x06 or der:sub(s, e) ~= OID_OCSP_BASIC then
		return nil
	end
	-- response OCTET STRING → BasicOCSPResponse → tbsResponseData
	t, s, e = der_read(der, nx, rb_end)
	if t ~= 0x04 then
		return nil
	end
	t, s, e = der_read(der, s, e)
	if t ~= 0x30 then
		return nil
	end
	t, s, e = der_read(der, s, e)
	if t ~= 0x30 then
		return nil
	end
	local rd_end = e
	-- [0] version (optional), responderID [1]|[2], producedAt, responses
	t, s, e, nx = der_read(der, s, rd_end)
	if t == 0xA0 then
		t, s, e, nx = der_read(der, nx, rd_end)
	end
	if t ~= 0xA1 and t ~= 0xA2 then
		return nil
	end
	t, s, e, nx = der_read(der, nx, rd_end)
	if t ~= 0x18 then
		return nil
	end
	t, s, e = der_read(der, nx, rd_end)
	if t ~= 0x30 then
		return nil
	end
	local serials = {}
	local pos, list_end = s, e
	while pos <= list_end do
		local st, ss, se, snx = der_read(der, pos, list_end)
		if st ~= 0x30 then
			return nil
		end
		-- CertID: hashAlgorithm, issuerNameHash, issuerKeyHash, serialNumber
		local ct, cs, ce = der_read(der, ss, se)
		if ct ~= 0x30 then
			return nil
		end
		local at, _, _, anx = der_read(der, cs, ce)
		local nt, _, _, nnx = der_read(der, anx, ce)
		local kt, _, _, knx = der_read(der, nnx, ce)
		local it, is, ie = der_read(der, knx, ce)
		if at ~= 0x30 or nt ~= 0x04 or kt ~= 0x04 or it ~= 0x02 or ie < is then
			return nil
		end
		-- RFC 5280 serials are positive; a negative INTEGER is not a leaf we issued.
		if der:byte(is) >= 0x80 then
			return nil
		end
		local hex = to_hex(der:sub(is, ie)):upper():gsub("^0+", "")
		serials[#serials + 1] = hex == "" and "0" or hex
		pos = snx
	end
	if #serials == 0 then
		return nil
	end
	return serials
end

-- Serial of the SingleResponse naming want_hex when present, else the first one.
-- Callers compare the result with want_hex, so this is a "response covers it" test.
local function ocsp_resp_serial_hex(ocsp_der, want_hex)
	local serials = ocsp_der_serials(ocsp_der)
	if not serials then
		return nil
	end
	if want_hex then
		for _, serial in ipairs(serials) do
			if serial == want_hex then
				return serial
			end
		end
	end
	return serials[1]
end

function _M.ocsp_resp_serial_hex(ocsp_der, want_hex)
	return ocsp_resp_serial_hex(ocsp_der, want_hex)
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
	local got_hex = ocsp_resp_serial_hex(resp, banned_hex)
	if not got_hex then
		log(
			ngx.ERR,
			"OCSP serial blacklist present but response serial unreadable; refusing staple fp="
				.. fingerprint:sub(1, 16)
				.. "..."
		)
		return true
	end
	if got_hex == banned_hex then
		log(
			ngx.ERR,
			"OCSP serial blacklist refuse staple fp="
				.. fingerprint:sub(1, 16)
				.. "... serial_hex="
				.. banned_hex:sub(1, 16)
		)
		return true
	end
	return false
end

-- Canonical uppercase hex serial without leading zeros. Strings are always hex:
-- ocsp-refresh.py writes format(serial, "X"), and an all-digit hex serial such as
-- "1000" (0x1000) must not be reinterpreted as decimal.
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
		-- Doubles are exact only below 2^53; larger serials must arrive as hex strings.
		if serial < 0 or serial >= 2 ^ 53 or serial % 1 ~= 0 then
			return nil
		end
		local hex = string.format("%X", serial)
		hex = hex:gsub("^0+", "")
		return hex == "" and "0" or hex
	end
	if type(serial) ~= "string" then
		return nil
	end
	serial = serial:upper():gsub("[%s:]+", ""):gsub("^0X", "")
	if serial == "" or not serial:match("^[0-9A-F]+$") then
		return nil
	end
	serial = serial:gsub("^0+", "")
	return serial == "" and "0" or serial
end

function uncached.leaf_serial_hex(cert_pem)
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

local function leaf_serial_hex(cert_pem)
	return pem_memo_fetch("serial", cert_pem, uncached.leaf_serial_hex)
end

local function pem_dn_str(cert_pem, which)
	if type(cert_pem) ~= "string" or cert_pem == "" then
		return nil
	end
	local subject, issuer = pem_names(cert_pem)
	local out = subject
	if which == "issuer" then
		out = issuer
	end
	if type(out) == "string" and #out > 0 then
		return out
	end
	return nil
end

-- CertID must name this handshake leaf: serial match + issuer DN binds to a candidate
-- issuer PEM (subject == leaf.issuer). Fail closed when either side is unreadable.
-- Several PEMs can share one subject DN (cross-signs). Accept that DN only when
-- every match is the same SPKI; distinct keys return issuer_ambiguous (caller
-- maps this to certid_mismatch). This is not a full OCSP CertID issuerNameHash /
-- issuerKeyHash check — ocsp_der_serials reads the serial only, and the SPKI
-- tie-break stops the wrong cross-sign from passing on DN text alone.
-- ngx.ocsp.validate_ocsp_response also binds CertID; this gate covers verified-L1
-- paths that skip re-validate after a same-key renew left a stale body under the SPKI.
local function certid_matches_handshake_leaf(leaf_pem, ocsp_der, issuer_pems)
	if type(leaf_pem) ~= "string" or leaf_pem == "" or type(ocsp_der) ~= "string" or ocsp_der == "" then
		return false, "missing_leaf_or_resp"
	end
	local leaf_serial = leaf_serial_hex(leaf_pem)
	local resp_serial = ocsp_resp_serial_hex(ocsp_der, leaf_serial)
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
	local matches = {}
	for _, iss in ipairs(issuer_pems) do
		if type(iss) == "string" and iss ~= "" then
			local subj = pem_dn_str(iss, "subject")
			if subj and subj == leaf_issuer then
				matches[#matches + 1] = iss
			end
		end
	end
	if #matches == 0 then
		return false, "issuer_mismatch"
	end
	-- One DN hit, or several PEMs that are the same key: DN match is enough.
	-- Distinct SPKIs under one DN are different issuers; refuse rather than
	-- accept the first PEM in bag order.
	local seen_fp = nil
	for _, iss in ipairs(matches) do
		local fp = spki_fingerprint(iss)
		if not fp then
			return false, "issuer_spki_unreadable"
		end
		if seen_fp and seen_fp ~= fp then
			return false, "issuer_ambiguous"
		end
		seen_fp = fp
	end
	return true, nil
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
	local resp_serial = ocsp_resp_serial_hex(ocsp_der, meta_serial)
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
function uncached.leaf_aia_ocsp_uris(cert_pem)
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

-- Memoized list is shared: callers must treat it as read-only.
local function leaf_aia_ocsp_uris(cert_pem)
	return pem_memo_fetch("aia", cert_pem, uncached.leaf_aia_ocsp_uris)
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

-- Shared ligand verdict: one ligand read, hardened merge, body binding.
-- Single source of truth for HTTP (ssl-certificate-by-lua.conf) and stream
-- (this module). An inlined copy in the conf caused a zone-split after the
-- outside-ligand move — do not reintroduce it.
-- Returns ok, reason, meta_sha, body_sha, eff_meta.
-- Paged shards fail closed on ligand ENOENT (promote tear / missing publish).
-- Unpaged / soft-recall may still bind via in-shard der_sha256 (cutover).
local function ligand_verdict(shard_meta, fingerprint, resp)
	if not fingerprint or not is_fp64(fingerprint) then
		return false, "fingerprint_mismatch_or_missing_meta", nil, nil, shard_meta
	end
	local ligand = read_ocsp_ligand(fingerprint)
	local meta = merge_ligand(shard_meta, ligand, fingerprint)
	-- Canary-paged generations require the outside-shard ligand.
	if not ligand then
		local paged = type(shard_meta) == "table" and shard_meta.paged == true
		if paged then
			return false, "ligand_missing", nil, nil, meta
		end
	end
	if type(meta) ~= "table" or type(meta.fingerprint) ~= "string" or meta.fingerprint:lower() ~= fingerprint then
		return false, "fingerprint_mismatch_or_missing_meta", nil, nil, meta
	end
	if type(meta.der_sha256) ~= "string" then
		return false, "missing_der_sha256", nil, nil, meta
	end
	local meta_sha = meta.der_sha256:lower()
	if #meta_sha ~= 64 or not meta_sha:match("^[0-9a-f]+$") then
		return false, "invalid_der_sha256", nil, nil, meta
	end
	local body_sha = resp_binding(resp)
	if body_sha == nil or body_sha ~= meta_sha then
		return false, "der_sha256_mismatch", meta_sha, body_sha, meta
	end
	return true, nil, meta_sha, body_sha, meta
end

local function ocsp_json_ligand_matches(meta, fingerprint, resp)
	local ok, reason, meta_sha, body_sha = ligand_verdict(meta, fingerprint, resp)
	return ok, reason, meta_sha, body_sha
end

-- Job canary already verified this exact body (openssl CLI + ligands) and stamped
-- paged=true (ligand + allow-pin). Handshake may skip ngx.ocsp.validate_ocsp_response
-- for that body so CLI vs OpenResty FFI disagreement cannot unpage a live shard;
-- set_ocsp_status_resp and CertID/leaf checks still run.
local function canary_paged_body_ok(meta, fingerprint, resp)
	local ok, _, _, _, eff = ligand_verdict(meta, fingerprint, resp)
	if not ok or type(eff) ~= "table" then
		return false
	end
	if eff.paged ~= true or eff.tombstoned == true then
		return false
	end
	return true
end

function _M.canary_paged_body_ok(meta, fingerprint, resp)
	return canary_paged_body_ok(meta, fingerprint, resp)
end

-- Single shared evaluator for HTTP + stream (zone-split fix).
-- Returns ok, reason, meta_sha, body_sha, eff_meta.
-- Conf wrappers must fail closed if require fails — never reintroduce an
-- inlined in-shard-only ligand check beside this export.
function _M.ligand_verdict(shard_meta, fingerprint, resp)
	return ligand_verdict(shard_meta, fingerprint, resp)
end

function _M.ligand_matches(shard_meta, fingerprint, resp)
	return ocsp_json_ligand_matches(shard_meta, fingerprint, resp)
end

-- Effective ligand sha for L1 disk-match (HTTP conf / stream warmer).
-- Returns sha string or nil; tombstoned / missing ligand for a paged shard → nil
-- so L1 cannot keep a body the handshake would refuse.
function _M.ligand_effective_sha(shard_meta, fingerprint)
	local ligand = read_ocsp_ligand(fingerprint)
	local eff = merge_ligand(shard_meta, ligand, fingerprint)
	if type(eff) ~= "table" then
		return nil
	end
	if eff.tombstoned == true then
		return nil
	end
	if type(shard_meta) == "table" and shard_meta.paged == true and not ligand then
		return nil
	end
	if type(eff.der_sha256) == "string" and #eff.der_sha256 == 64 then
		return eff.der_sha256:lower()
	end
	return nil
end

-- Shared HTTP↔stream L1↔disk coherence. Fail-closed like ligand_verdict:
-- corrupt meta / paged+ligand ENOENT / require-path gaps drop L1. Publish-gap keep
-- (meta+DER both gone, epoch still matches) only while outside ligand is paged=true
-- AND ligand_effective_sha names the cached binding — never bare true / ligand-only
-- after a full shard retract. HTTP conf must call this export rather than inlining.
local function l1_body_matches_disk(fingerprint, resp, stored_epoch)
	local binding = resp_binding(resp)
	if not binding then
		return false
	end
	if not fingerprint or not is_fp64(fingerprint) then
		return false
	end
	if (stored_epoch or "") ~= current_ocsp_epoch() then
		return false
	end

	local disk_sha = nil
	local tombstoned = false
	local meta_missing = false
	local meta_corrupt = false
	local shard_meta = nil
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
			meta_missing = true
			return
		end
		local raw = f:read("*a")
		f:close()
		if type(raw) ~= "string" or #raw == 0 then
			meta_corrupt = true
			return
		end
		local ok_decode, decoded = pcall(require("cjson").decode, raw)
		if not ok_decode or type(decoded) ~= "table" then
			meta_corrupt = true
			return
		end
		shard_meta = decoded
		if decoded.tombstoned == true then
			tombstoned = true
			return
		end
		if type(decoded.der_sha256) == "string" then
			local sha = decoded.der_sha256:lower()
			if #sha == 64 and sha:match("^[0-9a-f]+$") then
				disk_sha = sha
			end
		end
	end)
	if tombstoned or meta_corrupt then
		return false
	end

	local eff = _M.ligand_effective_sha(shard_meta, fingerprint)
	if type(eff) == "string" and #eff == 64 then
		disk_sha = eff
	elseif type(shard_meta) == "table" and shard_meta.paged == true then
		return false
	elseif eff == nil and disk_sha == nil then
		return false
	end

	if disk_sha then
		return disk_sha == binding
	end
	-- Both shard files gone: do NOT keep L1 on ligand SHA alone (staggered job
	-- delete can leave outside ligand naming the old body). Require ligand present
	-- with paged=true (active canary generation mid-promote) plus SHA match.
	if meta_missing and not read_file(ocsp_path(fingerprint)) then
		local ligand = read_ocsp_ligand(fingerprint)
		if type(ligand) ~= "table" or ligand.paged ~= true then
			return false
		end
		local ligand_sha = _M.ligand_effective_sha(nil, fingerprint)
		return type(ligand_sha) == "string" and #ligand_sha == 64 and ligand_sha == binding
	end
	return false
end

l1_matches_disk = function(internalstore, fingerprint, resp, stored_epoch)
	return l1_body_matches_disk(fingerprint, resp, stored_epoch)
end

function _M.l1_body_matches_disk(fingerprint, resp, stored_epoch)
	return l1_body_matches_disk(fingerprint, resp, stored_epoch)
end

-- Fingerprint-hint path cannot call validate_ocsp_response (no leaf PEM).
-- Require meta.fingerprint match AND der_sha256 == sha256(body) so a swapped
-- ocsp.der under matching SPKI meta cannot be stapled.
-- Logs accept/refuse with truncated expected vs observed digests for audit.
local function ocsp_json_authorizes_resp(meta, fingerprint, resp)
	local fp_short = (type(fingerprint) == "string" and fingerprint:sub(1, 16)) or "?"
	local ok, reason, meta_sha, body_sha = ligand_verdict(meta, fingerprint, resp)
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
	log(ngx.INFO, "OCSP meta der_sha256 accept fp=" .. fp_short .. "... der_sha256=" .. meta_sha:sub(1, 16) .. "...")
	return true
end

-- Must-Staple may not rely on stream-private crypto-verified L1 alone.
-- Returns true, or false, raw ligand_verdict reason for OCSP_MUST_STAPLE_REFUSE.
-- Raw reason (not shared_ligand_*) so KEEP_ALLOW[ligand_missing] can hold the pin;
-- format_staple_decision still aliases to staple_decision=shared_ligand.
local function must_staple_binds_shared_ligand(meta, fingerprint, resp)
	local ok, reason = ocsp_json_ligand_matches(meta, fingerprint, resp)
	if ok then
		return true
	end
	return false, tostring(reason or "ligand_mismatch")
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
		log(
			ngx.ERR,
			"OCSP intrinsic timing refuse reason="
				.. tostring(why)
				.. " fp="
				.. tostring(fingerprint and fingerprint:sub(1, 16) or "?")
		)
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
	-- L1 may only tighten the meta death clock, never extend past stripped meta.
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

-- Forward declarations: assigned below with `name = function`, never `local function`
-- (a second local would shadow these and leave earlier callers holding nil).
local attach_ocsp_staple
local issuer_path_intermediate_ready
local clear_connection_staple
local maybe_rearm_l1_warmer

local function try_staple(
	ocsp,
	ssl,
	resp,
	leaf_pem,
	issuers,
	shard_issuer_spki,
	probe_only,
	meta,
	fingerprint,
	chain_blocks
)
	local ok_id, why = certid_matches_handshake_leaf(leaf_pem, resp, issuers)
	if not ok_id then
		log(ngx.ERR, "OCSP CertID refuse staple reason=" .. tostring(why))
		-- Must be certid_mismatch (DROP_ALLOW), not bare false → set_staple_failed/unmet KEEP.
		return false, "certid_mismatch"
	end
	local function set_resp()
		if probe_only then
			-- Leaf shard ok is not enough: demote if this leaf's issuer path cannot staple.
			local path_ok, path_detail = issuer_path_intermediate_ready(chain_blocks)
			if not path_ok then
				return false, path_detail or "unmet"
			end
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
		if
			detail == "intermediate_must_staple_libssl"
			or detail == "intermediate_must_staple_colony"
			or detail == "multi_staple_attach_failed"
		then
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
	-- ngx.now() is cached per event-loop tick and validate never yields, so the
	-- seconds fallback must refresh it or elapsed stays 0 and the budget never fires.
	local function budget_clock_s()
		if ngx.update_time then
			ngx.update_time()
		end
		return ngx.now()
	end
	local t0 = hrtime and hrtime() or budget_clock_s()
	for i = 1, n do
		local over_budget
		if hrtime then
			over_budget = (hrtime() - t0) > OCSP_VALIDATE_BUDGET_NS
		else
			over_budget = (budget_clock_s() - t0) > OCSP_VALIDATE_BUDGET_S
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

-- OpenSSL staple setters are macros over SSL_ctrl, not exported symbols, so they
-- must be called through SSL_ctrl (an ffi.C lookup of the macro name throws).
-- 143 exists from OpenSSL 3.6; earlier libssl returns 0 for an unknown ctrl.
local SSL_CTRL_SET_TLSEXT_STATUS_REQ_OCSP_RESP = 71
local SSL_CTRL_SET_TLSEXT_STATUS_REQ_OCSP_RESP_EX = 143

-- ffi + C with SSL_ctrl, the OpenSSL stack API and the OCSP_RESPONSE codec declared,
-- or nil. Reuses lua-resty-openssl's typedefs; each fallback declaration gets its own
-- pcall because a redeclare error aborts the rest of a multi-declaration cdef.
local _ssl_ffi = nil
local function ssl_ffi()
	if _ssl_ffi ~= nil then
		return _ssl_ffi or nil
	end
	local ok_ffi, ffi = pcall(require, "ffi")
	if not ok_ffi or not ffi then
		_ssl_ffi = false
		return nil
	end
	pcall(require, "resty.openssl.include.ssl")
	pcall(require, "resty.openssl.include.stack")
	for _, decl in ipairs({
		"long SSL_ctrl(void *ssl, int cmd, long larg, void *parg);",
		"const void *TLS_server_method(void);",
		"void *SSL_CTX_new(const void *meth);",
		"void SSL_CTX_free(void *ctx);",
		"void *SSL_new(void *ctx);",
		"void SSL_free(void *ssl);",
		"void *OPENSSL_sk_new_null(void);",
		"int OPENSSL_sk_push(void *st, const void *data);",
		"void OPENSSL_sk_pop_free(void *st, void (*func)(void *));",
		"void *d2i_OCSP_RESPONSE(void **a, const unsigned char **pp, long length);",
		"void OCSP_RESPONSE_free(void *r);",
	}) do
		pcall(ffi.cdef, decl)
	end
	local ok_sym = pcall(function()
		return ffi.C.SSL_ctrl
	end)
	if not ok_sym then
		_ssl_ffi = false
		return nil
	end
	_ssl_ffi = { ffi = ffi, C = ffi.C }
	return _ssl_ffi
end

-- True when this libssl accepts the TLS 1.3 multi-staple ctrl (143 → 1 on a scratch SSL).
-- A capability probe, not a version gate: distro backports and forks vary.
local function probe_multi_staple_ctrl()
	local st = ssl_ffi()
	if not st then
		return false
	end
	local ok, capable = pcall(function()
		local C = st.C
		local sctx = C.SSL_CTX_new(C.TLS_server_method())
		if sctx == nil then
			return false
		end
		local rc = 0
		local s = C.SSL_new(sctx)
		if s ~= nil then
			rc = tonumber(C.SSL_ctrl(s, SSL_CTRL_SET_TLSEXT_STATUS_REQ_OCSP_RESP_EX, 0, nil)) or 0
			C.SSL_free(s)
		end
		C.SSL_CTX_free(sctx)
		return rc == 1
	end)
	return ok and capable == true
end

-- TLS 1.3 multi-staple via SSL_ctrl(ssl, 143, 0, STACK_OF(OCSP_RESPONSE)).
-- Colony capability is the MIN across live workers (not last-writer on one file):
-- each worker writes .multi_staple_attach.d/<host-pid-wid>; aggregate .multi_staple_attach
-- is "1" only when every live marker is "1". Any leaf-only worker forces fleet leaf-only
-- until its marker expires. ocsp-refresh reads that min before intermediate AIA fetch.
local MULTI_STAPLE_ATTACH_PATH = "/var/cache/bunkerweb/ssl/.multi_staple_attach"
local MULTI_STAPLE_ATTACH_DIR = "/var/cache/bunkerweb/ssl/.multi_staple_attach.d"
local MULTI_STAPLE_WORKER_TTL = 120 -- seconds; warmer / probe refresh keeps live workers fresh
local MULTI_STAPLE_PUBLISH_INTERVAL = 15 -- rate-limit colony republish on hot paths
local _multi_staple_state = nil -- nil=unprobed, false=unavailable, table=ready
local _multi_staple_worker_id = nil
local _multi_staple_last_publish = 0

-- Colony vote filename. Hash the full hostname (do not truncate to 64 chars):
-- two pods that share a long name prefix must not publish into the same file
-- and overwrite each other's 0/1 vote. Tag is sha256(host)[1..16], else crc32.
local function multi_staple_worker_id()
	if _multi_staple_worker_id then
		return _multi_staple_worker_id
	end
	local host = tostring(os.getenv("HOSTNAME") or os.getenv("HOST") or "unknown")
	local host_tag = nil
	pcall(function()
		local digest_lib = require("resty.openssl.digest")
		local digest_ctx = digest_lib.new("sha256")
		digest_ctx:update(host)
		host_tag = to_hex(digest_ctx:final())
	end)
	if type(host_tag) ~= "string" or #host_tag < 16 then
		local crc = 0
		pcall(function()
			if ngx.crc32_long then
				crc = ngx.crc32_long(host) or 0
			end
		end)
		host_tag = string.format("%08x", crc)
	else
		host_tag = host_tag:sub(1, 16)
	end
	local pid = 0
	local wid = 0
	pcall(function()
		if ngx.worker and ngx.worker.pid then
			pid = tonumber(ngx.worker.pid()) or 0
		end
		if ngx.worker and ngx.worker.id then
			wid = tonumber(ngx.worker.id()) or 0
		end
	end)
	_multi_staple_worker_id = host_tag .. "-" .. tostring(pid) .. "-" .. tostring(wid)
	return _multi_staple_worker_id
end

-- Drop worker votes older than MULTI_STAPLE_WORKER_TTL. Publish-only: the
-- handshake read path must not unlink files (a reader racing a writer, or a
-- handshake that only wanted the min, must not delete a peer's vote).
local function prune_stale_multi_staple_votes(now)
	pcall(function()
		local lfs = require "lfs"
		if lfs.attributes(MULTI_STAPLE_ATTACH_DIR, "mode") ~= "directory" then
			return
		end
		now = now or ngx.now()
		for name in lfs.dir(MULTI_STAPLE_ATTACH_DIR) do
			if name ~= "." and name ~= ".." and not name:find("%.tmp%.", 1, false) then
				local path = MULTI_STAPLE_ATTACH_DIR .. "/" .. name
				local mtime = lfs.attributes(path, "modification")
				if type(mtime) == "number" and (now - mtime) > MULTI_STAPLE_WORKER_TTL then
					os.remove(path)
				end
			end
		end
	end)
end

-- Colony multi-staple capability = MIN across live worker votes under
-- .multi_staple_attach.d/. Any live "0" (e.g. OpenSSL 3.5) forces fleet leaf-only.
-- Returns false / true / nil (no live markers yet).
--
-- Read path does not os.remove. Stale files are ignored here and unlinked only
-- by publish_multi_staple_attach. In-progress "*.tmp.*" names are skipped:
-- publish writes a temp then rename(2)s it, so readers never need a lock.
-- A live file whose first byte is neither "0" nor "1" (torn or garbage) is
-- leaf-only (false), not "no opinion" (nil). nil would let openssl_multi_staple_ready
-- attach multi-staple while a peer's vote is unreadable.
local function colony_multi_staple_min()
	local found_zero = false
	local found_one = false
	local live = false
	pcall(function()
		local lfs = require "lfs"
		if lfs.attributes(MULTI_STAPLE_ATTACH_DIR, "mode") ~= "directory" then
			return
		end
		local now = ngx.now()
		for name in lfs.dir(MULTI_STAPLE_ATTACH_DIR) do
			if name ~= "." and name ~= ".." and not name:find("%.tmp%.", 1, false) then
				local path = MULTI_STAPLE_ATTACH_DIR .. "/" .. name
				local mtime = lfs.attributes(path, "modification")
				local stale = type(mtime) == "number" and (now - mtime) > MULTI_STAPLE_WORKER_TTL
				if not stale then
					local f = io.open(path, "r")
					if f then
						local raw = f:read("*l") or ""
						f:close()
						live = true
						if raw:sub(1, 1) == "0" then
							found_zero = true
						elseif raw:sub(1, 1) == "1" then
							found_one = true
						end
					end
				end
			end
		end
	end)
	if not live then
		return nil
	end
	if found_zero then
		return false
	end
	if found_one then
		return true
	end
	-- Live marker exists but is neither 0 nor 1.
	return false
end

-- Publish this worker's multi-staple vote and refresh the aggregate colony marker.
-- Aggregate is the live MIN (any "0" wins), not last-writer-wins.
local function publish_multi_staple_attach(ready, force)
	local now = ngx.now()
	if not force and (now - _multi_staple_last_publish) < MULTI_STAPLE_PUBLISH_INTERVAL then
		return
	end
	_multi_staple_last_publish = now
	prune_stale_multi_staple_votes(now)
	pcall(function()
		local lfs = require "lfs"
		lfs.mkdir("/var/cache/bunkerweb/ssl")
		lfs.mkdir(MULTI_STAPLE_ATTACH_DIR)
		local wid = multi_staple_worker_id()
		local worker_path = MULTI_STAPLE_ATTACH_DIR .. "/" .. wid
		local wtmp = worker_path .. ".tmp." .. tostring(ngx.worker.id() or 0)
		local wf = io.open(wtmp, "w")
		if not wf then
			return
		end
		wf:write(ready and "1\n" or "0\n")
		wf:close()
		os.rename(wtmp, worker_path)

		-- Colony min: any live "0" wins; else all-live-"1"; else this worker's vote.
		local colony = colony_multi_staple_min()
		local aggregate = ready
		if colony == false then
			aggregate = false
		elseif colony == true then
			aggregate = true
		end

		local tmp = MULTI_STAPLE_ATTACH_PATH .. ".tmp." .. tostring(ngx.worker.id() or 0)
		local f = io.open(tmp, "w")
		if not f then
			return
		end
		f:write(aggregate and "1\n" or "0\n")
		f:close()
		os.rename(tmp, MULTI_STAPLE_ATTACH_PATH)
	end)
end

-- True when this worker can multi-staple AND the colony MIN allows it.
-- Probes SSL_ctrl 143 once, publishes the vote, then still fails closed with
-- why_not="colony" while any live peer is leaf-only.
local function openssl_multi_staple_ready()
	-- Local capability probe (publishes this worker's vote). Colony min may still force
	-- leaf-only while any live peer cannot attach — even if this worker is 3.6+.
	local function finish_local(local_ok)
		if not local_ok then
			return false, nil, "libssl"
		end
		local colony = colony_multi_staple_min()
		-- false covers a live "0" and a live vote that is neither "0" nor "1".
		-- nil (no live markers yet) does not block this worker.
		if colony == false then
			return false, nil, "colony"
		end
		return true, _multi_staple_state, nil
	end
	if _multi_staple_state ~= nil then
		-- Refresh liveness so a departed leaf-only worker can expire from the colony min.
		publish_multi_staple_attach(_multi_staple_state ~= false, false)
		return finish_local(_multi_staple_state ~= false)
	end
	local st = ssl_ffi()
	if not st or not probe_multi_staple_ctrl() then
		_multi_staple_state = false
		publish_multi_staple_attach(false, true)
		return false, nil, "libssl"
	end
	_multi_staple_state = st
	publish_multi_staple_attach(true, true)
	return finish_local(true)
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
-- Unknown TLS Feature (resty throw) without ocsp.json fail-closes as true so leaf-only
-- attach cannot silently skip intermediate Must-Staple.
local function chain_has_intermediate_must_staple(chain_blocks)
	if type(chain_blocks) ~= "table" or #chain_blocks < 2 then
		return false
	end
	for i = 2, #chain_blocks do
		local pem = chain_blocks[i]
		if is_self_signed(pem) then
			break
		end
		local tls_ms = has_must_staple(pem)
		if tls_ms == true then
			return true
		end
		local fp = spki_fingerprint(pem)
		local meta = fp and read_ocsp_json(fp) or nil
		if ocsp_json_must_staple(meta) then
			return true
		end
		-- resty unknown and no job meta → fail closed (treat as intermediate Must-Staple).
		if tls_ms == nil and meta == nil then
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
		if is_self_signed(pem) then
			break
		end
		local inter_must = cert_must_staple_bool(pem, true)
		local der, fp = load_paged_intermediate_staple(pem, leaf_pem)
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

-- Attach leaf OCSP; when the colony can multi-staple (every live worker's libssl
-- accepts SSL_ctrl 143) also attach intermediate responses in chain order.
-- Colony leaf-only (any live pre-3.6 peer) or local probe failed: leaf-only.
-- Intermediate Must-Staple then refuses — never log leaf success while a TLS 1.3
-- client would still abort on the missing CertificateEntry status.
--
-- Multi-staple stack build / SSL_set0 / missing SSL pointer after the colony was
-- ready: if the chain has intermediate Must-Staple, refuse (multi_staple_attach_failed
-- or intermediate_must_staple_*), clearing the connection staple when possible.
-- Leaf-only fallback is only legal when no intermediate carries Must-Staple.
attach_ocsp_staple = function(ocsp, leaf_resp, chain_blocks)
	-- issuer_linked_chain_blocks omitted Must-Staple bag PEMs it could not link.
	-- The presented chain no longer shows them; refuse instead of leaf-only success.
	if type(chain_blocks) == "table" and (tonumber(chain_blocks.unresolved_must_staple) or 0) > 0 then
		clear_multi_staple_attach_note()
		log(
			ngx.ERR,
			"OCSP attach refused: issuer path omitted Must-Staple intermediate(s) count="
				.. tostring(chain_blocks.unresolved_must_staple)
		)
		return nil, "issuer_unresolved_must_staple"
	end
	local ready, st, why_not = openssl_multi_staple_ready()
	if not ready then
		clear_multi_staple_attach_note()
		if chain_has_intermediate_must_staple(chain_blocks) then
			if why_not == "colony" then
				return nil, "intermediate_must_staple_colony"
			end
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

	-- After leaf staple is set, multi-staple failure must not return leaf_ok when
	-- intermediate Must-Staple is present (header contract / TLS 1.3 clients).
	local function refuse_or_leaf_only(why_detail)
		clear_multi_staple_attach_note()
		pcall(clear_connection_staple)
		if chain_has_intermediate_must_staple(chain_blocks) then
			log(
				ngx.ERR,
				"OCSP multi-staple failed with intermediate Must-Staple; refusing leaf-only detail="
					.. tostring(why_detail or "multi_staple_attach_failed")
			)
			return nil, why_detail or "multi_staple_attach_failed"
		end
		log(ngx.ERR, "OCSP multi-staple failed; keeping leaf-only staple (no intermediate Must-Staple)")
		return ocsp.set_ocsp_status_resp(leaf_resp)
	end

	local ssl_mod = require "ngx.ssl"
	if not ssl_mod.get_req_ssl_pointer then
		return refuse_or_leaf_only("multi_staple_attach_failed")
	end
	local ssl_ptr = ssl_mod.get_req_ssl_pointer()
	if not ssl_ptr then
		-- Colony said multi-ready but this request has no SSL pointer — same gate
		-- as the leaf-only path (do not bypass intermediate Must-Staple).
		return refuse_or_leaf_only("multi_staple_attach_failed")
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
		return refuse_or_leaf_only("multi_staple_attach_failed")
	end
	local free_resp = ffi.cast("void (*)(void *)", C.OCSP_RESPONSE_free)
	local push_ok = true
	for _, der in ipairs(ders) do
		if der == false or der == nil then
			if C.OPENSSL_sk_push(stack, nil) == 0 then
				push_ok = false
				break
			end
		else
			local buf = ffi.new("unsigned char[?]", #der)
			ffi.copy(buf, der, #der)
			local pp = ffi.new("const unsigned char *[1]")
			pp[0] = buf
			local resp_obj = C.d2i_OCSP_RESPONSE(nil, pp, #der)
			if resp_obj == nil then
				push_ok = false
				break
			end
			if C.OPENSSL_sk_push(stack, resp_obj) == 0 then
				C.OCSP_RESPONSE_free(resp_obj)
				push_ok = false
				break
			end
		end
	end
	if not push_ok then
		C.OPENSSL_sk_pop_free(stack, free_resp)
		return refuse_or_leaf_only("multi_staple_attach_failed")
	end

	-- The status callback that makes OpenSSL emit stored staples is already on the
	-- ctx: ocsp.set_ocsp_status_resp above installs lua-nginx's, and it only skips
	-- that when the client sent no status_request (nothing would be sent anyway).
	-- Ownership of stack + responses transfers to SSL on success.
	local rc = C.SSL_ctrl(ssl_ptr, SSL_CTRL_SET_TLSEXT_STATUS_REQ_OCSP_RESP_EX, 0, stack)
	if tonumber(rc) ~= 1 then
		C.OPENSSL_sk_pop_free(stack, free_resp)
		return refuse_or_leaf_only("multi_staple_attach_failed")
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

-- Drop staples stored on this connection's SSL object.
-- Leaf: SSL_ctrl 71 with NULL. Multi (only when this worker's probe proved ctrl 143):
-- SSL_ctrl 143 with NULL, so a previous CertificateEntry stack cannot survive
-- clear_certs / context swap onto another leaf.
-- SSL_certs_clear does not clear either staple slot.
-- Assigns the forward-declared local so attach_ocsp_staple's refuse_or_leaf_only sees it.
clear_connection_staple = function()
	local prev = ngx.ctx and ngx.ctx.bw_ocsp_stapled_fp or nil
	if ngx.ctx then
		ngx.ctx.bw_ocsp_stapled_fp = nil
		ngx.ctx.bw_ocsp_multi_entries = nil
		ngx.ctx.bw_ocsp_multi_stapled = nil
		ngx.ctx.bw_ocsp_multi_null_slots = nil
	end
	local ok_clear = false
	pcall(function()
		local ssl_mod = require "ngx.ssl"
		if not ssl_mod.get_req_ssl_pointer then
			return
		end
		local ptr = ssl_mod.get_req_ssl_pointer()
		if not ptr then
			return
		end
		local st = ssl_ffi()
		if not st then
			return
		end
		ok_clear = tonumber(st.C.SSL_ctrl(ptr, SSL_CTRL_SET_TLSEXT_STATUS_REQ_OCSP_RESP, 0, nil)) == 1
		if type(_multi_staple_state) == "table" then
			pcall(st.C.SSL_ctrl, ptr, SSL_CTRL_SET_TLSEXT_STATUS_REQ_OCSP_RESP_EX, 0, nil)
		end
	end)
	if prev and ok_clear then
		log(
			ngx.DEBUG,
			"OCSP dropped connection staple on SSL context swap prev_fp=" .. tostring(prev):sub(1, 16) .. "..."
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
function uncached.cert_pubkey_kind(cert_pem)
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

local function cert_pubkey_kind(cert_pem)
	return pem_memo_fetch("kind", cert_pem, uncached.cert_pubkey_kind)
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
-- The returned table is memoized and shared: callers must treat it as read-only.
function uncached.cert_sig_profile(cert_pem)
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

local function cert_sig_profile(cert_pem)
	return pem_memo_fetch("sigprof", cert_pem, uncached.cert_sig_profile)
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
			local offered_ecdsa = false
			while i + 1 <= end_i do
				local scheme = sigalgs_ext:byte(i) * 256 + sigalgs_ext:byte(i + 1)
				if scheme == 0x0403 or scheme == 0x0503 or scheme == 0x0603 then
					offered_ecdsa = true
				end
				for li = 1, #leaves do
					if leaf_matches_scheme(profiles[li], scheme) then
						matched = true
						add(li)
					end
				end
				i = i + 2
			end
			-- TLS 1.2 ECDSA schemes name only the hash, not the curve, so an EC leaf on
			-- another curve is still usable there. Rank it after every exact match so a
			-- TLS 1.3 client (curve-bound schemes) still gets an exact leaf first.
			if offered_ecdsa then
				for li = 1, #leaves do
					if profiles[li].kind == "ec" and not seen[li] then
						matched = true
						add(li)
					end
				end
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

-- First of ordered_leaves_for_handshake (single-pick helper).
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
	return spki_fingerprint(cert_pem)
end

-- Subject / issuer DN strings for issuer-path linking (nil on parse failure).
local function cert_subject_issuer_dns(pem)
	return pem_names(pem)
end

-- Several bag PEMs can share one subject DN (cross-signs). Do not take cands[1]
-- (bag order). Prefer the unique SPKI; if keys differ, prefer the single
-- candidate that already has a canary-paged staple we can attach. Still
-- ambiguous → nil so the caller stops the walk instead of stapling the wrong path.
local function pick_issuer_candidate(cands, leaf_pem)
	if type(cands) ~= "table" or #cands == 0 then
		return nil
	end
	if #cands == 1 then
		return cands[1]
	end
	local seen_fp = nil
	local unique = true
	for _, cand in ipairs(cands) do
		local fp = cand and spki_fingerprint(cand.pem) or nil
		if not fp then
			unique = false
			break
		end
		if seen_fp and seen_fp ~= fp then
			unique = false
			break
		end
		seen_fp = fp
	end
	if unique and seen_fp then
		return cands[1]
	end
	local staplable = {}
	for _, cand in ipairs(cands) do
		local der = load_paged_intermediate_staple(cand.pem, leaf_pem)
		if der then
			staplable[#staplable + 1] = cand
		end
	end
	if #staplable == 1 then
		return staplable[1]
	end
	return nil
end

-- Ordered Certificate message for one leaf: leaf + issuer-linked intermediates only.
-- Drops off-path bag members (cross-signs, unused extras) so their Must-Staple cannot
-- fail-close a healthy leaf→issuer path (including after ClientHello sibling fallback).
-- If the leaf's issuer cannot be resolved in the bag, never restore the full bag —
-- that reintroduces "steer onto sibling, die on extra Must-Staple PEM". Instead keep
-- only non-Must-Staple intermediates as chain hints.
--
-- When that unresolved bag still held Must-Staple PEMs, those PEMs are omitted from
-- the presented chain (the client does not receive them) AND blocks.unresolved_must_staple
-- is set so issuer_path / attach refuse leaf-only. Presentation and the staple
-- decision stay the same: we do not serve a chain that hid a Must-Staple issuer.
local function issuer_linked_chain_blocks(leaf_pem, intermediate_pems)
	if type(leaf_pem) ~= "string" or leaf_pem == "" then
		return {}
	end
	local blocks = { leaf_pem }
	if type(intermediate_pems) ~= "table" or #intermediate_pems == 0 then
		return blocks, true
	end
	local by_subject = {}
	for _, pem in ipairs(intermediate_pems) do
		if type(pem) == "string" and pem ~= "" then
			local subj, iss = cert_subject_issuer_dns(pem)
			if subj and subj ~= "" then
				local list = by_subject[subj]
				if not list then
					list = {}
					by_subject[subj] = list
				end
				list[#list + 1] = { pem = pem, issuer = iss }
			end
		end
	end
	local _, current_issuer = cert_subject_issuer_dns(leaf_pem)
	local seen = {}
	local linked = 0
	local ambiguous = false
	for _ = 1, 8 do
		if not current_issuer or current_issuer == "" then
			break
		end
		local cands = by_subject[current_issuer]
		if not cands or #cands == 0 then
			break
		end
		local pick = pick_issuer_candidate(cands, leaf_pem)
		if not pick then
			-- Distinct SPKIs and no single paged staple to prefer. Stop; do not
			-- guess cands[1]. Caller treats this like an unresolved issuer.
			ambiguous = true
			log(
				ngx.ERR,
				"OCSP issuer DN matched "
					.. tostring(#cands)
					.. " PEMs with different SPKIs; refusing to pick by bag order"
			)
			break
		end
		local pick_subj, pick_iss = cert_subject_issuer_dns(pick.pem)
		-- Trust anchor: stop; do not present the root as a stapled CertificateEntry.
		if pick_subj and pick_iss and pick_subj == pick_iss then
			break
		end
		local fp = spki_fingerprint(pick.pem)
		if fp and seen[fp] then
			break
		end
		if fp then
			seen[fp] = true
		end
		blocks[#blocks + 1] = pick.pem
		linked = linked + 1
		current_issuer = pick.issuer or pick_iss
	end
	if linked == 0 or ambiguous then
		-- Unresolved or ambiguous issuer DN: never full-bag concat. Must-Staple
		-- extras in the bag would fail-close after dual-cert health steers onto
		-- this sibling, so they are omitted from the Certificate message.
		-- The client only sees `blocks`. If we omitted Must-Staple PEMs, set
		-- unresolved_must_staple so attach / issuer_path refuse leaf-only
		-- (issuer_unresolved_must_staple) instead of treating the short chain
		-- as "no intermediate Must-Staple".
		local dropped_must = 0
		if linked == 0 then
			for _, pem in ipairs(intermediate_pems) do
				if type(pem) == "string" and pem ~= "" then
					-- Skip self-signed trust anchors first (not CertificateEntry staple targets).
					local subj, iss = cert_subject_issuer_dns(pem)
					if subj and iss and subj == iss then
						-- Root certificates are never presented in TLS Certificate messages,
						-- so they cannot be stapled regardless of Must-Staple. Skip them.
						goto next_pem
					end
					local must = cert_must_staple_bool(pem, true)
					if must then
						dropped_must = dropped_must + 1
					else
						blocks[#blocks + 1] = pem
					end
					::next_pem::
				end
			end
		else
			-- Partial link then an ambiguous hop: count Must-Staple PEMs that
			-- were not already placed on the chain. Skip self-signed roots since
			-- they are never presented in TLS Certificate messages.
			local placed = {}
			for i = 2, #blocks do
				placed[blocks[i]] = true
			end
			for _, pem in ipairs(intermediate_pems) do
				if type(pem) == "string" and pem ~= "" and not placed[pem] then
					-- Root certificates (subj == issuer) are never CertificateEntry
					-- staple targets and should not count as unresolved Must-Staple.
					local subj, iss = cert_subject_issuer_dns(pem)
					if subj and iss and subj == iss then
						-- Skip self-signed root
						goto next_unplaced
					end
					if cert_must_staple_bool(pem, true) then
						dropped_must = dropped_must + 1
					end
					::next_unplaced::
				end
			end
		end
		if dropped_must > 0 then
			blocks.unresolved_must_staple = dropped_must
			log(
				ngx.ERR,
				"OCSP unresolved issuer path: omitted "
					.. tostring(dropped_must)
					.. " Must-Staple bag PEM(s); presented_entries="
					.. tostring(#blocks)
					.. " ambiguous="
					.. tostring(ambiguous)
					.. " — attach refuses leaf-only (issuer_unresolved_must_staple)"
			)
		end
		return blocks, false
	end
	local dropped = #intermediate_pems - linked
	if dropped > 0 then
		log(
			ngx.DEBUG,
			"OCSP issuer-linked chain dropped "
				.. tostring(dropped)
				.. " off-path bag PEM(s); presented_entries="
				.. tostring(#blocks)
		)
	end
	return blocks, true
end

-- Concatenate issuer_linked_chain_blocks into one PEM string for set_cert.
-- Named fields (unresolved_must_staple) are NOT preserved — callers that need
-- the refuse flag must use issuer_linked_chain_blocks / presentable_chain_blocks
-- and pass the table into health/attach, not this PEM.
local function issuer_linked_chain_pem(leaf_pem, intermediate_pems)
	local blocks = issuer_linked_chain_blocks(leaf_pem, intermediate_pems)
	if type(blocks) ~= "table" or #blocks == 0 then
		return ""
	end
	return table.concat(blocks, "\n")
end

-- Narrow a PEM bag or block list to the leaf's issuer-linked presentation
-- (same rules as issuer_linked_chain_blocks; used by health + attach paths).
--
-- Accepts a PEM string or a blocks table. If the input table already carries
-- unresolved_must_staple (from a prior issuer_linked_chain_blocks call), that
-- count is preserved across re-link: table.concat → re-parse would otherwise
-- drop the named field and the omitted Must-Staple PEMs, making health/attach
-- treat an abbreviated chain as "no intermediate Must-Staple".
local function presentable_chain_blocks(cert_pem_or_blocks)
	local prior_unresolved = nil
	local blocks = cert_pem_or_blocks
	if type(blocks) == "table" then
		prior_unresolved = tonumber(blocks.unresolved_must_staple)
	elseif type(blocks) == "string" then
		blocks = pem_blocks(blocks)
	end
	if type(blocks) ~= "table" or #blocks <= 1 then
		return blocks
	end
	local leaf = blocks[1]
	local inters = {}
	for i = 2, #blocks do
		inters[#inters + 1] = blocks[i]
	end
	local out = issuer_linked_chain_blocks(leaf, inters)
	if prior_unresolved and prior_unresolved > 0 then
		local cur = tonumber(out.unresolved_must_staple) or 0
		if prior_unresolved > cur then
			out.unresolved_must_staple = prior_unresolved
		end
	end
	return out
end

-- PEM for set_cert from issuer-linked blocks (array part only; named fields ignored).
local function chain_pem_from_blocks(blocks)
	if type(blocks) ~= "table" or #blocks == 0 then
		return ""
	end
	return table.concat(blocks, "\n")
end

function _M.issuer_linked_chain_pem(leaf_pem, intermediate_pems)
	return issuer_linked_chain_pem(leaf_pem, intermediate_pems)
end

function _M.issuer_linked_chain_blocks(leaf_pem, intermediate_pems)
	return issuer_linked_chain_blocks(leaf_pem, intermediate_pems)
end

-- Dual-cert / probe health: can this leaf's issuer-linked intermediates be stapled?
-- Does not require a leaf OCSP body. Legal NULL slots (no intermediate Must-Staple) pass.
-- Sticky defects demote the leaf: intermediate Must-Staple capability gap / missing body.
-- (libssl missing symbol, or colony leaf-only while a 3.5 peer is live.)
issuer_path_intermediate_ready = function(chain_pem_or_blocks)
	local blocks = presentable_chain_blocks(chain_pem_or_blocks)
	-- Check before the short-chain success return: omitted Must-Staple PEMs leave
	-- a leaf-only list (#blocks < 2) that would otherwise look healthy.
	if type(blocks) == "table" and (tonumber(blocks.unresolved_must_staple) or 0) > 0 then
		return false, "issuer_unresolved_must_staple"
	end
	if type(blocks) ~= "table" or #blocks < 2 then
		return true
	end
	local ready, _, why_not = openssl_multi_staple_ready()
	if not ready then
		if chain_has_intermediate_must_staple(blocks) then
			if why_not == "colony" then
				return false, "intermediate_must_staple_colony"
			end
			return false, "intermediate_must_staple_libssl"
		end
		return true
	end
	local leaf_pem = blocks[1]
	for i = 2, #blocks do
		local pem = blocks[i]
		if is_self_signed(pem) then
			break
		end
		local inter_must = cert_must_staple_bool(pem, true)
		local der = load_paged_intermediate_staple(pem, leaf_pem)
		if not der and inter_must then
			return false, "response_not_found"
		end
	end
	return true
end

function _M.issuer_path_intermediate_ready(chain_pem_or_blocks)
	return issuer_path_intermediate_ready(chain_pem_or_blocks)
end

-- How many issuer-path intermediates would attach as NULL (ok_partial slots).
-- Used to rank leaf-GOOD siblings: fewer nulls = more complete multi-staple.
-- Leaf-only chains and leaf-only colony/libssl score 0 (vacuously complete for ranking).
-- Does not demote — ok_partial remains legal when it is the only healthy option.
local function issuer_path_null_slots(chain_pem_or_blocks)
	local blocks = presentable_chain_blocks(chain_pem_or_blocks)
	if type(blocks) ~= "table" or #blocks < 2 then
		return 0
	end
	local ready = openssl_multi_staple_ready()
	if not ready then
		return 0
	end
	local leaf_pem = blocks[1]
	local nulls = 0
	for i = 2, #blocks do
		local pem = blocks[i]
		if is_self_signed(pem) then
			break
		end
		local der = load_paged_intermediate_staple(pem, leaf_pem)
		if not der then
			nulls = nulls + 1
		end
	end
	return nulls
end

function _M.issuer_path_null_slots(chain_pem_or_blocks)
	return issuer_path_null_slots(chain_pem_or_blocks)
end

-- Install the single leaf this handshake will present (dual-cert: one of RSA/ECDSA).
-- prefer_kind / ClientHello signature_algorithms select which leaf; only that leaf is
-- set_cert'd so the OCSP staple cannot land on a different CertificateEntry.
-- Returns: true, chain_blocks_or_pem, leaf_fp  OR  false, err_msg [, detail]
-- On success the second value is the issuer-linked blocks table (array of PEMs plus
-- optional unresolved_must_staple). Callers may pass it to staple/probe/attach;
-- table.concat is only for set_cert. Named fields survive — PEM round-trip does not.
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
		-- Issuer-linked blocks keep unresolved_must_staple; PEM concat alone would drop it.
		local blocks = issuer_linked_chain_blocks(leaf.pem, intermediates)
		local chain_pem = chain_pem_from_blocks(blocks)
		local leaf_must = false
		if probe_must then
			leaf_must = resolve_leaf_must_staple(leaf.pem, leaf.fp) == true
			if leaf_must and mode == "open" then
				leaf_must = false
			end
		end
		-- Bind staple health to this leaf's issuer-linked intermediates (not leaf shard alone).
		-- Soft-fuse install (probe_must=false) skips demotion so the preferred leaf can load unstapled.
		-- Skip-leaf demotion must NOT write the peer-refuse bus: a sibling may still install.
		if probe_must and mode ~= "open" then
			local path_ok, path_detail = issuer_path_intermediate_ready(blocks)
			if not path_ok then
				local detail = path_detail or "unmet"
				log(
					ngx.ERR,
					format_staple_decision(detail, {
						tag = "OCSP_MUST_STAPLE_REFUSE",
						action = "skip_leaf",
						mode = mode,
						detail = "issuer_path_health",
						fp = tostring(leaf.fp and leaf.fp:sub(1, 16) or "nil") .. "...",
					})
				)
				return false, "must_staple", detail
			end
		end
		if leaf_must and internalstore and mode ~= "open" then
			-- Pass blocks (not depleted PEM) so probe/presentable keep unresolved_must_staple.
			local probe_ok, probe_reason, probe_detail = _M.probe(internalstore, server_name, blocks, leaf.fp, false)
			if not probe_ok then
				-- Skip-leaf: no peer-bus write (tombstone / floor / canary are meta-derived,
				-- so every sibling refuses on its own without this worker revoking the pin).
				local detail = probe_detail or probe_reason or "probe_failed"
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
		-- Return blocks so staple/attach see the same CertificateEntrys + unresolved flag.
		return true, blocks, leaf.fp
	end

	-- Collect ClientHello-compatible leaves that pass Must-Staple / path health, then
	-- prefer the sibling whose issuer path is most completely stapled (fewest NULL slots).
	-- First match alone would stick on ok_partial while a fully stapled sibling exists.
	local last_err, last_detail
	local preferred = candidates[1]
	local healthy = {}
	for ci, leaf in ipairs(candidates) do
		-- Probe only (no set_cert) via install_one's health gates, then discard.
		-- Re-run install after selection so set_cert lands on the chosen leaf once.
		local blocks = issuer_linked_chain_blocks(leaf.pem, intermediates)
		local path_ok, path_detail = true, nil
		if mode ~= "open" then
			path_ok, path_detail = issuer_path_intermediate_ready(blocks)
		end
		if not path_ok then
			log(
				ngx.ERR,
				format_staple_decision(path_detail or "unmet", {
					tag = "OCSP_MUST_STAPLE_REFUSE",
					action = "skip_leaf",
					mode = mode,
					detail = "issuer_path_health",
					fp = tostring(leaf.fp and leaf.fp:sub(1, 16) or "nil") .. "...",
				})
			)
			last_err, last_detail = "must_staple", path_detail or "unmet"
		else
			local leaf_must = resolve_leaf_must_staple(leaf.pem, leaf.fp) == true
			if leaf_must and mode == "open" then
				leaf_must = false
			end
			local leaf_ok = true
			local leaf_detail = nil
			if leaf_must and internalstore and mode ~= "open" then
				local probe_ok, probe_reason, probe_detail =
					_M.probe(internalstore, server_name, blocks, leaf.fp, false)
				if not probe_ok then
					leaf_ok = false
					-- Skip-leaf demotion never writes the peer bus (see install_one).
					leaf_detail = probe_detail or probe_reason or "probe_failed"
					log(
						ngx.ERR,
						format_staple_decision(leaf_detail, {
							tag = "OCSP_MUST_STAPLE_REFUSE",
							action = "skip_leaf",
							mode = mode,
							fp = tostring(leaf.fp and leaf.fp:sub(1, 16) or "nil") .. "...",
						})
					)
					last_err, last_detail = "must_staple", leaf_detail
				end
			end
			if leaf_ok then
				healthy[#healthy + 1] = {
					leaf = leaf,
					ci = ci,
					nulls = issuer_path_null_slots(blocks),
				}
			end
		end
	end
	if #healthy > 0 then
		local best = healthy[1]
		for i = 2, #healthy do
			local h = healthy[i]
			if h.nulls < best.nulls then
				best = h
			end
		end
		local ok_inst, a, b = install_one(best.leaf, false)
		if ok_inst then
			if best.ci > 1 or (best.nulls < healthy[1].nulls) then
				local detail = "staple_health_fallback"
				if best.nulls < healthy[1].nulls then
					detail = "path_completeness"
				end
				log(
					ngx.NOTICE,
					format_staple_decision("skip_slot", {
						tag = "OCSP_STAPLE_HEALTH_FALLBACK",
						detail = detail,
						null_slots = best.nulls,
						fp = tostring(best.leaf.fp and best.leaf.fp:sub(1, 16) or "nil") .. "...",
						server_name = server_name or "nil",
					})
				)
			end
			log_skipped_sibling_leaves(leaves, best.leaf, server_name)
			return true, a, b
		end
		last_err, last_detail = a, b
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
local function staple_from_fingerprint(internalstore, server_name, fingerprint, probe_only, mode, chain_blocks)
	mode = mode or "normal"
	local meta = read_ocsp_json(fingerprint)
	local must_staple = ocsp_json_must_staple(meta)
	-- open (incl. stapling off): no enforcement, same as the PEM leaf path in _M.staple.
	-- Gates below still skip a bad body; they just return false instead of refusing.
	if must_staple and mode == "open" then
		must_staple = false
	end
	-- Fingerprint-only: intermediate Must-Staple is unprovable without PEM chain.
	-- Must-Staple leaves refuse with fingerprint_chain_unavailable (see attach_fp).
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
		log(
			ngx.DEBUG,
			format_staple_decision("stapling_off", { tag = "OCSP_STAPLING_OFF", detail = "ngx_ocsp_unavailable" })
		)
		return false
	end

	-- Attach helper: Must-Staple without chain → fingerprint_chain_unavailable.
	local function attach_fp(resp)
		if must_staple and (type(chain_blocks) ~= "table" or #chain_blocks < 1) then
			return nil, "fingerprint_chain_unavailable"
		end
		return attach_ocsp_staple(ocsp, resp, chain_blocks)
	end

	-- Must-Staple without chain: refuse before L1/disk work (unprovable intermediate MS).
	if must_staple and (type(chain_blocks) ~= "table" or #chain_blocks < 1) then
		if probe_only then
			return false, "must_staple", "fingerprint_chain_unavailable"
		end
		return must_staple_refuse(fingerprint, meta, nil, "fingerprint_chain_unavailable", mode)
	end

	local cached, cached_verified, cached_epoch, cached_expires = get_l1(internalstore, fingerprint)
	if cached then
		if not l1_matches_disk(internalstore, fingerprint, cached, cached_epoch) then
			drop_cache(internalstore, fingerprint)
		else
			local fresh, fresh_why = resp_still_fresh(cached_expires, fingerprint, meta)
			if not fresh then
				log(
					ngx.ERR,
					"OCSP L1 response past nextUpdate/expires; discarding fp=" .. fingerprint:sub(1, 16) .. "..."
				)
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
						log(
							ngx.ERR,
							"OCSP CertID refuse fingerprint staple reason="
								.. tostring(why)
								.. " fp="
								.. fingerprint:sub(1, 16)
								.. "..."
						)
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
						set_ok, set_err = attach_fp(cached)
					end)
					if ok_set and set_ok then
						local exp = meta_effective_expires_unix(meta, cached_expires)
						-- Re-warm with the epoch l1_matches_disk already accepted.
						if verified then
							warm_cache(internalstore, fingerprint, cached, true, exp, cached_epoch)
						else
							warm_cache(internalstore, fingerprint, cached, false, exp, cached_epoch)
						end
						log_ocsp_stapled(server_name, nil, fingerprint, cached)
						return true
					end
					log(ngx.ERR, "OCSP failed to set stapling from L1: " .. tostring(set_err or set_ok))
					drop_cache(internalstore, fingerprint)
					local detail = tostring(set_err or set_ok)
					if
						must_staple
						or detail == "fingerprint_chain_unavailable"
						or detail == "multi_staple_attach_failed"
						or detail == "intermediate_must_staple_libssl"
						or detail == "intermediate_must_staple_colony"
					then
						return must_staple_refuse(fingerprint, meta, cached, detail, mode)
					end
				end
			end
		end
	end

	local resp = read_file(ocsp_path(fingerprint))
	if resp then
		local fresh, fresh_why = resp_still_fresh(nil, fingerprint, meta)
		if not fresh then
			log(
				ngx.ERR,
				"OCSP disk response past nextUpdate/expires; refusing staple fp=" .. fingerprint:sub(1, 16) .. "..."
			)
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
				log(
					ngx.ERR,
					"OCSP CertID refuse fingerprint staple reason="
						.. tostring(why)
						.. " fp="
						.. fingerprint:sub(1, 16)
						.. "..."
				)
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
				set_ok, set_err = attach_fp(resp)
			end)
			if ok_set and set_ok then
				warm_cache(internalstore, fingerprint, resp, verified, meta_effective_expires_unix(meta))
				log_ocsp_stapled(server_name, nil, fingerprint, resp)
				return true
			end
			log(ngx.ERR, "OCSP failed to set stapling: " .. tostring(set_err or set_ok))
			local detail = tostring(set_err or set_ok)
			if
				must_staple
				or detail == "fingerprint_chain_unavailable"
				or detail == "multi_staple_attach_failed"
				or detail == "intermediate_must_staple_libssl"
				or detail == "intermediate_must_staple_colony"
			then
				return must_staple_refuse(fingerprint, meta, resp, detail, mode)
			end
			return false
		end
	end

	if must_staple then
		return must_staple_refuse(fingerprint, meta, nil, "response_not_found", mode)
	end
	return false
end

local function staple_one_leaf(
	internalstore,
	ocsp,
	ssl,
	blocks,
	leaf_pem,
	fingerprint,
	must_staple,
	server_name,
	probe_only,
	mode
)
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
				log(
					ngx.ERR,
					"OCSP L1 response past nextUpdate/expires; discarding fp=" .. fingerprint:sub(1, 16) .. "..."
				)
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
				issuers = issuer_candidates(blocks, leaf_pem, fingerprint, shard_issuer_pem or false)
				local ok_id, why = certid_matches_handshake_leaf(leaf_pem, cached, issuers)
				if not ok_id then
					log(
						ngx.ERR,
						"OCSP CertID refuse L1 staple reason="
							.. tostring(why)
							.. " fp="
							.. fingerprint:sub(1, 16)
							.. "..."
					)
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
						local path_ok, path_detail = issuer_path_intermediate_ready(blocks)
						if not path_ok then
							return false, "must_staple", path_detail or "unmet"
						end
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
					if
						attach_detail == "intermediate_must_staple_libssl"
						or attach_detail == "intermediate_must_staple_colony"
						or attach_detail == "multi_staple_attach_failed"
						or attach_detail == "fingerprint_chain_unavailable"
						or attach_detail == "issuer_unresolved_must_staple"
						or must_staple
					then
						local detail = attach_detail
						if
							detail ~= "intermediate_must_staple_libssl"
							and detail ~= "intermediate_must_staple_colony"
							and detail ~= "multi_staple_attach_failed"
							and detail ~= "fingerprint_chain_unavailable"
							and detail ~= "issuer_unresolved_must_staple"
						then
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
				issuers = issuer_candidates(blocks, leaf_pem, fingerprint, shard_issuer_pem or false)
				local result, result_detail = try_staple(
					ocsp,
					ssl,
					cached,
					leaf_pem,
					issuers,
					shard_issuer_spki,
					probe_only,
					meta,
					fingerprint,
					blocks
				)
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
						local path_ok, path_detail = issuer_path_intermediate_ready(blocks)
						if not path_ok then
							return false, "must_staple", path_detail or "unmet"
						end
						return true
					end
					warm_cache(
						internalstore,
						fingerprint,
						cached,
						true,
						meta_effective_expires_unix(meta or read_ocsp_json(fingerprint), cached_expires),
						cached_epoch
					)
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
					if
						result_detail == "intermediate_must_staple_libssl"
						or result_detail == "intermediate_must_staple_colony"
						or result_detail == "multi_staple_attach_failed"
						or result_detail == "fingerprint_chain_unavailable"
						or result_detail == "issuer_unresolved_must_staple"
						or result_detail == "certid_mismatch"
						or result_detail == "response_not_found"
						or must_staple
					then
						-- Preserve DROP/KEEP codes from try_staple (certid_mismatch, path demotion).
						-- Only bare false + canary ligand collapses to set_staple_failed / unmet.
						local detail = result_detail
						if
							detail ~= "intermediate_must_staple_libssl"
							and detail ~= "intermediate_must_staple_colony"
							and detail ~= "multi_staple_attach_failed"
							and detail ~= "fingerprint_chain_unavailable"
							and detail ~= "issuer_unresolved_must_staple"
							and detail ~= "certid_mismatch"
							and detail ~= "response_not_found"
						then
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
			log(
				ngx.ERR,
				"OCSP disk response past nextUpdate/expires; refusing staple fp=" .. fingerprint:sub(1, 16) .. "..."
			)
			if must_staple then
				return must_staple_refuse(fingerprint, meta, nil, fresh_why or "response_stale", mode)
			end
			return false
		end
		issuers = issuers or issuer_candidates(blocks, leaf_pem, fingerprint, shard_issuer_pem or false)
		if serial_blacklist_blocks(fingerprint, resp) then
			if must_staple then
				return must_staple_refuse(fingerprint, meta, nil, "serial_blacklisted", mode)
			end
			return false
		end
		local result, result_detail =
			try_staple(ocsp, ssl, resp, leaf_pem, issuers, shard_issuer_spki, probe_only, meta, fingerprint, blocks)
		if result == true then
			local ligand_ok, ligand_detail = must_staple_binds_shared_ligand(meta, fingerprint, resp)
			if must_staple and not ligand_ok then
				return must_staple_refuse(fingerprint, meta, nil, ligand_detail, mode)
			end
			if probe_only then
				local path_ok, path_detail = issuer_path_intermediate_ready(blocks)
				if not path_ok then
					return false, "must_staple", path_detail or "unmet"
				end
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
			if
				result_detail == "intermediate_must_staple_libssl"
				or result_detail == "intermediate_must_staple_colony"
				or result_detail == "multi_staple_attach_failed"
				or result_detail == "fingerprint_chain_unavailable"
				or result_detail == "issuer_unresolved_must_staple"
				or result_detail == "certid_mismatch"
				or result_detail == "response_not_found"
				or must_staple
			then
				local detail = result_detail
				if
					detail ~= "intermediate_must_staple_libssl"
					and detail ~= "intermediate_must_staple_colony"
					and detail ~= "multi_staple_attach_failed"
					and detail ~= "fingerprint_chain_unavailable"
					and detail ~= "issuer_unresolved_must_staple"
					and detail ~= "certid_mismatch"
					and detail ~= "response_not_found"
				then
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
	maybe_rearm_l1_warmer()

	local mode = ocsp_staple_mode(internalstore, server_name)
	local fp_hint = normalize_fp_hint(cert_fp_hint)
	-- Accept PEM string or issuer-linked blocks table (preserves unresolved_must_staple).
	local blocks = nil
	if type(cert_pem) == "table" and #cert_pem > 0 then
		blocks = cert_pem
	elseif type(cert_pem) == "string" and cert_pem ~= "" then
		blocks = pem_blocks(cert_pem)
	end
	local pem_ok = type(blocks) == "table" and #blocks > 0

	if not pem_ok then
		if fp_hint then
			return soften_must_staple(mode, staple_from_fingerprint(internalstore, server_name, fp_hint, false, mode))
		end
		return false
	end

	-- Fullchain order: first block is the leaf. Do not scan intermediates for key type
	-- (an ECDSA intermediate would steal the staple from an RSA leaf).
	local leaf_pem = blocks[1]
	if not leaf_pem then
		return false
	end
	-- Drop off-path bag PEMs (sibling dual-cert leaf, cross-signs) before Must-Staple scan.
	blocks = presentable_chain_blocks(blocks)
	leaf_pem = blocks[1] or leaf_pem

	-- Staple only this leaf's SPKI. Never use a dual-cert sibling hint (RSA hint on ECDSA leaf),
	-- including for the Must-Staple decision below.
	local leaf_fp = spki_fingerprint(leaf_pem)
	if fp_hint and leaf_fp and fp_hint ~= leaf_fp then
		log_ocsp_staple_skip(
			cert_pubkey_kind(leaf_pem) == "ec" and "rsa" or "ec",
			fp_hint,
			"wrong_key_type_hint",
			server_name
		)
		fp_hint = nil
	end
	-- No SPKI from PEM: fingerprint-only path (no sibling borrow possible without a second leaf).
	local fingerprint = leaf_fp or fp_hint

	local must_tri = resolve_leaf_must_staple(leaf_pem, fingerprint)
	-- Fail closed: unknown (nil) enforces Must-Staple; proven false does not.
	local must_staple = must_tri ~= false

	-- open: disable Must-Staple enforcement entirely (still staple when possible).
	if must_staple and mode == "open" then
		log(ngx.NOTICE, "OCSP_STAPLE_MODE=open - Must-Staple enforcement disabled for " .. (server_name or "unknown"))
		must_staple = false
	elseif must_tri == true and fingerprint then
		log(ngx.INFO, "OCSP-Must-Staple for fp=" .. fingerprint:sub(1, 16) .. "...")
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
		log(
			ngx.DEBUG,
			format_staple_decision("stapling_off", { tag = "OCSP_STAPLING_OFF", detail = "ngx_ocsp_unavailable" })
		)
		return false
	end
	local ssl = require "ngx.ssl"

	local result, reason, detail =
		staple_one_leaf(internalstore, ocsp, ssl, blocks, leaf_pem, fingerprint, must_staple, server_name, false, mode)
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
	maybe_rearm_l1_warmer()
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
	local fp_hint = normalize_fp_hint(cert_fp_hint)
	-- Accept PEM string or issuer-linked blocks table (preserves unresolved_must_staple).
	local blocks = nil
	if type(cert_pem) == "table" and #cert_pem > 0 then
		blocks = cert_pem
	elseif type(cert_pem) == "string" and cert_pem ~= "" then
		blocks = pem_blocks(cert_pem)
	end
	local pem_ok = type(blocks) == "table" and #blocks > 0
	if not pem_ok then
		if fp_hint then
			local ok, reason, detail = staple_from_fingerprint(internalstore, server_name, fp_hint, true, mode)
			return finish(ok, reason, detail)
		end
		return true
	end
	local leaf_pem = blocks[1]
	if not leaf_pem then
		return false
	end
	blocks = presentable_chain_blocks(blocks)
	leaf_pem = blocks[1] or leaf_pem
	-- Issuer-path readiness binds dual-cert health even when the leaf itself is not Must-Staple.
	local path_ok, path_detail = issuer_path_intermediate_ready(blocks)
	if not path_ok then
		return finish(false, "must_staple", path_detail or "unmet")
	end
	-- Never let a dual-cert sibling hint decide this leaf's Must-Staple bit.
	local leaf_fp = spki_fingerprint(leaf_pem)
	if fp_hint and leaf_fp and fp_hint ~= leaf_fp then
		fp_hint = nil
	end
	local fingerprint = leaf_fp or fp_hint
	-- Fail closed: unknown enforces Must-Staple; proven false may load unstapled.
	if resolve_leaf_must_staple(leaf_pem, fingerprint) == false then
		-- Optional leaf stapling: path already scored; leaf may load without a live body.
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
	if not fingerprint then
		return finish(false, "must_staple", "fingerprint_unavailable")
	end
	local result, reason, detail =
		staple_one_leaf(internalstore, ocsp, ssl, blocks, leaf_pem, fingerprint, true, server_name, true, mode)
	if result == true then
		return true
	end
	if result == false then
		return finish(false, reason, detail)
	end
	return finish(false, "must_staple", "response_not_found")
end

-- Cross-subsystem allow-pin bus (HTTP ↔ stream). Missing pin refuses Must-Staple.
-- meta must carry der_sha256 (+ soft_recall_gen); string-only generation ids are gone.
function _M.peer_refuse_blocks(fingerprint, meta, resp)
	return peer_refuse_blocks(fingerprint, meta, resp)
end

-- Shared skip predicate for HTTP refuse_must_staple and stream must_staple_refuse.
-- Transient / soft-recall causes must not enter the allow-pin bus. skip ⊆ KEEP.
function _M.should_skip_peer_bus(detail, meta, fingerprint)
	return should_skip_peer_bus(detail, meta, fingerprint)
end

function _M.record_peer_refuse(fingerprint, meta, decision, resp)
	return record_peer_refuse(fingerprint, meta, resp, decision)
end

function _M.drop_allow_pin(fingerprint)
	return drop_allow_pin(fingerprint)
end

function _M.write_allow_pin(fingerprint, der_sha256, soft_recall_gen, expires_unix)
	return write_allow_pin(fingerprint, der_sha256, soft_recall_gen, expires_unix)
end

-- Back-compat: clear = drop allow pin (+ legacy refuse).
function _M.clear_peer_refuse(fingerprint)
	return drop_allow_pin(fingerprint)
end

-- True when the leaf PEM or ocsp.json marks Must-Staple (TLS Feature status_request).
-- Unknown (resty miss + no ocsp.json) returns true (fail closed), matching handshake.
function _M.requires_must_staple(cert_pem, cert_fp_hint)
	local fp_hint = normalize_fp_hint(cert_fp_hint)
	local leaf_pem = nil
	if type(cert_pem) == "string" and cert_pem ~= "" then
		local blocks = pem_blocks(cert_pem)
		leaf_pem = blocks[1]
	end
	local leaf_fp = leaf_pem and spki_fingerprint(leaf_pem) or nil
	return resolve_leaf_must_staple(leaf_pem, leaf_fp or fp_hint) ~= false
end

-- Tri-state export for HTTP/conf callers that need unknown ≠ false vs true.
-- Returns true | false | nil (see resolve_leaf_must_staple).
function _M.resolve_leaf_must_staple(cert_pem, fingerprint)
	return resolve_leaf_must_staple(cert_pem, fingerprint)
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
local l1_warmer_no_add_logged = false
local l1_warmer_last_epoch = nil
local l1_warmer_last_full = 0
-- Store the warmer was armed with; lets a handshake re-arm it after a failed reschedule.
local l1_warmer_store = nil
local l1_warmer_rearm_at = 0
local L1_WARMER_REARM_INTERVAL = 5

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
	-- Lease free: only shared-dict add is atomic. set-then-recheck lets two
	-- workers both observe an empty key and both scan. If add is missing,
	-- skip this tick (return false) instead of racing.
	local claimed = false
	pcall(function()
		local dict = internalstore.dict
		if dict and dict.add then
			claimed = dict:add(L1_WARMER_LEASE_KEY, token, L1_WARMER_LEASE_TTL) and true or false
			return
		end
		if not l1_warmer_no_add_logged then
			l1_warmer_no_add_logged = true
			log(ngx.ERR, "OCSP L1 warmer lease has no dict.add; skipping scan to avoid a set/recheck race")
		end
		claimed = false
	end)
	return claimed
end

-- Directory order only (no Must-Staple priority). warm_l1_from_disk sorts
-- must_staple=true shards first so a short lease still warms fail-closed leaves.
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

-- Load one paged shard into L1 without crypto validate (outside ligand + allow-pin
-- are enough for the handshake authorize path). Runs off the TLS critical path only.
-- Do not re-warm generations the handshake would refuse (allow-pin missing/mismatch
-- or serial-blacklist): that churns shm and forces refuse/drop on every hit.
local function warm_one_shard(internalstore, fingerprint)
	if not internalstore or not is_fp64(fingerprint) then
		return false
	end
	local meta = read_ocsp_json(fingerprint)
	meta = ligand_or_meta(meta, fingerprint)
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
-- list_ocsp_fingerprints is directory order. This warmer sorts Must-Staple
-- shards first (ocsp.json must_staple=true) so a lease that expires mid-scan
-- still covers fail-closed leaves before optional ones.
-- Returns warmed count.
function _M.warm_l1_from_disk(internalstore)
	if not internalstore then
		return 0
	end
	local fps = list_ocsp_fingerprints()
	-- Read each ocsp.json once: reading inside the comparator cost O(n log n) disk
	-- reads, and a file changing mid-sort made the order inconsistent, so table.sort
	-- raised "invalid order function" and the whole pass was lost.
	local is_must = {}
	for _, fp in ipairs(fps) do
		local meta = read_ocsp_json(fp)
		is_must[fp] = type(meta) == "table" and meta.must_staple == true
	end
	table.sort(fps, function(a, b)
		if is_must[a] ~= is_must[b] then
			return is_must[a]
		end
		return a < b
	end)
	local warmed = 0
	for _, fp in ipairs(fps) do
		local ok, did = pcall(warm_one_shard, internalstore, fp)
		if ok and did then
			warmed = warmed + 1
		end
	end
	if warmed > 0 then
		log(
			ngx.INFO,
			"OCSP L1 warmer loaded " .. tostring(warmed) .. " shard(s) subsystem=" .. tostring(ngx.config.subsystem)
		)
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
	-- Off handshake: ensure allow/ligand/legacy-refuse dirs exist (job writes pins).
	if not ensure_ocsp_bus_dirs() then
		log(ngx.ERR, "OCSP could not provision ocsp-allow/ocsp-ligand dirs; allow-pin bus may fail")
	end
	-- Publish multi-staple attach capability for ocsp-refresh (intermediate fetch gate).
	pcall(openssl_multi_staple_ready)
	l1_warmer_started = true
	l1_warmer_store = internalstore

	local function tick(premature)
		if premature then
			return
		end
		-- Refresh this worker's multi-staple colony vote (MIN across live workers).
		if _multi_staple_state ~= nil then
			pcall(publish_multi_staple_attach, _multi_staple_state ~= false, false)
		else
			pcall(openssl_multi_staple_ready)
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

-- A failed ngx.timer.at reschedule used to stop the warmer for the worker's lifetime.
-- Handshakes re-arm it (throttled) once it has been started at least once.
maybe_rearm_l1_warmer = function()
	if l1_warmer_started or not l1_warmer_store then
		return
	end
	if ngx.worker and ngx.worker.exiting and ngx.worker.exiting() then
		return
	end
	local now = ngx.now()
	if now - l1_warmer_rearm_at < L1_WARMER_REARM_INTERVAL then
		return
	end
	l1_warmer_rearm_at = now
	pcall(_M.start_l1_warmer, l1_warmer_store)
end

-- Public attach: presentable_chain_blocks first, then attach_ocsp_staple.
-- Reviewers: multi-staple build/set0 failure refuses when intermediate Must-Staple
-- is present (multi_staple_attach_failed); leaf-only fallback only otherwise.
-- Pass fullchain PEM/blocks — nil chain cannot prove intermediate Must-Staple
-- (fingerprint-only Must-Staple uses fingerprint_chain_unavailable upstream).
function _M.attach_ocsp_staple(leaf_resp, chain_pem_or_blocks)
	local ok_ocsp, ocsp = pcall(require, "ngx.ocsp")
	if not ok_ocsp or not ocsp or not ocsp.set_ocsp_status_resp then
		return nil, "ngx_ocsp_unavailable"
	end
	local blocks = presentable_chain_blocks(chain_pem_or_blocks)
	return attach_ocsp_staple(ocsp, leaf_resp, blocks)
end

return _M
