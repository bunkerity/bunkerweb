--[[
================================================================================
OCSP Must-Staple Module: Detection, Caching, and Enforcement
================================================================================

MODULE OVERVIEW:
Detects and enforces Must-Staple requirements using tri-state logic (true/false/nil).
Caches per-request to avoid redundant lookups across probe→health→attach phases.
Fail-closed: unknown treated as Must-Staple (enforce) rather than not-Must-Staple.

KEY CONCEPTS:
1. Tri-State Must-Staple:
   - true: Must-Staple proven present (TLS Feature ext or ocsp.json flag)
   - false: Proven absent (TLS Feature ext parsed, no status_request)
   - nil: Unknown (ext parse failed, no ocsp.json flag, unrecognized text)
   Fail-closed: unknown ~= false → enforce Must-Staple

2. Detection Sources (in priority order):
   - TLS Feature extension (resty.openssl in PEM path)
   - ocsp.json must_staple=true (job path, disk or ligand)
   - Unknown if either fails → fall back to conservative enforcement

3. Cache Strategy:
   - Per-request ngx.ctx cache (ms_cache) keyed by (fp + pem_binding)
   - Avoids redundant PEM parsing + ocsp.json reads within single handshake
   - Each value boxed {_boxed=true, _ms=result} to cache nil (unset vs. absent)

EXPORTS:
- Public: check_enabled, get_must_staple, annotate_leaves, should_skip_validation
- Internal: Per-request caching, mode-aware skip logic

DEPENDENCIES:
- ocsp_common: resp_binding utility
- ocsp_store: resolve_leaf_must_staple (TLS Feature + ocsp.json detection)
- Called by ocsp.lua try_staple (skip validation gate), probe, health check

================================================================================
]]

-- OCSP Must-Staple Module
-- Detects, caches, and enforces must-staple requirements.
-- Tri-state from resolve_leaf_must_staple: true | false | nil (unknown).
-- Fail-closed gate everywhere: unknown ~= false → enforce / do not skip validate.

local _M = {}

local common = require("bunkerweb.ocsp_common").internal
local store = require("bunkerweb.ocsp_store").internal

local is_fp64 = common.is_fp64
local resp_binding = common.resp_binding
local resolve_leaf_must_staple = store.resolve_leaf_must_staple

-- Stable request-cache key. Never use a PEM prefix: "-----BEGIN CERTIFICATE-----"
-- is ~27 bytes, so sub(1, 32) collides across every leaf in a dual-cert handshake.
-- When both fp and PEM are present, bind them together so an early fp-only miss
-- cannot sticky-cache false across a later real MS PEM (HTTP leaf_ms_cache parity).
local function ms_cache_key(cert_pem, cert_fp)
	local fp_part = nil
	if is_fp64(cert_fp) then
		fp_part = cert_fp:lower()
	end
	local pem_part = nil
	if type(cert_pem) == "string" and cert_pem ~= "" then
		local dig = resp_binding(cert_pem)
		if dig then
			pem_part = dig
		end
	end
	if fp_part and pem_part then
		return "fp:" .. fp_part .. ":pem:" .. pem_part
	end
	if fp_part then
		return "fp:" .. fp_part
	end
	if pem_part then
		return "pem:" .. pem_part
	end
	return nil
end

-- Per-request Must-Staple detection cache avoiding redundant lookups within handshake.
-- Three calls (try_staple, probe, health) may check the same leaf — cache the result.
-- Uses request-scoped ngx.ctx to avoid cross-handshake pollution.
--
-- BOXING PATTERN (cache nil values without table removal complexity):
--   Normal Lua table caching: t[k] = nil deletes the entry (identical to no-entry).
--   Tri-state Must-Staple returns nil (unknown); we MUST cache that as distinct.
--   Solution: Box all results: { _boxed=true, _ms=result } where result can be nil.
--
--   - Cache hit: cached._boxed == true → return cached._ms (nil/true/false OK)
--   - Cache miss: key not in table (unset) → compute + box + store
--   - Boxed nil: { _boxed=true, _ms=nil } distinct from unset entry
--   - Invariant: always check _boxed before using _ms (prevents false negatives)
--
-- CACHE KEY: (fp + pem_binding) prevents dual-cert poison
--   - Dual-cert handshake: EC and RSA leaves both present
--   - If keyed by fp alone, early fp-only miss could poison later PEM-based check
--   - Combined key ensures EC and RSA leaves don't share cache entries
--
-- @param cert_pem: leaf certificate PEM (may be nil for fp-only paths)
-- @param cert_fp: leaf SPKI fingerprint (may be nil for PEM-only paths)
-- @return: tri-state Must-Staple (true/false/nil)
--
-- PERFORMANCE:
--   First call: resolve_leaf_must_staple(pem, fp) cost (~1-2ms for disk read if ocsp.json needed)
--   Subsequent calls: O(1) table lookup from ngx.ctx (<0.1ms)
-- Typical handshake: ~3 calls → 1 compute + 2 cache hits (1.5-2ms savings)
--
-- Called by: try_staple (leaf selection), probe (health check), attach path (final verify)
local function resolve_leaf_must_staple_with_cache(cert_pem, cert_fp)
	local ctx = ngx.ctx
	if not ctx then
		return resolve_leaf_must_staple(cert_pem, cert_fp)
	end

	local key = ms_cache_key(cert_pem, cert_fp)
	if not key then
		return resolve_leaf_must_staple(cert_pem, cert_fp)
	end

	if not ctx.bw_ocsp_ms_cache then
		ctx.bw_ocsp_ms_cache = {}
	end

	local cached = ctx.bw_ocsp_ms_cache[key]
	-- Box every result (incl. nil): raw t[k]=nil would delete the entry.
	-- BOXING PATTERN (cache nil values without table.remove complexity):
	--   - Cache hit: cached._boxed == true → return cached._ms (nil OK)
	--   - Cache miss: key not in table (unset) → compute + box + store
	--   - Boxed nil: { _boxed=true, _ms=nil } distinct from unset entry
	--   - Invariant: always check _boxed before using _ms (prevents false negatives)
	if type(cached) == "table" and cached._boxed then
		return cached._ms
	end

	local result = resolve_leaf_must_staple(cert_pem, cert_fp)
	-- Box even nil: { _boxed=true, _ms=nil } is a valid cache entry
	-- (distinguishes "cached and unknown" from "never seen before")
	ctx.bw_ocsp_ms_cache[key] = { _boxed = true, _ms = result }
	return result
end

-- True when Must-Staple enforcement applies for this mode.
-- Never call ocsp_staple_mode() without internalstore+SNI (that always yields "open").
-- Omitted mode → assume enforcement on (fail closed).
function _M.check_enabled(mode)
	if mode == nil or mode == "" then
		return true
	end
	return tostring(mode):lower() ~= "open"
end

-- Tri-state Must-Staple for this leaf (true / false / nil), request-cached.
-- SEMANTICS:
--   true  = Must-Staple proven present (TLS Feature extension parsed, or ocsp.json flag)
--   false = Must-Staple proven absent (TLS Feature extension parsed without feature 5)
--   nil   = Unknown (ext parse failed, no ocsp.json flag, unrecognized feature text)
--
-- CALLER GATE: if must_staple ~= false → fail-closed (unknown is treated as Must-Staple)
--              (nil is not false in Lua; "~= false" includes nil, true)
function _M.get_must_staple(cert_pem, cert_fp)
	return resolve_leaf_must_staple_with_cache(cert_pem, cert_fp)
end

-- Annotate leaves in-place with tri-state must_staple (fail-closed callers use ~= false).
function _M.annotate_leaves(leaves)
	if type(leaves) ~= "table" then
		return
	end
	for _, leaf in ipairs(leaves) do
		if type(leaf) == "table" then
			local pem = leaf.pem or leaf.ocsp_cert or leaf.cert_pem
			local fp = leaf.fp or leaf.ocsp_fp_hint
			if pem or fp then
				leaf.must_staple = resolve_leaf_must_staple_with_cache(pem, fp)
			end
		end
	end
end

-- Whether ngx.ocsp.validate may be skipped for this leaf.
-- mode == "open" → always skip (optional stapling).
-- Otherwise skip only when Must-Staple is proven false.
-- Omitted mode → do not open-skip (callers that lack mode still fail closed).
-- Unknown (nil) → do not skip.
function _M.should_skip_validation(leaf_pem, fingerprint, mode)
	if mode ~= nil and tostring(mode):lower() == "open" then
		return true
	end
	return resolve_leaf_must_staple_with_cache(leaf_pem, fingerprint) == false
end

return _M
