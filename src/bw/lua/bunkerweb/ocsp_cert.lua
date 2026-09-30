--[[
================================================================================
OCSP Certificate Module: PEM/DER Parsing, SPKI Fingerprinting, and CertID Matching
================================================================================

MODULE OVERVIEW:
Pure certificate and OCSP response parsing with per-worker memoization (no disk
or shared state). Exports fingerprints, serial numbers, Must-Staple detection,
AIA URIs, and CertID matching for use by higher-level OCSP modules.

KEY FUNCTIONS:
1. SPKI Fingerprinting: spki_fingerprint(cert_pem) → SHA256 hex, cache-keyed
   for /var/cache/bunkerweb/ssl/{h}/{l}/{fp}/ shard directories.

2. PEM Profile Extraction: Per-worker memo caches complete certificate facts
   (Must-Staple, serial, key kind, issuer DN, AIA URIs) in single x509 pass,
   avoiding redundant FFI calls across multiple handshakes.

3. CertID Validation: certid_matches_handshake_leaf() verifies OCSP response
   names this leaf (serial + issuer DN + SPKI ambiguity gate). Fingerprint-only
   path uses certid_consistent_with_meta().

4. DER Parsing: Native Lua DER reader (no resty.openssl.ocsp) for extracting
   certificate serials from OCSP responses (RFC 6960 SingleResponse CertID).

5. AIA URI Handling: Normalized OCSP Authority Info Access URIs (http/https,
   lowercase scheme/host, no userinfo, drop default ports).

ARCHITECTURE:
- Per-worker PEM memo: LRU cache (512 entries max, O(1) hits, O(n) eviction).
  Keyed by exact PEM bytes to distinguish rewrapped certificates.
- Per-worker OCSP DER memo: Separate LRU (256 entries) for serial walks; keyed
  by SHA256(full DER) to handle same-responder structural prefixes.
- No disk access: All parsing done in-memory via lua-resty-openssl FFI.

EXPORTS:
- Public: ocsp_resp_serial_hex, aia_uri_pin_ok, cert_pubkey_kind
- Internal: Certificate facts (serial, SPKI, Must-Staple), CertID matching,
  AIA URI parsing, batch fingerprinting

DEPENDENCIES:
- lua-resty-openssl: x509, pkey, digest modules for FFI parsing
- ocsp_common: is_fp64, to_hex, log utilities
- Called by ocsp_chain, ocsp.lua for cert validation

================================================================================
]]

-- Pure certificate / OCSP DER parsing with a per-worker memo (no disk, no shared state).
-- Part of bunkerweb.ocsp; other modules use the .internal table, callers use bunkerweb.ocsp.
local _M = {}

local ngx = ngx

local common = require("bunkerweb.ocsp_common").internal
local is_fp64 = common.is_fp64
local log = common.log
local to_hex = common.to_hex

-- OpenSSL NIDs for TLS 1.3 CertificateVerify EC/Ed schemes
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

-- Split PEM string into individual certificate blocks.
-- Handles multi-cert PEM bundles (common in chains and bags).
-- If no full blocks found, returns input as-is (handles single-cert non-standard PEM).
--
-- @param cert_pem: PEM string (may contain one or many "-----BEGIN CERTIFICATE-----...-----END CERTIFICATE-----")
-- @return: table of PEM block strings {block1, block2, ...}
--
-- REGEX PATTERN EXPLAINED:
--   (%-%-%-%-%-BEGIN CERTIFICATE%-%-%-%-%-.-%-%-%-%-%-END CERTIFICATE%--%-%-%-%-)
--   - %-%-... = escaped dashes (---) in Lua string pattern
--   - .-     = non-greedy match of any content (certificate body + internals)
--   - gmatch = iterate over all non-overlapping matches
--
-- EDGE CASES:
--   pem_blocks("-----BEGIN CERTIFICATE-----\\n...\\n-----END CERTIFICATE-----")
--     → {"-----BEGIN CERTIFICATE-----\\n...\\n-----END CERTIFICATE-----"}
--   pem_blocks("cert1\\ncert2") with no BEGIN/END
--     → {"cert1\\ncert2"} (original input, possibly malformed)
--   pem_blocks("") → {""} (empty cert_pem treated as single block)
--
-- ============================================================================
-- pem_blocks(cert_pem)
-- ============================================================================
-- PURPOSE:
--   Split PEM string into individual certificate blocks (multi-cert support).
--   Extracts each -----BEGIN CERTIFICATE-----...-----END CERTIFICATE----- block.
--
-- PARAMETERS:
--   cert_pem (string): one or more PEM-encoded certificates
--
-- RETURNS:
--   (table): array of individual PEM blocks, or [cert_pem] if no blocks found
--
-- SIDE EFFECTS:
--   - String manipulation only (no state/IO)
--   - Performance: O(n) single regex scan, ~0.5ms per 64KB
--
-- DESIGN NOTES:
--   - Regex extraction: Captures full -----BEGIN...END----- blocks
--   - Fallback: If no blocks found, returns [cert_pem] as-is (single block)
--   - Used by: Chain builders, intermediates processing, bulk parsing
--   - Related: parse_pem_keys() for key block extraction
--
-- RELATED:
--   - presentable_chain_blocks() uses this for PEM→blocks conversion
--   - issuer_linked_chain_blocks() filters results
--   - parse_pem_keys() similar for private keys
--
-- ============================================================================
-- Performance: O(n) regex scan (one pass, linear with input size)
-- Used by: issuer_linked_chain_blocks, presentable_chain_blocks
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

-- Per-worker memo of pure PEM-derived facts (SPKI, DNs, Must-Staple bit, serial, key
-- kind). One handshake used to re-parse the same PEM ~20 times. Keyed by the exact
-- PEM bytes, so a rewrapped PEM is only a miss, never a wrong answer.
-- Stores one full profile per PEM (single x509 pass); accessors read fields from it.
-- Eviction: touch-counter LRU — O(1) hits, O(n) only when the cache is full.
-- Main-chunk locals are capped at 200 by LuaJIT, so memo state lives in this block.
local pem_profile_get
local pem_profile_batched
local ocsp_der_memo_fetch
do
	local PEM_MEMO_MAX = 512
	local OCSP_DER_MEMO_MAX = 256
	local MEMO_NIL = {}
	local pem_memo = {}
	local pem_memo_count = 0
	local pem_memo_touch = {} -- pem → monotonic touch for LRU
	local pem_touch_gen = 0
	local ocsp_der_memo = {}
	local ocsp_der_memo_count = 0

	-- Mark PEM as recently accessed for LRU eviction tracking.
	-- Increments touch_gen and records the new timestamp for this PEM.
	-- Used on every cache hit to move the entry toward the "hot" end of LRU.
	--
	-- @param pem: exact PEM bytes (key in pem_memo)
	-- @note: side-effect: increments pem_touch_gen (per-worker counter)
	-- @note: called by pem_profile_get on every cache hit or new insert
	--
	-- MONOTONIC ORDERING:
	--   Each PEM records the touch_gen value it saw on access.
	--   Highest touch_gen = most recently accessed (hottest).
	--   Lowest touch_gen = least recently accessed (coldest → first to evict).
	--
	-- Performance: O(1) assignment (no table scan)
	-- Called by: pem_profile_get (cache hit + insert)
	local function touch_pem(pem)
		pem_touch_gen = pem_touch_gen + 1
		pem_memo_touch[pem] = pem_touch_gen
	end

	-- Evict least-recently-touched PEM from L1 memo. Returns true if an entry was removed.
	-- ALGORITHM: O(n) scan for minimum touch value across all cached PEMs.
	--   - Simple single-pass scan (n < 512; no heap needed)
	--   - Keeps oldest_touch tracking: nil for empty cache, or oldest mtime value
	--   - Removes exactly one entry per call (not all stale, just one LRU victim)
	--   - touch_gen monotonically increments → LRU order is deterministic
	--   - Return true only if an entry was deleted (false = cache is empty)
	--
	-- @return: true if a PEM was evicted, false if cache was empty
	--
	-- EVICTION POLICY:
	--   1. Scan all pem_memo_touch entries for the minimum touch value
	--   2. Delete that PEM from both pem_memo and pem_memo_touch
	--   3. Decrement pem_memo_count
	--   4. Return true (success) or false (cache empty)
	--
	-- Performance: O(n) where n = entries in cache (max 512)
	--   Called only when cache is full; typical cost < 0.5ms for 512 entries
	--
	-- Called by: pem_profile_get (when memo exceeds PEM_MEMO_MAX limit)
	local function evict_lru()
		local oldest_pem, oldest_touch = nil, nil
		for pem, t in pairs(pem_memo_touch) do
			if oldest_touch == nil or t < oldest_touch then
				oldest_touch = t
				oldest_pem = pem
			end
		end
		if not oldest_pem then
			return false
		end
		pem_memo[oldest_pem] = nil
		pem_memo_touch[oldest_pem] = nil
		pem_memo_count = pem_memo_count - 1
		return true
	end

	-- One batched profile per PEM. Shared table is read-only for callers.
	pem_profile_get = function(pem)
		if type(pem) ~= "string" or pem == "" then
			return pem_profile_batched(pem)
		end
		local profile = pem_memo[pem]
		if profile then
			touch_pem(pem)
			return profile
		end
		if pem_memo_count >= PEM_MEMO_MAX then
			if not evict_lru() then
				-- Invariant broken; wipe rather than grow unbounded.
				pem_memo = {}
				pem_memo_touch = {}
				pem_memo_count = 0
			end
		end
		profile = pem_profile_batched(pem)
		-- Do not memoize empty/incomplete profiles (transient FFI glitch or BN miss).
		-- Missing serial/SPKI would strand CertID / pin paths until LRU.
		if
			type(profile) ~= "table"
			or next(profile) == nil
			or profile.serial == nil
			or not is_fp64(profile.spki_fingerprint)
		then
			return profile or {}
		end
		pem_memo[pem] = profile
		touch_pem(pem)
		pem_memo_count = pem_memo_count + 1
		return profile
	end

	-- Generate cache key from full OCSP DER body using SHA256 hash.
	-- WHY FULL HASH NOT PREFIX:
	--   Multiple OCSP responses from the same responder share structural prefixes
	--   (same response header format, timestamp fields, etc.). A 32-byte prefix
	--   was causing hash collisions: two different OCSP bodies matched the same key.
	--   Result: CertID and blacklist lookups returned wrong answer (cached from first body).
	--
	-- @param ocsp_der: OCSP response DER bytes (binary string)
	-- @return: lowercase hex SHA256 digest (64 chars), or full ocsp_der if hash fails
	--
	-- FALLBACK LOGIC:
	--   If FFI digest fails (unlikely, but keeps cache operational):
	--   Use full ocsp_der as key (correct but heavier; no collision).
	--   This is fail-closed: correct answer, just slower cache hit.
	--
	-- Performance: ~1ms for typical ~200-byte OCSP response
	-- Security: SHA256 collision (2^128) extremely unlikely; full-body fallback provides safety
	-- Called by: ocsp_der_memo_fetch (memo keying for serial extraction)
	local function der_body_key(ocsp_der)
		local ok, hex = pcall(function()
			local digest_lib = require("resty.openssl.digest")
			local digest_ctx = digest_lib.new("sha256")
			digest_ctx:update(ocsp_der)
			return to_hex(digest_ctx:final())
		end)
		if ok and type(hex) == "string" and #hex == 64 then
			return hex
		end
		-- Fail closed to correct (if heavy) keying rather than a colliding prefix.
		return ocsp_der
	end

	-- Create a fresh shallow copy of a string list to prevent caller mutations.
	-- RATIONALE: Memoized OCSP DER serial tables must be immutable from the caller's POV.
	--   If a caller mutates the returned table (modifies / removes serials),
	--   the memo cache entry would be corrupted for all subsequent callers.
	--   Solution: every memo hit returns a fresh clone.
	--
	-- @param t: table to clone (should be indexed list: {serial1, serial2, ...})
	-- @return: new table with same indices + values, or original t if not a table
	--
	-- OPERATION:
	--   1. Check if t is a table (non-table → return unchanged)
	--   2. Create new table `out`
	--   3. Copy indices 1..#t to new table (shallow copy of list part only)
	--   4. Return fresh copy
	--
	-- Performance: O(n) where n = list length (usually 1-3 serials per response)
	-- Used by: ocsp_der_memo_fetch (clone before return and before store)
	local function clone_str_list(t)
		if type(t) ~= "table" then
			return t
		end
		local out = {}
		for i = 1, #t do
			out[i] = t[i]
		end
		return out
	end

	ocsp_der_memo_fetch = function(ocsp_der, compute)
		if type(ocsp_der) ~= "string" or #ocsp_der < 2 then
			return compute(ocsp_der)
		end
		local key = der_body_key(ocsp_der)
		local result = ocsp_der_memo[key]
		if result == MEMO_NIL then
			return nil
		end
		if result ~= nil then
			return clone_str_list(result)
		end
		if ocsp_der_memo_count >= OCSP_DER_MEMO_MAX then
			ocsp_der_memo = {}
			ocsp_der_memo_count = 0
		end
		result = compute(ocsp_der)
		if result == nil then
			ocsp_der_memo[key] = MEMO_NIL
			ocsp_der_memo_count = ocsp_der_memo_count + 1
			return nil
		end
		ocsp_der_memo[key] = clone_str_list(result)
		ocsp_der_memo_count = ocsp_der_memo_count + 1
		return clone_str_list(ocsp_der_memo[key])
	end
end

-- True when TLS Feature text asserts status_request (Must-Staple / feature id 5).
-- ============================================================================
-- TLS_FEATURE_IS_MUST_STAPLE(text)
-- ============================================================================
-- PURPOSE:
--   Parses a certificate TLS Feature extension text to detect Must-Staple
--   (OCSP status_request feature ID 5). Handles multiple OpenSSL output formats
--   to robustly identify the Must-Staple requirement.
--
-- PARAMETERS:
--   text (string): TLS Feature extension text from resty.openssl cert parsing
--
-- RETURNS:
--   (boolean): true if Must-Staple (feature 5) found, false otherwise
--
-- SIDE EFFECTS:
--   - String matching only (no state/IO)
--   - Performance: O(n) linear with text length (~0.5ms typical)
--
-- DESIGN NOTES:
--   - Feature ID 5 = status_request (Must-Staple in TLS 1.3 context)
--   - Named forms: "OCSP status request", "status_request", "statusRequest" (case variants)
--   - Numeric forms: bare feature-id lists ("5", "5, 17") — never parses OID arcs
--   - OpenSSL formats: handles text dumps, zero-padded IDs ("05"), mixed case
--   - Scope: TLS Feature extension only (ignores other extension types)
--   - Conservative: rejects ambiguous forms (e.g., "status_request_v2") to avoid
--     false positives on related features
--   - Used by: pem_profile_batched() to set profile.must_staple tri-state
--
-- RELATED:
--   - has_must_staple() — wrapper that calls this and returns tri-state
--   - pem_profile_batched() — calls this to extract Must-Staple from cert
--   - resolve_leaf_must_staple() — combines TLS Feature + ocsp.json
--
-- ============================================================================
-- Named forms first. Digit "5" only when the whole text is a feature-id list
-- ("5", "5, 17") — never gmatch %d+ over OID arcs or openssl dumps.
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
	local trimmed = text:match("^%s*(.-)%s*$") or ""
	-- Bare feature-id list only (digits, commas, whitespace) — rejects OID text.
	if trimmed:match("^[%d%s,]+$") then
		for token in trimmed:gmatch("%d+") do
			-- Accept zero-padded forms ("05") — OpenSSL digit dumps occasionally pad.
			if tonumber(token) == 5 then
				return true
			end
		end
	end
	return false
end

-- ============================================================================
-- CANONICAL_SERIAL_HEX(serial)
-- ============================================================================
-- PURPOSE:
--   Normalizes certificate serial numbers to canonical uppercase hex format.
--   Handles multiple input types (BigNum, string, number) and produces a
--   consistent format for comparison and matching (no leading zeros, uppercase).
--
-- PARAMETERS:
--   serial: one of:
--     - (userdata/table): resty.openssl.BN (BigNum) from certificate
--     - (string): hex string (may have colons, spaces, 0x prefix, mixed case)
--     - (number): integer serial (0 ≤ n < 2^53 for exact representation)
--     - (nil): returns nil
--
-- RETURNS:
--   (string): canonical uppercase hex without leading zeros (e.g., "ABCD" or "0")
--   (nil): if serial malformed, invalid, or unparseable
--
-- SIDE EFFECTS:
--   - String/number manipulation only (no state/IO/FFI)
--   - Performance: O(n) where n = serial length (~1µs typical)
--
-- DESIGN NOTES:
--   - Type handling: BigNum → to_hex() or to_number(); string/number directly
--   - String normalization: uppercase + strip colons/spaces + strip 0x prefix
--   - Hex validation: rejects non-hex chars, empty strings, malformed input
--   - Leading zeros: stripped uniformly (e.g., "00FF" → "FF", "000" → "0")
--   - Edge case: all-zeros always returns "0" (not empty string)
--   - Number validation: only accepts 0 ≤ n < 2^53 (IEEE 754 exact range)
--   - Security-critical: strings treated as pure hex, never decimal-coerced
--     (prevents "100" vs "256" collision if mistaken for decimal)
--   - Cross-system agreement: matches ocsp-refresh.py format(serial, "X")
--
-- RELATED:
--   - ocsp_resp_serial_hex() — extracts and canonicalizes response serials
--   - leaf_serial_hex() — extracts and canonicalizes leaf serials
--   - certid_consistent_with_meta() — uses for metadata serial matching
--
-- ============================================================================
-- Canonical uppercase hex serial without leading zeros. Strings are always hex:
-- ocsp-refresh.py writes format(serial, "X"), and an all-digit hex serial such as
-- "1000" (0x1000) must not be reinterpreted as decimal.
--
-- NORMALIZATION RULES:
--   1. BigNum userdata (resty.openssl.BN): call :to_hex() or :to_number()
--   2. String: uppercase, strip colons/spaces, strip 0x prefix, strip leading 0s
--   3. Number: format %X (no 0x prefix), accept only if 0 <= n < 2^53 (exact)
--   4. Result: uppercase no-prefix hex (e.g. "1000" not "0x1000"; "FF" not "00FF")
--   5. Edge case: all-zeros → "0" not empty string (cannot omit)
--
-- SECURITY: Strings must be exact hex (no tonumber("1e2") coercion) to prevent
--           serial collision attacks (e.g., "100" == "256" if decimalized)
local function canonical_serial_hex(serial)
	if serial == nil then
		return nil
	end
	-- resty BN may be userdata or a table with to_hex / to_number.
	local st = type(serial)
	if st == "table" or st == "userdata" then
		if serial.to_hex then
			local ok_hex, hex = pcall(function()
				return serial:to_hex()
			end)
			if ok_hex and type(hex) == "string" and #hex > 0 then
				hex = hex:upper():gsub("[%s:]+", ""):gsub("^0X", "")
				if hex == "" or not hex:match("^[0-9A-F]+$") then
					return nil
				end
				hex = hex:gsub("^0+", "")
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

-- ============================================================================
-- SPKI_FINGERPRINT(cert_pem)
-- ============================================================================
-- PURPOSE:
--   Returns the SHA256 fingerprint of a certificate's SubjectPublicKeyInfo (SPKI).
--   This is the canonical key hash for matching OCSP responses and validating
--   certificate identity across formats (matches ocsp-refresh.py).
--
-- PARAMETERS:
--   cert_pem (string): X.509 certificate in PEM format
--
-- RETURNS:
--   (string): 64-character hex SHA256 of SPKI, if valid profile exists
--   (nil): if profile is missing, invalid, or SPKI unavailable
--
-- SIDE EFFECTS:
--   - Reads: pem_profile_get() cache (profile table per cert_pem)
--   - Calls: pem_profile_get(cert_pem), is_fp64(fingerprint)
--   - Performance: O(1) — profile already parsed and cached once per PEM
--
-- DESIGN NOTES:
--   - Never use ngx.md5(cert_pem) as SPKI stand-in: PEM rewrap changes that
--     hash while SPKI stays identical (file format variance vs key material).
--   - Profile is memoized once per PEM with single x509 pass (all facts at once).
--   - SPKI fingerprint is the definitive key identity for cross-module matching.
--   - Validation: is_fp64() check ensures result is 64-char hex, not stale/nil.
--
-- RELATED:
--   - pem_profile_get() — memoized profile cache
--   - is_fp64() — validates fingerprint format
--   - batch_spki_fingerprints_filtered() — bulk SPKI extraction for issuers
--   - key_spki_fingerprint() — computes SPKI for private keys
--
-- ============================================================================
-- SHA256 of SubjectPublicKeyInfo DER, matching ocsp-refresh.py.
-- Never key anything by ngx.md5(cert_pem) as a stand-in for the SPKI: PEM rewrap
-- changes that hash while the SPKI is identical (path skew vs the job).
-- Profile is memoized once per PEM (single x509 pass for all facts).
local function spki_fingerprint(cert_pem)
	local profile = pem_profile_get(cert_pem)
	local fingerprint = profile and profile.spki_fingerprint
	if is_fp64(fingerprint) then
		return fingerprint
	end
	return nil
end

-- ============================================================================
-- BATCH_SPKI_FINGERPRINTS_FILTERED(dn_grouped_issuers)
-- ============================================================================
-- PURPOSE:
--   Bulk-extracts SPKI fingerprints for issuers already filtered by DN matching.
--   Optimized companion to batch_spki_fingerprints() for pre-filtered, smaller lists.
--
-- PARAMETERS:
--   dn_grouped_issuers (table): map-like table with PEM keys (values ignored),
--                               representing issuers already matched by DN
--
-- RETURNS:
--   (table): {pem_string → fingerprint_string} mapping each issuer to its SPKI
--   (empty table): if input not a table or empty
--
-- SIDE EFFECTS:
--   - Reads: dn_grouped_issuers table keys (PEM strings)
--   - Calls: spki_fingerprint() for each PEM
--   - Performance: ~1-3ms per unique PEM (memoized)
--
-- DESIGN NOTES:
--   - Variant of batch_spki_fingerprints(): iterates over table keys (not array)
--   - Use case: prefilter_issuers_by_spki() passes DN-grouped issuers to this
--   - Optimization: processes only filtered list (avoids full issuer table)
--   - Profile memoization: spki_fingerprint() internally caches per-PEM
--   - No deduplication: assumes caller has already deduplicated by DN grouping
--
-- RELATED:
--   - batch_spki_fingerprints() — array-based variant for raw issuer lists
--   - prefilter_issuers_by_spki() — calls this on DN-filtered results
--   - spki_fingerprint() — single SPKI extraction (memoized)
--
-- ============================================================================
-- Helper: batch extract SPKI for issuers already grouped by DN.
-- Optimized for pre-filtered list (smaller than full issuer list).
local function batch_spki_fingerprints_filtered(dn_grouped_issuers)
	local result = {}
	if type(dn_grouped_issuers) ~= "table" then
		return result
	end
	for iss, _ in pairs(dn_grouped_issuers) do
		if type(iss) == "string" and iss ~= "" then
			result[iss] = spki_fingerprint(iss)
		end
	end
	return result
end

-- ============================================================================
-- NORMALIZE_OCSP_AIA_URI(url)
-- ============================================================================
-- PURPOSE:
--   Canonicalizes an OCSP URI for comparison, matching ocsp-refresh.py's
--   normalization. Ensures consistent matching despite URL representation variants
--   (userinfo, case, default ports, trailing punctuation).
--
-- PARAMETERS:
--   url (string): OCSP URI in any HTTP(S) format (may have userinfo, mixed case,
--                 default ports, trailing punctuation)
--
-- RETURNS:
--   (string): canonical lowercase URI (scheme://host[:port]/path?query#fragment)
--   (nil): if url invalid, unsupported scheme, or missing components
--
-- SIDE EFFECTS:
--   - String manipulation only (no state/IO)
--   - Performance: O(n) linear with URL length (~0.5ms typical)
--
-- DESIGN NOTES:
--   - Supported schemes: http, https (case-insensitive input)
--   - Whitespace trim: leading/trailing spaces removed
--   - Punctuation: trailing punctuation (,;.) stripped (artifact from text dumps)
--   - Userinfo drop: user:pass@ removed before comparing hosts
--   - Case normalization: scheme and host lowercased; path/query/fragment preserved
--   - IPv6 support: literal [::1] format handled separately from IPv4:port
--   - Default ports: 80 (http) and 443 (https) omitted from output if present
--   - Fallback preservation: non-default ports always included in output
--   - Cross-system consistency: matches ocsp-refresh._normalize_ocsp_aia_uri for
--     job/Lua agreement on which URIs match
--
-- RELATED:
--   - aia_uri_pin_ok() — uses for leaf AIA URI comparison
--   - leaf_aia_ocsp_uris() — provides URIs that are normalized by this function
--   - ocsp-refresh.py — Python-side normalization must match
--
-- ============================================================================
-- Canonical AIA OCSP URI for comparison — must match ocsp-refresh._normalize_ocsp_aia_uri:
-- http(s) only, lowercase scheme/host, drop userinfo, omit default :80/:443, keep path/query/fragment.
local function normalize_ocsp_aia_uri(url)
	if type(url) ~= "string" then
		return nil
	end
	url = url:match("^%s*(.-)%s*$") or ""
	-- Trim trailing punctuation often left by text dumps ("URI:http://x,").
	url = url:gsub("[,;%.]+$", "")
	if url == "" then
		return nil
	end
	local scheme, rest = url:match("^([Hh][Tt][Tt][Pp][Ss]?)://(.+)$")
	if not scheme or not rest then
		return nil
	end
	scheme = scheme:lower()
	local authority, pathquery = rest:match("^([^/?#]*)(.*)$")
	if type(authority) ~= "string" or authority == "" then
		return nil
	end
	-- Drop userinfo (user:pass@host).
	local at = authority:match("^.*@(.-)$")
	if at then
		authority = at
	end
	local host, port
	if authority:sub(1, 1) == "[" then
		-- IPv6 literal [::1] or [::1]:8443
		host, port = authority:match("^(%[[%x:]+%]):(%d+)$")
		if not host then
			host = authority:match("^(%[[%x:]+%])$")
		end
	else
		host, port = authority:match("^([^:]+):(%d+)$")
		if not host then
			host = authority
		end
	end
	if type(host) ~= "string" or host == "" then
		return nil
	end
	host = host:lower()
	local netloc = host
	if port then
		local pnum = tonumber(port)
		local default = (scheme == "http") and 80 or 443
		if pnum and pnum ~= default then
			netloc = host .. ":" .. port
		end
	end
	return scheme .. "://" .. netloc .. (pathquery or "")
end

-- Batch extract all certificate profile facts in single x509 object pass
-- Reuses cert_obj instead of creating 5 separate instances per PEM
-- Saves: 5-8ms per certificate (single FFI call vs 5 separate ones)
-- Set after all helper functions are defined to avoid forward references.
pem_profile_batched = function(pem)
	if type(pem) ~= "string" or pem == "" then
		return {}
	end
	local profile = {}
	local ok = pcall(function()
		local x509 = require("resty.openssl.x509")
		local cert_obj = x509.new(pem)
		if not cert_obj then
			return
		end

		-- Must-Staple: TLS Feature extension. Tri-state for has_must_staple:
		-- true = positive MS, false = proven absent/non-MS, nil = extension present
		-- but text unrecognized (never invent false — that fail-opens vs ocsp.json).
		local tls_feature_ext = cert_obj:get_extension("tlsfeature")
		if tls_feature_ext then
			local text = tls_feature_ext:text() or ""
			if tls_feature_is_must_staple(text) then
				profile.must_staple = true
			else
				local trimmed = text:match("^%s*(.-)%s*$") or ""
				-- Bare feature-id list without 5 → proven not Must-Staple (e.g. "17").
				if trimmed ~= "" and trimmed:match("^[%d%s,]+$") then
					profile.must_staple = false
				else
					-- Empty / ASN.1 dump / unrecognized named form → unknown.
					profile.must_staple = nil
				end
			end
		else
			profile.must_staple = false
		end

		-- Serial: Extract certificate serial number (checked after definition)
		profile.serial = canonical_serial_hex(cert_obj:get_serial_number())

		-- Public key: Extract once, use for both kind and sig_profile
		local pub = cert_obj:get_pubkey()
		if pub then
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

			-- Key kind (checked after NIDs defined)
			if label:find("ed25519", 1, true) or nid == NID_ED25519 then
				profile.pubkey_kind = "ed"
				profile.curve_nid = NID_ED25519
			elseif label:find("ed448", 1, true) or nid == NID_ED448 then
				profile.pubkey_kind = "ed"
				profile.curve_nid = NID_ED448
			elseif label:find("rsa", 1, true) then
				profile.pubkey_kind = "rsa"
			elseif label:find("ec", 1, true) or label:find("id-ec", 1, true) then
				profile.pubkey_kind = "ec"
				local params = pub.get_parameters and pub:get_parameters() or nil
				if type(params) == "table" and type(params.group) == "number" and params.group > 0 then
					profile.curve_nid = params.group
				end
			end
		end

		-- Names: Extract subject and issuer DNs
		if cert_obj.get_subject_name and cert_obj.get_issuer_name then
			profile.subject_dn = tostring(cert_obj:get_subject_name() or "")
			profile.issuer_dn = tostring(cert_obj:get_issuer_name() or "")
		end

		-- AIA OCSP URIs: Extract from certificate (checked after definition)
		local aia_ext = cert_obj:get_extension("authorityInfoAccess")
		if aia_ext then
			local aia_text = aia_ext:text() or ""
			local uris = {}
			local seen = {}
			for uri in aia_text:gmatch("1%.3%.6%.1%.5%.5%.7%.48%.1%s*[-=]%s*URI:([%w%p]+)") do
				local n = normalize_ocsp_aia_uri(uri)
				if n and not seen[n] then
					seen[n] = true
					uris[#uris + 1] = n
				end
			end
			if #uris == 0 then
				for uri in aia_text:gmatch("OCSP%s*[-=]?%s*URI:([%w%p]+)") do
					local n = normalize_ocsp_aia_uri(uri)
					if n and not seen[n] then
						seen[n] = true
						uris[#uris + 1] = n
					end
				end
			end
			profile.aia_uris = uris
		else
			profile.aia_uris = {}
		end

		-- SPKI: Extract public key and SHA256
		if pub then
			local spki = pub:tostring("public", "DER")
			if spki then
				local digest_lib = require("resty.openssl.digest")
				local digest_ctx = digest_lib.new("sha256")
				digest_ctx:update(spki)
				profile.spki_fingerprint = to_hex(digest_ctx:final())
			end
		end
	end)
	if not ok then
		log(ngx.DEBUG, "OCSP certificate profile batch extraction failed")
		-- Discard partial facts — caching a half-filled profile fail-opens Must-Staple
		-- (false) or strands serial/AIA until LRU.
		return {}
	end
	return profile
end

-- ============================================================================
-- has_must_staple(cert_pem)
-- ============================================================================
-- PURPOSE:
--   Check TLS Feature extension for Must-Staple requirement (tri-state).
--   Returns true/false/nil (unknown treated as required by callers).
--
-- PARAMETERS:
--   cert_pem (string): certificate PEM
--
-- RETURNS:
--   (boolean): true if Must-Staple required, false if optional
--   (nil): if TLS Feature not found or parse error
--
-- SIDE EFFECTS:
--   - Memoized: cached per PEM (one x509 parse)
--   - Calls: pem_profile_get() for cached profile
--   - Performance: O(1) memoized, ~1-2ms cache miss
--
-- DESIGN NOTES:
--   - Resty.openssl only: no CLI/temp file (handshake safe)
--   - Tri-state: Unknown treated as required (fail-closed)
--   - Fallback: ocsp.json consulted if resty cannot see TLS Feature
--   - Profile memoized: All facts (SPKI, DN, Must-Staple, serial) cached
--   - Callers: resolve_leaf_must_staple combines TLS Feature + ocsp.json
--
-- RELATED:
--   - resolve_leaf_must_staple() tri-state wrapper (TLS + ocsp.json)
--   - ocsp_json_must_staple() checks ocsp.json flag
--   - pem_profile_get() memoization layer
--
-- ============================================================================
-- Handshake path: resty.openssl only — no /tmp + openssl CLI.
-- Returns true | false | nil (unknown). Unknown must stay fail-closed at call sites
-- that decide whether Must-Staple enforcement applies (never invent false on throw).
-- Callers also consult ocsp.json (written by ocsp-refresh) when resty cannot see
-- Must-Staple — see resolve_leaf_must_staple.
-- Profile is memoized once per PEM (single x509 pass for all facts).
local function has_must_staple(cert_pem)
	if type(cert_pem) ~= "string" or cert_pem == "" then
		return nil
	end
	local profile = pem_profile_get(cert_pem)
	local must = profile and profile.must_staple
	if must == nil then
		return nil
	end
	return must
end

-- ============================================================================
-- PEM_NAMES(pem)
-- ============================================================================
-- PURPOSE:
--   Extracts subject and issuer Distinguished Names (DNs) from a certificate.
--   Returns a tuple of two DN strings for certificate chain matching and
--   issuer validation.
--
-- PARAMETERS:
--   pem (string): certificate in PEM format
--
-- RETURNS:
--   (string, string): (subject_dn, issuer_dn) both as RFC X.500 format strings
--   (nil, nil): if certificate invalid or PEM parsing fails
--
-- SIDE EFFECTS:
--   - Reads: pem_profile_get() cache (profile per PEM)
--   - Calls: pem_profile_get()
--   - Performance: O(1) memoized, ~1-2ms cache miss
--
-- DESIGN NOTES:
--   - Dual return: both DNs extracted in single profile parse (efficient)
--   - Null propagation: if profile missing/invalid, both return nil (not exceptions)
--   - DN format: RFC X.500 as extracted from certificate (C=..., O=..., CN=...)
--   - Used for: self-signed detection (subject == issuer), chain linking,
--     issuer matching in certificate validation
--   - Memoization: all facts (SPKI, DNs, Must-Staple, serial) cached together
--
-- RELATED:
--   - pem_profile_get() — returns full profile with subject_dn/issuer_dn fields
--   - pem_dn_str() — wrapper to extract just subject or issuer alone
--   - is_self_signed() — uses for identity check
--   - certid_matches_handshake_leaf() — uses for issuer matching
--
-- ============================================================================
-- { subject_dn, issuer_dn } strings (either may be nil on parse failure).
-- Profile is memoized once per PEM (single x509 pass for all facts).
local function pem_names(pem)
	local profile = pem_profile_get(pem)
	if type(profile) ~= "table" then
		return nil, nil
	end
	return profile.subject_dn, profile.issuer_dn
end

-- ============================================================================
-- IS_SELF_SIGNED(pem)
-- ============================================================================
-- PURPOSE:
--   Identifies self-signed certificates by comparing subject and issuer DNs.
--   Used to exclude trust anchors from OCSP stapling (self-signed CAs should
--   never appear in certificate chains sent to clients).
--
-- PARAMETERS:
--   pem (string): certificate in PEM format
--
-- RETURNS:
--   (boolean): true if subject == issuer (self-signed)
--   (boolean): false if certificate is not self-signed or DN parsing failed
--
-- SIDE EFFECTS:
--   - Reads: pem_names() to extract subject and issuer DN
--   - Calls: pem_names(pem)
--   - Performance: O(1) with memoization (profile cached per PEM)
--
-- DESIGN NOTES:
--   - Simple check: only validates DN equality, not cryptographic self-signature
--   - Excludes: trust anchors, root CAs, self-signed intermediates from chains
--   - Edge case: if subject or issuer unreadable, returns false (not considered self-signed)
--   - Empty DN check: s == "" returns false (unparseable cert)
--   - Used in: chain building, certificate filtering (never staple self-signed)
--
-- RELATED:
--   - pem_names() — extracts subject and issuer DN strings
--   - issuer_linked_chain_blocks() — filters self-signed when building chains
--   - leaf_aia_ocsp_uris() — related certificate introspection
--
-- ============================================================================
-- Trust anchor (subject == issuer): never a stapled CertificateEntry.
local function is_self_signed(pem)
	local s, iss = pem_names(pem)
	return s ~= nil and s ~= "" and s == iss
end

-- ============================================================================
-- DER_READ(der, pos, limit)
-- ============================================================================
-- PURPOSE:
--   Primitive DER tag/length parser for OCSP CertID serial extraction.
--   Walks a single TLV (Tag-Length-Value) structure in DER format, enforcing
--   strict bounds checking. Replaces absent lua-resty-openssl OCSP module.
--
-- PARAMETERS:
--   der (string): DER-encoded data bytes
--   pos (number): 1-indexed position to start reading (tag byte)
--   limit (number): maximum valid index (inclusive); positions beyond this fail
--
-- RETURNS:
--   (number, number, number, number): (tag, content_start, content_end, next_pos)
--     - tag: byte value of TLV tag (0x00–0xFF)
--     - content_start: 1-indexed position of first content byte
--     - content_end: 1-indexed position of last content byte (inclusive)
--     - next_pos: position after this TLV (content_end + 1), ready for next tag
--   (nil): if DER malformed (out of bounds, invalid length encoding, etc.)
--
-- SIDE EFFECTS:
--   - String indexing only (no state/IO)
--   - Performance: O(1) constant time (max 6 bytes read: 1 tag + 5 length)
--
-- DESIGN NOTES:
--   - DER format (RFC 5280): tag (1 byte) + length (1+ bytes) + content (n bytes)
--   - Tag structure: class (bits 7-6) + constructed (bit 5) + number (bits 4-0)
--   - Length encoding: if < 0x80 → value; else 0x80 OR count, then count bytes
--   - Strict bounds: rejects any structure extending past limit (malformed safe)
--   - Multi-byte length: supports up to 4-byte length fields (max 2^32 octets)
--   - Used by: ocsp_der_serials() to walk OCSP response structure
--   - Error handling: returns nil on any violation (not exceptions)
--
-- RELATED:
--   - ocsp_der_serials() — uses to parse OCSP responses
--   - RFC 5280, RFC 5652 — DER encoding standards
--
-- ============================================================================
-- Minimal DER walk for OCSP CertID serials. lua-resty-openssl has no OCSP module, so
-- the former require("resty.openssl.ocsp") always failed and every CertID check
-- refused. Returns tag, content_start, content_end, next_pos (or nil if malformed).
--
-- DER PARSING: RFC 5280 BER/DER encoding format
--   Tag (1 byte): class (bits 7-6) + constructed (bit 5) + number (bits 4-0)
--   Length (1+ bytes): if byte < 0x80 → value; else high bits (0x80 & val) = count of following bytes
--   Content: length bytes of content
--   Next: content_end + 1
--
-- BOUNDS CHECKING:
--   - pos + 1 > limit → malformed (no tag byte)
--   - length form (0x80 & len): count of bytes to read (max 4 bytes)
--   - cs + n - 1 > limit → malformed (length field extends past boundary)
--   - ce > limit → malformed (content extends past boundary)
--
-- RETURNS: tag (byte), cs (content_start index), ce (content_end index), next_pos
--   or nil if malformed (misaligned, extends past limit, or length form invalid)
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

-- ============================================================================
-- OCSP_DER_SERIALS(der)
-- ============================================================================
-- PURPOSE:
--   Parses an OCSP response DER to extract all SingleResponse CertID serial numbers.
--   Returns serials in response order, canonicalized to uppercase hex without
--   leading zeros. Gate for response structure validation and CertID matching.
--
-- PARAMETERS:
--   der (string): OCSP response in DER format (raw bytes)
--
-- RETURNS:
--   (table): array of serial strings in order (uppercase hex, no leading zeros)
--     - Each serial is valid decimal→hex conversion from RFC 5280 INTEGER
--     - Empty table: never returned; either non-empty or nil
--   (nil): if DER invalid, malformed, unsuccessful status, or structure errors
--
-- SIDE EFFECTS:
--   - Reads: OCSP DER bytes (no modifications)
--   - Calls: der_read() for DER tag/length parsing
--   - Performance: O(n) where n = response size (~1-5ms typical for small responses)
--   - Not memoized: see ocsp_der_serials_memoized() for cached version
--
-- DESIGN NOTES:
--   - DER parse: strict RFC 5280/6960 structure validation (tag/length checks)
--   - Response structure: OCSPResponse → ResponseBytes → BasicOCSPResponse → tbsResponseData
--   - Status check: responseStatus must be 0 (successful); others rejected
--   - SingleResponse parsing: extracts CertID.serialNumber (not hashAlgorithm/hashes)
--   - Serial validation: rejects negative serials (byte >= 0x80); not a leaf serial
--   - Canonical format: lowercase to UPPERCASE, strip leading zeros (except "0")
--   - Error-safe: any malformed structure returns nil (no exceptions)
--
-- RELATED:
--   - der_read() — primitive DER tag/length parser
--   - ocsp_der_serials_memoized() — cached wrapper (external memoization)
--   - ocsp_resp_serial_hex() — wrapper for single serial or find-specific
--   - certid_matches_handshake_leaf() — uses for serial validation
--
-- ============================================================================
-- Canonical uppercase hex serial of every SingleResponse CertID (RFC 6960 4.2.1),
-- in response order. nil when the DER is not a successful basic OCSP response.
-- Memoized by full-body SHA256 (see ocsp_der_memo_fetch).
local function ocsp_der_serials(der)
	if type(der) ~= "string" or #der < 2 then
		return nil
	end
	local n = #der
	local t, s, e, nx
	-- DER sequence tag check
	t, s, e = der_read(der, 1, n)
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
	local _
	t, _, _, nx = der_read(der, s, rd_end)
	if t == 0xA0 then
		t, _, _, nx = der_read(der, nx, rd_end)
	end
	if t ~= 0xA1 and t ~= 0xA2 then
		return nil
	end
	t, _, _, nx = der_read(der, nx, rd_end)
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

-- ============================================================================
-- OCSP_DER_SERIALS_MEMOIZED(ocsp_der)
-- ============================================================================
-- PURPOSE:
--   Memoized wrapper around ocsp_der_serials() for efficient repeated access to
--   the same OCSP response. Caches serial lists by response body SHA256 hash to
--   avoid redundant DER parsing.
--
-- PARAMETERS:
--   ocsp_der (string): OCSP response in DER format
--
-- RETURNS:
--   (table): array of serial strings (from cache if recently seen)
--   (nil): if response invalid or parsing fails (same as ocsp_der_serials)
--
-- SIDE EFFECTS:
--   - Reads: ocsp_der bytes
--   - Calls: ocsp_der_memo_fetch() for memoization logic
--   - Caching: stores result by SHA256(ocsp_der) in module-level memo table
--   - Performance: O(1) on cache hit; O(n) on miss (then cached for future calls)
--
-- DESIGN NOTES:
--   - External memoization: cache key is full response SHA256, not partial
--   - Cache scope: per-session or per-reload (implementation detail)
--   - Idempotent: same DER always returns same result or nil
--   - Memory: grows with unique responses seen (consider cache cleanup on high volume)
--   - Used by: ocsp_resp_serial_hex() internal calls, frequent serial lookups
--   - Alternative: ocsp_der_serials() for one-shot or non-critical paths
--
-- RELATED:
--   - ocsp_der_serials() — underlying parser (unmemoized)
--   - ocsp_der_memo_fetch() — memoization infrastructure
--   - ocsp_resp_serial_hex() — calls this for parsing
--   - certid_matches_handshake_leaf() — indirect usage via ocsp_resp_serial_hex
--
-- ============================================================================
-- Memoized wrapper around ocsp_der_serials to cache results per response body hash.
local function ocsp_der_serials_memoized(ocsp_der)
	return ocsp_der_memo_fetch(ocsp_der, ocsp_der_serials)
end

-- ============================================================================
-- ocsp_resp_serial_hex(ocsp_der, want_hex)
-- ============================================================================
-- PURPOSE:
--   Extract serial number from OCSP response DER (optionally match specific).
--   Used for serial blacklist checking and CertID validation.
--
-- PARAMETERS:
--   ocsp_der (string): OCSP response DER bytes
--   want_hex (string|nil): optional specific serial to match (uppercase hex)
--
-- RETURNS:
--   (string): serial number as uppercase hex (no leading zeros)
--   (nil): if want_hex specified but not found, or DER unreadable
--
-- SIDE EFFECTS:
--   - Memoized: results cached per OCSP DER hash
--   - Calls: ocsp_der_serials_memoized() for parsing
--   - Performance: O(1) memoized, ~1-2ms on cache miss
--
-- DESIGN NOTES:
--   - Flexible matching: want_hex=nil returns first serial
--   - Miss behavior: want_hex set but not found returns nil (not fallback)
--   - Memoization: Results cached to avoid re-parsing same response
--   - Used by: serial blacklist checks, CertID validation
--   - Related: ocsp_der_serials() raw parser
--
-- RELATED:
--   - serial_blacklist_blocks() uses this for blacklist checking
--   - certid_matches_handshake_leaf() uses for CertID validation
--   - ocsp_der_serials() base parser
--
-- ============================================================================
-- Serial of the SingleResponse naming want_hex when present.
-- When want_hex is set and no SingleResponse names it → nil (not serials[1]).
-- When want_hex is nil/omitted → first serial (callers that only need "any").
-- Callers that compare with want_hex must treat nil as miss or unreadable;
-- use a second call without want_hex to distinguish unreadable DER.
local function ocsp_resp_serial_hex(ocsp_der, want_hex)
	local serials = ocsp_der_serials_memoized(ocsp_der)
	if not serials then
		return nil
	end
	if want_hex then
		for _, serial in ipairs(serials) do
			if serial == want_hex then
				return serial
			end
		end
		return nil
	end
	return serials[1]
end

function _M.ocsp_resp_serial_hex(ocsp_der, want_hex)
	return ocsp_resp_serial_hex(ocsp_der, want_hex)
end

-- ============================================================================
-- LEAF_SERIAL_HEX(cert_pem)
-- ============================================================================
-- PURPOSE:
--   Extracts the certificate serial number as uppercase hex without leading zeros.
--   Lightweight wrapper around pem_profile_get() for certificate serial retrieval.
--
-- PARAMETERS:
--   cert_pem (string): certificate in PEM format
--
-- RETURNS:
--   (string): serial number as canonical hex (e.g., "0123456789ABCDEF")
--   (nil): if PEM invalid, empty, or profile/serial unreadable
--
-- SIDE EFFECTS:
--   - Reads: pem_profile_get() cache (profile per PEM)
--   - Calls: pem_profile_get(cert_pem)
--   - Performance: O(1) — profile already parsed and cached once per PEM
--
-- DESIGN NOTES:
--   - Canonical format: uppercase hex, no leading zeros (except "0" for zero serial)
--   - Simple lookup: direct table access on cached profile
--   - Null propagation: if profile missing/nil, returns nil (not exception)
--   - Used for: certificate serial matching in OCSP CertID validation,
--     blacklist checks, certificate comparison
--
-- RELATED:
--   - pem_profile_get() — returns cached profile with serial field
--   - ocsp_resp_serial_hex() — extracts serial from OCSP response
--   - canonical_serial_hex() — normalizes serial hex format
--   - certid_matches_handshake_leaf() — uses for CertID serial matching
--
-- ============================================================================
local function leaf_serial_hex(cert_pem)
	if type(cert_pem) ~= "string" or cert_pem == "" then
		return nil
	end
	local profile = pem_profile_get(cert_pem)
	return profile and profile.serial or nil
end

-- ============================================================================
-- PEM_DN_STR(cert_pem, which)
-- ============================================================================
-- PURPOSE:
--   Extracts the Distinguished Name (DN) string from a certificate in subject or
--   issuer form. Used for certificate chain linking and issuer matching validation.
--
-- PARAMETERS:
--   cert_pem (string): certificate in PEM format
--   which (string|nil): "issuer" to extract issuer DN, defaults to subject DN
--
-- RETURNS:
--   (string): DN string in RFC X.500 format (e.g., "C=US,O=...,CN=...")
--   (nil): if PEM invalid, empty, or named field not readable
--
-- SIDE EFFECTS:
--   - Reads: cert_pem, calls pem_names() for subject/issuer extraction
--   - Calls: pem_names(cert_pem)
--   - Performance: O(1) with memoization (profile cached per PEM)
--
-- DESIGN NOTES:
--   - Default field: "subject" when which is not "issuer"
--   - DN format: extracted as-is from certificate parsing (RFC X.500 order)
--   - Empty check: returns nil if DN string empty or not present
--   - Used for: issuer chain linking, leaf/issuer matching in CertID validation
--   - Related to: subject_issuer_dns for dual extraction
--
-- RELATED:
--   - pem_names() — raw subject/issuer extraction (called internally)
--   - cert_subject_issuer_dns() — returns both subject and issuer together
--   - certid_matches_handshake_leaf() — uses for issuer DN matching
--   - prefilter_issuers_by_spki() — uses for DN grouping
--
-- ============================================================================
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

-- ============================================================================
-- BATCH_SPKI_FINGERPRINTS(issuer_pems)
-- ============================================================================
-- PURPOSE:
--   Bulk-extracts SPKI fingerprints for multiple issuer certificates, avoiding
--   redundant computation when the same PEM appears multiple times in the list.
--   Optimizes for large issuer chains where duplicates are common.
--
-- PARAMETERS:
--   issuer_pems (table): array of issuer certificates in PEM format (may include
--                        duplicates)
--
-- RETURNS:
--   (table): {pem_string → fingerprint_string, ...} mapping each unique PEM to
--            its 64-char hex SHA256 SPKI fingerprint. Entries with nil fingerprint
--            (unreadable PEM) are included in the map.
--   (empty table): if issuer_pems is not a table or empty
--
-- SIDE EFFECTS:
--   - Reads: issuer_pems table, each PEM's profile via spki_fingerprint()
--   - Calls: spki_fingerprint() for each unique PEM
--   - Performance: ~1-3ms per unique PEM (memo hit if same PEM seen before);
--                  deduplication saves 1-3ms per duplicate avoided
--
-- DESIGN NOTES:
--   - Deduplication: tracks seen PEMs in local set; each unique string computed once
--   - Profile memoization: spki_fingerprint() internally caches per-PEM; this function
--     avoids calling it multiple times on identical strings within a single batch
--   - Map structure: PEM as key, fingerprint as value (string→string or string→nil)
--   - Used by: issuer chain disambiguation, pre-filtering candidate issuers
--   - Optimization: typical issuer chains have 2-4 issuers; dedup saves time when
--     bundled with cross-signs or alternate roots
--
-- RELATED:
--   - spki_fingerprint() — single SPKI extraction (memoized per PEM)
--   - batch_spki_fingerprints_filtered() — variant for DN-grouped issuers
--   - prefilter_issuers_by_spki() — uses this to detect duplicate issuers
--   - certid_matches_handshake_leaf() — calls for issuer disambiguation
--
-- ============================================================================
-- Batch extract SPKI fingerprints for multiple issuer PEMs.
-- Avoids redundant extractions when same PEM appears multiple times in list.
-- Returns: {pem1 → fp1, pem2 → fp2, ...} (only unique PEMs computed once)
-- Saves: 1-3ms per duplicate issuer PEM (via memo hit instead of re-extract).
local function batch_spki_fingerprints(issuer_pems)
	local result = {}
	local seen = {}
	if type(issuer_pems) ~= "table" then
		return result
	end
	-- First pass: identify unique PEMs and extract SPKIs.
	-- Memo cache ensures each unique PEM computed only once per batch.
	for _, iss in ipairs(issuer_pems) do
		if type(iss) == "string" and iss ~= "" and not seen[iss] then
			seen[iss] = true
			result[iss] = spki_fingerprint(iss)
		end
	end
	return result
end

-- ============================================================================
-- PREFILTER_ISSUERS_BY_SPKI(issuer_pems, target_dn)
-- ============================================================================
-- PURPOSE:
--   Filters a list of issuer PEMs by matching subject DN, then disambiguates
--   cross-signs by counting distinct SPKI fingerprints. Detects when multiple
--   issuers with the same DN have different keys (certificate ambiguity).
--
-- PARAMETERS:
--   issuer_pems (table): array of issuer certificates in PEM format
--   target_dn (string): subject DN to match (RFC X.500 format)
--
-- RETURNS:
--   (number, table, number): tuple of:
--     - distinct_spki_count: number of unique SPKI fingerprints found (0, 1, or >1)
--     - spki_map: {pem → fingerprint} mapping DN-matched issuers to SPKI
--     - unreadable_count: number of DN-matched issuers with unreadable SPKI
--
-- SIDE EFFECTS:
--   - Reads: issuer_pems, target_dn string
--   - Calls: pem_dn_str(), batch_spki_fingerprints_filtered()
--   - Performance: ~1-3ms (DN extraction + SPKI computation for filtered list)
--
-- DESIGN NOTES:
--   - Two-phase filtering: first by DN (fast), then SPKI computation on matches
--   - Optimization: avoids SPKI extraction for non-matching DNs (large issuers skip)
--   - Unreadable handling: nil SPKI counted separately (never collapsed with valid)
--     {A_fp, nil} reports distinct_spki=1 + unreadable=1, not ambiguous
--   - Cross-sign detection: distinct_spki > 1 indicates same DN, different keys
--   - Return semantics: caller decides policy (1=accept, >1=ambiguous, nil=error)
--   - Used by: certid_matches_handshake_leaf() to disambiguate issuer candidates
--
-- RELATED:
--   - pem_dn_str() — extracts subject DN for filtering
--   - batch_spki_fingerprints_filtered() — computes SPKI for DN-matched group
--   - spki_fingerprint() — underlying SPKI extraction
--   - certid_matches_handshake_leaf() — uses to validate issuer candidates
--
-- ============================================================================
-- Pre-filter issuers by SPKI fingerprint to detect true duplicates early.
-- Groups issuers by (DN, SPKI) pair: if all matching DN have same SPKI, early exit.
-- Returns: distinct_spki_count, spki_map, unreadable_count.
-- unreadable_count > 0 means at least one DN match lacked a readable SPKI.
local function prefilter_issuers_by_spki(issuer_pems, target_dn)
	if type(issuer_pems) ~= "table" or type(target_dn) ~= "string" then
		return 0, {}, 0
	end
	local dn_to_issuers = {}
	local distinct_spki = {}

	-- Group issuers by subject DN first (avoids SPKI extraction for non-matching DNs)
	for _, iss in ipairs(issuer_pems) do
		if type(iss) == "string" and iss ~= "" then
			local subj = pem_dn_str(iss, "subject")
			if subj and subj == target_dn then
				if not dn_to_issuers[iss] then
					dn_to_issuers[iss] = true
				end
			end
		end
	end

	-- Extract SPKI for DN-matching issuers only (pre-filtered list is usually small)
	local spki_map = batch_spki_fingerprints_filtered(dn_to_issuers)

	-- Count distinct readable SPKIs. Any nil fingerprint among DN matches is
	-- reported separately — never treat {A, nil} as a single unambiguous SPKI.
	local seen_spki = {}
	local unreadable = 0
	for iss, _ in pairs(dn_to_issuers) do
		local fp = spki_map[iss]
		if not fp then
			unreadable = unreadable + 1
		elseif not seen_spki[fp] then
			seen_spki[fp] = true
			distinct_spki[#distinct_spki + 1] = fp
		end
	end

	return #distinct_spki, spki_map, unreadable
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

-- ============================================================================
-- CERTID_MATCHES_HANDSHAKE_LEAF(leaf_pem, ocsp_der, issuer_pems)
-- ============================================================================
-- PURPOSE:
--   Validates that an OCSP response (CertID) matches the TLS handshake leaf
--   certificate and can be bound to an issuer in the chain. Returns true only
--   when serial, issuer DN, and SPKI all match—disambiguating cross-signs and
--   detecting stale OCSP under certificate renewal.
--
-- PARAMETERS:
--   leaf_pem (string): leaf certificate in PEM format
--   ocsp_der (string): OCSP response in DER format
--   issuer_pems (table): array of issuer certificates in PEM format
--
-- RETURNS:
--   (true, nil): if all checks pass (serial, DN, SPKI match)
--   (false, reason): on failure with diagnostic code:
--     - "missing_leaf_or_resp": leaf or response missing/invalid
--     - "serial_unreadable": leaf certificate serial unreadable
--     - "serial_mismatch": response serial doesn't match leaf
--     - "leaf_issuer_unreadable": leaf issuer DN not readable
--     - "no_issuer_candidates": issuer_pems empty or invalid
--     - "issuer_mismatch": no issuer DN matches leaf's issuer
--     - "issuer_spki_unreadable": issuer SPKI hash not readable
--     - "issuer_ambiguous": multiple distinct SPKIs for same DN (cross-sign ambiguity)
--
-- SIDE EFFECTS:
--   - Reads: leaf_serial_hex(), pem_dn_str(), ocsp_resp_serial_hex(),
--            prefilter_issuers_by_spki()
--   - Calls: leaf_serial_hex(), ocsp_resp_serial_hex(), pem_dn_str(),
--            prefilter_issuers_by_spki()
--   - Performance: ~1-5ms typical (depends on issuer count and SPKI cache hits)
--
-- DESIGN NOTES:
--   - Serial validation: Exact match required (case-insensitive hex, no leading zeros)
--   - DN matching: Leaf's issuer DN must match at least one issuer PEM's subject DN
--   - SPKI tie-break: When DN alone is ambiguous (cross-signs, different CA branches),
--     SPKI disambiguates. All DN-matched issuers must have same SPKI (or fail).
--   - Not a full CertID check: ocsp_der_serials reads serial only; issuerNameHash
--     and issuerKeyHash are validated by ngx.ocsp.validate_ocsp_response separately.
--   - Scope: covers verified-L1 paths that skip ngx.ocsp.validate_ocsp_response after
--     certificate renewal (same SPKI, stale OCSP left under old body).
--   - Edge case: {A, nil} SPKI counts as 2 (fail-open on unreadable, not collapse).
--
-- RELATED:
--   - leaf_serial_hex() — extracts leaf serial
--   - ocsp_resp_serial_hex() — extracts response serial
--   - pem_dn_str() — extracts subject/issuer DN strings
--   - prefilter_issuers_by_spki() — filters and disambiguates issuers
--   - certid_consistent_with_meta() — metadata-only CertID validation
--
-- ============================================================================
local function certid_matches_handshake_leaf(leaf_pem, ocsp_der, issuer_pems)
	if type(leaf_pem) ~= "string" or leaf_pem == "" or type(ocsp_der) ~= "string" or ocsp_der == "" then
		return false, "missing_leaf_or_resp"
	end
	local leaf_serial = leaf_serial_hex(leaf_pem)
	if not leaf_serial then
		return false, "serial_unreadable"
	end
	local resp_serial = ocsp_resp_serial_hex(ocsp_der, leaf_serial)
	if resp_serial ~= leaf_serial then
		if not ocsp_resp_serial_hex(ocsp_der) then
			return false, "serial_unreadable"
		end
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

	-- Pre-filter issuers by SPKI to detect true duplicates early.
	-- Accept only when every DN match has a readable SPKI and they all agree.
	-- {A, nil} must not collapse to distinct_count==1 (cross-sign fail-open).
	local distinct_spki_count, _, unreadable = prefilter_issuers_by_spki(matches, leaf_issuer)

	if unreadable > 0 then
		return false, "issuer_spki_unreadable"
	end

	-- Optimization: If only 1 distinct SPKI, all issuers are identical, accept immediately.
	if distinct_spki_count == 1 then
		return true, nil
	end

	-- Multiple distinct SPKIs: ambiguous DN (different CAs, cross-signs, etc.)
	if distinct_spki_count > 1 then
		return false, "issuer_ambiguous"
	end

	-- No readable SPKI among DN matches (unreadable already handled above).
	return false, "issuer_spki_unreadable"
end

-- ============================================================================
-- CERTID_CONSISTENT_WITH_META(meta, ocsp_der)
-- ============================================================================
-- PURPOSE:
--   Validates OCSP response CertID against job-published metadata. Used in
--   fingerprint-only mode (no leaf PEM) to verify response serial matches the
--   pinned meta.certid.serial or meta.serial, ensuring response was for the
--   intended certificate.
--
-- PARAMETERS:
--   meta (table): metadata with certid (table with .serial) or serial (string)
--                 certid overrides serial when both present (job-accepted specific response)
--   ocsp_der (string): OCSP response in DER format
--
-- RETURNS:
--   (true, nil): if response serial matches pinned meta serial
--   (false, reason): on mismatch or error:
--     - "no_meta": meta is not a table (missing metadata)
--     - "certid_serial_unreadable": meta.certid.serial invalid/corrupt
--     - "serial_unreadable": meta.serial invalid, or response has no readable serial
--     - "serial_mismatch": response serial differs from pinned serial
--
-- SIDE EFFECTS:
--   - Reads: meta table, ocsp_der bytes
--   - Calls: canonical_serial_hex(), ocsp_resp_serial_hex()
--   - Performance: ~1-2ms (memoized serial extraction)
--
-- DESIGN NOTES:
--   - Fingerprint-only scope: this function handles responses without leaf PEM
--     (full CertID validation needs handshake leaf; see certid_matches_handshake_leaf)
--   - Meta structure: meta.certid takes priority (job's exact SingleResponse match)
--     falls back to meta.serial (job's general certificate match)
--   - Serial canonicalization: both pin and response serials normalized to uppercase hex
--   - Diagnostic chain: first checks if response has SOME readable serial (helps
--     distinguish "response corrupt" vs "serial mismatch")
--   - Used by: fingerprint-only staple binding, OCSP response validation without cert
--
-- RELATED:
--   - certid_matches_handshake_leaf() — full CertID validation with leaf PEM
--   - canonical_serial_hex() — normalizes serial format
--   - ocsp_resp_serial_hex() — extracts response serial by search key
--   - ligand_verdict() — uses for metadata binding decision
--
-- ============================================================================
-- Fingerprint-only path has no handshake leaf PEM: require response CertID serial
-- to match the job-published pin (meta.certid.serial, else meta.serial).
-- When meta.certid is present, those bytes are the SingleResponse the job accepted
-- (exactly one CertID match among possibly several in the DER).
local function certid_consistent_with_meta(meta, ocsp_der)
	if type(meta) ~= "table" then
		return false, "no_meta"
	end
	local pin = meta.certid
	local meta_serial
	if type(pin) == "table" then
		meta_serial = canonical_serial_hex(pin.serial)
		if not meta_serial then
			return false, "certid_serial_unreadable"
		end
	else
		meta_serial = canonical_serial_hex(meta.serial)
	end
	if not meta_serial then
		return false, "serial_unreadable"
	end
	local resp_serial = ocsp_resp_serial_hex(ocsp_der, meta_serial)
	if resp_serial == meta_serial then
		return true, nil
	end
	if not ocsp_resp_serial_hex(ocsp_der) then
		return false, "serial_unreadable"
	end
	return false, "serial_mismatch"
end

-- ============================================================================
-- LEAF_AIA_OCSP_URIS(cert_pem)
-- ============================================================================
-- PURPOSE:
--   Extracts all OCSP URIs from a certificate's Authority Info Access (AIA)
--   extension. Returns a fresh copy safe for mutation, supporting Must-Staple
--   validation and OCSP URI matching.
--
-- PARAMETERS:
--   cert_pem (string): certificate in PEM format
--
-- RETURNS:
--   (table): array of OCSP URIs from AIA extension (may be empty if none present)
--     - Each URI is normalized (lowercase scheme, no userinfo, default ports omitted)
--     - Fresh copy each call (caller can mutate without affecting cache)
--   (never nil, always returns table)
--
-- SIDE EFFECTS:
--   - Reads: pem_profile_get() cache (AIA URIs pre-extracted and cached per PEM)
--   - Calls: pem_profile_get()
--   - Performance: O(n) where n = number of AIA URIs (typically 1-3); table copy trivial
--
-- DESIGN NOTES:
--   - AIA extension (RFC 5280 4.2.2.1): contains method + URI pairs
--   - Extraction: filter for OCSP method (1.3.6.1.5.5.7.48.1)
--   - Normalization: scheme lowercase, userinfo dropped, default :80/:443 omitted
--   - Fresh copy: each call returns independent array (safe for caller mutations)
--   - Empty case: returns {} if AIA missing, malformed, or no OCSP URIs
--   - Used for: Must-Staple compliance (pin matching), URI list validation,
--     OCSP responder availability checking
--
-- RELATED:
--   - pem_profile_get() — returns cached profile with aia_uris field
--   - normalize_ocsp_aia_uri() — normalizes individual URIs
--   - aia_uri_pin_ok() — compares leaf URIs against staple pin
--   - has_must_staple() — determines Must-Staple enforcement
--
-- ============================================================================
-- All OCSP URIs from leaf AIA (authorityInfoAccess), normalized.
-- Profile is memoized once per PEM; returned list is a fresh copy (safe to mutate).
local function leaf_aia_ocsp_uris(cert_pem)
	local profile = pem_profile_get(cert_pem)
	local uris = profile and profile.aia_uris
	if type(uris) ~= "table" then
		return {}
	end
	local out = {}
	for i = 1, #uris do
		out[i] = uris[i]
	end
	return out
end

-- ============================================================================
-- AIA_URI_PIN_OK(leaf_pem, meta, must_staple)
-- ============================================================================
-- PURPOSE:
--   Validates that the published OCSP staple's AIA URI pin matches the live leaf
--   certificate's AIA OCSP URI. Required for Must-Staple compliance and critical
--   for detecting configuration drift or certificate changes.
--
-- PARAMETERS:
--   leaf_pem (string|nil): leaf certificate in PEM format (may be absent in
--                          fingerprint-only mode)
--   meta (table|nil): metadata table with aia_ocsp_uri or ocsp_url field
--   must_staple (boolean): whether certificate has Must-Staple TLS Feature
--
-- RETURNS:
--   (true, nil): if pin matches leaf AIA URI (or optional pin when no PEM)
--   (false, reason): on failure with diagnostic code:
--     - "aia_uri_unpinned": meta has no AIA URI field (Must-Staple only)
--     - "aia_uri_leaf_unavailable": PEM missing but Must-Staple requires live check
--     - "aia_uri_missing_on_leaf": leaf certificate has no AIA OCSP URI extension
--     - "aia_uri_mismatch": pinned URI differs from leaf's AIA URI
--
-- SIDE EFFECTS:
--   - Reads: meta.aia_ocsp_uri or meta.ocsp_url, leaf certificate AIA extension
--   - Calls: normalize_ocsp_aia_uri(), leaf_aia_ocsp_uris()
--   - Logging: ERR level on leaf/pin mismatches (helps troubleshoot config drift)
--   - Performance: ~1ms typical (profile/AIA extraction already cached)
--
-- DESIGN NOTES:
--   - Optional staple: absence of pin or PEM is permitted (pin + ligand still bind)
--   - Must-Staple mode: fail-closed on missing/mismatched URI (security requirement)
--   - Fingerprint-only (no PEM): Optional staple allows pin alone; Must-Staple rejects
--   - URI normalization: both pin and leaf URIs normalized before comparison
--     (scheme lowercase, userinfo dropped, default ports omitted)
--   - Multiple AIA URIs: any leaf URI match against single normalized pin is sufficient
--   - Drift detection: on mismatch, logs both pin and leaf AIA count for troubleshooting
--
-- RELATED:
--   - normalize_ocsp_aia_uri() — canonicalizes URLs for comparison
--   - leaf_aia_ocsp_uris() — extracts all AIA OCSP URIs from certificate
--   - has_must_staple() — detects Must-Staple TLS Feature extension
--   - certid_consistent_with_meta() — related metadata validation
--
-- ============================================================================
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

-- ============================================================================
-- CERT_PUBKEY_KIND(cert_pem)
-- ============================================================================
-- PURPOSE:
--   Classifies a certificate's public key type ("rsa", "ec", "ed") for dual-cert
--   staple selection and signature scheme matching in TLS handshakes.
--
-- PARAMETERS:
--   cert_pem (string): certificate in PEM format
--
-- RETURNS:
--   (string): "rsa", "ec", or "ed" — public key type
--   (nil): if PEM invalid, empty, or profile unavailable
--
-- SIDE EFFECTS:
--   - Reads: pem_profile_get() cache (profile table per PEM)
--   - Calls: pem_profile_get()
--   - Performance: O(1) — profile pre-computed and cached on first access
--
-- DESIGN NOTES:
--   - Canonical key types: RSA, ECDSA (ec), EdDSA (ed)
--   - Profile memoized once per PEM with single x509 pass (all cert facts together)
--   - Used for: dual-cert staple selection (pick RSA or ECDSA cert), scheme matching
--   - Related to: curve_nid in profile (additional ECDSA/EdDSA curve metadata)
--
-- RELATED:
--   - pem_profile_get() — returns cached profile with pubkey_kind
--   - cert_sig_profile() — returns kind + curve_nid as fresh table
--   - leaf_matches_scheme() — validates scheme matches kind/curve
--   - key_spki_fingerprint() — similar structure for private keys
--
-- ============================================================================
-- Classify leaf PEM as "ec", "rsa", "ed", or nil (for dual-cert staple selection).
-- Profile is memoized once per PEM (single x509 pass for all facts).
local function cert_pubkey_kind(cert_pem)
	if type(cert_pem) ~= "string" or cert_pem == "" then
		return nil
	end
	local profile = pem_profile_get(cert_pem)
	return profile and profile.pubkey_kind or nil
end

-- ============================================================================
-- CERT_SIG_PROFILE(cert_pem)
-- ============================================================================
-- PURPOSE:
--   Returns a fresh table with public key kind and curve NID for matching against
--   TLS SignatureScheme fields in ClientHello. Encapsulates profile fields while
--   protecting the memoized cache from caller-induced mutations.
--
-- PARAMETERS:
--   cert_pem (string): certificate in PEM format
--
-- RETURNS:
--   (table): {kind: string|nil, curve_nid: number|nil}
--     - kind: "rsa", "ec", "ed", or nil
--     - curve_nid: NID_P256/NID_P384/NID_P521 (ec), NID_ED25519/NID_ED448 (ed), or nil
--   (never nil, always returns a table)
--
-- SIDE EFFECTS:
--   - Reads: pem_profile_get() cache
--   - Calls: pem_profile_get()
--   - Performance: O(1) — profile cached, table copy trivial (~1µs)
--
-- DESIGN NOTES:
--   - Fresh table per call: each caller receives independent copy to prevent
--     accidental cache pollution via field mutations (caller's t.kind = X doesn't
--     affect memoized profile or other callers)
--   - Graceful fallback: returns {nil, nil} when profile missing/invalid (not nil)
--   - Thin projection: only exposes kind and curve_nid, hides SPKI/serial/issuer
--   - TLS scheme matching: callers use this against ClientHello SignatureScheme list
--     to verify certificate can produce CertificateVerify for the scheme
--
-- RELATED:
--   - cert_pubkey_kind() — returns kind only (lighter weight)
--   - leaf_matches_scheme() — validates returned profile against scheme number
--   - pem_profile_get() — returns memoized full profile (internal cache)
--
-- ============================================================================
-- kind + curve_nid for matching ClientHello signature_algorithms schemes.
-- Fresh table each call so callers cannot poison the PEM memo via field writes.
-- Profile is memoized once per PEM; this is a thin view of the cache entry.
local function cert_sig_profile(cert_pem)
	local profile = pem_profile_get(cert_pem)
	if type(profile) ~= "table" then
		return { kind = nil, curve_nid = nil }
	end
	return { kind = profile.pubkey_kind, curve_nid = profile.curve_nid }
end

-- ============================================================================
-- LEAF_MATCHES_SCHEME(profile, scheme)
-- ============================================================================
-- PURPOSE:
--   Validates that a certificate's public key type and curve can produce a valid
--   CertificateVerify signature for a specific TLS SignatureScheme. Used to reject
--   signature schemes incompatible with the certificate's key material.
--
-- PARAMETERS:
--   profile (table): {kind: string, curve_nid: number} from cert_sig_profile()
--   scheme (number): TLS SignatureScheme as 16-bit value (e.g., 0x0403 for
--                    ecdsa_secp256r1_sha256, 0x0401 for rsa_pkcs1_sha256)
--
-- RETURNS:
--   (boolean): true if profile's key type and curve match scheme; false otherwise
--
-- SIDE EFFECTS:
--   - Reads: profile.kind, profile.curve_nid
--   - Calls: none (pure validation)
--   - Performance: O(1) — constant-time table lookup
--
-- DESIGN NOTES:
--   - Scheme encoding: TLS 1.3 uses 16-bit SignatureScheme values in ClientHello
--   - Supported RSA schemes: pkcs1 (0x0401/0x0501/0x0601) and PSS (0x0804-0x080b)
--   - Supported ECDSA schemes: P256 (0x0403), P384 (0x0503), P521 (0x0603)
--   - Supported EdDSA schemes: Ed25519 (0x0807), Ed448 (0x0808)
--   - Fail-safe: returns false for unknown schemes or invalid profile (no exceptions)
--   - Used for: cert/scheme compatibility checks during handshake sig validation
--
-- RELATED:
--   - cert_sig_profile() — produces profile parameter
--   - NID_P256, NID_P384, NID_P521 — ECDSA curve identifiers
--   - NID_ED25519, NID_ED448 — EdDSA key identifiers
--   - certid_matches_handshake_leaf() — broader certificate validation context
--
-- ============================================================================
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

-- ============================================================================
-- PARSE_PEM_KEYS(pem_data)
-- ============================================================================
-- PURPOSE:
--   Parses a concatenated PEM string containing one or more private keys,
--   extracting each key block (BEGIN...END) as a separate PEM-formatted string.
--   Used for multi-key configurations (dual RSA/ECDSA certs, key rotation).
--
-- PARAMETERS:
--   pem_data (string): concatenated PEM file data (may contain multiple private key blocks)
--
-- RETURNS:
--   (table): array of individual PEM strings, one per private key block found
--   (empty table): if pem_data is nil, empty, not a string, or contains no keys
--
-- SIDE EFFECTS:
--   - Reads: pem_data string
--   - Calls: line-by-line gmatch parsing (no FFI)
--   - Performance: O(n) where n = number of lines; typical 1-3ms for reasonable files
--
-- DESIGN NOTES:
--   - PEM block detection: matches "-----BEGIN" + "PRIVATE KEY" in header
--                           matches "-----END" + "PRIVATE KEY" in trailer
--   - Multi-block support: extracts multiple keys if file contains several
--   - Concatenation: preserves newlines between lines (reconstructs valid PEM)
--   - Error resilience: incomplete blocks (no END marker) are silently dropped
--   - Format agnostic: handles PKCS#1 (RSA, EC), PKCS#8, SEC1 equally
--   - Used by: dual-cert key loading, certificate rollover, key bundle processing
--
-- RELATED:
--   - key_spki_fingerprint() — computes SPKI for keys extracted by this function
--   - batch_spki_fingerprints() — similar bulk extraction for certificates
--   - pem_blocks() — related PEM block splitting (for certificates)
--
-- ============================================================================
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

-- ============================================================================
-- KEY_SPKI_FINGERPRINT(key_pem)
-- ============================================================================
-- PURPOSE:
--   Computes the SHA256 fingerprint of a private key's SPKI (SubjectPublicKeyInfo)
--   in DER format. Mirrors cert spki_fingerprint for private keys, enabling
--   symmetric matching between certificates and private keys (dual-cert pinning).
--
-- PARAMETERS:
--   key_pem (string): private key in PEM format (PKCS#1, PKCS#8, or SEC1)
--
-- RETURNS:
--   (string): 64-character hex SHA256 of SPKI, if key readable and valid
--   (nil): on parse error, missing key, or FFI failure
--
-- SIDE EFFECTS:
--   - Reads: key_pem file data
--   - Calls: resty.openssl.pkey.new(), resty.openssl.digest (FFI to OpenSSL)
--   - FFI calls: libssl/libcrypto for key parsing and SHA256 hashing
--   - Performance: ~1-5ms (key load and hash computation, not cached)
--   - Error handling: wrapped in pcall() — all exceptions converted to nil return
--
-- DESIGN NOTES:
--   - SPKI extraction: key_obj:tostring(false, "DER") extracts public key SPKI
--   - Hashing: SHA256 computed via OpenSSL's EVP digest API
--   - Error resilience: pcall() ensures no exceptions escape (parse fails → nil)
--   - Not memoized: unlike cert profiles, key fingerprints computed fresh each call
--     (keys typically loaded once during startup; cost is acceptable)
--   - Symmetric with cert: produces same SPKI fingerprint as certificate public key
--   - Use case: dual-cert pinning, private key/cert matching validation
--
-- RELATED:
--   - spki_fingerprint() — computes SPKI for certificates (memoized)
--   - batch_spki_fingerprints() — bulk cert SPKI extraction
--   - parse_pem_keys() — parses multiple keys from concatenated PEM
--   - pem_profile_get() — memoized profile cache (certificates only)
--
-- ============================================================================
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

-- ============================================================================
-- CERT_SPKI_FINGERPRINT(cert_pem)
-- ============================================================================
-- PURPOSE:
--   Public wrapper around spki_fingerprint() for certificate SPKI extraction.
--   Exported to _M.internal for access from other modules.
--
-- PARAMETERS:
--   cert_pem (string): certificate in PEM format
--
-- RETURNS:
--   (string): 64-character hex SHA256 of SPKI
--   (nil): if profile missing or SPKI unreadable
--
-- SIDE EFFECTS:
--   - Reads: pem_profile_get() cache
--   - Calls: spki_fingerprint()
--   - Performance: O(1) memoized
--
-- DESIGN NOTES:
--   - Thin wrapper: direct pass-through to spki_fingerprint()
--   - Exported as: _M.internal.cert_spki_fingerprint for module visibility
--   - Purpose: public API boundary for certificate SPKI access
--
-- RELATED:
--   - spki_fingerprint() — internal implementation
--   - key_spki_fingerprint() — analogous wrapper for private keys
--
-- ============================================================================
local function cert_spki_fingerprint(cert_pem)
	return spki_fingerprint(cert_pem)
end

-- ============================================================================
-- CERT_SUBJECT_ISSUER_DNS(pem)
-- ============================================================================
-- PURPOSE:
--   Public wrapper around pem_names() for extracting both subject and issuer DNs.
--   Exported to _M.internal for issuer-path linking and certificate comparison.
--
-- PARAMETERS:
--   pem (string): certificate in PEM format
--
-- RETURNS:
--   (string, string): (subject_dn, issuer_dn) both RFC X.500 format
--   (nil, nil): if certificate invalid or parsing fails
--
-- SIDE EFFECTS:
--   - Reads: pem_profile_get() cache
--   - Calls: pem_names()
--   - Performance: O(1) memoized
--
-- DESIGN NOTES:
--   - Thin wrapper: direct pass-through to pem_names()
--   - Exported as: _M.internal.cert_subject_issuer_dns for module visibility
--   - Dual return: both DNs extracted in single parse (efficient)
--   - Used for: issuer path linking, certificate chain building
--
-- RELATED:
--   - pem_names() — internal implementation
--   - pem_dn_str() — single DN extraction (subject or issuer)
--
-- ============================================================================
-- Subject / issuer DN strings for issuer-path linking (nil on parse failure).
local function cert_subject_issuer_dns(pem)
	return pem_names(pem)
end

_M.internal = {
	aia_uri_pin_ok = aia_uri_pin_ok,
	batch_spki_fingerprints = batch_spki_fingerprints,
	cert_pubkey_kind = cert_pubkey_kind,
	cert_sig_profile = cert_sig_profile,
	cert_spki_fingerprint = cert_spki_fingerprint,
	cert_subject_issuer_dns = cert_subject_issuer_dns,
	certid_consistent_with_meta = certid_consistent_with_meta,
	certid_matches_handshake_leaf = certid_matches_handshake_leaf,
	has_must_staple = has_must_staple,
	is_self_signed = is_self_signed,
	key_spki_fingerprint = key_spki_fingerprint,
	leaf_matches_scheme = leaf_matches_scheme,
	ocsp_resp_serial_hex = ocsp_resp_serial_hex,
	parse_pem_keys = parse_pem_keys,
	pem_blocks = pem_blocks,
	spki_fingerprint = spki_fingerprint,
	-- Pure helpers exported for unit tests (no disk / no ngx.ocsp).
	tls_feature_is_must_staple = tls_feature_is_must_staple,
	ocsp_der_serials = ocsp_der_serials,
	normalize_ocsp_aia_uri = normalize_ocsp_aia_uri,
	canonical_serial_hex = canonical_serial_hex,
}

return _M
