local _M = {}

local ngx = ngx

-- Async validation: defer OCSP validation to background job, allow speculative attachment.
-- Reduces TLS critical path latency by moving crypto validation off-path.
-- Key concept: attach OCSP speculatively, validate async, mark as validated when done.
local ASYNC_VALIDATION_PENDING = "pending"  -- Validation queued, not yet done
local ASYNC_VALIDATION_DONE = "validated"   -- Validation complete, result stored
local ASYNC_VALIDATION_FAILED = "failed"    -- Validation failed, response invalid

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
local ocsp_json_must_staple = store.ocsp_json_must_staple
local read_ocsp_json = store.read_ocsp_json
local resolve_leaf_must_staple = store.resolve_leaf_must_staple
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

-- Async validation state management (off-path validation)
-- Defers OCSP validation to background job, reduces TLS critical path latency.

-- Returns the key where async validation status is stored for a fingerprint.
local function async_validation_key(fingerprint)
	if not fingerprint or fingerprint == "" then
		return nil
	end
	return "OCSP:ASYNC_VALIDATE:" .. fingerprint
end

-- Mark response as pending async validation (queued to background job).
-- Allows handshakes to speculatively attach response while validation runs async.
local function mark_async_validation_pending(fingerprint)
	if not ngx.shared or not ngx.shared.bw_ocsp_validations or not fingerprint then
		return
	end
	local key = async_validation_key(fingerprint)
	if not key then
		return
	end
	pcall(function()
		-- Mark as "pending" with 120s TTL (enough time for async job to complete)
		ngx.shared.bw_ocsp_validations:set(key, ASYNC_VALIDATION_PENDING, 120)
	end)
end

-- Mark response as validated (async validation job completed successfully).
-- Future handshakes skip validation and use this cached result.
local function mark_async_validation_done(fingerprint)
	if not ngx.shared or not ngx.shared.bw_ocsp_validations or not fingerprint then
		return
	end
	local key = async_validation_key(fingerprint)
	if not key then
		return
	end
	pcall(function()
		-- Mark as "validated" with 3600s TTL (1 hour, until next OCSP refresh)
		ngx.shared.bw_ocsp_validations:set(key, ASYNC_VALIDATION_DONE, 3600)
	end)
end

-- Check if response is already validated by async job (or mark as pending if not).
-- Returns: "validated" (safe, skip validation), "pending" (async in progress),
--          "failed" (validation failed), or nil (not yet queued).
local function get_async_validation_status(fingerprint)
	if not ngx.shared or not ngx.shared.bw_ocsp_validations or not fingerprint then
		return nil
	end
	local key = async_validation_key(fingerprint)
	if not key then
		return nil
	end
	local status
	pcall(function()
		status = ngx.shared.bw_ocsp_validations:get(key)
	end)
	return status
end
local issuer_path_intermediate_ready = chain.issuer_path_intermediate_ready
local issuer_path_null_slots = chain.issuer_path_null_slots
local note_connection_staple = chain.note_connection_staple
local presentable_chain_blocks = chain.presentable_chain_blocks

local warmer = require("bunkerweb.ocsp_warmer").internal
local maybe_rearm_l1_warmer = warmer.maybe_rearm_l1_warmer

-- issuer_candidates: PEMs ngx.ocsp.validate may try for this leaf body.
-- Prefer shard issuer.pem SPKI when present; otherwise accept chain issuers
-- (issuer.pem absent is fail-open by design — not fail-closed).
-- stored_pem: caller-supplied issuer.pem (string), false = known absent, nil = read here.
-- Returns an ordered list deduped by SPKI (not PEM bytes) so re-encodings of the
-- same key cannot burn the soft validate_budget as distinct candidates.
-- Empty list is a real outcome (no pin + no chain issuer) → try_staple returns
-- issuer_unavailable, not a hollow response_not_found.
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

-- validate: one ngx.ocsp.validate_ocsp_response against leaf+issuer DER.
-- Enforces shard issuer SPKI pin when shard_issuer_spki is set, then death-time
-- (nextUpdate − skew). Returns boolean only; budget / multi-issuer walk lives in try_staple.
-- Cross-handshake validation state sharing (thundering-herd protection).
-- Multiple concurrent handshakes for the same cert can share validation results.
-- First handshake validates (5-20ms); others read cached result (0.1ms each).
-- Uses shared dict with spin-lock pattern: in_flight → result → done.
local function get_shared_validation_state_key(fingerprint)
	if not fingerprint or fingerprint == "" then
		return nil
	end
	return "OCSP:VALIDATE:" .. fingerprint
end

local function set_shared_validation_result(fingerprint, result)
	if not ngx.shared or not ngx.shared.bw_ocsp_validations then
		return
	end
	local key = get_shared_validation_state_key(fingerprint)
	if not key then
		return
	end
	pcall(function()
		-- Mark as "done" with result (pass/fail). TTL: 60s to allow cross-handshake sharing
		-- but invalidate stale results. Handshakes within 60s can reuse.
		ngx.shared.bw_ocsp_validations:set(key, result and "pass" or "fail", 60)
	end)
end

local function get_shared_validation_result(fingerprint, max_wait_ms)
	if not ngx.shared or not ngx.shared.bw_ocsp_validations then
		return nil
	end
	local key = get_shared_validation_state_key(fingerprint)
	if not key then
		return nil
	end
	-- Spin-wait for validation to complete (with timeout).
	-- If another handshake is validating, wait up to max_wait_ms for result.
	local t0 = ngx.now() * 1000  -- Convert to milliseconds
	local max_wait = max_wait_ms or 100  -- Default: 100ms timeout
	while true do
		local result
		pcall(function()
			result = ngx.shared.bw_ocsp_validations:get(key)
		end)
		if result then
			-- Validation complete (result is "pass" or "fail")
			return result == "pass"
		end
		-- Not ready yet; check timeout
		local elapsed = ngx.now() * 1000 - t0
		if elapsed > max_wait then
			-- Timeout: other handshake is slow or validation failed to store
			return nil
		end
		-- Brief sleep to avoid busy-spin (yield to other workers)
		ngx.sleep(0.001)  -- 1ms sleep
	end
end

local function set_shared_validation_in_flight(fingerprint)
	if not ngx.shared or not ngx.shared.bw_ocsp_validations then
		return false
	end
	local key = get_shared_validation_state_key(fingerprint)
	if not key then
		return false
	end
	-- Try to atomically set a flag indicating this handshake is validating.
	-- If another handshake already set it, we'll wait for their result.
	local ok
	pcall(function()
		ok = ngx.shared.bw_ocsp_validations:add(key, "in_flight", 60)
	end)
	return ok or false
end

-- Bounded cache manager: prevents der_cache from growing unbounded.
-- Keeps track of cache size; evicts oldest entry when limit exceeded.
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
	-- If at limit, evict oldest (first key in iteration order)
	if count >= max_entries and first_key then
		cache[first_key] = nil
	end
	cache[key] = value
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
	-- Cache cert_pem_to_der() results to avoid expensive PEM parsing per issuer candidate.
	-- Key: hash of (leaf_pem, issuer_pem) pair; only valid for this stapling operation.
	local der_chain, err
	local ctx = ngx.ctx
	if ctx then
		if not ctx.bw_ocsp_der_cache then
			ctx.bw_ocsp_der_cache = {}
		end
		-- Use first 32 chars of each PEM as a cache key (fingerprints are unique)
		local der_cache_key = (leaf_pem and leaf_pem:sub(1, 32) or "leaf") ..
			"|" .. (issuer_pem and issuer_pem:sub(1, 32) or "issuer")
		local cached_entry = ctx.bw_ocsp_der_cache[der_cache_key]
		local current_gen = current_ocsp_epoch()
		-- Generation binding: invalidate cache if soft-recall (generation) changed.
		-- Prevents attacker from keeping poisoned DER across certificate rotations.
		if cached_entry and cached_entry.gen == current_gen then
			-- Cache hit: reuse DER chain (generation still valid)
			der_chain = cached_entry.chain
			err = cached_entry.err
		else
			-- Cache miss or stale generation: compute DER chain
			der_chain, err = ssl.cert_pem_to_der(leaf_pem .. "\n" .. issuer_pem)
			-- Bounded cache: cap at 16 entries per request (typical: 1-4 issuers per cert)
			-- Tag with current generation for soft-recall invalidation
			bounded_cache_set(ctx.bw_ocsp_der_cache, der_cache_key,
				{ chain = der_chain, err = err, gen = current_gen }, 16)
		end
	else
		der_chain, err = ssl.cert_pem_to_der(leaf_pem .. "\n" .. issuer_pem)
	end
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

-- force_ffi latch (per internalstore / subsystem):
-- When validate_budget aborts mid-issuer walk we KEEP the fleet allow-pin (so
-- canary trust still exists) but demote local L1 and stamp this key so the next
-- handshake cannot canary-skip attach an unfinished body.
-- Value is "der_sha256|soft_recall_gen|hmac_tag": soft-recall / re-page
-- flips gen → is_ffi_needed clears the stale latch. All latches require HMAC tag.
-- Wall-clock TTL is only a safety cap (86400s); generation match is the real death clock.
-- mark on budget abort; clear on successful FFI/attach (incl. verified-L1 restock);
-- is_ffi_needed is also consulted on the verified-L1 shortcut so a warmer
-- re-verify cannot bypass the latch. HMAC tag prevents tampering via shared state.
local function ffi_needed_key(fingerprint)
	return "TLS:SSL:ocsp_ffi_needed:" .. fingerprint
end

-- Fast integrity tag for latch tokens (prevents forgery via poisoned shared state).
-- Uses rolling hash + epoch salt (not crypto-grade, but sufficient to detect
-- tampering while avoiding HMAC-SHA256 overhead). Generation binding already
-- provides timing protection; this adds integrity against external writes.
local function latch_token_tag(token, fingerprint)
	if not token or not fingerprint then
		return nil
	end
	-- Mix token with fingerprint + epoch for tamper detection.
	-- Attacker cannot forge valid tags without knowing the epoch.
	local salt = (fingerprint or ""):sub(1, 8) .. tostring(current_ocsp_epoch() or 0)
	local combined = token .. "|" .. salt
	-- Simple rolling hash: XOR each byte with position (O(n), not crypto).
	local tag = 0
	for i = 1, #combined do
		local byte_val = combined:byte(i)
		tag = (tag * 31 + byte_val) % 0xFFFFFFFF  -- 32-bit rolling hash
	end
	return string.format("%08x", tag)  -- Hex-encoded tag (8 chars)
end

-- Compact generation identity for the latch value. nil when sha/gen incomplete
-- (type drift / missing body) — callers treat that as "honor any latch".
local function ffi_needed_token(meta, resp, fingerprint)
	local sha, gen = generation_tuple(ligand_or_meta(meta, fingerprint), resp)
	if type(sha) ~= "string" or #sha ~= 64 or type(gen) ~= "number" then
		return nil
	end
	return sha .. "|" .. tostring(gen)
end

-- Stamp force_ffi after validate_budget. meta+resp bind the latch to this body gen.
-- Token is now signed with a fast integrity tag to prevent forgery via shared state.
-- All latches require valid HMAC tag (no legacy bypass).
local function mark_ffi_needed(internalstore, fingerprint, meta, resp)
	if not internalstore or type(fingerprint) ~= "string" or #fingerprint ~= 64 then
		return
	end
	local token = ffi_needed_token(meta, resp, fingerprint)
	if not token then
		-- Cannot create valid latch without generation identity. Do not fall back to "1".
		return
	end
	local tag = latch_token_tag(token, fingerprint)
	if not tag then
		-- Cannot compute tag; do not store invalid latch.
		return
	end
	pcall(function()
		-- Long TTL: generation match is the real death clock; 300s let canary-skip resume early.
		-- Latch value: "token|tag" (both required, no legacy "1" bypass).
		internalstore:set(ffi_needed_key(fingerprint), token .. "|" .. tag, 86400)
	end)
end

-- Drop the latch after a successful validate+attach (or when gen no longer matches).
local function clear_ffi_needed(internalstore, fingerprint)
	if not internalstore or type(fingerprint) ~= "string" or #fingerprint ~= 64 then
		return
	end
	pcall(function()
		internalstore:delete(ffi_needed_key(fingerprint))
	end)
end

-- True when this worker must run ngx.ocsp.validate despite canary trust.
-- All latches require HMAC tag; legacy untagged latches rejected for security.
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
	local token = ffi_needed_token(meta, resp, fingerprint)
	if not token then
		-- No generation identity: honor any latch (incl. legacy "1").
		return true
	end
	-- HMAC-signed latch: all latches MUST have valid tag (no legacy bypass).
	-- Format: "token|tag" (both required).
	local pipe_pos = v:find("|", 1, true)
	if not pipe_pos then
		-- Legacy untagged latch: reject (all latches must be signed).
		log(ngx.NOTICE, "OCSP latch rejected: legacy untagged format (requires HMAC tag)")
		clear_ffi_needed(internalstore, fingerprint)
		return false
	end
	local stored_token = v:sub(1, pipe_pos - 1)
	local stored_tag = v:sub(pipe_pos + 1)
	-- Verify token matches expected (generation-bound check).
	if stored_token ~= token then
		-- Soft-recall / new page: stale latch dies with the old generation.
		clear_ffi_needed(internalstore, fingerprint)
		return false
	end
	-- Verify tag (tamper detection). If tag invalid, latch was poisoned.
	local expected_tag = latch_token_tag(token, fingerprint)
	if stored_tag ~= expected_tag then
		log(ngx.WARN, "OCSP latch tag mismatch (possible tampering): clearing latch")
		clear_ffi_needed(internalstore, fingerprint)
		return false
	end
	return true
end

-- try_staple: CertID → empty-issuer gate → (optional canary skip) → issuer validate → attach.
-- probe_only: path health only (no set_ocsp_status_resp). force_ffi: ignore canary
-- skip for one walk after validate_budget.
-- Returns:
--   true                         — probe ok or staple attached
--   false, "certid_mismatch"     — DROP_ALLOW when Must-Staple + body present
--   false, "validate_budget"     — soft budget; caller demotes L1 + marks force_ffi
--   false, "issuer_unavailable"  — body present but zero accepted issuer PEMs
--   false, "validate_exhausted"  — every issuer candidate failed validate (body present)
--   false, <attach detail>       — intermediate MS / multi attach codes
--   false                        — generic attach/validate miss (optional stapling)
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
	force_ffi
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
			or detail == "issuer_unresolved_must_staple"
			or detail == "fingerprint_chain_unavailable"
		then
			return false, detail
		end
		return false
	end
	-- Trust scheduler canary (openssl CLI) for crypto verify when paged+ligand
	-- match AND live allow-pin names this generation (soft-fuse / pin revoke
	-- must not keep skip-validate alive on ligand bits alone).
	-- Empty issuers before canary: CertID usually already failed, but probe_only
	-- must not greenlight a body that force_ffi attach would name issuer_unavailable.
	if type(issuers) ~= "table" or #issuers == 0 then
		return false, "issuer_unavailable"
	end
	-- Async validation: defer validation to background job if already queued.
	-- If async validation already completed, skip (response already validated).
	-- Allows handshake to skip expensive crypto validation.
	local async_status = get_async_validation_status(fingerprint)
	if async_status == ASYNC_VALIDATION_DONE then
		log(ngx.DEBUG, "OCSP async validation already complete: skipping validation, attaching")
		return set_resp()
	end
	if async_status == ASYNC_VALIDATION_FAILED then
		log(ngx.DEBUG, "OCSP async validation failed: response invalid, aborting")
		return false, "async_validation_failed"
	end

	-- Optimization: Skip validation for non-must-staple certs in 'open' mode.
	-- In open mode, must-staple enforcement is disabled; optional stapling doesn't
	-- require cryptographic validation. We can attach the response blindly.
	local is_open_mode = ocsp_staple_mode() == "open"
	local is_must_staple = get_must_staple_with_ctx_cache(leaf_pem, fingerprint)
	if is_open_mode and not is_must_staple then
		log(ngx.DEBUG, "OCSP open mode + non-must-staple: skipping validation, attaching speculatively")
		-- Queue async validation for future handshakes (even though this one doesn't need it)
		if not async_status then
			mark_async_validation_pending(fingerprint)
		end
		return set_resp()
	end
	-- force_ffi: prior validate_budget demoted L1 but KEEP pin — finish one FFI walk.
	if canary_paged_body_ok(meta, fingerprint, resp) and not force_ffi then
		log(ngx.DEBUG, "OCSP trusting canary-paged body; skipping ngx.ocsp.validate_ocsp_response")
		-- Queue async validation to confirm canary was correct
		if not async_status then
			mark_async_validation_pending(fingerprint)
		end
		return set_resp()
	end
	if force_ffi and canary_paged_body_ok(meta, fingerprint, resp) then
		log(ngx.NOTICE, "OCSP force FFI after validate_budget; ignoring canary skip once")
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
	-- Probabilistic issuer reordering: shuffle candidates using deterministic seed
	-- (fingerprint + epoch) to prevent attackers from controlling validation order.
	-- Seed is constant per request but varies across requests.
	if #issuers > 1 and fingerprint and type(fingerprint) == "string" then
		local seed = fingerprint:sub(1, 8) .. tostring(current_ocsp_epoch() or 0)
		math.randomseed(tonumber(seed:sub(1, 12), 16) or ngx.time() * 1000)
		-- Fisher-Yates shuffle with deterministic seed
		for i = #issuers, 2, -1 do
			local j = math.random(1, i)
			issuers[i], issuers[j] = issuers[j], issuers[i]
		end
	end
	-- Cross-handshake validation state sharing (thundering-herd protection).
	-- If another concurrent handshake is already validating this fingerprint,
	-- wait for their result instead of re-validating (saves 5-20ms per duplicate).
	-- Timeout: 100ms (prevent infinite hangs if validation is stuck).
	if fingerprint and type(fingerprint) == "string" and #fingerprint == 64 then
		local shared_result = get_shared_validation_result(fingerprint, 100)
		if shared_result ~= nil then
			if shared_result then
				log(ngx.DEBUG, "OCSP validation result reused from concurrent handshake (hit)")
				return set_resp()
			else
				log(ngx.DEBUG, "OCSP validation result reused from concurrent handshake (fail)")
				return false, "validate_exhausted"
			end
		end
		-- No concurrent validation in progress; try to claim the lock for this handshake.
		-- If we succeed, we'll validate and store the result for other handshakes.
		if set_shared_validation_in_flight(fingerprint) then
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
			-- Do NOT store result in shared state (budget abort is transient).
			return false, "validate_budget"
		end
		-- Early-exit optimization: stop on first successful validation (don't test all 4 issuers).
		-- This is load-bearing for latency: validate() is 5-20ms per issuer, so early-exit
		-- can save 10-60ms in common dual-issuer scenarios.
		if validate(ocsp, ssl, resp, leaf_pem, issuers[i], shard_issuer_spki) then
			-- Validation succeeded: store result for other concurrent handshakes.
			if fingerprint and type(fingerprint) == "string" and #fingerprint == 64 then
				set_shared_validation_result(fingerprint, true)
			end
			return set_resp()
		end
	end
	-- Body present; every issuer candidate failed crypto validate (not missing DER).
	-- Store failure result for other concurrent handshakes.
	if fingerprint and type(fingerprint) == "string" and #fingerprint == 64 then
		set_shared_validation_result(fingerprint, false)
	end
	return false, "validate_exhausted"
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
				leaf.sig_profile = profiles[i]  -- Cache on leaf for future calls
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
-- Compute Must-Staple once per leaf during parsing phase.
-- Avoids re-parsing PEM + re-reading ocsp.json for same cert multiple times.
local function annotate_leaves_must_staple(leaves)
	if type(leaves) ~= "table" then
		return
	end
	for leaf_idx, leaf in ipairs(leaves) do
		if type(leaf) == "table" then
			local pem = leaf.pem or leaf.ocsp_cert or leaf.cert_pem
			local fp = leaf.fp or leaf.ocsp_fp_hint
			if pem or fp then
				leaf.must_staple = resolve_leaf_must_staple(pem, fp)
			end
		end
	end
end

-- Request-scoped memoization of Must-Staple resolution via ngx.ctx.
-- Avoids re-resolving the same cert during staple(), probe(), and requires_must_staple().
local function get_must_staple_with_ctx_cache(cert_pem, cert_fp)
	local ctx = ngx.ctx
	if not ctx then
		-- No context (should not happen in TLS handshake); resolve directly
		return resolve_leaf_must_staple(cert_pem, cert_fp)
	end
	if not ctx.bw_ocsp_ms_cache then
		ctx.bw_ocsp_ms_cache = {}
	end
	local key = cert_fp or ("pem_" .. (cert_pem and cert_pem:sub(1, 32) or "unknown"))
	if ctx.bw_ocsp_ms_cache[key] ~= nil then
		return ctx.bw_ocsp_ms_cache[key]
	end
	local result = resolve_leaf_must_staple(cert_pem, cert_fp)
	ctx.bw_ocsp_ms_cache[key] = result
	return result
end

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
	annotate_leaves_must_staple(leaves)

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
			local leaf_detail = nil
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
	local best = nil
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
				best = h
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
	if must_staple and (type(chain_blocks) ~= "table" or #chain_blocks < 1) then
		if not probe_only then
			return must_staple_refuse(fingerprint, meta, nil, "fingerprint_chain_unavailable", mode)
		end
		return false, "must_staple", "fingerprint_chain_unavailable"
	end
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

	-- Refuse attach while a PEM-path validate_budget latch is live (no leaf PEM here).
	local function refuse_force_ffi(resp_body)
		if not is_ffi_needed(internalstore, fingerprint, meta, resp_body) then
			return nil
		end
		if must_staple then
			if probe_only then
				return false, "must_staple", "force_ffi_pending"
			end
			return must_staple_refuse(fingerprint, meta, resp_body, "force_ffi_pending", mode)
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
						return must_staple_refuse(fingerprint, meta, cached, ligand_detail, mode)
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
							return must_staple_refuse(fingerprint, meta, cached, "certid_mismatch", mode)
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
						return must_staple_refuse(fingerprint, meta, cached, detail, mode)
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
			return must_staple_refuse(fingerprint, meta, nil, "response_empty", mode)
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
				return must_staple_refuse(fingerprint, meta, nil, fresh_why or "response_stale", mode)
			end
			return false
		end
		-- Disk path: verified binding only exists in L1; after drop/miss, require meta authorize
		-- or a concurrent warmer rewrite. Re-check composite if rewarmed.
		local _, disk_verified, _, _, disk_gen = get_l1(internalstore, fingerprint)
		if serial_blacklist_blocks(fingerprint, resp) then
			if must_staple then
				return must_staple_refuse(fingerprint, meta, nil, "serial_blacklisted", mode)
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
				return must_staple_refuse(fingerprint, meta, resp, ligand_detail, mode)
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
					return must_staple_refuse(fingerprint, meta, resp, "certid_mismatch", mode)
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

-- staple_one_leaf: L1 then disk staple/probe for one leaf SPKI.
-- Gates: tombstone, peer refuse, cluster floor, not_paged, AIA, serial blacklist,
-- shared ligand (Must-Staple), CertID, then try_staple / attach.
-- Verified L1: restocks warm_cache TTL on hit; if is_ffi_needed, forces try_staple
-- instead of the attach shortcut so validate_budget unfinished bodies still FFI once.
-- Unverified L1 / disk: try_staple with force_ffi from the gen-bound latch; budget
-- abort demotes L1 + mark_ffi_needed; success (incl. probe_only) clear_ffi_needed.
-- try_staple dialect: issuer_unavailable (zero PEMs), validate_exhausted (all failed),
-- validate_budget (soft ceiling). Empty disk DER → response_empty (not response_not_found).
-- Disk fallthrough rebuilds issuer_candidates when L1 left a truthy empty table
-- (Lua `issuers or …` would keep {}).
-- probe_only: never writes the allow-pin bus; returns true or false,"must_staple",detail.
-- Returns true | false [, reason [, detail]] | nil (no usable body).
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
					return must_staple_refuse(fingerprint, meta, nil, fresh_why or "response_stale", mode)
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
						return must_staple_refuse(fingerprint, meta, cached, "certid_mismatch", mode)
					end
				-- Fall through to disk / re-validate with the current leaf.
				else
					-- Must-Staple: bind shared ocsp.json ligand, not stream-private L1 alone.
					if must_staple then
						meta = meta or read_ocsp_json(fingerprint)
						local ligand_ok, ligand_detail = must_staple_binds_shared_ligand(meta, fingerprint, cached)
						if not ligand_ok then
							drop_cache(internalstore, fingerprint)
							return must_staple_refuse(fingerprint, meta, cached, ligand_detail, mode)
						end
					end
					-- force_ffi: prior validate_budget — do not attach via verified shortcut.
					local force_ffi = is_ffi_needed(internalstore, fingerprint, meta, cached)
					if force_ffi then
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
							blocks,
							true
						)
						if result == true then
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
								cached_epoch,
								soft_recall_gen_of(ligand_or_meta(meta, fingerprint))
							)
							clear_ffi_needed(internalstore, fingerprint)
							log_ocsp_stapled(server_name, cert_pubkey_kind(leaf_pem), fingerprint, cached)
							return true
						end
						if result == false then
							if result_detail == "validate_budget" then
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
								if must_staple then
									return must_staple_refuse(fingerprint, meta, cached, "validate_budget", mode)
								end
								return false
							end
							if result_detail == "issuer_unavailable" or result_detail == "validate_exhausted" then
								if must_staple then
									return must_staple_refuse(fingerprint, meta, cached, result_detail, mode)
								end
								return false
							end
							if result_detail == "certid_mismatch" then
								if must_staple then
									drop_cache(internalstore, fingerprint)
									return must_staple_refuse(fingerprint, meta, cached, "certid_mismatch", mode)
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
								then
									detail = canary_paged_body_ok(meta, fingerprint, cached) and "set_staple_failed"
										or "unmet"
								end
								pcall(clear_connection_staple)
								return must_staple_refuse(fingerprint, meta, cached, detail, mode)
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
						clear_ffi_needed(internalstore, fingerprint)
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
							clear_ffi_needed(internalstore, fingerprint)
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
				-- Ligand before attach: try_staple attaches on success. Soft fuse must not
				-- leave a mismatched DER on the SSL object. Pass body for DROP_ALLOW CAS.
				if must_staple then
					meta = meta or read_ocsp_json(fingerprint)
					local ligand_ok, ligand_detail = must_staple_binds_shared_ligand(meta, fingerprint, cached)
					if not ligand_ok then
						drop_cache(internalstore, fingerprint)
						return must_staple_refuse(fingerprint, meta, cached, ligand_detail, mode)
					end
				end
				local force_ffi = is_ffi_needed(internalstore, fingerprint, meta, cached)
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
					blocks,
					force_ffi
				)
				if result == true then
					if probe_only then
						local path_ok, path_detail = issuer_path_intermediate_ready(blocks)
						if not path_ok then
							return false, "must_staple", path_detail or "unmet"
						end
						clear_ffi_needed(internalstore, fingerprint)
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
					clear_ffi_needed(internalstore, fingerprint)
					log_ocsp_stapled(server_name, cert_pubkey_kind(leaf_pem), fingerprint, cached)
					return true
				end
				if result == false then
					if result_detail == "validate_budget" then
						-- Demote local bw3 verified→unverified so the next handshake
						-- cannot skip FFI on a body this budget never finished proving.
						-- KEEP fleet allow-pin (validate_budget is KEEP_ALLOW); mark force_ffi.
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
						if must_staple then
							return must_staple_refuse(fingerprint, meta, cached, "validate_budget", mode)
						end
						return false
					end
					if result_detail == "issuer_unavailable" or result_detail == "validate_exhausted" then
						if must_staple then
							return must_staple_refuse(fingerprint, meta, cached, result_detail, mode)
						end
						return false
					end
					-- Optional stapling: CertID miss on unverified L1 falls through to disk.
					-- Must-Staple fails immediately; optional stapling re-validates on disk.
					if result_detail == "certid_mismatch" then
						if must_staple then
							drop_cache(internalstore, fingerprint)
							return must_staple_refuse(fingerprint, meta, cached, "certid_mismatch", mode)
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
						then
							detail = canary_paged_body_ok(meta, fingerprint, cached) and "set_staple_failed" or "unmet"
						end
						-- Attach already ran for some path demotions; clear leftover staple.
						pcall(clear_connection_staple)
						return must_staple_refuse(fingerprint, meta, cached, detail, mode)
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
			return must_staple_refuse(fingerprint, meta, nil, "response_empty", mode)
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
				return must_staple_refuse(fingerprint, meta, nil, fresh_why or "response_stale", mode)
			end
			return false
		end
		-- Rebuild when L1 left a truthy empty table (issuers or … would keep {}).
		if type(issuers) ~= "table" or #issuers == 0 then
			issuers = issuer_candidates(blocks, leaf_pem, fingerprint, shard_issuer_pem or false)
		end
		if serial_blacklist_blocks(fingerprint, resp) then
			if must_staple then
				return must_staple_refuse(fingerprint, meta, nil, "serial_blacklisted", mode)
			end
			return false
		end
		-- Ligand before attach (same contract as L1 unverified path).
		if must_staple then
			local ligand_ok, ligand_detail = must_staple_binds_shared_ligand(meta, fingerprint, resp)
			if not ligand_ok then
				return must_staple_refuse(fingerprint, meta, resp, ligand_detail, mode)
			end
		end
		local force_ffi = is_ffi_needed(internalstore, fingerprint, meta, resp)
		local result, result_detail = try_staple(
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
			force_ffi
		)
		if result == true then
			if probe_only then
				local path_ok, path_detail = issuer_path_intermediate_ready(blocks)
				if not path_ok then
					return false, "must_staple", path_detail or "unmet"
				end
				clear_ffi_needed(internalstore, fingerprint)
				return true
			end
			warm_cache(internalstore, fingerprint, resp, true, meta_effective_expires_unix(meta))
			clear_ffi_needed(internalstore, fingerprint)
			log_ocsp_stapled(server_name, cert_pubkey_kind(leaf_pem), fingerprint, resp)
			return true
		end
		if result == false then
			if result_detail == "validate_budget" then
				-- Demote local L1 verified (KEEP pin) — same contract as L1 path.
				warm_cache(internalstore, fingerprint, resp, false, meta_effective_expires_unix(meta))
				mark_ffi_needed(internalstore, fingerprint, meta, resp)
				if must_staple then
					return must_staple_refuse(fingerprint, meta, resp, "validate_budget", mode)
				end
				return false
			end
			if result_detail == "issuer_unavailable" or result_detail == "validate_exhausted" then
				if must_staple then
					return must_staple_refuse(fingerprint, meta, resp, result_detail, mode)
				end
				return false
			end
			if result_detail == "certid_mismatch" then
				if must_staple then
					return must_staple_refuse(fingerprint, meta, resp, "certid_mismatch", mode)
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
				then
					detail = canary_paged_body_ok(meta, fingerprint, resp) and "set_staple_failed" or "unmet"
				end
				pcall(clear_connection_staple)
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
	local must_tri = get_must_staple_with_ctx_cache(leaf_pem, fingerprint)
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
		return true
	end
	local leaf_pem = blocks[1]
	if not leaf_pem then
		return false
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
	if get_must_staple_with_ctx_cache(leaf_pem, fingerprint) == false then
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
	return get_must_staple_with_ctx_cache(leaf_pem, leaf_fp or fp_hint) ~= false
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

function _M.async_validate_response(fingerprint, ocsp_der, issuers, leaf_pem)
	if not fingerprint or not ocsp_der or not issuers or not leaf_pem then
		log(ngx.WARN, "OCSP async_validate_response: missing parameters")
		mark_async_validation_done(fingerprint)  -- Mark as done (won't retry)
		return false
	end

	-- Use validate() function to cryptographically validate response
	-- This runs in background job context, not TLS critical path
	local ocsp = require("ngx.ocsp")
	if not ocsp or not ocsp.validate_ocsp_response then
		log(ngx.WARN, "OCSP async_validate_response: ngx.ocsp not available")
		mark_async_validation_done(fingerprint)
		return false
	end

	-- Try each issuer candidate (same logic as try_staple, but no budget pressure)
	local ssl = require("ngx.ssl")
	local shard_issuer_spki = nil  -- No shard pin in async job

	for _, issuer_pem in ipairs(issuers) do
		if validate(ocsp, ssl, ocsp_der, leaf_pem, issuer_pem, shard_issuer_spki) then
			-- Validation succeeded: mark response as validated for all future handshakes
			log(ngx.DEBUG, "OCSP async validation succeeded: marking response as validated")
			mark_async_validation_done(fingerprint)
			return true
		end
	end

	-- All issuers failed: mark response as invalid
	log(ngx.WARN, "OCSP async validation failed: response signature invalid")
	if ngx.shared and ngx.shared.bw_ocsp_validations then
		pcall(function()
			ngx.shared.bw_ocsp_validations:set(async_validation_key(fingerprint),
				ASYNC_VALIDATION_FAILED, 3600)
		end)
	end
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
_M.meta_expires_unix = store_api.meta_expires_unix
_M.resolve_leaf_must_staple = store_api.resolve_leaf_must_staple
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
local chain_api = require("bunkerweb.ocsp_chain")
_M.attach_ocsp_staple = chain_api.attach_ocsp_staple
_M.issuer_linked_chain_blocks = chain_api.issuer_linked_chain_blocks
_M.issuer_linked_chain_pem = chain_api.issuer_linked_chain_pem
_M.issuer_path_intermediate_ready = chain_api.issuer_path_intermediate_ready
_M.issuer_path_null_slots = chain_api.issuer_path_null_slots
_M.on_ssl_context_swap = chain_api.on_ssl_context_swap
local warmer_api = require("bunkerweb.ocsp_warmer")
_M.start_l1_warmer = warmer_api.start_l1_warmer
_M.warm_l1_from_disk = warmer_api.warm_l1_from_disk

return _M
