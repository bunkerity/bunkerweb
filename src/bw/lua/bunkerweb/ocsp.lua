--[[
================================================================================
OCSP Main Orchestrator Module: Central Stapling and Validation Pipeline
================================================================================

MODULE OVERVIEW:
Central orchestrator for OCSP stapling across HTTP and stream subsystems.
Implements two-tier validation (Tier 1 L1 cache + Tier 2 FFI), allow-pin bus
coordination, Must-Staple enforcement, and dual-cert leaf ranking.

DESIGN: Split architecture with HTTP (ocsp_http.lua) and stream (stream/ocsp.lua)
subsystem-specific code calling into this module for shared logic: SPKI parsing,
CertID matching, chain building, Must-Staple detection, cache management.

KEY VALIDATION TIERS:
- Tier 1 (L1 Cache): Shared-dict lookup (0.1-1ms) with verified binding
  (SHA256 of DER) and soft_recall_gen match. Hit → skip FFI, attach immediately.
- Tier 2 (Full FFI): ngx.ocsp.validate_ocsp_response (10-20ms) on L1 miss.
  Result shared via compare-and-delete for thundering-herd protection.
- Tier 3 (Async): Background job validation (ocsp-refresh.py) pre-warms L1
  for next epoch. TLS path uses canary-paged ligand + allow-pin for skip-validate.

TWO-TIER STORAGE:
- In-Memory: Per-worker PEM/DER/ISS caches (no shared state to avoid invalidation)
- Disk: Shard metadata (ocsp.json), outside ligand, L1 cache dumps, allow-pins
- Shared-Dict L1: Coherent via .ocsp_epoch (job bump bus)

DUAL-CERT HANDLING:
- ordered_leaves_for_handshake(): ClientHello signature_algorithms aware
- Must-Staple tri-state + allow-pin gate for health ranking
- Single leaf install per TLS handshake (HTTP/2 one cert per conn)

ALLOW-PIN BUS:
- Missing pin → Must-Staple refuse (conservative default)
- Present pin → generation-matched allow (der_sha256 + soft_recall_gen)
- Compare-and-delete revoke (atomic, gen-bound, sibling claim sweep)

MUST-STAPLE ENFORCEMENT:
- Tri-state detection (true/false/nil unknown): TLS Feature + ocsp.json
- Fail-closed: unknown treated as Must-Staple (enforce)
- Soft-fuse modes (open/staple_only) continue handshake on Must-Staple miss

KEY FUNCTIONS:
- try_staple(): Leaf + issuer validation → attach with budget guard + force_ffi latch
- validate(): FFI signature + death-time check with cross-handshake sharing
- ordered_leaves_for_handshake(): Rank leaves by Must-Staple health + sig-alg fit
- attachment flow: probe → health → final install with staple attach/clear

DEPENDENCIES:
All OCSP submodules: ocsp_common, ocsp_cert, ocsp_chain, ocsp_store, ocsp_pin,
ocsp_must_staple, ocsp_warmer; HTTP integration: ocsp_http.lua;
Stream integration: stream/ocsp.lua

================================================================================
]]

local _M = {}

local ngx = ngx

-- ============================================================================
-- OCSP Validation Architecture Overview
-- ============================================================================
--
-- Two-tier validation strategy to minimize TLS handshake latency:
--
-- TIER 1: TLS Critical Path (must complete in <100ms)
--   - L1 cache lookup [~0.1ms] ← most handshakes hit here
--   - Metadata validation [<1ms] ← tombstone, peer-refuse, cluster checks
--   - SPKI provisional trust [~1ms] ← defer full cert validation
--   - Async result check [~0.1ms] ← if scheduler already validated, skip FFI
--   - Attach response [~0.5-1ms] ← ngx.ocsp.set_ocsp_status_resp FFI
--
-- TIER 2: Background Job (async/scheduler, off-path)
--   - Full FFI validation [10-20ms] ← ngx.ocsp.validate_ocsp_response
--   - Certificate chain validation [~5ms] ← parse + verify issuer
--   - Result cached for TLS path [~0.1ms] ← shared dict, 3600s TTL
--
-- Key insight: TLS path uses cached result if available; validates only if needed.
--
-- Async validation status tracking (off-path):
-- - "pending" = validation queued, not yet done (attach speculatively)
-- - "validated" = scheduler confirmed valid (skip TLS-path FFI)
-- - "failed" = scheduler found invalid (abort, don't staple)

local ASYNC_VALIDATION_PENDING = "pending" -- Validation queued, not yet done
local ASYNC_VALIDATION_DONE = "validated" -- Validation complete, result stored
local ASYNC_VALIDATION_FAILED = "failed" -- Validation failed, response invalid

-- SPKI-only provisional trust: validate against issuer key fingerprint without full cert.
-- Reduces cert parsing & chain traversal from TLS critical path (~15ms → ~1ms).
-- Full issuer cert validation deferred to background job.
-- local SPKI_VALIDATION_PROVISIONAL = "provisional"  -- SPKI matched, awaiting full cert validation
-- local SPKI_VALIDATION_CONFIRMED = "confirmed"      -- SPKI matched & issuer cert validated
-- local SPKI_VALIDATION_FAILED = "failed_spki"       -- SPKI mismatch or issuer unavailable

-- Versioned OCSP responses: prevent stale cache after cert rotation.
-- Each response version tagged with generation/epoch so stale cached responses
-- are automatically invalidated when certificates change or new OCSP issued.
-- Scheduler updates global version on cert rotation; TLS path checks match before using cache.
-- local OCSP_VERSION_KEY = "OCSP:RESPONSE_VERSION"   -- Global response version (incremented on rotation)
-- local OCSP_RESPONSE_VERSION_PREFIX = "OCSP:VERSION:"  -- Per-fingerprint: version at time of validation

local common = require("bunkerweb.ocsp_common").internal
local OCSP_CLOCK_SKEW_SECONDS = common.OCSP_CLOCK_SKEW_SECONDS
local OCSP_VALIDATE_BUDGET_NS = common.OCSP_VALIDATE_BUDGET_NS
local OCSP_VALIDATE_BUDGET_S = common.OCSP_VALIDATE_BUDGET_S
local OCSP_VALIDATE_MAX_ISSUERS = common.OCSP_VALIDATE_MAX_ISSUERS
local current_ocsp_epoch = common.current_ocsp_epoch
local format_staple_decision = common.format_staple_decision
local issuer_path = common.issuer_path
local log = common.log
local log_stapling_off = common.log_stapling_off
local normalize_fp_hint = common.normalize_fp_hint
local ocsp_path = common.ocsp_path
local ocsp_staple_mode = common.ocsp_staple_mode
local read_file = common.read_file
local resp_binding = common.resp_binding
local soften_must_staple = common.soften_must_staple
local stapling_enabled = common.stapling_enabled

local cert = require("bunkerweb.ocsp_cert").internal
local aia_uri_pin_ok = cert.aia_uri_pin_ok
local cert_pubkey_kind = cert.cert_pubkey_kind
local cert_sig_profile = cert.cert_sig_profile
local cert_spki_fingerprint = cert.cert_spki_fingerprint
local certid_consistent_with_meta = cert.certid_consistent_with_meta
local certid_matches_handshake_leaf = cert.certid_matches_handshake_leaf
local key_spki_fingerprint = cert.key_spki_fingerprint
local leaf_matches_scheme = cert.leaf_matches_scheme
local parse_pem_keys = cert.parse_pem_keys
local pem_blocks = cert.pem_blocks
local spki_fingerprint = cert.spki_fingerprint

local store = require("bunkerweb.ocsp_store").internal
local cluster_floor_blocks = store.cluster_floor_blocks
local store_drop_cache = store.drop_cache
-- drop_cache: thin wrapper around store.drop_cache.
-- Dual-cert ranking probes every ClientHello-compatible Must-Staple sibling before
-- set_cert. Those probes must not clear L1 for a fingerprint that a later handshake
-- (or a sibling leaf still under consideration) may still need. Callers set
-- ngx.ctx.bw_ocsp_skip_l1_drop = true around rank-time _M.probe only; install-time
-- re-probe and real refuse paths leave it unset so poison still evicts DRAM.
-- ============================================================================
-- drop_cache(internalstore, fingerprint)
-- ============================================================================
-- PURPOSE:
--   Evict L1 cache entry for a certificate. Guards against L1 poisoning during
--   multi-cert leaf ranking (probe phase) when same fingerprint reused in different
--   Must-Staple health scenarios.
--
-- PARAMETERS:
--   internalstore (table): shared dict object (ngx.shared.internalstore or _stream)
--   fingerprint (string): certificate SPKI fingerprint (64 hex chars)
--
-- RETURNS:
--   nil (side effect: evicts L1 entry if guard is not set)
--
-- SIDE EFFECTS:
--   - Calls store_drop_cache() to evict L1 shared-dict entry
--   - Checks ngx.ctx.bw_ocsp_skip_l1_drop guard (set during ranking phase)
--   - If guard is set, returns early (no eviction)
--
-- DESIGN NOTES:
--   - Guard (bw_ocsp_skip_l1_drop) prevents L1 poison during ranking:
--     Probing multiple Must-Staple siblings must not clear L1 for a fingerprint
--     that a later handshake (or a sibling still under consideration) may need
--   - Install-time re-probe and real refuse paths leave guard unset so poison
--     still evicts DRAM (normal operation, safety-critical)
--   - Performance: O(1) (shared dict operation)
--
-- RELATED:
--   - store_drop_cache() in ocsp_store.lua (actual eviction)
--   - ngx.ctx.bw_ocsp_skip_l1_drop guard set by ordered_leaves_for_handshake()
--
-- ============================================================================
local function drop_cache(internalstore, fingerprint)
	if ngx.ctx and ngx.ctx.bw_ocsp_skip_l1_drop then
		return
	end
	return store_drop_cache(internalstore, fingerprint)
end
local entry_verified = store.entry_verified
local get_l1 = store.get_l1
local l1_matches_disk = store.l1_matches_disk
local ligand_or_meta = store.ligand_or_meta
local meta_effective_expires_unix = store.meta_effective_expires_unix
local meta_tombstoned = store.meta_tombstoned
local must_staple_binds_shared_ligand = store.must_staple_binds_shared_ligand
local ocsp_json_authorizes_resp = store.ocsp_json_authorizes_resp
local read_ocsp_json = store.read_ocsp_json
local resp_still_fresh = store.resp_still_fresh
local serial_blacklist_blocks = store.serial_blacklist_blocks
local shard_not_paged = store.shard_not_paged
local soft_recall_gen_of = store.soft_recall_gen_of
local generation_tuple = store.generation_tuple
local warm_cache = store.warm_cache

local pin = require("bunkerweb.ocsp_pin").internal
-- Skip-validate needs live allow-pin (sha, gen), not ligand+paged alone.
local canary_paged_body_ok = pin.canary_trust_ok
local must_staple_refuse = pin.must_staple_refuse
local peer_refuse_blocks = pin.peer_refuse_blocks

local chain = require("bunkerweb.ocsp_chain").internal
local attach_ocsp_staple = chain.attach_ocsp_staple
local chain_pem_from_blocks = chain.chain_pem_from_blocks
local clear_connection_staple = chain.clear_connection_staple
local issuer_linked_chain_blocks = chain.issuer_linked_chain_blocks

-- Lazy-loaded must-staple module. Always load when required: mode is per-site
-- (open vs normal), so a worker-global "skip load because open" memo was wrong
-- and ocsp_staple_mode() without internalstore+SNI always returned "open".
local must_staple_module = nil
-- ============================================================================
-- get_must_staple_module()
-- ============================================================================
-- PURPOSE:
--   Lazy-load and cache ocsp_must_staple module for Must-Staple detection.
--   Returns cached module on subsequent calls (single pcall overhead).
--
-- PARAMETERS:
--   None
--
-- RETURNS:
--   (table|nil): Must-Staple module if available
--               nil if module unavailable or load failed
--
-- SIDE EFFECTS:
--   - Caches result in local variable (Lua module-level)
--   - Calls: require("bunkerweb.ocsp_must_staple") once (lazy-load)
--   - Performance: O(1) after first call (cached)
--
-- DESIGN NOTES:
--   - Lazy-load: Module loaded only on first call
--   - Caching: false cached to indicate unavailable (not nil retry loop)
--   - Fail-safe: pcall() catches load errors (no throw)
--   - Type check: Validates module is table before caching
--   - Used by: set_certs_from_pem(), staple(), probe() for Must-Staple detection
--   - Performance: First call ~1ms (module load), subsequent <0.1ms
--
-- RELATED:
--   - ocsp_must_staple.lua provides Must-Staple detection
--   - _M.requires_must_staple() uses this to get detector
--   - staple()/probe() use for Must-Staple health checks
--
-- ============================================================================
local function get_must_staple_module()
	if must_staple_module ~= nil then
		if must_staple_module == false then
			return nil
		end
		return must_staple_module
	end
	local ok, mod = pcall(require, "bunkerweb.ocsp_must_staple")
	if ok and type(mod) == "table" then
		must_staple_module = mod
		return mod
	end
	must_staple_module = false
	return nil
end

-- Async validation state management (off-path validation)
-- Defers OCSP validation to background job, reduces TLS critical path latency.

-- Async status is fingerprint-keyed but value-bound to body generation:
--   "pending|sha|gen" | "validated|sha|gen" | "failed|sha|gen"
-- Soft-recall / re-page of a new body must not inherit a prior FAILED for 3600s.
-- ============================================================================
-- async_validation_key(fingerprint)
-- ============================================================================
-- PURPOSE:
--   Generate shared-dict key for async validation status tracking.
--   Used to cache whether background job has validated an OCSP response.
--
-- PARAMETERS:
--   fingerprint (string): certificate SPKI fingerprint (64 hex chars, required)
--
-- RETURNS:
--   (string): key formatted as "OCSP:ASYNC_VALIDATE:{fingerprint}"
--   (nil): if fingerprint is nil or empty (invalid input)
--
-- DESIGN NOTES:
--   - Key format enables per-certificate status tracking
--   - Used with async_status_payload() to encode status + generation binding
--   - Generation binding (soft_recall_gen) prevents stale status blocking new cert
--   - Performance: O(1) string concatenation
--
-- RELATED:
--   - async_status_payload() encodes status with generation
--   - get_async_validation_status() retrieves status
--   - mark_async_validation_* functions store status
--
-- ============================================================================
local function async_validation_key(fingerprint)
	if not fingerprint or fingerprint == "" then
		return nil
	end
	return "OCSP:ASYNC_VALIDATE:" .. fingerprint
end

-- ============================================================================
-- async_status_payload(status, meta, resp, fingerprint)
-- ============================================================================
-- PURPOSE:
--   Encode async validation status with generation binding to prevent stale
--   status from blocking new cert bodies after soft-recall (cert rotation).
--
-- PARAMETERS:
--   status (string): validation status ("pending"|"validated"|"failed")
--   meta (table): ocsp.json metadata containing soft_recall_gen
--   resp (string): OCSP response DER bytes (for generation tuple)
--   fingerprint (string): certificate fingerprint (for ligand lookup)
--
-- RETURNS:
--   (string): encoded payload "{status}|{sha256_der}|{soft_recall_gen}"
--   (nil): if validation fails or inputs invalid
--
-- SIDE EFFECTS:
--   - Reads meta.soft_recall_gen and resp body
--   - Calls generation_tuple() to extract DER SHA + gen
--
-- DESIGN NOTES:
--   - Format: "status|sha256_64chars|gen_number"
--   - Generation binding: soft_recall_gen increments on cert rotation
--   - Old payload (gen=N) becomes invalid when soft_recall_gen increments (N+1)
--   - Prevents "VALIDATED" from gen=1 blocking new DER with gen=2
--   - Performance: O(n) for generation_tuple() + parsing
--
-- RELATED:
--   - parse_async_status_payload() decodes this format
--   - generation_tuple() extracts (DER_SHA, soft_recall_gen)
--   - soft_recall_gen prevents stale responses blocking new certs
--
-- ============================================================================
local function async_status_payload(status, meta, resp, fingerprint)
	if not status then
		return nil
	end
	local sha, gen = generation_tuple(ligand_or_meta(meta, fingerprint), resp)
	if type(sha) ~= "string" or #sha ~= 64 or type(gen) ~= "number" then
		return nil
	end
	return status .. "|" .. sha .. "|" .. tostring(gen)
end

-- ============================================================================
-- parse_async_status_payload(raw)
-- ============================================================================
-- PURPOSE:
--   Decode async validation status payload with generation validation.
--   Extracts status + DER SHA + generation from encoded payload string.
--
-- PARAMETERS:
--   raw (string): encoded payload "{status}|{sha256}|{gen}" | nil or empty
--
-- RETURNS:
--   (string, string, number): (status, sha256_hex, soft_recall_gen)
--   (nil): if payload invalid, malformed, or legacy bare status (no gen)
--
-- DESIGN NOTES:
--   - Rejects legacy bare status (PENDING|DONE|FAILED with no "|")
--   - Validates format: must be "x|y|z" with z being a number
--   - SHA256 validation: must be exactly 64 hex characters
--   - Generation binding: soft_recall_gen must be positive number
--   - Performance: O(n) string parsing (~0.1ms)
--   - Used by: get_async_validation_status() to check status
--   - Related: async_status_payload() creates this format
--
-- ============================================================================
local function parse_async_status_payload(raw)
	if type(raw) ~= "string" or raw == "" then
		return nil
	end
	-- Legacy bare status (no gen) — treat as unknown so soft-recall is not blocked.
	if raw == ASYNC_VALIDATION_PENDING or raw == ASYNC_VALIDATION_DONE or raw == ASYNC_VALIDATION_FAILED then
		return nil
	end
	local a, b, c = raw:match("^([^|]+)|([^|]+)|([^|]+)$")
	if not a or not b or not c then
		return nil
	end
	local gen = tonumber(c)
	if type(b) ~= "string" or #b ~= 64 or not gen then
		return nil
	end
	return a, b, gen
end

-- ============================================================================
-- mark_async_validation_pending(fingerprint, meta, resp)
-- ============================================================================
-- PURPOSE:
--   Mark OCSP response as queued for async validation (short-term placeholder).
--   Signals to other TLS handshakes that validation is in-flight.
--
-- PARAMETERS:
--   fingerprint (string): certificate SPKI fingerprint
--   meta (table): ocsp.json metadata
--   resp (string): OCSP response DER
--
-- RETURNS:
--   nil (side effect: stores "pending|sha|gen" in shared dict)
--
-- SIDE EFFECTS:
--   - Writes to ngx.shared.bw_ocsp_validations with TTL 120s
--   - Wraps in pcall to handle shared dict unavailability
--
-- DESIGN NOTES:
--   - Short TTL (120s): job should validate quickly or status expires
--   - Used in try_staple() before FFI to mark "in-flight"
--   - Generation binding: prevents old responses from blocking new cert
--
-- RELATED:
--   - mark_async_validation_done() marks success
--   - mark_async_validation_failed() marks failure
--   - get_async_validation_status() retrieves status
--
-- ============================================================================
local function mark_async_validation_pending(fingerprint, meta, resp)
	if not ngx.shared or not ngx.shared.bw_ocsp_validations or not fingerprint then
		return
	end
	local key = async_validation_key(fingerprint)
	local payload = async_status_payload(ASYNC_VALIDATION_PENDING, meta, resp, fingerprint)
	if not key or not payload then
		return
	end
	pcall(function()
		ngx.shared.bw_ocsp_validations:set(key, payload, 120)
	end)
end

-- ============================================================================
-- mark_async_validation_done(fingerprint, meta, resp)
-- ============================================================================
-- PURPOSE:
--   Mark OCSP response as successfully validated by async job.
--   Signals to subsequent TLS handshakes that validation is complete + valid.
--
-- PARAMETERS:
--   fingerprint (string): certificate SPKI fingerprint
--   meta (table): ocsp.json metadata
--   resp (string): OCSP response DER
--
-- RETURNS:
--   nil (side effect: stores "validated|sha|gen" in shared dict)
--
-- SIDE EFFECTS:
--   - Writes to ngx.shared.bw_ocsp_validations with TTL 3600s (1 hour)
--   - Wraps in pcall to handle shared dict unavailability
--
-- DESIGN NOTES:
--   - Long TTL (3600s): validation result valid for 1 hour
--   - Used after successful async FFI validation
--   - Generation binding: soft-recall increments invalidate this status
--
-- RELATED:
--   - mark_async_validation_pending() marks start
--   - mark_async_validation_failed() marks failure
--   - get_async_validation_status() retrieves status
--
-- ============================================================================
local function mark_async_validation_done(fingerprint, meta, resp)
	if not ngx.shared or not ngx.shared.bw_ocsp_validations or not fingerprint then
		return
	end
	local key = async_validation_key(fingerprint)
	local payload = async_status_payload(ASYNC_VALIDATION_DONE, meta, resp, fingerprint)
	if not key or not payload then
		return
	end
	pcall(function()
		ngx.shared.bw_ocsp_validations:set(key, payload, 3600)
	end)
end

-- ============================================================================
-- mark_async_validation_failed(fingerprint, meta, resp)
-- ============================================================================
-- PURPOSE:
--   Mark OCSP response as validation failure in async job.
--   Signals to subsequent TLS handshakes that async validation failed.
--
-- PARAMETERS:
--   fingerprint (string): certificate SPKI fingerprint
--   meta (table): ocsp.json metadata
--   resp (string): OCSP response DER
--
-- RETURNS:
--   nil (side effect: stores "failed|sha|gen" in shared dict)
--
-- SIDE EFFECTS:
--   - Writes to ngx.shared.bw_ocsp_validations with TTL 3600s (1 hour)
--   - Wraps in pcall to handle shared dict unavailability
--
-- DESIGN NOTES:
--   - Long TTL (3600s): failure status valid for 1 hour
--   - Advisory only: TLS path still attempts local FFI validation
--   - Generation binding: soft-recall invalidates this status
--   - Conservative: failure doesn't hard-block stapling (job issuer set thin)
--
-- RELATED:
--   - mark_async_validation_pending() marks start
--   - mark_async_validation_done() marks success
--   - get_async_validation_status() retrieves status
--
-- ============================================================================
local function mark_async_validation_failed(fingerprint, meta, resp)
	if not ngx.shared or not ngx.shared.bw_ocsp_validations or not fingerprint then
		return
	end
	local key = async_validation_key(fingerprint)
	local payload = async_status_payload(ASYNC_VALIDATION_FAILED, meta, resp, fingerprint)
	if not key or not payload then
		return
	end
	pcall(function()
		ngx.shared.bw_ocsp_validations:set(key, payload, 3600)
	end)
end

-- Returns status only when the stored generation matches this body; else nil.
-- ============================================================================
-- get_async_validation_status(fingerprint, meta, resp)
-- ============================================================================
-- PURPOSE:
--   Retrieve async validation status (if any) for OCSP response, with
--   generation binding to prevent stale status from blocking new cert.
--
-- PARAMETERS:
--   fingerprint (string): certificate SPKI fingerprint
--   meta (table): ocsp.json metadata (for ligand lookup + generation)
--   resp (string): OCSP response DER (for generation tuple)
--
-- RETURNS:
--   (string): "pending"|"validated"|"failed" if status found and generation matches
--   (nil): if no status, generation mismatch (soft-recall), or inputs invalid
--
-- DESIGN NOTES:
--   - Generation binding: stored (sha, gen) must match current (sha, gen)
--   - Soft-recall safety: old status (gen=1) rejected when gen increments (2)
--   - Shared dict access wrapped in pcall (handle unavailability gracefully)
--   - Three validation gates:
--     (1) Status present in shared dict
--     (2) Status payload parseable
--     (3) Generation + DER SHA match current state
--   - Performance: O(1) shared dict lookup (~0.1ms)
--   - Used by: try_staple() to skip FFI when async_validated
--
-- RELATED:
--   - mark_async_validation_* functions store status
--   - parse_async_status_payload() decodes status
--   - generation_tuple() extracts binding
--   - ligand_or_meta() chooses live state
--
-- ============================================================================
local function get_async_validation_status(fingerprint, meta, resp)
	if not ngx.shared or not ngx.shared.bw_ocsp_validations or not fingerprint then
		return nil
	end
	local key = async_validation_key(fingerprint)
	if not key then
		return nil
	end
	local raw
	pcall(function()
		raw = ngx.shared.bw_ocsp_validations:get(key)
	end)
	-- Decode status + generation binding from stored payload
	local status, stored_sha, stored_gen = parse_async_status_payload(raw)
	if not status then
		return nil
	end
	-- Extract current generation from metadata + response
	local sha, gen = generation_tuple(ligand_or_meta(meta, fingerprint), resp)
	if type(sha) ~= "string" or #sha ~= 64 or type(gen) ~= "number" then
		return nil
	end
	-- Generation match required: soft-recall increments gen, invalidating old status
	if sha ~= stored_sha or gen ~= stored_gen then
		return nil
	end
	return status
end

-- SPKI-only provisional trust: validate issuer key fingerprint without full cert.
-- Returns: issuer_spki (fingerprint) if found, nil otherwise.
-- Fast path: O(1) lookup, no cert parsing or chain traversal.
-- local function lookup_issuer_spki(issuer_fingerprint)
-- 	if not issuer_fingerprint or issuer_fingerprint == "" then
-- 		return nil
-- 	end
--
-- 	-- Query shared state for cached issuer SPKI
-- 	-- Key format: "OCSP:ISSUER_SPKI:fingerprint"
-- 	local ngx_shared = ngx and ngx.shared
-- 	if not ngx_shared or not ngx_shared.bw_ocsp_validations then
-- 		return nil
-- 	end
--
-- 	local spki_key = "OCSP:ISSUER_SPKI:" .. issuer_fingerprint
-- 	local issuer_spki
-- 	pcall(function()
-- 		issuer_spki = ngx_shared.bw_ocsp_validations:get(spki_key)
-- 	end)
-- 	return issuer_spki
-- end

-- Cache issuer SPKI for fast lookups (provisional trust).
-- Issuer cert validation happens async in background.
-- TTL: 3600s (until next issuer refresh).
-- local function cache_issuer_spki(issuer_fingerprint, issuer_spki)
-- 	if not issuer_fingerprint or not issuer_spki then
-- 		return
-- 	end
--
-- 	local ngx_shared = ngx and ngx.shared
-- 	if not ngx_shared or not ngx_shared.bw_ocsp_validations then
-- 		return
-- 	end
--
-- 	local spki_key = "OCSP:ISSUER_SPKI:" .. issuer_fingerprint
-- 	pcall(function()
-- 		ngx_shared.bw_ocsp_validations:set(spki_key, issuer_spki, 3600)
-- 	end)
-- end

-- Validate leaf certificate against issuer SPKI (provisional, no full cert required).
-- Returns: issuer_spki if SPKI matches, nil otherwise.
-- Latency: ~1ms (no cert parsing, no chain traversal).
-- Safe: only used when async job will do full validation later.
-- local function validate_against_issuer_spki(leaf_pem, issuer_spki_expected)
-- 	if not leaf_pem or not issuer_spki_expected then
-- 		return nil
-- 	end
--
-- 	-- Extract issuer key reference from leaf certificate
-- 	-- This requires the leaf cert to have issuer information
-- 	-- For now: use issuer_spki_expected directly for validation
-- 	-- In full implementation: extract issuer DN from leaf, lookup SPKI
--
-- 	return issuer_spki_expected  -- Placeholder: assume match if provided
-- end

-- Check SPKI validation status (provisional trust state).
-- Returns: "provisional" (SPKI matched, awaiting full cert),
--          "confirmed" (SPKI + issuer cert validated),
--          "failed_spki" (SPKI mismatch), or nil (not checked yet).
-- local function get_spki_validation_status(issuer_fingerprint)
-- 	if not ngx.shared or not ngx.shared.bw_ocsp_validations or not issuer_fingerprint then
-- 		return nil
-- 	end
--
-- 	local spki_status_key = "OCSP:SPKI_STATUS:" .. issuer_fingerprint
-- 	local status
-- 	pcall(function()
-- 		status = ngx.shared.bw_ocsp_validations:get(spki_status_key)
-- 	end)
-- 	return status
-- end

-- Mark SPKI validation status in shared state.
-- Used by TLS path (provisional) and async job (confirmed/failed).
-- local function set_spki_validation_status(issuer_fingerprint, status, ttl)
-- 	if not issuer_fingerprint or not status then
-- 		return
-- 	end
--
-- 	local ngx_shared = ngx and ngx.shared
-- 	if not ngx_shared or not ngx_shared.bw_ocsp_validations then
-- 		return
-- 	end
--
-- 	local spki_status_key = "OCSP:SPKI_STATUS:" .. issuer_fingerprint
-- 	local ttl_val = ttl or 3600
-- 	pcall(function()
-- 		ngx_shared.bw_ocsp_validations:set(spki_status_key, status, ttl_val)
-- 	end)
-- end

-- Versioned OCSP Responses: Track response versions to auto-invalidate stale cached responses.
-- When certificates rotate or new OCSP responses are issued, increment global version.
-- TLS path checks: if cached_version ~= current_version, cache is stale (re-validate).
-- local function get_ocsp_response_version()
-- 	if not ngx or not ngx.shared or not ngx.shared.bw_ocsp_validations then
-- 		return 0
-- 	end
-- 	local version
-- 	pcall(function()
-- 		version = ngx.shared.bw_ocsp_validations:get(OCSP_VERSION_KEY)
-- 	end)
-- 	return tonumber(version) or 0
-- end

-- local function set_ocsp_response_version(version)
-- 	if not version or version <= 0 then
-- 		return
-- 	end
-- 	local ngx_shared = ngx and ngx.shared
-- 	if not ngx_shared or not ngx_shared.bw_ocsp_validations then
-- 		return
-- 	end
-- 	pcall(function()
-- 		ngx_shared.bw_ocsp_validations:set(OCSP_VERSION_KEY, tostring(version), 86400)
-- 	end)
-- end

-- local function increment_ocsp_response_version()
-- 	local current = get_ocsp_response_version()
-- 	local next_version = current + 1
-- 	set_ocsp_response_version(next_version)
-- 	return next_version
-- end

-- local function get_cached_response_version(fingerprint)
-- 	if not fingerprint or fingerprint == "" then
-- 		return 0
-- 	end
-- 	if not ngx or not ngx.shared or not ngx.shared.bw_ocsp_validations then
-- 		return 0
-- 	end
-- 	local version_key = OCSP_RESPONSE_VERSION_PREFIX .. fingerprint
-- 	local version
-- 	pcall(function()
-- 		version = ngx.shared.bw_ocsp_validations:get(version_key)
-- 	end)
-- 	return tonumber(version) or 0
-- end

-- local function set_cached_response_version(fingerprint, version)
-- 	if not fingerprint or not version then
-- 		return
-- 	end
-- 	local ngx_shared = ngx and ngx.shared
-- 	if not ngx_shared or not ngx_shared.bw_ocsp_validations then
-- 		return
-- 	end
-- 	local version_key = OCSP_RESPONSE_VERSION_PREFIX .. fingerprint
-- 	pcall(function()
-- 		ngx_shared.bw_ocsp_validations:set(version_key, tostring(version), 86400)
-- 	end)
-- end

-- local function is_response_version_current(fingerprint)
-- 	if not fingerprint or fingerprint == "" then
-- 		return false
-- 	end
-- 	local cached_version = get_cached_response_version(fingerprint)
-- 	local current_version = get_ocsp_response_version()
-- 	if cached_version == 0 or current_version == 0 then
-- 		return true
-- 	end
-- 	return cached_version == current_version
-- end

-- Cache Warmup: Pre-load OCSP responses at startup.
-- Scans cache directory and marks valid responses as already validated.
-- Reduces first handshake latency (20ms → 1-5ms) for cached certificates.
-- Returns: {warmed=N, stale=N, invalid=N, failed=N}
-- local function warmup_ocsp_cache()
-- 	if not ngx or not ngx.shared or not ngx.shared.bw_ocsp_validations then
-- 		return {warmed=0, stale=0, invalid=0, failed=0}
-- 	end
--
-- 	local cache_dir = ocsp_path() or "/var/cache/bunkerweb/ocsp"
-- 	local stats = {warmed=0, stale=0, invalid=0, failed=0}
--
-- 	-- Open cache directory
-- 	local dir_handle, dir_err = io.popen("find " .. cache_dir .. " -maxdepth 2 -name '*.der' 2>/dev/null")
-- 	if not dir_handle then
-- 		log(ngx.WARN, "OCSP warmup: could not open cache directory: " .. tostring(dir_err))
-- 		return stats
-- 	end
--
-- 	-- Scan for OCSP response files
-- 	for ocsp_file in dir_handle:lines() do
-- 		local read_ok, read_err
-- 		local ocsp_der
--
-- 		-- Read OCSP response from disk
-- 		read_ok, read_err = pcall(function()
-- 			local f = io.open(ocsp_file, "rb")
-- 			if f then
-- 				ocsp_der = f:read("*a")
-- 				f:close()
-- 			end
-- 		end)
--
-- 		if not read_ok or not ocsp_der then
-- 			stats.failed = stats.failed + 1
-- 			goto continue_warmup
-- 		end
--
-- 		-- Extract fingerprint from path: /path/shard/fingerprint.der
-- 		local fingerprint = ocsp_file:match("([a-f0-9]+)%.der$")
-- 		if not fingerprint or #fingerprint ~= 64 then
-- 			stats.invalid = stats.invalid + 1
-- 			goto continue_warmup
-- 		end
--
-- 		-- Check if response is expired (basic check: has thisUpdate/nextUpdate)
-- 		-- For now: assume valid if file is recent (mtime within 7 days)
-- 		local mtime = io.popen("stat -f%m " .. ocsp_file .. " 2>/dev/null"):read("*n")
-- 		local current_time = os.time()
-- 		local age_seconds = (mtime and (current_time - mtime)) or 999999
-- 		local seven_days = 7 * 24 * 60 * 60  -- 604800 seconds
--
-- 		if age_seconds > seven_days then
-- 			stats.stale = stats.stale + 1
-- 			goto continue_warmup
-- 		end
--
-- 		-- Response looks valid: mark as pre-warmed
-- 		pcall(function()
-- 			-- Mark as already validated by async job
-- 			mark_async_validation_done(fingerprint)
--
-- 			-- Tag with current version
-- 			local current_version = get_ocsp_response_version()
-- 			set_cached_response_version(fingerprint, current_version)
--
-- 			stats.warmed = stats.warmed + 1
-- 		end)
--
-- 		::continue_warmup::
-- 	end
--
-- 	dir_handle:close()
--
-- 	log(ngx.INFO, "OCSP cache warmup complete: " .. stats.warmed .. " ready, " ..
-- 		stats.stale .. " stale, " .. stats.invalid .. " invalid, " ..
-- 		stats.failed .. " failed")
--
-- 	return stats
-- end

local issuer_path_intermediate_ready = chain.issuer_path_intermediate_ready
local issuer_path_null_slots = chain.issuer_path_null_slots
local note_connection_staple = chain.note_connection_staple
local presentable_chain_blocks = chain.presentable_chain_blocks

local warmer = require("bunkerweb.ocsp_warmer").internal
local maybe_rearm_l1_warmer = warmer.maybe_rearm_l1_warmer

-- ============================================================================
-- issuer_candidates(blocks, leaf_pem, fingerprint, stored_pem)
-- ============================================================================
-- PURPOSE:
--   Build list of issuer PEM candidates for FFI validation, with optional
--   shard issuer pin. Prevents re-encodings of same key from burning
--   validate_budget via deduplication by SPKI (not PEM bytes).
--
-- PARAMETERS:
--   blocks (table): certificate chain blocks (may include issuers)
--   leaf_pem (string): leaf certificate (for filtering chain)
--   fingerprint (string): leaf SPKI fingerprint (for reading issuer.pem)
--   stored_pem (string|false|nil):
--     - string: issuer.pem PEM content (use directly)
--     - false: issuer.pem confirmed absent (don't read from disk)
--     - nil: not checked yet (read from disk if available)
--
-- RETURNS:
--   (table): ordered {issuer_pem, ...} deduplicated by SPKI
--   (empty table): if no issuer candidates found (issuer_unavailable outcome)
--
-- SIDE EFFECTS:
--   - May read: issuer.pem from disk via issuer_path()
--   - Calls: spki_fingerprint() to deduplicate
--   - Logs: errors if issuer.pem unreadable (ERR level)
--
-- DESIGN NOTES:
--   - SPKI PIN ENFORCEMENT: If issuer.pem present, only that issuer's SPKI
--     is accepted (or identical re-encoding from chain). Prevents using
--     different CA to validate response (security).
--   - FAIL-OPEN: If issuer.pem absent, accept unpinned chain issuers
--     (conservative default when shard doesn't have pin).
--   - FAIL-CLOSED: If issuer.pem unreadable (corruption/permission),
--     refuse chain fallthrough (empty list → issuer_unavailable).
--   - DEDUPLICATION: Re-encodings of same key (PEM vs DER re-wrap)
--     deduplicated by SPKI. Prevents validate_budget burn on duplicates.
--   - Performance: O(n*m) where n=blocks, m=SPKI computations (but deduped)
--   - Empty list is valid outcome (→ issuer_unavailable, not error).
--
-- RELATED:
--   - try_staple() calls this to build validation candidate list
--   - validate() called for each candidate with validate_budget guard
--   - issuer_path() reads shard issuer.pem location
--   - spki_fingerprint() for PIN enforcement + deduplication
--
-- ============================================================================
local function issuer_candidates(blocks, leaf_pem, fingerprint, stored_pem)
	-- When the shard has issuer.pem, only accept that issuer SPKI (or an identical
	-- re-encoding from the chain). Do not let validate succeed against a different CA.
	-- false = issuer.pem confirmed absent; nil = not checked; string = PEM content
	local stored = nil
	local issuer_absent = false
	if stored_pem ~= nil then
		if stored_pem == false then
			issuer_absent = true
		else
			stored = stored_pem
		end
	elseif fingerprint then
		stored = read_file(issuer_path(fingerprint))
		if not stored then
			issuer_absent = true
		end
	end
	local want_spki = stored and spki_fingerprint(stored) or nil
	if stored and not want_spki then
		-- issuer.pem present but unparsable: do NOT fail-open to unpinned chain
		-- issuers (that would weaken the shard pin). Empty list → issuer_unavailable.
		local fp_str = fingerprint and fingerprint:sub(1, 16) or "nil"
		log(ngx.ERR, "OCSP issuer.pem unreadable SPKI for fp " .. fp_str .. "; refusing chain fallthrough")
		return {}
	end
	if issuer_absent and not want_spki then
		local fp_str = fingerprint and fingerprint:sub(1, 16) or "nil"
		log(ngx.DEBUG, "OCSP issuer.pem absent for fp " .. fp_str .. "; accepting chain issuers without SPKI pin")
	end

	local issuers = {}
	-- Dedupe by SPKI (not PEM bytes): re-encodings of the same key must not
	-- multiply ngx.ocsp.validate attempts into validate_budget.
	local seen = {}
	local function add(pem)
		if type(pem) ~= "string" or pem == "" then
			return
		end
		local got = spki_fingerprint(pem)
		if want_spki then
			if not got or got ~= want_spki then
				return
			end
		end
		local key = got or pem
		if seen[key] then
			return
		end
		seen[key] = true
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

-- ============================================================================
-- get_shared_validation_state_key(fingerprint, meta, resp)
-- ============================================================================
-- PURPOSE:
--   Build cache key for cross-handshake validation result sharing.
--   Binds key to leaf fingerprint + OCSP generation (soft-recall safe).
--
-- PARAMETERS:
--   fingerprint (string): leaf SPKI fingerprint (64 hex chars)
--   meta (table|nil): ocsp.json metadata for current generation
--   resp (string): OCSP response DER bytes (for generation tuple)
--
-- RETURNS:
--   (string|nil): cache key "OCSP:VALIDATE:{fp}:{sha}|{gen}"
--                 nil if unable to form generation tuple
--
-- SIDE EFFECTS:
--   - Calls: generation_tuple(), ligand_or_meta() for generation binding
--   - No state modification
--
-- DESIGN NOTES:
--   - Key format: "OCSP:VALIDATE:{fingerprint}:{sha256_of_der}|{generation}"
--   - Generation binding: Prevents DER₁ validation from attaching DER₂
--   - Fail-closed: Returns nil if generation_tuple fails (no cross-handshake share)
--   - Thundering-herd: Multiple handshakes share validation result (60s TTL)
--   - Per-generation: Soft-recall invalidates old key without cleanup
--   - Performance: O(1) key construction after generation_tuple (~0.1ms)
--
-- RELATED:
--   - set_shared_validation_result() writes using this key
--   - get_shared_validation_result() reads using this key
--   - generation_tuple() binds to current OCSP generation
--
-- ============================================================================
local function get_shared_validation_state_key(fingerprint, meta, resp)
	if not fingerprint or fingerprint == "" then
		return nil
	end
	local sha, gen = generation_tuple(ligand_or_meta(meta, fingerprint), resp)
	if type(sha) ~= "string" or #sha ~= 64 or type(gen) ~= "number" then
		-- No generation → no cross-handshake share (fail closed to local validate).
		return nil
	end
	return "OCSP:VALIDATE:" .. fingerprint .. ":" .. sha .. "|" .. tostring(gen)
end

-- ============================================================================
-- set_shared_validation_result(fingerprint, meta, resp, result)
-- ============================================================================
-- PURPOSE:
--   Store OCSP validation result in cross-handshake cache for thundering-herd.
--   Shares success ("pass") but not failure (prevents blocking fatter chain).
--
-- PARAMETERS:
--   fingerprint (string): leaf SPKI fingerprint
--   meta (table|nil): ocsp.json metadata
--   resp (string): OCSP response DER
--   result (boolean): validation outcome (true=pass, false=fail)
--
-- RETURNS:
--   None (side effect only)
--
-- SIDE EFFECTS:
--   - Writes: bw_ocsp_validations shared dict with "pass" (60s TTL)
--   - Clears: in_flight lock on failure (let other handshakes try)
--   - Performance: O(1) shared dict write (~0.1ms)
--
-- DESIGN NOTES:
--   - Success ("pass"): Cached for 60s, reused by concurrent handshakes
--   - Failure: NOT shared (thin issuer bag must not block fatter chain)
--   - Fail-closed: On failure, clear in_flight lock so waiters don't spin
--   - Thin vs Fatter: Multiple issuer chains in shard; thin fails, fatter succeeds
--   - TTL: 60s matches async shared validation timeout
--   - Thundering-herd: First handshake validates; others read "pass"
--
-- RELATED:
--   - get_shared_validation_state_key() builds the cache key
--   - get_shared_validation_result() reads the cached value
--   - set_shared_validation_in_flight() sets "in_flight" marker
--
-- ============================================================================
local function set_shared_validation_result(fingerprint, meta, resp, result)
	if not ngx.shared or not ngx.shared.bw_ocsp_validations then
		return
	end
	local key = get_shared_validation_state_key(fingerprint, meta, resp)
	if not key then
		return
	end
	if not result then
		-- Do not share "fail": a thin issuer bag must not block a later fuller
		-- chain for 60s. Release in_flight so peers are not stuck waiting.
		pcall(function()
			local cur = ngx.shared.bw_ocsp_validations:get(key)
			if cur == "in_flight" then
				ngx.shared.bw_ocsp_validations:delete(key)
			end
		end)
		return
	end
	pcall(function()
		ngx.shared.bw_ocsp_validations:set(key, "pass", 60)
	end)
end

-- ============================================================================
-- get_shared_validation_result(fingerprint, meta, resp, max_wait_ms)
-- ============================================================================
-- PURPOSE:
--   Retrieve cached OCSP validation result from cross-handshake cache.
--   Waits briefly if in-flight, returns nil on miss/timeout/failure.
--
-- PARAMETERS:
--   fingerprint (string): leaf SPKI fingerprint
--   meta (table|nil): ocsp.json metadata
--   resp (string): OCSP response DER
--   max_wait_ms (number|nil): max wait for in-flight result (default 100ms)
--
-- RETURNS:
--   (boolean): true if cached "pass" result found
--   (nil): on cache miss, timeout, failure, or unreadable state
--
-- SIDE EFFECTS:
--   - Reads: bw_ocsp_validations shared dict
--   - Sleeps: up to max_wait_ms if in-flight (0.001s per iteration)
--   - Performance: O(1) hit (<0.1ms), O(max_wait) spin on in-flight
--
-- DESIGN NOTES:
--   - Cold miss (nil): No validator yet; caller does FFI validation
--   - Pass (true): Cached result; skip FFI, use cached OCSP
--   - Failure (nil): Never cached (don't block fatter chains)
--   - In-flight (nil after wait): Concurrent validator still running; timeout safe
--   - Legacy "fail" (nil): Pre-pass-only writer; treat as cold miss
--   - Max wait: Default 100ms prevents spinning forever if validator hangs
--   - Thundering-herd: Fast path when first validator finishes
--
-- RELATED:
--   - set_shared_validation_result() writes the cache
--   - set_shared_validation_in_flight() marks validation in progress
--   - get_shared_validation_state_key() builds the cache key
--
-- ============================================================================
local function get_shared_validation_result(fingerprint, meta, resp, max_wait_ms)
	if not ngx.shared or not ngx.shared.bw_ocsp_validations then
		return nil
	end
	local key = get_shared_validation_state_key(fingerprint, meta, resp)
	if not key then
		return nil
	end
	local result
	pcall(function()
		result = ngx.shared.bw_ocsp_validations:get(key)
	end)
	-- Cold path: no concurrent validator — do not spin 100ms.
	if result == nil or result == false then
		return nil
	end
	if result == "pass" then
		return true
	end
	-- Legacy "fail" entries (pre pass-only writers): treat as cold miss so a
	-- rolling upgrade cannot validate_exhausted for 60s after soft-recall.
	if result == "fail" then
		return nil
	end
	if result ~= "in_flight" then
		return nil
	end
	-- Another handshake owns the lock — wait briefly for pass only.
	local t0 = ngx.now() * 1000
	local max_wait = max_wait_ms or 100
	while true do
		pcall(function()
			result = ngx.shared.bw_ocsp_validations:get(key)
		end)
		if result == "pass" then
			return true
		end
		if result == "fail" or result ~= "in_flight" then
			return nil
		end
		if (ngx.now() * 1000 - t0) > max_wait then
			return nil
		end
		ngx.sleep(0.001)
	end
end

-- ============================================================================
-- set_shared_validation_in_flight(fingerprint, meta, resp)
-- ============================================================================
-- PURPOSE:
--   Mark validation in-flight for this cert (thundering-herd lock).
--   Allows concurrent handshakes to wait for shared validation result.
--
-- PARAMETERS:
--   fingerprint (string): leaf SPKI fingerprint
--   meta (table|nil): ocsp.json metadata
--   resp (string): OCSP response DER
--
-- RETURNS:
--   (boolean): true if lock acquired, false if already locked or unavailable
--
-- SIDE EFFECTS:
--   - Writes: bw_ocsp_validations:add() with "in_flight" (60s TTL)
--   - Atomic: Uses add() (not set) to fail if key already exists
--   - Performance: O(1) shared dict operation (~0.1ms)
--
-- DESIGN NOTES:
--   - Lock pattern: add() returns false if key exists (first writer wins)
--   - TTL 60s: Matches shared dict timeout for validation results
--   - Atomic: Prevents multiple concurrent validators (lock-free approach)
--   - Fail-open: Returns false if shared dict unavailable (no lock possible)
--   - Waiting: Other handshakes spin via get_shared_validation_result()
--
-- RELATED:
--   - clear_shared_validation_in_flight() removes the lock
--   - get_shared_validation_result() waits on in-flight lock
--   - set_shared_validation_result() replaces with "pass" or clears on fail
--
-- ============================================================================
local function set_shared_validation_in_flight(fingerprint, meta, resp)
	if not ngx.shared or not ngx.shared.bw_ocsp_validations then
		return false
	end
	local key = get_shared_validation_state_key(fingerprint, meta, resp)
	if not key then
		return false
	end
	local ok
	pcall(function()
		ok = ngx.shared.bw_ocsp_validations:add(key, "in_flight", 60)
	end)
	return ok or false
end

-- ============================================================================
-- clear_shared_validation_in_flight(fingerprint, meta, resp)
-- ============================================================================
-- PURPOSE:
--   Release stuck in-flight lock (validate_budget abort or early exit).
--   Never deletes "pass" or "fail" results (only in_flight markers).
--
-- PARAMETERS:
--   fingerprint (string): leaf SPKI fingerprint
--   meta (table|nil): ocsp.json metadata
--   resp (string): OCSP response DER
--
-- RETURNS:
--   None
--
-- SIDE EFFECTS:
--   - Reads: current value from bw_ocsp_validations shared dict
--   - Writes: deletes only if current value is "in_flight" (CAS pattern)
--   - Performance: O(1) shared dict operation
--
-- DESIGN NOTES:
--   - CAS pattern: Read current value, delete only if it matches "in_flight"
--   - Fail-safe: Never deletes "pass" or "fail" results
--   - Validate_budget: Called when FFI validation hits time budget
--   - Thundering-herd: Releases lock so other handshakes can retry
--   - Preserves results: Race between clear and update is safe
--   - Early abort: Called if issuer list exhausted or FFI returns
--
-- RELATED:
--   - set_shared_validation_in_flight() sets the lock
--   - get_shared_validation_result() waits on lock
--   - try_staple() calls this on validate_budget abort
--
-- ============================================================================
local function clear_shared_validation_in_flight(fingerprint, meta, resp)
	if not ngx.shared or not ngx.shared.bw_ocsp_validations then
		return
	end
	local key = get_shared_validation_state_key(fingerprint, meta, resp)
	if not key then
		return
	end
	pcall(function()
		local cur = ngx.shared.bw_ocsp_validations:get(key)
		if cur == "in_flight" then
			ngx.shared.bw_ocsp_validations:delete(key)
		end
	end)
end

-- ============================================================================
-- bounded_cache_set(cache, key, value, max_entries)
-- ============================================================================
-- PURPOSE:
--   Insert into bounded Lua table cache with LRU eviction.
--   Prevents per-request DER cache from growing unbounded.
--
-- PARAMETERS:
--   cache (table): Lua table to use as cache
--   key (string): cache key (typically DER hash or fingerprint)
--   value (any): value to store
--   max_entries (number): maximum cache entries before eviction
--
-- RETURNS:
--   None (side effect only)
--
-- SIDE EFFECTS:
--   - Modifies: cache table (adds entry, possibly evicts first)
--   - Iteration: Counts entries (O(n) where n=current cache size)
--
-- DESIGN NOTES:
--   - LRU approximation: Evicts "first" key in iteration order (not true LRU)
--   - Evict-on-full: Only evicts when adding NEW key at max_entries
--   - Update safe: Re-setting existing key does not evict (count check)
--   - Fail-open: If any param missing, silently does nothing
--   - Performance: O(n) where n=cache size; typical n=10-20 (acceptable)
--   - Per-request: Fresh cache per TLS handshake (no accumulation)
--   - Use case: DER parsing cache (fingerprint → DER) per handshake
--
-- RELATED:
--   - validate() uses this for per-request DER cache
--   - Per-request cache (ngx.ctx) separate from shared dict cache
--
-- ============================================================================
local function bounded_cache_set(cache, key, value, max_entries)
	if not cache or not key or not value then
		return
	end
	-- Count entries
	local count = 0
	local first_key = nil
	for k in pairs(cache) do
		if not first_key then
			first_key = k
		end
		count = count + 1
	end
	-- If at limit, evict oldest (first key in iteration order) only when adding new entries
	if count >= max_entries and first_key and not cache[key] then
		cache[first_key] = nil
	end
	cache[key] = value
end

-- ============================================================================
-- validate(ocsp, ssl, ocsp_der, leaf_pem, issuer_pem, shard_issuer_spki)
-- ============================================================================
-- PURPOSE:
--   Perform one FFI-based OCSP response validation attempt against a leaf+issuer
--   pair. Verifies OCSP signature and validates time bounds (nextUpdate check).
--   Called by try_staple() in a loop over issuer candidates.
--
-- PARAMETERS:
--   ocsp (ffi): ngx.ocsp FFI module object (for validate_ocsp_response call)
--   ssl (ffi): ngx.ssl FFI module object (for cert_pem_to_der function)
--   ocsp_der (string): OCSP response DER bytes (required, non-empty)
--   leaf_pem (string): leaf certificate PEM (required)
--   issuer_pem (string): issuer certificate PEM (must be non-empty)
--   shard_issuer_spki (string): expected issuer SPKI fingerprint for pin validation
--                              (optional; if set, issuer SPKI must match)
--
-- RETURNS:
--   (boolean): true if OCSP validation succeeds (signature valid + time bounds ok)
--              false if validation fails, issuer SPKI mismatch, or any error
--
-- SIDE EFFECTS:
--   - Calls FFI: ssl.cert_pem_to_der() for PEM→DER conversion (expensive: 2-5ms)
--   - Calls FFI: ocsp.validate_ocsp_response() for signature verify (expensive: 10-20ms)
--   - Per-request cache: stores parsed DER in ngx.ctx (Tier 1 optimization)
--   - Shared dict cache: stores parsed DER in ngx.shared (Tier 2 persistence)
--   - Per-request FFI cache: stores validation result (avoid duplicate validates)
--   - Metrics: records FFI duration in ngx.ctx.bw_ocsp_metrics
--
-- DESIGN NOTES:
--   - Two-tier DER parsing cache:
--     (1) Per-request (ngx.ctx) - survives single handshake [<0.1ms hit]
--     (2) Persistent (shared dict) - survives across handshakes [<0.1ms hit]
--     (3) Fresh parse - on cache miss, store in both tiers [2-5ms cost]
--   - Key innovation: multiple issuer candidates don't re-parse leaf (same DER)
--   - Shard issuer pin: if shard_issuer_spki set, candidate issuer SPKI must match
--   - Death-time validation: response must be fresh enough (nextUpdate - skew)
--   - Per-request FFI cache: same (response, issuer) pair not validated twice
--   - Performance: 15-20ms total (10-20ms FFI + 1-2ms parse + 0.1ms cache hits)
--   - Latency: CRITICAL PATH - must complete in ~50ms budget across all candidates
--
-- RELATED:
--   - try_staple() calls this in a loop with multiple issuers
--   - issuer_candidates() builds candidate list
--   - generation_tuple() used for cross-handshake sharing
--   - set_shared_validation_result() caches result for thundering-herd
--
-- EXAMPLE:
--   local leaf_pem = read_cert("leaf.pem")
--   local issuer_pem = read_cert("issuer.pem")
--   local ocsp_der = read_file("ocsp.der")
--   if validate(ngx.ocsp, ngx.ssl, ocsp_der, leaf_pem, issuer_pem, nil) then
--     log(ngx.INFO, "OCSP validation succeeded")
--   else
--     log(ngx.WARN, "OCSP validation failed")
--   end
--
-- ============================================================================
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
	-- ========================================================================
	-- Certificate Parsing with Two-Tier DER Cache
	-- ========================================================================
	-- Tier 1: Per-request cache (ngx.ctx) — survives for single handshake
	-- Tier 2: Persistent cache (shared dict) — survives across handshakes
	--
	-- Problem: cert_pem_to_der() is expensive (2-5ms)
	-- - Multi-issuer certs parse same leaf multiple times
	-- - Cold start handshakes parse without benefit of prior requests
	--
	-- Solution:
	-- 1. Per-request cache (Tier 1): Reuse within same handshake [DONE]
	-- 2. Persistent cache (Tier 2): Reuse across handshakes [NEW]
	--
	-- Generation binding: Invalidate when cert rotates (soft-recall)
	-- Prevents using stale DER after certificate renewal

	local der_chain, err
	local current_gen = current_ocsp_epoch()
	-- Key by SPKI fingerprints — never use "leaf|issuer" sentinels (collision when
	-- spki_fingerprint fails). Missing SPKI → skip both cache tiers.
	local leaf_spki = (type(leaf_pem) == "string" and leaf_pem ~= "") and spki_fingerprint(leaf_pem) or nil
	local issuer_spki = (type(issuer_pem) == "string" and issuer_pem ~= "") and spki_fingerprint(issuer_pem) or nil
	local der_cache_key = (leaf_spki and issuer_spki) and (leaf_spki .. "|" .. issuer_spki) or nil
	local persistent_cache_key = der_cache_key and ("OCSP:DER_CACHE:" .. der_cache_key) or nil

	-- ────────────────────────────────────────────────────────────────────
	-- Tier 1: Per-Request Cache (Handshake-scoped)
	-- ────────────────────────────────────────────────────────────────────
	local ctx = ngx.ctx
	if der_cache_key and ctx then
		if not ctx.bw_ocsp_der_cache then
			ctx.bw_ocsp_der_cache = {}
		end

		local cached_entry = ctx.bw_ocsp_der_cache[der_cache_key]
		if cached_entry and cached_entry.gen == current_gen then
			-- Tier 1 HIT: Reuse from current handshake [<0.1ms]
			der_chain = cached_entry.chain
			err = cached_entry.err
			if ngx.ctx and ngx.ctx.bw_ocsp_metrics then
				ngx.ctx.bw_ocsp_metrics.der_cache_tier1_hit = true
			end
		end
	end

	-- ────────────────────────────────────────────────────────────────────
	-- Tier 2: Persistent Cache (Shared Dict, across handshakes)
	-- ────────────────────────────────────────────────────────────────────
	-- Only try if Tier 1 missed and we have a real SPKI key
	if not der_chain and persistent_cache_key and ngx.shared and ngx.shared.bw_ocsp_validations then
		local cached_str = nil
		pcall(function()
			cached_str = ngx.shared.bw_ocsp_validations:get(persistent_cache_key)
		end)

		if cached_str then
			-- Parse cached entry format: "der_bytes|gen"
			-- (JSON would be overkill; use delimiter)
			-- Find last occurrence of "|" (Lua 5.1 has no rfind, iterate backwards)
			local gen_pos = nil
			for i = #cached_str, 1, -1 do
				if cached_str:sub(i, i) == "|" then
					gen_pos = i
					break
				end
			end
			if gen_pos then
				local cached_der = cached_str:sub(1, gen_pos - 1)
				-- current_ocsp_epoch() returns a string; tonumber() would never == it.
				local cached_gen = cached_str:sub(gen_pos + 1)

				if cached_gen ~= "" and cached_gen == tostring(current_gen) then
					-- Tier 2 HIT: Reuse from persistent cache [<0.1ms]
					der_chain = cached_der
					if ngx.ctx and ngx.ctx.bw_ocsp_metrics then
						ngx.ctx.bw_ocsp_metrics.der_cache_tier2_hit = true
					end
				end
			end
		end
	end

	-- ────────────────────────────────────────────────────────────────────
	-- Cache Miss: Parse Certificate (expensive 2-5ms operation)
	-- ────────────────────────────────────────────────────────────────────
	if not der_chain then
		-- Measure parsing latency
		local t_parse_start = ngx.hrtime and ngx.hrtime() or nil
		der_chain, err = ssl.cert_pem_to_der(leaf_pem .. "\n" .. issuer_pem)

		if t_parse_start and ngx.ctx then
			local elapsed_ns = ngx.hrtime() - t_parse_start
			local elapsed_ms = elapsed_ns / 1e6
			if not ngx.ctx.bw_ocsp_disk_io then
				ngx.ctx.bw_ocsp_disk_io = {}
			end
			ngx.ctx.bw_ocsp_disk_io.cert_parse_ms = elapsed_ms

			-- Log slow parsing (>5ms indicates issue)
			if elapsed_ms > 5 then
				log(ngx.WARN, "OCSP cert parse slow: " .. string.format("%.1f", elapsed_ms) .. "ms")
			end
		end

		if der_chain and der_cache_key then
			-- Store in Tier 1 cache (per-request)
			if ctx then
				if not ctx.bw_ocsp_der_cache then
					ctx.bw_ocsp_der_cache = {}
				end
				pcall(function()
					bounded_cache_set(
						ctx.bw_ocsp_der_cache,
						der_cache_key,
						{ chain = der_chain, err = err, gen = current_gen },
						16
					)
				end)
			end

			-- Store in Tier 2 cache (persistent, across handshakes)
			if persistent_cache_key and ngx.shared and ngx.shared.bw_ocsp_validations then
				pcall(function()
					local cache_value = der_chain .. "|" .. current_gen
					ngx.shared.bw_ocsp_validations:set(persistent_cache_key, cache_value, 3600)
				end)
			end
		end
	end
	if not der_chain then
		log(ngx.DEBUG, "OCSP cert_pem_to_der failed: " .. tostring(err))
		return false
	end
	-- ========================================================================
	-- OCSP Response FFI Validation (Most Expensive Operation: 10-20ms)
	-- ========================================================================
	-- This is the critical path bottleneck. Deferred to async job in production.
	-- TLS path uses cached result or skips if async status = "validated".
	--
	-- Optimization: Per-request FFI validation cache keyed by body SHA + issuer SPKI.
	-- - Cache hit: Same (response, issuer) pair in this handshake [<0.1ms]
	-- - FFI call: First validation of this (response, issuer) pair [10-20ms]
	--
	-- OpenSSL FFI via ngx.ocsp.validate_ocsp_response:
	-- - Verifies OCSP response signature against issuer public key
	-- - Validates time bounds (thisUpdate <= now <= nextUpdate)
	-- - Returns: ok_call (whether FFI executed), validate_ok (signature valid), next_update (unix timestamp)
	--
	-- Latency: ~10-20ms (crypto-heavy: ECDSA/RSA signature verification)
	-- This is why async validation defers it off-path (handshakes use cached result).

	-- Initialize per-request FFI validation cache
	if ngx.ctx and not ngx.ctx.bw_ffi_validation_cache then
		ngx.ctx.bw_ffi_validation_cache = {}
		ngx.ctx.bw_ffi_cache_hits = 0
		ngx.ctx.bw_ffi_cache_misses = 0
	end

	-- Death-time gate shared by live FFI and cache hits (validate returns boolean).
	local function death_time_ok(next_update)
		if type(next_update) == "number" and next_update > 0 then
			local death_time = next_update - OCSP_CLOCK_SKEW_SECONDS
			if ngx.time() >= death_time then
				log(
					ngx.DEBUG,
					"OCSP validate rejected: past death time "
						.. "(nextUpdate="
						.. next_update
						.. ", now="
						.. ngx.time()
						.. ", skew="
						.. OCSP_CLOCK_SKEW_SECONDS
						.. "s)"
				)
				return false
			end
			return true
		elseif next_update ~= nil then
			log(ngx.ERR, "OCSP validate refuse: nextUpdate unusable (type=" .. type(next_update) .. ")")
			return false
		end
		-- Legacy OpenResty: boolean-only FFI — outer meta expires must gate attach.
		log(ngx.WARN, "OCSP response missing nextUpdate (legacy OpenResty); relying on meta expires")
		return true
	end

	-- Per-request (response, issuer) cache only — keyed by full body SHA-256 +
	-- issuer SPKI hex. Do NOT reuse on "same leaf as last call": probe→staple can
	-- swap bodies mid-handshake; der_chain[1] is the leaf, not the issuer.
	local ffi_cache_key = nil
	local body_sha = (type(ocsp_der) == "string" and ocsp_der ~= "") and resp_binding(ocsp_der) or nil
	-- issuer_spki already computed above for DER cache key (hex); reuse it.
	if ngx.ctx and body_sha and issuer_spki then
		ffi_cache_key = body_sha .. ":" .. issuer_spki
		local cached = ngx.ctx.bw_ffi_validation_cache[ffi_cache_key]
		if cached then
			if ngx.ctx.bw_ffi_cache_hits then
				ngx.ctx.bw_ffi_cache_hits = ngx.ctx.bw_ffi_cache_hits + 1
			end
			-- Re-check death time; never return pcall's ok_call as the boolean result.
			return death_time_ok(cached.next_update)
		end
	end

	-- Track cache miss
	if ngx.ctx and ngx.ctx.bw_ffi_cache_misses then
		ngx.ctx.bw_ffi_cache_misses = ngx.ctx.bw_ffi_cache_misses + 1
	end

	local t_ffi_start = nil
	if ngx.hrtime then
		t_ffi_start = ngx.hrtime()
	end

	-- Newer OpenResty returns true, next_update; older returns true only.
	-- Some builds already reject past nextUpdate inside the FFI call.
	-- Wrap in pcall to catch unexpected FFI crashes.
	local ok_call, validate_ok, next_update = pcall(function()
		return ocsp.validate_ocsp_response(ocsp_der, der_chain)
	end)

	-- Record FFI latency for telemetry
	if t_ffi_start and ngx.ctx then
		local elapsed_ns = ngx.hrtime() - t_ffi_start
		local elapsed_ms = elapsed_ns / 1e6
		if not ngx.ctx.bw_ocsp_metrics then
			ngx.ctx.bw_ocsp_metrics = {}
		end
		ngx.ctx.bw_ocsp_metrics.ffi_validate_ms = elapsed_ms

		-- Log slow FFI calls (>20ms indicates issue or heavy load)
		if elapsed_ms > 20 then
			log(ngx.WARN, "OCSP FFI validation slow: " .. string.format("%.1f", elapsed_ms) .. "ms")
		end
	end

	-- Handle FFI crash or signature verification failure
	if not ok_call then
		log(ngx.ERR, "OCSP FFI crash: ngx.ocsp.validate_ocsp_response raised exception")
		return false
	end

	if validate_ok ~= true then
		-- Signature verification failed or OpenSSL error
		-- This is expected for revoked or tampered responses
		log(ngx.DEBUG, "OCSP signature validation failed: response_invalid")
		return false
	end

	-- ========================================================================
	-- Death Time Validation (Time Bound Check)
	-- ========================================================================
	-- Reject responses that are within OCSP_CLOCK_SKEW_SECONDS of expiry.
	-- Formula: nextUpdate - clock_skew <= now → REJECT
	if not death_time_ok(next_update) then
		return false
	end

	-- Cache only after signature + death-time pass (boolean validate result).
	if ngx.ctx and ffi_cache_key and type(ngx.ctx.bw_ffi_validation_cache) == "table" then
		ngx.ctx.bw_ffi_validation_cache[ffi_cache_key] = { next_update = next_update }
	end

	return true
end

-- force_ffi latch (per internalstore / subsystem):
-- When validate_budget aborts mid-issuer walk we KEEP the fleet allow-pin (so
-- canary trust still exists) but demote local L1 and stamp this key so the next
-- handshake cannot canary-skip attach an unfinished body.
-- Value is "der_sha256|soft_recall_gen|hmac_tag" (or "budget|hmac_tag"): soft-recall /
-- re-page flips gen → is_ffi_needed clears the stale latch. Readers split on LAST '|'.
-- All latches require an integrity tag.
-- Wall-clock TTL is only a safety cap (86400s); generation match is the real death clock.
-- mark on budget abort; clear on successful FFI/attach (incl. verified-L1 restock);
-- is_ffi_needed is also consulted on the verified-L1 shortcut so a warmer
-- re-verify cannot bypass the latch. Tag is fingerprint-salted (not epoch — see latch_token_tag).
-- ============================================================================
-- ffi_needed_key(fingerprint)
-- ============================================================================
-- PURPOSE:
--   Build cache key for force-FFI latch in shared dict.
--
-- PARAMETERS:
--   fingerprint (string): leaf SPKI fingerprint (64 hex chars)
--
-- RETURNS:
--   (string): shared dict key "TLS:SSL:ocsp_ffi_needed:{fingerprint}"
--
-- SIDE EFFECTS:
--   None (pure key generator, no state modification)
--
-- DESIGN NOTES:
--   - Key format: "TLS:SSL:ocsp_ffi_needed:{fp}"
--   - Used by mark_ffi_needed() to store latch
--   - Used by is_ffi_needed() to read latch
--   - No collision risk (distinct cert per fp)
--
-- RELATED:
--   - mark_ffi_needed() writes using this key
--   - is_ffi_needed() reads using this key
--   - latch_token_tag() generates integrity tag
--
-- ============================================================================
local function ffi_needed_key(fingerprint)
	return "TLS:SSL:ocsp_ffi_needed:" .. fingerprint
end

-- ============================================================================
-- latch_token_tag(token, fingerprint)
-- ============================================================================
-- PURPOSE:
--   Generate integrity tag for force-FFI latch (detect corruption).
--   SHA2-256 hash of token + fingerprint for collision resistance.
--
-- PARAMETERS:
--   token (string): generation token ("sha|gen" or "budget")
--   fingerprint (string): leaf SPKI fingerprint (64 hex chars)
--
-- RETURNS:
--   (string|nil): 8-byte (16-char hex) tag, nil on error
--
-- SIDE EFFECTS:
--   - Calls: resty.sha256 FFI for hashing
--   - Performance: ~0.5ms per hash computation
--
-- DESIGN NOTES:
--   - Fast integrity check: Not cryptographic auth, just corruption detection
--   - Salt: Fingerprint only (NOT epoch) to persist across epoch bumps
--   - Purpose: Detect accidental shared-dict corruption
--   - Format: SHA256(token|fingerprint) first 8 bytes as hex
--   - Epoch exclusion: Epoch bump must NOT flip tag (prevents latch re-open)
--   - Tag mismatch: Fails closed to FFI (safer than reopening canary-skip)
--
-- RELATED:
--   - mark_ffi_needed() uses this to tag the latch
--   - is_ffi_needed() validates tag before trusting latch
--
-- ============================================================================
-- Lightweight latch tag (not crypto / not HMAC). Salt is fingerprint-only:
-- global .ocsp_epoch must NOT be mixed in — an unrelated cert publish would
-- flip the tag, clear the latch, and re-open canary-skip after validate_budget.
-- Generation mismatch (stored token ≠ live sha|gen) is the intentional death clock.
local function latch_token_tag(token, fingerprint)
	if not token or not fingerprint then
		return nil
	end
	-- Use SHA2-256 for integrity checking (collision-resistant, cryptographically secure)
	-- The tag is used to detect accidental corruption of the latch value in shared dict
	local combined = token .. "|" .. fingerprint
	local sha256 = require("resty.sha256")
	local hasher = sha256:new()
	if not hasher then
		return nil
	end
	hasher:update(combined)
	return hasher:final():sub(1, 8)  -- Take first 16 hex chars (8 bytes) for compact tag
end

-- ============================================================================
-- ffi_needed_token(meta, resp, fingerprint)
-- ============================================================================
-- PURPOSE:
--   Build generation token for force-FFI latch (sha|gen format).
--   Returns nil if generation cannot be formed (incomplete metadata).
--
-- PARAMETERS:
--   meta (table|nil): ocsp.json metadata
--   resp (string): OCSP response DER bytes
--   fingerprint (string): leaf SPKI fingerprint
--
-- RETURNS:
--   (string|nil): token "{sha}|{gen}" where sha=DER_SHA256, gen=soft_recall_gen
--                 nil if generation_tuple cannot form valid tuple
--
-- SIDE EFFECTS:
--   - Calls: generation_tuple(), ligand_or_meta()
--   - No state modification
--
-- DESIGN NOTES:
--   - Format: "sha|gen" where sha=64-char hex, gen=number
--   - Fail-closed: Returns nil if any component invalid (type check)
--   - Used by: mark_ffi_needed() to stamp latch with current generation
--   - Used by: is_ffi_needed() to compare stored vs live token
--   - Soft-recall: Token changes when gen bumps (invalidates old latch)
--   - Performance: O(1) tuple generation (~0.1ms)
--
-- RELATED:
--   - generation_tuple() creates (sha, gen) pair
--   - mark_ffi_needed() uses token to build latch value
--   - is_ffi_needed() uses token to validate latch
--
-- ============================================================================
-- Compact generation identity for the latch value. nil when sha/gen incomplete
-- (type drift / missing body) — callers treat that as "honor any latch".
local function ffi_needed_token(meta, resp, fingerprint)
	local sha, gen = generation_tuple(ligand_or_meta(meta, fingerprint), resp)
	if type(sha) ~= "string" or #sha ~= 64 or type(gen) ~= "number" then
		return nil
	end
	return sha .. "|" .. tostring(gen)
end

-- ============================================================================
-- mark_ffi_needed(internalstore, fingerprint, meta, resp)
-- ============================================================================
-- PURPOSE:
--   Mark certificate as requiring FFI validation (after validate_budget abort).
--   Prevents canary-skip optimization on next handshake for this generation.
--
-- PARAMETERS:
--   internalstore (table): per-worker cache (ngx.shared.bw_ocsp_*)
--   fingerprint (string): leaf SPKI fingerprint (64 hex chars)
--   meta (table|nil): ocsp.json metadata (for generation tuple)
--   resp (string): OCSP response DER (for generation tuple)
--
-- RETURNS:
--   None (side effect only)
--
-- SIDE EFFECTS:
--   - Writes: ffi_needed_key(fingerprint) to shared dict with TTL 86400s
--   - Format: "{token}|{tag}" where token="sha|gen"|"budget", tag=integrity
--   - Performance: O(1) shared dict write (~0.1ms)
--
-- DESIGN NOTES:
--   - Trigger: Called when try_staple() hits validate_budget timeout
--   - Generation-bound: Token = sha|gen (soft-recall invalidates on cert change)
--   - Fallback: If token cannot form, uses "budget" (gen-less marker)
--   - Integrity: All latches tagged via latch_token_tag() (no corruption)
--   - TTL: 86400s (24 hours) for long-lived force_ffi requirement
--   - Fail-safe: pcall() wraps all writes (no throw on shared dict fail)
--
-- RELATED:
--   - try_staple() calls when validate_budget exhausted
--   - is_ffi_needed() reads and validates this latch
--   - clear_ffi_needed() removes latch after successful validate+attach
--   - ffi_needed_token() builds the generation token
--
-- ============================================================================
-- Stamp force_ffi after validate_budget. meta+resp bind the latch to this body gen.
-- Token is now signed with a fast integrity tag to prevent forgery via shared state.
-- All latches require a valid integrity tag (no legacy bypass).
local function mark_ffi_needed(internalstore, fingerprint, meta, resp)
	if not internalstore or type(fingerprint) ~= "string" or #fingerprint ~= 64 then
		return
	end
	-- Prefer gen-bound token; if soft_recall_gen type-drifts, still stamp a budget
	-- sentinel so canary-skip cannot resume after validate_budget (KEEP pin).
	local token = ffi_needed_token(meta, resp, fingerprint) or "budget"
	local tag = latch_token_tag(token, fingerprint)
	if not tag then
		return
	end
	pcall(function()
		-- Latch value: "token|tag" where token may contain '|' (sha|gen).
		-- Readers MUST split on the LAST '|'.
		internalstore:set(ffi_needed_key(fingerprint), token .. "|" .. tag, 86400)
	end)
end

-- ============================================================================
-- clear_ffi_needed(internalstore, fingerprint, meta, resp)
-- ============================================================================
-- PURPOSE:
--   Remove force-FFI latch after successful validation (CAS-safe deletion).
--   Only deletes if generation matches current (no TOCTOU race).
--
-- PARAMETERS:
--   internalstore (table): per-worker cache (ngx.shared.bw_ocsp_*)
--   fingerprint (string): leaf SPKI fingerprint (64 hex chars)
--   meta (table|nil): ocsp.json metadata (for generation tuple)
--   resp (string): OCSP response DER (for generation tuple)
--
-- RETURNS:
--   None (side effect only)
--
-- SIDE EFFECTS:
--   - Reads: current latch value from shared dict
--   - Writes: deletes latch only if token matches (CAS pattern)
--   - Performance: O(1) shared dict operations
--
-- DESIGN NOTES:
--   - CAS pattern: Read current token, delete only if matches expected
--   - Generation binding: Expects token from ffi_needed_token(meta, resp)
--   - Fail-safe: If meta/resp missing, token is nil (no delete, safe)
--   - No-op on mismatch: Never wipes a newer generation's latch
--   - TOCTOU race: Solved by comparing tokens before deleting
--   - Called by: try_staple() when did_ffi=true and validation succeeded
--   - Guards: Prevents re-opening canary-skip after validate_budget+FFI
--
-- RELATED:
--   - mark_ffi_needed() sets the latch
--   - is_ffi_needed() checks if latch set
--   - try_staple() calls this when did_ffi=true
--   - ffi_needed_token() generates expected token for CAS check
--
-- ============================================================================
-- Drop the latch after a successful validate+attach for THIS body generation.
-- CAS-delete only: never wipe a concurrent mark_ffi_needed for a newer gen.
-- meta+resp required to form the expected token; without them this is a no-op
-- (blind delete reopens the TOCTOU that gen-mismatch CAS fixed).
local function clear_ffi_needed(internalstore, fingerprint, meta, resp)
	if not internalstore or type(fingerprint) ~= "string" or #fingerprint ~= 64 then
		return
	end
	local expected = ffi_needed_token(meta, resp, fingerprint)
	pcall(function()
		local key = ffi_needed_key(fingerprint)
		local cur = internalstore:get(key)
		if type(cur) ~= "string" or cur == "" then
			return
		end
		local pipe_pos = nil
		for i = #cur, 1, -1 do
			if cur:sub(i, i) == "|" then
				pipe_pos = i
				break
			end
		end
		if not pipe_pos or pipe_pos == 1 then
			return
		end
		local stored_token = cur:sub(1, pipe_pos - 1)
		-- Match this handshake's gen, or gen-less budget after a completed FFI walk.
		if expected then
			if stored_token ~= expected and stored_token ~= "budget" then
				return
			end
		else
			return
		end
		if internalstore:get(key) == cur then
			internalstore:delete(key)
		end
	end)
end

-- ============================================================================
-- is_ffi_needed(internalstore, fingerprint, meta, resp)
-- ============================================================================
-- PURPOSE:
--   Check if FFI validation must run despite canary-skip optimization.
--   Validates force-FFI latch with generation binding and tag verification.
--
-- PARAMETERS:
--   internalstore (table): per-worker cache store
--   fingerprint (string): leaf SPKI fingerprint (64 hex chars)
--   meta (table): ocsp.json metadata for current generation
--   resp (string): OCSP response DER for current generation
--
-- RETURNS:
--   (boolean): true if FFI must run, false if canary-skip is safe
--
-- SIDE EFFECTS:
--   - Reads: ffi_needed_key(fingerprint) from internalstore
--   - Writes: CAS-deletes stale latch value on soft-recall/new-gen
--   - Logs: WARN on tag mismatch, NOTICE on corrupt/legacy formats
--
-- DESIGN NOTES:
--   - Format: "token|tag" where token="sha|gen"|"budget" and tag=HMAC
--   - Fail-closed: Corrupt/untagged latches force FFI (never skip)
--   - Tag mismatch: Epoch-era tags prevent re-opening canary-skip
--   - Budget token: Gen-less abort marker (honored until TTL/clear_ffi)
--   - Soft-recall: CAS-delete stale generation; don't wipe newer latches
--   - Canary skip safe when: token matches current gen AND tag matches
--   - Performance: O(1) latch check + tag verification (~0.1ms typical)
--
-- RELATED:
--   - mark_ffi_needed() sets the latch
--   - ffi_needed_key(), ffi_needed_token(), latch_token_tag() helpers
--   - try_staple() uses this to skip FFI when canary is trusted
--
-- ============================================================================
local function is_ffi_needed(internalstore, fingerprint, meta, resp)
	if not internalstore or type(fingerprint) ~= "string" or #fingerprint ~= 64 then
		return false
	end
	local v
	pcall(function()
		v = internalstore:get(ffi_needed_key(fingerprint))
	end)
	if v == nil or v == false then
		return false
	end
	-- Format: "token|tag" where token is "sha|gen" or "budget". Split on LAST '|'.
	if type(v) ~= "string" or #v == 0 then
		return false
	end
	local pipe_pos = nil
	for i = #v, 1, -1 do
		if v:sub(i, i) == "|" then
			pipe_pos = i
			break
		end
	end
	if not pipe_pos or pipe_pos == 1 or pipe_pos == #v then
		-- Corrupt / legacy untagged: fail closed to FFI (do not clear — TTL / clear_ffi).
		log(ngx.NOTICE, "OCSP latch untagged/corrupt: forcing FFI (fail closed)")
		return true
	end
	local stored_token = v:sub(1, pipe_pos - 1)
	local stored_tag = v:sub(pipe_pos + 1)
	local expected_tag = latch_token_tag(stored_token, fingerprint)
	if stored_tag ~= expected_tag then
		-- Do not clear: epoch-era tags or partial writes must not reopen canary-skip.
		log(ngx.WARN, "OCSP latch tag mismatch: forcing FFI (fail closed)")
		return true
	end
	if stored_token == "budget" then
		-- Gen-less budget abort: honor until clear_ffi / soft-recall clears key.
		return true
	end
	local token = ffi_needed_token(meta, resp, fingerprint)
	if not token then
		-- Live latch but this handshake cannot form gen — honor (fail closed to FFI).
		return true
	end
	if stored_token ~= token then
		-- Soft-recall / new page: this handshake does not need FFI for the new gen.
		-- CAS-delete only the value we read — never wipe a newer mark_ffi_needed
		-- that raced in between get and clear (would reopen canary-skip).
		pcall(function()
			local key = ffi_needed_key(fingerprint)
			local cur = internalstore:get(key)
			if cur == v then
				internalstore:delete(key)
			end
		end)
		return false
	end
	return true
end

-- try_staple: CertID → empty-issuer gate → (optional canary skip) → issuer validate → attach.
-- probe_only: path health only (no set_ocsp_status_resp). force_ffi: ignore canary
-- skip for one walk after validate_budget.
-- Returns:
--   true [, nil, did_ffi]        — probe ok or staple attached; did_ffi clears force_ffi
--   false, "certid_mismatch"     — DROP_ALLOW (serial/issuer poison only)
--   false, "certid_unreadable"   — KEEP (parse / missing leaf-or-resp)
--   false, "issuer_ambiguous"    — KEEP (multi SPKI under same DN)
--   false, "validate_budget"     — soft budget; caller demotes L1 + marks force_ffi
--   false, "issuer_unavailable"  — body present but zero accepted issuer PEMs (KEEP)
--   false, "validate_exhausted"  — every issuer candidate failed validate (body present)
--   false, <attach detail>       — intermediate MS / multi attach codes
--   false                        — generic attach/validate miss (optional stapling)

-- ============================================================================
-- certid_handshake_refuse_dialect(why)
-- ============================================================================
-- PURPOSE:
--   Map CertID validation failure reason to stapling decision dialect code.
--   Determines whether allow-pin should be dropped (certid_mismatch) or kept.
--
-- PARAMETERS:
--   why (string): reason from certid_matches_handshake_leaf() failure
--
-- RETURNS:
--   (string): dialect code ("certid_mismatch", "issuer_unavailable",
--             "issuer_ambiguous", or "certid_unreadable")
--
-- SIDE EFFECTS:
--   None (pure function, no state modification)
--
-- DESIGN NOTES:
--   - Serial/issuer mismatch → "certid_mismatch" (DROP allow-pin, poison detected)
--   - No issuer candidates → "issuer_unavailable" (KEEP pin, temporary unavail)
--   - Ambiguous issuer → "issuer_ambiguous" (KEEP pin, cannot resolve)
--   - Parse/unreadable → "certid_unreadable" (KEEP pin, transient error)
--   - Only DROP (certid_mismatch) prevents future staple attempts
--   - KEEP outcomes allow retries on subsequent connections
--
-- RELATED:
--   - certid_matches_handshake_leaf() generates the reason codes
--   - try_staple() calls this for decision conversion
--
-- ============================================================================
local function certid_handshake_refuse_dialect(why)
	if why == "serial_mismatch" or why == "issuer_mismatch" then
		return "certid_mismatch"
	end
	if why == "no_issuer_candidates" then
		return "issuer_unavailable"
	end
	if why == "issuer_ambiguous" then
		return "issuer_ambiguous"
	end
	return "certid_unreadable"
end

-- ============================================================================
-- try_staple(ocsp, ssl, resp, leaf_pem, issuers, shard_issuer_spki,
--            probe_only, meta, fingerprint, chain_blocks, force_ffi, mode)
-- ============================================================================
-- PURPOSE:
--   Core OCSP stapling logic: validate leaf + issuer, attach response if valid.
--   Implements two-tier validation (L1 cache + FFI), async status checks,
--   Must-Staple enforcement, and budget guards.
--
-- PARAMETERS:
--   ocsp (ffi): ngx.ocsp module for FFI calls
--   ssl (ffi): ngx.ssl module for FFI calls
--   resp (string): OCSP response DER bytes
--   leaf_pem (string): leaf certificate PEM
--   issuers (table): {issuer_pem, ...} candidates for validation
--   shard_issuer_spki (string): optional issuer SPKI pin from shard
--   probe_only (boolean): true = health check only (skip attachment)
--   meta (table): ocsp.json metadata
--   fingerprint (string): leaf SPKI fingerprint (64 hex chars)
--   chain_blocks (table): {leaf, intermediates...} for presentable chain
--   force_ffi (boolean): force FFI validation (skip L1 + canary optimizations)
--   mode (string): "open"|"staple_only"|"normal" (Must-Staple enforcement mode)
--
-- RETURNS:
--   (boolean, string, boolean): (success, decision_code, did_ffi)
--   - success: true if staple attached/proven (probe_only returns true if ready)
--   - decision_code: machine-readable outcome (ok, ok_partial, issuer_unavailable, ...)
--   - did_ffi: true if FFI validation actually ran (used to clear force_ffi latch)
--
-- SIDE EFFECTS:
--   - Reads/writes: L1 cache, async validation state, allow-pin bus
--   - Calls: issuer_candidates(), validate(), attach_ocsp_staple()
--   - FFI calls: ngx.ocsp.validate_ocsp_response (up to 10 issuer attempts)
--   - Shared state: cross-handshake validation result caching
--   - Metrics: records validation timing + cache hits
--
-- DESIGN NOTES:
--   - TIER 1 - L1 Cache: Shared-dict lookup with binding+gen verification (~0.1ms)
--   - TIER 2 - Metadata: Freshness, tombstone, peer-refuse checks (~1-5ms)
--   - TIER 3 - Skip-Validate: If mode=open or Must-Staple=false, attach speculatively
--   - TIER 4 - FFI Validation: Walk issuer list with budget guard (50ms hardcap)
--   - Budget Guard: Max 10 issuers + 50ms total time
--   - Early-Exit: Stop on first successful validation (don't test all issuers)
--   - Cross-Handshake: Reuse validation result (shared dict, 60s TTL)
--   - Force FFI: Set when validate_budget aborted; must finish FFI once
--   - Async Status: Check if scheduler already validated (skip TLS FFI)
--   - Must-Staple: Tri-state (true/false/nil); nil = enforce (fail-closed)
--   - Soft-Recall: Generation tuple prevents stale status after cert rotation
--
-- RELATED:
--   - issuer_candidates() builds issuer list
--   - validate() performs single FFI validation
--   - attach_ocsp_staple() attaches response to TLS conn
--   - ordered_leaves_for_handshake() ranks leaves (calls try_staple to probe)
--
-- ============================================================================
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
	chain_blocks,
	force_ffi,
	mode
)
	-- Empty issuers before CertID: no_issuer_candidates used to collapse to
	-- certid_mismatch (DROP). issuer_unavailable is KEEP.
	if type(issuers) ~= "table" or #issuers == 0 then
		return false, "issuer_unavailable", false
	end
	local ok_id, why = certid_matches_handshake_leaf(leaf_pem, resp, issuers)
	if not ok_id then
		local dialect = certid_handshake_refuse_dialect(why)
		log(ngx.ERR, "OCSP CertID refuse staple reason=" .. tostring(why) .. " dialect=" .. dialect)
		return false, dialect, false
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
			or detail == "issuer_unresolved_must_staple"
			or detail == "fingerprint_chain_unavailable"
		then
			return false, detail
		end
		return false
	end
	-- Third return: did_ffi — true only when crypto was proven this walk (local
	-- validate or shared pass). Callers clear force_ffi latch only when did_ffi.
	local function finish_attach(did_ffi)
		local ok, detail = set_resp()
		if ok then
			return true, nil, did_ffi and true or false
		end
		return false, detail, false
	end
	-- Trust scheduler canary (openssl CLI) for crypto verify when paged+ligand
	-- match AND live allow-pin names this generation (soft-fuse / pin revoke
	-- must not keep skip-validate alive on ligand bits alone).
	-- Async validation: defer validation to background job if already queued.
	-- If async validation already completed, skip (response already validated).
	-- Allows handshake to skip expensive crypto validation.
	-- Versioned responses: check if cached version matches current (not stale after cert rotation).
	local async_status = get_async_validation_status(fingerprint, meta, resp)
	-- if async_status == ASYNC_VALIDATION_DONE then
	-- 	-- Check if cached response version is current (not stale after cert rotation)
	-- 	if is_response_version_current(fingerprint) then
	-- 		log(ngx.DEBUG, "OCSP async validation already complete: skipping validation, attaching")
	-- 		return set_resp()
	-- 	else
	-- 		log(ngx.DEBUG, "OCSP response version stale: re-validating after cert rotation")
	-- 	end
	-- end
	-- Async FAILED is advisory: job issuer set can be thinner than handshake
	-- issuer_candidates. Fall through to local FFI (do not hard-abort for 3600s).
	if async_status == ASYNC_VALIDATION_FAILED then
		log(ngx.NOTICE, "OCSP async validation failed for this gen; forcing local FFI")
		force_ffi = true
	end

	-- SPKI-only provisional trust: validate against issuer key fingerprint alone (1ms).
	-- Full issuer cert validation deferred to async job.
	-- Only used in soft-fuse modes (open/staple_only); normal mode requires full validation.
	-- if shard_issuer_spki and type(shard_issuer_spki) == "string" then
	-- 	local issuer_spki_status = get_spki_validation_status(shard_issuer_spki)
	--
	-- 	if issuer_spki_status == SPKI_VALIDATION_CONFIRMED then
	-- 		log(ngx.DEBUG, "OCSP SPKI issuer cert already validated: skipping validation, attaching")
	-- 		return set_resp()
	-- 	elseif issuer_spki_status == SPKI_VALIDATION_FAILED then
	-- 		log(ngx.DEBUG, "OCSP SPKI issuer cert validation failed: refusing staple")
	-- 		return false, "spki_validation_failed"
	-- 	elseif issuer_spki_status == SPKI_VALIDATION_PROVISIONAL then
	-- 		-- SPKI matched, full cert validation pending in async job
	-- 		-- Safe to use in soft-fuse modes (open/staple_only)
	-- 		local mode = ocsp_staple_mode()
	-- 		if mode == "open" or mode == "staple_only" then
	-- 			log(ngx.DEBUG, "OCSP SPKI provisional trust: issuer SPKI matched, using provisional (async job will confirm)")
	-- 			return set_resp()
	-- 		end
	-- 		-- In normal mode, still requires full validation even if SPKI matches
	-- 		log(ngx.DEBUG, "OCSP SPKI provisional (normal mode): deferring to full validation")
	-- 	end
	-- end

	-- force_ffi: prior validate_budget demoted L1 but KEEP pin — finish one FFI walk.
	-- Must run before should_skip_validation / canary so mode=open cannot bypass the latch.
	if force_ffi and canary_paged_body_ok(meta, fingerprint, resp) then
		log(ngx.NOTICE, "OCSP force FFI after validate_budget; ignoring canary/skip once")
	end
	-- Skip ngx.ocsp.validate when mode=open, or when Must-Staple is proven false.
	-- Unknown (nil) and true must still validate (fail closed). Pass mode from
	-- staple_one_leaf — never call ocsp_staple_mode() without store+SNI here.
	-- If the module failed to load, do not skip (fail closed → validate).
	local ms_module = get_must_staple_module()
	if not force_ffi and ms_module and ms_module.should_skip_validation(leaf_pem, fingerprint, mode) then
		log(ngx.DEBUG, "OCSP: skipping validation, attaching speculatively")
		-- Queue async validation for future handshakes (even though this one doesn't need it)
		if not async_status then
			mark_async_validation_pending(fingerprint, meta, resp)
		end
		return finish_attach(false)
	end
	if canary_paged_body_ok(meta, fingerprint, resp) and not force_ffi then
		log(ngx.DEBUG, "OCSP trusting canary-paged body; skipping ngx.ocsp.validate_ocsp_response")
		-- Queue async validation to confirm canary was correct
		if not async_status then
			mark_async_validation_pending(fingerprint, meta, resp)
		end
		return finish_attach(false)
	end
	-- Deduplicate issuers by SPKI to avoid redundant validate() calls on duplicate certs.
	-- Malformed cert bundles may include the same issuer multiple times; skip them.
	local seen_spkis = {}
	local unique_issuers = {}
	for _, issuer_pem in ipairs(issuers) do
		if issuer_pem and issuer_pem ~= "" then
			local issuer_spki = spki_fingerprint(issuer_pem)
			if issuer_spki and not seen_spkis[issuer_spki] then
				seen_spkis[issuer_spki] = true
				unique_issuers[#unique_issuers + 1] = issuer_pem
			end
		end
	end
	-- Replace issuers with deduplicated list
	issuers = unique_issuers
	if #issuers == 0 then
		return false, "issuer_unavailable", false
	end
	-- Deterministic issuer shuffle via local LCG — never math.randomseed (global PRNG).
	if #issuers > 1 and fingerprint and type(fingerprint) == "string" then
		local state = tonumber(fingerprint:sub(1, 8), 16) or 1
		state = (state + (tonumber(current_ocsp_epoch()) or 0)) % 2147483647
		if state == 0 then
			state = 1
		end
		local function lcg_next()
			state = (state * 1103515245 + 12345) % 2147483648
			return state
		end
		for i = #issuers, 2, -1 do
			local j = (lcg_next() % i) + 1
			issuers[i], issuers[j] = issuers[j], issuers[i]
		end
	end
	-- Cross-handshake validation state sharing (thundering-herd protection).
	-- Keyed by fingerprint + body generation so soft-recall cannot reuse a stale pass.
	-- Cold path returns immediately; only in_flight waits (max 100ms).
	local owned_shared_lock = false
	if fingerprint and type(fingerprint) == "string" and #fingerprint == 64 then
		local shared_result = get_shared_validation_result(fingerprint, meta, resp, 100)
		if shared_result ~= nil then
			if shared_result then
				log(ngx.DEBUG, "OCSP validation result reused from concurrent handshake (hit)")
				return finish_attach(true)
			else
				log(ngx.DEBUG, "OCSP validation result reused from concurrent handshake (fail)")
				return false, "validate_exhausted", false
			end
		end
		-- Claim lock; if another worker won the race, wait once more for their result.
		if not set_shared_validation_in_flight(fingerprint, meta, resp) then
			shared_result = get_shared_validation_result(fingerprint, meta, resp, 100)
			if shared_result ~= nil then
				if shared_result then
					return finish_attach(true)
				end
				return false, "validate_exhausted", false
			end
		else
			owned_shared_lock = true
			log(ngx.DEBUG, "OCSP validation lock acquired for this handshake (will validate)")
		end
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
			-- Do NOT store pass/fail (budget is transient) — but release in_flight so
			-- peers are not stuck waiting/spinning for up to 60s.
			if owned_shared_lock then
				clear_shared_validation_in_flight(fingerprint, meta, resp)
			end
			return false, "validate_budget", false
		end
		-- Early-exit optimization: stop on first successful validation (don't test all 4 issuers).
		-- This is load-bearing for latency: validate() is 5-20ms per issuer, so early-exit
		-- can save 10-60ms in common dual-issuer scenarios.
		if validate(ocsp, ssl, resp, leaf_pem, issuers[i], shard_issuer_spki) then
			-- Attach/path gate first — do not publish shared "pass" if set_resp fails.
			local ok_resp, resp_detail = set_resp()
			if ok_resp then
				if fingerprint and type(fingerprint) == "string" and #fingerprint == 64 then
					set_shared_validation_result(fingerprint, meta, resp, true)
					mark_async_validation_done(fingerprint, meta, resp)
				end
				return true, nil, true
			end
			if owned_shared_lock then
				clear_shared_validation_in_flight(fingerprint, meta, resp)
			end
			return ok_resp, resp_detail, false
		end
	end
	-- Body present; every issuer candidate failed crypto validate (not missing DER).
	-- Do not share "fail"; only the lock owner may clear in_flight (non-owners
	-- must not yank a peer's lock after wait timeout).
	if owned_shared_lock then
		set_shared_validation_result(fingerprint, meta, resp, false)
	end
	return false, "validate_exhausted", false
end

-- Audit which leaf was stapled — kind + SPKI + der_sha256 + epoch this node served.
-- Multi-staple NULL slots are legal omissions: log staple_decision=ok_partial (not hollow ok).
-- ============================================================================
-- log_ocsp_stapled(server_name, kind, fp, resp)
-- ============================================================================
-- PURPOSE:
--   Audit successful OCSP staple attachment to TLS connection.
--   Logs decision code ("ok" or "ok_partial" for multi-staple NULL slots).
--
-- PARAMETERS:
--   server_name (string): SNI hostname for audit trail
--   kind (string): certificate key type ("rsa"|"ec"|"ed")
--   fp (string): leaf SPKI fingerprint (64-char hex)
--   resp (string): OCSP response DER bytes
--
-- RETURNS:
--   None (logging side effect only)
--
-- SIDE EFFECTS:
--   - Calls: resp_binding() to compute DER SHA256, current_ocsp_epoch()
--   - Calls: note_connection_staple() to record staple state
--   - Calls: format_staple_decision() to format audit log
--   - Logs: INFO level with tag="OCSP_STAPLED"
--   - Multi-staple: Detects NULL slots from ngx.ctx metrics
--
-- DESIGN NOTES:
--   - Decision "ok": all requested slots stapled
--   - Decision "ok_partial": some NULL slots remain (multi-staple limitation)
--   - Fingerprint: validates 64-char format; uses "-" if missing
--   - Worker ID: captured for load-balancing diagnostics
--   - DER SHA256: included for auditing/debugging (identifies cached response)
--   - Epoch: current OCSP generation for cache coherency
--   - Multi-staple: NULL slots logged when OpenSSL multi-staple has limits
--   - Performance: O(1), <1ms
--
-- RELATED:
--   - log_ocsp_staple_skip() logs skipped/refused staples
--   - try_staple() calls this on successful attachment
--   - staple_one_leaf() calls this for disk OCSP responses
--
-- ============================================================================
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

-- ============================================================================
-- log_ocsp_staple_skip(kind, fp, reason, server_name)
-- ============================================================================
-- PURPOSE:
--   Audit skipped or refused OCSP staple with machine-readable decision code.
--   Logs reason for each certificate not stapled (dual-cert, multi-staple, etc.).
--
-- PARAMETERS:
--   kind (string): certificate key type ("rsa"|"ec"|"ed")
--   fp (string): leaf SPKI fingerprint (64-char hex or partial)
--   reason (string): machine-readable skip reason (decision code)
--   server_name (string): SNI hostname for audit trail
--
-- RETURNS:
--   None (logging side effect only)
--
-- SIDE EFFECTS:
--   - Calls: format_staple_decision() to format audit log
--   - Logs: NOTICE level with tag="OCSP_STAPLE_SKIP"
--   - Performance: O(1), <1ms
--
-- DESIGN NOTES:
--   - Reason codes: machine-readable (single_slot_rsa_prefer, validate_budget, etc.)
--   - Fingerprint: accepts 64-char hex or partial (for partial extraction)
--   - Used for: dual-cert sibling exclusion, validation failures, multi-staple limits
--   - Audit trail: identifies why each cert wasn't stapled
--   - Reason default: "skip_slot" if reason is nil/falsy
--   - Fingerprint handling: partial FP ok for dual-cert logging (16 chars + "...")
--
-- RELATED:
--   - log_ocsp_stapled() logs successful staples
--   - log_skipped_sibling_leaves() calls this for dual-cert siblings
--   - try_staple() may log skips via this
--   - Decision codes defined in ocsp_common.lua
--
-- ============================================================================
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

-- ============================================================================
-- ordered_leaves_for_handshake(leaves, sigalgs_ext, prefer_kind)
-- ============================================================================
-- PURPOSE:
--   Rank certificate leaves in preference order for dual-cert TLS handshake.
--   Respects ClientHello signature_algorithms and key type preference.
--
-- PARAMETERS:
--   leaves (table): array of leaf certificates {pem, fp, must_staple, ...}
--   sigalgs_ext (string|nil): ClientHello signature_algorithms extension (raw bytes)
--   prefer_kind (string|nil): "rsa"|"ec"|"ed" preference override
--
-- RETURNS:
--   (table): ordered array of compatible leaves (each appears once)
--           empty if no suitable leaves
--
-- SIDE EFFECTS:
--   - Calls: cert_sig_profile() for each leaf (expensive PEM parsing)
--   - Caches: sig_profile result on each leaf for reuse
--   - Performance: O(n*m) where n=leaves, m=sigalgs bytes
--
-- DESIGN NOTES:
--   - Ranking: signature_algorithms aware, then must_staple health, then key kind
--   - Signature validation: Only schemes matching ClientHello advertised algos
--   - Dual-cert: Selects RSA or ECDSA based on ClientHello preference
--   - Must-Staple: Demotes leaves that fail path/probe health checks
--   - Deduplication: Each leaf appears at most once (seen set)
--   - Profile caching: Expensive cert_sig_profile() result cached on leaf
--   - Typical OpenSSL default: ECDSA before RSA if both available
--   - Fallback: Returns all leaves if no sigalgs match
--
-- RELATED:
--   - select_leaf_for_handshake() returns first (best) result
--   - _M.set_certs_from_pem() uses this to rank for installation
--   - cert_sig_profile() extracts algorithm from PEM
--
-- ============================================================================
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

	-- Cache cert_sig_profile() results to avoid expensive PEM parsing per leaf.
	-- Store on leaf object for reuse across functions.
	local profiles = {}
	for i, leaf in ipairs(leaves) do
		local pem = leaf
		if type(leaf) == "table" then
			pem = leaf.pem or leaf.ocsp_cert or leaf.cert_pem
			-- Check if profile already cached on leaf object
			if leaf.sig_profile then
				profiles[i] = leaf.sig_profile
			else
				profiles[i] = cert_sig_profile(pem)
				leaf.sig_profile = profiles[i] -- Cache on leaf for future calls
			end
		else
			profiles[i] = cert_sig_profile(pem)
		end
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
			-- TLS 1.2 ECDSA schemes name only the hash, not the curve; technically usable across curves.
			-- But only as fallback after exact matches, not as primary strategy to avoid curve mismatches.
			if matched then
				return ordered
			end
			-- Fallback for TLS 1.2: accept any EC curve if no exact matches found.
			if offered_ecdsa then
				for li = 1, #leaves do
					if profiles[li].kind == "ec" and not seen[li] then
						add(li)
					end
				end
				if #ordered > 0 then
					return ordered
				end
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

-- ============================================================================
-- select_leaf_for_handshake(leaves, sigalgs_ext, prefer_kind)
-- ============================================================================
-- PURPOSE:
--   Select single leaf from candidate list for dual-cert TLS handshake.
--   Returns best candidate by ClientHello signature_algorithms + key preference.
--
-- PARAMETERS:
--   leaves (table): array of leaf certificates {pem, fp, must_staple, ...}
--   sigalgs_ext (string|nil): ClientHello signature_algorithms extension bytes
--   prefer_kind (string|nil): "rsa"|"ec"|"ed" preference override
--
-- RETURNS:
--   (table|nil): first (best) leaf from ordered list
--                nil if no suitable leaves after ranking
--
-- SIDE EFFECTS:
--   - Calls: ordered_leaves_for_handshake() for ranking
--   - No state modification
--
-- DESIGN NOTES:
--   - Wrapper around ordered_leaves_for_handshake() taking first result
--   - Respects: ClientHello sigalgs (curve matching), Must-Staple health
--   - Typical OpenSSL default: ECDSA before RSA (if both available)
--   - Ranking: curve-aware sigalgs → Must-Staple health → key kind preference
--   - Performance: O(n) leaf ranking, typical <1ms for dual-cert
--
-- RELATED:
--   - ordered_leaves_for_handshake() does full ranking
--   - _M.set_certs_from_pem() uses this to pick primary leaf
--
-- ============================================================================
local function select_leaf_for_handshake(leaves, sigalgs_ext, prefer_kind)
	local ordered = ordered_leaves_for_handshake(leaves, sigalgs_ext, prefer_kind)
	return ordered[1]
end

-- ============================================================================
-- leaf_pem_of(leaf)
-- ============================================================================
-- PURPOSE:
--   Extract PEM from leaf (flexible: string or table with pem field).
--   Supports multiple field names for compatibility across modules.
--
-- PARAMETERS:
--   leaf (string|table|any): leaf representation
--     - string: PEM directly (returned as-is)
--     - table: extract from .pem, .ocsp_cert, or .cert_pem field
--     - other: nil
--
-- RETURNS:
--   (string|nil): PEM content if found, nil otherwise
--
-- SIDE EFFECTS:
--   None (pure function, no state modification)
--
-- DESIGN NOTES:
--   - Flexible interface: handles raw PEM or leaf table objects
--   - Field precedence: .pem > .ocsp_cert > .cert_pem (first found used)
--   - Defensive: returns nil for invalid types (no throw)
--   - Performance: O(1) table lookup
--
-- RELATED:
--   - leaf_fp_of() extract fingerprint from same leaf format
--   - _M.set_certs_from_pem() uses this throughout
--
-- ============================================================================
local function leaf_pem_of(leaf)
	if type(leaf) == "string" then
		return leaf
	end
	if type(leaf) == "table" then
		return leaf.pem or leaf.ocsp_cert or leaf.cert_pem
	end
	return nil
end

-- ============================================================================
-- leaf_fp_of(leaf)
-- ============================================================================
-- PURPOSE:
--   Extract or compute SPKI fingerprint from leaf table.
--   Tries cached fields first, then computes from PEM on miss.
--
-- PARAMETERS:
--   leaf (table|any): leaf object with optional .fp or .ocsp_fp_hint field
--
-- RETURNS:
--   (string|nil): 64-char hex SPKI fingerprint, nil if unable to extract/compute
--
-- SIDE EFFECTS:
--   - Calls: spki_fingerprint(pem) to compute if cached field missing
--   - FFI calls: OpenSSL hash for SHA256 computation (expensive: 2-5ms)
--
-- DESIGN NOTES:
--   - Cache lookup first: .fp (primary) → .ocsp_fp_hint (fallback)
--   - Cache must be 64-char hex (validates length)
--   - On cache miss: extract PEM from leaf, compute fingerprint
--   - Compute fallback: only when cached field absent/invalid
--   - Performance: O(1) for cached FP, O(len(PEM)) for computation (~2-5ms)
--   - Returns nil if: not a table, no cached FP, PEM unreadable
--
-- RELATED:
--   - leaf_pem_of() extracts PEM from same leaf
--   - spki_fingerprint() computes hash from PEM
--   - issuer_candidates() uses this for PIN enforcement
--
-- ============================================================================
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

-- ============================================================================
-- log_skipped_sibling_leaves(leaves, chosen, server_name)
-- ============================================================================
-- PURPOSE:
--   Log all sibling leaves not presented in TLS Certificate message.
--   Dual-cert: one leaf installed (RSA or ECDSA), siblings logged as skipped.
--
-- PARAMETERS:
--   leaves (table): array of all candidate leaves
--   chosen (table): the leaf that was selected for installation
--   server_name (string): SNI hostname for audit logging
--
-- RETURNS:
--   None (logging side effect only)
--
-- SIDE EFFECTS:
--   - Calls: cert_pubkey_kind() to determine algorithm of each leaf
--   - Calls: leaf_pem_of(), leaf_fp_of() for leaf data extraction
--   - Calls: log_ocsp_staple_skip() to audit each skipped sibling
--   - Logs: one entry per sibling with skip reason (ERR level)
--
-- DESIGN NOTES:
--   - Reason code: "single_slot_ecdsa_prefer"|"single_slot_rsa_prefer"
--   - Reason shows which algorithm was selected instead
--   - Only logs for leaves that differ from chosen (siblings)
--   - Fingerprint extracted: cache first, then computed from PEM
--   - Key kind used: RSA vs ECDSA (determines skip reason string)
--   - Audit trail: shows why dual-cert path selected one over other
--
-- RELATED:
--   - log_ocsp_staple_skip() records the skip event
--   - leaf_pem_of(), leaf_fp_of() extract leaf data
--   - cert_pubkey_kind() determines RSA vs ECDSA
--   - _M.set_certs_from_pem() calls this during leaf selection
--
-- ============================================================================
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

-- ============================================================================
-- _M.set_certs_from_pem(cert_pem, key_pem, internalstore, server_name,
--                       prefer_kind)
-- ============================================================================
-- PURPOSE:
--   Public API: Install certificate and select best leaf for TLS handshake.
--   Handles dual-cert (RSA+ECDSA) ranking, Must-Staple health checks, and
--   OCSP staple blocking with soft-fuse capability.
--
-- PARAMETERS:
--   cert_pem (string): full certificate chain PEM (leaf + intermediates)
--   key_pem (string): private key(s) PEM (must match leaf SPKI)
--   internalstore (table): per-worker cache (ngx.shared.bw_ocsp_*)
--   server_name (string): SNI hostname for config/logging
--   prefer_kind (string|nil): "rsa"|"ec"|"ed" preference override
--
-- RETURNS:
--   (true, blocks, leaf_fp): success
--     blocks = issuer-linked chain table (leaf + intermediates)
--     leaf_fp = installed leaf SPKI fingerprint (64 hex chars)
--   (false, error_msg): failure (cert parse, key mismatch, etc.)
--
-- SIDE EFFECTS:
--   - Calls: ngx.ssl.set_cert(), ngx.ssl.set_priv_key() (installs cert)
--   - Calls: _M.probe() for Must-Staple health ranking
--   - Calls: _M.staple() after selected leaf installed
--   - Caches: issuer-linked blocks with ocsp_path_sealed flag
--   - Logs: Single leaf selected + skipped siblings (dual-cert audit)
--   - Clears: Prior staple before cert swap (TOCTOU safe)
--
-- DESIGN NOTES:
--   - Dual-cert: Ranks RSA + ECDSA by Must-Staple health + ClientHello preference
--   - Ranking: ClientHello sigalgs → must-staple probe → issuer_path health
--   - Selection: Tries best candidate, falls back to siblings on soft-fuse
--   - Soft-fuse: Mode "open"/"staple_only" allows unstapled fallback
--   - Re-probe: TOCTOU check before final installation (gen may change)
--   - Path sealing: Sets ocsp_path_sealed to avoid re-link (preserves unresolved_ms)
--   - Fallback: If best fails, tries next sibling (ranked order)
--   - Performance: ~50-100ms (probes each dual-cert candidate)
--   - Must-Staple: Probes must pass before install (unless soft-fuse mode)
--
-- RELATED:
--   - _M.probe() health-checks for dual-cert ranking
--   - _M.staple() attaches OCSP after installation
--   - ordered_leaves_for_handshake() ranks by signature_algorithms
--   - issuer_linked_chain_blocks() builds issuer chain
--
-- EXAMPLE:
--   local ocsp = require("bunkerweb.ocsp")
--   local ok, blocks, leaf_fp = ocsp.set_certs_from_pem(
--     full_chain_pem, key_pem, ngx.shared.bw_ocsp, "example.com"
--   )
--   if ok then
--     local staple_ok = ocsp.staple(ngx.shared.bw_ocsp, "example.com", blocks)
--   end
--
-- ============================================================================
-- Install the single leaf this handshake will present (dual-cert: one of RSA/ECDSA).
-- prefer_kind / ClientHello signature_algorithms select which leaf; only that leaf is
-- set_cert'd so the OCSP staple cannot land on a different CertificateEntry.
--
-- Selection:
--   1) Build ClientHello-ordered candidates (curve-aware sigalgs).
--   2) Probe path health + Must-Staple for each (rank probes skip L1 drop).
--   3) Rank survivors by fewest issuer_path_null_slots, then ClientHello order.
--   4) install_one with re-probe (TOCTOU); try next sibling before soft fuse.
-- Soft fuse (OCSP_STAPLE_MODE=open|staple_only): install a path-ready survivor
-- (ranked best or first path_ready) unstapled when Must-Staple probes fail —
-- never load a leaf that failed issuer_path_health, never revoke the allow-pin,
-- never seal ocsp_path_sealed (later staple must re-presentable). Logs full fp
-- once (bw_ocsp_soft_fuse_logged) so soften_must_staple does not double-ERR.
--
-- install_one: clears connection staple before set_cert; on set_priv_key fail runs
-- clear_certs so a torn CertificateEntry cannot linger for soft-fuse/sibling retry.
-- Proven install seals blocks.ocsp_path_sealed so staple/probe skip re-presentable
-- (keeps unresolved_must_staple). Rank probes wrap bw_ocsp_skip_l1_drop in pcall.
-- Rearms the L1 warmer on entry.
--
-- Returns: true, chain_blocks, leaf_fp  OR  false, err_msg [, detail]
-- On success the second value is the issuer-linked blocks table (array of PEMs plus
-- optional unresolved_must_staple). Callers may pass it to staple/probe/attach;
-- table.concat is only for set_cert. Named fields survive — PEM round-trip does not.
function _M.set_certs_from_pem(cert_pem, key_pem, internalstore, server_name, prefer_kind)
	maybe_rearm_l1_warmer()
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

	-- Compute Must-Staple once per leaf upfront; reuse throughout selection phase.
	local ms_module = get_must_staple_module()
	if ms_module then
		ms_module.annotate_leaves(leaves)
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

	local function install_one(leaf, probe_must, seal_path)
		-- Parse + set_cert/set_priv_key for one dual-cert leaf.
		-- probe_must=true (normal/staple_only install): issuer_path + live probe first;
		--   skip-leaf demotion must NOT write the peer-refuse bus.
		-- probe_must=false (soft fuse / open): load unstapled without demotion.
		-- seal_path=false (soft fuse): do NOT set ocsp_path_sealed — later staple must
		--   re-presentable so an unprobed bag cannot hide path drift.
		-- Issuer-linked blocks keep unresolved_must_staple; PEM concat alone would drop it.
		local blocks = issuer_linked_chain_blocks(leaf.pem, intermediates)
		local chain_pem = chain_pem_from_blocks(blocks)
		local leaf_must = false
		if probe_must then
			-- Use pre-computed Must-Staple from leaf annotation phase.
			-- Fail closed: unknown (nil) enforces Must-Staple like staple()/probe().
			leaf_must = (leaf.must_staple ~= false)
			if leaf_must and mode == "open" then
				leaf_must = false
			end
		end
		-- Bind staple health to this leaf's issuer-linked intermediates (not leaf shard alone).
		-- Soft-fuse install (probe_must=false) skips demotion so a path-ready
		-- survivor can load unstapled (caller never passes a path-failed leaf).
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
						fp = (type(leaf.fp) == "string" and #leaf.fp == 64) and leaf.fp
							or (tostring(leaf.fp and leaf.fp:sub(1, 16) or "nil") .. "..."),
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
						fp = (type(leaf.fp) == "string" and #leaf.fp == 64) and leaf.fp
							or (tostring(leaf.fp and leaf.fp:sub(1, 16) or "nil") .. "..."),
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
		-- Drop any prior leaf/multi staple before swapping CertificateEntrys.
		pcall(clear_connection_staple)
		local ok_cert, err_cert = ssl.set_cert(parsed_cert)
		if not ok_cert then
			return false, "set_cert failed: " .. tostring(err_cert)
		end
		local ok_key, err_key = ssl.set_priv_key(parsed_key)
		if not ok_key then
			-- Tear down the half-written CertificateEntry so soft-fuse / sibling
			-- install does not inherit a cert without a matching privkey.
			pcall(function()
				if ssl.clear_certs then
					ssl.clear_certs()
				end
			end)
			pcall(clear_connection_staple)
			return false, "set_priv_key failed: " .. tostring(err_key)
		end
		-- Seal probed/healthy installs only (keeps unresolved_must_staple across staple).
		if seal_path ~= false then
			blocks.ocsp_path_sealed = true
		end
		-- Return blocks so staple/attach see the same CertificateEntrys + unresolved flag.
		return true, blocks, leaf.fp
	end

	-- Collect ClientHello-compatible leaves that pass Must-Staple / path health, then
	-- prefer the sibling whose issuer path is most completely stapled (fewest NULL slots).
	-- First match alone would stick on ok_partial while a fully stapled sibling exists.
	local last_err, last_detail
	local healthy = {}
	-- Leaves that passed issuer_path (even if Must-Staple probe failed). Soft fuse may
	-- load these unstapled; never soft-fuse a leaf that failed path health.
	local path_ready = {}
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
					fp = (type(leaf.fp) == "string" and #leaf.fp == 64) and leaf.fp
						or (tostring(leaf.fp and leaf.fp:sub(1, 16) or "nil") .. "..."),
				})
			)
			last_err, last_detail = "must_staple", path_detail or "unmet"
		else
			path_ready[#path_ready + 1] = leaf
			-- Use pre-computed Must-Staple from leaf annotation phase.
			local leaf_must = (leaf.must_staple ~= false)
			if leaf_must and mode == "open" then
				leaf_must = false
			end
			local leaf_ok = true
			local leaf_detail
			if leaf_must and internalstore and mode ~= "open" then
				-- Rank probes must not drop_cache sibling L1 (leaf may still be needed later).
				-- pcall so a probe throw still restores bw_ocsp_skip_l1_drop.
				local prev_skip = ngx.ctx and ngx.ctx.bw_ocsp_skip_l1_drop
				if ngx.ctx then
					ngx.ctx.bw_ocsp_skip_l1_drop = true
				end
				local ok_p, probe_ok, probe_reason, probe_detail = pcall(function()
					return _M.probe(internalstore, server_name, blocks, leaf.fp, false)
				end)
				if ngx.ctx then
					ngx.ctx.bw_ocsp_skip_l1_drop = prev_skip
				end
				if not ok_p then
					leaf_ok = false
					leaf_detail = "probe_failed"
					log(
						ngx.ERR,
						format_staple_decision(leaf_detail, {
							tag = "OCSP_MUST_STAPLE_REFUSE",
							action = "skip_leaf",
							mode = mode,
							detail = tostring(probe_ok),
							fp = (type(leaf.fp) == "string" and #leaf.fp == 64) and leaf.fp
								or (tostring(leaf.fp and leaf.fp:sub(1, 16) or "nil") .. "..."),
						})
					)
					last_err, last_detail = "must_staple", leaf_detail
				elseif not probe_ok then
					leaf_ok = false
					-- Skip-leaf demotion never writes the peer bus (see install_one).
					leaf_detail = probe_detail or probe_reason or "probe_failed"
					log(
						ngx.ERR,
						format_staple_decision(leaf_detail, {
							tag = "OCSP_MUST_STAPLE_REFUSE",
							action = "skip_leaf",
							mode = mode,
							fp = (type(leaf.fp) == "string" and #leaf.fp == 64) and leaf.fp
								or (tostring(leaf.fp and leaf.fp:sub(1, 16) or "nil") .. "..."),
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
	local best
	if #healthy > 0 then
		-- Prefer fewest NULL slots (path completeness); ClientHello order (ci) breaks ties.
		table.sort(healthy, function(a, b)
			if a.nulls ~= b.nulls then
				return a.nulls < b.nulls
			end
			return a.ci < b.ci
		end)
		best = healthy[1]
		-- Re-probe on install for normal/staple_only (TOCTOU); try next sibling before soft fuse.
		for _, h in ipairs(healthy) do
			local ok_inst, a, b = install_one(h.leaf, mode ~= "open", true)
			if ok_inst then
				-- best = h
				if h ~= healthy[1] or h.ci > 1 then
					log(
						ngx.NOTICE,
						format_staple_decision("skip_slot", {
							tag = "OCSP_STAPLE_HEALTH_FALLBACK",
							detail = "path_completeness",
							null_slots = h.nulls,
							fp = (type(h.leaf.fp) == "string" and #h.leaf.fp == 64) and h.leaf.fp
								or (tostring(h.leaf.fp and h.leaf.fp:sub(1, 16) or "nil") .. "..."),
							server_name = server_name or "nil",
						})
					)
				end
				log_skipped_sibling_leaves(leaves, h.leaf, server_name)
				return true, a, b
			end
			last_err, last_detail = a, b
		end
	end
	if last_err == "must_staple" and (mode == "open" or mode == "staple_only") then
		-- Soft fuse: only a path-ready survivor (or ranked best). Never load preferred
		-- when every leaf failed issuer_path_health — that would skip the readiness gate.
		local soft_leaf = (best and best.leaf) or path_ready[1]
		if not soft_leaf then
			return false, "must_staple", last_detail or "issuer_path_health"
		end
		local soft_fp = soft_leaf.fp
		log(
			ngx.ERR,
			format_staple_decision(last_detail or "probe_failed", {
				tag = "OCSP_MUST_STAPLE_REFUSE",
				action = "continue_install",
				mode = mode,
				fp = (type(soft_fp) == "string" and #soft_fp == 64) and soft_fp
					or (tostring(soft_fp and soft_fp:sub(1, 16) or "nil") .. "..."),
			})
		)
		if ngx.ctx then
			ngx.ctx.bw_ocsp_soft_fuse_logged = true
		end
		-- seal_path=false: unprobed soft-fuse bag must re-presentable on staple.
		local ok_soft, soft_pem, soft_fp_out = install_one(soft_leaf, false, false)
		if ok_soft then
			log_skipped_sibling_leaves(leaves, soft_leaf, server_name)
			return true, soft_pem, soft_fp_out
		end
		return false, soft_pem or "must_staple", soft_fp_out or last_detail
	elseif last_err == "must_staple" then
		-- normal: no soft fuse for Must-Staple; require proven staple.
		return false, "must_staple", last_detail or "no_staple_candidates"
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
-- chain_blocks (optional): when present, probe_only runs the same issuer_path_intermediate_ready
-- gate as the PEM path; Must-Staple without chain → fingerprint_chain_unavailable.
-- Gen-bound ffi_needed: fingerprint path cannot run ngx.ocsp.validate without leaf PEM
-- issuers — if the latch is set, refuse with force_ffi_pending (KEEP) until a PEM handshake
-- clears it. Empty disk DER returns response_empty (not response_not_found).
-- ============================================================================
-- staple_from_fingerprint(internalstore, server_name, fingerprint,
--                         probe_only, mode, chain_blocks)
-- ============================================================================
-- PURPOSE:
--   Staple OCSP for certificate identified by fingerprint only (no PEM).
--   Used for stream subsystem and fingerprint-hint fallback path.
--
-- PARAMETERS:
--   internalstore (table): per-worker cache
--   server_name (string): SNI hostname for config/logging
--   fingerprint (string): leaf SPKI fingerprint (64 hex chars)
--   probe_only (boolean): health-check only (don't write allow-pin bus)
--   mode (string): "normal"|"open"|"staple_only" (Must-Staple enforcement)
--   chain_blocks (table|nil): issuer-linked blocks for intermediate MS check
--
-- RETURNS:
--   (boolean): true if staple ready/attached
--   (false, "must_staple", detail): Must-Staple unmet
--   (false): optional stapling skip
--
-- SIDE EFFECTS:
--   - Reads: ocsp.json metadata, L1/disk cache, ocsp.der, issuer.pem
--   - Writes: ngx.ocsp.set_ocsp_status_resp() if attaching
--   - Calls: staple_one_leaf() for actual attachment logic
--   - Logging: Must-Staple detection logged
--
-- DESIGN NOTES:
--   - Fingerprint-only: No leaf PEM (stream context or hint fallback)
--   - Must-Staple: Fail-closed (no PEM = must prove from ocsp.json)
--   - Chain blocks: Optional, required for intermediate MS check
--   - Probe-only: Rank probes don't write allow-pin bus (dual-cert safety)
--   - Gates: Tombstone, peer-refuse, cluster-floor, not-paged checks
--   - Soft-fuse: Mode determines enforcement after gates pass
--   - Performance: Same as PEM path (~1-50ms depending on cache)
--
-- RELATED:
--   - Called by _M.staple() when cert_pem absent (fingerprint-hint fallback)
--   - staple_one_leaf() does actual stapling for fingerprint
--   - _M.probe() uses this for fingerprint health-check
--
-- ============================================================================
local function staple_from_fingerprint(internalstore, server_name, fingerprint, probe_only, mode, chain_blocks)
	mode = mode or "normal"
	-- probe_only: score health without touching the allow-pin bus (dual-cert rank).
	local function refuse(fp, m, r, detail)
		if probe_only then
			return false, "must_staple", detail
		end
		return must_staple_refuse(fp, m, r, detail, mode)
	end
	local meta = read_ocsp_json(fingerprint)
	-- Fail closed like PEM staple / resolve_leaf_must_staple(nil, fp):
	-- no PEM → cannot prove non-MS; missing/false ocsp.json flag is not proven-false.
	-- Do not use ocsp_json_must_staple alone (that fail-opens optional stapling).
	local ms_module = get_must_staple_module()
	local must_tri
	if ms_module then
		must_tri = ms_module.get_must_staple(nil, fingerprint)
	else
		must_tri = store.resolve_leaf_must_staple(nil, fingerprint)
	end
	local must_staple = must_tri ~= false
	-- open (incl. stapling off): no enforcement, same as the PEM leaf path in _M.staple.
	-- Gates below still skip a bad body; they just return false instead of refusing.
	if must_staple and mode == "open" then
		must_staple = false
	end
	-- Fingerprint-only: intermediate Must-Staple is unprovable without PEM chain.
	-- Must-Staple leaves refuse with fingerprint_chain_unavailable (see attach_fp).
	if must_staple and (type(chain_blocks) ~= "table" or #chain_blocks < 1) then
		return refuse(fingerprint, meta, nil, "fingerprint_chain_unavailable")
	end
	if meta_tombstoned(meta, fingerprint) then
		drop_cache(internalstore, fingerprint)
		if must_staple then
			return refuse(fingerprint, meta, nil, "tombstoned")
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
	if must_tri == true then
		log(ngx.INFO, "OCSP-Must-Staple from ocsp.json for fp=" .. fingerprint:sub(1, 16) .. "...")
	elseif must_staple then
		log(ngx.INFO, "OCSP-Must-Staple (fail-closed fingerprint-only) fp=" .. fingerprint:sub(1, 16) .. "...")
	end

	if must_staple and cluster_floor_blocks(fingerprint, meta) then
		return refuse(fingerprint, meta, nil, "cluster_floor")
	end
	if shard_not_paged(meta, fingerprint) then
		if must_staple then
			return refuse(fingerprint, meta, nil, "not_paged")
		end
		return false
	end

	-- Prefer leaf PEM from optional chain_blocks so AIA pin can run when wired.
	local leaf_for_aia = nil
	if type(chain_blocks) == "table" and type(chain_blocks[1]) == "string" and chain_blocks[1] ~= "" then
		leaf_for_aia = chain_blocks[1]
	end
	local aia_ok, aia_why = aia_uri_pin_ok(leaf_for_aia, meta, must_staple)
	if not aia_ok then
		if must_staple then
			return refuse(fingerprint, meta, nil, aia_why or "aia_uri_mismatch")
		end
		return false
	end

	if not stapling_enabled(internalstore, server_name) then
		if must_staple then
			return refuse(fingerprint, meta, nil, "ssl_use_ocsp_stapling_no")
		end
		log_stapling_off("ssl_use_ocsp_stapling_no")
		return false
	end

	local ok_ocsp, ocsp = pcall(require, "ngx.ocsp")
	if not ok_ocsp or not ocsp or not ocsp.set_ocsp_status_resp then
		if must_staple then
			return refuse(fingerprint, meta, nil, "ngx_ocsp_unavailable")
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
		return refuse(fingerprint, meta, nil, "fingerprint_chain_unavailable")
	end

	-- Refuse attach while a PEM-path validate_budget latch is live (no leaf PEM here).
	local function refuse_force_ffi(resp_body)
		if not is_ffi_needed(internalstore, fingerprint, meta, resp_body) then
			return nil
		end
		if must_staple then
			if probe_only then
				return false, "must_staple", "force_ffi_pending"
			end
			return refuse(fingerprint, meta, resp_body, "force_ffi_pending")
		end
		return false
	end

	local cached, cached_verified, cached_epoch, cached_expires, cached_gen = get_l1(internalstore, fingerprint)
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
					return refuse(fingerprint, meta, nil, fresh_why or "response_stale")
				end
			else
				if serial_blacklist_blocks(fingerprint, cached) then
					drop_cache(internalstore, fingerprint)
					if must_staple then
						return refuse(fingerprint, meta, nil, "serial_blacklisted")
					end
					return false
				end
				local live_gen = soft_recall_gen_of(ligand_or_meta(meta, fingerprint))
				local verified = entry_verified(cached_verified, cached, cached_gen, live_gen)
				-- Only consult meta when L1 is not already crypto-verified (avoids refuse noise).
				local authorized = false
				if not verified then
					authorized = ocsp_json_authorizes_resp(meta, fingerprint, cached)
				end
				if verified or authorized then
					-- Must-Staple: stream-private verified L1 is not enough; bind shared ligand.
					-- Pass body bytes so DROP_ALLOW causes (concrete ligand / CertID) can CAS-delete.
					local ligand_ok, ligand_detail = must_staple_binds_shared_ligand(meta, fingerprint, cached)
					if must_staple and not ligand_ok then
						drop_cache(internalstore, fingerprint)
						return refuse(fingerprint, meta, cached, ligand_detail)
					end
					local ok_id, why = certid_consistent_with_meta(meta or read_ocsp_json(fingerprint), cached)
					if not ok_id then
						local dialect = (why == "serial_mismatch") and "certid_mismatch" or "certid_unreadable"
						log(
							ngx.ERR,
							"OCSP CertID refuse fingerprint staple reason="
								.. tostring(why)
								.. " dialect="
								.. dialect
								.. " fp="
								.. fingerprint:sub(1, 16)
								.. "..."
						)
						drop_cache(internalstore, fingerprint)
						if must_staple then
							return refuse(fingerprint, meta, cached, dialect)
						end
						return false
					end
					do
						local blocked = refuse_force_ffi(cached)
						if blocked ~= nil then
							return blocked
						end
					end
					if probe_only then
						-- Same issuer-path gate as PEM probe when chain blocks are available.
						if type(chain_blocks) == "table" and #chain_blocks > 0 then
							local path_ok, path_detail = issuer_path_intermediate_ready(chain_blocks)
							if not path_ok then
								return false, "must_staple", path_detail or "unmet"
							end
						end
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
							warm_cache(internalstore, fingerprint, cached, true, exp, cached_epoch, live_gen)
						else
							warm_cache(internalstore, fingerprint, cached, false, exp, cached_epoch, live_gen)
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
						return refuse(fingerprint, meta, cached, detail)
					end
				end
			end
		end
	end

	local resp, resp_why = read_file(ocsp_path(fingerprint))
	if not resp and resp_why == "empty" then
		if must_staple then
			if probe_only then
				return false, "must_staple", "response_empty"
			end
			return refuse(fingerprint, meta, nil, "response_empty")
		end
		return false
	end
	if resp then
		local fresh, fresh_why = resp_still_fresh(nil, fingerprint, meta)
		if not fresh then
			log(
				ngx.ERR,
				"OCSP disk response past nextUpdate/expires; refusing staple fp=" .. fingerprint:sub(1, 16) .. "..."
			)
			if must_staple then
				return refuse(fingerprint, meta, nil, fresh_why or "response_stale")
			end
			return false
		end
		-- Disk path: verified binding only exists in L1; after drop/miss, require meta authorize
		-- or a concurrent warmer rewrite. Re-check composite if rewarmed.
		local _, disk_verified, _, _, disk_gen = get_l1(internalstore, fingerprint)
		if serial_blacklist_blocks(fingerprint, resp) then
			if must_staple then
				return refuse(fingerprint, meta, nil, "serial_blacklisted")
			end
			return false
		end
		local live_gen = soft_recall_gen_of(ligand_or_meta(meta, fingerprint))
		local verified = entry_verified(disk_verified, resp, disk_gen, live_gen)
		local authorized = false
		if not verified then
			authorized = ocsp_json_authorizes_resp(meta, fingerprint, resp)
		end
		if verified or authorized then
			local ligand_ok, ligand_detail = must_staple_binds_shared_ligand(meta, fingerprint, resp)
			if must_staple and not ligand_ok then
				return refuse(fingerprint, meta, resp, ligand_detail)
			end
			local ok_id, why = certid_consistent_with_meta(meta, resp)
			if not ok_id then
				local dialect = (why == "serial_mismatch") and "certid_mismatch" or "certid_unreadable"
				log(
					ngx.ERR,
					"OCSP CertID refuse fingerprint staple reason="
						.. tostring(why)
						.. " dialect="
						.. dialect
						.. " fp="
						.. fingerprint:sub(1, 16)
						.. "..."
				)
				if must_staple then
					return refuse(fingerprint, meta, resp, dialect)
				end
				return false
			end
			do
				local blocked = refuse_force_ffi(resp)
				if blocked ~= nil then
					return blocked
				end
			end
			if probe_only then
				if type(chain_blocks) == "table" and #chain_blocks > 0 then
					local path_ok, path_detail = issuer_path_intermediate_ready(chain_blocks)
					if not path_ok then
						return false, "must_staple", path_detail or "unmet"
					end
				end
				return true
			end
			local set_ok, set_err
			local ok_set = pcall(function()
				set_ok, set_err = attach_fp(resp)
			end)
			if ok_set and set_ok then
				warm_cache(internalstore, fingerprint, resp, verified, meta_effective_expires_unix(meta), nil, live_gen)
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
				return refuse(fingerprint, meta, resp, detail)
			end
			return false
		end
	end

	if must_staple then
		return refuse(fingerprint, meta, nil, "response_not_found")
	end
	return false
end

-- staple_one_leaf: L1 then disk staple/probe for one leaf SPKI.
-- Gates: tombstone, peer refuse, cluster floor, not_paged, AIA, serial blacklist,
-- shared ligand (Must-Staple), CertID, then try_staple / attach.
-- Verified L1: restocks warm_cache TTL on hit; if is_ffi_needed, forces try_staple
-- instead of the attach shortcut so validate_budget unfinished bodies still FFI once.
-- Unverified L1 / disk: try_staple with force_ffi from the gen-bound latch; budget
-- abort demotes L1 + mark_ffi_needed (install only); clear_ffi only when did_ffi.
-- try_staple dialect: issuer_unavailable (zero PEMs), validate_exhausted (all failed),
-- validate_budget (soft ceiling). Empty disk DER → response_empty (not response_not_found).
-- Disk fallthrough rebuilds issuer_candidates when L1 left a truthy empty table
-- (Lua `issuers or …` would keep {}).
-- probe_only: never writes the allow-pin bus (local refuse wrapper); returns true or false,"must_staple",detail.
-- Returns true | false [, reason [, detail]] | nil (no usable body).
-- ============================================================================
-- staple_one_leaf(internalstore, ocsp, ssl, blocks, leaf_pem, fingerprint,
--                 must_staple, server_name, probe_only, mode)
-- ============================================================================
-- PURPOSE:
--   Core OCSP stapling orchestrator: L1 cache + disk path with complete gates.
--   Handles all freshness validation, Must-Staple enforcement, and attachment.
--
-- PARAMETERS:
--   internalstore (table): per-worker cache
--   ocsp (ffi): ngx.ocsp FFI module for validation/attachment
--   ssl (ffi): ngx.ssl FFI module for PEM parsing
--   blocks (table): certificate chain blocks (intermediates for multi-staple)
--   leaf_pem (string): leaf certificate PEM
--   fingerprint (string): leaf SPKI fingerprint (64 hex chars)
--   must_staple (boolean): enforce Must-Staple requirement
--   server_name (string): SNI hostname for config/logging
--   probe_only (boolean): health-check only (no attachment/pin changes)
--   mode (string): "normal"|"open"|"staple_only" (enforcement mode)
--
-- RETURNS:
--   (boolean): true if staple attached/ready
--   (false, "must_staple", detail): Must-Staple unmet
--   (false): optional stapling skip
--   (nil): no usable body
--
-- SIDE EFFECTS:
--   - Reads: L1 cache, disk ocsp.der/ocsp.json, issuer.pem
--   - Writes: ngx.ocsp.set_ocsp_status_resp() on success
--   - Calls: try_staple(), attach_ocsp_staple(), issuer_candidates()
--   - Caches: issuer SPKI, validation results
--   - Metrics: disk I/O timing (issuer_pem, meta_json, ocsp_der)
--
-- DESIGN NOTES:
--   - Critical path orchestrator: L1 cache + metadata + freshness gates
--   - Gates: Tombstone, peer-refuse, cluster-floor, not-paged, AIA, serial-blacklist
--   - L1 path: Verified (sha256 bound) + generation-matched
--   - Disk path: Meta authorization + freshness re-check
--   - FFI latch: Respects force_ffi (after validate_budget)
--   - Metrics: Tracks disk I/O latency (issuer, metadata, response)
--   - Soft-fuse: Mode determines enforcement after gates
--   - Performance: L1 hit (~1ms), L1 miss + disk (~50ms with FFI)
--
-- RELATED:
--   - staple_from_fingerprint() calls this for fingerprint path
--   - try_staple() does FFI validation logic
--   - Called by PEM path (via staple_one_leaf wrapper) and fingerprint path
--
-- ============================================================================
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
	-- probe_only: never DROP/KEEP the fleet pin — return soft must_staple only.
	local function refuse(fp, m, r, detail)
		if probe_only then
			return false, "must_staple", detail
		end
		return must_staple_refuse(fp, m, r, detail, mode)
	end
	-- ========================================================================
	-- Disk I/O Optimization: Cache Issuer SPKI & Metadata
	-- ========================================================================
	-- Strategy: On L1 miss, cache issuer SPKI + ocsp.json in shared dict
	-- to avoid re-reading from disk on next L1 miss.
	--
	-- Shared Dict Keys:
	--   "OCSP:ISSUER_SPKI:{fingerprint}:{epoch}" → write-through SPKI (pin always from PEM)
	-- Refuse gates (tombstoned / paged) always read ocsp.json fresh — job writes
	-- tombstoned before epoch bump, so META shm must not serve those fields.

	local issuers = nil

	-- ────────────────────────────────────────────────────────────────────
	-- Issuer.pem (always read) + SPKI cache (epoch-bound)
	-- ────────────────────────────────────────────────────────────────────
	-- Always read issuer.pem for issuer_candidates. A SPKI-only cache hit must
	-- NOT map to stored_pem=false ("confirmed absent") — that skips disk and
	-- leaves leaf-only bags with empty candidates → issuer_unavailable.
	-- Always derive SPKI from the PEM we read — never trust shm alone (issuer replace
	-- without epoch bump must not pin validate() to a stale SPKI).
	local issuer_spki_cache_key = "OCSP:ISSUER_SPKI:" .. fingerprint .. ":" .. tostring(current_ocsp_epoch() or "0")

	local t_issuer_start = ngx.hrtime and ngx.hrtime() or nil
	local shard_issuer_pem = read_file(issuer_path(fingerprint))
	if t_issuer_start and ngx.ctx then
		local elapsed_ns = ngx.hrtime() - t_issuer_start
		if not ngx.ctx.bw_ocsp_disk_io then
			ngx.ctx.bw_ocsp_disk_io = {}
		end
		ngx.ctx.bw_ocsp_disk_io.issuer_pem_ns = elapsed_ns
	end

	-- Three-state for issuer_candidates: string PEM | false = absent | never nil here.
	local issuer_stored = shard_issuer_pem or false
	local shard_issuer_spki = nil
	if shard_issuer_pem then
		shard_issuer_spki = spki_fingerprint(shard_issuer_pem)
		if shard_issuer_spki and ngx.shared and ngx.shared.bw_ocsp_validations then
			pcall(function()
				ngx.shared.bw_ocsp_validations:set(issuer_spki_cache_key, shard_issuer_spki, 300)
			end)
		end
	end

	-- ────────────────────────────────────────────────────────────────────
	-- Metadata: always fresh disk read for refuse gates
	-- ────────────────────────────────────────────────────────────────────
	local t_meta_start = ngx.hrtime and ngx.hrtime() or nil
	local meta = read_ocsp_json(fingerprint)
	if t_meta_start and ngx.ctx then
		local elapsed_ns = ngx.hrtime() - t_meta_start
		if not ngx.ctx.bw_ocsp_disk_io then
			ngx.ctx.bw_ocsp_disk_io = {}
		end
		ngx.ctx.bw_ocsp_disk_io.meta_json_ns = elapsed_ns
	end
	if meta_tombstoned(meta, fingerprint) then
		drop_cache(internalstore, fingerprint)
		if must_staple then
			return refuse(fingerprint, meta, nil, "tombstoned")
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
		return refuse(fingerprint, meta, nil, "cluster_floor")
	end
	if shard_not_paged(meta, fingerprint) then
		if must_staple then
			return refuse(fingerprint, meta, nil, "not_paged")
		end
		return false
	end
	local aia_ok, aia_why = aia_uri_pin_ok(leaf_pem, meta, must_staple)
	if not aia_ok then
		if must_staple then
			return refuse(fingerprint, meta, nil, aia_why or "aia_uri_mismatch")
		end
		return false
	end

	-- ========================================================================
	-- L1 Cache Instrumentation
	-- ========================================================================
	-- Track L1 cache hit/miss rate for monitoring
	-- Metric: Cache hit rate should be >80% on warm system
	-- If <80%: L1 TTL too short or cache not warmed

	local cached, cached_verified, cached_epoch, cached_expires, cached_gen = get_l1(internalstore, fingerprint)

	-- Record L1 hit/miss in request context
	if ngx.ctx then
		if not ngx.ctx.bw_ocsp_metrics then
			ngx.ctx.bw_ocsp_metrics = {}
		end
		if cached then
			ngx.ctx.bw_ocsp_metrics.l1_cache_hit = true
		else
			ngx.ctx.bw_ocsp_metrics.l1_cache_miss = true
		end
	end

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
					return refuse(fingerprint, meta, nil, fresh_why or "response_stale")
				end
			elseif
				entry_verified(
					cached_verified,
					cached,
					cached_gen,
					soft_recall_gen_of(ligand_or_meta(meta, fingerprint))
				)
			then
				if serial_blacklist_blocks(fingerprint, cached) then
					drop_cache(internalstore, fingerprint)
					if must_staple then
						return refuse(fingerprint, meta, nil, "serial_blacklisted")
					end
					return false
				end
				issuers = issuer_candidates(blocks, leaf_pem, fingerprint, issuer_stored)
				local ok_id, why = certid_matches_handshake_leaf(leaf_pem, cached, issuers)
				if not ok_id then
					local dialect = certid_handshake_refuse_dialect(why)
					log(
						ngx.ERR,
						"OCSP CertID refuse L1 staple reason="
							.. tostring(why)
							.. " dialect="
							.. dialect
							.. " fp="
							.. fingerprint:sub(1, 16)
							.. "..."
					)
					drop_cache(internalstore, fingerprint)
					if must_staple then
						return refuse(fingerprint, meta, cached, dialect)
					end
				-- Fall through to disk / re-validate with the current leaf.
				else
					-- Must-Staple: bind shared ocsp.json ligand, not stream-private L1 alone.
					if must_staple then
						meta = meta or read_ocsp_json(fingerprint)
						local ligand_ok, ligand_detail = must_staple_binds_shared_ligand(meta, fingerprint, cached)
						if not ligand_ok then
							drop_cache(internalstore, fingerprint)
							return refuse(fingerprint, meta, cached, ligand_detail)
						end
					end
					-- force_ffi: prior validate_budget — do not attach via verified shortcut.
					local force_ffi = is_ffi_needed(internalstore, fingerprint, meta, cached)
					if force_ffi then
						issuers = issuer_candidates(blocks, leaf_pem, fingerprint, issuer_stored)
						local result, result_detail, did_ffi = try_staple(
							ocsp,
							ssl,
							cached,
							leaf_pem,
							issuers,
							shard_issuer_spki,
							probe_only,
							meta,
							fingerprint,
							blocks,
							true,
							mode
						)
						if result == true then
							if probe_only then
								local path_ok, path_detail = issuer_path_intermediate_ready(blocks)
								if not path_ok then
									return false, "must_staple", path_detail or "unmet"
								end
								-- Clear latch only when this walk proved crypto (did_ffi).
								if did_ffi then
									clear_ffi_needed(internalstore, fingerprint, meta, cached)
								end
								return true
							end
							warm_cache(
								internalstore,
								fingerprint,
								cached,
								true,
								meta_effective_expires_unix(meta or read_ocsp_json(fingerprint), cached_expires),
								cached_epoch,
								soft_recall_gen_of(ligand_or_meta(meta, fingerprint))
							)
							if did_ffi then
								clear_ffi_needed(internalstore, fingerprint, meta, cached)
							end
							log_ocsp_stapled(server_name, cert_pubkey_kind(leaf_pem), fingerprint, cached)
							return true
						end
						if result == false then
							if result_detail == "validate_budget" then
								-- probe_only must not demote L1 or stamp force_ffi (HTTP parity).
								if not probe_only then
									warm_cache(
										internalstore,
										fingerprint,
										cached,
										false,
										meta_effective_expires_unix(meta or read_ocsp_json(fingerprint), cached_expires),
										cached_epoch,
										soft_recall_gen_of(ligand_or_meta(meta, fingerprint))
									)
									mark_ffi_needed(internalstore, fingerprint, meta, cached)
								end
								if must_staple then
									return refuse(fingerprint, meta, cached, "validate_budget")
								end
								return false
							end
							if
								result_detail == "issuer_unavailable"
								or result_detail == "validate_exhausted"
								or result_detail == "certid_unreadable"
								or result_detail == "issuer_ambiguous"
							then
								if must_staple then
									return refuse(fingerprint, meta, cached, result_detail)
								end
								return false
							end
							if result_detail == "certid_mismatch" then
								if must_staple then
									drop_cache(internalstore, fingerprint)
									return refuse(fingerprint, meta, cached, "certid_mismatch")
								end
							elseif
								result_detail == "intermediate_must_staple_libssl"
								or result_detail == "intermediate_must_staple_colony"
								or result_detail == "multi_staple_attach_failed"
								or result_detail == "fingerprint_chain_unavailable"
								or result_detail == "issuer_unresolved_must_staple"
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
									and detail ~= "response_not_found"
									and detail ~= "issuer_unavailable"
									and detail ~= "validate_exhausted"
									and detail ~= "certid_unreadable"
									and detail ~= "issuer_ambiguous"
									and detail ~= "unmet"
									and detail ~= "validate_budget"
									and detail ~= "set_staple_failed"
								then
									detail = canary_paged_body_ok(meta, fingerprint, cached) and "set_staple_failed"
										or "unmet"
								end
								pcall(clear_connection_staple)
								return refuse(fingerprint, meta, cached, detail)
							end
							if result_detail ~= "certid_mismatch" then
								return false
							end
							-- certid optional: fall through to disk
						else
							drop_cache(internalstore, fingerprint)
						end
					elseif probe_only then
						local path_ok, path_detail = issuer_path_intermediate_ready(blocks)
						if not path_ok then
							return false, "must_staple", path_detail or "unmet"
						end
						-- Verified shortcut: no FFI this walk — do not clear force_ffi latch.
						return true
					else
						local set_ok, set_err
						local ok_set = pcall(function()
							set_ok, set_err = attach_ocsp_staple(ocsp, cached, blocks)
						end)
						if ok_set and set_ok then
							-- Restock L1 TTL on hot verified hits (was only on cold/FFI paths).
							warm_cache(
								internalstore,
								fingerprint,
								cached,
								true,
								meta_effective_expires_unix(meta or read_ocsp_json(fingerprint), cached_expires),
								cached_epoch,
								soft_recall_gen_of(ligand_or_meta(meta, fingerprint))
							)
							-- Verified shortcut: no FFI — leave force_ffi latch intact.
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
							return refuse(fingerprint, meta, cached, detail)
						end
					end
				end
			else
				if serial_blacklist_blocks(fingerprint, cached) then
					drop_cache(internalstore, fingerprint)
					if must_staple then
						return refuse(fingerprint, meta, nil, "serial_blacklisted")
					end
					return false
				end
				issuers = issuer_candidates(blocks, leaf_pem, fingerprint, issuer_stored)
				-- Ligand before attach: try_staple attaches on success. Soft fuse must not
				-- leave a mismatched DER on the SSL object. Pass body for DROP_ALLOW CAS.
				if must_staple then
					meta = meta or read_ocsp_json(fingerprint)
					local ligand_ok, ligand_detail = must_staple_binds_shared_ligand(meta, fingerprint, cached)
					if not ligand_ok then
						drop_cache(internalstore, fingerprint)
						return refuse(fingerprint, meta, cached, ligand_detail)
					end
				end
				local force_ffi = is_ffi_needed(internalstore, fingerprint, meta, cached)
				local result, result_detail, did_ffi = try_staple(
					ocsp,
					ssl,
					cached,
					leaf_pem,
					issuers,
					shard_issuer_spki,
					probe_only,
					meta,
					fingerprint,
					blocks,
					force_ffi,
					mode
				)
				if result == true then
					if probe_only then
						local path_ok, path_detail = issuer_path_intermediate_ready(blocks)
						if not path_ok then
							return false, "must_staple", path_detail or "unmet"
						end
						if did_ffi then
							clear_ffi_needed(internalstore, fingerprint, meta, cached)
						end
						return true
					end
					warm_cache(
						internalstore,
						fingerprint,
						cached,
						true,
						meta_effective_expires_unix(meta or read_ocsp_json(fingerprint), cached_expires),
						cached_epoch,
						soft_recall_gen_of(ligand_or_meta(meta, fingerprint))
					)
					if did_ffi then
						clear_ffi_needed(internalstore, fingerprint, meta, cached)
					end
					log_ocsp_stapled(server_name, cert_pubkey_kind(leaf_pem), fingerprint, cached)
					return true
				end
				if result == false then
					if result_detail == "validate_budget" then
						-- Demote L1 + mark force_ffi only on install (not probe_only rank).
						if not probe_only then
							warm_cache(
								internalstore,
								fingerprint,
								cached,
								false,
								meta_effective_expires_unix(meta or read_ocsp_json(fingerprint), cached_expires),
								cached_epoch,
								soft_recall_gen_of(ligand_or_meta(meta, fingerprint))
							)
							mark_ffi_needed(internalstore, fingerprint, meta, cached)
						end
						if must_staple then
							return refuse(fingerprint, meta, cached, "validate_budget")
						end
						return false
					end
					if
						result_detail == "issuer_unavailable"
						or result_detail == "validate_exhausted"
						or result_detail == "certid_unreadable"
						or result_detail == "issuer_ambiguous"
					then
						if must_staple then
							return refuse(fingerprint, meta, cached, result_detail)
						end
						return false
					end
					-- Optional stapling: CertID miss on unverified L1 falls through to disk.
					-- Must-Staple fails immediately; optional stapling re-validates on disk.
					if result_detail == "certid_mismatch" then
						if must_staple then
							drop_cache(internalstore, fingerprint)
							return refuse(fingerprint, meta, cached, "certid_mismatch")
						end
						-- Fall through to disk path for optional stapling re-validation
					end
					if
						result_detail == "intermediate_must_staple_libssl"
						or result_detail == "intermediate_must_staple_colony"
						or result_detail == "multi_staple_attach_failed"
						or result_detail == "fingerprint_chain_unavailable"
						or result_detail == "issuer_unresolved_must_staple"
						or result_detail == "response_not_found"
						or must_staple
					then
						-- Preserve DROP/KEEP codes from try_staple. Bare false + canary
						-- ligand collapses to set_staple_failed / unmet.
						local detail = result_detail
						if
							detail ~= "intermediate_must_staple_libssl"
							and detail ~= "intermediate_must_staple_colony"
							and detail ~= "multi_staple_attach_failed"
							and detail ~= "fingerprint_chain_unavailable"
							and detail ~= "issuer_unresolved_must_staple"
							and detail ~= "response_not_found"
							and detail ~= "issuer_unavailable"
							and detail ~= "validate_exhausted"
							and detail ~= "certid_unreadable"
							and detail ~= "issuer_ambiguous"
							and detail ~= "unmet"
							and detail ~= "validate_budget"
							and detail ~= "set_staple_failed"
						then
							detail = canary_paged_body_ok(meta, fingerprint, cached) and "set_staple_failed" or "unmet"
						end
						-- Attach already ran for some path demotions; clear leftover staple.
						pcall(clear_connection_staple)
						return refuse(fingerprint, meta, cached, detail)
					end
					return false
				end
				drop_cache(internalstore, fingerprint)
			end
		end
	end

	local resp, resp_why = read_file(ocsp_path(fingerprint))
	if not resp and resp_why == "empty" then
		-- Truncated/empty ocsp.der is not "missing" — keep dialect distinct for refuse policy.
		if must_staple then
			if probe_only then
				return false, "must_staple", "response_empty"
			end
			return refuse(fingerprint, meta, nil, "response_empty")
		end
		return false
	end
	if resp then
		meta = meta or read_ocsp_json(fingerprint)
		local fresh, fresh_why = resp_still_fresh(nil, fingerprint, meta)
		if not fresh then
			log(
				ngx.ERR,
				"OCSP disk response past nextUpdate/expires; refusing staple fp=" .. fingerprint:sub(1, 16) .. "..."
			)
			if must_staple then
				return refuse(fingerprint, meta, nil, fresh_why or "response_stale")
			end
			return false
		end
		-- Rebuild when L1 left a truthy empty table (issuers or … would keep {}).
		if type(issuers) ~= "table" or #issuers == 0 then
			issuers = issuer_candidates(blocks, leaf_pem, fingerprint, issuer_stored)
		end
		if serial_blacklist_blocks(fingerprint, resp) then
			if must_staple then
				return refuse(fingerprint, meta, nil, "serial_blacklisted")
			end
			return false
		end
		-- Ligand before attach (same contract as L1 unverified path).
		if must_staple then
			local ligand_ok, ligand_detail = must_staple_binds_shared_ligand(meta, fingerprint, resp)
			if not ligand_ok then
				return refuse(fingerprint, meta, resp, ligand_detail)
			end
		end
		local force_ffi = is_ffi_needed(internalstore, fingerprint, meta, resp)
		local result, result_detail, did_ffi = try_staple(
			ocsp,
			ssl,
			resp,
			leaf_pem,
			issuers,
			shard_issuer_spki,
			probe_only,
			meta,
			fingerprint,
			blocks,
			force_ffi,
			mode
		)
		if result == true then
			if probe_only then
				local path_ok, path_detail = issuer_path_intermediate_ready(blocks)
				if not path_ok then
					return false, "must_staple", path_detail or "unmet"
				end
				if did_ffi then
					clear_ffi_needed(internalstore, fingerprint, meta, resp)
				end
				return true
			end
			warm_cache(internalstore, fingerprint, resp, true, meta_effective_expires_unix(meta), nil, soft_recall_gen_of(ligand_or_meta(meta, fingerprint)))
			if did_ffi then
				clear_ffi_needed(internalstore, fingerprint, meta, resp)
			end
			log_ocsp_stapled(server_name, cert_pubkey_kind(leaf_pem), fingerprint, resp)
			return true
		end
		if result == false then
			if result_detail == "validate_budget" then
				if not probe_only then
					warm_cache(internalstore, fingerprint, resp, false, meta_effective_expires_unix(meta), nil, soft_recall_gen_of(ligand_or_meta(meta, fingerprint)))
					mark_ffi_needed(internalstore, fingerprint, meta, resp)
				end
				if must_staple then
					return refuse(fingerprint, meta, resp, "validate_budget")
				end
				return false
			end
			if
				result_detail == "issuer_unavailable"
				or result_detail == "validate_exhausted"
				or result_detail == "certid_unreadable"
				or result_detail == "issuer_ambiguous"
			then
				if must_staple then
					return refuse(fingerprint, meta, resp, result_detail)
				end
				return false
			end
			if result_detail == "certid_mismatch" then
				if must_staple then
					return refuse(fingerprint, meta, resp, "certid_mismatch")
				end
				return false
			end
			if
				result_detail == "intermediate_must_staple_libssl"
				or result_detail == "intermediate_must_staple_colony"
				or result_detail == "multi_staple_attach_failed"
				or result_detail == "fingerprint_chain_unavailable"
				or result_detail == "issuer_unresolved_must_staple"
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
					and detail ~= "response_not_found"
					and detail ~= "issuer_unavailable"
					and detail ~= "validate_exhausted"
					and detail ~= "certid_unreadable"
					and detail ~= "issuer_ambiguous"
					and detail ~= "unmet"
					and detail ~= "validate_budget"
					and detail ~= "set_staple_failed"
				then
					detail = canary_paged_body_ok(meta, fingerprint, resp) and "set_staple_failed" or "unmet"
				end
				pcall(clear_connection_staple)
				return refuse(fingerprint, meta, resp, detail)
			end
			return false
		end
	end
	return nil
end

-- ============================================================================
-- _M.staple(internalstore, server_name, cert_pem, cert_fp_hint)
-- ============================================================================
-- PURPOSE:
--   Public API: Attach OCSP staple to TLS connection. Main entry point for
--   HTTP and stream subsystems to staple cached OCSP responses.
--
-- PARAMETERS:
--   internalstore (table): per-worker cache (ngx.shared.bw_ocsp_*) or internalstore_stream
--   server_name (string): SNI hostname for logging/config lookups
--   cert_pem (string|table): full PEM chain OR issuer-linked blocks table
--                            blocks[1] = leaf, blocks[2..n] = intermediates
--   cert_fp_hint (string|nil): SPKI fingerprint (64-char hex) for fingerprint-only path
--
-- RETURNS:
--   (boolean): true if staple attached successfully
--   (false, "must_staple", detail): Must-Staple unmet (caller may soft-fuse)
--   (false): optional stapling skip (response missing/invalid/etc.)
--
-- SIDE EFFECTS:
--   - Reads: L1 cache, disk ocsp.der, ocsp.json, issuer.pem
--   - Writes: ngx.ocsp.set_ocsp_status_resp() to TLS connection
--   - Calls: try_staple(), validate(), issuer_candidates()
--   - FFI calls: ngx.ocsp validation (up to 10 issuer attempts)
--   - Metrics: records validation timing + cache hits
--   - Logging: log_ocsp_stapled() on success, log_ocsp_staple_skip() on skip
--
-- DESIGN NOTES:
--   - Dual input: PEM string (parses automatically) or blocks table (pre-parsed)
--   - Blocks.ocsp_path_sealed: Optimization from set_certs_from_pem to skip re-link
--   - Fingerprint-only: When cert_pem absent, uses cert_fp_hint + ocsp.json
--   - L1 cache: Verified (DER SHA256 bound) + generation matched
--   - Soft-fuse: Must-Staple can continue handshake in open/staple_only mode
--   - Multi-staple: One ECDSA leaf stapled (one ngx.ocsp status slot)
--   - Performance: L1 hit (~1ms), L1 miss (~50ms with FFI validation)
--   - Budget: Max 10 issuer candidates, 50ms time hardcap
--   - Async: Scheduler may pre-validate for skip-FFI optimization
--
-- RELATED:
--   - _M.probe() health-check only (no attachment)
--   - _M.set_certs_from_pem() installation with blocking staple
--   - set_certs_from_pem() and this staple use common try_staple logic
--   - ocsp_http.lua / stream/ocsp.lua call this from TLS hooks
--
-- EXAMPLE:
--   local ocsp_module = require("bunkerweb.ocsp")
--   local ok = ocsp_module.staple(ngx.shared.bw_ocsp, "example.com", cert_pem)
--   if not ok then
--     log(ngx.ERR, "OCSP staple failed")
--   end
--
-- ============================================================================
-- Staple a cached OCSP response for cert_pem. Used by the stream TLS handshake.
-- HTTP uses ngx.shared.internalstore; stream uses internalstore_stream. Same key layout
-- (TLS:SSL:ocsp: composite of epoch|verified|expires|DER) so each subsystem warms its own L1.
-- Shm TTL is min(300s, remaining until expires_unix) so DRAM cannot outlive nextUpdate.
-- Verified binding is sha256(DER) packed with the body; L1 drops when epoch or der_sha256 diverges.
-- Must-Staple also requires the shared ocsp.json der_sha256 ligand (cross-zone stand-in for
-- HTTP's L1 entry); stream-private crypto-verified L1 alone is refused.
-- Optional cert_fp_hint (plugin status[5]) enforces Must-Staple via ocsp.json when PEM is absent.
-- Dual-cert PEMs staple the ECDSA leaf only (one ngx.ocsp status slot).
-- Accepts PEM string or issuer-linked blocks; blocks.ocsp_path_sealed (from set_certs_from_pem)
-- skips presentable_chain_blocks re-link so unresolved_must_staple is preserved.
-- Fingerprint-only path unpacks staple_from_fingerprint into locals before soften_must_staple.
-- Rearms the L1 warmer on entry.
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
			local ok, reason, detail = staple_from_fingerprint(internalstore, server_name, fp_hint, false, mode)
			return soften_must_staple(mode, ok, reason, detail)
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
	-- Sealed blocks from set_certs already issuer-linked — skip re-presentable.
	if not blocks.ocsp_path_sealed then
		blocks = presentable_chain_blocks(blocks)
	end
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

	-- Use request-scoped cache to avoid re-resolving same cert multiple times.
	-- Do not use `and … or nil`: a proven-false result would collapse to nil.
	local ms_module = get_must_staple_module()
	local must_tri = nil
	if ms_module then
		must_tri = ms_module.get_must_staple(leaf_pem, fingerprint)
	end
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

-- ============================================================================
-- _M.probe(internalstore, server_name, cert_pem, cert_fp_hint, apply_soften)
-- ============================================================================
-- PURPOSE:
--   Public API: Health-check OCSP staple readiness without installing cert.
--   Validates Must-Staple requirement before set_cert (dual-cert ranking).
--
-- PARAMETERS:
--   internalstore (table): per-worker cache (ngx.shared.bw_ocsp_*)
--   server_name (string): SNI hostname for config/logging
--   cert_pem (string|table): full PEM chain OR issuer-linked blocks table
--   cert_fp_hint (string|nil): SPKI fingerprint for fingerprint-only path
--   apply_soften (boolean|nil): apply soft-fuse (default true for must_staple)
--                               false = skip-leaf caller logs own action
--
-- RETURNS:
--   (boolean): true if staple ready (Must-Staple satisfied or open mode)
--   (false, "must_staple", detail): Must-Staple unmet (abort, cannot install)
--   (false): soft skip (continue without abort, used for sibling ranking)
--
-- SIDE EFFECTS:
--   - Reads: L1 cache, disk ocsp.der, ocsp.json, issuer.pem
--   - Does NOT write: ngx.ocsp.set_ocsp_status_resp() (no cert installed)
--   - Does NOT drop: L1 cache when apply_soften=false (rank probe safety)
--   - Calls: try_staple() with probe_only=true
--   - Metrics: records validation timing
--
-- DESIGN NOTES:
--   - Purpose: Validate staple before commit (set_cert). Fail-safe gate.
--   - Dual-cert: Rank leaves by Must-Staple health before installing
--   - Skip-leaf: apply_soften=false prevents dropping L1 (siblings reuse cache)
--   - Soft-fuse: apply_soften=true honors soft-fuse modes (open/staple_only)
--   - open mode: Returns true immediately (Must-Staple off entirely)
--   - Blocks.ocsp_path_sealed: Honors sealed status from set_certs_from_pem
--   - Performance: Same as staple() but no TLS attachment (~1-50ms)
--   - L1 drop gate: Skipped when apply_soften=false (ranking phase safety)
--
-- RELATED:
--   - _M.staple() actually attaches (with soft-fuse capability)
--   - _M.set_certs_from_pem() uses probe to rank dual-cert leaves
--   - called by ordered_leaves_for_handshake() for health ranking
--   - try_staple() with probe_only=true does actual work
--
-- EXAMPLE:
--   -- Rank dual-cert leaves by staple readiness
--   local probe_ok, reason, detail = ocsp_module.probe(internalstore, sni, leaf_pem)
--   if probe_ok then
--     -- This leaf can be installed with valid staple
--   elseif reason == "must_staple" then
--     -- This leaf's Must-Staple is unmet, skip this leaf
--   end
--
-- ============================================================================
-- Live staple probe for a leaf/shard without installing the cert or setting the staple.
-- Must-Staple leaves must pass this before set_cert (normal and staple_only). Soft fuses
-- only affect handshake abort after install fails entirely — not the skip-leaf gate.
-- Pass apply_soften=false for skip-leaf callers that log their own action
-- (e.g. set_certs_from_pem). open mode short-circuits to true (Must-Staple off).
-- Honors blocks.ocsp_path_sealed (skip re-presentable) and ngx.ctx.bw_ocsp_skip_l1_drop
-- (rank probes must not drop sibling L1). Rearms the L1 warmer on entry.
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
		-- No PEM and no fingerprint: fail closed (Must-Staple harden / dual-cert probe).
		return finish(false, "must_staple", "probe_no_material")
	end
	local leaf_pem = blocks[1]
	if not leaf_pem then
		return finish(false, "must_staple", "probe_no_material")
	end
	-- Sealed blocks from set_certs already issuer-linked — skip re-presentable.
	if not blocks.ocsp_path_sealed then
		blocks = presentable_chain_blocks(blocks)
	end
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
	-- Use request-scoped cache to avoid re-resolving same cert multiple times.
	-- Fail closed: unknown enforces Must-Staple; proven false may load unstapled.
	local ms_module = get_must_staple_module()
	if ms_module and ms_module.get_must_staple(leaf_pem, fingerprint) == false then
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

-- ============================================================================
-- _M.requires_must_staple(cert_pem, cert_fp_hint)
-- ============================================================================
-- PURPOSE:
--   Query whether certificate must have OCSP staple. Returns Must-Staple tri-state
--   from TLS Feature (PEM) or ocsp.json metadata (fingerprint-only path).
--
-- PARAMETERS:
--   cert_pem (string|nil): leaf certificate PEM
--   cert_fp_hint (string|nil): SPKI fingerprint (64-char hex) fallback
--
-- RETURNS:
--   (boolean): true = Must-Staple required (enforce staple)
--             false = Must-Staple disabled (optional stapling ok)
--   Returns true if: TLS Feature set OR unknown (fail-closed)
--   Returns false only if: explicitly marked false in ocsp.json or cert
--
-- SIDE EFFECTS:
--   - Calls: pem_blocks(), spki_fingerprint() for PEM parsing
--   - Calls: get_must_staple_module() for cached detection
--   - No state modification
--
-- DESIGN NOTES:
--   - Tri-state: true (required), false (optional), nil (unknown, treated as true)
--   - Fail-closed: Unknown/missing = enforce (safer default)
--   - TLS Feature: Extracted from PEM during cert parsing
--   - Fingerprint-only: Falls back to ocsp.json if no PEM
--   - Request cache: Uses ngx.ctx cache to avoid re-parsing
--   - Performance: O(1) with cache hit, O(len(PEM)) on miss
--
-- RELATED:
--   - ocsp_must_staple.lua implements Must-Staple detection
--   - staple() and probe() use this to decide enforcement
--   - _M.set_certs_from_pem() annotates leaves with Must-Staple result
--
-- EXAMPLE:
--   local needs_staple = ocsp_module.requires_must_staple(leaf_pem)
--   if needs_staple then
--     log(ngx.INFO, "Certificate requires OCSP staple")
--   end
--
-- ============================================================================
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
	-- Use request-scoped cache.
	local ms_module = get_must_staple_module()
	return not ms_module or ms_module.get_must_staple(leaf_pem, leaf_fp or fp_hint) ~= false
end

-- ============================================================================
-- _M.prefer_kind_from_sigalgs(ext)
-- ============================================================================
-- PURPOSE:
--   Extract coarse key type preference from ClientHello signature_algorithms ext.
--   Returns "ec"|"rsa"|"ed" based on first matching algorithm scheme.
--
-- PARAMETERS:
--   ext (string): raw ClientHello signature_algorithms extension bytes
--
-- RETURNS:
--   (string|nil): "ec" (ECDSA), "rsa" (RSA), "ed" (EdDSA), or nil if absent/unknown
--
-- SIDE EFFECTS:
--   None (pure parsing function, no state modification)
--
-- DESIGN NOTES:
--   - Parsing: Extension format: [len (2 bytes)] [alg_pairs]
--   - Scheme codes: IANA signature algorithm enum (0x0403, 0x0501, etc.)
--   - First match: Returns on first recognized algorithm found
--   - EC schemes: 0x0403, 0x0503, 0x0603 (ECDSA with SHA256/384/512)
--   - EdDSA schemes: 0x0807, 0x0808 (Ed25519, Ed448)
--   - RSA schemes: 0x0401, 0x0501, 0x0601, 0x0804-080b (RSA-PSS variants)
--   - Coarse only: Does not distinguish curves (use raw ext for curve-aware)
--   - Performance: O(n) where n=extension length (~20 bytes typical)
--
-- RELATED:
--   - ordered_leaves_for_handshake() uses raw ext for curve-aware matching
--   - This function provides coarse preference for fallback ranking
--   - _M.capture_client_hello() calls this to cache preference
--
-- EXAMPLE:
--   local kind = ocsp_module.prefer_kind_from_sigalgs(client_hello_ext_13)
--   if kind == "ec" then
--     -- Prefer ECDSA leaf for this client
--   end
--
-- ============================================================================
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

-- ============================================================================
-- _M.capture_client_hello()
-- ============================================================================
-- PURPOSE:
--   Extract ClientHello SNI and signature_algorithms extension during handshake.
--   Stores on ngx.ctx for downstream ssl_certificate phase leaf selection.
--
-- PARAMETERS:
--   None (reads from TLS ClientHello)
--
-- RETURNS:
--   None (stores results in ngx.ctx)
--
-- SIDE EFFECTS:
--   - Reads: ngx.ssl.clienthello (FFI, early in TLS handshake)
--   - Writes: ngx.ctx.bw_ocsp_sni (string|nil)
--             ngx.ctx.bw_ocsp_sigalgs_ext (string|nil, raw ext 13)
--             ngx.ctx.bw_ocsp_prefer_kind (string|nil, coarse kind)
--   - Calls: maybe_rearm_l1_warmer() for early warmer recovery
--   - Performance: O(n) where n=extension size (~50 bytes typical)
--
-- DESIGN NOTES:
--   - SNI extraction: Server name from ClientHello (required for fallback)
--   - Signature algorithms: Extension 13 (raw bytes for curve-aware ranking)
--   - Prefer kind: Coarse extraction (ec/rsa/ed) for fallback ranking
--   - Per-request: Stores on ngx.ctx (cleared on new request)
--   - Early timer: Rearms L1 warmer in case timer.at was unscheduled
--   - Fail-safe: All reads wrapped in pcall(), no errors if feature unavailable
--   - Performance: Called very early in TLS handshake (~1ms typical)
--
-- RELATED:
--   - _M.handshake_sni() retrieves stored SNI with fallback
--   - ordered_leaves_for_handshake() uses stored sigalgs_ext
--   - ssl_client_hello hook calls this (HTTP + stream)
--
-- EXAMPLE:
--   -- Called from http {ssl_client_hello} or stream {ssl_preread}
--   ocsp_module.capture_client_hello()
--   -- Later, in ssl_certificate phase:
--   local sni = ocsp_module.handshake_sni()
--
-- ============================================================================
-- Capture SNI + preferred leaf kind during ssl_client_hello (HTTP and stream).
-- Stores on ngx.ctx for the later ssl_certificate leaf pick / staple:
--   bw_ocsp_sni, bw_ocsp_sigalgs_ext (raw ext 13), bw_ocsp_prefer_kind (coarse).
-- Also rearms the L1 warmer early so a failed timer.at can recover before set_certs/staple.
function _M.capture_client_hello()
	maybe_rearm_l1_warmer()
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

-- ============================================================================
-- _M.handshake_sni(fallback)
-- ============================================================================
-- PURPOSE:
--   Resolve handshake SNI for stream stapling with fallback chain.
--   Checks ssl.server_name(), ctx, then fallback parameter.
--
-- PARAMETERS:
--   fallback (string|nil): SNI to use if others unavailable (lowest priority)
--
-- RETURNS:
--   (string|nil): SNI hostname (non-empty), or nil if all sources empty
--
-- SIDE EFFECTS:
--   - Reads: ngx.ssl.server_name() (stream phase)
--             ngx.ctx.bw_ocsp_sni (HTTP/capture_client_hello)
--             fallback parameter
--   - No writes or state modification
--
-- DESIGN NOTES:
--   - Fallback chain: ssl.server_name() → ctx → fallback → nil
--   - Stream: ssl.server_name() available; HTTP must use ctx
--   - HTTP HTTP: capture_client_hello() populates ctx.bw_ocsp_sni
--   - Empty check: Returns nil for empty strings
--   - Performance: O(1) simple lookups
--
-- RELATED:
--   - _M.capture_client_hello() populates ctx.bw_ocsp_sni (HTTP)
--   - _M.staple() and _M.probe() receive SNI from caller
--   - Stream uses this directly; HTTP uses ctx version
--
-- EXAMPLE:
--   -- In stream ssl_certificate phase
--   local sni = ocsp_module.handshake_sni("default.example.com")
--   if sni then
--     local ok = ocsp_module.staple(store, sni, cert_pem)
--   end
--
-- ============================================================================
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

-- ============================================================================
-- _M.async_validate_response(fingerprint, ocsp_der, issuers, leaf_pem, meta)
-- ============================================================================
-- PURPOSE:
--   Background validator for OCSP responses (off-path, scheduler context).
--   Validates response FFI-side and marks cache as "validated" for TLS path.
--
-- PARAMETERS:
--   fingerprint (string): leaf SPKI fingerprint (64 hex chars)
--   ocsp_der (string): OCSP response DER bytes (required)
--   issuers (table): issuer PEM candidates {issuer_pem, ...}
--   leaf_pem (string): leaf certificate PEM
--   meta (table|nil): ocsp.json metadata (optional)
--
-- RETURNS:
--   (boolean): true if FFI validation succeeded
--             false if validation failed or parameters missing
--
-- SIDE EFFECTS:
--   - Reads: issuers list, leaf/issuer PEMs
--   - Writes: async validation cache via set_shared_validation_result()
--             (status="validated" on success, cleared on failure)
--   - Calls: validate() for each issuer (FFI)
--   - Logging: WARN level on parameter errors
--   - Performance: ~100-300ms per response (10-20ms FFI per issuer, up to 10 issuers)
--
-- DESIGN NOTES:
--   - Off-path: Called by scheduler job outside TLS handshake
--   - No TLS attachment: Just validates and caches result
--   - Cross-handshake: Shares result with concurrent TLS paths via shared dict
--   - Parameter check: Returns false if critical params missing (no throw)
--   - Issuer walk: Tries each issuer candidate until success
--   - Cache write: Only on success (thin chain failures don't block fatter chains)
--   - TTL: 3600s (one hour) for cached validated status
--   - Performance: Much slower than L1 hit (~100ms vs ~1ms), but faster overall
--
-- RELATED:
--   - validate() does the actual FFI validation
--   - ocsp-refresh.py background job calls this
--   - TLS path reads via get_shared_validation_result()
--   - mark_async_validation_done() would replace this
--
-- EXAMPLE:
--   -- From scheduler job context
--   local ocsp_module = require("bunkerweb.ocsp")
--   local ok = ocsp_module.async_validate_response(
--     "abc123...64char",  -- fingerprint
--     ocsp_der_bytes,     -- response DER
--     {issuer1_pem, issuer2_pem},  -- issuers
--     leaf_pem
--   )
--   if ok then
--     ngx.log(ngx.INFO, "OCSP validated background")
--   end
--
-- ============================================================================
-- --- Async OCSP Validation (Off-Path) ----------------------------------------
-- Background validation job: called by scheduler to validate OCSP responses
-- outside the TLS critical path. Marks responses as "validated" when complete,
-- allowing future handshakes to skip validation.
--
-- Usage: Call from scheduler job (ocsp-async-validate.lua or similar):
--   local ocsp = require("bunkerweb.ocsp").internal
--   ocsp.async_validate_response(fingerprint, ocsp_der, issuers, leaf_pem)
--
-- Returns: true if validation succeeded, false otherwise.

function _M.async_validate_response(fingerprint, ocsp_der, issuers, leaf_pem, meta)
	if not fingerprint or not ocsp_der or not issuers or not leaf_pem then
		log(ngx.WARN, "OCSP async_validate_response: missing parameters")
		-- Do not mark DONE — that would skip validate if DONE short-circuit is re-enabled.
		return false
	end

	local ocsp = require("ngx.ocsp")
	if not ocsp or not ocsp.validate_ocsp_response then
		log(ngx.WARN, "OCSP async_validate_response: ngx.ocsp not available")
		return false
	end

	local ssl = require("ngx.ssl")
	local shard_issuer_spki = nil -- No shard pin in async job
	meta = meta or read_ocsp_json(fingerprint)

	for _, issuer_pem in ipairs(issuers) do
		if validate(ocsp, ssl, ocsp_der, leaf_pem, issuer_pem, shard_issuer_spki) then
			log(ngx.DEBUG, "OCSP async validation succeeded: marking response as validated")
			mark_async_validation_done(fingerprint, meta, ocsp_der)
			return true
		end
	end

	log(ngx.WARN, "OCSP async validation failed: response signature invalid")
	mark_async_validation_failed(fingerprint, meta, ocsp_der)
	return false
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

-- Public API defined in the submodules, re-exported unchanged.
local common_api = require("bunkerweb.ocsp_common")
_M.current_ocsp_epoch = common_api.current_ocsp_epoch
_M.format_staple_decision = common_api.format_staple_decision
_M.soften_must_staple = common_api.soften_must_staple
_M.staple_mode = common_api.staple_mode
_M.stapling_enabled = common_api.stapling_enabled
local cert_api = require("bunkerweb.ocsp_cert")
_M.aia_uri_pin_ok = cert_api.aia_uri_pin_ok
_M.ocsp_resp_serial_hex = cert_api.ocsp_resp_serial_hex
local store_api = require("bunkerweb.ocsp_store")
_M.l1_body_matches_disk = store_api.l1_body_matches_disk
_M.ligand_effective_sha = store_api.ligand_effective_sha
_M.ligand_matches = store_api.ligand_matches
_M.ligand_verdict = store_api.ligand_verdict
_M.live_soft_recall_gen = store_api.live_soft_recall_gen
_M.meta_expires_unix = store_api.meta_expires_unix
_M.meta_tombstoned = store_api.meta_tombstoned
_M.cluster_floor_blocks = store_api.cluster_floor_blocks
_M.resolve_leaf_must_staple = store_api.resolve_leaf_must_staple
_M.resp_still_fresh = store_api.resp_still_fresh
_M.serial_blacklist_blocks = store_api.serial_blacklist_blocks
local pin_api = require("bunkerweb.ocsp_pin")
-- Skip-validate = ligand+paged + live allow-pin (sha, gen). Store keeps ligand-only.
_M.canary_paged_body_ok = pin_api.canary_paged_body_ok
_M.clear_peer_refuse = pin_api.clear_peer_refuse
_M.drop_allow_pin = pin_api.drop_allow_pin
_M.ensure_ocsp_bus_dirs = pin_api.ensure_ocsp_bus_dirs
_M.ensure_ocsp_refuse_dir = pin_api.ensure_ocsp_refuse_dir
_M.peer_refuse_blocks = pin_api.peer_refuse_blocks
_M.record_peer_refuse = pin_api.record_peer_refuse
_M.should_skip_peer_bus = pin_api.should_skip_peer_bus
_M.write_allow_pin = pin_api.write_allow_pin
-- Shared CertID / force_ffi latch (HTTP must not diverge from stream).
_M.certid_matches_handshake_leaf = certid_matches_handshake_leaf
_M.mark_ffi_needed = mark_ffi_needed
_M.is_ffi_needed = is_ffi_needed
_M.clear_ffi_needed = clear_ffi_needed
local chain_api = require("bunkerweb.ocsp_chain")
_M.attach_ocsp_staple = chain_api.attach_ocsp_staple
_M.issuer_linked_chain_blocks = chain_api.issuer_linked_chain_blocks
_M.issuer_linked_chain_pem = chain_api.issuer_linked_chain_pem
_M.issuer_path_intermediate_ready = chain_api.issuer_path_intermediate_ready
_M.issuer_path_null_slots = chain_api.issuer_path_null_slots
_M.chain_has_intermediate_must_staple = chain_api.chain_has_intermediate_must_staple
_M.on_ssl_context_swap = chain_api.on_ssl_context_swap
local warmer_api = require("bunkerweb.ocsp_warmer")
_M.start_l1_warmer = warmer_api.start_l1_warmer
_M.warm_l1_from_disk = warmer_api.warm_l1_from_disk

-- ============================================================================
-- FFI Validation Telemetry & Observability
-- ============================================================================
-- Public API for monitoring OCSP FFI performance and cache effectiveness

-- Get FFI validation latency from current request
-- Returns: latency in milliseconds, or nil if not measured
function _M.get_ffi_validation_latency()
	if ngx.ctx and ngx.ctx.bw_ocsp_metrics then
		return ngx.ctx.bw_ocsp_metrics.ffi_validate_ms
	end
	return nil
end

-- Get L1 cache hit status
-- Returns: true if L1 cache hit, false if L1 cache miss, nil if not checked
function _M.get_l1_cache_hit()
	if ngx.ctx and ngx.ctx.bw_ocsp_metrics then
		if ngx.ctx.bw_ocsp_metrics.l1_cache_hit then
			return true
		elseif ngx.ctx.bw_ocsp_metrics.l1_cache_miss then
			return false
		end
	end
	return nil
end

-- Get disk I/O latencies from current request
-- Returns: table with latencies {issuer_pem_ms, meta_json_ms, ocsp_der_ms, cert_parse_ms}
-- Used to track slow disk reads and certificate parsing
function _M.get_disk_io_latencies()
	if ngx.ctx and ngx.ctx.bw_ocsp_disk_io then
		return {
			issuer_pem_ms = ngx.ctx.bw_ocsp_disk_io.issuer_pem_ns and ngx.ctx.bw_ocsp_disk_io.issuer_pem_ns / 1e6
				or nil,
			meta_json_ms = ngx.ctx.bw_ocsp_disk_io.meta_json_ns and ngx.ctx.bw_ocsp_disk_io.meta_json_ns / 1e6 or nil,
			ocsp_der_ms = ngx.ctx.bw_ocsp_disk_io.ocsp_der_ns and ngx.ctx.bw_ocsp_disk_io.ocsp_der_ns / 1e6 or nil,
			cert_parse_ms = ngx.ctx.bw_ocsp_disk_io.cert_parse_ms or nil,
		}
	end
	return {}
end

-- Get DER cache hit status from current handshake
-- Returns: table with {tier1_hit, tier2_hit}
-- Used to monitor certificate parsing cache effectiveness
function _M.get_der_cache_status()
	if ngx.ctx and ngx.ctx.bw_ocsp_metrics then
		return {
			tier1_hit = ngx.ctx.bw_ocsp_metrics.der_cache_tier1_hit or false,
			tier2_hit = ngx.ctx.bw_ocsp_metrics.der_cache_tier2_hit or false,
		}
	end
	return { tier1_hit = false, tier2_hit = false }
end

-- Get all OCSP metrics from current request
-- Returns: comprehensive table with all metrics
-- {
--   ffi_validate_ms: validation latency,
--   l1_cache_hit: true/false/nil,
--   async_deferred: true/false,
--   issuer_pem_ms: disk I/O latency,
--   meta_json_ms: disk I/O latency,
--   ocsp_der_ms: disk I/O latency
-- }
function _M.get_ocsp_metrics()
	if ngx.ctx then
		local metrics = {}

		if ngx.ctx.bw_ocsp_metrics then
			for k, v in pairs(ngx.ctx.bw_ocsp_metrics) do
				metrics[k] = v
			end
		end

		if ngx.ctx.bw_ocsp_disk_io then
			if ngx.ctx.bw_ocsp_disk_io.issuer_pem_ns then
				metrics.issuer_pem_ms = ngx.ctx.bw_ocsp_disk_io.issuer_pem_ns / 1e6
			end
			if ngx.ctx.bw_ocsp_disk_io.meta_json_ns then
				metrics.meta_json_ms = ngx.ctx.bw_ocsp_disk_io.meta_json_ns / 1e6
			end
			if ngx.ctx.bw_ocsp_disk_io.ocsp_der_ns then
				metrics.ocsp_der_ms = ngx.ctx.bw_ocsp_disk_io.ocsp_der_ns / 1e6
			end
		end

		return metrics
	end
	return {}
end

-- Get FFI validation cache statistics (hit/miss rates).
-- Returns: {hits: number, misses: number, hit_rate: 0-100}
-- Used to monitor multi-issuer handshake cache effectiveness.
function _M.get_ffi_cache_stats()
	if not ngx.ctx then
		return { hits = 0, misses = 0, hit_rate = 0 }
	end

	local hits = ngx.ctx.bw_ffi_cache_hits or 0
	local misses = ngx.ctx.bw_ffi_cache_misses or 0
	local total = hits + misses

	local hit_rate = 0
	if total > 0 then
		hit_rate = (hits / total) * 100
	end

	return {
		hits = hits,
		misses = misses,
		total = total,
		hit_rate = hit_rate,
	}
end

-- Mark FFI validation as async (deferred off-path)
-- Called by TLS path when async result available
function _M.mark_ffi_async_deferred()
	if ngx.ctx then
		if not ngx.ctx.bw_ocsp_metrics then
			ngx.ctx.bw_ocsp_metrics = {}
		end
		ngx.ctx.bw_ocsp_metrics.async_deferred = true
	end
end

-- Mark FFI validation as L1 cache hit
-- Called by TLS path when L1 cache has verified response
function _M.mark_l1_cache_hit()
	if ngx.ctx then
		if not ngx.ctx.bw_ocsp_metrics then
			ngx.ctx.bw_ocsp_metrics = {}
		end
		ngx.ctx.bw_ocsp_metrics.l1_cache_hit = true
	end
end

-- ============================================================================
-- Disk I/O Optimization Wrapper
-- ============================================================================
-- Internal function to track disk I/O latency
-- Wraps read_file() calls with nanosecond precision timing
local function read_file_with_timing(file_path, metric_key)
	local t_start = ngx.hrtime and ngx.hrtime() or nil
	local content = read_file(file_path)

	if t_start and ngx.ctx then
		local elapsed_ns = ngx.hrtime() - t_start
		if not ngx.ctx.bw_ocsp_disk_io then
			ngx.ctx.bw_ocsp_disk_io = {}
		end
		ngx.ctx.bw_ocsp_disk_io[metric_key] = elapsed_ns

		-- Log slow disk reads (>5ms)
		local elapsed_ms = elapsed_ns / 1e6
		if elapsed_ms > 5 then
			log(ngx.WARN, "OCSP disk I/O slow (" .. metric_key .. "): " .. string.format("%.1f", elapsed_ms) .. "ms")
		end
	end

	return content
end

-- Public API: Get disk I/O monitoring function
-- Used to track slow disk reads for debugging
function _M.read_file_with_timing(file_path, metric_key)
	return read_file_with_timing(file_path, metric_key)
end

return _M
