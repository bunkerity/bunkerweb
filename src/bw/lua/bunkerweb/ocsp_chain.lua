--[[
================================================================================
OCSP Chain Module: Certificate Chain Presentation and Multi-Staple Attachment
================================================================================

MODULE OVERVIEW:
Manages certificate chain presentation to TLS clients and OCSP response
attachment via ngx.ocsp. Implements TLS 1.3 multi-staple (leaf + intermediates)
with fallback to leaf-only for older OpenSSL versions.

KEY RESPONSIBILITIES:
1. Issuer-Linked Chain Building: issuer_linked_chain_blocks() filters cert bag
   (cross-signs, unused extras) keeping only verified path from leaf to trust
   anchor. Drops off-path certs that cannot fail-close Must-Staple.

2. Presentable Chain: presentable_chain_blocks() caches issuer-linked result
   per-request (optimization #3) to avoid redundant chain building across
   multiple handshake phases (probe, health check, final attach).

3. Multi-Staple Capability: openssl_multi_staple_ready() probes SSL_ctrl(143)
   and publishes worker vote. Colony MIN (any leaf-only peer → leaf-only fleet)
   prevents mid-install intermediate Must-Staple failures.

4. Staple Attachment: attach_ocsp_staple() decides leaf-only vs multi-staple,
   builds FFI stack, calls SSL_ctrl 143 or 71, and refuses when intermediate
   Must-Staple is unprovable.

5. Connection Staple Clearing: clear_connection_staple() drops L1 on context
   swap (HTTP/2 coalescing, plugin re-entry) to prevent leaf A's staple
   landing on leaf B.

CACHE HIERARCHY:
- L1 (Per-Request ngx.ctx): presentable_chain_blocks cache (Tier 1)
- L2 (Fallback LRU): 64-entry touch-counter LRU when ngx.ctx unavailable
  (edge case for stream-only or unusual setups)
- Multi-Staple Attach: LRU to cache chain format (leaf SPKI + bag identity)
  avoiding redundant re-linkage.

EXPORTS:
- Public: attach_ocsp_staple, issuer_linked_chain_pem, chain_has_intermediate_must_staple
- Internal: presentable_chain_blocks, issuer_path_intermediate_ready, multi-staple probing

DEPENDENCIES:
- ocsp_cert: cert_subject_issuer_dns, spki_fingerprint, is_self_signed, pem_blocks
- ocsp_store: cert_must_staple_bool, cluster_floor_blocks
- ocsp_pin: peer_refuse_blocks
- Called by ocsp.lua try_staple, probe, health check phases

================================================================================
]]

-- Issuer-chain presentation and staple attach/clear (TLS 1.3 multi-staple via FFI).
-- Part of bunkerweb.ocsp; other modules use the .internal table, callers use bunkerweb.ocsp.
local _M = {}

local ngx = ngx

local common = require("bunkerweb.ocsp_common").internal
local is_fp64 = common.is_fp64
local log = common.log
local ocsp_path = common.ocsp_path
local read_file = common.read_file
local to_hex = common.to_hex

local cert = require("bunkerweb.ocsp_cert").internal
local batch_spki_fingerprints = cert.batch_spki_fingerprints
local cert_subject_issuer_dns = cert.cert_subject_issuer_dns
local is_self_signed = cert.is_self_signed
local pem_blocks = cert.pem_blocks
local spki_fingerprint = cert.spki_fingerprint

local store = require("bunkerweb.ocsp_store").internal
local cert_must_staple_bool = store.cert_must_staple_bool
local cluster_floor_blocks = store.cluster_floor_blocks
local meta_tombstoned = store.meta_tombstoned
local ocsp_json_ligand_matches = store.ocsp_json_ligand_matches
local read_ocsp_json = store.read_ocsp_json
local resp_still_fresh = store.resp_still_fresh
local serial_blacklist_blocks = store.serial_blacklist_blocks
local shard_not_paged = store.shard_not_paged

local pin = require("bunkerweb.ocsp_pin").internal
local peer_refuse_blocks = pin.peer_refuse_blocks

-- Forward declarations: assigned below with `name = function`, never `local function`
-- (a second local would shadow these and leave earlier callers holding nil).
local attach_ocsp_staple
local issuer_path_intermediate_ready
local clear_connection_staple
local note_connection_staple
-- OpenSSL staple setters are macros over SSL_ctrl, not exported symbols, so they
-- must be called through SSL_ctrl (an ffi.C lookup of the macro name throws).
-- 143 exists from OpenSSL 3.6; earlier libssl returns 0 for an unknown ctrl.
local SSL_CTRL_SET_TLSEXT_STATUS_REQ_OCSP_RESP = 71
local SSL_CTRL_SET_TLSEXT_STATUS_REQ_OCSP_RESP_EX = 143

-- Fallback cache for when ngx.ctx is unavailable (optimization #7).
-- Touch-counter LRU: O(1) hits, O(n) only on eviction when full.
-- Keys MUST include the intermediate bag identity (not leaf SPKI alone) —
-- same leaf with a fatter Must-Staple bag must not hit a prior clean entry.
local fallback_chain_cache = {}
local fallback_cache_touch = {} -- key → monotonic touch
local fallback_touch_gen = 0
local fallback_cache_count = 0
local fallback_cache_max = 64

-- ============================================================================
-- FALLBACK_TOUCH(key)
-- ============================================================================
-- PURPOSE:
--   Updates the touch timestamp for a cache entry in the fallback LRU.
--   Used by fallback_cache_get() and fallback_cache_set() to track recency
--   for eviction ordering.
--
-- PARAMETERS:
--   key (string): cache key (leaf_spki|bag_identity format)
--
-- RETURNS:
--   (nil): no return value; side effect only
--
-- SIDE EFFECTS:
--   - Reads: global fallback_touch_gen, global fallback_cache_touch table
--   - Writes: fallback_cache_touch[key] = monotonic timestamp
--   - Performance: O(1) table assignment
--
-- DESIGN NOTES:
--   - Monotonic counter: fallback_touch_gen increments per touch (LRU order deterministic)
--   - Simple scheme: no clock; generation counter serves as recency marker
--   - Used by: fallback_cache_get (on hit), fallback_cache_set (on insert)
--   - Eviction uses: fallback_evict_lru() finds minimum touch value for victim
--   - Cache key: includes both leaf SPKI and bag identity (prevents poisoning)
--
-- RELATED:
--   - fallback_cache_get() — calls after successful lookup
--   - fallback_cache_set() — calls on insert
--   - fallback_evict_lru() — uses touch values for victim selection
--
-- ============================================================================
local function fallback_touch(key)
	fallback_touch_gen = fallback_touch_gen + 1
	fallback_cache_touch[key] = fallback_touch_gen
end

-- ============================================================================
-- FALLBACK_EVICT_LRU()
-- ============================================================================
-- PURPOSE:
--   Evicts the least-recently-used entry from the fallback chain cache when
--   at capacity. Implements touch-counter LRU for edge cases where ngx.ctx
--   is unavailable.
--
-- RETURNS:
--   (boolean): true if an entry was evicted (space freed), false if cache empty
--
-- SIDE EFFECTS:
--   - Reads: global fallback_chain_cache, fallback_cache_touch, fallback_cache_count
--   - Writes: fallback_chain_cache[key] = nil, fallback_cache_touch[key] = nil,
--            fallback_cache_count decremented, possibly full cache wipe
--   - Performance: O(n) where n ≤ 64 (acceptable for small cache)
--
-- DESIGN NOTES:
--   - LRU algorithm: finds entry with minimum touch value (oldest access)
--   - Single eviction: removes exactly one victim, not a sweep
--   - Touch counter: monotonic, set by fallback_touch() on each access
--   - Cache key: leaf_spki|bag_identity (includes intermediate count + SPKIs)
--   - Recovery: if cache_count mismatch detected, wipes entire cache to reset
--   - Edge case: called only when ngx.ctx unavailable (rare) and cache full
--   - Fallback scope: stream-only mode or unusual setups without per-request context
--
-- RELATED:
--   - fallback_cache_set() — calls when cache full
--   - fallback_touch() — updates touch values
--   - fallback_cache_get() — reads from cache
--   - fallback_cache_max — capacity limit (64 entries)
--
-- ============================================================================
-- Evict oldest entry from fallback chain cache when at capacity.
-- Implements LRU (Least Recently Used) eviction via touch counter.
-- Called only when cache is full and a new entry must be added (optimization #7).
--
-- ALGORITHM: O(n) scan for minimum touch across all entries (n ≤ 64; no heap).
--   - touch_gen monotonically increments per hit/set (LRU order is deterministic)
--   - Scans entire cache once to find entry with minimum touch value
--   - Removes exactly one entry on eviction (not a sweep, just one victim)
--   - Returns true only if an entry was deleted (false = cache empty on mismatch)
--
-- CACHE KEY: "leaf_spki|intermediate_bag_identity" (not leaf SPKI alone)
--   - Prevents same leaf + fatter Must-Staple bag from poisoning prior clean entry
--   - Bag identity includes intermediate count + SPKI checksums via presentable_cache_key
--   - Example: "abc123...|3|sha1...|sha2..." (leaf + 3 intermediates)
--
-- INVARIANT: fallback_cache_count must match actual entry count; evict decrements it.
-- If cache appears empty despite fallback_cache_count > 0, something is inconsistent
-- and we reset the entire cache (wipe + count=0) to recover.
--
-- Performance: O(n) where n ≤ 64 (full scan is acceptable for small cache)
-- Called when: ngx.ctx is unavailable and cache is full (rare edge case)
--
-- @return: true if an entry was evicted (space freed for new entry), false if cache was empty
local function fallback_evict_lru()
	-- ALGORITHM: O(n) scan for minimum touch across all entries (n ≤ 64; no heap).
	--   - touch_gen monotonically increments per hit/set (LRU order is deterministic)
	--   - Removes exactly one entry on eviction (not a sweep, just one victim)
	--   - Returns true only if an entry was deleted (false = cache empty)
	--
	-- CACHE KEY: "leaf_spki|intermediate_bag_identity" (not leaf SPKI alone)
	--   - Prevents same leaf + fatter Must-Staple bag from poisoning prior clean entry
	--   - Bag identity includes intermediate count + SPKI checksums via presentable_cache_key
	local oldest_key, oldest_touch = nil, nil
	for k, t in pairs(fallback_cache_touch) do
		if oldest_touch == nil or t < oldest_touch then
			oldest_touch = t
			oldest_key = k
		end
	end
	if not oldest_key then
		return false
	end
	fallback_chain_cache[oldest_key] = nil
	fallback_cache_touch[oldest_key] = nil
	fallback_cache_count = fallback_cache_count - 1
	return true
end

-- ============================================================================
-- FALLBACK_CACHE_GET(key)
-- ============================================================================
-- PURPOSE:
--   Retrieves a chain cache entry from the fallback LRU and updates its
--   recency timestamp on hit.
--
-- PARAMETERS:
--   key (string): cache key (leaf_spki|bag_identity format)
--
-- RETURNS:
--   (string): cached chain blocks value (or nil on miss)
--   (nil): if key not in cache
--
-- SIDE EFFECTS:
--   - Reads: global fallback_chain_cache
--   - Writes: calls fallback_touch(key) on cache hit (updates recency)
--   - Performance: O(1) table lookup + optional O(1) touch
--
-- DESIGN NOTES:
--   - Cache hit: returns value and updates LRU recency
--   - Cache miss: returns nil (no side effects)
--   - Used by: presentable_chain_blocks() as fallback when ngx.ctx unavailable
--   - Touch update: ensures hit is counted in LRU eviction ordering
--
-- RELATED:
--   - fallback_cache_set() — inserts entries
--   - fallback_touch() — updates recency on hit
--   - presentable_chain_blocks() — calls for caching chain format
--
-- ============================================================================
local function fallback_cache_get(key)
	local v = fallback_chain_cache[key]
	if v ~= nil then
		fallback_touch(key)
		return v
	end
	return nil
end

-- ============================================================================
-- FALLBACK_CACHE_SET(key, value)
-- ============================================================================
-- PURPOSE:
--   Stores or updates a chain cache entry in the fallback LRU, evicting
--   an old entry if at capacity.
--
-- PARAMETERS:
--   key (string): cache key (leaf_spki|bag_identity format)
--   value (string): chain blocks to cache
--
-- RETURNS:
--   (nil): no return value; side effect only
--
-- SIDE EFFECTS:
--   - Reads/writes: global fallback_chain_cache, fallback_cache_count
--   - Writes: may call fallback_evict_lru() if at capacity
--   - Performance: O(1) on update, O(64) worst-case on new entry with eviction
--
-- DESIGN NOTES:
--   - Update case: if key exists, replace value and touch (no eviction)
--   - Insert case: if cache full, evict LRU victim first (O(64) scan)
--   - Recovery: if evict fails and cache inconsistent, wipes entire cache
--   - Cache key: leaf_spki|bag_identity format (prevents poisoning)
--   - Used by: presentable_chain_blocks() when caching chain format
--   - Fallback scope: ngx.ctx unavailable (rare stream-only or edge case)
--
-- RELATED:
--   - fallback_cache_get() — retrieves entries
--   - fallback_evict_lru() — evicts victim on capacity
--   - fallback_touch() — updates recency
--   - presentable_chain_blocks() — calls to cache chain format
--
-- ============================================================================
local function fallback_cache_set(key, value)
	if fallback_chain_cache[key] ~= nil then
		fallback_chain_cache[key] = value
		fallback_touch(key)
		return
	end
	if fallback_cache_count >= fallback_cache_max then
		if not fallback_evict_lru() then
			fallback_chain_cache = {}
			fallback_cache_touch = {}
			fallback_cache_count = 0
		end
	end
	fallback_chain_cache[key] = value
	fallback_touch(key)
	fallback_cache_count = fallback_cache_count + 1
end

-- ffi + C with SSL_ctrl, the OpenSSL stack API and the OCSP_RESPONSE codec declared,
-- or nil. Reuses lua-resty-openssl's typedefs; each fallback declaration gets its own
-- ============================================================================
-- SSL_FFI()
-- ============================================================================
-- PURPOSE:
--   Lazily loads FFI bindings to OpenSSL for multi-staple support (SSL_ctrl,
--   certificate stack manipulation, OCSP response handling). Returns cached
--   ffi module and C function references.
--
-- RETURNS:
--   (table): {ffi: ffi_module, C: ffi.C} with loaded symbols
--   (nil): if FFI unavailable or symbol resolution failed
--
-- SIDE EFFECTS:
--   - Reads: cached _ssl_ffi on subsequent calls
--   - Calls: pcall(require("ffi")), multiple pcall(ffi.cdef, ...) for declarations
--   - Performance: O(1) on cache hit (after first call), ~1-2ms on first miss
--
-- DESIGN NOTES:
--   - Lazy loading: first call declares all FFI bindings, subsequent calls return cache
--   - Error resilience: all FFI operations wrapped in pcall() (non-fatal on failure)
--   - Cached state: _ssl_ffi = false means unavailable (don't retry), table = ready
--   - Declarations: SSL_ctrl, TLS_server_method, SSL_CTX_*, SSL_new/free, stack ops,
--     OCSP_RESPONSE parsing (d2i_OCSP_RESPONSE, OCSP_RESPONSE_free)
--   - Symbol check: probes ffi.C.SSL_ctrl to verify all symbols loadable
--   - Used by: probe_multi_staple_ctrl() for capability check
--
-- RELATED:
--   - probe_multi_staple_ctrl() — uses to test SSL_ctrl(143) support
--   - ffi.cdef declarations — OpenSSL C function signatures
--
-- ============================================================================
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
		"int OPENSSL_sk_num(const void *st);",
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

-- ============================================================================
-- PROBE_MULTI_STAPLE_CTRL()
-- ============================================================================
-- PURPOSE:
--   Tests whether the installed libssl supports TLS 1.3 multi-staple (SSL_ctrl
--   143 = SET_TLSEXT_STATUS_REQ_OCSP_RESP_EX). Capability probe, not version gate.
--
-- RETURNS:
--   (boolean): true if SSL_ctrl(ssl, 143, ...) returns 1 (supported)
--   (boolean): false if FFI unavailable, SSL_CTX creation failed, or probe returned 0
--
-- SIDE EFFECTS:
--   - Calls: ssl_ffi() to load FFI bindings
--   - FFI calls: TLS_server_method(), SSL_CTX_new(), SSL_new(), SSL_ctrl(),
--              SSL_free(), SSL_CTX_free() on a scratch SSL context
--   - Performance: ~5-10ms (test context allocation + FFI call)
--   - Exceptions: all wrapped in pcall() (safe even if FFI crashes)
--
-- DESIGN NOTES:
--   - Capability probe: directly tests if ctrl 143 works (not version-based)
--   - Scratch context: creates temporary SSL_CTX/SSL for testing, frees immediately
--   - Return value: 1 = capable, 0 = unsupported, nil = probe error → treated as false
--   - Error-safe: pcall wraps entire probe (crashes don't kill handshake)
--   - Used by: multi-staple initialization to decide attach strategy
--   - Fleet coordination: worker publishes capability via .multi_staple_attach.d file
--     (MIN across fleet decides if intermediates can be stapled)
--
-- RELATED:
--   - ssl_ffi() — loads FFI bindings
--   - multi_staple_worker_id() — used for vote file naming
--   - SSL_CTRL_SET_TLSEXT_STATUS_REQ_OCSP_RESP_EX = 143 (from OpenSSL headers)
--
-- ============================================================================
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
local _free_resp_cast = nil -- cached ffi.cast of OCSP_RESPONSE_free (one per worker)

-- ============================================================================
-- MULTI_STAPLE_WORKER_ID()
-- ============================================================================
-- PURPOSE:
--   Generates a unique worker identifier for multi-staple capability voting.
--   Used as colony vote filename to aggregate worker capability across fleet.
--
-- RETURNS:
--   (string): unique identifier "host_tag-pid-wid" (e.g., "abc123...-1234-0")
--
-- SIDE EFFECTS:
--   - Reads: os.getenv("HOSTNAME"), os.getenv("HOST"), ngx.worker.pid(), ngx.worker.id()
--   - Calls: digest library (SHA256) or ngx.crc32_long for host hashing
--   - Caching: memoized in _multi_staple_worker_id on first call
--   - Performance: ~1-2ms on first call (hash + FFI), O(1) on subsequent calls
--
-- DESIGN NOTES:
--   - Host tag: SHA256(HOSTNAME)[0..16] hex, fallback to CRC32 if digest unavailable
--   - Uniqueness: hash[16] + "-" + pid + "-" + wid prevents name collisions
--   - Collision avoidance: full host hash used (not truncated) to separate long-name-prefix pods
--   - PID/WID: captures both process ID and nginx worker ID for redundancy
--   - Memoization: first call computes, subsequent calls return cached value
--   - Used by: vote file naming in .multi_staple_attach.d/ directory
--   - Purpose: allows independent per-worker capability voting (MIN aggregation)
--
-- RELATED:
--   - prune_stale_multi_staple_votes() — removes old vote files
--   - MULTI_STAPLE_ATTACH_DIR — directory for vote files
--   - colony_multi_staple_min() — aggregates votes across workers
--
-- ============================================================================
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

-- ============================================================================
-- PRUNE_STALE_MULTI_STAPLE_VOTES(now)
-- ============================================================================
-- PURPOSE:
--   Removes stale worker capability votes and orphaned temp files from the
--   multi-staple voting directory. Called by publish path only (not readers).
--
-- PARAMETERS:
--   now (number|nil): current unix time (defaults to ngx.now() if omitted)
--
-- RETURNS:
--   (nil): no return value; side effect only
--
-- SIDE EFFECTS:
--   - Reads: directory MULTI_STAPLE_ATTACH_DIR, file modification times
--   - Writes: deletes files older than MULTI_STAPLE_WORKER_TTL (120 seconds)
--   - Performance: O(n) where n = number of vote files (typically < 10)
--   - Error resilience: entire operation wrapped in pcall() (lfs failures non-fatal)
--
-- DESIGN NOTES:
--   - TTL: MULTI_STAPLE_WORKER_TTL = 120 seconds (workers refresh periodically)
--   - File removal: age-based eviction (stale live votes + crashed temp files)
--   - Temp files: *.tmp.* files expire just like regular votes (same mechanism)
--   - Reader-writer safety: publish path only; readers must not unlink (race prevention)
--   - Default time: if now omitted, uses ngx.now() (handles both stream + http)
--   - Safe-to-call: pcall wraps lfs operations (missing dir, permissions don't crash)
--   - Used by: publish-path functions (e.g., colony_multi_staple_min setter)
--
-- RELATED:
--   - multi_staple_worker_id() — generates vote filenames to be pruned
--   - colony_multi_staple_min() — reads votes to aggregate capability
--   - MULTI_STAPLE_WORKER_TTL — age threshold (120 seconds)
--   - MULTI_STAPLE_ATTACH_DIR — directory scanned
--
-- ============================================================================
-- Drop worker votes older than MULTI_STAPLE_WORKER_TTL, and orphan publish temps
-- (*.tmp.*) that crashed mid-write. Publish-only: the handshake read path must
-- not unlink files (a reader racing a writer must not delete a peer's vote).
local function prune_stale_multi_staple_votes(now)
	pcall(function()
		local lfs = require "lfs"
		if lfs.attributes(MULTI_STAPLE_ATTACH_DIR, "mode") ~= "directory" then
			return
		end
		now = now or ngx.now()
		for name in lfs.dir(MULTI_STAPLE_ATTACH_DIR) do
			if name ~= "." and name ~= ".." then
				local path = MULTI_STAPLE_ATTACH_DIR .. "/" .. name
				local mtime = lfs.attributes(path, "modification")
				local stale = type(mtime) == "number" and (now - mtime) > MULTI_STAPLE_WORKER_TTL
				if stale then
					-- Live votes and crashed mid-write temps both expire by age.
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
-- ============================================================================
-- COLONY_MULTI_STAPLE_MIN()
-- ============================================================================
-- PURPOSE:
--   Aggregates multi-staple capability votes across all live workers in the
--   fleet. Returns fleet-wide consensus via MIN logic (any "0" or invalid
--   vote forces leaf-only).
--
-- RETURNS:
--   (boolean): true if all live votes are "1" (multi-staple ready)
--   (boolean): false if any live vote is "0" or invalid (leaf-only fallback)
--   (nil): if no live votes found (no workers publishing yet)
--
-- SIDE EFFECTS:
--   - Reads: directory MULTI_STAPLE_ATTACH_DIR, vote files and modification times
--   - Calls: lfs.dir, io.open, file reading
--   - Performance: O(n) where n ≤ 10 live workers (typically < 5ms)
--   - Error resilience: entire operation wrapped in pcall() (lfs/io failures safe)
--
-- DESIGN NOTES:
--   - MIN aggregation: any "0" or unreadable vote → false (fail-closed)
--   - Live detection: file age checked against MULTI_STAPLE_WORKER_TTL (120s)
--   - Invalid handling: torn/garbage votes treated as "0" (forces leaf-only)
--   - Temp file skip: *.tmp.* files ignored (mid-write drafts not counted)
--   - Atomic reads: each vote file read fresh (not cached in this function)
--   - Purpose: ocsp.lua uses this to decide inter-request attachment strategy
--   - Return nil: when no workers publishing (fleet cold start)
--
-- RELATED:
--   - publish_multi_staple_attach() — publishes this worker's vote
--   - openssl_multi_staple_ready() — combines with probe result
--   - prune_stale_multi_staple_votes() — removes aged votes before reading
--
-- ============================================================================
-- attach multi-staple while a peer's vote is unreadable. Any such invalid live
-- vote forces leaf-only even when other live votes are "1" (MIN, not majority).
local function colony_multi_staple_min()
	local found_zero = false
	local found_one = false
	local found_invalid = false
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
						local bit = raw:sub(1, 1)
						if bit == "0" then
							found_zero = true
						elseif bit == "1" then
							found_one = true
						else
							found_invalid = true
						end
					end
				end
			end
		end
	end)
	if not live then
		return nil
	end
	-- Any live "0" or unreadable/torn vote → leaf-only (colony MIN).
	if found_zero or found_invalid then
		return false
	end
	if found_one then
		return true
	end
	return false
end

-- ============================================================================
-- PUBLISH_MULTI_STAPLE_ATTACH(ready, force)
-- ============================================================================
-- PURPOSE:
--   Publishes this worker's multi-staple capability vote and updates the fleet
--   aggregate file. Implements rate-limited heartbeating to keep votes alive
--   across TTL windows.
--
-- PARAMETERS:
--   ready (boolean): this worker's capability (true = multi-staple ready)
--   force (boolean|nil): when true, bypass rate limit and publish immediately
--
-- RETURNS:
--   (boolean): true if vote successfully written/heartbeat (mtime refreshed)
--   (boolean): false if write failed (vote file not updated)
--
-- SIDE EFFECTS:
--   - Reads: global _multi_staple_last_publish, worker ID, colony MIN state
--   - Writes: worker vote file (.multi_staple_attach.d/{wid}), aggregate marker
--   - Calls: multi_staple_worker_id(), colony_multi_staple_min()
--   - File I/O: atomic rename to avoid torn-write races
--   - Performance: ~1-2ms on actual publish, O(1) on rate-limited heartbeat
--
-- DESIGN NOTES:
--   - Rate limiting: MULTI_STAPLE_PUBLISH_INTERVAL = 15 seconds (throttle hot paths)
--   - Heartbeat: skipped publishes still refresh vote mtime (prevents TTL expiry)
--   - Atomic writes: uses atomic rename (tmp → final) to prevent torn reads
--   - Aggregate update: recalculates fleet MIN and writes .multi_staple_attach marker
--   - Fallback: orphaned temp files (*.tmp.*) auto-expire after TTL
--   - Used by: openssl_multi_staple_ready() during cache warmth/probe phases
--   - Return value: true = vote active, false = write failed (use leaf-only)
--
-- RELATED:
--   - colony_multi_staple_min() — reads aggregated votes
--   - multi_staple_worker_id() — generates vote filename
--   - prune_stale_multi_staple_votes() — removes aged votes before aggregation
--
-- ============================================================================
-- Publish this worker's multi-staple vote and refresh the aggregate colony marker.
-- Aggregate is the live MIN (any "0" wins), not last-writer-wins.
-- Returns true when this worker's vote file landed (or a rate-limited skip kept a
-- prior vote alive via mtime heartbeat). false → caller must not claim multi-ready.
local function publish_multi_staple_attach(ready, force)
	local now = ngx.now()
	local wid = multi_staple_worker_id()
	local worker_path = MULTI_STAPLE_ATTACH_DIR .. "/" .. wid
	if not force and (now - _multi_staple_last_publish) < MULTI_STAPLE_PUBLISH_INTERVAL then
		-- Heartbeat: refresh vote mtime even when the bit matches the colony MIN,
		-- so a matched-true worker does not age out under TTL while still live.
		-- Atomic rename (same as full publish) — truncate-in-place can tear-read as
		-- empty/garbage and briefly trip the invalid-vote leaf-only gate.
		local ok_hb = false
		pcall(function()
			local wtmp = worker_path .. ".tmp." .. tostring(ngx.worker.id() or 0)
			local wf = io.open(wtmp, "w")
			if not wf then
				return
			end
			wf:write(ready and "1\n" or "0\n")
			wf:close()
			if os.rename(wtmp, worker_path) then
				ok_hb = true
			else
				os.remove(wtmp)
			end
		end)
		if ok_hb then
			return true
		end
		-- No vote file yet (or dir missing): fall through to a full publish.
	end
	_multi_staple_last_publish = now
	prune_stale_multi_staple_votes(now)
	local published = false
	pcall(function()
		local lfs = require "lfs"
		lfs.mkdir("/var/cache/bunkerweb/ssl")
		lfs.mkdir(MULTI_STAPLE_ATTACH_DIR)
		local wtmp = worker_path .. ".tmp." .. tostring(ngx.worker.id() or 0)
		local wf = io.open(wtmp, "w")
		if not wf then
			return
		end
		wf:write(ready and "1\n" or "0\n")
		wf:close()
		local ok_r = os.rename(wtmp, worker_path)
		if not ok_r then
			os.remove(wtmp)
			return
		end
		published = true

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
		if not os.rename(tmp, MULTI_STAPLE_ATTACH_PATH) then
			os.remove(tmp)
		end
	end)
	return published
end

-- True when this worker can multi-staple AND the colony MIN allows it.
-- Probes SSL_ctrl 143 once, publishes the vote, then still fails closed with
-- ============================================================================
-- openssl_multi_staple_ready()
-- ============================================================================
-- PURPOSE:
--   Probe OpenSSL multi-staple capability (SSL_CTRL 143) and publish worker vote.
--   Returns capability + colony MIN consensus (leaf-only if any peer can't multi-staple).
--
-- PARAMETERS:
--   None. Uses worker-local state + disk colony vote.
--
-- RETURNS:
--   (ok, ffi_state, why_not):
--     ok (boolean): true if multi-staple ready for this handshake
--     ffi_state: SSL_CTX FFI handle if multi-ready, nil otherwise
--     why_not (string|nil): reason if not ready: "libssl", "colony", nil
--
-- SIDE EFFECTS:
--   - Probes: OpenSSL FFI SSL_ctrl(143) once per worker (latched)
--   - Publishes: Worker vote to /var/cache/bunkerweb/ssl/ocsp-multi-staple-attach
--   - Reads: Colony MIN from disk (live peer votes)
--   - Logs: None (silent probing)
--   - State: Latches _multi_staple_state, _ssl_ffi per worker
--   - Performance: O(1) after first call (state latched)
--
-- DESIGN NOTES:
--   - Capability probe: SSL_ctrl(143) to detect OpenSSL 3.6+ (multi-staple support)
--   - Sticky false: Latches false on OOM/failure (cleared by refresh_multi_staple_vote)
--   - Colony MIN: Any peer leaf-only = entire fleet must be leaf-only
--   - Vote publishing: Publishes capability bit to colony consensus file
--   - Rate limit: Skips publish if state unchanged (15s cooldown)
--   - Force publish: On reload/peer flip (capability change)
--   - Called by: attach_ocsp_staple() to decide leaf-only vs multi-staple
--
-- RELATED:
--   - probe_multi_staple_ctrl() FFI SSL_ctrl(143) wrapper
--   - colony_multi_staple_min() reads consensus from disk
--   - publish_multi_staple_attach() writes worker vote
--   - refresh_multi_staple_vote() clears sticky state for warmer
--
-- ============================================================================
-- why_not="colony" while any live peer is leaf-only.
local function openssl_multi_staple_ready()
	-- Local capability probe (publishes this worker's vote). Colony min may still force
	-- leaf-only while any live peer cannot attach — even if this worker is 3.6+.
	local function finish_local(local_ok)
		if not local_ok then
			return false, nil, "libssl"
		end
		local colony = colony_multi_staple_min()
		-- false covers a live "0" and any live vote that is neither "0" nor "1"
		-- (including when other peers voted "1" — colony MIN, not majority).
		-- nil (no live markers yet) does not block this worker.
		if colony == false then
			return false, nil, "colony"
		end
		return true, _multi_staple_state, nil
	end
	if _multi_staple_state ~= nil then
		local local_ok = _multi_staple_state ~= false
		-- Bypass the 15s rate-limit when our capability disagrees with the live MIN
		-- (reload / peer flip window where attach and disk would otherwise diverge).
		local colony = colony_multi_staple_min()
		local force = (local_ok and colony == false) or ((not local_ok) and colony == true)
		if not publish_multi_staple_attach(local_ok, force) then
			-- Vote never landed: do not claim multi-ready with a blind colony.
			if local_ok then
				return false, nil, "colony"
			end
		end
		return finish_local(local_ok)
	end
	local st = ssl_ffi()
	if not st or not probe_multi_staple_ctrl() then
		_multi_staple_state = false
		publish_multi_staple_attach(false, true)
		return false, nil, "libssl"
	end
	-- Capability proven; only latch multi-ready state after the vote file lands.
	if not publish_multi_staple_attach(true, true) then
		return false, nil, "colony"
	end
	_multi_staple_state = st
	return finish_local(true)
end

-- ============================================================================
-- REFRESH_MULTI_STAPLE_VOTE()
-- ============================================================================
-- PURPOSE:
--   Warmer tick function: clears sticky false states and re-probes multi-staple
--   capability. Prevents permanent leaf-only fallback after transient failures
--   (OOM, SSL_CTX creation race).
--
-- RETURNS:
--   (nil): no return value; side effect only
--
-- SIDE EFFECTS:
--   - Reads: global _multi_staple_state, _ssl_ffi
--   - Writes: clears _multi_staple_state = nil, _ssl_ffi = nil, _free_resp_cast = nil
--   - Calls: openssl_multi_staple_ready() for re-probe
--   - Performance: O(1) (state reset) + re-probe cost (~5-10ms first call)
--
-- DESIGN NOTES:
--   - Sticky false reset: latched false states cleared (allows retry on warmer tick)
--   - Without reset: transient OOM/failure would block multi-staple until worker recycle
--   - Periodic called: warmer job runs regularly, keeps capability fresh
--   - Re-probe: openssl_multi_staple_ready() called after reset (full probe again)
--   - FFI cache: _ssl_ffi=nil also cleared (forces re-load of FFI declarations)
--   - Resp cast: _free_resp_cast=nil ensures fresh cast lookup
--   - State scope: _multi_staple_state module-local (warmer knows to call this)
--   - Used by: ocsp_warmer.lua to periodically refresh capability
--
-- RELATED:
--   - openssl_multi_staple_ready() — re-called after state reset
--   - ssl_ffi() — re-loaded when _ssl_ffi reset to nil
--   - ocsp_warmer.lua — calls during periodic warmth ticks
--
-- ============================================================================
-- Warmer tick: refresh this worker's colony vote.
-- Latched false (OOM / scratch SSL_CTX failure) and latched _ssl_ffi=false are
-- cleared so a later warmer can re-probe — sticky false forever would page every
-- Must-Staple handshake until recycle.
-- Lives here because _multi_staple_state is this module's mutable state.
local function refresh_multi_staple_vote()
	if _multi_staple_state == false then
		_multi_staple_state = nil
	end
	if _ssl_ffi == false then
		_ssl_ffi = nil
		_free_resp_cast = nil
	end
	openssl_multi_staple_ready()
end

-- Per-tenant control key for intermediate OCSP negatives (must match Python
-- ============================================================================
-- INTERMEDIATE_CONTROL_FP(leaf_pem, inter_pem)
-- ============================================================================
-- PURPOSE:
--   Generates per-tenant control key for intermediate OCSP negatives (refuse,
--   tombstone, blacklist, floor). Prevents one leaf's deny-list from affecting
--   other sites on the same intermediate CA.
--
-- PARAMETERS:
--   leaf_pem (string): leaf certificate in PEM format
--   inter_pem (string): intermediate certificate in PEM format
--
-- RETURNS:
--   (string): 64-char hex SHA256 of (leaf_spki:inter_spki)
--   (nil): if either certificate SPKI unreadable or FFI error
--
-- SIDE EFFECTS:
--   - Reads: spki_fingerprint() for both certs
--   - Calls: digest library (SHA256) via pcall
--   - Performance: ~1-2ms (FFI + two SPKI lookups)
--
-- DESIGN NOTES:
--   - Tenant isolation: key = SHA256(leaf_fp + ":" + inter_fp)
--   - Per-leaf negatives: stored under control_fp (not shared SPKI)
--   - Scope: limits deny-list to specific leaf+intermediate pair
--   - Error resilience: pcall wraps digest call (non-fatal on FFI crash)
--   - Used by: load_paged_intermediate_staple() for tenant-gated access
--
-- RELATED:
--   - spki_fingerprint() — extracts leaf and intermediate fingerprints
--   - load_paged_intermediate_staple() — uses control_fp for gating
--
-- ============================================================================
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

-- ============================================================================
-- LOAD_PAGED_INTERMEDIATE_STAPLE(cert_pem, leaf_pem)
-- ============================================================================
-- PURPOSE:
--   Loads intermediate OCSP DER from canary-paged cache, applying tenant-scoped
--   negative gates (refuse, tombstone, blacklist, floor). Fails closed when
--   tenant control key cannot be derived.
--
-- PARAMETERS:
--   cert_pem (string): intermediate certificate in PEM format
--   leaf_pem (string|nil): leaf cert for tenant scoping (optional)
--
-- RETURNS:
--   (string, string|nil): (der, body_fp) if found and accessible
--     - der: OCSP response DER bytes (binary)
--     - body_fp: intermediate SPKI fingerprint (for tracking)
--   (nil, body_fp): if body blocked by negative gate (still returns body_fp)
--   (nil, nil): if intermediate SPKI unreadable
--
-- SIDE EFFECTS:
--   - Reads: spki_fingerprint(), ocsp.json metadata, tenant control gates
--   - Calls: read_ocsp_json(), meta_tombstoned(), peer_refuse_blocks()
--   - Performance: ~1-3ms (metadata lookup + gate checks)
--
-- DESIGN NOTES:
--   - Tenant gating: leaf_pem required for applying negative gates
--   - Fail closed: if leaf provided but control_fp missing, returns nil
--   - Prevents drift: blocks shared DER if tenant's refuse/tombstone applied
--   - Body SPKI level: floor checks live on body, not control key
--   - Paging: canary-paged DER (may not be present, that's OK)
--   - Used by: collect_chain_staple_ders() for multi-staple DER list building
--
-- RELATED:
--   - intermediate_control_fp() — generates tenant control key
--   - read_ocsp_json() — loads metadata shards
--   - meta_tombstoned() — checks negative tombstone gate
--   - peer_refuse_blocks() — checks peer refuse gate
--
-- ============================================================================
-- Load a canary-paged, still-fresh OCSP DER for an intermediate SPKI (or nil).
-- Negatives (tombstone / peer-refuse / serial-blacklist / floor) are checked on
-- the tenant control key when leaf_pem is provided — never on the shared SPKI alone.
-- When leaf_pem is provided but control_fp cannot be derived, refuse the shared
-- body (fail closed) — serving CA-shared DER without tenant gates would let one
-- leaf's refuse be invisible to another site on the same intermediate.
local function load_paged_intermediate_staple(cert_pem, leaf_pem)
	local body_fp = spki_fingerprint(cert_pem)
	if not body_fp then
		return nil, nil
	end
	local control_fp = nil
	if type(leaf_pem) == "string" and leaf_pem ~= "" then
		control_fp = intermediate_control_fp(leaf_pem, cert_pem)
		if not control_fp then
			return nil, body_fp
		end
	end
	if control_fp then
		local cmeta = read_ocsp_json(control_fp)
		if meta_tombstoned(cmeta, control_fp) then
			return nil, body_fp
		end
		if peer_refuse_blocks(control_fp, cmeta, nil, true) then
			return nil, body_fp
		end
		-- Control shards are negative-only (no this_update_unix); floor lives on body SPKI.
	end
	local meta = read_ocsp_json(body_fp)
	if not meta or meta_tombstoned(meta, body_fp) or shard_not_paged(meta, body_fp) then
		return nil, body_fp
	end
	-- Body SPKI floor vs body this_update (job advances floor on body publish).
	if cluster_floor_blocks(body_fp, meta) then
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

-- ============================================================================
-- chain_has_intermediate_must_staple(chain_blocks)
-- ============================================================================
-- PURPOSE:
--   Check if any intermediate in chain requires Must-Staple OCSP attachment.
--   Gate for refusing leaf-only when Must-Staple intermediate present.
--
-- PARAMETERS:
--   chain_blocks (table): PEM array from issuer_linked_chain_blocks
--
-- RETURNS:
--   (boolean): true if any intermediate (not leaf, not root) has Must-Staple
--   (boolean): false if no intermediates or none have Must-Staple
--
-- SIDE EFFECTS:
--   - Calls: cert_must_staple_bool() for each intermediate (fail-closed)
--   - Uses: chain_blocks.trust_anchor_index for early exit (Optimization #2)
--   - Performance: O(n) worst case, ~1ms typical
--
-- DESIGN NOTES:
--   - Non-root only: Skips root (self-signed) and leaf in loop
--   - Early exit: Uses cached trust_anchor_index to skip below root
--   - Fail-closed: cert_must_staple_bool(..., true) treats unknown as Must-Staple
--   - Single oracle: Same detector as collect_chain_staple_ders (no drift)
--   - Called by: issuer_path_intermediate_ready, attach_ocsp_staple
--   - Related: issuer_path_null_slots counts missing intermediates
--
-- RELATED:
--   - cert_must_staple_bool() Must-Staple detector
--   - collect_chain_staple_ders() collects OCSP DERs for multi-staple
--   - issuer_path_intermediate_ready() readiness check using this
--
-- ============================================================================
-- True when any non-root chain cert carries Must-Staple.
-- ============================================================================
-- CHAIN_HAS_INTERMEDIATE_MUST_staple(chain_blocks)
-- ============================================================================
-- PURPOSE:
--   Detects whether any intermediate in a certificate chain has Must-Staple
--   requirement. Used to gate multi-staple attachment and handle failures
--   when intermediates cannot be stapled.
--
-- PARAMETERS:
--   chain_blocks (table): certificate chain array with trust_anchor_index metadata
--                         [1] = leaf, [2..n] = intermediates/root
--
-- RETURNS:
--   (boolean): true if any intermediate (except trust anchor) has Must-Staple
--   (boolean): false if no Must-Staple intermediates or chain too short
--
-- SIDE EFFECTS:
--   - Reads: chain_blocks array, trust_anchor_index metadata
--   - Calls: cert_must_staple_bool() for each intermediate
--   - Performance: O(n) where n = intermediates (max ~10), ~1-10ms
--
-- DESIGN NOTES:
--   - Scope: intermediates only (indices 2 to trust_anchor_index - 1)
--   - Early exit: skips trust anchor (self-signed, never stapled)
--   - Optimization: uses trust_anchor_index cache (avoids duplicate detect)
--   - Single oracle: cert_must_staple_bool(pem, true) used (consistent detector)
--   - Purpose: determines if multi-staple is required/possible for this chain
--   - Used by: multi-staple attachment decision, error handling
--
-- RELATED:
--   - cert_must_staple_bool() — per-cert Must-Staple detector
--   - issuer_linked_chain_blocks() — builds this chain structure
--   - collect_chain_staple_ders() — uses to enforce intermediate stapling
--
-- ============================================================================
-- Single fail-closed oracle: cert_must_staple_bool(pem, true) — same detector as
-- collect_chain_staple_ders / issuer_path body checks (no parallel TLS/meta walk).
local function chain_has_intermediate_must_staple(chain_blocks)
	if type(chain_blocks) ~= "table" or #chain_blocks < 2 then
		return false
	end
	-- Use cached trust_anchor_index for early exit (optimization #2)
	local anchor_idx = tonumber(chain_blocks.trust_anchor_index)
	local loop_end = anchor_idx and (anchor_idx - 1) or #chain_blocks
	for i = 2, loop_end do
		local pem = chain_blocks[i]
		if cert_must_staple_bool(pem, true) then
			return true
		end
	end
	return false
end

-- ============================================================================
-- COLLECT_CHAIN_STAPLE_DERS(leaf_resp, chain_blocks)
-- ============================================================================
-- PURPOSE:
--   Builds Certificate-message-ordered OCSP DER array for multi-staple: leaf
--   response followed by each intermediate's OCSP DER (or nil for missing).
--
-- PARAMETERS:
--   leaf_resp (string): leaf OCSP response DER bytes
--   chain_blocks (table): issuer-linked chain from issuer_linked_chain_blocks
--
-- RETURNS:
--   (table, nil): array of DER bytes + nil slots (success multi-staple ready)
--   (nil, string, string): (nil, reason, detail) on failure:
--     - ("unmet", nil): leaf_resp missing/empty
--     - ("must_staple", "response_not_found"): intermediate Must-Staple missing DER
--
-- SIDE EFFECTS:
--   - Reads: chain_blocks, trust_anchor_index
--   - Calls: cert_must_staple_bool(), load_paged_intermediate_staple()
--   - Performance: O(n) where n = intermediates, ~1-5ms
--
-- DESIGN NOTES:
--   - Leaf-first: ders[1] = leaf_resp (required for RFC 6961)
--   - NULL slots: ders[i] = false for missing intermediates (OpenSSL omits)
--   - Must-Staple gate: missing GOOD body with Must-Staple = refuse (safety)
--   - Early exit: uses trust_anchor_index to skip root
--   - Order preservation: matches certificate chain order (critical for OpenSSL)
--   - Call guard: only when openssl_multi_staple_ready() returns true
--   - Used by: attach_ocsp_staple() for FFI staple array building
--
-- RELATED:
--   - openssl_multi_staple_ready() — guards this call
--   - load_paged_intermediate_staple() — fetches intermediate OCSP
--   - chain_has_intermediate_must_staple() — pre-check for Must-Staple
--
-- ============================================================================
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
	-- Use cached trust_anchor_index for early exit (optimization #2)
	local anchor_idx = tonumber(chain_blocks.trust_anchor_index)
	local loop_end = anchor_idx and (anchor_idx - 1) or #chain_blocks
	for i = 2, loop_end do
		local pem = chain_blocks[i]
		local inter_must = cert_must_staple_bool(pem, true)
		local der = load_paged_intermediate_staple(pem, leaf_pem)
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

-- ============================================================================
-- NOTE_MULTI_STAPLE_ATTACH(entries, null_slots)
-- ============================================================================
-- PURPOSE:
--   Records multi-staple stack shape (entries + NULL slots) in ngx.ctx for
--   OCSP_STAPLED audit and debugging (which intermediates were included/omitted).
--
-- PARAMETERS:
--   entries (number|nil): total CertificateEntry count in multi-staple stack
--   null_slots (number|nil): count of NULL slots (missing intermediates)
--
-- RETURNS:
--   (nil): no return value; side effect only
--
-- SIDE EFFECTS:
--   - Reads: ngx.ctx availability
--   - Writes: ngx.ctx.bw_ocsp_multi_entries, ngx.ctx.bw_ocsp_multi_stapled,
--            ngx.ctx.bw_ocsp_multi_null_slots (or clears if n < 1)
--   - Performance: O(1) table assignment
--
-- DESIGN NOTES:
--   - Context only: does nothing if ngx.ctx unavailable (silent)
--   - Clear behavior: n < 1 clears all multi-staple context fields
--   - Audit value: bw_ocsp_multi_stapled = entries - null_slots (OCSP count)
--   - NULL legal: null_slots indicates missing-but-OK intermediates (per RFC)
--   - Used by: attach_ocsp_staple() to record attachment results
--   - Related: clear_multi_staple_attach_note() for bulk clearing
--
-- RELATED:
--   - clear_multi_staple_attach_note() — clears via note_multi_staple_attach(0, 0)
--   - attach_ocsp_staple() — calls after multi-staple or error
--
-- ============================================================================
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

-- ============================================================================
-- CLEAR_MULTI_STAPLE_ATTACH_NOTE()
-- ============================================================================
-- PURPOSE:
--   Clears multi-staple context fields when attachment failed or was refused.
--   Wrapper around note_multi_staple_attach(0, 0) for clarity.
--
-- RETURNS:
--   (nil): no return value; side effect only
--
-- SIDE EFFECTS:
--   - Calls: note_multi_staple_attach(0, 0)
--   - Clears: ngx.ctx.bw_ocsp_multi_entries, bw_ocsp_multi_stapled, bw_ocsp_multi_null_slots
--   - Performance: O(1)
--
-- DESIGN NOTES:
--   - Simple wrapper: delegates to note_multi_staple_attach with 0 entries
--   - Used for: error paths, attachment refusals, early exits
--   - Context awareness: silently no-op if ngx.ctx unavailable
--   - Audit cleanup: ensures no stale multi-staple fields on error paths
--
-- RELATED:
--   - note_multi_staple_attach() — underlying implementation
--   - attach_ocsp_staple() — calls on various error paths
--
-- ============================================================================
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
		local ok_leaf = ocsp.set_ocsp_status_resp(leaf_resp)
		if ok_leaf then
			note_connection_staple(spki_fingerprint(chain_blocks and chain_blocks[1]))
		end
		return ok_leaf
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
		local ok_leaf = ocsp.set_ocsp_status_resp(leaf_resp)
		if ok_leaf then
			note_connection_staple(spki_fingerprint(chain_blocks and chain_blocks[1]))
		end
		return ok_leaf
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
		local ok_leaf = ocsp.set_ocsp_status_resp(leaf_resp)
		if ok_leaf then
			note_connection_staple(spki_fingerprint(chain_blocks and chain_blocks[1]))
		end
		return ok_leaf
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
	-- One cast per worker — fresh ffi.cast on every attach leaks cdata under load.
	if not _free_resp_cast then
		_free_resp_cast = ffi.cast("void (*)(void *)", C.OCSP_RESPONSE_free)
	end
	local free_resp = _free_resp_cast
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

	-- Cardinality check: nil NULL-slot pushes must not desync staples onto the wrong
	-- CertificateEntry. Refuse rather than silently mis-staple.
	local sk_num = -1
	pcall(function()
		sk_num = tonumber(C.OPENSSL_sk_num(stack)) or -1
	end)
	if sk_num ~= #ders then
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
	note_connection_staple(spki_fingerprint(chain_blocks and chain_blocks[1]))
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
-- Leaf: SSL_ctrl 71 with NULL. Multi: SSL_ctrl 143 with NULL when this connection
-- previously attached a multi stack (ngx.ctx.bw_ocsp_multi_entries) OR this worker's
-- probe proved ctrl 143 — so clear_certs / context swap cannot leave leaf A's
-- CertificateEntry stack on leaf B after a never-probed / state-reset worker.
-- ============================================================================
-- clear_connection_staple()
-- ============================================================================
-- PURPOSE:
--   Drop OCSP staples from connection (SSL_ctrl clear for slots 71 + 143).
--   Called on SSL context swap to prevent leaf A's staple landing on leaf B.
--
-- PARAMETERS:
--   None. Operates on ngx.ctx.bw_ocsp_* state and FFI SSL connection.
--
-- RETURNS:
--   (boolean): true if both leaf + multi slots cleared successfully
--   (boolean): false if either clear failed or FFI unavailable
--
-- SIDE EFFECTS:
--   - FFI calls: SSL_ctrl(71) for leaf slot, SSL_ctrl(143) for multi slot
--   - Clears: ngx.ctx.bw_ocsp_stapled_fp, bw_ocsp_multi_* entries
--   - Logs: DEBUG on successful clear, no log on failure
--   - Performance: O(1) FFI call, ~0.1ms
--
-- DESIGN NOTES:
--   - Context swap: Called on HTTP/2 coalescing, plugin re-entry
--   - Slot clearing: Both SSL_ctrl 71 (leaf) and 143 (multi) must succeed
--   - Fail-safe: If EX clear fails, kept had_multi for retry on next swap
--   - Idempotent: Multiple calls safe (ctx state nulled after success)
--   - Preventing pollution: Staple from prior connection must not leak
--   - Called by: SSL context lifecycle hooks
--   - Related: attach_ocsp_staple sets staples, this clears them
--
-- RELATED:
--   - attach_ocsp_staple() sets both staple slots
--   - SSL_CTRL_SET_TLSEXT_STATUS_REQ_OCSP_RESP (71) for leaf
--   - SSL_CTRL_SET_TLSEXT_STATUS_REQ_OCSP_RESP_EX (143) for multi
--
-- ============================================================================
-- SSL_certs_clear does not clear either staple slot.
-- Ctx notes are wiped only after clear succeeds — a failed EX clear must leave
-- had_multi so a later swap can retry apoptosis.
-- Assigns the forward-declared local so attach_ocsp_staple's refuse_or_leaf_only sees it.
clear_connection_staple = function()
	local prev = ngx.ctx and ngx.ctx.bw_ocsp_stapled_fp or nil
	local had_multi = ngx.ctx and (tonumber(ngx.ctx.bw_ocsp_multi_entries) or 0) > 0
	local ok_leaf = false
	local ok_ex = not had_multi and type(_multi_staple_state) ~= "table"
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
		ok_leaf = tonumber(st.C.SSL_ctrl(ptr, SSL_CTRL_SET_TLSEXT_STATUS_REQ_OCSP_RESP, 0, nil)) == 1
		if had_multi or type(_multi_staple_state) == "table" then
			ok_ex = tonumber(st.C.SSL_ctrl(ptr, SSL_CTRL_SET_TLSEXT_STATUS_REQ_OCSP_RESP_EX, 0, nil)) == 1
		else
			ok_ex = true
		end
	end)
	local ok_clear = ok_leaf and ok_ex
	if ok_clear and ngx.ctx then
		ngx.ctx.bw_ocsp_stapled_fp = nil
		ngx.ctx.bw_ocsp_multi_entries = nil
		ngx.ctx.bw_ocsp_multi_stapled = nil
		ngx.ctx.bw_ocsp_multi_null_slots = nil
	end
	if prev and ok_clear then
		log(
			ngx.DEBUG,
			"OCSP dropped connection staple on SSL context swap prev_fp=" .. tostring(prev):sub(1, 16) .. "..."
		)
	end
	return ok_clear
end

note_connection_staple = function(fp)
	if ngx.ctx and type(fp) == "string" and #fp == 64 then
		ngx.ctx.bw_ocsp_stapled_fp = fp
	end
end

-- Drop the connection staple (often set from L1) when clear_certs swaps the SSL context.
-- HTTP/2 coalescing / plugin re-entry must not leave leaf A's staple on leaf B.
-- Does not delete the process-wide L1 shared-dict entry (other connections still need it).
function _M.on_ssl_context_swap()
	return clear_connection_staple()
end

-- ============================================================================
-- pick_issuer_candidate(cands, _leaf_pem)
-- ============================================================================
-- PURPOSE:
--   Pick one issuer from candidates with same subject DN (cross-signs).
--   Rejects ambiguous (different SPKIs) to prevent wrong path selection.
--
-- PARAMETERS:
--   cands (table): array of candidate objects {pem, issuer, fp}
--   _leaf_pem (string): leaf PEM (for context, not directly used)
--
-- RETURNS:
--   (candidate): single candidate object if unique SPKI found
--   (nil): if ambiguous (multiple distinct SPKIs) or empty candidates
--
-- SIDE EFFECTS:
--   - Calls: spki_fingerprint() if .fp not pre-computed in candidates
--   - No reads/writes or state modification
--   - Performance: O(n) where n = candidates, ~0.5ms typical
--
-- DESIGN NOTES:
--   - Cross-sign handling: Same DN multiple SPKIs = ambiguous (fail-closed)
--   - SPKI optimization: Uses pre-computed fp if available (#1)
--   - Bag order ignored: Never take cands[1] as default
--   - Unique SPKI: If all candidates share one SPKI, return first one
--   - Early exit: First mismatch returns nil (stops chain walk)
--   - Canary danger: Single paged SPKI ≠ issuer-path proof (avoid steering)
--   - Called by: issuer_linked_chain_blocks() during chain walking
--   - Related: issuer_linked_chain_blocks() fails walk on nil return
--
-- RELATED:
--   - issuer_linked_chain_blocks() uses result to extend chain
--   - spki_fingerprint() extracts SPKI hash
--   - batch_spki_fingerprints() pre-computes for optimization
--
-- ============================================================================
-- Several bag PEMs can share one subject DN (cross-signs). Do not take cands[1]
-- (bag order). Prefer the unique SPKI; if keys differ, stop (ambiguous) — do not
-- steer onto the single canary-paged SPKI (paged DER ≠ issuer-path proof and
-- can pick the wrong cross-sign). Still ambiguous → nil so the caller stops the
-- walk instead of stapling the wrong path.
local function pick_issuer_candidate(cands, _leaf_pem)
	if type(cands) ~= "table" or #cands == 0 then
		return nil
	end
	if #cands == 1 then
		return cands[1]
	end
	local seen_fp = nil
	local unique = true
	for _, cand in ipairs(cands) do
		-- Use pre-computed SPKI if available, otherwise extract (SPKI-based optimization #1)
		local fp = (cand.fp ~= nil and cand.fp) or (cand and spki_fingerprint(cand.pem) or nil)
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
	-- Distinct SPKIs under one subject DN: fail closed (no staplable-only tiebreak).
	return nil
end

-- Ordered Certificate message for one leaf: leaf + issuer-linked intermediates only.
-- Drops off-path bag members (cross-signs, unused extras) so their Must-Staple cannot
-- fail-close a healthy leaf→issuer path (including after ClientHello sibling fallback).
-- If the leaf's issuer cannot be resolved in the bag, never restore the full bag —
-- that reintroduces "steer onto sibling, die on extra Must-Staple PEM". Keep
-- leaf-only (do not inject off-path non-MS bag PEMs as CertificateEntry hints).
--
-- ============================================================================
-- issuer_linked_chain_blocks(leaf_pem, intermediate_pems)
-- ============================================================================
-- PURPOSE:
--   Build issuer-linked chain: filters cert bag to verified path from leaf→trust.
--   Drops off-path certs + cross-signs, detects unresolved Must-Staple.
--
-- PARAMETERS:
--   leaf_pem (string): leaf certificate PEM
--   intermediate_pems (table): array of intermediate certificate PEMs (bag)
--
-- RETURNS:
--   (blocks_table, is_clean):
--     blocks: PEM array + trust_anchor_index + optional unresolved_must_staple flag
--     is_clean: true if fully resolved, false if unresolved/ambiguous/depth-capped
--
-- SIDE EFFECTS:
--   - Reads: Cert DN extraction via cert_subject_issuer_dns()
--   - Computes: SPKI fingerprints via batch_spki_fingerprints()
--   - Logs: ERR on ambiguous/unresolved, WARN on depth cap, DEBUG on off-path drop
--   - Performance: O(n*m) worst case (n=hops, m=bag size), ~2-4ms typical
--
-- DESIGN NOTES:
--   - Lazy SPKI/DN parsing: Only parse matched candidates (optimization #5)
--   - Chain walking: Follow issuer→subject links up to 8 hops (hop_cap)
--   - Ambiguity detection: Same DN multiple SPKIs = refuse ambiguous
--   - Trust anchor: Stop at self-signed cert (root)
--   - Depth cap: Walk stopped with resolvable issuer = unresolved_must_staple
--   - Must-Staple flag: Set if ANY dropped PEM has Must-Staple
--   - Used by: presentable_chain_blocks() caching wrapper
--   - Called by: Certificate presentation, staple attachment decision
--
-- RELATED:
--   - presentable_chain_blocks() caches this per-request
--   - pick_issuer_candidate() selects issuer from candidates
--   - cert_subject_issuer_dns() extracts DN pair
--   - batch_spki_fingerprints() computes SPKI set
--
-- ============================================================================
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
	-- Lazy certificate parsing for first-call optimization (optimization #5)
	-- Only parse intermediates when needed (pick_issuer_candidate), not upfront.
	-- This defers expensive DN extraction from batch to on-demand, reducing first-call latency.
	-- First call: only parse matched candidates (~0.5-1ms vs 2-4ms batch)
	-- Subsequent calls: use cache (cached at presentable_chain_blocks level)
	local spki_map = nil
	local spki_map_ready = false

	-- Lazy-init SPKI map only when first candidate is needed
	local function ensure_spki_map()
		if not spki_map_ready then
			spki_map = batch_spki_fingerprints(intermediate_pems)
			spki_map_ready = true
		end
		return spki_map
	end

	-- Lazy parsing: defer DN extraction until candidate matching
	for _, pem in ipairs(intermediate_pems) do
		if type(pem) == "string" and pem ~= "" then
			-- Store raw PEM references initially, parse on-demand in pick_issuer_candidate
			by_subject["__pending__"] = by_subject["__pending__"] or {}
			by_subject["__pending__"][#(by_subject["__pending__"] or {}) + 1] = pem
		end
	end

	-- Materialization function: parse DN and organize by subject on-demand
	local function materialize_by_subject()
		if by_subject["__pending__"] then
			local pending = by_subject["__pending__"]
			by_subject["__pending__"] = nil
			local spki_cache = ensure_spki_map()

			for _, pem in ipairs(pending) do
				local subj, iss = cert_subject_issuer_dns(pem)
				if subj and subj ~= "" then
					local list = by_subject[subj]
					if not list then
						list = {}
						by_subject[subj] = list
					end
					local fp = spki_cache[pem]
					list[#list + 1] = { pem = pem, issuer = iss, fp = fp }
				end
			end
		end
	end
	local _, current_issuer = cert_subject_issuer_dns(leaf_pem)
	local seen = {}
	local linked = 0
	local ambiguous = false
	local hop_cap = 8
	for _ = 1, hop_cap do
		if not current_issuer or current_issuer == "" then
			break
		end
		-- Lazy-materialize candidates on first access (optimization #5)
		materialize_by_subject()
		local cands = by_subject[current_issuer]
		if not cands or #cands == 0 then
			break
		end
		local pick = pick_issuer_candidate(cands, leaf_pem)
		if not pick then
			-- Distinct SPKIs under one DN: stop; do not guess cands[1].
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
		-- Use pre-computed SPKI (SPKI-based optimization #1)
		local fp = pick.fp or spki_fingerprint(pick.pem)
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
	-- Depth cap: walk stopped with a still-resolvable issuer → leftover PEMs
	-- (including Must-Staple) were silently truncated. Fail closed.
	local depth_capped = linked >= hop_cap
		and type(current_issuer) == "string"
		and current_issuer ~= ""
		and type(by_subject[current_issuer]) == "table"
		and #by_subject[current_issuer] > 0

	local function compute_trust_anchor_index()
		-- Compute and cache trust anchor position for early-exit optimization.
		-- Saves 3-6ms by avoiding redundant is_self_signed() checks in later loops.
		for i = 2, #blocks do
			if is_self_signed(blocks[i]) then
				return i
			end
		end
		return nil
	end

	local function count_unplaced_must()
		-- Optimized counting: build placed set only once (optimization #6)
		-- Early exit for depth_capped case: just need to know if ANY dropped has Must-Staple
		local placed = {}
		for i = 2, #blocks do
			placed[blocks[i]] = true
		end
		local dropped_must = 0
		for _, pem in ipairs(intermediate_pems) do
			if type(pem) == "string" and pem ~= "" and not placed[pem] then
				-- Skip self-signed trust anchors early (optimization #6)
				local subj, iss = cert_subject_issuer_dns(pem)
				if subj and iss and subj == iss then
					-- Self-signed: skip (trust anchor or root)
					goto continue
				end
				if cert_must_staple_bool(pem, true) then
					dropped_must = dropped_must + 1
					-- Early exit for depth_capped: only need to know if ANY dropped has MS
					if depth_capped and dropped_must >= 1 then
						break
					end
				end
				::continue::
			end
		end
		return dropped_must
	end

	if linked == 0 or ambiguous or depth_capped then
		-- Unresolved / ambiguous / depth-capped: never full-bag concat. Must-Staple
		-- extras are omitted from the Certificate message. linked==0 stays leaf-only
		-- (no off-path non-MS bag PEMs as CertificateEntry hints without issuer proof).
		local dropped_must = count_unplaced_must()
		if depth_capped and dropped_must < 1 then
			-- Still-resolvable hop past the cap even without a counted MS PEM.
			dropped_must = 1
		end
		if dropped_must > 0 then
			blocks.unresolved_must_staple = dropped_must
			-- Telemetry for depth-capped chains (optimization #6)
			if depth_capped then
				log(
					ngx.WARN,
					"OCSP depth cap: chain exceeded hop_cap="
						.. tostring(hop_cap)
						.. " linked="
						.. tostring(linked)
						.. " dropped_must="
						.. tostring(dropped_must)
						.. " — rare case, explicit depth cap by design"
				)
			end
			log(
				ngx.ERR,
				"OCSP unresolved issuer path: omitted "
					.. tostring(dropped_must)
					.. " Must-Staple bag PEM(s); presented_entries="
					.. tostring(#blocks)
					.. " ambiguous="
					.. tostring(ambiguous)
					.. " depth_capped="
					.. tostring(depth_capped)
					.. " — attach refuses leaf-only (issuer_unresolved_must_staple)"
			)
		end
		-- Strip any linked intermediates when linked==0 path had been filling hints;
		-- keep only the leaf for a fully unresolved issuer.
		if linked == 0 then
			blocks = { leaf_pem }
			if dropped_must > 0 then
				blocks.unresolved_must_staple = dropped_must
			end
		end
		blocks.trust_anchor_index = compute_trust_anchor_index()
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
	blocks.trust_anchor_index = compute_trust_anchor_index()
	return blocks, true
end

-- Concatenate issuer_linked_chain_blocks into one PEM string for set_cert.
-- Named fields (unresolved_must_staple) are NOT preserved in the PEM bytes —
-- callers that need the refuse flag must use issuer_linked_chain_blocks /
-- presentable_chain_blocks and pass the table into health/attach, not this PEM.
-- ============================================================================
-- NOTE_DEPLETED_PEM_UNRESOLVED(unresolved, leaf_pem) / CTX_UNRESOLVED_FOR_LEAF / RESTORE_CTX_UNRESOLVED
-- ============================================================================
-- PURPOSE:
--   Manage per-leaf unresolved Must-Staple counts in ngx.ctx across same-request
--   PEM re-parses. Prevents dual-cert sibling interference via SPKI-keyed storage.
--
-- FUNCTIONS:
--   note_depleted_pem_unresolved(unresolved, leaf_pem) — records count by leaf SPKI
--   ctx_unresolved_for_leaf(leaf_pem) — retrieves count for leaf
--   restore_ctx_unresolved(out, leaf_pem) — merges ctx count into output table
--
-- PARAMETERS:
--   unresolved (number): count of omitted Must-Staple intermediates (0 clears)
--   leaf_pem (string): leaf certificate to key by SPKI fingerprint
--   out (table): output table to receive unresolved_must_staple field
--
-- RETURNS:
--   note_depleted: (nil), side effect only
--   ctx_unresolved_for_leaf: (number|nil) stored unresolved count
--   restore_ctx_unresolved: (nil), modifies out table in-place
--
-- SIDE EFFECTS:
--   - Reads: ngx.ctx (may be unavailable)
--   - Writes: ngx.ctx.bw_ocsp_chain_unresolved_by_fp[spki_fingerprint]
--   - Performance: O(1) table operations
--
-- DESIGN NOTES:
--   - Scope: per-leaf by SPKI (dual-cert safe, prevents sibling cross-talk)
--   - Key format: leaf_fp → unresolved_count mapping
--   - Update logic: keeps maximum count (never downgrades)
--   - Clear: unresolved ≤ 0 removes entry (cleanup)
--   - Restore: merges ctx count into output, maximizing both
--   - Used by: presentable_chain_blocks for PEM re-parse flow
--
-- RELATED:
--   - spki_fingerprint() — derives leaf key
--   - issuer_linked_chain_blocks() — generates unresolved count
--   - presentable_chain_blocks() — calls all three functions
--
-- ============================================================================
-- When unresolved>0, stamps ngx.ctx keyed by leaf SPKI so a same-request
-- PEM→re-parse restores the count for that leaf only (dual-cert sibling safe).
local function note_depleted_pem_unresolved(unresolved, leaf_pem)
	if not ngx.ctx then
		return
	end
	local fp = type(leaf_pem) == "string" and spki_fingerprint(leaf_pem) or nil
	if not is_fp64(fp) then
		return
	end
	local by_fp = ngx.ctx.bw_ocsp_chain_unresolved_by_fp
	if type(by_fp) ~= "table" then
		by_fp = {}
		ngx.ctx.bw_ocsp_chain_unresolved_by_fp = by_fp
	end
	local u = tonumber(unresolved) or 0
	if u <= 0 then
		by_fp[fp] = nil
		return
	end
	local prev = tonumber(by_fp[fp]) or 0
	if u > prev then
		by_fp[fp] = u
	end
end

local function ctx_unresolved_for_leaf(leaf_pem)
	if not ngx.ctx then
		return nil
	end
	local by_fp = ngx.ctx.bw_ocsp_chain_unresolved_by_fp
	if type(by_fp) ~= "table" then
		return nil
	end
	local fp = type(leaf_pem) == "string" and spki_fingerprint(leaf_pem) or nil
	if not is_fp64(fp) then
		return nil
	end
	return tonumber(by_fp[fp])
end

local function restore_ctx_unresolved(out, leaf_pem)
	if type(out) ~= "table" then
		return
	end
	local ctx_u = ctx_unresolved_for_leaf(leaf_pem)
	if not ctx_u or ctx_u <= 0 then
		return
	end
	local cur = tonumber(out.unresolved_must_staple) or 0
	if ctx_u > cur then
		out.unresolved_must_staple = ctx_u
	end
end

-- ============================================================================
-- PRESENTABLE_CACHE_KEY(leaf_fp, blocks)
-- ============================================================================
-- PURPOSE:
--   Generates collision-resistant cache key for presentable chain per-request
--   caching. Includes leaf SPKI + intermediate bag identity to prevent poisoning.
--
-- PARAMETERS:
--   leaf_fp (string): leaf SPKI fingerprint (64-char hex)
--   blocks (table): certificate chain array [leaf, inter1, inter2, ...]
--
-- RETURNS:
--   (string): cache key format "leaf_fp|inter_count|pem1_len:crc|pem2_len:crc|..."
--   (nil): if leaf_fp not valid SPKI or blocks not a table
--
-- SIDE EFFECTS:
--   - Reads: blocks array, PEM strings
--   - Calls: ngx.crc32_long() for each intermediate (pcall-wrapped)
--   - Performance: O(n) where n = intermediates, ~0.5-1ms
--
-- DESIGN NOTES:
--   - Components: leaf_fp + count + PEM length:CRC per intermediate
--   - Collision hardness: CRC32 + length is sufficient for small LRU
--   - Bag identity: includes all intermediates (prevents same-leaf poisoning)
--   - Fallback: missing CRC treated as "?" (safe miss-optimize)
--   - Purpose: per-request cache avoids re-linking same chain
--   - False positives OK: wrong cache hit only misses optimization, not unsafe
--
-- RELATED:
--   - presentable_chain_blocks() — uses this for ngx.ctx cache key
--   - issuer_linked_chain_blocks() — generates blocks to cache
--
-- ============================================================================
-- Cache key: leaf SPKI + intermediate bag identity. Leaf-only keying allowed a
-- clean linked path to poison a later call with a fatter Must-Staple bag
-- (fail-open on unresolved_must_staple). crc32+len is collision-hard enough for
-- a per-request / small LRU memo; wrong hit would only miss-optimize.
local function presentable_cache_key(leaf_fp, blocks)
	if not is_fp64(leaf_fp) or type(blocks) ~= "table" then
		return nil
	end
	local n = #blocks
	local parts = { leaf_fp, tostring(n) }
	for i = 2, n do
		local pem = blocks[i]
		if type(pem) ~= "string" then
			parts[#parts + 1] = "?"
		else
			local crc = 0
			pcall(function()
				if ngx.crc32_long then
					crc = ngx.crc32_long(pem) or 0
				end
			end)
			parts[#parts + 1] = tostring(#pem) .. ":" .. string.format("%08x", crc)
		end
	end
	return table.concat(parts, "|")
end

-- ============================================================================
-- FINALIZE_PRESENTABLE(out, leaf, prior_unresolved, from_pem_string)
-- ============================================================================
-- PURPOSE:
--   Merges prior and context unresolved Must-Staple counts into presentable
--   result (whether from cache or fresh). Mutates output in-place to preserve
--   refuse flags across same-request flows.
--
-- PARAMETERS:
--   out (table): presentable chain output (cache hit or fresh build)
--   leaf (string): leaf certificate PEM (for ctx recovery)
--   prior_unresolved (number|nil): unresolved count from prior call
--   from_pem_string (boolean): whether input was PEM string re-parse
--
-- RETURNS:
--   (table): modified out table with merged unresolved_must_staple field
--   (input): unchanged if out not a table
--
-- SIDE EFFECTS:
--   - Reads: prior_unresolved, ctx unresolved for leaf
--   - Writes: out.unresolved_must_staple (mutates cache entry)
--   - Calls: restore_ctx_unresolved(), note_depleted_pem_unresolved()
--   - Performance: O(1) table updates
--
-- DESIGN NOTES:
--   - In-place mutation: shared cache entries so refuse flags persist
--   - Merging: keeps maximum unresolved count (never downgrades)
--   - PEM re-parse: restores ctx counts when from_pem_string=true
--   - Cleanup: clears ctx when unresolved resolves to 0
--   - Safety: fail-closed on any unresolved (maximizes refuse checks)
--   - Used by: presentable_chain_blocks on both cache hits and misses
--
-- RELATED:
--   - note_depleted_pem_unresolved() — records unresolved by leaf SPKI
--   - restore_ctx_unresolved() — merges ctx count
--   - presentable_chain_blocks() — calls before returning
--
-- ============================================================================
-- Merge prior/ctx unresolved onto a presentable result (cache hit or miss).
-- Mutates out in place (shared cache entry) so a raised refuse flag sticks.
local function finalize_presentable(out, leaf, prior_unresolved, from_pem_string)
	if type(out) ~= "table" then
		return out
	end
	if prior_unresolved and prior_unresolved > 0 then
		local cur = tonumber(out.unresolved_must_staple) or 0
		if prior_unresolved > cur then
			out.unresolved_must_staple = prior_unresolved
		end
	end
	if from_pem_string then
		restore_ctx_unresolved(out, leaf)
	end
	if (tonumber(out.unresolved_must_staple) or 0) <= 0 then
		note_depleted_pem_unresolved(0, leaf)
	end
	return out
end

-- ============================================================================
-- ISSUER_LINKED_CHAIN_PEM(leaf_pem, intermediate_pems)
-- ============================================================================
-- PURPOSE:
--   Wrapper: builds issuer-linked chain blocks and converts to newline-delimited
--   PEM string for direct certificate encoding.
--
-- PARAMETERS:
--   leaf_pem (string): leaf certificate
--   intermediate_pems (table): intermediate PEM array
--
-- RETURNS:
--   (string): newline-delimited PEM (leaf + intermediates) or "" if empty
--
-- SIDE EFFECTS:
--   - Calls: issuer_linked_chain_blocks(), note_depleted_pem_unresolved()
--   - Performance: O(n*m) chain build + O(n) string concat
--
-- RELATED:
--   - issuer_linked_chain_blocks() — chain builder
--   - chain_pem_from_blocks() — inverse (blocks → PEM)
--
-- ============================================================================
local function issuer_linked_chain_pem(leaf_pem, intermediate_pems)
	local blocks = issuer_linked_chain_blocks(leaf_pem, intermediate_pems)
	if type(blocks) ~= "table" or #blocks == 0 then
		return ""
	end
	note_depleted_pem_unresolved(blocks.unresolved_must_staple, blocks[1] or leaf_pem)
	return table.concat(blocks, "\n")
end

-- ============================================================================
-- presentable_chain_blocks(cert_pem_or_blocks)
-- ============================================================================
-- PURPOSE:
--   Cache issuer-linked chain per-request to avoid redundant building.
--   Accepts PEM string or blocks table, returns verified presentation.
--
-- PARAMETERS:
--   cert_pem_or_blocks (string|table): full cert PEM or blocks from prior build
--
-- RETURNS:
--   (blocks_table): issuer-linked PEM array + trust_anchor_index + optional flags
--
-- SIDE EFFECTS:
--   - Cache: Per-request ngx.ctx.bw_presentable_chain_cache (Optimization #3)
--   - Reads: pem_blocks() to parse PEM string if needed
--   - Calls: issuer_linked_chain_blocks() on cache miss
--   - Logs: WARN/ERR for unresolved Must-Staple
--   - Performance: O(1) cache hit, O(n*m) on miss (see issuer_linked_chain_blocks)
--
-- DESIGN NOTES:
--   - Per-request caching: Avoids rebuilding same chain across probe/health/attach
--   - Cache key: Leaf SPKI + intermediate bag identity (prevents collisions)
--   - Fallback LRU: 64-entry touch-counter LRU when ngx.ctx unavailable
--   - Unresolved preservation: Keeps unresolved_must_staple flag across calls
--   - PEM string handling: Restores ctx unresolved only if leaf FP matches
--   - Called by: attach_ocsp_staple(), probe paths, health checks
--   - Related: issuer_linked_chain_blocks() does actual building
--
-- RELATED:
--   - issuer_linked_chain_blocks() core chain builder
--   - presentable_cache_key() generates cache key
--   - finalize_presentable() merges unresolved flags
--
-- ============================================================================
-- Narrow a PEM bag or block list to the leaf's issuer-linked presentation
-- (same rules as issuer_linked_chain_blocks; used by health + attach paths).
--
-- Accepts a PEM string or a blocks table. If the input table already carries
-- unresolved_must_staple (from a prior issuer_linked_chain_blocks call), that
-- count is preserved across re-link: table.concat → re-parse would otherwise
-- drop the named field and the omitted Must-Staple PEMs, making health/attach
-- treat an abbreviated chain as "no intermediate Must-Staple".
-- Same-request depleted-PEM export stamps ngx.ctx by leaf SPKI; string inputs
-- restore only when the re-parsed leaf fingerprint matches (no dual-cert poison).
local function presentable_chain_blocks(cert_pem_or_blocks)
	local prior_unresolved = nil
	local blocks = cert_pem_or_blocks
	local from_pem_string = false
	if type(blocks) == "table" then
		prior_unresolved = tonumber(blocks.unresolved_must_staple)
	elseif type(blocks) == "string" then
		from_pem_string = true
		blocks = pem_blocks(blocks)
	end
	if type(blocks) ~= "table" or #blocks <= 1 then
		-- Short/empty after PEM parse: restore ctx stamp for this leaf only.
		if from_pem_string and type(blocks) == "table" and blocks[1] then
			restore_ctx_unresolved(blocks, blocks[1])
		end
		return blocks
	end
	local leaf = blocks[1]
	local leaf_fp = spki_fingerprint(leaf)
	local cache_key = presentable_cache_key(leaf_fp, blocks)

	-- Cache chain format conversion per-request (optimization #3).
	-- Key includes intermediate bag identity so leaf SPKI alone cannot collide.
	if ngx.ctx then
		if cache_key then
			local cache_table = ngx.ctx.bw_presentable_chain_cache
			if not cache_table then
				cache_table = {}
				ngx.ctx.bw_presentable_chain_cache = cache_table
			end
			local cached = cache_table[cache_key]
			if cached then
				-- Cache hit still merges prior/ctx unresolved (fail closed).
				return finalize_presentable(cached, leaf, prior_unresolved, from_pem_string)
			end
		end
	else
		-- Fallback for edge case: ngx.ctx not available (optimization #7)
		-- Use LRU fallback cache (64-entry limit, per-worker process)
		if cache_key then
			local cached = fallback_cache_get(cache_key)
			if cached then
				log(ngx.DEBUG, "OCSP presentable_chain_blocks: fallback cache hit (ngx.ctx unavailable)")
				return finalize_presentable(cached, leaf, prior_unresolved, from_pem_string)
			end
		end
		log(
			ngx.DEBUG,
			"OCSP presentable_chain_blocks: ngx.ctx unavailable, using fallback cache (no per-request cache)"
		)
	end
	local inters = {}
	for i = 2, #blocks do
		inters[#inters + 1] = blocks[i]
	end
	local out = issuer_linked_chain_blocks(leaf, inters)
	finalize_presentable(out, leaf, prior_unresolved, from_pem_string)
	-- Store in cache for reuse (optimization #3)
	-- Fallback: if ngx.ctx not available, use LRU fallback cache (optimization #7)
	if ngx.ctx then
		if cache_key then
			local cache_table = ngx.ctx.bw_presentable_chain_cache
			if cache_table then
				cache_table[cache_key] = out
			end
		end
	else
		-- Fallback cache: 64-entry LRU, per-worker storage
		if cache_key then
			fallback_cache_set(cache_key, out)
		end
	end
	return out
end

-- ============================================================================
-- CHAIN_PEM_FROM_BLOCKS(blocks)
-- ============================================================================
-- PURPOSE:
--   Inverse of issuer_linked_chain_blocks: converts blocks table (with unresolved
--   flag) to newline-delimited PEM for TLS certificate encoding.
--
-- PARAMETERS:
--   blocks (table): issuer-linked chain from issuer_linked_chain_blocks
--
-- RETURNS:
--   (string): newline-delimited PEM or "" if empty
--
-- SIDE EFFECTS:
--   - Calls: note_depleted_pem_unresolved() to record unresolved state
--   - Performance: O(n) string concat where n = chain length
--
-- DESIGN NOTES:
--   - Array only: named fields (unresolved_must_staple, trust_anchor_index) ignored
--   - Context stamping: records unresolved for later recovery in same request
--   - Used by: certificate presentation flow (TLS set_cert)
--
-- RELATED:
--   - issuer_linked_chain_pem() — forward conversion (pems → PEM string)
--   - issuer_linked_chain_blocks() — array builder
--
-- ============================================================================
-- PEM for set_cert from issuer-linked blocks (array part only; named fields ignored).
-- Stamps ngx.ctx by leaf SPKI when unresolved_must_staple>0 (PEM→presentable refuse).
local function chain_pem_from_blocks(blocks)
	if type(blocks) ~= "table" or #blocks == 0 then
		return ""
	end
	note_depleted_pem_unresolved(blocks.unresolved_must_staple, blocks[1])
	return table.concat(blocks, "\n")
end

function _M.issuer_linked_chain_pem(leaf_pem, intermediate_pems)
	return issuer_linked_chain_pem(leaf_pem, intermediate_pems)
end

function _M.issuer_linked_chain_blocks(leaf_pem, intermediate_pems)
	return issuer_linked_chain_blocks(leaf_pem, intermediate_pems)
end

-- ============================================================================
-- issuer_path_intermediate_ready(chain_pem_or_blocks)
-- ============================================================================
-- PURPOSE:
--   Readiness check: can this leaf's intermediates be OCSP-stapled?
--   Used for dual-cert/probe health checks (no leaf body needed).
--
-- PARAMETERS:
--   chain_pem_or_blocks (string|table): full cert chain or blocks from builder
--
-- RETURNS:
--   (ok, reason):
--     ok (boolean): true if intermediates can be stapled
--     reason (string|nil): failure reason if not ready
--       - issuer_unresolved_must_staple: omitted Must-Staple intermediates
--       - intermediate_must_staple_libssl: needs OpenSSL 3.6+
--       - intermediate_must_staple_colony: colony consensus is leaf-only
--       - response_not_found: Must-Staple intermediate has no OCSP body
--
-- SIDE EFFECTS:
--   - Calls: presentable_chain_blocks() for chain prep
--   - Calls: openssl_multi_staple_ready() for capability check
--   - Calls: chain_has_intermediate_must_staple() for Must-Staple detection
--   - Calls: load_paged_intermediate_staple() to verify bodies
--   - Performance: O(n) worst case, ~2-3ms typical
--
-- DESIGN NOTES:
--   - Sticky defects: intermediate_must_staple gap demotes leaf
--   - NULL slots OK: missing intermediate without Must-Staple is legal
--   - Unresolved check first: Omitted PEMs left out of blocks still count
--   - Multi-staple gate: Checks capability before validating bodies
--   - Colony check: Even one leaf-only peer forces leaf-only fleet
--   - No leaf body: Can check intermediate readiness without leaf OCSP
--   - Used by: probe health checks, dual-cert readiness
--   - Related: issuer_path_null_slots for slot counting
--
-- RELATED:
--   - presentable_chain_blocks() for chain normalization
--   - openssl_multi_staple_ready() for capability detection
--   - chain_has_intermediate_must_staple() for Must-Staple check
--   - load_paged_intermediate_staple() for body verification
--
-- ============================================================================
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
	-- Use cached trust_anchor_index for early exit (optimization #2)
	local anchor_idx = tonumber(blocks.trust_anchor_index)
	local loop_end = anchor_idx and (anchor_idx - 1) or #blocks
	for i = 2, loop_end do
		local pem = blocks[i]
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

function _M.chain_has_intermediate_must_staple(chain_pem_or_blocks)
	local blocks = presentable_chain_blocks(chain_pem_or_blocks)
	-- Omitted Must-Staple PEMs leave a depleted list that chain_has would miss;
	-- unresolved_must_staple must still count as intermediate Must-Staple present.
	if type(blocks) == "table" and (tonumber(blocks.unresolved_must_staple) or 0) > 0 then
		return true
	end
	return chain_has_intermediate_must_staple(blocks)
end

-- How many issuer-path intermediates would attach as NULL (ok_partial slots).
-- Used to rank leaf-GOOD siblings: fewer nulls = more complete multi-staple.
-- Colony/libssl leaf-only with intermediate Must-Staple scores a large sentinel
-- (not vacuous 0) so a multi-capable sibling wins ranking. unresolved_must_staple
-- on a short/#blocks<2 depleted chain also scores the sentinel (not vacuous 0).
-- Without intermediate Must-Staple, leaf-only still scores 0 (legal completeness).
-- Does not demote — ok_partial remains legal when it is the only healthy option.
local function issuer_path_null_slots(chain_pem_or_blocks)
	local blocks = presentable_chain_blocks(chain_pem_or_blocks)
	if type(blocks) ~= "table" then
		return 0
	end
	if (tonumber(blocks.unresolved_must_staple) or 0) > 0 then
		return 64
	end
	if #blocks < 2 then
		return 0
	end
	local ready = openssl_multi_staple_ready()
	if not ready then
		if chain_has_intermediate_must_staple(blocks) then
			-- Vacuous "0 nulls" would rank a crippled path above a multi-ready sibling.
			return 64
		end
		return 0
	end
	local leaf_pem = blocks[1]
	local nulls = 0
	-- Use cached trust_anchor_index for early exit (optimization #2)
	local anchor_idx = tonumber(blocks.trust_anchor_index)
	local loop_end = anchor_idx and (anchor_idx - 1) or #blocks
	for i = 2, loop_end do
		local pem = blocks[i]
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

_M.internal = {
	attach_ocsp_staple = attach_ocsp_staple,
	chain_pem_from_blocks = chain_pem_from_blocks,
	clear_connection_staple = clear_connection_staple,
	issuer_linked_chain_blocks = issuer_linked_chain_blocks,
	issuer_path_intermediate_ready = issuer_path_intermediate_ready,
	issuer_path_null_slots = issuer_path_null_slots,
	chain_has_intermediate_must_staple = chain_has_intermediate_must_staple,
	note_connection_staple = note_connection_staple,
	openssl_multi_staple_ready = openssl_multi_staple_ready,
	presentable_chain_blocks = presentable_chain_blocks,
	refresh_multi_staple_vote = refresh_multi_staple_vote,
}

return _M
