-- Shared OCSP stapling config, staple_decision codes, logging, paths and constants.
-- Part of bunkerweb.ocsp; other modules use the .internal table, callers use bunkerweb.ocsp.
local _M = {}

local ngx = ngx

local function log(level, msg)
	ngx.log(level, msg)
end

-- Validate SNI against service's declared domains (security hardening).
-- Returns: true if SNI is in the service's SERVER_NAME list, false otherwise.
-- Prevents attacker-controlled SNI from routing to unintended services.
local function sni_in_service_domains(site_vars, sni)
	if not site_vars or not sni or type(site_vars) ~= "table" then
		return false
	end
	local names = site_vars["SERVER_NAME"]
	if type(names) ~= "string" or names == "" then
		return false
	end
	local sni_lower = tostring(sni):lower()
	for name in names:gmatch("%S+") do
		if name == sni or name:lower() == sni_lower then
			return true
		end
	end
	return false
end

-- Resolve SNI to primary service id with explicit precision tiers (highest to lowest).
-- Tier 1: exact match on primary service id (key in vars table)
-- Tier 2: case-insensitive match on primary service id
-- Tier 3: SERVER_NAME token search (exact match then case-insensitive)
-- Returns: primary service id (key in vars) or nil. Ensures consistent resolution order.
-- Includes SNI domain whitelist validation to prevent routing to unintended services.
local function resolve_multisite_service_id_from_vars(vars, sni)
	if not sni or type(vars) ~= "table" then
		return nil
	end
	-- Tier 1: exact match on primary service id (bypass whitelist; FQDN as service name)
	if type(vars[sni]) == "table" then
		return sni
	end
	local sni_lower = tostring(sni):lower()
	-- Tier 2: case-insensitive match on primary service id
	for primary, site_vars in pairs(vars) do
		if primary ~= "global" and type(primary) == "string" and type(site_vars) == "table" then
			if primary:lower() == sni_lower then
				return primary
			end
		end
	end
	-- Tier 3: SERVER_NAME token search with domain whitelist validation.
	-- Tier 3a: exact token match with whitelist check
	for primary, site_vars in pairs(vars) do
		if primary ~= "global" and type(site_vars) == "table" then
			if sni_in_service_domains(site_vars, sni) then
				return primary
			end
		end
	end
	return nil
end

-- Apply per-site setting override: check site-specific value, fall back to global.
-- Separate phase from SNI resolution for clarity and testability.
local function apply_site_override(vars, service_id, name, global_value)
	if not service_id or type(vars[service_id]) ~= "table" then
		return global_value
	end
	local site_value = vars[service_id][name]
	if site_value ~= nil then
		return site_value
	end
	return global_value
end

-- Read a multisite setting: per-site (primary service id) wins over global.
-- Per-request resolution ensures config changes (reload) invalidate cached service mappings.
local function get_site_variable(internalstore, server_name, name)
	local ok, vars = pcall(function()
		return internalstore:get("variables", true)
	end)
	if not ok or type(vars) ~= "table" or type(vars["global"]) ~= "table" then
		return nil
	end
	local value = vars["global"][name]
	if vars["global"]["MULTISITE"] == "yes" and server_name then
		-- Per-request SNI resolution: always resolve against current config, no caching
		local service_id = resolve_multisite_service_id_from_vars(vars, server_name)
		-- Separate phase: apply per-site override
		value = apply_site_override(vars, service_id, name, value)
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
-- This is intentional policy (not a silent bug): refuse codes still log
-- ssl_use_ocsp_stapling_no when a Must-Staple leaf hits the stapling-off path.
-- Unknown OCSP_STAPLE_MODE values coerce to "normal" (fail-close), never soft-open.
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
	-- μs claim/restore window (or reclaimable orphan claim) — not "never canaried".
	allow_pin_claim_inflight = true,
	-- soft_recall_gen present but non-integer (type drift). Local refuse; KEEP pin.
	gen_type_drift = true,
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
	-- Body present but no accepted issuer PEM/SPKI for ngx.ocsp.validate (not a missing DER).
	issuer_unavailable = true,
	-- Every issuer candidate failed validate (body present; not empty queue, not missing DER).
	validate_exhausted = true,
	-- Disk ocsp.der exists but is zero-length (truncate race); not ENOENT.
	response_empty = true,
	-- Fingerprint-only path cannot finish a gen-bound force_ffi walk (no leaf PEM issuers).
	force_ffi_pending = true,
	unmet = true,
}

-- Allow-pin DROP/KEEP policy (single source of truth for pin.lua + docs).
-- Keys are raw refuse_cause strings BEFORE runbook alias collapse.
-- DROP = semantic poison about this body vs leaf / colony / canary (sibling must
--   fail closed until a new generation is canary-paged).
-- KEEP = this worker's view of pin state or its own clock. Must not erase a pin
--   every zone shares (stale reader / skewed clock → fleet Must-Staple outage).
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
	der_sha256_mismatch = true,
	missing_der_sha256 = true,
	invalid_der_sha256 = true,
	fingerprint_mismatch_or_missing_meta = true,
	canary_refused = true,
}

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
	allow_pin_claim_inflight = true,
	gen_type_drift = true,
	ligand_missing = true,
	shared_ligand = true,
	peer_refuse_unavailable = true,
	fingerprint_chain_unavailable = true,
	multi_staple_attach_failed = true,
	issuer_unresolved_must_staple = true,
	issuer_unavailable = true,
	validate_exhausted = true,
	response_empty = true,
	force_ffi_pending = true,
	thisUpdate_future = true,
	thisUpdate_stale = true,
	lifetime_invalid = true,
	lifetime_too_long = true,
	thisUpdate_unreadable = true,
}

-- DROP causes that may revoke using meta.der_sha256 when resp is nil.
local META_ONLY_DROP_ALLOW = {
	tombstoned = true,
	serial_blacklisted = true,
	cluster_floor = true,
	canary_refused = true,
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
-- Canonical field ordering prevents information leakage and improves auditability.
-- All logs use fixed ordering regardless of how many fields are present.
local function format_staple_decision(code, fields)
	local raw = tostring(code or "unmet")
	local decision, alias_detail = normalize_staple_decision(code)
	local parts = { "staple_decision=" .. decision }
	local f = {}
	if type(fields) == "table" then
		for k, v in pairs(fields) do
			f[k] = v
		end
	end
	-- Always stamp subsystem so HTTP/stream logs cannot look identical while diverging.
	if (f.subsystem == nil or f.subsystem == "") and ngx.config and ngx.config.subsystem then
		f.subsystem = ngx.config.subsystem
	end
	-- Forensic invariant: refuse_cause= holds the pre-alias raw whenever we collapsed
	-- a code (ligand_* → shared_ligand, canary_* → canary_refused, …). Pin DROP/KEEP
	-- must key that raw — never staple_decision= alone. If the caller already set
	-- refuse_cause, keep it; otherwise use alias_detail or the raw closed code.
	if f.refuse_cause == nil or f.refuse_cause == "" then
		if alias_detail then
			f.refuse_cause = alias_detail
		elseif
			decision ~= "ok"
			and decision ~= "ok_partial"
			and decision ~= "stapling_off"
			and decision ~= "skip_slot"
		then
			f.refuse_cause = raw
		end
	end
	if alias_detail then
		if f.detail == nil or f.detail == "" then
			f.detail = alias_detail
		elseif tostring(f.detail) ~= alias_detail then
			-- Caller preseeded detail= with a different string — do not hide the alias
			-- raw (already in refuse_cause=); also surface it as alias=.
			f.alias = alias_detail
		end
	end
	-- Canonical field ordering: fixed sequence for consistent log parsing.
	-- Prevents side-channel leaks where field order reveals internal resolution hierarchy.
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
	-- Append any dynamic fields not in canonical order (rare; audit these).
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
-- Always logs staple_decision=CODE (runbook) with tag=OCSP_MUST_STAPLE_REFUSE
-- and refuse_cause= raw detail (pre-alias) so pin/bus forensics survive collapse.
-- Skips a second ERR when set_certs_from_pem already logged action=continue_install
-- for this handshake (ngx.ctx.bw_ocsp_soft_fuse_logged) — one intentional fuse, one line.
--
-- Return contract (callers MUST branch on the second value, not bare falsiness):
--   soft continue → false, nil, "continue"
--   abort         → false, "must_staple", "abort"
-- Stream ssl_certificate already checks soft_reason == "must_staple".
local function soften_must_staple(mode, ok, reason, detail)
	if reason ~= "must_staple" then
		return ok, reason
	end
	local action = "abort"
	if mode == "staple_only" or mode == "open" then
		action = "continue"
	end
	local raw_cause = tostring(detail or "unmet")
	local already = ngx.ctx and ngx.ctx.bw_ocsp_soft_fuse_logged
	if not already then
		log(
			ngx.ERR,
			format_staple_decision(raw_cause, {
				tag = "OCSP_MUST_STAPLE_REFUSE",
				action = action,
				mode = mode or "normal",
				refuse_cause = raw_cause,
			})
		)
	end
	if action == "continue" then
		return false, nil, "continue"
	end
	return false, "must_staple", "abort"
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

local function read_file(path)
	if type(path) ~= "string" or path == "" then
		return nil, "missing"
	end
	local f = io.open(path, "rb")
	if not f then
		return nil, "missing"
	end
	local data = f:read("*a")
	f:close()
	if data and #data > 0 then
		return data
	end
	-- Empty file ≠ ENOENT: callers that only use the first return still see nil,
	-- but second return lets refuse paths distinguish truncate races from absence.
	return nil, "empty"
end

-- First two hex chars of the SPKI fingerprint → 16×16 directory layout.
local function fingerprint_shard(fingerprint)
	if not fingerprint or #fingerprint < 2 then
		return "0", "0"
	end
	return fingerprint:sub(1, 1), fingerprint:sub(2, 2)
end

-- Build OCSP response path from fingerprint. Nil fingerprint / empty string → nil
-- (never the shared 0/0/unknown sink — that was a last-writer-wins collision hole).
-- Optional collision_index appends .N for rare SPKI-dir collisions.
local function ocsp_path(fingerprint, collision_index)
	if type(fingerprint) ~= "string" or fingerprint == "" then
		return nil
	end
	local h, l = fingerprint_shard(fingerprint)
	local base = "/var/cache/bunkerweb/ssl/" .. h .. "/" .. l .. "/" .. fingerprint .. "/ocsp.der"
	if collision_index and collision_index > 0 then
		return base .. "." .. tostring(collision_index)
	end
	return base
end

-- Build issuer PEM path from fingerprint. Empty/nil → nil (no shared unknown sink).
local function issuer_path(fingerprint)
	if type(fingerprint) ~= "string" or fingerprint == "" then
		return nil
	end
	local h, l = fingerprint_shard(fingerprint)
	return "/var/cache/bunkerweb/ssl/" .. h .. "/" .. l .. "/" .. fingerprint .. "/issuer.pem"
end

-- Cache key includes fingerprint to auto-invalidate on certificate rotation.
-- Same fingerprint = same cert; new cert = new fingerprint = new cache entry.
-- This prevents stale OCSP decisions from applying to rotated certificates.
local function cache_key(fingerprint)
	if not fingerprint or fingerprint == "" then
		return "TLS:SSL:ocsp:unknown"
	end
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

local function path_exists(path)
	local f = io.open(path, "rb")
	if f then
		f:close()
		return true
	end
	return false
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

_M.internal = {
	DROP_ALLOW_ON_REFUSE = DROP_ALLOW_ON_REFUSE,
	KEEP_ALLOW_ON_REFUSE = KEEP_ALLOW_ON_REFUSE,
	META_ONLY_DROP_ALLOW = META_ONLY_DROP_ALLOW,
	OCSP_CLOCK_SKEW_SECONDS = OCSP_CLOCK_SKEW_SECONDS,
	OCSP_MAX_INTRINSIC_LIFETIME_SECONDS = OCSP_MAX_INTRINSIC_LIFETIME_SECONDS,
	OCSP_MAX_THIS_UPDATE_AGE_SECONDS = OCSP_MAX_THIS_UPDATE_AGE_SECONDS,
	OCSP_VALIDATE_BUDGET_NS = OCSP_VALIDATE_BUDGET_NS,
	OCSP_VALIDATE_BUDGET_S = OCSP_VALIDATE_BUDGET_S,
	OCSP_VALIDATE_MAX_ISSUERS = OCSP_VALIDATE_MAX_ISSUERS,
	apply_site_override = apply_site_override,
	cache_key = cache_key,
	current_ocsp_epoch = current_ocsp_epoch,
	fingerprint_shard = fingerprint_shard,
	format_staple_decision = format_staple_decision,
	is_fp64 = is_fp64,
	issuer_path = issuer_path,
	log = log,
	log_stapling_off = log_stapling_off,
	normalize_fp_hint = normalize_fp_hint,
	ocsp_path = ocsp_path,
	ocsp_staple_mode = ocsp_staple_mode,
	path_exists = path_exists,
	read_file = read_file,
	resp_binding = resp_binding,
	sni_in_service_domains = sni_in_service_domains,
	soften_must_staple = soften_must_staple,
	stapling_enabled = stapling_enabled,
	to_hex = to_hex,
}

return _M
