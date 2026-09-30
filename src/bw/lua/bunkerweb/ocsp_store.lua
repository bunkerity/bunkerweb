--[[
================================================================================
OCSP Store Module: Metadata Storage, Cache Management, and Ligand Integration
================================================================================

MODULE OVERVIEW:
Central data storage layer managing ocsp.json shard metadata, outside-ligand
bindings, L1 (Tier 1) shared-dict caching, and freshness gates. Implements
the critical HTTP↔stream coherence bus for OCSP state.

KEY CONCEPTS:
1. Shard Metadata (ocsp.json): Job-published per-certificate facts (SPKI
   fingerprint, DER SHA256, soft_recall_gen, expiry, Must-Staple flag).

2. Outside Ligand (ocsp-ligand/): Canary-paged binding (der_sha256 +
   soft_recall_gen) outside the SPKI directory structure. Enables atomic
   promotion of issuer.pem + ocsp.der + ocsp.json in paged workflow.

3. L1 Cache (Tier 1): Shared-dict storage (bw3 binary format) with epoch
   coherence bus (.ocsp_epoch) for TLS path optimization. Survives 300s
   (or until response expires), avoids frequent disk/ligand checks.

4. Freshness Gates: Validates OCSP response time bounds (thisUpdate, nextUpdate),
   intrinsic lifetime, max-age, cluster floor consensus, tombstone marks.

5. Must-Staple Resolution: Tri-state detection (true/false/nil unknown) from
   TLS Feature extension + ocsp.json flag, feeding into Must-Staple enforcement.

CACHE HIERARCHY:
- L1 (Tier 1/Per-Worker): ngx.shared.internalstore + ngx.shared.internalstore_stream
  (bw3 format: epoch|verified_sha|soft_recall_gen|expires|DER bytes)
- L2 (Disk/Shard): /var/cache/bunkerweb/ssl/{h}/{l}/{fp}/ocsp.json (job-maintained)
- L3 (Disk/Ligand): /var/cache/bunkerweb/ssl/ocsp-ligand/{fp} (job-maintained)
- L4 (Disk/Expires): /var/cache/bunkerweb/ssl/ocsp-floor/{fp}, serial-blacklist.json

EXPORTS:
- Public: resolve_leaf_must_staple, serial_blacklist_blocks, resp_still_fresh,
  cluster_floor_blocks, l1_body_matches_disk, ligand_verdict
- Internal: Ligand merging, L1 cache operations, freshness validation, Must-Staple
  resolution, warm_cache

DEPENDENCIES:
- ocsp_common: Clock skew, lifetime limits, epoch handling, logging
- ocsp_cert: Must-Staple detection, SPKI fingerprinting, serial extraction
- Called by ocsp.lua, ocsp_warmer.lua, ocsp_pin.lua for validation gates

================================================================================
]]

-- Shard metadata (ocsp.json), outside ligand, L1 shared-dict cache and freshness gates.
-- Part of bunkerweb.ocsp; other modules use the .internal table, callers use bunkerweb.ocsp.
local _M = {}

local ngx = ngx

local common = require("bunkerweb.ocsp_common").internal
local OCSP_CLOCK_SKEW_SECONDS = common.OCSP_CLOCK_SKEW_SECONDS
local OCSP_MAX_INTRINSIC_LIFETIME_SECONDS = common.OCSP_MAX_INTRINSIC_LIFETIME_SECONDS
local OCSP_MAX_THIS_UPDATE_AGE_SECONDS = common.OCSP_MAX_THIS_UPDATE_AGE_SECONDS
local cache_key = common.cache_key
local current_ocsp_epoch = common.current_ocsp_epoch
local is_fp64 = common.is_fp64
local log = common.log
local ocsp_path = common.ocsp_path
local read_file = common.read_file
local resp_binding = common.resp_binding

local cert = require("bunkerweb.ocsp_cert").internal
local has_must_staple = cert.has_must_staple
local ocsp_resp_serial_hex = cert.ocsp_resp_serial_hex
local spki_fingerprint = cert.spki_fingerprint

-- One shm value = epoch + optional verified binding + soft_recall_gen + expires + DER.
-- Evicting this key cannot orphan verified from DER (or gen from DER).
-- Layout v3: "bw3\0" .. epoch .. "\0" .. binding .. "\0" .. gen .. "\0" .. expires .. "\0" .. der
-- Layout v2 (legacy): "bw2\0" .. epoch .. "\0" .. binding .. "\0" .. expires .. "\0" .. der
--   bw2 has no gen → entry_verified always false (soft-recall cannot leave sticky verified).
local L1_MAGIC = "bw3\0"
local L1_MAGIC_V2 = "bw2\0"
-- Cap DRAM residence; never longer than remaining OCSP life when known.
local L1_MAX_TTL = 300

-- ============================================================================
-- fp64_or_nil(fingerprint)
-- ============================================================================
-- PURPOSE:
--   Normalize and validate SPKI fingerprint format (64 hex chars, lowercase).
--   Used before all path operations and cache key generation.
--
-- PARAMETERS:
--   fingerprint (string|nil): potential SPKI fingerprint (64 hex chars)
--
-- RETURNS:
--   (string): lowercase 64-char hex fingerprint if valid
--   (nil): if invalid format, wrong length, or non-hex
--
-- SIDE EFFECTS:
--   - Calls: is_fp64() for format validation
--   - No reads/writes or state modification
--   - Performance: O(1) string operation, ~0.01ms
--
-- DESIGN NOTES:
--   - Normalization: Disk paths and pin bus use lowercase (job consistency)
--   - is_fp64 validation: Allows A-F uppercase, normalizes to lowercase
--   - Fail-safe: Returns nil for invalid (prevents path traversal)
--   - Used by: All functions needing fingerprint path operations
--   - Called before: Path joins, cache keys, fingerprint equality checks
--
-- RELATED:
--   - is_fp64() from common module for hex validation
--   - All path functions (ocsp_path, ocsp_ligand_path) call this first
--   - Cache keys normalized via this function
--
-- ============================================================================
-- Disk paths and pin bus use lowercase hex (job + ocsp_pin). is_fp64 allows
-- A-F; normalize before path join / cache key / fingerprint equality checks.
local function fp64_or_nil(fingerprint)
	if not is_fp64(fingerprint) then
		return nil
	end
	return fingerprint:lower()
end

-- Parse and validate unix timestamp, preventing common parsing attacks.
--
-- This function hardens timestamp parsing to reject non-integer representations
-- that Lua's tonumber() would accept:
--   - tonumber("1e20") → 1×10²⁰ (exponential, not a real unix timestamp)
--   - tonumber("inf") / "nan" (non-finite, would break comparisons)
--   - Negative numbers (timestamps before epoch, invalid for OCSP)
--
-- @param v: value to parse (number or string)
-- @return: positive integer unix timestamp, or nil if invalid/non-positive
--
-- VALIDATION RULES:
-- - Number: Reject NaN (v ~= v), infinity (math.huge), and non-positive (<= 0)
--           Accept only finite positive numbers, floor to integer
-- - String: Reject if not all digits (prevents "1e2", "inf", "abc")
--           Only parse digit-only strings, verify result is positive
-- - Any other type: Return nil (fail-closed for unknown input)
--
-- Used for: expires_unix, thisUpdate, max_age parsing (OCSP freshness validation)
-- Called by: resp_still_fresh, meta_effective_expires_unix, warm_cache
-- Performance: O(1) string matching + optional tonumber
--
-- Security: Prevents timestamp coercion attacks where attacker controls
--           OCSP response timestamps and tries to parse "9e99" as valid TTL
--
-- ============================================================================
-- positive_unix(v)
-- ============================================================================
-- PURPOSE:
--   Parse and validate unix timestamp, rejecting NaN, infinity, non-positive values.
--   Hardens timestamp parsing against tonumber() attacks and malformed inputs.
--
-- PARAMETERS:
--   v (number|string): timestamp to validate
--     - number: validated and floored to integer
--     - string: must be all digits (no scientific notation)
--     - other: returns nil
--
-- RETURNS:
--   (number): validated unix timestamp (integer seconds)
--   (nil): if invalid (NaN, infinity, <=0, malformed string)
--
-- SIDE EFFECTS:
--   None (pure validation function)
--   Performance: O(1) type checks + tonumber (~0.01ms)
--
-- DESIGN NOTES:
--   - NaN rejection: v ~= v true only for NaN (self-comparison fails)
--   - Infinity rejection: Explicitly checks ±math.huge
--   - Positive guard: Rejects zero and negative (before epoch invalid)
--   - String parsing: Only accepts all-digit strings (no scientific notation)
--   - Numeric string: tonumber("1e20") rejected (not matched by ^%d+$)
--   - Floor to integer: Removes fractional seconds (unix is integer seconds)
--   - Type safety: Returns nil for unexpected types
--   - Called by: meta_expires_unix(), metadata parsing, time validations
--
-- RELATED:
--   - meta_expires_unix() uses this to validate expires field
--   - l1_shm_ttl() uses for TTL calculation
--   - resp_still_fresh() uses for freshness checks
--
-- ============================================================================
local function positive_unix(v)
	if type(v) == "number" then
		-- Reject NaN (NaN ~= NaN is true; only NaN satisfies this)
		-- Reject positive/negative infinity (invalid timestamps)
		-- Reject zero and negative numbers (unix timestamp before epoch)
		if v ~= v or v == math.huge or v == -math.huge or v <= 0 then
			return nil
		end
		-- Floor to integer (remove fractional seconds)
		return math.floor(v)
	end
	if type(v) == "string" and v:match("^%d+$") then
		-- String is all digits (no scientific notation, signs, or non-digits)
		local n = tonumber(v)
		-- Verify tonumber succeeded and result is positive
		if n and n > 0 then
			return n
		end
	end
	return nil
end

-- Forward decls: warm_cache tightens expires / gen against live ligand (defined below).
local ligand_or_meta
local soft_recall_gen_of
local meta_effective_expires_unix
local read_ocsp_json
local read_ocsp_ligand

-- Calculate time-to-live (TTL) for storing OCSP response in L1 shared-dict cache.
--
-- OCSP responses have an expiry time (nextUpdate). This function:
-- 1. Validates the expiry is a valid unix timestamp
-- 2. Subtracts clock skew (tolerate clock drift between servers)
-- 3. Calculates time remaining until response is stale
-- 4. Caps TTL at L1_MAX_TTL (300s) to prevent stale cached responses
--
-- @param expires_unix: response expiry timestamp (unix seconds)
-- @return: TTL in seconds for shared dict, or nil if response already expired
--
-- EXAMPLE:
--   expires_unix = 1696003200 (future)
--   now = 1696003100
--   OCSP_CLOCK_SKEW_SECONDS = 60
--   remaining = 1696003200 - 60 - 1696003100 = 40 seconds
--   → return 40 (cache for 40 seconds)
--
-- EDGE CASES:
-- - No expiry: Returns nil (never cache undated responses)
-- - Already expired: Returns nil (response is stale)
-- - Very long TTL: Capped at L1_MAX_TTL=300s (prevents DRAM bloat)
-- - Negative remaining: Returns nil (expiry is in the past)
--
-- Called by: warm_cache (before storing DER in shared dict)
-- Performance: O(1) arithmetic
--
-- ============================================================================
-- l1_shm_ttl(expires_unix)
-- ============================================================================
-- PURPOSE:
--   Calculate optimal TTL for L1 cache entry. Prevents stale responses from
--   living too long in shared dict while respecting response lifetime.
--
-- PARAMETERS:
--   expires_unix (number): response expiry time (unix timestamp)
--
-- RETURNS:
--   (number): TTL in seconds for shared dict.set(key, value, ttl)
--   (nil): if already stale or no valid expiry
--
-- SIDE EFFECTS:
--   - Reads: ngx.time() for current time
--   - No state modification
--   - Performance: O(1) arithmetic (~0.01ms)
--
-- DESIGN NOTES:
--   - TTL calculation: min(remaining_until_expires, L1_MAX_TTL=300s)
--   - Clock skew buffer: Subtracts OCSP_CLOCK_SKEW_SECONDS (30s typical)
--   - Stale detection: Returns nil if remaining <= 0 (already expired)
--   - Max cap: 300s prevents old responses from living in DRAM beyond expiry
--   - Type checking: Rejects nil, non-numbers, or negative expires
--   - Called by: warm_cache() to set shared dict TTL
--   - Principle: Never let DRAM entry outlive response lifetime
--
-- RELATED:
--   - warm_cache() uses this TTL for shared dict.set()
--   - resp_still_fresh() validates response not past expiry
--   - meta_effective_expires_unix() computes death clock
--
-- ============================================================================
local function l1_shm_ttl(expires_unix)
	-- Validate expiry is a positive number (reject nil, non-numeric, or negative)
	-- Never cache responses without an expiry (they could stay in DRAM forever)
	if type(expires_unix) ~= "number" or expires_unix <= 0 then
		return nil
	end
	-- Calculate seconds remaining until response expires
	-- Subtract OCSP_CLOCK_SKEW_SECONDS to tolerate clock skew between servers
	-- Example: expires at T=100, skew=60, now=50 → remaining = 100-60-50 = -10 (expired)
	local remaining = expires_unix - OCSP_CLOCK_SKEW_SECONDS - ngx.time()
	if remaining <= 0 then
		return nil  -- Response already stale (or will be within clock skew tolerance)
	end
	-- Cap TTL at L1_MAX_TTL=300 seconds to prevent stale responses living too long in DRAM
	-- Shared dict entry lives longer if we request longer TTL, but we only want 5 minutes max
	if remaining > L1_MAX_TTL then
		return L1_MAX_TTL
	end
	-- Return calculated TTL (will be set on shared dict entry)
	return remaining
end

-- Pack one L1 shm entry: epoch | verified sha256 binding | soft_recall_gen | expires | DER.
--
-- L1 BLOB FORMAT (bw3 version):
--   "bw3\0" + epoch + "\0" + verified_binding + "\0" + soft_recall_gen + "\0" + expires + "\0" + der_bytes
--   - epoch: string .ocsp_epoch token (job coherence bus for HTTP↔stream)
--   - verified_binding: hex SHA256(OCSP DER) or "" if not cryptographically trusted
--   - soft_recall_gen: generation counter (for soft-recall / allow-pin matching) or ""
--   - expires: unix timestamp (death-time for response) or ""
--   - der_bytes: full OCSP response DER (binary)
--
-- NULL-SEPARATOR SAFETY: \0 is safe as field delimiter (binary safe; never in hex/epoch/gen/expires)
--   - epoch: alphanumeric timestamp string (no \0)
--   - verified_binding: hex digits (no \0)
--   - soft_recall_gen: digits (no \0)
--   - expires: digits (no \0)
--   - DER: binary arbitrary bytes (may contain \0, but is always last)
-- Pack OCSP response into L1 shared-dict storage format (bw3 version).
--
-- Encodes response with metadata into binary blob for storage in nginx shared dict.
-- Uses null-byte separators which are safe because all prefix fields are digit/hex only.
--
-- BLOB FORMAT:
--   "bw3\0" + epoch + "\0" + verified_binding + "\0" + gen + "\0" + expires + "\0" + der
--
-- FIELDS:
-- - epoch (string): .ocsp_epoch token from scheduler (alphanumeric, no null bytes)
-- - verified_binding (hex string): SHA256(response_der) if cryptographically validated,
--                                 or "" if only cached for reuse (unverified)
-- - gen (digits): soft_recall generation counter (for allow-pin matching after cert rotation)
-- - expires (digits): unix timestamp when this response expires
-- - der (binary): full OCSP response bytes (may contain arbitrary bytes including null)
--
-- @param epoch: scheduler-managed epoch token (coherence bus for HTTP↔stream)
-- @param verified_binding: SHA256 hex of DER (64 hex chars) or "" if unverified
-- @param der: OCSP response DER bytes (binary string)
-- @param expires_unix: response expiry timestamp (number or digit string)
-- @param soft_recall_gen: generation counter (number or string digits) or nil
-- @return: packed blob string (binary safe, can be stored in shared dict)
--
-- SECURITY: Uses null-byte delimiters (binary safe):
--   - epoch: alphanumeric timestamps (no null bytes)
--   - verified_binding: hex digits only (no null bytes)
--   - gen: digits only (no null bytes)
--   - expires: digits only (no null bytes)
--   - der: binary data (may contain nulls, but is always last)
--
-- TYPE SAFETY: Accepts both numbers and strings for expires/gen to handle
--              cases where values come from different sources (disk, TTL, caller)
--
-- ============================================================================
-- PACK_L1(epoch, verified_binding, der, expires_unix, soft_recall_gen)
-- ============================================================================
-- PURPOSE:
--   Serializes OCSP response data into bw3 binary format for L1 (Tier 1) shared-dict
--   cache storage. Encodes metadata (epoch, binding, generation, expiry) alongside
--   DER bytes for coherent per-worker caching.
--
-- PARAMETERS:
--   epoch (string|nil): scheduler epoch token for cache coherence bus
--   verified_binding (string|nil): SHA256(der) hex if cryptographically verified
--   der (string): OCSP response DER bytes (binary)
--   expires_unix (number|string): response expiry unix timestamp (float or digit string)
--   soft_recall_gen (number|nil): generation counter for soft-recall invalidation
--
-- RETURNS:
--   (string): binary blob in bw3 format: "bw3\0" + epoch + "\0" + binding + "\0" +
--             gen + "\0" + expires + "\0" + der (null-delimited fields)
--
-- SIDE EFFECTS:
--   - String manipulation only (no state/IO)
--   - Performance: O(n) linear with DER size (typical ~1KB, trivial)
--
-- DESIGN NOTES:
--   - Format version: "bw3\0" magic prefix for version detection
--   - Normalization: expires_unix (number or digit string) converted to digit string
--   - Generation field: included in bw3 (differentiates from legacy bw2)
--   - Null delimiters: each field separated by \0 for reliable field extraction
--   - Empty values: binding/gen coerced to "" if nil (unverified/no generation)
--   - Type safety: rejects non-number expires (preserves only valid timestamps)
--   - Inverse: unpack_l1() reverses this operation
--   - Used by: warm_cache() when populating L1 shared dict
--
-- RELATED:
--   - unpack_l1() — unpacks this format for cache retrieval
--   - get_l1() — stores and retrieves packed data
--   - L1_MAGIC, L1_MAGIC_V2 — format version constants
--
-- ============================================================================
local function pack_l1(epoch, verified_binding, der, expires_unix, soft_recall_gen)
	-- Normalize expires_unix to digit string (reject invalid types)
	local exp = ""
	if type(expires_unix) == "number" and expires_unix > 0 then
		-- Convert number to string, floor to remove fractional seconds
		exp = tostring(math.floor(expires_unix))
	elseif type(expires_unix) == "string" and expires_unix:match("^%d+$") then
		-- Already a digit string, use as-is
		exp = expires_unix
	end
	-- Normalize soft_recall_gen to digit string (empty if nil or invalid)
	local gen = ""
	if type(soft_recall_gen) == "number" and soft_recall_gen >= 0 then
		-- Convert non-negative number to string
		gen = tostring(math.floor(soft_recall_gen))
	end
	-- Assemble final blob: magic + epoch + null + binding + null + gen + null + exp + null + der
	return L1_MAGIC .. (epoch or "0") .. "\0" .. (verified_binding or "") .. "\0" .. gen .. "\0" .. exp .. "\0" .. der
end

-- ============================================================================
-- UNPACK_L1(blob)
-- ============================================================================
-- PURPOSE:
--   Deserializes bw3 (or legacy bw2) binary format from L1 cache into component
--   fields. Handles format version detection and field extraction with fail-closed
--   semantics (corrupted/malformed entries return all-nil).
--
-- PARAMETERS:
--   blob (string): binary blob from L1 shared-dict cache (may be bw3 or bw2 format)
--
-- RETURNS:
--   (string, string|nil, string, number|nil, number|nil): tuple of:
--     - epoch: scheduler epoch token (version identifier for .ocsp_epoch coherence)
--     - binding: SHA256(der) hex if verified, nil if unverified/legacy
--     - der: OCSP response DER bytes (binary string)
--     - expires_unix: response expiry unix timestamp (number) or nil if unparseable
--     - gen: soft_recall generation counter or nil (nil in bw2 format)
--   (nil, nil, nil, nil, nil): on corruption, wrong format, or empty DER
--
-- SIDE EFFECTS:
--   - String matching only (no state/IO)
--   - Performance: O(n) regex matching where n = blob size (typical ~1KB, trivial)
--
-- DESIGN NOTES:
--   - Format versions: "bw3\0" (current with generation) vs "bw2\0" (legacy, no gen)
--   - Magic detection: first 4 bytes identify format; unknown magic rejects blob
--   - Null delimiters: field structure: epoch\0 + binding\0 + gen\0 + expires\0 + der
--     (bw2 omits gen field: epoch\0 + binding\0 + expires\0 + der)
--   - Empty binding: treated as nil (unverified response, safe to cache)
--   - Type coercion: expires digit-string → number; gen only if digit-string
--   - DER validation: must exist and be non-empty (corrupted blobs rejected)
--   - Fail-closed: any parsing error returns all-nil (not partial results)
--   - Inverse: pack_l1() creates this format
--   - Used by: get_l1(), entry_verified() for cache state management
--
-- RELATED:
--   - pack_l1() — serializes data into this format
--   - get_l1() — wrapper that retrieves and unpacks blobs
--   - L1_MAGIC, L1_MAGIC_V2 — format version constants
--
-- ============================================================================
-- Unpack L1 blob into component fields. Supports both bw3 (current) and bw2 (legacy) formats.
--
-- Reverses the packing done by pack_l1(). Handles format version detection and field extraction.
-- Legacy bw2 format lacks generation field (gen=nil), so verified trust is disabled.
--
-- @param blob: binary blob from L1 shared dict
-- @return: epoch, binding, der, expires_unix, gen (or nil,nil,nil,nil,nil on error)
--
-- RETURN VALUES:
-- - epoch: scheduler epoch token (string, version identifier for .ocsp_epoch)
-- - binding: SHA256(der) in hex, or nil if unverified
-- - der: OCSP response bytes (binary string)
-- - expires_unix: response expiry unix timestamp (number)
-- - gen: soft_recall generation counter (number), or nil in legacy bw2 format
--
-- FORMAT DETECTION:
-- - Checks first 4 bytes for magic: "bw3\0" (current) or "bw2\0" (legacy)
-- - bw3: Contains generation field (safe for soft-recall invalidation)
-- - bw2: No generation field (must not trust verified state across soft-recall)
--
-- SECURITY:
-- - Validates DER is non-empty (rejects corrupted entries)
-- - Parses generation only if digit string (rejects non-numeric)
-- - Returns nil for both binding and gen if fields are empty (fail-closed)
-- - Normalizes empty strings to nil (cleaner for caller logic)
--
-- Called by: get_l1 (L1 cache lookup), entry_verified (cache state validation)
-- Performance: O(n) string search for null bytes (n = blob size)
--
local function unpack_l1(blob)
	-- Validate blob is a string with minimum size (magic + null terminator)
	if type(blob) ~= "string" or #blob < 4 then
		return nil, nil, nil, nil, nil
	end
	-- Extract magic bytes (first 4 bytes identify format version)
	local magic = blob:sub(1, 4)
	if magic == L1_MAGIC then
		-- Current bw3 format: epoch\0 + binding\0 + gen\0 + expires\0 + der
		-- Use regex to split by null delimiters
		local epoch, binding, gen_s, exp, der = blob:sub(5):match("^([^\0]*)\0([^\0]*)\0([^\0]*)\0([^\0]*)\0(.*)$")
		-- Validate DER bytes exist and are non-empty (reject corrupted entries)
		if type(der) ~= "string" or #der == 0 then
			return nil, nil, nil, nil, nil
		end
		-- Empty binding means response was not cryptographically verified (strip to nil for clarity)
		if binding == "" then
			binding = nil
		end
		-- Parse expires timestamp (digit string → number)
		local expires_unix = nil
		if type(exp) == "string" and exp:match("^%d+$") then
			expires_unix = tonumber(exp)
		end
		-- Parse generation (digit string → number, nil if absent or non-numeric)
		local gen = nil
		if type(gen_s) == "string" and gen_s:match("^%d+$") then
			gen = tonumber(gen_s)
		end
		return epoch or "0", binding, der, expires_unix, gen
	end
	if magic == L1_MAGIC_V2 then
		-- Legacy bw2 format: epoch\0 + binding\0 + expires\0 + der (NO generation field)
		-- Regex: split by three null delimiters only (bw2 has no gen field)
		local epoch, binding, exp, der = blob:sub(5):match("^([^\0]*)\0([^\0]*)\0([^\0]*)\0(.*)$")
		-- Validate DER is present and non-empty
		if type(der) ~= "string" or #der == 0 then
			return nil, nil, nil, nil, nil
		end
		-- Empty binding → nil (same as bw3)
		if binding == "" then
			binding = nil
		end
		-- Parse expires (same as bw3)
		local expires_unix = nil
		if type(exp) == "string" and exp:match("^%d+$") then
			expires_unix = tonumber(exp)
		end
		-- bw2 has no generation field: caller must not trust verified state across soft-recall
		-- Return nil for gen to signal "generation mismatch → unverified"
		return epoch or "0", binding, der, expires_unix, nil
	end
	-- Unknown magic bytes: corrupted blob or wrong format
	return nil, nil, nil, nil, nil
end

-- Retrieve OCSP response from L1 shared-dict cache.
--
-- L1 is a per-worker shared-dict cache that survives across multiple handshakes
-- within a single nginx worker. This is populated by warm_cache() and checked
-- before doing expensive FFI validation.
--
-- @param internalstore: ngx.shared dict handle (bw_ocsp_responses or similar)
-- @param fingerprint: certificate SPKI fingerprint (64-char hex) or nil
-- @return: der, verified_binding, epoch, expires_unix, gen (or nil if cache miss)
--
-- RETURN VALUE SEMANTICS:
-- - der (string): OCSP response DER bytes (binary)
-- - verified_binding (string or nil): SHA256(der) hex if cryptographically trusted,
--                                     nil if cached for reuse but not verified
-- - epoch (string): scheduler epoch token (coherence bus identifier)
-- - expires_unix (number): response expiry timestamp
-- - gen (number or nil): soft_recall generation (nil in legacy bw2 format)
--
-- CACHE HIT CRITERIA:
-- 1. internalstore exists and is accessible
-- 2. fingerprint is valid 64-char hex
-- 3. Shared dict key generation succeeds
-- 4. PCall succeeds (shared dict accessible)
-- 5. Blob exists and is non-empty

-- CACHE MISS SCENARIOS (return nil):
-- - internalstore is nil or broken
-- - fingerprint is invalid (wrong length, non-hex)
-- - Shared dict inaccessible (PCall fails)
-- - Key not found in dict (entry expired or never set)
-- - Blob is empty (corrupted entry)
-- - Unpack fails (malformed blob, version mismatch)
--
-- PERFORMANCE:
-- - Cache hit: <0.1ms (shared dict lookup + unpack)
-- - Cache miss: ~1-2µs (key generation + get call)
--
-- CALLED BY: try_attach_from_l1_cache (TLS handshake path)
--
-- ============================================================================
-- get_l1(internalstore, fingerprint)
-- ============================================================================
-- PURPOSE:
--   Retrieve cached OCSP response from L1 shared-dict cache.
--   Validates format (bw3/bw2), unpacks generation binding, returns DER + metadata.
--
-- PARAMETERS:
--   internalstore (table): shared dict (ngx.shared.bw_ocsp_* or internalstore_stream)
--   fingerprint (string): leaf SPKI fingerprint (64 hex chars, normalized lowercase)
--
-- RETURNS:
--   (der, verified, epoch, expires_unix, gen): on hit
--     der = OCSP response DER bytes
--     verified = SHA256 binding matched (crypto-verified)
--     epoch = ocsp.json epoch when cached
--     expires_unix = response expiry time
--     gen = soft_recall_gen for generation binding
--   (nil): on miss or error
--
-- SIDE EFFECTS:
--   - Reads: shared dict lookup via pcall (exception-safe)
--   - Calls: fp64_or_nil() for normalization, unpack_l1() for format parsing
--   - Performance: O(1) shared dict lookup (~0.1ms typical)
--
-- DESIGN NOTES:
--   - Fingerprint normalization: Validates 64-char hex, lowercases for key uniformity
--   - Blob format: bw3 (epoch|verified|gen|expires|der) or bw2 legacy
--   - Verified flag: True only if DER SHA256 matches stored binding + gen matches
--   - Exception safety: pcall wraps shared dict access (permissions/storage errors)
--   - Empty-blob guard: Rejects zero-length entries (corruption protection)
--   - Unpack validation: Returns nil if format invalid or unpack fails
--   - All-or-nothing: Returns all 5 fields or nil (no partial returns)
--
-- RELATED:
--   - warm_cache() writes to L1 cache
--   - entry_verified() validates crypto binding + generation
--   - unpack_l1() parses blob format
--
-- ============================================================================
local function get_l1(internalstore, fingerprint)
	-- Validate shared dict is available (not nil)
	if not internalstore then
		return nil
	end
	-- Normalize fingerprint: validate hex format and lowercase for cache key uniformity
	-- Rejects fingerprints that are wrong length or contain non-hex characters
	fingerprint = fp64_or_nil(fingerprint)
	if not fingerprint then
		return nil
	end
	-- Generate cache key (stable hash of fingerprint for shared dict lookup)
	local key = cache_key(fingerprint)
	if not key then
		return nil
	end
	-- Wrap shared dict access in pcall to catch exceptions
	-- (nginx shared dicts can throw if permissions issue or storage exhausted)
	local ok, blob = pcall(function()
		-- Shared dict is shared across all workers in this nginx process
		-- (unlike per-worker caches, which don't survive worker restarts)
		return internalstore:get(key)
	end)
	-- Check three conditions for valid blob:
	-- 1. PCall succeeded (no exception thrown)
	-- 2. Blob is a string (not nil or other type)
	-- 3. Blob is non-empty (reject corrupted zero-length entries)
	if not ok or type(blob) ~= "string" or #blob == 0 then
		return nil
	end

	-- Unpack blob into component fields (handles bw3 and legacy bw2 formats)
	local epoch, verified, der, expires_unix, gen = unpack_l1(blob)
	-- Return all fields if unpack succeeded (der is non-nil)
	if der then
		return der, verified, epoch, expires_unix, gen
	end
	-- Unpack failed (malformed blob, wrong version, etc)
	return nil
end

-- ============================================================================
-- entry_verified(stored_binding, resp, stored_gen, live_gen)
-- ============================================================================
-- PURPOSE:
--   Validate L1 cache entry is crypto-verified and generation-bound.
--   Both SHA256 binding AND generation must match current to return true.
--
-- PARAMETERS:
--   stored_binding (string|nil): DER SHA256 from L1 cache
--   resp (string): OCSP response DER bytes (current)
--   stored_gen (number|nil): soft_recall_gen from L1 cache
--   live_gen (number|nil): current soft_recall_gen from ligand_or_meta()
--
-- RETURNS:
--   (boolean): true if both binding AND generation match
--             false if mismatch or type error
--
-- SIDE EFFECTS:
--   - Calls: resp_binding() to compute DER SHA256
--   - No writes or state modification
--   - Performance: O(1) comparison (~0.1ms)
--
-- DESIGN NOTES:
--   - Dual verification: SHA256 binding + generation number both required
--   - DER binding: resp_binding(resp) = SHA256 of DER bytes
--   - Generation binding: Soft-recall gen prevents stale status blocking new cert
--   - Type checking: Both gen values must be numbers (rejects nil, strings, tables)
--   - All-or-nothing: Returns false on any mismatch (not partially verified)
--   - Crypto trust: Only when both conditions met (fail-closed)
--   - Called by: L1 path validation, entry_verified path
--   - Legacy handling: bw2 format has no stored_gen (treated as no match)
--
-- RELATED:
--   - resp_binding() computes DER SHA256
--   - warm_cache() writes stored binding + generation
--   - get_l1() retrieves stored binding and generation
--
-- ============================================================================
-- True when L1's stored binding is still sha256(resp) AND soft_recall_gen matches.
-- Missing/mismatched gen (bw2 legacy or soft-recall bump) → not crypto-trusted.
local function entry_verified(stored_binding, resp, stored_gen, live_gen)
	local binding = resp_binding(resp)
	if binding == nil or stored_binding ~= binding then
		return false
	end
	if type(stored_gen) ~= "number" or type(live_gen) ~= "number" then
		return false
	end
	return stored_gen == live_gen
end

-- ============================================================================
-- warm_cache(internalstore, fingerprint, resp, mark_verified, expires_unix,
--            packed_epoch, soft_recall_gen)
-- ============================================================================
-- PURPOSE:
--   Write OCSP response to L1 shared-dict cache with generation binding.
--   Enforces live metadata (ligand+shard) death clock to prevent L1 outliving response.
--
-- PARAMETERS:
--   internalstore (table): shared dict (ngx.shared.bw_ocsp_*)
--   fingerprint (string): leaf SPKI fingerprint (64 hex chars)
--   resp (string): OCSP response DER bytes
--   mark_verified (boolean|nil): true = crypto-verified (SHA256 bound),
--                                false = cached unverified, nil = default true
--   expires_unix (number|nil): caller's expiry time (may be demoted by live meta)
--   packed_epoch (number|nil): epoch from prior L1 hit (preserve staleness)
--   soft_recall_gen (number): generation tuple for soft-recall binding
--
-- RETURNS:
--   None (side effect only)
--
-- SIDE EFFECTS:
--   - Writes: L1 blob to shared dict with computed TTL
--   - Reads: live metadata via ligand_or_meta() (always fresh)
--   - Calls: meta_effective_expires_unix(), pack_l1()
--   - Demotion: mark_verified demoted if caller expires looser than live meta
--   - Performance: O(1) metadata merge + pack + write (~0.5ms)
--
-- DESIGN NOTES:
--   - Live metadata always wins: Never extend DER lifetime beyond ligand+shard
--   - Tombstone guard: Refuses cache if ligand tombstoned
--   - Demotion: If caller's expires > live meta, drop verified bit
--   - Epoch preservation: packed_epoch prevents old body from appearing current
--   - TTL calculation: min(300s, remaining until expires_unix)
--   - Stripped metadata: If meta has no death clock, refuse cache entirely
--   - Generation binding: soft_recall_gen paired with DER for soft-recall invalidation
--   - Called by: try_staple() on success, disk path on fallthrough validation
--
-- RELATED:
--   - get_l1() reads cached value
--   - entry_verified() validates crypto binding + generation
--   - meta_effective_expires_unix() computes live death clock
--   - ligand_or_meta() merges outside ligand + shard metadata
--
-- ============================================================================
-- Write DER into stream/HTTP L1 (bw3 composite).
-- packed_epoch: when re-parking a body that already passed l1_matches_disk, pass
-- the epoch from that get — never stamp "now's" epoch over an old body (that would
-- make a stale DER look current until the next ligand check). Matches HTTP
-- ocsp_l1_put(..., packed_epoch) in ssl-certificate-by-lua.conf.
-- mark_verified=false: cache DER for reuse but do not skip crypto on later hits.
-- soft_recall_gen: generation identity parked with the body (required for verified trust).
local function warm_cache(internalstore, fingerprint, resp, mark_verified, expires_unix, packed_epoch, soft_recall_gen)
	-- mark_verified=false: cache DER for reuse but do not skip crypto on later hits.
	-- Only PEM + validate_ocsp_response (or a prior verified binding) may set verified.
	if mark_verified == nil then
		mark_verified = true
	end
	if type(resp) ~= "string" or #resp == 0 then
		return
	end
	fingerprint = fp64_or_nil(fingerprint)
	-- Live merged death clock wins: never mark verified under a looser expires than
	-- ligand/shard min (L1 TTL and resp_still_fresh would disagree across workers).
	-- Must merge shard ocsp.json too — ligand-only merge drops a tighter shard
	-- expires / soft_recall_gen when the ligand omits or is looser.
	local live_meta = nil
	if fingerprint then
		live_meta = ligand_or_meta(nil, fingerprint)
		-- Never re-warm a tombstoned generation (ligand may tombstone before shard).
		if type(live_meta) == "table" and live_meta.tombstoned == true then
			return
		end
		local tight = meta_effective_expires_unix(live_meta, nil)
		if type(tight) ~= "number" or tight <= 0 then
			-- Stripped meta+ligand: never park from caller/L1 expires alone.
			return
		end
		if type(expires_unix) ~= "number" or expires_unix <= 0 then
			-- Adopt live death clock. Caller had no clock to disagree with —
			-- do not demote verified (post-validate parks often pass shard-only
			-- meta_effective which is nil when only the ligand carries expires).
			expires_unix = tight
		elseif expires_unix > tight then
			-- Caller/L1 claimed a looser deadline than live merge — demote.
			if mark_verified then
				mark_verified = false
			end
			expires_unix = tight
		end
		-- expires_unix <= tight: keep caller's tighter clock and verified bit.
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
	local gen = soft_recall_gen
	-- When live meta/ligand is present, its gen wins (caller can lag a soft-recall bump).
	-- soft_recall_gen_of(nil) is upgrade-grace 0 — do not treat that as live authority.
	if type(live_meta) == "table" then
		local live_gen = soft_recall_gen_of(live_meta)
		if type(live_gen) == "number" then
			if type(gen) == "number" and gen ~= live_gen and mark_verified then
				-- Gen drift: park DER for reuse but do not claim verified trust.
				binding = nil
				mark_verified = false
			end
			gen = live_gen
		else
			-- Live type-drift (false sentinel / invalid): never park a gen that
			-- soft_recall_gen_of would refuse to match — clear gen + verified.
			binding = nil
			mark_verified = false
			gen = nil
		end
	elseif type(gen) ~= "number" then
		gen = soft_recall_gen_of(live_meta)
	end
	-- Verified without a concrete gen cannot survive soft-recall — demote.
	if mark_verified and type(gen) ~= "number" then
		binding = nil
	end
	local epoch = packed_epoch
	if type(epoch) ~= "string" or #epoch == 0 then
		epoch = current_ocsp_epoch()
	end
	local key = fingerprint and cache_key(fingerprint) or nil
	if not key then
		return
	end
	pcall(function()
		internalstore:set(key, pack_l1(epoch, binding, resp, expires_unix, gen), ttl)
		-- Clear per-worker LRU so a prior worker-scoped put cannot shadow shared dict.
		internalstore:delete(key, true)
	end)
end

-- ============================================================================
-- drop_cache(internalstore, fingerprint)
-- ============================================================================
-- PURPOSE:
--   Evict OCSP response from L1 cache. Called when freshness/validation fails
--   or CertID mismatch detected. Forces reload from disk on next request.
--
-- PARAMETERS:
--   internalstore (table): shared dict (ngx.shared.bw_ocsp_*)
--   fingerprint (string): leaf SPKI fingerprint (64 hex chars)
--
-- RETURNS:
--   None (side effect only)
--
-- SIDE EFFECTS:
--   - Calls: internalstore:delete() twice (normal + expired variants)
--   - Wrapped in pcall for exception safety
--   - Performance: O(1) shared dict delete (~0.1ms)
--
-- DESIGN NOTES:
--   - Double delete: Removes both current and expired entry variants
--   - Fingerprint normalization: Validates 64-char hex lowercase
--   - Exception safety: pcall wraps all shared dict operations
--   - Triggers: Freshness failure, CertID mismatch, tombstone, serial blacklist
--   - Effect: Next request reads disk (ligand + ocsp.json + ocsp.der)
--   - Called by: resp_still_fresh failures, CertID validation, rank probes
--   - Conservative: Drops on any doubt (fail-closed)
--
-- RELATED:
--   - get_l1() retrieves cached value
--   - warm_cache() writes to L1
--   - resp_still_fresh() calls this on stale detection
--
-- ============================================================================
local function drop_cache(internalstore, fingerprint)
	fingerprint = fp64_or_nil(fingerprint)
	local key = fingerprint and cache_key(fingerprint) or nil
	if not key then
		return
	end
	pcall(function()
		internalstore:delete(key)
		internalstore:delete(key, true)
	end)
end

-- True when this L1 body is still coherent with disk + .ocsp_epoch.
-- Implemented after ligand_effective_sha (shared with HTTP); see l1_body_matches_disk.
local l1_matches_disk

-- Job-written shard metadata ({fp[1]}/{fp[2]}/{fp}/ocsp.json), or nil when absent/invalid.
-- Must stay above resolve_leaf_must_staple / cert_must_staple_bool: a local
-- ============================================================================
-- read_ocsp_json(fingerprint)
-- ============================================================================
-- PURPOSE:
--   Load OCSP metadata from ocsp.json. Per-request cached to avoid repeated disk reads.
--   Critical metadata source: expires_unix, must_staple, tombstoned, soft_recall_gen.
--
-- PARAMETERS:
--   fingerprint (string|nil): leaf SPKI fingerprint (64 hex chars)
--
-- RETURNS:
--   (table): parsed ocsp.json object with metadata fields
--   (nil): if file missing, unreadable, or invalid JSON
--
-- SIDE EFFECTS:
--   - Reads: /var/cache/bunkerweb/ssl/{shard}/{fp}/ocsp.json from disk
--   - Per-request cache: stores result in ngx.ctx.bw_ocsp_json_cache (dedup)
--   - No writes or external calls
--   - Performance: O(1) for cache hits, ~2ms for disk reads
--
-- DESIGN NOTES:
--   - Per-request caching: Avoids re-reading same file in single handshake
--   - Dedup logic: Distinguishes "file missing" (false) from "found" (table)
--   - Fail-safe: Returns nil on JSON decode error (malformed file)
--   - Disk layout: Uses 2-char sharding by fingerprint (0x{fp[0]}/{fp[1]}/{fp}.json)
--   - Truncate safety: Empty file (truncate race) returns nil
--   - Type checking: Only returns if decoded to table (rejects scalar JSON)
--   - Called by: All freshness gates, ligand_or_meta(), warm_cache()
--   - Related: read_ocsp_ligand() is companion for outside ligand
--
-- RELATED:
--   - ligand_or_meta() merges this with outside ligand
--   - resp_still_fresh() uses metadata for freshness check
--   - warm_cache() validates metadata before caching
--   - read_ocsp_ligand() companion for /var/cache/bunkerweb/ssl/ocsp-ligand/{fp}
--
-- ============================================================================
read_ocsp_json = function(fingerprint)
	fingerprint = fp64_or_nil(fingerprint)
	if not fingerprint then
		return nil
	end

	-- Initialize per-request cache on first use
	local ctx = ngx.ctx
	if ctx and not ctx.bw_ocsp_json_cache then
		ctx.bw_ocsp_json_cache = {}
	end

	-- Check per-request cache first
	if ctx and ctx.bw_ocsp_json_cache then
		local cached = ctx.bw_ocsp_json_cache[fingerprint]
		if cached ~= nil then
			-- Distinguish between "file not found" (false) and "found" (table)
			if cached == false then
				return nil
			end
			return cached
		end
	end

	-- Cache miss: read from disk
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
		-- missing or empty (truncate): both cache as absent for this request.
		-- l1_body_matches_disk distinguishes empty via read_file's second return.
		if ctx and ctx.bw_ocsp_json_cache then
			ctx.bw_ocsp_json_cache[fingerprint] = false
		end
		return nil
	end
	local ok, decoded = pcall(function()
		return require("cjson").decode(raw)
	end)
	if ok and type(decoded) == "table" then
		-- Cache successful decode
		if ctx and ctx.bw_ocsp_json_cache then
			ctx.bw_ocsp_json_cache[fingerprint] = decoded
		end
		return decoded
	end
	-- Cache decode failure to prevent re-reading
	if ctx and ctx.bw_ocsp_json_cache then
		ctx.bw_ocsp_json_cache[fingerprint] = false
	end
	return nil
end

-- ============================================================================
-- ocsp_json_must_staple(meta)
-- ============================================================================
-- PURPOSE:
--   Check if ocsp.json declares must_staple=true (job-recorded TLS Feature flag).
--   Used as fallback when TLS Feature extension unavailable.
--
-- PARAMETERS:
--   meta (table|nil): ocsp.json metadata
--
-- RETURNS:
--   (boolean): true only if must_staple field == true
--   (boolean): false otherwise (nil, missing field, or non-true value)
--
-- SIDE EFFECTS:
--   - No reads/writes or state modification
--   - Performance: O(1) field check, ~0.01ms
--
-- DESIGN NOTES:
--   - Job-recorded flag: Set by ocsp-refresh job after parsing TLS Feature
--   - Exact match: Only true value accepted (false/nil/string = false)
--   - Fallback source: Used when TLS Feature parsing unavailable
--   - Called by: resolve_leaf_must_staple() as secondary check
--   - Related: has_must_staple() checks live TLS Feature extension
--
-- RELATED:
--   - has_must_staple() checks TLS Feature from certificate
--   - resolve_leaf_must_staple() wraps both checks (TLS Feature + ocsp.json)
--   - cert_must_staple_bool() boolean variant for strict contexts
--
-- ============================================================================
-- True only when the job recorded must_staple=true in ocsp.json (resty-invisible TLS Feature).
local function ocsp_json_must_staple(meta)
	return meta ~= nil and meta.must_staple == true
end

-- Tri-state leaf Must-Staple: TLS Feature, then ocsp.json positive, then unknown→nil.
-- Fail-closed gate: resolve_leaf_must_staple(...) ~= false.
-- meta without must_staple=true must NOT invent false when TLS Feature is unknown
-- (parse miss / unrecognized text) — aligns with HTTP leaf_requires tls_known rule.
-- ============================================================================
-- resolve_leaf_must_staple(cert_pem, fingerprint)
-- ============================================================================
-- PURPOSE:
--   Tri-state Must-Staple detection: checks TLS Feature extension + ocsp.json.
--   Returns true/false/nil (unknown treated as required by callers).
--
-- PARAMETERS:
--   cert_pem (string|nil): leaf certificate PEM
--   fingerprint (string|nil): leaf SPKI fingerprint fallback
--
-- RETURNS:
--   true: Must-Staple required (TLS Feature or ocsp.json flag)
--   false: Must-Staple explicitly disabled (TLS Feature confirms absent)
--   nil: unknown (cannot prove false, treat as required)
--
-- SIDE EFFECTS:
--   - Calls: has_must_staple(), ocsp_json_must_staple(), read_ocsp_json()
--   - No writes or state modification
--
-- DESIGN NOTES:
--   - Tri-state: true (required), false (optional), nil (unknown = required)
--   - Fail-closed: Unknown defaults to Must-Staple enforcement
--   - Priority: TLS Feature checked first (authoritative)
--   - Fallback: fingerprint used if cert_pem unavailable
--   - JSON check: ocsp.json must_staple=true as secondary signal
--   - Absence != false: Missing meta flag does not prove false
--   - Called by: staple(), probe(), set_certs_from_pem()
--
-- RELATED:
--   - has_must_staple() checks TLS Feature extension
--   - ocsp_json_must_staple() checks ocsp.json flag
--   - cert_must_staple_bool() boolean variant for strict contexts
--
-- ============================================================================
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
		-- Resty positively parsed: no Must-Staple (extension absent or non-MS features).
		return false
	end
	-- tls == nil: unknown — do not trust "meta present without must_staple=true" as
	-- proven-false (job may omit the flag; resty may have failed).
	return nil
end

-- ============================================================================
-- cert_must_staple_bool(pem, fail_closed_unknown)
-- ============================================================================
-- PURPOSE:
--   Boolean Must-Staple for any PEM block (leaf or intermediate).
--   Used for bag filtering + intermediate chain validation.
--
-- PARAMETERS:
--   pem (string): certificate PEM block (leaf or intermediate)
--   fail_closed_unknown (boolean): true = unknown→Must-Staple, false = unknown→optional
--
-- RETURNS:
--   (boolean): true if Must-Staple required, false if optional
--
-- SIDE EFFECTS:
--   - Calls: has_must_staple(), spki_fingerprint(), read_ocsp_json()
--   - Per-request cache via read_ocsp_json
--   - No writes or state modification
--   - Performance: O(1) with cache, ~1ms for misses
--
-- DESIGN NOTES:
--   - Boolean return: Unlike resolve_leaf (tri-state), always true/false
--   - Unknown handling: Configurable fail_closed_unknown parameter
--   - Priority: TLS Feature > ocsp.json > configurable default
--   - Used for: Intermediate filtering, bag verification
--   - Strict mode: fail_closed_unknown=true (intermediate path)
--   - Loose mode: fail_closed_unknown=false (rare fallback)
--   - Called by: Chain validation, intermediate filtering
--
-- RELATED:
--   - resolve_leaf_must_staple() tri-state variant
--   - has_must_staple() TLS Feature detector
--   - ocsp_json_must_staple() JSON flag checker
--
-- ============================================================================
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
	if tls == false then
		return false
	end
	-- tls == nil: same as resolve_leaf — meta-without-flag is not proven-false.
	return fail_closed_unknown == true
end

-- ============================================================================
-- meta_unix_field(meta, key)
-- ============================================================================
-- PURPOSE:
--   Extract and validate unix timestamp field from metadata (helper).
--   Used for colony consensus checks (floor, this_update, etc).
--
-- PARAMETERS:
--   meta (table|nil): metadata object
--   key (string): field name to extract (e.g., "this_update_unix")
--
-- RETURNS:
--   (number): validated positive unix timestamp
--   (nil): if meta missing, key missing, or value invalid
--
-- SIDE EFFECTS:
--   - Calls: positive_unix() for validation
--   - No reads/writes or state modification
--   - Performance: O(1), ~0.01ms
--
-- DESIGN NOTES:
--   - Floor consensus: Colony uses CA-signed this_update_unix (not wall clock)
--   - Missing = no opinion: Never invents 0 (missing doesn't equal 0)
--   - Clock drift: Uses signed timestamps not wall-clock (nodes drift)
--   - Called by: cluster_floor_blocks() for consensus comparison
--   - Related: positive_unix() does actual validation
--
-- RELATED:
--   - positive_unix() for timestamp validation
--   - cluster_floor_blocks() uses this for consensus check
--   - parse_floor_rank() similar helper for floor file parsing
--
-- ============================================================================
-- Colony floor: peers advance ocsp-floor/{fp} on publish/tombstone using CA-signed
-- this_update_unix only (not wall-clock published_unix — clocks drift across nodes).
-- Missing local this_update_unix is no opinion (do not treat as 0 vs a positive floor).
local function meta_unix_field(meta, key)
	if type(meta) ~= "table" or type(key) ~= "string" then
		return nil
	end
	return positive_unix(meta[key])
end

-- ============================================================================
-- parse_floor_rank(raw)
-- ============================================================================
-- PURPOSE:
--   Parse JSON floor file to extract CA-signed this_update_unix ranking.
--   Used for cluster consensus validation (prevents stale OCSP).
--
-- PARAMETERS:
--   raw (string|nil): file contents of /var/cache/bunkerweb/ssl/ocsp-floor/{fp}
--
-- RETURNS:
--   (number): positive unix this_update_unix from JSON (colony rank)
--   (nil): if file empty, invalid JSON, or missing this_update_unix
--
-- SIDE EFFECTS:
--   - Calls: cjson.decode() for JSON parsing
--   - Calls: meta_unix_field() for timestamp validation
--   - No writes or state modification
--   - Performance: O(n) JSON parse, ~0.5ms typical
--
-- DESIGN NOTES:
--   - Floor rank: Peer's CA-signed this_update_unix (consensus truth)
--   - JSON format: {"this_update_unix": <number>} from job publish
--   - Whitespace trim: Handles surrounding whitespace safely
--   - Fail-safe: Returns nil on decode error (invalid JSON)
--   - Validation: Must be positive unix timestamp (via meta_unix_field)
--   - Called by: cluster_floor_blocks() to read peer consensus
--   - Related: Colony floor used when multiple peers must agree
--
-- RELATED:
--   - cluster_floor_blocks() reads floor file and parses it
--   - meta_unix_field() validates timestamp field
--   - Job publishes ocsp-floor/{fp} with consensus
--
-- ============================================================================
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
-- Always sample live shard timing; caller meta can claim a higher this_update than
-- disk and fail-open colony floor during a lagging publish.
local function cluster_floor_blocks(fingerprint, _meta)
	fingerprint = fp64_or_nil(fingerprint)
	if not fingerprint then
		return false
	end
	local floor_rank = parse_floor_rank(read_file("/var/cache/bunkerweb/ssl/ocsp-floor/" .. fingerprint))
	if not floor_rank or floor_rank <= 0 then
		return false
	end
	local local_rank = meta_unix_field(read_ocsp_json(fingerprint), "this_update_unix")
	-- Missing live timing: no opinion — never invent 0 vs a positive floor,
	-- and never trust caller meta over a retracted/lagging shard.
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

-- ============================================================================
-- shard_not_paged(meta, fingerprint)
-- ============================================================================
-- PURPOSE:
--   Canary gate: returns true if OCSP not verified by canary handshake.
--   Prevents stapling unvalidated OCSP from restore (paged=false).
--
-- PARAMETERS:
--   meta (table|nil): ocsp.json metadata (can be nil, will check ligand)
--   fingerprint (string|nil): optional leaf SPKI fingerprint to sample live ligand
--
-- RETURNS:
--   (boolean): true if paged != true (not yet canary-validated)
--   (boolean): false if paged == true (canary succeeded)
--
-- SIDE EFFECTS:
--   - Calls: ligand_or_meta() to sample live state if fingerprint provided
--   - Reads: outside ligand from /var/cache/bunkerweb/ssl/ocsp-ligand/{fp}
--   - No writes or state modification
--
-- DESIGN NOTES:
--   - Canary: Explicit paged=true required (missing/false means unvalidated)
--   - Live sampling: When fingerprint provided, samples live ligand not stale meta
--   - Fail-closed: Missing/unpaged returns true (refuse to staple)
--   - Restore recovery: Job sets paged=false on restore, true on canary pass
--   - Used in: staple path before attachment (staple_one_leaf)
--   - Performance: O(1) ligand lookup, ~0.5ms typical
--
-- RELATED:
--   - ligand_or_meta() to get live state from both shard and outside ligand
--   - resp_still_fresh() other freshness gate
--   - cluster_floor_blocks() consensus gate
--
-- ============================================================================
local function shard_not_paged(meta, fingerprint)
	if fingerprint then
		local live = ligand_or_meta(nil, fingerprint)
		if type(live) ~= "table" then
			return true
		end
		meta = live
	end
	if type(meta) ~= "table" then
		return true
	end
	return meta.paged ~= true
end

-- ============================================================================
-- meta_tombstoned(meta, fingerprint)
-- ============================================================================
-- PURPOSE:
--   Tombstone gate: detects when OCSP response is being retired (DER unlinked).
--   Blocks Must-Staple during multi-step atomicity window of job publish.
--
-- PARAMETERS:
--   meta (table|nil): ocsp.json metadata (from disk or caller state)
--   fingerprint (string|nil): optional leaf SPKI fingerprint for live ligand check
--
-- RETURNS:
--   (boolean): true if tombstoned == true (response being retired)
--   (boolean): false if not tombstoned or meta missing
--
-- SIDE EFFECTS:
--   - Calls: ligand_or_meta() to sample live state if fingerprint provided
--   - Reads: live ligand and ocsp.json from disk
--   - No writes or state modification
--
-- DESIGN NOTES:
--   - Tombstone: Job writes tombstoned=true BEFORE DER unlink (atomicity)
--   - Why needed: L1 cache can return "last GOOD" while job unlinks DER mid-flight
--   - Live sampling: fingerprint forces check of live ligand (not stale meta)
--   - Epoch not enough: ocsp_epoch bump alone insufficient (lag issue)
--   - Called before: attachment (staple_one_leaf), Must-Staple enforcement
--   - Performance: O(1) cache/file lookup, ~0.5ms typical
--
-- RELATED:
--   - ligand_or_meta() for live state sampling
--   - shard_not_paged() similar freshness gate (canary)
--   - cluster_floor_blocks() consensus gate
--   - Job publishes ocsp.json with tombstoned=true during retire
--
-- ============================================================================
local function meta_tombstoned(meta, fingerprint)
	if type(meta) == "table" and meta.tombstoned == true then
		return true
	end
	if fingerprint then
		local live = ligand_or_meta(nil, fingerprint)
		if type(live) == "table" and live.tombstoned == true then
			return true
		end
	end
	return false
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

-- ============================================================================
-- ocsp_ligand_path(fingerprint)
-- ============================================================================
-- PURPOSE:
--   Build path to outside ligand file (/var/cache/bunkerweb/ssl/ocsp-ligand/{fp}).
--   Used for HTTP/stream cross-zone OCSP state sharing.
--
-- PARAMETERS:
--   fingerprint (string): SPKI fingerprint (64 hex chars, any case)
--
-- RETURNS:
--   (string): full path to ocsp-ligand file (not normalized, lowercase fingerprint)
--
-- SIDE EFFECTS:
--   - String manipulation only, no I/O or state modification
--   - Performance: O(1) string concat, ~0.01ms
--
-- DESIGN NOTES:
--   - File location: /var/cache/bunkerweb/ssl/ocsp-ligand/{fingerprint}
--   - Flat layout: Unlike ocsp.json (2-level sharding), ligand is flat namespace
--   - Lowercase: Job + ocsp_pin both use lowercase hex normalization
--   - Cross-zone: HTTP (ngx.shared.internalstore) cannot read stream dict
--   - Outside ligand: Binding + paging truth for consensus checks
--   - Called by: read_ocsp_ligand(), ligand_or_meta()
--   - Related: ocsp_path() for DER, ocsp_json paths use sharding
--
-- RELATED:
--   - read_ocsp_ligand() reads this path
--   - ocsp_path() for DER file path
--   - fp64_or_nil() for fingerprint normalization
--
-- ============================================================================
-- Disk paths and pin bus use lowercase hex (job + ocsp_pin). is_fp64 allows
-- A-F; normalize before path join / cache key / fingerprint equality checks.
local function ocsp_ligand_path(fingerprint)
	return "/var/cache/bunkerweb/ssl/ocsp-ligand/" .. fingerprint:lower()
end

-- Integer soft_recall_gen from ligand / ocsp.json / allow-pin.
-- Missing key → 0 (upgrade grace so pre-gen pins still match).
-- Present but non-integer (table, bool, non-digit string, NaN, negative) → nil
-- so generation_tuple / allow-pin match fail closed (KEEP pin; no CAS revoke).
-- Job-minted counter: bumps on soft-recall so peer-refuse / allow identity
-- (der_sha256, soft_recall_gen) cannot re-match a leftover pin after re-page.
--
-- ============================================================================
-- soft_recall_gen_of(meta)
-- ============================================================================
-- PURPOSE:
--   Extract soft-recall generation number from metadata (for pin matching).
--   Maps omitted gen to 0 (upgrade grace), rejects invalid types (fail-closed).
--
-- PARAMETERS:
--   meta (table|nil): ocsp.json or ligand metadata
--
-- RETURNS:
--   (number): generation number (0 = omitted key, upgrade grace)
--   (nil): type-drift (invalid value, NaN, negative, or false sentinel)
--
-- SIDE EFFECTS:
--   - Type validation: Checks number/string/nil for soft_recall_gen field
--   - No reads/writes or external calls
--   - Performance: O(1) type checking, ~0.01ms
--
-- DESIGN NOTES:
--   - Omit = 0: Missing soft_recall_gen key defaults to 0 (upgrade grace)
--   - False sentinel: read_ocsp_ligand stores false when key present but invalid
--   - Type-drift: Invalid types (false, table, etc.) return nil (fail-closed)
--   - Numeric validation: Rejects NaN/infinity/negative (only non-negative allowed)
--   - String parsing: Digit-only (rejects scientific notation, signs, octal)
--   - Floor truncation: Fractional JSON numbers truncated to integers
--   - Publish-gap safety: Must check raw field first to distinguish omit vs invalid
--   - Used by: generation_tuple, consensus checking, must_staple enforcement
--
-- RELATED:
--   - generation_tuple() uses this for soft-recall binding
--   - read_ocsp_ligand() stores false for invalid ligand.soft_recall_gen
--   - live_soft_recall_gen() wraps this with ligand_or_meta sampling
--   - Pin consensus (ocsp_pin.lua) matches via (sha, gen) tuple
--
-- EXAMPLE:
--   local gen = soft_recall_gen_of(meta)
--   if gen == nil then return keep_allow[gen_type_drift] end
--   -- Can use gen for pin matching
--
-- ============================================================================
soft_recall_gen_of = function(meta)
	if type(meta) ~= "table" then
		return 0
	end
	local raw = meta.soft_recall_gen
	if raw == nil then
		return 0
	end
	if type(raw) == "number" then
		-- Reject NaN / inf / negative; floor truncates fractional JSON numbers.
		if raw ~= raw or raw == math.huge or raw == -math.huge or raw < 0 then
			return nil
		end
		return math.floor(raw)
	end
	if type(raw) == "string" then
		-- Digit-only only (no tonumber("1e2") / "08" octal surprises).
		if not raw:match("^%d+$") then
			return nil
		end
		return tonumber(raw)
	end
	-- false sentinel (read_ocsp_ligand) and any other non-number → type drift.
	return nil
end

-- Load ocsp-ligand/{fp}. Prefer this over in-shard ocsp.json for der_sha256 binding.
-- Reject when ligand.fingerprint disagrees with the path fingerprint (a self-asserted
-- fingerprint inside the file must not bless a different SPKI directory).
-- Per-request cache: avoids re-reading same ligand multiple times in one handshake
read_ocsp_ligand = function(fingerprint)
	fingerprint = fp64_or_nil(fingerprint)
	if not fingerprint then
		return nil
	end

	-- Initialize per-request cache on first use
	local ctx = ngx.ctx
	if ctx and not ctx.bw_ocsp_ligand_cache then
		ctx.bw_ocsp_ligand_cache = {}
	end

	-- Check per-request cache first
	if ctx and ctx.bw_ocsp_ligand_cache then
		local cached = ctx.bw_ocsp_ligand_cache[fingerprint]
		if cached ~= nil then
			-- Distinguish between "file not found" (false) and "found" (table)
			if cached == false then
				return nil
			end
			return cached
		end
	end

	-- Cache miss: read from disk
	local raw = read_file(ocsp_ligand_path(fingerprint))
	if not raw or raw == "" then
		-- Cache the "not found" result to prevent re-reading
		if ctx and ctx.bw_ocsp_ligand_cache then
			ctx.bw_ocsp_ligand_cache[fingerprint] = false
		end
		return nil
	end
	local ok, obj = pcall(function()
		return require("cjson").decode(raw)
	end)
	if not ok or type(obj) ~= "table" then
		-- Cache decode failure to prevent re-reading
		if ctx and ctx.bw_ocsp_ligand_cache then
			ctx.bw_ocsp_ligand_cache[fingerprint] = false
		end
		return nil
	end
	local sha = obj.der_sha256
	if type(sha) ~= "string" then
		-- Cache validation failure to prevent re-reading
		if ctx and ctx.bw_ocsp_ligand_cache then
			ctx.bw_ocsp_ligand_cache[fingerprint] = false
		end
		return nil
	end
	sha = sha:lower()
	if #sha ~= 64 or not sha:match("^[0-9a-f]+$") then
		-- Cache validation failure to prevent re-reading
		if ctx and ctx.bw_ocsp_ligand_cache then
			ctx.bw_ocsp_ligand_cache[fingerprint] = false
		end
		return nil
	end
	if type(obj.fingerprint) == "string" and obj.fingerprint:lower() ~= fingerprint then
		-- Cache validation failure to prevent re-reading
		if ctx and ctx.bw_ocsp_ligand_cache then
			ctx.bw_ocsp_ligand_cache[fingerprint] = false
		end
		return nil
	end
	obj.der_sha256 = sha
	-- Preserve key presence. soft_recall_gen_of maps omitted→0 for allow-pin
	-- upgrade grace, but publish-gap keep requires an *explicit* key on the
	-- ligand object (nil here means omitted — see l1_body_matches_disk).
	-- Assigning soft_recall_gen_of(obj) unconditionally turned every omit into
	-- 0 and made the publish-gap nil-check dead (fail-open mid-promote).
	-- Present-but-invalid must NOT become nil: a later soft_recall_gen_of would
	-- treat that as omit→0 (upgrade grace) and rematch leftover gen-0 pins.
	-- Sentinel false → soft_recall_gen_of returns nil (type-drift / fail closed).
	local raw_gen = obj.soft_recall_gen
	if raw_gen == nil then
		obj.soft_recall_gen = nil
	else
		local normalized = soft_recall_gen_of(obj)
		if type(normalized) == "number" then
			obj.soft_recall_gen = normalized
		else
			obj.soft_recall_gen = false
		end
	end
	-- Cache successful decode
	if ctx and ctx.bw_ocsp_ligand_cache then
		ctx.bw_ocsp_ligand_cache[fingerprint] = obj
	end
	return obj
end

-- Harden expires_unix the same way as soft_recall_gen / thisUpdate (positive_unix).
local positive_expires_unix = positive_unix

-- Merge already-read ligand with shard meta (caller reads ligand once per decision).
-- Rules (load-bearing — HTTP and stream must agree):
--   * ligand wins der_sha256; soft_recall_gen only when ligand key is present
--     (omit must not clobber shard gen→upgrade-grace 0 and rematch leftover pins)
--   * tombstone from EITHER side forces tombstoned + paged=false
--   * paged=true only when shard meta exists AND both sides say paged
--     (missing shard meta never grants canary trust)
--   * expires_unix = min of positive values (generation authority pairs with
--     the tighter death clock, not a stale looser shard deadline)
--   * fingerprint is the path fp (never trust a self-assert alone)
--
-- MERGE ALGORITHM:
--   1. Copy shard_meta into merged (avoid mutating caller's cache entry)
--   2. Overlay ligand.der_sha256 (binding is always ligand's version when present)
--   3. Soft_recall_gen: only update if ligand key IS PRESENT (omit=0 is implicit; omit-key stays omit)
--   4. Tombstone: if either side says tombstoned=true → tombstoned=true + paged=false
--   5. Paged: true only if shard exists AND shard.paged AND ligand.paged (AND gate = fail-safe)
--   6. Expires: min(shard.expires, ligand.expires) when both present, else ligand>shard>nil
--   7. Fingerprint: use path fp (argument), else ligand fp, else shard fp (never self-assert alone)
--
-- ============================================================================
-- merge_ligand(shard_meta, ligand, fingerprint)
-- ============================================================================
-- PURPOSE:
--   Merge outside ligand with in-shard metadata (ligand wins tiebreaks).
--   Ensures HTTP and stream see identical state (deterministic merge).
--
-- PARAMETERS:
--   shard_meta (table|nil): in-shard ocsp.json metadata
--   ligand (table|nil): outside ligand from /var/cache/.../ocsp-ligand/{fp}
--   fingerprint (string|nil): path-based SPKI fingerprint (authoritative source)
--
-- RETURNS:
--   (table): merged metadata with ligand-preferred fields
--   (nil): if both shard and ligand missing
--
-- SIDE EFFECTS:
--   - Creates: shallow copy of shard_meta (prevents caller mutation)
--   - No external calls or state modification
--   - Performance: O(n) where n = field count (~10 fields), ~0.1ms
--
-- DESIGN NOTES:
--   - Ligand priority: Ligand fields win over shard (outside state > in-shard)
--   - Shallow copy: Returns copy of shard when no ligand (prevents poisoning)
--   - Field logic:
--     * der_sha256: ligand only (binding source)
--     * soft_recall_gen: ligand keeps shard gen if omitted (publish-gap safety)
--     * tombstoned: true if either side tombstoned (OR gate = fail-safe)
--     * paged: true only if both shard.paged AND ligand.paged (AND gate)
--     * expires_unix: min(shard, ligand) when both present (takes tightest)
--     * fingerprint: path arg > ligand > shard (never self-assert alone)
--   - Determinism: Identical output for HTTP and stream (no random/order deps)
--   - Called by: ligand_or_meta() as core merge operation
--
-- RELATED:
--   - ligand_or_meta() wrapper that reads both sources
--   - read_ocsp_json() for shard source
--   - read_ocsp_ligand() for ligand source
--   - All validation gates use merged result
--
-- ============================================================================
-- INVARIANT: HTTP + stream must produce identical merges (no version skew, no random errors)
local function merge_ligand(shard_meta, ligand, fingerprint)
	if not ligand then
		-- Shallow copy: read_ocsp_json caches the shard table in ngx.ctx; returning
		-- it by reference lets a caller mutate poison the rest of the request.
		if type(shard_meta) ~= "table" then
			return shard_meta
		end
		local copy = {}
		for k, v in pairs(shard_meta) do
			copy[k] = v
		end
		if type(fingerprint) == "string" then
			copy.fingerprint = fingerprint:lower()
		end
		return copy
	end
	local merged = {}
	if type(shard_meta) == "table" then
		for k, v in pairs(shard_meta) do
			merged[k] = v
		end
	end
	merged.der_sha256 = ligand.der_sha256
	-- Present ligand gen (number / false sentinel) wins. Omitted key leaves shard
	-- gen intact — unconditional nil assign turned soft-recall shard gen=N into
	-- omit→0 and rematched leftover gen-0 pins while ligand lagged the bump.
	if ligand.soft_recall_gen ~= nil then
		merged.soft_recall_gen = ligand.soft_recall_gen
	end
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
	local shard_exp = type(shard_meta) == "table" and positive_expires_unix(shard_meta.expires_unix) or nil
	local ligand_exp = positive_expires_unix(ligand.expires_unix)
	if shard_exp and ligand_exp then
		merged.expires_unix = math.min(shard_exp, ligand_exp)
	elseif ligand_exp then
		merged.expires_unix = ligand_exp
	elseif shard_exp then
		merged.expires_unix = shard_exp
	end
	if type(fingerprint) == "string" then
		-- Path fp wins; lowercase so ligand_verdict equality is case-stable.
		merged.fingerprint = fingerprint:lower()
	elseif type(ligand.fingerprint) == "string" then
		merged.fingerprint = ligand.fingerprint:lower()
	end
	return merged
end

-- ============================================================================
-- ligand_or_meta(_meta, fingerprint)
-- ============================================================================
-- PURPOSE:
--   Get effective live metadata: merges outside ligand + in-shard ocsp.json.
--   Always freshly sampled (ignores caller meta to prevent stale decisions).
--   Critical for all freshness/validation gates.
--
-- PARAMETERS:
--   _meta (table|nil): caller's metadata (IGNORED; always samples fresh)
--   fingerprint (string): leaf SPKI fingerprint (samples both shard + ligand)
--
-- RETURNS:
--   (table): merged metadata with fields from both sources (ligand wins tiebreaks)
--   (nil): if both shard and ligand missing or invalid
--
-- SIDE EFFECTS:
--   - Reads: /var/cache/bunkerweb/ssl/{shard}/{fp}/ocsp.json (in-shard)
--   - Reads: /var/cache/bunkerweb/ssl/ocsp-ligand/{fp} (outside ligand)
--   - Per-request cache: Both read_ocsp_json + read_ocsp_ligand are per-request cached
--   - No writes or external calls
--   - Performance: O(1) with per-request cache, ~1ms for cache misses
--
-- DESIGN NOTES:
--   - Always fresh: Never trusts caller meta, always re-samples both sources
--   - Fail-safe: Missing shard = nil (don't resurrect stale caller state)
--   - Merge strategy: Ligand favored (outside state wins over in-shard)
--   - Used everywhere: All validation gates call this for live state
--   - Per-request cached: Avoids redundant reads within single handshake
--   - Caller meta ignored: Prevents stale decisions from lag (tombstone/gen bump)
--   - Called by: resp_still_fresh, warm_cache, meta_tombstoned, shard_not_paged
--
-- RELATED:
--   - read_ocsp_json() reads in-shard metadata
--   - read_ocsp_ligand() reads outside ligand file
--   - merge_ligand() performs ligand+shard merge (ligand wins)
--   - All freshness gates sample via this function
--
-- ============================================================================
ligand_or_meta = function(_meta, fingerprint)
	return merge_ligand(read_ocsp_json(fingerprint), read_ocsp_ligand(fingerprint), fingerprint)
end

-- Live soft_recall_gen after ligand↔shard merge. HTTP and stream must share this:
-- ligand-only soft_recall_gen_of rematches leftover gen-0 pins when the ligand
-- omits the key while the shard already holds a bumped gen (same class as
-- merge_ligand omit-keeps-shard). Missing meta+ligand → upgrade-grace 0.
-- ============================================================================
-- live_soft_recall_gen(fingerprint)
-- ============================================================================
-- PURPOSE:
--   Get current soft-recall generation after ligand+shard merge.
--   Used for pin consensus and generation binding verification.
--
-- PARAMETERS:
--   fingerprint (string): leaf SPKI fingerprint
--
-- RETURNS:
--   (number): soft_recall_gen from merged metadata (0 if omitted)
--   (nil): if fingerprint invalid or type-drift (false sentinel)
--
-- SIDE EFFECTS:
--   - Calls: ligand_or_meta() for live metadata merge (fresh sample)
--   - Per-request cache via ligand_or_meta()
--   - No writes or state modification
--   - Performance: O(1) with cache, ~0.5ms for misses
--
-- DESIGN NOTES:
--   - Live sample: Always re-reads fresh ligand + shard (ignore caller state)
--   - Merge: Ligand gen wins, shard gen kept if ligand omits (publish-gap safety)
--   - Omit = 0: Missing gen key defaults to 0 (upgrade grace for old pins)
--   - Type-drift: Non-integer → nil (fail-closed for generation matching)
--   - Used for: Pin consensus, allow-pin matching, generation binding
--   - Related: soft_recall_gen_of() for type validation
--   - Export: _M.live_soft_recall_gen() for public use
--
-- RELATED:
--   - ligand_or_meta() for live metadata merge
--   - soft_recall_gen_of() for generation extraction + validation
--   - generation_tuple() uses this for binding identity
--   - Pin consensus (ocsp_pin.lua) uses this for matching
--
-- ============================================================================
-- Type-drift (false sentinel / invalid) → nil (fail closed).
local function live_soft_recall_gen(fingerprint)
	fingerprint = fp64_or_nil(fingerprint)
	if not fingerprint then
		return nil
	end
	local live = ligand_or_meta(nil, fingerprint)
	if type(live) ~= "table" then
		return 0
	end
	return soft_recall_gen_of(live)
end

-- ============================================================================
-- generation_tuple(meta, resp)
-- ============================================================================
-- PURPOSE:
--   Build soft-recall binding (der_sha256, soft_recall_gen) for pin consensus.
--   Unique identity for OCSP response including per-cert generation counter.
--
-- PARAMETERS:
--   meta (table|nil): ocsp.json metadata with der_sha256, soft_recall_gen
--   resp (string|nil): OCSP DER response bytes (preferred over meta SHA)
--
-- RETURNS:
--   (string, number): (der_sha256_hex, generation) for CAS/rematch
--   (string, nil): (der_sha256_hex, nil) if gen missing/invalid (type-drift)
--   (nil, nil): if no body (resp or meta.der_sha256)
--
-- SIDE EFFECTS:
--   - Calls: resp_binding() to hash resp DER, soft_recall_gen_of() for gen
--   - No writes or state modification
--
-- DESIGN NOTES:
--   - Soft-recall: (SHA, gen) tuple prevents stale allow-pins after cert rotation
--   - Priority: Actual resp DER SHA wins over meta (never use meta alone after refuse)
--   - Type-drift: gen=nil means type mismatch (caller must not CAS on body alone)
--   - Incomplete identity: Callers must handle (body, nil) → cannot rematch on SHA alone
--   - Used for: Peer consensus (allow-pin bus), Must-Staple enforcement gates
--   - Performance: O(1) hash + type checking, ~0.5ms typical
--   - Edge case: Probe paths refusing cert/ligand use meta SHA (tombstone/serial/canary drops)
--
-- RELATED:
--   - resp_binding() to compute DER SHA256
--   - soft_recall_gen_of() to extract generation number from meta
--   - must_staple_binds_shared_ligand() uses this for binding verification
--   - Pin consensus (ocsp_pin.lua) uses generation_tuple for CAS
--
-- EXAMPLE:
--   local sha, gen = generation_tuple(meta, resp)
--   if gen == nil then
--     -- Type-drift: incomplete identity, don't rematch on SHA alone
--     return pin.gen_type_drift
--   end
--   -- Can safely compare (sha, gen) with previous allow-pin
--
-- ============================================================================
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
	local gen = soft_recall_gen_of(meta)
	if type(gen) ~= "number" then
		return body, nil
	end
	return body, gen
end

-- ============================================================================
-- serial_blacklist_blocks(fingerprint, resp)
-- ============================================================================
-- PURPOSE:
--   Revocation gate: blocks OCSP if leaf serial banned by serial-blacklist.json.
--   Used during manual revocation before CRL/OCSP response updates.
--
-- PARAMETERS:
--   fingerprint (string|nil): leaf SPKI fingerprint
--   resp (string): OCSP DER response bytes (to extract serial)
--
-- RETURNS:
--   (boolean): true if serial is banned (Must-Staple blocked)
--   (boolean): false if serial not banned, not in blacklist, or fingerprint missing
--
-- SIDE EFFECTS:
--   - Reads: /var/cache/bunkerweb/ssl/{shard}/{fp}/serial-blacklist.json
--   - Calls: ocsp_resp_serial_hex() to extract response serial
--   - Per-request cache: caches result by (fingerprint, body_sha) key
--   - Logs: ERR if blacklist unreadable/ambiguous or serial banned
--
-- DESIGN NOTES:
--   - Ban format: serial-blacklist.json with serial_hex field (uppercase)
--   - Single serial: Bans one serial per cert (reissue on same key allowed)
--   - Fail-closed: Unreadable/ambiguous blacklist refuses staple
--   - Truncate race: Empty file (truncate mid-write) fails closed
--   - JSON security: Rejects duplicate serial_hex keys (parsing oddities)
--   - Performance: O(1) with per-request cache, ~1ms typical
--   - Used in: staple path (staple_one_leaf → resp_still_fresh gate)
--   - Related: Manual revocation flow (not CRL/OCSP updates)
--
-- RELATED:
--   - ocsp_resp_serial_hex() to extract serial from response DER
--   - resp_still_fresh() freshness gate that calls this
--   - Must-Staple enforcement gate
--
-- ============================================================================
local function serial_blacklist_blocks(fingerprint, resp)
	fingerprint = fp64_or_nil(fingerprint)
	if not fingerprint or type(resp) ~= "string" or resp == "" then
		return false
	end

	-- Initialize per-request cache on first use
	local ctx = ngx.ctx
	if ctx and not ctx.bw_ocsp_serial_cache then
		ctx.bw_ocsp_serial_cache = {}
	end

	-- Cache key needs a stable body id. When resp_binding fails, do NOT key as
	-- "fp|" — distinct unreadable DERs would collide and a prior "allowed"
	-- (no blacklist file) could fail-open a later banned body.
	local binding = resp_binding(resp)
	local serial_cache_key = nil
	if binding then
		serial_cache_key = fingerprint .. "|" .. binding
	end

	-- Check per-request cache first
	if serial_cache_key and ctx and ctx.bw_ocsp_serial_cache then
		local cached = ctx.bw_ocsp_serial_cache[serial_cache_key]
		if cached ~= nil then
			-- Cached value is boolean (true = blocked, false = allowed)
			return cached == true
		end
	end

	-- Cache miss: read and validate from disk
	local raw, why = read_file(
		"/var/cache/bunkerweb/ssl/"
			.. fingerprint:sub(1, 1)
			.. "/"
			.. fingerprint:sub(2, 2)
			.. "/"
			.. fingerprint
			.. "/serial-blacklist.json"
	)
	local blocked
	if not raw then
		-- Missing file: no ban. Empty (truncate race) = present-but-unreadable → refuse.
		if why == "empty" then
			log(ngx.ERR, "OCSP serial blacklist empty; refusing staple fp=" .. fingerprint:sub(1, 16) .. "...")
			blocked = true
		else
			blocked = false
		end
	else
		local ok_decode, obj = pcall(require("cjson").decode, raw)
		if not ok_decode or type(obj) ~= "table" then
			log(ngx.ERR, "OCSP serial blacklist unreadable; refusing staple fp=" .. fingerprint:sub(1, 16) .. "...")
			blocked = true
		else
			local banned = obj.serial_hex
			if type(banned) ~= "string" or banned == "" or not banned:match("^[0-9A-Fa-f]+$") then
				log(ngx.ERR, "OCSP serial blacklist unreadable; refusing staple fp=" .. fingerprint:sub(1, 16) .. "...")
				blocked = true
			else
				-- Reject duplicate / conflicting serial_hex keys disguised via JSON oddities:
				-- cjson gives one value; also refuse if a second distinct match exists in raw.
				local first = raw:match('"serial_hex"%s*:%s*"([0-9A-Fa-f]+)"')
				local rest = first
					and raw:match('"serial_hex"%s*:%s*"[0-9A-Fa-f]+".-("serial_hex"%s*:%s*"[0-9A-Fa-f]+")')
				if rest then
					log(
						ngx.ERR,
						"OCSP serial blacklist ambiguous; refusing staple fp=" .. fingerprint:sub(1, 16) .. "..."
					)
					blocked = true
				else
					local banned_hex = banned:upper():gsub("^0+", "")
					if banned_hex == "" then
						banned_hex = "0"
					end
					-- want_hex hit → banned. want miss + parseable body → not banned.
					-- Unreadable DER (no serials at all) → refuse (fail closed).
					local got_hex = ocsp_resp_serial_hex(resp, banned_hex)
					if got_hex == banned_hex then
						log(
							ngx.ERR,
							"OCSP serial blacklist refuse staple fp="
								.. fingerprint:sub(1, 16)
								.. "... serial_hex="
								.. banned_hex:sub(1, 16)
						)
						blocked = true
					elseif not ocsp_resp_serial_hex(resp) then
						log(
							ngx.ERR,
							"OCSP serial blacklist present but response serial unreadable; refusing staple fp="
								.. fingerprint:sub(1, 16)
								.. "..."
						)
						blocked = true
					else
						blocked = false
					end
				end
			end
		end
	end

	-- Cache result: store boolean (true = blocked, false = allowed).
	-- Skip when binding is nil (no stable key — see above).
	if serial_cache_key and ctx and ctx.bw_ocsp_serial_cache then
		ctx.bw_ocsp_serial_cache[serial_cache_key] = blocked
	end
	return blocked
end

-- Shared ligand verdict: one ligand read, hardened merge, body binding.
-- Single source of truth for HTTP (ssl-certificate-by-lua.conf) and stream
-- (this module). An inlined copy in the conf caused a zone-split after the
-- ============================================================================
-- ligand_verdict(shard_meta, fingerprint, resp)
-- ============================================================================
-- PURPOSE:
--   **CORE BINDING CHECKER**: Comprehensive OCSP validation via ligand+shard.
--   Single source of truth for HTTP/stream consistency (must be identical).
--   Prevents stapling wrong response, swapped files, or tombstoned bodies.
--
-- PARAMETERS:
--   shard_meta (table|nil): in-shard ocsp.json (ignored if live re-sample available)
--   fingerprint (string): leaf SPKI fingerprint
--   resp (string): OCSP DER response bytes
--
-- RETURNS:
--   (true, nil, meta_sha, body_sha, eff_meta): validation passed
--   (false, reason_code, meta_sha, body_sha, eff_meta): validation failed
--   reason_codes: fingerprint_mismatch, ligand_missing, tombstoned,
--                missing_der_sha256, invalid_der_sha256, der_sha256_mismatch
--
-- SIDE EFFECTS:
--   - Reads: live shard + ligand metadata (always fresh, ignores caller meta)
--   - Calls: read_ocsp_json(), read_ocsp_ligand(), merge_ligand(), resp_binding()
--   - Per-request cache: Both reads are per-request cached
--   - No writes or external calls
--   - Performance: O(1) with cache, ~1ms for misses
--
-- DESIGN NOTES:
--   - Live shard WINS: Always re-samples (caller meta can lag tombstone)
--   - Paged safety: Requires ligand if shard.paged=true (fail-closed)
--   - Tombstone check: Refuses if either side tombstoned (OR gate)
--   - Fingerprint validation: Must match path arg (prevents self-assertion)
--   - SHA256 check: Binding must match body hash (prevents swaps)
--   - HTTP/stream identical: No randomness, deterministic logic (zone-split safety)
--   - Used by: All authorization gates, HTTP conf, stream module
--   - Critical: Must never be inlined (zone-split vulnerability)
--
-- RELATED:
--   - read_ocsp_json() for shard data source
--   - read_ocsp_ligand() for ligand data source
--   - merge_ligand() for ligand+shard merge (ligand wins)
--   - resp_binding() to compute DER SHA256
--   - ocsp_json_ligand_matches() wrapper for consensus checks
--   - All validation gates built on top of this
--
-- ============================================================================
-- outside-ligand move — do not reintroduce it.
-- Returns ok, reason, meta_sha, body_sha, eff_meta.
-- Paged shards fail closed on ligand ENOENT (promote tear / missing publish).
-- Unpaged / soft-recall may still bind via in-shard der_sha256 (cutover).
local function ligand_verdict(shard_meta, fingerprint, resp)
	fingerprint = fp64_or_nil(fingerprint)
	if not fingerprint then
		return false, "fingerprint_mismatch_or_missing_meta", nil, nil, shard_meta
	end
	-- Live shard wins over caller meta (stale caller can miss a shard-first tombstone).
	local live_shard = read_ocsp_json(fingerprint)
	local ligand = read_ocsp_ligand(fingerprint)
	local meta = merge_ligand(live_shard, ligand, fingerprint)
	-- Canary-paged generations require the outside-shard ligand.
	if not ligand then
		local paged = type(live_shard) == "table" and live_shard.paged == true
		if paged then
			return false, "ligand_missing", nil, nil, meta
		end
	end
	-- Tombstone from either side (merge forces tombstoned=true). Callers often
	-- only sample shard ocsp.json before this — ligand-first tombstone must refuse.
	if type(meta) == "table" and meta.tombstoned == true then
		return false, "tombstoned", nil, nil, meta
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

-- ============================================================================
-- ocsp_json_ligand_matches(meta, fingerprint, resp)
-- ============================================================================
-- PURPOSE:
--   Ligand consensus check: validates OCSP response visible to HTTP.
--   Wrapper around ligand_verdict for HTTP/stream split prevention.
--
-- PARAMETERS:
--   meta (table|nil): stream-side ocsp.json metadata
--   fingerprint (string): leaf SPKI fingerprint
--   resp (string): OCSP DER response bytes
--
-- RETURNS:
--   (ok, reason, meta_sha, body_sha):
--     ok (boolean): true if ligand + binding match
--     reason (string|nil): mismatch reason code
--     meta_sha (string): der_sha256 from metadata
--     body_sha (string): computed SHA256 of DER
--
-- SIDE EFFECTS:
--   - Calls: ligand_verdict() for comprehensive binding check
--   - Reads: ligand + shard metadata via ligand_verdict
--   - No writes or state modification
--   - Performance: ~1ms via ligand_verdict
--
-- DESIGN NOTES:
--   - Zone split prevention: Must-Staple uses this for HTTP visibility
--   - Wrapper: Direct pass-through to ligand_verdict result
--   - Used by: must_staple_binds_shared_ligand() gate
--   - Related: ligand_verdict does actual work
--
-- RELATED:
--   - ligand_verdict() comprehensive binding checker
--   - must_staple_binds_shared_ligand() calls this
--   - ocsp_json_authorizes_resp() similar binding check
--
-- ============================================================================
local function ocsp_json_ligand_matches(meta, fingerprint, resp)
	local ok, reason, meta_sha, body_sha = ligand_verdict(meta, fingerprint, resp)
	return ok, reason, meta_sha, body_sha
end

-- ============================================================================
-- canary_paged_body_ok(meta, fingerprint, resp)
-- ============================================================================
-- PURPOSE:
--   Canary gate: validates OCSP canary-verified and paged (safe to skip crypto).
--   Used for skip-validate path (fast handshake without re-validating).
--
-- PARAMETERS:
--   meta (table|nil): stream-side ocsp.json metadata
--   fingerprint (string): leaf SPKI fingerprint
--   resp (string): OCSP DER response bytes
--
-- RETURNS:
--   (boolean): true if ligand binding OK + paged=true + not tombstoned
--   (boolean): false if any check fails
--
-- SIDE EFFECTS:
--   - Calls: ligand_verdict() for comprehensive binding check
--   - Reads: ligand + shard metadata via ligand_verdict
--   - No writes or state modification
--   - Performance: ~1ms via ligand_verdict
--
-- DESIGN NOTES:
--   - Canary requirement: CLI canary handshake must have stamped paged=true
--   - Ligand binding: Must pass ligand_verdict() binding check first
--   - Paged validation: Merged metadata must have paged=true (canary proof)
--   - Tombstone guard: Returns false if tombstoned (no skip-validate mid-retire)
--   - Pin requirement: Caller must also verify allow-pin generation (not here)
--   - Used by: skip-validate path (accelerated TLS handshake)
--   - Related: pin.canary_trust_ok wraps this with generation check
--
-- RELATED:
--   - ligand_verdict() for binding validation
--   - pin.canary_trust_ok() wrapper with generation match
--   - shard_not_paged() for paging status check (different context)
--   - _M.canary_paged_body_ok() public export
--
-- ============================================================================
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

-- Ligand-only predicate (warmer / internal). Public facade re-exports pin's
-- canary_trust_ok as canary_paged_body_ok so skip-validate needs the allow-pin.
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

-- ============================================================================
-- _M.ligand_effective_sha(_shard_meta, fingerprint)
-- ============================================================================
-- PURPOSE:
--   Get effective binding SHA256 after ligand+shard merge.
--   Used for L1 disk consistency checks (prevents stale cache hits).
--
-- PARAMETERS:
--   _shard_meta (table|nil): caller's shard metadata (IGNORED, always re-reads)
--   fingerprint (string): leaf SPKI fingerprint
--
-- RETURNS:
--   (string): 64-char hex SHA256 of OCSP binding (der_sha256)
--   (nil): if tombstoned, paged+no-ligand, or SHA invalid
--
-- SIDE EFFECTS:
--   - Reads: live shard + ligand metadata (per-request cached)
--   - Calls: read_ocsp_json(), read_ocsp_ligand(), merge_ligand()
--   - No writes or state modification
--   - Performance: O(1) with per-request cache, ~0.5ms
--
-- DESIGN NOTES:
--   - Live shard: Always re-samples fresh metadata (ignores caller's _shard_meta)
--   - Tombstone guard: Returns nil if tombstoned (L1 must drop)
--   - Paged+no-ligand: Returns nil (handshake would refuse stale body)
--   - Ligand effective: Ligand binding wins after merge
--   - Fail-safe: Returns nil on any mismatch (L1 cannot keep body)
--   - Used by: l1_body_matches_disk() for disk consistency check
--   - Related: HTTP conf + stream warmer both use this
--
-- RELATED:
--   - merge_ligand() for ligand+shard merge logic
--   - l1_body_matches_disk() uses this for L1 validation
--   - read_ocsp_json() and read_ocsp_ligand() data sources
--
-- ============================================================================
function _M.ligand_effective_sha(_shard_meta, fingerprint)
	local live_shard = read_ocsp_json(fingerprint)
	local ligand = read_ocsp_ligand(fingerprint)
	local eff = merge_ligand(live_shard, ligand, fingerprint)
	if type(eff) ~= "table" then
		return nil
	end
	if eff.tombstoned == true then
		return nil
	end
	if type(live_shard) == "table" and live_shard.paged == true and not ligand then
		return nil
	end
	if type(eff.der_sha256) == "string" then
		local sha = eff.der_sha256:lower()
		if #sha == 64 and sha:match("^[0-9a-f]+$") then
			return sha
		end
	end
	return nil
end

-- Shared HTTP↔stream L1↔disk coherence. Fail-closed like ligand_verdict:
-- corrupt meta / paged+ligand ENOENT / require-path gaps drop L1. Publish-gap keep
-- ============================================================================
-- l1_body_matches_disk(fingerprint, resp, stored_epoch)
-- ============================================================================
-- PURPOSE:
--   L1 consistency check: validates cached DER still matches disk metadata.
--   Detects stale cache hits during publish gaps, tombstones, or file removes.
--
-- PARAMETERS:
--   fingerprint (string): leaf SPKI fingerprint
--   resp (string): OCSP DER response bytes (to validate SHA256)
--   stored_epoch (string|nil): epoch from L1 cache entry
--
-- RETURNS:
--   (boolean): true if L1 DER still matches current disk binding
--   (boolean): false if epoch mismatch, tombstoned, or binding differs
--
-- SIDE EFFECTS:
--   - Reads: ocsp.json + ocsp-ligand from disk (per-request cached)
--   - Calls: ligand_effective_sha() for ligand + shard merge
--   - Logs: None (silent validation)
--   - Performance: O(1) with per-request cache, ~1ms for cache misses
--
-- DESIGN NOTES:
--   - Epoch check: Stored epoch must match current scheduler epoch
--   - Tombstone guard: Returns false if meta tombstoned
--   - Publish-gap safety: Handles clean meta+DER removal with ligand fallback
--   - Gap keep logic: Can use ligand binding if paged=true + explicit soft_recall_gen
--   - Corruption detection: Distinguishes ENOENT (clean) from empty (truncate race)
--   - Never bare ligand SHA: Rejects ligand binding after full shard retract
--   - Called by: L1 validation path (before attaching cached DER)
--
-- RELATED:
--   - l1_matches_disk() public export (same function)
--   - entry_verified() for generation binding validation
--   - current_ocsp_epoch() for scheduler epoch
--   - ligand_effective_sha() for ligand+shard binding merge
--
-- ============================================================================
-- (meta+DER both gone, epoch still matches) only while outside ligand is paged=true
-- with an explicit soft_recall_gen and der_sha256 matching the cached binding —
-- never bare ligand SHA after a full shard retract. HTTP conf must call this
-- export rather than inlining.
local function l1_body_matches_disk(fingerprint, resp, stored_epoch)
	local binding = resp_binding(resp)
	if not binding then
		return false
	end
	fingerprint = fp64_or_nil(fingerprint)
	if not fingerprint then
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
	do
		local meta_path = "/var/cache/bunkerweb/ssl/"
			.. fingerprint:sub(1, 1)
			.. "/"
			.. fingerprint:sub(2, 2)
			.. "/"
			.. fingerprint
			.. "/ocsp.json"
		-- Use shared read_file so empty (truncate race) ≠ missing (ENOENT).
		local raw, why = read_file(meta_path)
		if not raw then
			if why == "empty" then
				meta_corrupt = true
			else
				meta_missing = true
			end
		else
			local ok_decode, decoded = pcall(require("cjson").decode, raw)
			if not ok_decode or type(decoded) ~= "table" then
				meta_corrupt = true
			else
				shard_meta = decoded
				if decoded.tombstoned == true then
					tombstoned = true
				elseif type(decoded.der_sha256) == "string" then
					local sha = decoded.der_sha256:lower()
					if #sha == 64 and sha:match("^[0-9a-f]+$") then
						disk_sha = sha
					end
				end
			end
		end
	end
	if tombstoned or meta_corrupt then
		return false
	end

	-- Shard meta+DER both gone: publish-gap keep only (never bare ligand SHA).
	-- Must run before ligand_effective_sha, which would otherwise accept any
	-- ligand der_sha256 and skip paged + explicit soft_recall_gen gates.
	--
	-- PUBLISH-GAP SCENARIO (all-or-nothing atomic update):
	--   1. Scheduler removes ocsp.json (metadata gone)
	--   2. Scheduler removes ocsp.der (body gone)
	--   3. Between step 1-2 or after, TLS handshake reads disk → may see partial state
	--
	-- DETECTION: Shard ocsp.json is ENOENT + ocsp.der is ENOENT → clean gap
	--   - Shard ocsp.json is ENOENT + ocsp.der is empty → truncate race, not gap
	--   - Shard ocsp.json is ENOENT + ocsp.der exists → not clean, drop L1 (corrupt)
	--
	-- KEEP LOGIC: If BOTH are gone AND outside ligand says paged=true with explicit gen:
	--   - Ligand is the authority during the gap (body may be on disk elsewhere)
	--   - Accept L1 body if ligand.der_sha256 matches AND generation is explicit (not omit→0)
	--   - Never use bare ligand SHA after full shard retract (wait for new shard publish)
	if meta_missing then
		-- Clean publish-gap: both meta and DER gone (ENOENT). Empty DER is a
		-- truncate race, not absence — same as empty ocsp.json → drop L1.
		local der_raw, der_why = read_file(ocsp_path(fingerprint))
		if der_raw then
			-- DER without ocsp.json: not a clean publish-gap; drop L1.
			return false
		end
		if der_why == "empty" then
			return false
		end
		local ligand = read_ocsp_ligand(fingerprint)
		if type(ligand) ~= "table" or ligand.paged ~= true then
			return false
		end
		-- Publish-gap keep requires an explicit soft_recall_gen on the ligand
		-- (missing key ≠ upgrade-grace 0 — that rematches leftover identity mid-promote).
		if ligand.soft_recall_gen == nil then
			return false
		end
		local gap_gen = soft_recall_gen_of(ligand)
		if type(gap_gen) ~= "number" then
			return false
		end
		if ligand.tombstoned == true then
			return false
		end
		local ligand_sha = ligand.der_sha256
		return type(ligand_sha) == "string"
			and #ligand_sha == 64
			and ligand_sha:match("^[0-9a-f]+$") ~= nil
			and ligand_sha == binding
	end

	local eff = _M.ligand_effective_sha(shard_meta, fingerprint)
	if type(eff) == "string" and #eff == 64 and eff:match("^[0-9a-f]+$") then
		disk_sha = eff
	elseif type(shard_meta) == "table" and shard_meta.paged == true then
		return false
	elseif read_ocsp_ligand(fingerprint) then
		-- Ligand present but effective sha nil → tombstoned (or refuse-shaped).
		-- Never fall back to in-shard der_sha256 while outside ligand refuses.
		return false
	elseif disk_sha == nil then
		return false
	end

	return disk_sha == binding
end

l1_matches_disk = function(_internalstore, fingerprint, resp, stored_epoch)
	return l1_body_matches_disk(fingerprint, resp, stored_epoch)
end

function _M.l1_body_matches_disk(fingerprint, resp, stored_epoch)
	return l1_body_matches_disk(fingerprint, resp, stored_epoch)
end

-- ============================================================================
-- ocsp_json_authorizes_resp(meta, fingerprint, resp)
-- ============================================================================
-- PURPOSE:
--   Authorization gate: validates OCSP response matches metadata binding.
--   Prevents stapling wrong response or swapped files (SHA256 mismatch).
--
-- PARAMETERS:
--   meta (table|nil): ocsp.json metadata with fingerprint, der_sha256
--   fingerprint (string): leaf SPKI fingerprint (path-based, for consistency check)
--   resp (string): OCSP DER response bytes (to validate SHA256)
--
-- RETURNS:
--   (boolean): true if fingerprint + SHA256 match metadata
--   (boolean): false if mismatch or metadata missing
--
-- SIDE EFFECTS:
--   - Calls: ligand_verdict() for comprehensive binding check
--   - Logs: INFO on accept, ERR/DEBUG on refuse (with digest audit)
--   - No writes or state modification
--   - Performance: O(1) binding check, ~0.5ms typical
--
-- DESIGN NOTES:
--   - Dual verification: Fingerprint + SHA256 both required
--   - Audit logging: Truncated digests logged for troubleshooting
--   - Swapped file protection: Prevents wrong response under matching path
--   - Fingerprint-hint only: Called for restore/fingerprint-only paths
--   - PEM unavailable: Cannot validate with crypto, relies on metadata SHA256
--   - Called by: restore path, fingerprint-hint fallback paths
--   - Related: ligand_verdict() does comprehensive validation
--
-- RELATED:
--   - ligand_verdict() comprehensive binding checker
--   - entry_verified() similar for L1 cache validation
--   - generation_tuple() for soft-recall binding
--
-- ============================================================================
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

-- ============================================================================
-- must_staple_binds_shared_ligand(meta, fingerprint, resp)
-- ============================================================================
-- PURPOSE:
--   Must-Staple binding gate: validates ligand consensus visible to HTTP.
--   Prevents HTTP/stream split decisions on Must-Staple enforcement.
--
-- PARAMETERS:
--   meta (table|nil): stream-side ocsp.json metadata
--   fingerprint (string): leaf SPKI fingerprint
--   resp (string): OCSP DER response bytes
--
-- RETURNS:
--   (true): ligand binding verified (safe for Must-Staple enforcement)
--   (false, reason_string): ligand mismatch (HTTP has different view)
--
-- SIDE EFFECTS:
--   - Calls: ocsp_json_ligand_matches() for HTTP/stream consensus check
--   - No writes or state modification
--   - Performance: O(1) binding check, ~0.5ms typical
--
-- DESIGN NOTES:
--   - Zone split prevention: Must-Staple must agree with HTTP path
--   - Ligand critical: Cannot use stream-private L1 for enforcement gate
--   - Raw reason: Returns ligand_mismatch for KEEP_ALLOW lookup
--   - Fail-closed: False when ligand unavailable or mismatch
--   - Called by: Must-Staple enforcement gate (staple_one_leaf)
--   - Related: HTTP checks same ligand via ssl-certificate-by-lua.conf
--
-- RELATED:
--   - ocsp_json_ligand_matches() comprehensive binding checker
--   - resp_still_fresh() other binding gate
--   - HTTP ssl-certificate-by-lua.conf for HTTP-side check
--
-- ============================================================================
local function must_staple_binds_shared_ligand(meta, fingerprint, resp)
	local ok, reason = ocsp_json_ligand_matches(meta, fingerprint, resp)
	if ok then
		return true
	end
	return false, tostring(reason or "ligand_mismatch")
end

-- ============================================================================
-- meta_expires_unix(meta)
-- ============================================================================
-- PURPOSE:
--   Extract absolute expiry time (nextUpdate) from OCSP metadata.
--   Critical for freshness checks and cache TTL calculation.
--
-- PARAMETERS:
--   meta (table|nil): ocsp.json metadata with expires_unix field
--
-- RETURNS:
--   (number): unix timestamp when response expires (nextUpdate)
--   (nil): if meta missing, invalid, or expires_unix not set
--
-- SIDE EFFECTS:
--   - Calls: positive_expires_unix() to validate expires_unix field
--   - No reads/writes or state modification
--   - Performance: O(1) field lookup, ~0.01ms
--
-- DESIGN NOTES:
--   - Source: CA-signed nextUpdate from OCSP response (job extracted)
--   - Validation: Only valid positive unix timestamps accepted
--   - Used by: resp_still_fresh(), warm_cache(), all freshness gates
--   - Companion: meta_max_age_unix() for wall-clock expiry alternative
--   - Fail-safe: Returns nil if field missing (cannot assume infinity)
--
-- RELATED:
--   - meta_max_age_unix() for published_unix + max_age calculation
--   - resp_still_fresh() uses this for freshness checks
--   - warm_cache() uses this for cache TTL
--   - meta_effective_expires_unix() combines both sources
--
-- ============================================================================
local function meta_expires_unix(meta)
	if type(meta) ~= "table" then
		return nil
	end
	return positive_expires_unix(meta.expires_unix)
end

function _M.meta_expires_unix(meta)
	return meta_expires_unix(meta)
end

-- ============================================================================
-- meta_max_age_unix(meta)
-- ============================================================================
-- PURPOSE:
--   Extract wall-clock expiry (max_age_unix or published_unix + 24h).
--   Fallback expiry when nextUpdate missing or less restrictive.
--
-- PARAMETERS:
--   meta (table|nil): ocsp.json metadata
--
-- RETURNS:
--   (number): unix timestamp (either max_age_unix or published_unix + 86400s)
--   (nil): if both fields missing or invalid
--
-- SIDE EFFECTS:
--   - Calls: positive_unix() to validate metadata fields
--   - No reads/writes or state modification
--   - Performance: O(1) field lookup, ~0.01ms
--
-- DESIGN NOTES:
--   - Primary: max_age_unix if set (explicit max age from job)
--   - Fallback: published_unix + 86400 (24-hour default for PREVIOUS_GOOD)
--   - Source: Both values from job (independent of OCSP response)
--   - Used by: resp_still_fresh() when nextUpdate too loose
--   - Companion: meta_expires_unix() for CA-signed nextUpdate
--   - Fail-safe: Returns nil if both missing (cannot assume expiry)
--
-- RELATED:
--   - meta_expires_unix() for CA-signed nextUpdate
--   - resp_still_fresh() compares min(expires_unix, max_age_unix)
--   - warm_cache() uses this for cache TTL calculation
--   - meta_effective_expires_unix() combines both sources (takes minimum)
--
-- ============================================================================
local function meta_max_age_unix(meta)
	if type(meta) ~= "table" then
		return nil
	end
	local max_age = positive_unix(meta.max_age_unix)
	if max_age then
		return max_age
	end
	local published = positive_unix(meta.published_unix)
	if published then
		-- Match PREVIOUS_GOOD_MAX_AGE_SECONDS in ocsp-refresh.py (24h).
		return published + 86400
	end
	return nil
end

-- ============================================================================
-- intrinsic_timing_ok(meta)
-- ============================================================================
-- PURPOSE:
--   Validate OCSP response's thisUpdate/nextUpdate bounds (CA-signed window).
--   Ensures response age is within policy (not future, not too old, lifetime valid).
--
-- PARAMETERS:
--   meta (table|nil): ocsp.json metadata with this_update_unix, next_update_unix
--
-- RETURNS:
--   (true, nil): timing valid (or no thisUpdate to check)
--   (false, reason_code): timing invalid (future, stale, lifetime bounds, etc.)
--
-- SIDE EFFECTS:
--   - Reads: ngx.time() for current time check
--   - Calls: meta_unix_field() to extract timestamp fields
--   - No writes or state modification
--   - Performance: O(1) time arithmetic, ~0.1ms
--
-- DESIGN NOTES:
--   - thisUpdate check: Response must not be future (+ clock skew allowance)
--   - Max age: thisUpdate cannot be older than OCSP_MAX_THIS_UPDATE_AGE_SECONDS
--   - Lifetime bounds: nextUpdate - thisUpdate must be positive and <= max policy
--   - Missing check: No thisUpdate = pass (no signed window to validate)
--   - Reason codes: Future/stale/invalid_lifetime all fail-closed
--   - Policy constants: OCSP_CLOCK_SKEW, OCSP_MAX_THIS_UPDATE_AGE, OCSP_MAX_INTRINSIC_LIFETIME
--   - Called by: resp_still_fresh() as first timing check
--
-- RELATED:
--   - resp_still_fresh() uses this as first gate before checking max_age
--   - meta_expires_unix() for nextUpdate fallback
--   - meta_max_age_unix() for max_age field extraction
--   - Policy: OCSP_MAX_THIS_UPDATE_AGE_SECONDS (typical: 3600s)
--
-- ============================================================================
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

-- ============================================================================
-- resp_still_fresh(expires_unix, fingerprint, meta)
-- ============================================================================
-- PURPOSE:
--   Validate OCSP response is still within time bounds (thisUpdate, nextUpdate).
--   Critical gate preventing stale responses from being used. Merges ligand for
--   always-live freshness checks.
--
-- PARAMETERS:
--   expires_unix (number|nil): L1 cached expiry (may be nil for disk path)
--   fingerprint (string|nil): leaf SPKI fingerprint for ligand merge
--   meta (table|nil): ocsp.json metadata (ignored if fingerprint provided)
--
-- RETURNS:
--   (true): response is fresh (within bounds)
--   (false, reason): response stale (tombstoned, intrinsic invalid, past expiry, etc.)
--
-- SIDE EFFECTS:
--   - Reads: ligand via ligand_or_meta() (always fresh)
--             ngx.time() for current time check
--   - Calls: intrinsic_timing_ok(), meta_expires_unix(), meta_max_age_unix()
--   - Logging: ERR level on intrinsic timing failures
--   - Performance: O(1) time checks (~0.1ms)
--
-- DESIGN NOTES:
--   - Ligand overlay: Always reads live ligand (caller meta can lag)
--   - Tombstone check: Refuses if either ligand or shard tombstoned
--   - Intrinsic validation: thisUpdate age, nextUpdate, max-age bounds
--   - Death clock: min(expires_unix, meta_expires, max_age)
--   - L1 constraint: L1 can only tighten meta clock, never extend
--   - Clock skew: Built-in OCSP_CLOCK_SKEW_SECONDS buffer (30s typical)
--   - Stripped meta: If neither expires nor max_age, refuse (no death clock)
--   - Called by: L1 hit path, disk path, ligand validation
--
-- RELATED:
--   - warm_cache() enforces same death clock before caching
--   - intrinsic_timing_ok() checks thisUpdate/nextUpdate bounds
--   - meta_effective_expires_unix() computes final death clock
--   - ligand_or_meta() always returns fresh metadata merge
--
-- ============================================================================
-- ============================================================================
-- resp_still_fresh(expires_unix, fingerprint, meta)
-- ============================================================================
-- PURPOSE:
--   Freshness gate: validates OCSP response still within time bounds.
--   Critical path function called before every OCSP staple attachment.
--
-- PARAMETERS:
--   expires_unix (number|nil): L1 cache expiry (may be tighter than meta)
--   fingerprint (string|nil): leaf SPKI fingerprint (samples live metadata)
--   meta (table|nil): ocsp.json metadata (ignored if fingerprint provided)
--
-- RETURNS:
--   (boolean): true if response is fresh and valid
--   (false, string): (false, reason_code) if stale or invalid
--                    reason_codes: "tombstoned", timing error, "response_stale"
--
-- SIDE EFFECTS:
--   - Reads: Live metadata via ligand_or_meta() (always fresh)
--   - Calls: intrinsic_timing_ok(), meta_expires_unix(), meta_max_age_unix()
--   - Logs: ERR if intrinsic timing fails or no death clock
--   - Performance: O(1) metadata check + time comparison, ~0.5ms typical
--
-- DESIGN NOTES:
--   - Live metadata always wins: Samples fresh shard + ligand via fingerprint
--   - Tombstone check: Refuses if ligand or shard tombstoned (mid-retire)
--   - Intrinsic bounds: Validates thisUpdate/nextUpdate (from response)
--   - Death clock: min(expires_unix, max_age, expires_unix metadata field)
--   - L1 tightening: Caller expires_unix can only tighten, never extend
--   - Clock skew: OCSP_CLOCK_SKEW_SECONDS grace period before reject
--   - Called in: Critical path (must_staple, attachment validation)
--   - Related: warm_cache() enforces same death clock before caching
--
-- RELATED:
--   - meta_tombstoned() for tombstone detection
--   - cluster_floor_blocks(), shard_not_paged(), serial_blacklist_blocks()
--   - intrinsic_timing_ok() for thisUpdate/nextUpdate validation
--   - warm_cache() enforces consistency before cache write
--
-- ============================================================================
local function resp_still_fresh(expires_unix, fingerprint, meta)
	-- Overlay outside ligand so freshness uses the same min(expires) as
	-- warm_cache / merge_ligand. ligand_or_meta always samples live shard
	-- (caller meta ignored — can lag tombstone / expires tighten).
	local fp = fp64_or_nil(fingerprint)
	if fp then
		meta = ligand_or_meta(nil, fp)
	elseif type(meta) ~= "table" then
		meta = nil
	end
	-- After ligand merge: refuse if either side tombstoned (callers often only
	-- checked shard ocsp.json before calling).
	if type(meta) == "table" and meta.tombstoned == true then
		return false, "tombstoned"
	end
	local ok_intrinsic, why = intrinsic_timing_ok(meta)
	if not ok_intrinsic then
		log(
			ngx.ERR,
			"OCSP intrinsic timing refuse reason=" .. tostring(why) .. " fp=" .. tostring(fp and fp:sub(1, 16) or "?")
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
			"OCSP refuse staple: no expires_unix/max_age death clock fp=" .. tostring(fp and fp:sub(1, 16) or "?")
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

-- Meta death clock first; L1 expires_unix may only tighten, never extend or
-- invent a clock when meta/ligand is stripped (matches resp_still_fresh).
meta_effective_expires_unix = function(meta, expires_unix)
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
		-- No meta/ligand death clock: do not keep a stripped-meta DER alive via L1.
		return nil
	end
	if type(expires_unix) == "number" and expires_unix > 0 and expires_unix < exp then
		return math.floor(expires_unix)
	end
	return exp
end

-- Tri-state export for HTTP/conf callers that need unknown ≠ false vs true.
-- Returns true | false | nil (see resolve_leaf_must_staple).
function _M.resolve_leaf_must_staple(cert_pem, fingerprint)
	return resolve_leaf_must_staple(cert_pem, fingerprint)
end

function _M.serial_blacklist_blocks(fingerprint, resp)
	return serial_blacklist_blocks(fingerprint, resp)
end

function _M.meta_tombstoned(meta, fingerprint)
	return meta_tombstoned(meta, fingerprint)
end

-- Public colony-floor gate (HTTP must call this — do not reintroduce a loose
-- tonumber inline that accepts "1e20" / inf and forks Must-Staple closes).
function _M.cluster_floor_blocks(fingerprint, meta)
	return cluster_floor_blocks(fingerprint, meta)
end

-- Public freshness gate (HTTP must call this — do not reintroduce a shard-only
-- inline that ignores ligand min(expires) / tombstone).
function _M.resp_still_fresh(expires_unix, fingerprint, meta)
	return resp_still_fresh(expires_unix, fingerprint, meta)
end

-- Public live gen (HTTP must call this — do not reintroduce ligand-only soft_recall
-- that ignores shard gen when the ligand omits the key).
function _M.live_soft_recall_gen(fingerprint)
	return live_soft_recall_gen(fingerprint)
end

_M.internal = {
	L1_MAX_TTL = L1_MAX_TTL,
	canary_paged_body_ok = canary_paged_body_ok,
	cert_must_staple_bool = cert_must_staple_bool,
	cluster_floor_blocks = cluster_floor_blocks,
	drop_cache = drop_cache,
	entry_verified = entry_verified,
	generation_tuple = generation_tuple,
	get_l1 = get_l1,
	l1_matches_disk = l1_matches_disk,
	ligand_or_meta = ligand_or_meta,
	live_soft_recall_gen = live_soft_recall_gen,
	-- pin.ligand_or_meta wrapper caches via these (same ngx.ctx table as read path).
	merge_ligand = merge_ligand,
	meta_effective_expires_unix = meta_effective_expires_unix,
	meta_tombstoned = meta_tombstoned,
	must_staple_binds_shared_ligand = must_staple_binds_shared_ligand,
	ocsp_json_authorizes_resp = ocsp_json_authorizes_resp,
	ocsp_json_ligand_matches = ocsp_json_ligand_matches,
	ocsp_json_must_staple = ocsp_json_must_staple,
	read_ocsp_json = read_ocsp_json,
	read_ocsp_ligand = read_ocsp_ligand,
	resolve_leaf_must_staple = resolve_leaf_must_staple,
	resp_still_fresh = resp_still_fresh,
	serial_blacklist_blocks = serial_blacklist_blocks,
	shard_not_paged = shard_not_paged,
	soft_recall_gen_of = soft_recall_gen_of,
	warm_cache = warm_cache,
}

return _M
