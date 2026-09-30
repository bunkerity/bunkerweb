--[[
================================================================================
OCSP Pin Module: Fleet Allow-Pin Bus and Peer Refuse Policy Enforcement
================================================================================

MODULE OVERVIEW:
Cross-subsystem (HTTP↔stream) allow-pin bus for coordinated Must-Staple
enforcement and peer-refuse consensus. Inverts refuse semantics: MISSING pin
refuses Must-Staple (policy default), only PRESENT pins grant allow-through.

KEY CONCEPTS:
1. Allow-Pin Bus: /var/cache/bunkerweb/ssl/ocsp-allow/{fp} JSON files holding
   der_sha256 + soft_recall_gen generation identity. Missing pin = Must-Staple
   refused (conservative). Present pin = generation-matched allow granted.

2. Compare-and-Delete (CAS): Revoke via atomic rename to claim file, re-verify,
   disarm/restore, sweep orphan claims. Prevents thundering-herd on hot paths
   and ensures stale gen does not erase newer generation.

3. Claim/Restore Cycle: When revoking (worker death mid-CAS), claim files
   (/tmp.revoke.*) hold intermediate state. Restoration via hardlink or rename
   prevents fleet Must-Staple from disappearing if revoke fails.

4. Per-Tenant Control Keys: Intermediate OCSP state uses control FP (leaf SPKI
   + inter SPKI hash) so one leaf's negative does not poison entire CA.

5. Soft-Fuse Modes: OCSP_STAPLE_MODE=staple_only/open softens Must-Staple
   enforcement while keeping allow-pin bus intact for other workers' consensus.

OPERATIONS:
- read_allow_pin(): Per-request cached disk read with generation tri-state
- revoke_allow_pin(): CAS-delete, upgrade-grace gen-0 guard, sibling claim sweep
- write_allow_pin(): Job/canary publish with stale-gen guard
- drop_allow_pin(): Unconditional drop for admin/job cleanup (not handshake)

EXPORTS:
- Public: peer_refuse_blocks (inverted bus read), should_skip_peer_bus,
  record_peer_refuse (bus write), drop_allow_pin, write_allow_pin, canary_paged_body_ok
- Internal: must_staple_refuse, allow-pin read/write/revoke operations

DEPENDENCIES:
- ocsp_common: DROP/KEEP policies, format_staple_decision, logging
- ocsp_store: generation_tuple, ligand_or_meta, soft_recall_gen_of
- Called by ocsp.lua (peer_refuse_blocks check, record_peer_refuse on refuse)

================================================================================
]]

-- Allow-pin bus (HTTP <-> stream) and peer-refuse DROP/KEEP rules.
-- Part of bunkerweb.ocsp; other modules use the .internal table, callers use bunkerweb.ocsp.
local _M = {}

local ngx = ngx

local common = require("bunkerweb.ocsp_common").internal
local OCSP_CLOCK_SKEW_SECONDS = common.OCSP_CLOCK_SKEW_SECONDS
local DROP_ALLOW_ON_REFUSE = common.DROP_ALLOW_ON_REFUSE
local KEEP_ALLOW_ON_REFUSE = common.KEEP_ALLOW_ON_REFUSE
local META_ONLY_DROP_ALLOW = common.META_ONLY_DROP_ALLOW
local format_staple_decision = common.format_staple_decision
local is_fp64 = common.is_fp64
local log = common.log
local path_exists = common.path_exists
local read_file = common.read_file

local store = require("bunkerweb.ocsp_store").internal
local L1_MAX_TTL = store.L1_MAX_TTL
local generation_tuple = store.generation_tuple
local ligand_or_meta_uncached = store.ligand_or_meta
local shard_not_paged = store.shard_not_paged
local soft_recall_gen_of = store.soft_recall_gen_of

-- Transient allow-pin TTL when expires_unix is absent (align with L1).
local ALLOW_PIN_TTL_SECONDS = L1_MAX_TTL

-- store.ligand_or_meta always samples live shard+ligand (ignores caller meta) and
-- already per-request-caches via read_ocsp_json / read_ocsp_ligand. A prior wrapper
-- that merged caller meta with a cached ligand reintroduced stale-caller
-- tombstone/gen holes after the live-first store fix — do not resurrect it.
-- ============================================================================
-- LIGAND_OR_META(_meta, fingerprint)
-- ============================================================================
-- PURPOSE:
--   Resolves effective metadata: ligand (live) or meta (cached/default).
--   Prefers ligand when available for fleet consensus; falls back to meta.
--
-- PARAMETERS:
--   _meta (table|nil): metadata table (unused, for signature compat)
--   fingerprint (string): certificate SPKI fingerprint (64-char hex)
--
-- RETURNS:
--   (table): ligand metadata (from L1 cache or disk)
--   (nil): if no ligand and no fallback available
--
-- SIDE EFFECTS:
--   - Calls: ligand_or_meta_uncached() — reads from L1/disk
--   - Reads: /var/cache/bunkerweb/ssl/ocsp-ligand/{fp}
--   - Performance: ~0.5-2ms (L1 hit), ~2-5ms (L1 miss + disk read)
--
-- DESIGN NOTES:
--   - Live-first: ligand (live metadata) always preferred over cached meta
--   - L1 cache: avoids repeated disk reads within single request
--   - Fallback: when ligand unavailable, meta provides default
--   - Signature: _meta param unused (compatibility with ocsp_store caller)
--   - Used by: peer_refuse_blocks, should_skip_peer_bus, record_peer_refuse
--
-- RELATED:
--   - ligand_or_meta_uncached() — actual implementation
--   - read_ocsp_ligand() (ocsp_store) — reads from disk
--   - ligand_path() (ocsp_store) — ligand directory path
--
-- ============================================================================
local function ligand_or_meta(_meta, fingerprint)
	return ligand_or_meta_uncached(nil, fingerprint)
end

-- DROP/KEEP tables live in ocsp_common (STAPLE_POLICY). Prefix rules stay here:
-- canary_* defaults DROP; shared_ligand_* DROP unless KEEP on the stripped suffix.
-- Invariant: every cause should_skip_peer_bus returns true for must also be KEEP.

-- ============================================================================
-- OCSP_ALLOW_PATH(fingerprint)
-- ============================================================================
-- PURPOSE:
--   Computes allow-pin disk path for certificate fingerprint.
--   Normalizes uppercase hex to lowercase (case-insensitive POSIX).
--
-- PARAMETERS:
--   fingerprint (string): certificate SPKI fingerprint (64-char hex)
--
-- RETURNS:
--   (string): full path /var/cache/bunkerweb/ssl/ocsp-allow/{fp-lowercase}
--
-- SIDE EFFECTS:
--   - Reads: none
--   - Writes: none (pure computation)
--   - Logs: none
--   - Performance: O(1) string concatenation
--
-- DESIGN NOTES:
--   - Case normalization: uppercase converted to lowercase for disk
--   - Deterministic: same fingerprint always yields same path
--   - Used by: read_allow_pin, write_allow_pin, revoke_allow_pin
--   - Safe: prevents uppercase hex from forking parallel pin paths
--
-- RELATED:
--   - ocsp_refuse_path_legacy() — legacy refuse directory path
--   - read_allow_pin() — uses this path for disk read
--   - write_allow_pin() — uses for pin installation
--
-- ============================================================================
local function ocsp_allow_path(fingerprint)
	-- Lowercase so uppercase hex cannot fork a parallel pin path vs the job.
	return "/var/cache/bunkerweb/ssl/ocsp-allow/" .. fingerprint:lower()
end

-- Legacy refuse path — job-side cleanup only after the allow-pin invert.
-- ============================================================================
-- OCSP_REFUSE_PATH_LEGACY(fingerprint)
-- ============================================================================
-- PURPOSE:
--   Computes legacy refuse-pin disk path (deprecated, job-side cleanup only).
--   Old allow-pin style; replaced by inverted allow-pin bus.
--
-- PARAMETERS:
--   fingerprint (string): certificate SPKI fingerprint (64-char hex)
--
-- RETURNS:
--   (string): full path /var/cache/bunkerweb/ssl/ocsp-refuse/{fp-lowercase}
--
-- SIDE EFFECTS:
--   - Reads: none (pure computation)
--   - Writes: none (path computation only)
--   - Logs: none
--   - Performance: O(1) string concatenation
--
-- DESIGN NOTES:
--   - Legacy: old refuse-pin format (before inverted allow-pin)
--   - Job-only cleanup: handshake never touches refuse path (read-only)
--   - Case normalization: uppercase hex converted to lowercase
--   - Cleanup scope: write_allow_pin and drop_allow_pin unlink these
--   - Backward compat: maintains compatibility with older deployments
--
-- RELATED:
--   - ocsp_allow_path() — new allow-pin path (replacement)
--   - write_allow_pin() — unlinks legacy refuse on write
--   - drop_allow_pin() — unlinks legacy refuse on cleanup
--
-- ============================================================================
local function ocsp_refuse_path_legacy(fingerprint)
	return "/var/cache/bunkerweb/ssl/ocsp-refuse/" .. fingerprint:lower()
end

-- Handshake is read-only on the pin directory (except compare-and-delete revoke).
-- Do NOT unlink legacy refuse or gen-less pins here: that was a DoS lever on the
-- hot path and turned mixed-version rollouts into synchronized Must-Staple outages.
-- Missing soft_recall_gen → treat as 0 (one-release upgrade grace); job restamp
-- rewrites proper gen on the next run.
-- Decode allow-pin JSON bytes; nil unless der_sha256 is 64 lowercase-normalized hex.
-- ============================================================================
-- DECODE_ALLOW_PIN(raw)
-- ============================================================================
-- PURPOSE:
--   Parses allow-pin JSON with strict validation and generation normalization.
--   Fails closed on invalid input; only accepts valid der_sha256 + gen combo.
--
-- PARAMETERS:
--   raw (string|nil): JSON bytes from disk file {der_sha256: hex, soft_recall_gen: num}
--
-- RETURNS:
--   (table): {der_sha256: hex, soft_recall_gen: number|false} if valid
--   (nil): if JSON unparseable, missing der_sha256, or invalid format
--
-- SIDE EFFECTS:
--   - Reads: cjson library for JSON decode
--   - Normalizes: der_sha256 to lowercase, soft_recall_gen via soft_recall_gen_of
--   - Logs: none (errors handled via nil return)
--   - Performance: O(1) parse + validation
--
-- DESIGN NOTES:
--   - Fail-closed: nil if any field invalid (not lenient)
--   - Hex validation: der_sha256 must be exactly 64 lowercase-normalized hex chars
--   - Generation contract: omit→0 (upgrade grace), invalid→false (fail-closed)
--   - Sentinel tri-state: 0 = grace, number = generation, false = invalid
--   - Cache-safety: false prevents soft_recall_gen_of from re-normalizing to 0
--   - Upgrade grace: one-release rollout window when gen omitted
--
-- RELATED:
--   - soft_recall_gen_of() — normalizes generation from meta
--   - read_allow_pin() — disk read caller
--   - write_allow_pin() — creates pin with this structure
--
-- ============================================================================
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
	-- Same sentinel contract as read_ocsp_ligand: omit→0 (upgrade grace);
	-- present-but-invalid → false so a later soft_recall_gen_of cannot treat
	-- that as omit→0 and rematch leftover gen-0 pins.
	local raw_gen = obj.soft_recall_gen
	if raw_gen == nil then
		obj.soft_recall_gen = 0
	else
		local normalized = soft_recall_gen_of(obj)
		if type(normalized) == "number" then
			obj.soft_recall_gen = normalized
		else
			obj.soft_recall_gen = false
		end
	end
	return obj
end

-- Drop per-request pin/claim/revoke caches after revoke/write/drop/reclaim.
-- Pin entries must be cleared (nil), not set to false: false means "confirmed
-- missing" and would hide a just-written / just-reclaimed pin in the same ctx.
-- ============================================================================
-- INVALIDATE_PIN_CACHES(fingerprint)
-- ============================================================================
-- PURPOSE:
--   Clears per-request pin/claim/revoke caches after state changes.
--   Prevents stale "missing" sentinels from hiding just-written pins.
--
-- PARAMETERS:
--   fingerprint (string): certificate SPKI fingerprint (64-char hex)
--
-- RETURNS:
--   (nil): side effects only (no return value)
--
-- SIDE EFFECTS:
--   - Writes: clears ngx.ctx.bw_ocsp_pin_cache[fingerprint]
--   - Writes: clears ngx.ctx.bw_ocsp_claim_cache[fingerprint]
--   - Writes: clears ngx.ctx.bw_ocsp_revoke_cache entries for fp|sha|gen
--   - Performance: O(n) where n = revoke cache entries for this fingerprint
--
-- DESIGN NOTES:
--   - Nil clear: must use nil, not false (false = "confirmed missing")
--   - Case normalization: clears both mixed and lowercase variants
--   - Revoke prefix scan: drops fp|sha|gen and fp| prefixed entries
--   - Called by: write_allow_pin, revoke_allow_pin, drop_allow_pin, reclaim
--   - Safety: prevents false-negative "pin missing" after state change
--
-- RELATED:
--   - read_allow_pin() — reads and caches pins
--   - revoke_allow_pin() — calls to clear after delete
--   - write_allow_pin() — calls to clear after publish
--
-- ============================================================================
local function invalidate_pin_caches(fingerprint)
	local ctx = ngx.ctx
	if not ctx or type(fingerprint) ~= "string" then
		return
	end
	local lower = fingerprint:lower()
	if ctx.bw_ocsp_pin_cache then
		ctx.bw_ocsp_pin_cache[fingerprint] = nil
		if lower ~= fingerprint then
			ctx.bw_ocsp_pin_cache[lower] = nil
		end
	end
	if ctx.bw_ocsp_claim_cache then
		ctx.bw_ocsp_claim_cache[fingerprint] = nil
		if lower ~= fingerprint then
			ctx.bw_ocsp_claim_cache[lower] = nil
		end
	end
	-- Revoke outcomes are keyed fp|sha|gen; drop any entry for this fp so a
	-- prior allow_absent cannot suppress a post-restamp DROP in the same ctx.
	if ctx.bw_ocsp_revoke_cache then
		local prefix = lower .. "|"
		for k in pairs(ctx.bw_ocsp_revoke_cache) do
			if
				type(k) == "string"
				and (k:sub(1, #prefix) == prefix or k:sub(1, #fingerprint + 1) == fingerprint .. "|")
			then
				ctx.bw_ocsp_revoke_cache[k] = nil
			end
		end
	end
end

-- ============================================================================
-- READ_ALLOW_PIN(fingerprint)
-- ============================================================================
-- PURPOSE:
--   Reads allow-pin (generation identity) from disk with per-request cache.
--   Avoids redundant disk I/O for same cert within single handshake.
--
-- PARAMETERS:
--   fingerprint (string): certificate SPKI fingerprint (64-char hex)
--
-- RETURNS:
--   (table): {der_sha256: hex, soft_recall_gen: number} if pin exists
--   (nil): if pin not found or fingerprint invalid
--
-- SIDE EFFECTS:
--   - Reads: /var/cache/bunkerweb/ssl/ocsp-allow/{fp}
--   - Cache: ngx.ctx.bw_ocsp_pin_cache per-request dedup
--   - Performance: O(1) cache hit, ~1-2ms disk miss
--
-- DESIGN NOTES:
--   - Cache semantics: false = "not found" (miss), table = "found" (hit)
--   - Case normalization: fingerprint lowercased for cache/disk consistency
--   - Miss caching: prevents re-reading missing files within same request
--   - Tri-state: allows distinguishing unreadable from missing
--
-- RELATED:
--   - write_allow_pin() — publishes pin
--   - revoke_allow_pin() — deletes pin via CAS
--   - decode_allow_pin() — parses JSON
--
-- ============================================================================
-- Read allow-pin with per-request dedup cache (ngx.ctx)
-- Avoids re-reading the same file within a single handshake
local function read_allow_pin(fingerprint)
	if not is_fp64(fingerprint) then
		return nil
	end
	-- Lowercase cache key: is_fp64 allows A-F; disk path is lowercase — mixed
	-- case must not fork a parallel ngx.ctx entry beside the live pin.
	fingerprint = fingerprint:lower()

	-- Initialize per-request cache on first use
	local ctx = ngx.ctx
	if ctx and not ctx.bw_ocsp_pin_cache then
		ctx.bw_ocsp_pin_cache = {}
	end

	-- Check per-request cache first
	if ctx and ctx.bw_ocsp_pin_cache then
		local cached = ctx.bw_ocsp_pin_cache[fingerprint]
		if cached ~= nil then
			-- Distinguish between "file not found" (false) and "found" (table)
			if cached == false then
				return nil
			end
			return cached
		end
	end

	-- Cache miss: read from disk
	local pin = decode_allow_pin(read_file(ocsp_allow_path(fingerprint)))
	if pin == nil then
		-- Cache the "not found" result to prevent re-reading
		if ctx and ctx.bw_ocsp_pin_cache then
			ctx.bw_ocsp_pin_cache[fingerprint] = false
		end
		return nil
	end
	-- Cache successful decode
	if ctx and ctx.bw_ocsp_pin_cache then
		ctx.bw_ocsp_pin_cache[fingerprint] = pin
	end
	return pin
end

-- True when the pin names exactly this generation (der_sha256, soft_recall_gen).
-- want_g must be a number; pin.soft_recall_gen must already be a number (decode
-- stores 0 for omit, false for present-but-invalid — false fails closed here).
-- ============================================================================
-- ALLOW_PIN_MATCHES(pin, want_sha, want_g)
-- ============================================================================
-- PURPOSE:
--   Validates allow-pin matches expected generation (DER SHA256 + recall gen).
--   Fails closed on type errors; only true if exact match.
--
-- PARAMETERS:
--   pin (table): decoded pin {der_sha256: hex, soft_recall_gen: number}
--   want_sha (string): expected DER SHA256 (64-char hex)
--   want_g (number): expected soft recall generation
--
-- RETURNS:
--   (true): pin matches both der_sha256 and soft_recall_gen exactly
--   (false): mismatch or type error (including false for invalid gen)
--
-- SIDE EFFECTS:
--   - Reads: pin.der_sha256, pin.soft_recall_gen
--   - Logs: none
--   - Performance: O(1) type check + comparison
--
-- DESIGN NOTES:
--   - Fail-closed: false for invalid types (invalid gen → refuse)
--   - Type guard: want_g must be number (no string→number coercion)
--   - Decode safety: pin.soft_recall_gen is 0 or false (not nil)
--   - Generation identity: both SHA and gen must match (AND, not OR)
--   - Used by: peer_refuse_blocks() to validate generation binding
--
-- RELATED:
--   - generation_tuple() — extracts sha + gen from response
--   - decode_allow_pin() — sets gen to 0 or false
--   - peer_refuse_blocks() — calls to validate pin
--
-- ============================================================================
local function allow_pin_matches(pin, want_sha, want_g)
	if type(want_g) ~= "number" or type(pin) ~= "table" then
		return false
	end
	if pin.der_sha256 ~= want_sha then
		return false
	end
	local pin_g = pin.soft_recall_gen
	if type(pin_g) ~= "number" then
		return false
	end
	return pin_g == want_g
end

-- Claim / write temps match the job's stale-temp sweep (**/.ocsp_*.tmp) so a
-- worker that dies mid-CAS cannot leave litter behind indefinitely.
-- ============================================================================
-- ALLOW_PIN_TMP_PATH(fingerprint, kind)
-- ============================================================================
-- PURPOSE:
--   Generates unique temporary file path for pin operations (write/claim/dead).
--   Path naming prevents litter from accumulating across crashes.
--
-- PARAMETERS:
--   fingerprint (string): certificate SPKI fingerprint (64-char hex)
--   kind (string): operation type: "write", "revoke", "dead", or "tmp"
--
-- RETURNS:
--   (string): full path /var/cache/bunkerweb/ssl/ocsp-allow/.ocsp_{kind}.{fp}.{pid}.{seq}.tmp
--
-- SIDE EFFECTS:
--   - State: increments pin_tmp_seq counter (thread-local)
--   - Reads: ngx.worker.pid() for current worker process ID
--   - Logs: none
--   - Performance: O(1) string concatenation
--
-- DESIGN NOTES:
--   - Unique naming: pid + seq prevents temp collision between workers
--   - Job sweep: /.ocsp_*.tmp pattern matches job cleanup (stale-temp removal)
--   - Prefix types: write (install), revoke (claim), dead (disarmed)
--   - Case normalization: fingerprint lowercased for consistency
--   - Per-worker seq: each worker tracks its own temp sequence
--
-- RELATED:
--   - allow_pin_claim_path() — specialized revoke variant
--   - write_allow_pin() — uses "write" variant
--   - revoke_allow_pin() — uses "revoke" variant
--
-- ============================================================================
local pin_tmp_seq = 0
local function allow_pin_tmp_path(fingerprint, kind)
	pin_tmp_seq = pin_tmp_seq + 1
	local pid = (ngx.worker and ngx.worker.pid and ngx.worker.pid()) or 0
	return "/var/cache/bunkerweb/ssl/ocsp-allow/.ocsp_"
		.. tostring(kind or "tmp")
		.. "."
		.. fingerprint:lower()
		.. "."
		.. tostring(pid)
		.. "."
		.. tostring(pin_tmp_seq)
		.. ".tmp"
end

-- ============================================================================
-- ALLOW_PIN_CLAIM_PATH(fingerprint)
-- ============================================================================
-- PURPOSE:
--   Generates claim file path for compare-and-delete revocation operations.
--   Specialized variant of allow_pin_tmp_path with "revoke" kind.
--
-- PARAMETERS:
--   fingerprint (string): certificate SPKI fingerprint (64-char hex)
--
-- RETURNS:
--   (string): full path /var/cache/bunkerweb/ssl/ocsp-allow/.ocsp_revoke.{fp}.{pid}.{seq}.tmp
--
-- SIDE EFFECTS:
--   - Calls: allow_pin_tmp_path(fingerprint, "revoke")
--   - State: increments pin_tmp_seq counter
--   - Performance: O(1) wrapper call
--
-- DESIGN NOTES:
--   - Wrapper: convenience function for revoke-specific path
--   - Pattern: .ocsp_revoke.* used by claim scanning (list_allow_pin_claims)
--   - Unique: each call generates new path (different seq)
--   - Used by: revoke_allow_pin() CAS operation
--
-- RELATED:
--   - allow_pin_tmp_path() — base function with "revoke" kind
--   - revoke_allow_pin() — calls to generate claim path
--   - list_allow_pin_claims() — scans for .ocsp_revoke.* files
--
-- ============================================================================
local function allow_pin_claim_path(fingerprint)
	return allow_pin_tmp_path(fingerprint, "revoke")
end

-- Destroy or disarm a sticky claim so try_reclaim cannot restore it.
-- Order: unlink → rename out of .ocsp_revoke.* → poison decode with "{}".
-- ============================================================================
-- NEUTRALIZE_ALLOW_CLAIM(claim, fingerprint)
-- ============================================================================
-- PURPOSE:
--   Disarm sticky claim file to prevent try_reclaim_orphan_claim restoration.
--   Called after successful CAS delete to prevent pin resurrection.
--
-- PARAMETERS:
--   claim (string): full path to claim file (e.g., .ocsp_revoke.{fp}.{pid}.tmp)
--   fingerprint (string): certificate SPKI fingerprint (for tomb naming)
--
-- RETURNS:
--   (true): claim successfully destroyed or missing
--   (false): claim still readable after neutralization attempt
--
-- SIDE EFFECTS:
--   - Writes: attempts unlink, rename to .dead, or poison with "{}"
--   - Performance: ~1-5ms (filesystem ops)
--   - Idempotent: safe to call multiple times
--
-- DESIGN NOTES:
--   - Multi-stage disarm: unlink → rename → poison
--   - Unlink first: fast path on POSIX
--   - Rename fallback: moves to .dead prefix (out of .ocsp_revoke.*)
--   - Poison fallback: overwrites with "{}" (decode rejects it)
--   - Decode validation: "{}" fails decode_allow_pin check (fail-safe)
--   - Orphan prevention: ensures try_reclaim cannot restore deleted pin
--
-- RELATED:
--   - restore_claimed_pin() — restores if not neutralized
--   - revoke_allow_pin() — calls after successful CAS
--   - try_reclaim_orphan_claim() — checks if claim can restore
--
-- ============================================================================
local function neutralize_allow_claim(claim, fingerprint)
	if type(claim) ~= "string" or claim == "" then
		return true
	end
	os.remove(claim)
	if not path_exists(claim) then
		return true
	end
	os.remove(claim)
	if not path_exists(claim) then
		return true
	end
	local tomb = allow_pin_tmp_path(fingerprint, "dead")
	if os.rename(claim, tomb) then
		os.remove(tomb)
		return not path_exists(claim)
	end
	local poison = io.open(claim, "w")
	if poison then
		poison:write("{}")
		poison:close()
	end
	-- Still under revoke prefix, but decode_allow_pin rejects "{}".
	return decode_allow_pin(read_file(claim)) == nil
end

-- Put a claimed pin back at `path` without clobbering a newer one the job may have
-- published meanwhile. Prefer hard link (EEXIST = live pin already present).
-- Rename fallback when link fails with an empty slot (EXDEV / no lfs.link) — without
-- it, stale_gen / race_restore left the pin only in the claim until job sweep
-- unlinked it (~60s) and the fleet pin vanished.
--
-- After a successful link, the claim name MUST be unlinked. A leftover hardlink
-- to the same inode means DROP of `path` still leaves a reclaimable claim that
-- try_reclaim_orphan_claim will restore — undoing the DROP.
-- fingerprint is required to neutralize an obsolete claim when path is already taken.
-- ============================================================================
-- RESTORE_CLAIMED_PIN(claim, path, fingerprint)
-- ============================================================================
-- PURPOSE:
--   Restore claimed pin to live path without clobbering newer peer-published pins.
--   Called during CAS if race detected (job restamped between read and rename).
--
-- PARAMETERS:
--   claim (string): claim file path (.ocsp_revoke.{fp}.{pid}.tmp)
--   path (string): live pin path (/var/cache/bunkerweb/ssl/ocsp-allow/{fp})
--   fingerprint (string): certificate SPKI fingerprint (for neutralize)
--
-- RETURNS:
--   (true): pin successfully restored to live path
--   (false): peer won race (path taken) or dual hardlink stuck
--
-- SIDE EFFECTS:
--   - Writes: hardlink(claim → path) or rename(claim → path)
--   - Writes: unlinks or neutralizes claim after successful restore
--   - Calls: neutralize_allow_claim() if path pre-exists or race
--   - Performance: ~1-5ms (lfs.link + unlink, or rename)
--
-- DESIGN NOTES:
--   - Three-path strategy: hardlink (preferred) → rename → poison
--   - Hardlink safety: EEXIST means peer won, disarm claim
--   - Rename fallback: for EXDEV or no lfs.link
--   - Race recovery: if path appears during rename, neutralize claim
--   - Dual hardlink: both paths to same inode; DROP still leaves litter
--   - Never poison: hardlink restoration avoids shared-inode corruption
--
-- RELATED:
--   - revoke_allow_pin() — calls on race detection
--   - neutralize_allow_claim() — disarms if peer won
--
-- ============================================================================
local function restore_claimed_pin(claim, path, fingerprint)
	local ok_lfs, lfs = pcall(require, "lfs")
	if ok_lfs and type(lfs) == "table" and lfs.link and lfs.link(claim, path) then
		os.remove(claim)
		if path_exists(claim) then
			os.remove(claim)
		end
		if not path_exists(claim) then
			return true
		end
		-- Dual hardlink: undo by dropping the new path name. Never neutralize/poison
		-- here — that would wipe the shared inode (live pin + claim).
		os.remove(path)
		if not path_exists(path) then
			-- Claim is again the sole name (reclaimable litter).
			return false
		end
		-- Path unlink failed; try claim unlink once more (still no poison).
		os.remove(claim)
		if not path_exists(claim) then
			return true
		end
		-- Dual hardlink remains; caller may retry. Do not poison.
		return false
	end
	if path_exists(path) then
		-- Live pin already present (peer won): disarm claim so it cannot be
		-- reclaimed after a later DROP of the peer's pin.
		-- Safe: claim and path are distinct inodes (we never linked them).
		neutralize_allow_claim(claim, fingerprint)
		return false
	end
	if os.rename(claim, path) then
		return true
	end
	-- Race created path between exists-check and rename: keep claim only if
	-- path still empty (transient error); otherwise claim is obsolete.
	if path_exists(path) then
		neutralize_allow_claim(claim, fingerprint)
	end
	return false
end

-- Scan ocsp-allow for .ocsp_revoke.{fp}.* claim litter (worker death mid-revoke).
-- ============================================================================
-- LIST_ALLOW_PIN_CLAIMS(fingerprint)
-- ============================================================================
-- PURPOSE:
--   Scans for orphan claim files (.ocsp_revoke.{fp}.*) from crashed workers.
--   Used by sweep and reclaim paths to detect stranded CAS-in-progress state.
--
-- PARAMETERS:
--   fingerprint (string): certificate SPKI fingerprint (64-char hex)
--
-- RETURNS:
--   (table): array of full claim file paths matching .ocsp_revoke.{fp}.*.tmp
--   (empty table): if directory scan fails or fingerprint invalid
--
-- SIDE EFFECTS:
--   - Reads: /var/cache/bunkerweb/ssl/ocsp-allow directory contents
--   - Reads: lfs.dir() for directory iteration
--   - Logs: none (errors suppressed)
--   - Performance: O(n) where n = files in ocsp-allow directory
--
-- DESIGN NOTES:
--   - Pattern match: .ocsp_revoke.{fp}.{pid}.{seq}.tmp
--   - Best-effort: returns empty array if lfs unavailable
--   - Fingerprint-specific: only lists claims for this cert
--   - Prefix filtering: fast O(n) scan (no glob needed)
--   - Used by: sweep_allow_pin_claims, try_reclaim_orphan_claim
--
-- RELATED:
--   - sweep_allow_pin_claims() — neutralizes all claims
--   - try_reclaim_orphan_claim() — restores matching claim
--   - allow_pin_claim_path() — generates claim file name
--
-- ============================================================================
local function list_allow_pin_claims(fingerprint)
	local claims = {}
	if not is_fp64(fingerprint) then
		return claims
	end
	local prefix = ".ocsp_revoke." .. fingerprint:lower() .. "."
	local ok_lfs, lfs = pcall(require, "lfs")
	if not ok_lfs or type(lfs) ~= "table" or not lfs.dir then
		return claims
	end
	local dir = "/var/cache/bunkerweb/ssl/ocsp-allow"
	pcall(function()
		for name in lfs.dir(dir) do
			if type(name) == "string" and name:sub(1, #prefix) == prefix and name:sub(-4) == ".tmp" then
				claims[#claims + 1] = dir .. "/" .. name
			end
		end
	end)
	return claims
end

-- Neutralize every .ocsp_revoke.{fp}.* claim. Write/revoke used to disarm only
-- their own claim path; a crashed peer's orphan (other pid/seq, often older gen)
-- then survived and either blocked handshakes as claim_inflight after the live
-- pin was DROPped, or let try_reclaim restore the wrong generation.
-- Returns true when no still-decodeable revoke claim remains.
-- ============================================================================
-- SWEEP_ALLOW_PIN_CLAIMS(fingerprint)
-- ============================================================================
-- PURPOSE:
--   Neutralizes all orphan claim files for a fingerprint (crash cleanup).
--   Prevents claim_inflight false refusals and wrong-gen reclaim races.
--
-- PARAMETERS:
--   fingerprint (string): certificate SPKI fingerprint (64-char hex)
--
-- RETURNS:
--   (true): all claims neutralized (no decodeable claims remain)
--   (false): one or more claims still valid (cleanup incomplete)
--
-- SIDE EFFECTS:
--   - Reads: list_allow_pin_claims() to enumerate claims
--   - Writes: calls neutralize_allow_claim() on each claim
--   - Logs: none (errors suppressed)
--   - Performance: O(n*m) where n = claims, m = avg neutralize time
--
-- DESIGN NOTES:
--   - Two-pass: neutralize all, then verify none remain decodeable
--   - Orphan cleanup: removes other-pid crashes (not just own claim)
--   - Idempotent: safe to call multiple times
--   - Crash-safe: failed neutralization returns false (caller retries)
--   - Called by: write_allow_pin (after successful install)
--   - Called by: drop_allow_pin (before file deletion)
--
-- RELATED:
--   - list_allow_pin_claims() — enumerates claims
--   - neutralize_allow_claim() — disarms one claim
--   - allow_pin_has_claim() — checks if claim exists
--
-- ============================================================================
local function sweep_allow_pin_claims(fingerprint)
	for _, claim in ipairs(list_allow_pin_claims(fingerprint)) do
		neutralize_allow_claim(claim, fingerprint)
	end
	for _, claim in ipairs(list_allow_pin_claims(fingerprint)) do
		if decode_allow_pin(read_file(claim)) then
			return false
		end
	end
	return true
end

-- If a claim still holds want (sha, gen) and the live pin path is empty, restore it.
-- ============================================================================
-- TRY_RECLAIM_ORPHAN_CLAIM(fingerprint, want_sha, want_g)
-- ============================================================================
-- PURPOSE:
--   Recover stranded allow-pin from orphan claim file (worker death during CAS).
--   Restores if generation matches and live path empty; prevents Must-Staple loss.
--
-- PARAMETERS:
--   fingerprint (string): certificate SPKI fingerprint (64-char hex)
--   want_sha (string): expected DER SHA256 (64-char hex)
--   want_g (number): expected soft recall generation
--
-- RETURNS:
--   (true): claim successfully restored to live path
--   (false): claim missing, generation mismatch, or live path pre-exists
--
-- SIDE EFFECTS:
--   - Reads: /var/cache/bunkerweb/ssl/ocsp-allow/.ocsp_revoke.* claims
--   - Calls: restore_claimed_pin() if claim matches generation
--   - Calls: invalidate_pin_caches() on successful restore
--   - Performance: ~1-5ms (claim scan + match check + restore)
--
-- DESIGN NOTES:
--   - Orphan detection: scans .ocsp_revoke.* for matching (sha, gen)
--   - Generation guard: only restores exact sha + gen match
--   - Empty-path guard: live path must be missing to avoid clobber
--   - First-match: restores first claim with matching generation
--   - Fleet safety: prevents Must-Staple from disappearing on crash
--   - Called by: peer_refuse_blocks() when pin missing during handshake
--
-- RELATED:
--   - restore_claimed_pin() — performs actual restoration
--   - list_allow_pin_claims() — scans for claim files
--   - allow_pin_matches() — checks generation match
--
-- ============================================================================
local function try_reclaim_orphan_claim(fingerprint, want_sha, want_g)
	local path = ocsp_allow_path(fingerprint)
	if path_exists(path) then
		return false
	end
	for _, claim in ipairs(list_allow_pin_claims(fingerprint)) do
		local pin = decode_allow_pin(read_file(claim))
		if allow_pin_matches(pin, want_sha, want_g) then
			if restore_claimed_pin(claim, path, fingerprint) then
				return true
			end
		end
	end
	return false
end

-- True when a still-decodeable revoke claim exists (poisoned "{}" litter does not
-- count — that is post-DROP debris, not an in-flight CAS).
-- ============================================================================
-- ALLOW_PIN_HAS_CLAIM(fingerprint)
-- ============================================================================
-- PURPOSE:
--   Checks if an in-flight CAS revocation claim exists (not false/poisoned).
--   Used by peer_refuse_blocks() to skip local refuse if fleet is revoke-in-progress.
--
-- PARAMETERS:
--   fingerprint (string): certificate SPKI fingerprint (64-char hex)
--
-- RETURNS:
--   (true): decodeable claim exists (CAS in progress, avoid dup revoke)
--   (false): no claim or only poisoned "{}" remains
--
-- SIDE EFFECTS:
--   - Reads: /var/cache/bunkerweb/ssl/ocsp-allow/.ocsp_revoke.* claims
--   - Cache: ngx.ctx.bw_ocsp_claim_cache per-request dedup
--   - Calls: list_allow_pin_claims(), decode_allow_pin()
--   - Performance: O(1) cache hit, O(n) claim scan on miss
--
-- DESIGN NOTES:
--   - Tri-state claim: decodeable (in-flight), poisoned "{}" (done), missing (success)
--   - Per-request cache: avoids duplicate scans in same handshake
--   - Poisoned filter: decode_allow_pin rejects "{}", counts as false
--   - Race safety: handshake refuses KEEP if claim exists (don't race revoke)
--   - Cache invalidation: cleared by invalidate_pin_caches() after revoke
--
-- RELATED:
--   - list_allow_pin_claims() — enumerates claims
--   - decode_allow_pin() — checks if poisoned
--   - peer_refuse_blocks() — uses to avoid dup revoke
--
-- ============================================================================
local function allow_pin_has_claim(fingerprint)
	if not is_fp64(fingerprint) then
		return false
	end
	fingerprint = fingerprint:lower()

	-- Initialize per-request cache on first use
	local ctx = ngx.ctx
	if ctx and not ctx.bw_ocsp_claim_cache then
		ctx.bw_ocsp_claim_cache = {}
	end

	-- Check per-request cache first
	if ctx and ctx.bw_ocsp_claim_cache then
		local cached = ctx.bw_ocsp_claim_cache[fingerprint]
		if cached ~= nil then
			-- Cache stores: false (no reclaimable claims) or true (claims exist)
			return cached == true
		end
	end

	-- Cache miss: scan directory for decodeable claims only
	local has_claims = false
	for _, claim in ipairs(list_allow_pin_claims(fingerprint)) do
		if decode_allow_pin(read_file(claim)) then
			has_claims = true
			break
		end
	end
	if ctx and ctx.bw_ocsp_claim_cache then
		ctx.bw_ocsp_claim_cache[fingerprint] = has_claims
	end
	return has_claims
end

-- Unconditional drop of allow-pin and legacy refuse (admin/job cleanup only).
-- Unlike revoke_allow_pin (handshake CAS-delete), this does NOT check generation match
-- and does NOT preserve concurrent updates. Only safe when caller knows the body gen is gone.
--
-- USE CASES:
--   - Job restamp after certificate rotation (old gen is definitely gone)
--   - Admin clear-peer-refuse command (explicit operator request)
--   - Soft-recall cleanup (generation explicitly bumped via pin rewrite)
--
-- WHY NOT HANDSHAKE: Handshakes use revoke_allow_pin (CAS-delete with gen match)
--   because concurrent handshakes may be pushing newer generations. Blind drop
--   would race the canary and remove a pin that handshakes still need.
--
-- SWEEPS ORPHAN CLAIMS:
--   Also walks .ocsp_revoke.{fp}.* claim files and neutralizes/unlinks them.
--   Leaving claim litter allows try_reclaim_orphan_claim to resurrect a pin
--   the job just dropped (worker-death mid-CAS debris).
--
-- @param fingerprint: SHA256 hex (fp64)
-- @return: true if unlinked successfully (or ENOENT means it was already gone), false on permissions error
-- @note: Ignores job/admin calls — both are trusted to know generation is truly gone
--
-- Performance: O(1) for the pin + O(d) for sweep where d = claim count (typically 0-2)
-- Called by: job scheduler during restamp, admin via clear-peer-refuse endpoint
--
-- Safety: Does NOT store in shared state (compare-and-delete). Use for off-path cleanup only.
-- ============================================================================
-- DROP_ALLOW_PIN(fingerprint)
-- ============================================================================
-- PURPOSE:
--   Job-time unconditional pin deletion with orphan claim cleanup.
--   No generation matching; used when renewing cert or clearing cache.
--
-- PARAMETERS:
--   fingerprint (string): certificate SPKI fingerprint (64-char hex)
--
-- RETURNS:
--   (true, nil): pin successfully deleted (or already missing)
--   (false, reason): on failure with error code:
--     - "invalid_fingerprint": bad fingerprint format
--     - "claim_unlink_failed": failed to clean claim files
--     - os.remove error message: filesystem error
--
-- SIDE EFFECTS:
--   - Reads: /var/cache/bunkerweb/ssl/ocsp-allow/{fp} directory
--   - Writes: unlinks /ocsp-allow/{fp}, sweeps .ocsp_revoke.* claims
--   - Calls: sweep_allow_pin_claims(), invalidate_pin_caches()
--   - Logs: none (errors returned not logged)
--   - Performance: ~1-5ms (directory scan + unlinks)
--
-- DESIGN NOTES:
--   - Unconditional: no generation check (not CAS, just cleanup)
--   - Claim sweep: removes orphaned revoke claims to prevent reclaim
--   - Best-effort: ignores "No such file" errors (idempotent)
--   - Legacy cleanup: removes old ocsp_refuse_path_legacy files
--   - Cache invalidation: clears ngx.ctx caches after delete
--
-- RELATED:
--   - revoke_allow_pin() — handshake-time CAS deletion
--   - sweep_allow_pin_claims() — cleans orphan revoke files
--   - invalidate_pin_caches() — clears request caches
--
-- ============================================================================
local function drop_allow_pin(fingerprint)
	if not is_fp64(fingerprint) then
		return false, "invalid_fingerprint"
	end
	fingerprint = fingerprint:lower()
	local path = ocsp_allow_path(fingerprint)
	local ok, err = os.remove(path)
	if not ok and err and not tostring(err):find("No such file", 1, true) then
		return false, tostring(err)
	end
	if not sweep_allow_pin_claims(fingerprint) then
		invalidate_pin_caches(fingerprint)
		return false, "claim_unlink_failed"
	end
	-- Legacy refuse cleanup is job-side; best-effort here for admin clear.
	os.remove(ocsp_refuse_path_legacy(fingerprint))
	invalidate_pin_caches(fingerprint)
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
--
-- CAS STATE MACHINE (Compare-And-Delete):
--   1. Read live pin from disk (fast path checks for match)
--   2. Upgrade-grace guard: handshake_drop=true KEEP gen-0 pins (job can clear them)
--   3. Match check: if pin.gen != want_gen → early exit (pin moved, another worker won)
--   4. Rename /ocsp-allow/{fp} → /ocsp-allow/.ocsp_revoke.{fp}.{pid}.{seq}.tmp (atomic claim)
--   5. Re-verify claimed file (detect race: job restamped between read and rename)
--   6. If race-detected: restore_claimed_pin (new pin to path, disarm claim)
--   7. Neutralize claim (unlink, rename to .dead, or poison "{}") → prevent reclaim
--   8. Sweep orphan claims (.ocsp_revoke.{fp}.* from peer crashes) → prevent stale resurrect
--   9. Cache per-request revoke outcome (prevent duplicate CAS in same handshake)
--
-- Returns outcome: "allow_dropped" | "allow_kept_gen_moved" | "allow_absent"
--   | "allow_drop_eacces" | "allow_drop_failed" | "allow_kept_gen0_grace"
-- handshake_drop=true: refuse to CAS soft_recall_gen=0 upgrade-grace pins
-- (only job drop_allow_pin may clear those). Soft-recall not_paged cleanup
-- passes handshake_drop=false so leftover gen-0 pins can still be revoked.
-- Per-request revoke cache avoids re-runs in the same handshake.
-- Always destroy the claim on successful DROP — leaving it let
-- try_reclaim_orphan_claim restore a just-revoked pin for up to ~60s.
-- ============================================================================
-- REVOKE_ALLOW_PIN(fingerprint, want_sha, want_gen, refuse_cause, quiet, handshake_drop)
-- ============================================================================
-- PURPOSE:
--   Compare-and-delete allow-pin (CAS revocation with generation safety).
--   Only deletes pin if generation still matches; prevents races with job.
--
-- PARAMETERS:
--   fingerprint (string): certificate SPKI fingerprint (64-char hex)
--   want_sha (string): expected DER SHA256 (64-char hex) before delete
--   want_gen (number|nil): generation counter (0 if omitted)
--   refuse_cause (string|nil): reason for refusal (logged on drop)
--   quiet (boolean|nil): if true, suppress NOTICE logging
--   handshake_drop (boolean|nil): if true, refuse to delete gen-0 pins
--
-- RETURNS:
--   (string): outcome code:
--     - "allow_dropped": pin successfully deleted
--     - "allow_kept_gen_moved": pin has newer generation
--     - "allow_absent": pin already missing
--     - "allow_drop_eacces": permission denied
--     - "allow_drop_failed": validation error
--     - "allow_kept_gen0_grace": upgrade-grace protected
--
-- SIDE EFFECTS:
--   - Reads: /var/cache/bunkerweb/ssl/ocsp-allow/{fp} (pin file)
--   - Writes: atomic rename to claim file, then unlink
--   - Calls: restore_claimed_pin(), neutralize_claim(), sweep_orphans
--   - Logs: NOTICE on success, ERROR on failure (unless quiet)
--   - Performance: ~1-5ms (file I/O + rename)
--
-- DESIGN NOTES:
--   - CAS: read → claim (rename to .ocsp_revoke.*) → verify → delete
--   - Gen guard: only deletes if pin.gen == want_gen
--   - Grace protection: handshake_drop=true refuses gen-0 pins
--   - Per-request cache: avoids duplicate CAS in handshake
--   - Orphan sweep: cleans .ocsp_revoke.* from crashes
--
-- RELATED:
--   - write_allow_pin() — publishes pin
--   - read_allow_pin() — reads published pin
--   - restore_claimed_pin() — restores if race detected
--
-- ============================================================================
local function revoke_allow_pin(fingerprint, want_sha, want_gen, refuse_cause, quiet, handshake_drop)
	if not is_fp64(fingerprint) then
		return "allow_drop_failed"
	end
	fingerprint = fingerprint:lower()
	if type(want_sha) ~= "string" then
		return "allow_drop_failed"
	end
	want_sha = want_sha:lower()
	if #want_sha ~= 64 or not want_sha:match("^[0-9a-f]+$") then
		return "allow_drop_failed"
	end
	-- Same hardening as write_allow_pin (no tonumber("1e2") / false→0 surprises).
	local want_g = soft_recall_gen_of({ soft_recall_gen = want_gen })
	if type(want_g) ~= "number" then
		return "allow_drop_failed"
	end

	-- Path B: Per-request cache to avoid re-running same revoke in same handshake
	local ctx = ngx.ctx
	if ctx and not ctx.bw_ocsp_revoke_cache then
		ctx.bw_ocsp_revoke_cache = {}
	end
	local cache_key = fingerprint .. "|" .. want_sha .. "|" .. tostring(want_g)
	if ctx and ctx.bw_ocsp_revoke_cache[cache_key] then
		return ctx.bw_ocsp_revoke_cache[cache_key]
	end
	-- Read-only fast path: most mismatches never touch the directory.
	local pin = read_allow_pin(fingerprint)
	if not pin then
		local outcome = "allow_absent"
		if ctx and ctx.bw_ocsp_revoke_cache then
			ctx.bw_ocsp_revoke_cache[cache_key] = outcome
		end
		return outcome
	end
	-- Upgrade-grace gen-0 pins: handshake DROP must not wipe the one-release pin
	-- every sibling still relies on. Job drop_allow_pin remains unconditional.
	if handshake_drop and want_g == 0 and type(pin.soft_recall_gen) == "number" and pin.soft_recall_gen == 0 then
		if not quiet then
			log(
				ngx.NOTICE,
				format_staple_decision("peer_refuse_bus", {
					tag = "OCSP_PEER_REFUSE_BUS",
					action = "allow_kept_gen0_grace",
					refuse_cause = tostring(refuse_cause or ""),
					fp = fingerprint:sub(1, 16) .. "...",
					der_sha256 = want_sha:sub(1, 16) .. "...",
					detail = "handshake_drop_blocked_on_gen0",
				})
			)
		end
		local outcome = "allow_kept_gen0_grace"
		if ctx and ctx.bw_ocsp_revoke_cache then
			ctx.bw_ocsp_revoke_cache[cache_key] = outcome
		end
		return outcome
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
		local outcome = "allow_kept_gen_moved"
		if ctx and ctx.bw_ocsp_revoke_cache then
			ctx.bw_ocsp_revoke_cache[cache_key] = outcome
		end
		return outcome
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
			local outcome = "allow_drop_eacces"
			if ctx and ctx.bw_ocsp_revoke_cache then
				ctx.bw_ocsp_revoke_cache[cache_key] = outcome
			end
			return outcome
		end
		-- ENOENT under us: drop the cached live pin so the next read sees absence.
		invalidate_pin_caches(fingerprint)
		local outcome = "allow_absent"
		if ctx and ctx.bw_ocsp_revoke_cache then
			ctx.bw_ocsp_revoke_cache[cache_key] = outcome
		end
		return outcome
	end
	-- We now exclusively own what was at `path` at rename time. If the job restamped
	-- between the read above and the rename, this is the newer pin: put it back.
	if not allow_pin_matches(decode_allow_pin(read_file(claim)), want_sha, want_g) then
		local restored = restore_claimed_pin(claim, path, fingerprint)
		-- Disk now holds N+1 (restored or peer); cached pre-claim pin was N.
		invalidate_pin_caches(fingerprint)
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
		local outcome = "allow_kept_gen_moved"
		if ctx and ctx.bw_ocsp_revoke_cache then
			ctx.bw_ocsp_revoke_cache[cache_key] = outcome
		end
		return outcome
	end
	-- Destroy the claim. neutralize may unlink, tomb, or poison "{}".
	-- If it cannot disarm a still-decodeable claim, try restore; if that also
	-- fails, neutralize again so try_reclaim cannot undo the DROP attempt.
	-- Then sweep ANY sibling crash litter for this fp (other pid/seq) — disarming
	-- only our claim left orphans that blocked as claim_inflight or reclaimed
	-- an older gen after the live pin was gone.
	if not neutralize_allow_claim(claim, fingerprint) then
		local restored = restore_claimed_pin(claim, path, fingerprint)
		if not restored and path_exists(claim) then
			neutralize_allow_claim(claim, fingerprint)
		end
		invalidate_pin_caches(fingerprint)
		if not quiet then
			log(
				ngx.ERR,
				format_staple_decision("peer_refuse_bus", {
					tag = "OCSP_PEER_REFUSE_BUS",
					action = "allow_drop_failed",
					refuse_cause = tostring(refuse_cause or ""),
					fp = fingerprint:sub(1, 16) .. "...",
					detail = restored and "claim_unlink_restored" or "claim_unlink_failed",
				})
			)
		end
		local outcome = "allow_drop_failed"
		if ctx and ctx.bw_ocsp_revoke_cache then
			ctx.bw_ocsp_revoke_cache[cache_key] = outcome
		end
		return outcome
	end
	if not sweep_allow_pin_claims(fingerprint) then
		invalidate_pin_caches(fingerprint)
		if not quiet then
			log(
				ngx.ERR,
				format_staple_decision("peer_refuse_bus", {
					tag = "OCSP_PEER_REFUSE_BUS",
					action = "allow_drop_failed",
					refuse_cause = tostring(refuse_cause or ""),
					fp = fingerprint:sub(1, 16) .. "...",
					detail = "sibling_claim_unlink_failed",
				})
			)
		end
		local outcome = "allow_drop_failed"
		if ctx and ctx.bw_ocsp_revoke_cache then
			ctx.bw_ocsp_revoke_cache[cache_key] = outcome
		end
		return outcome
	end
	invalidate_pin_caches(fingerprint)
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
	local outcome = "allow_dropped"
	if ctx and ctx.bw_ocsp_revoke_cache then
		ctx.bw_ocsp_revoke_cache[cache_key] = outcome
	end
	return outcome
end

-- ============================================================================
-- WRITE_ALLOW_PIN(fingerprint, der_sha256, soft_recall_gen, expires_unix)
-- ============================================================================
-- PURPOSE:
--   Publish allow-pin (generation identity) to disk via compare-and-stamp.
--   Only called from job/canary paths, never from handshake refuse.
--
-- PARAMETERS:
--   fingerprint (string): certificate SPKI fingerprint (64-char hex)
--   der_sha256 (string): OCSP response DER SHA256 (64-char hex)
--   soft_recall_gen (number|nil): generation counter (0 if omitted)
--   expires_unix (number): response expiry timestamp
--
-- RETURNS:
--   (true, nil): if pin successfully written
--   (false, reason): on failure with error code:
--     - "invalid_inputs": bad fingerprint or der_sha256
--     - "invalid_der_sha256": not 64-char hex
--     - "invalid_soft_recall_gen": unparseable generation
--     - "stale_generation": pin already has newer generation
--     - "atomic_rename_failed": filesystem error
--
-- SIDE EFFECTS:
--   - Writes: /var/cache/bunkerweb/ssl/ocsp-allow/{fp} JSON file
--   - CAS semantics: rename via temp file (atomic, avoids clobber)
--   - Logs: NOTICE on successful write
--   - Performance: ~1-5ms (file I/O + rename)
--
-- DESIGN NOTES:
--   - Job-only scope: never called from handshake paths
--   - Stale-gen guard: refuses to overwrite newer generation
--   - Atomic rename: prevents last-writer-wins clobber
--   - Temp file location: dotfile under ocsp-allow for cleanup sweep
--   - Payload: der_sha256 + soft_recall_gen (generation identity)
--
-- RELATED:
--   - read_allow_pin() — reads published pin
--   - revoke_allow_pin() — deletes pin via CAS
--   - allow_pin_tmp_path() — temp file naming
--
-- ============================================================================
-- Job/canary only — never call from handshake refuse paths.
-- Compare-and-stamp via claim: rename live pin aside, refuse if claimed gen is
-- strictly newer, then install tmp into the empty slot. Plain rename over a live
-- path is last-writer-wins and can clobber N+1 with N.
local function write_allow_pin(fingerprint, der_sha256, soft_recall_gen, expires_unix)
	if not is_fp64(fingerprint) or type(der_sha256) ~= "string" then
		return false, "invalid_inputs"
	end
	fingerprint = fingerprint:lower()
	local sha = der_sha256:lower()
	if #sha ~= 64 or not sha:match("^[0-9a-f]+$") then
		return false, "invalid_der_sha256"
	end
	-- Digit-only / finite non-negative only (no tonumber("1e2") surprises).
	local gen
	if soft_recall_gen == nil then
		gen = 0
	else
		gen = soft_recall_gen_of({ soft_recall_gen = soft_recall_gen })
		if type(gen) ~= "number" then
			return false, "invalid_soft_recall_gen"
		end
	end
	local path = ocsp_allow_path(fingerprint)
	-- Dotfile under ocsp-allow so job `**/.ocsp_*.tmp` sweep cleans crash litter
	-- (legacy `{fp}.tmp.{pid}` sat beside the live pin and was never swept).
	local tmp = allow_pin_tmp_path(fingerprint, "write")
	local payload_obj = {
		der_sha256 = sha,
		soft_recall_gen = gen,
		allowed_unix = ngx.time(),
		allowed_by = tostring((ngx.config and ngx.config.subsystem) or "job"),
	}
	if
		type(expires_unix) == "number"
		and expires_unix == expires_unix
		and expires_unix ~= math.huge
		and expires_unix ~= -math.huge
		and expires_unix > 0
	then
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

	-- Hold the live pin aside until tmp is installed. Deleting the claim first
	-- opened a window where rename failure erased the fleet pin, or a lagging
	-- writer could clobber a newer pin that landed in the empty slot.
	local claim = nil
	if path_exists(path) then
		claim = allow_pin_claim_path(fingerprint)
		local ok_c, c_err = os.rename(path, claim)
		if not ok_c then
			os.remove(tmp)
			return false, "claim:" .. tostring(c_err or "nil")
		end
		local claimed = decode_allow_pin(read_file(claim))
		if claimed and type(claimed.soft_recall_gen) == "number" and claimed.soft_recall_gen > gen then
			restore_claimed_pin(claim, path, fingerprint)
			os.remove(tmp)
			-- Disk holds the newer pin again; drop any pre-claim cached view.
			invalidate_pin_caches(fingerprint)
			return false, "stale_gen"
		end
	end

	-- Prefer hard link into an empty slot (EEXIST = peer won). Plain rename
	-- replaces an occupied path on Unix and would clobber a newer pin.
	-- If link fails with an empty slot (EXDEV / unsupported), fall back to rename.
	-- After link, tmp MUST be unlinked — a leftover hardlink would keep pin bytes
	-- reachable after DROP of path (same inode resurrection class as restore).
	local installed = false
	local install_err = nil
	do
		local ok_lfs, lfs = pcall(require, "lfs")
		if ok_lfs and type(lfs) == "table" and lfs.link and lfs.link(tmp, path) then
			os.remove(tmp)
			if path_exists(tmp) then
				os.remove(tmp)
			end
			if not path_exists(tmp) then
				installed = true
			else
				-- Dual hardlink: undo path name. Never poison tmp (shared inode).
				os.remove(path)
				if not path_exists(path) then
					install_err = "tmp_unlink_failed"
				else
					os.remove(tmp)
					if not path_exists(tmp) then
						installed = true
					else
						install_err = "tmp_unlink_failed"
					end
				end
			end
		elseif path_exists(path) then
			install_err = "slot_taken"
		else
			local ok_r, rename_err = os.rename(tmp, path)
			if ok_r then
				installed = true
			else
				install_err = tostring(rename_err or "nil")
			end
		end
	end
	if not installed then
		os.remove(tmp)
		if claim then
			if path_exists(path) then
				-- Peer filled the slot; disarm our claim so it cannot be reclaimed
				-- after a later DROP of the peer's pin (same as restore_claimed_pin).
				neutralize_allow_claim(claim, fingerprint)
				invalidate_pin_caches(fingerprint)
				return false, "stale_gen"
			end
			restore_claimed_pin(claim, path, fingerprint)
			invalidate_pin_caches(fingerprint)
		end
		return false, "rename:" .. tostring(install_err or "nil")
	end
	-- Sweep all revoke claims for this fp (our aside-claim and any foreign
	-- crash litter). Own-claim-only cleanup left orphans that resurfaced as
	-- claim_inflight / wrong-gen reclaim after a later DROP of this pin.
	sweep_allow_pin_claims(fingerprint)
	-- Legacy refuse must not shadow allow polarity (job write path only).
	os.remove(ocsp_refuse_path_legacy(fingerprint))
	invalidate_pin_caches(fingerprint)
	return true
end

-- ============================================================================
-- ENSURE_OCSP_BUS_DIRS()
-- ============================================================================
-- PURPOSE:
--   Creates OCSP bus directories (allow, ligand, refuse) with safe permissions.
--   Called at startup; safe to call multiple times (idempotent).
--
-- PARAMETERS:
--   (none)
--
-- RETURNS:
--   (true): all directories created or already present
--   (false): one or more directories failed to create
--
-- SIDE EFFECTS:
--   - Writes: mkdir -p /var/cache/bunkerweb/ssl/ocsp-{allow,ligand,refuse}
--   - Writes: chmod on each directory for access control
--   - Logs: none (errors suppressed)
--   - Performance: ~1-10ms (filesystem ops)
--
-- DESIGN NOTES:
--   - Multi-purpose: creates three related bus directories in one call
--   - Safe-create: lfs.mkdir returns false if exists (no error)
--   - Permissions: set for shared access (handshake + job paths)
--   - Idempotent: safe to call at startup and in error paths
--   - Best-effort: failure logged but does not block startup
--
-- RELATED:
--   - ocsp_allow_path() — assumes /ocsp-allow exists
--   - ligand_path() (ocsp_store.lua) — assumes /ocsp-ligand exists
--   - ocsp_refuse_path_legacy() — assumes /ocsp-refuse exists
--
-- ============================================================================
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
-- ============================================================================
-- ENSURE_OCSP_REFUSE_DIR()
-- ============================================================================
-- PURPOSE:
--   Backward-compatibility wrapper for ensure_ocsp_bus_dirs().
--   Creates OCSP refuse directory (and related bus dirs) for older callers.
--
-- PARAMETERS:
--   (none)
--
-- RETURNS:
--   (true): all directories created or already present
--   (false): one or more directories failed to create
--
-- SIDE EFFECTS:
--   - Calls: ensure_ocsp_bus_dirs() (creates allow, ligand, refuse)
--   - Writes: mkdir -p /var/cache/bunkerweb/ssl/ocsp-refuse (+ others)
--   - Performance: ~1-10ms (filesystem ops)
--
-- DESIGN NOTES:
--   - Legacy name: "refuse_dir" from old refuse-pin era
--   - Now creates all three: allow, ligand, refuse (via ensure_ocsp_bus_dirs)
--   - Backward compat: older callers continue to work unchanged
--   - Idempotent: safe to call multiple times (no-op if directories exist)
--   - Re-exported: public function _M.ensure_ocsp_refuse_dir() calls this
--
-- RELATED:
--   - ensure_ocsp_bus_dirs() — actual implementation (creates all 3 dirs)
--   - _M.ensure_ocsp_refuse_dir() — public export
--
-- ============================================================================
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
-- Reject NaN / ±inf so a corrupt pin cannot claim immortality.
-- ============================================================================
-- ALLOW_PIN_EXPIRED(pin)
-- ============================================================================
-- PURPOSE:
--   Checks if allow-pin has passed TTL (expires_unix or allowed_unix + window).
--   Fails closed on corrupt input (NaN, inf, missing); expired = refuse KEEP.
--
-- PARAMETERS:
--   pin (table|nil): {expires_unix: number, allowed_unix: number}
--
-- RETURNS:
--   (true): pin expired or invalid (refuse locally, don't delete)
--   (false): pin still fresh (within TTL)
--
-- SIDE EFFECTS:
--   - Reads: pin.expires_unix, pin.allowed_unix (from decoded allow-pin)
--   - Reads: ngx.time(), OCSP_CLOCK_SKEW_SECONDS, ALLOW_PIN_TTL_SECONDS
--   - Logs: none
--   - Performance: O(1) time check
--
-- DESIGN NOTES:
--   - Dual TTL: expires_unix (primary, from OCSP) or allowed_unix + window
--   - Clock skew guard: subtracts OCSP_CLOCK_SKEW_SECONDS (same as resp_still_fresh)
--   - Fail-closed: NaN, ±inf, zero, or missing → expired (refuse)
--   - NaN detection: exp == exp (NaN fails this check)
--   - Inf detection: explicit math.huge checks
--   - Positive-only: exp > 0 guard prevents negative TTL bypass
--   - KEEP semantics: expired pin locally refused but not deleted (race safe)
--
-- RELATED:
--   - resp_still_fresh() (ocsp_store.lua) — same clock skew logic
--   - peer_refuse_blocks() — calls to validate freshness
--   - OCSP_CLOCK_SKEW_SECONDS, ALLOW_PIN_TTL_SECONDS (constants)
--
-- ============================================================================
local function allow_pin_expired(pin)
	if type(pin) ~= "table" then
		return true
	end
	local exp = pin.expires_unix
	if type(exp) == "number" and exp == exp and exp ~= math.huge and exp ~= -math.huge and exp > 0 then
		return ngx.time() >= (math.floor(exp) - OCSP_CLOCK_SKEW_SECONDS)
	end
	local t = pin.allowed_unix
	if type(t) ~= "number" or t ~= t or t == math.huge or t == -math.huge then
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
-- Soft-recall / unpaged before generation identity — control keys often lack
-- der_sha256 (negative-only meta). Checking after the sha early-return made
-- intermediate soft-recall invisible (Must-Staple fail-open until tombstone).
-- ============================================================================
-- PEER_REFUSE_BLOCKS(fingerprint, meta, resp, quiet)
-- ============================================================================
-- PURPOSE:
--   Handshake-time allow-pin validation (inverted bus read semantics).
--   Decides whether Must-Staple peer consensus allows or blocks stapling.
--
-- PARAMETERS:
--   fingerprint (string): certificate SPKI fingerprint (64-char hex)
--   meta (table|nil): metadata from L1 cache or ligand
--   resp (table|nil): OCSP response object with der_sha256, soft_recall_gen
--   quiet (boolean|nil): if true, suppress ERROR logging
--
-- RETURNS:
--   (nil): allow (pin matches, not expired, consensus OK)
--   (string): refuse reason code:
--     - "allow_pin_missing": no pin on disk (Must-Staple fail-closed)
--     - "allow_pin_mismatch": generation or DER mismatch (refuse, DROP)
--     - "allow_pin_expired": pin expired (refuse KEEP, don't DELETE)
--     - "allow_pin_claim_inflight": CAS revocation in progress (KEEP)
--     - "gen_type_drift": soft_recall_gen not number (type error)
--     - "not_paged": shard unpaged / soft-recall mode (KEEP)
--
-- SIDE EFFECTS:
--   - Reads: /var/cache/bunkerweb/ssl/ocsp-allow/{fp}
--   - Reads: L1 cache (ligand_or_meta), OCSP response metadata
--   - Calls: read_allow_pin(), allow_pin_matches(), try_reclaim_orphan_claim()
--   - Logs: ERROR on refuse (unless quiet)
--   - Performance: ~0.5-2ms (file read + comparison)
--
-- DESIGN NOTES:
--   - Inverted bus: missing pin = refuse (opposite of allowlist)
--   - Generation matching: only allows if sha + recall_gen match exactly
--   - Soft-recall guard: refuse BUT do not revoke (no CAS) to prevent races
--   - Unpaged handling: soft-recall revokes only the matching (sha, gen) pair
--   - Orphan recovery: try_reclaim_orphan_claim restores stranded pins
--   - Must-Staple coordination: fail-closed without gen (no auth proof)
--
-- RELATED:
--   - read_allow_pin() — reads pin from disk
--   - allow_pin_matches() — checks sha + gen match
--   - should_skip_peer_bus() — filters which refuse reasons enter bus
--   - record_peer_refuse() — publishes refuse to HTTP↔stream bus
--
-- ============================================================================
local function peer_refuse_blocks(fingerprint, meta, resp, quiet)
	-- Fail closed without a bus key: generation_tuple(resp) can still yield a sha
	-- when meta is nil, and fingerprint:sub in logs would throw on nil/garbage.
	if not is_fp64(fingerprint) then
		return "allow_pin_missing"
	end
	fingerprint = fingerprint:lower()
	meta = ligand_or_meta(meta, fingerprint)
	if type(meta) == "table" and (shard_not_paged(meta, fingerprint) or meta.unpaged_after_nongood == true) then
		local sha, recall_gen = generation_tuple(meta, resp)
		if sha and type(recall_gen) == "number" then
			-- Soft-recall / unpaged: revoke leftover allow for THIS (sha, gen) only so
			-- a lagging worker cannot erase a re-canaried pin (same DER, newer gen).
			-- handshake_drop=false: soft-recall cleanup may clear leftover gen-0 pins.
			revoke_allow_pin(fingerprint, sha, recall_gen, "not_paged", quiet, false)
		end
		-- Non-nil so a caller that skips shard_not_paged cannot staple this generation.
		return "not_paged"
	end
	local sha, recall_gen = generation_tuple(meta, resp)
	if not sha then
		-- Must-Staple without a generation cannot prove allow — fail closed.
		if type(meta) == "table" and (meta.must_staple == true or meta.paged == true) then
			return "allow_pin_missing"
		end
		return nil
	end
	-- Type-drift soft_recall_gen: refuse locally, KEEP fleet pin (no CAS).
	if type(recall_gen) ~= "number" then
		if not quiet then
			log(
				ngx.ERR,
				"OCSP soft_recall_gen type drift fp=" .. fingerprint:sub(1, 16) .. "... der=" .. sha:sub(1, 16) .. "..."
			)
		end
		return "gen_type_drift"
	end
	local pin = read_allow_pin(fingerprint)
	if not pin then
		-- Worker death mid-revoke may leave a matching claim with an empty live path.
		if try_reclaim_orphan_claim(fingerprint, sha, recall_gen) then
			-- Reclaim restored disk; drop the cached false "missing" sentinel or the
			-- re-read below still reports allow_pin_missing / claim_inflight wrongly.
			invalidate_pin_caches(fingerprint)
			pin = read_allow_pin(fingerprint)
		end
	end
	if not pin then
		-- Claim still present but not ours (or empty): another revoke is in flight —
		-- refuse locally without DROP (KEEP). Avoids racing the claim owner.
		if allow_pin_has_claim(fingerprint) then
			if not quiet then
				log(
					ngx.ERR,
					"OCSP allow-pin claim inflight fp="
						.. fingerprint:sub(1, 16)
						.. "... der="
						.. sha:sub(1, 16)
						.. "... soft_recall_gen="
						.. tostring(recall_gen)
				)
			end
			return "allow_pin_claim_inflight"
		end
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
	if not allow_pin_matches(pin, sha, recall_gen) then
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

-- Soft fuse: continue without touching the allow pin.
-- normal: revoke allow for DROP_ALLOW refuse_cause so sibling Must-Staple fails closed.
--
-- Transient causes must not enter the peer bus (HTTP↔stream).
-- skip is derived from KEEP_ALLOW_ON_REFUSE (plus unpaged / set_staple arms)
-- so the hand list cannot drift from ocsp_common policy tables.
-- ============================================================================
-- SHOULD_SKIP_PEER_BUS(detail, meta, fingerprint)
-- ============================================================================
-- PURPOSE:
--   Policy check: decide if refuse reason should skip the HTTP↔stream bus.
--   Filters transient causes (clock, cache misses) from peer consensus.
--
-- PARAMETERS:
--   detail (string|nil): refuse reason code (e.g., "allow_pin_missing")
--   meta (table|nil): metadata with paged, must_staple flags
--   fingerprint (string|nil): cert SPKI fingerprint (used to resolve meta)
--
-- RETURNS:
--   (true): skip peer bus (local refuse only, don't publish)
--   (false): enter peer bus (allow revocation via record_peer_refuse)
--
-- SIDE EFFECTS:
--   - Reads: ligand_or_meta(meta, fingerprint)
--   - Reads: KEEP_ALLOW_ON_REFUSE policy table from ocsp_common
--   - Logs: none
--   - Performance: O(1) table lookup
--
-- DESIGN NOTES:
--   - Policy-driven: derives skip list from KEEP_ALLOW_ON_REFUSE in ocsp_common
--   - Unpaged guard: unpaged shards always skip (soft-recall mode)
--   - Set-staple exception: paged set_staple_* failures also skip
--   - Hard-gate: prevents races where HTTP forgets outer skip check
--   - Must-staple coordinate: fail-closed without bus (no fleet consensus)
--
-- RELATED:
--   - record_peer_refuse() — publishes to peer bus if not skipped
--   - peer_refuse_blocks() — handshake validation
--   - KEEP_ALLOW_ON_REFUSE (ocsp_common) — policy table
--
-- ============================================================================
local function should_skip_peer_bus(detail, meta, fingerprint)
	local d = tostring(detail or "unmet")
	local eff = meta
	if type(fingerprint) == "string" and is_fp64(fingerprint) then
		eff = ligand_or_meta(meta, fingerprint)
	end
	-- Derive from KEEP_ALLOW so skip cannot drift ahead of / behind the policy table.
	-- Unpaged shards and paged set_staple_* failures also skip (local refuse only).
	if KEEP_ALLOW_ON_REFUSE[d] then
		return true
	end
	if type(eff) == "table" and eff.paged ~= true then
		return true
	end
	if (d == "set_staple_failed" or d == "set_staple_exception") and type(eff) == "table" and eff.paged == true then
		return true
	end
	return false
end

-- Handshake refuse: DROP allow pin for DROP_ALLOW causes via compare-and-delete.
-- refuse_cause is the raw pre-alias detail (logged); runbook staple_decision=
-- stays separate. Pin-state / clock causes are KEEP — this worker's view must
-- not revoke a pin HTTP, stream, and every sibling rely on.
-- Hard-gates should_skip_peer_bus first so HTTP/stream callers that forget the
-- outer skip check still cannot wipe the fleet pin on transient causes.
-- ============================================================================
-- RECORD_PEER_REFUSE(fingerprint, meta, resp, decision)
-- ============================================================================
-- PURPOSE:
--   Handshake-time allow-pin revocation via peer bus (HTTP↔stream consensus).
--   Publishes refuse decision to fleet; called when Must-Staple validation fails.
--
-- PARAMETERS:
--   fingerprint (string): certificate SPKI fingerprint (64-char hex)
--   meta (table|nil): metadata with paged, must_staple, der_sha256
--   resp (string|nil): OCSP response DER body (for generation tuple)
--   decision (string): refuse reason (e.g., "allow_pin_missing")
--
-- RETURNS:
--   (true): pin revoked via CAS (fleet consensus published)
--   (false): skipped (transient cause, no KEEP guard, or policy reject)
--
-- SIDE EFFECTS:
--   - Reads: should_skip_peer_bus(), ligand_or_meta(), policy tables
--   - Reads: DROP_ALLOW_ON_REFUSE, KEEP_ALLOW_ON_REFUSE (ocsp_common)
--   - Calls: revoke_allow_pin() if decision requires DROP
--   - Logs: DEBUG on keep, ERROR on invalid input, NOTICE on success
--   - Performance: ~1-5ms (policy lookup + CAS call if needed)
--
-- DESIGN NOTES:
--   - Policy-gated: should_skip_peer_bus() filters transient causes
--   - DROP variants: canary_*, shared_ligand_* cause revocation
--   - KEEP safety: refuses to drop pin for clock/cache reasons
--   - Meta-only: some causes revoke meta/pin gen, not resp gen
--   - Generation tuple: combines meta + resp for unified generation
--   - Prefix variants: canary_* and shared_ligand_* are aliased
--
-- RELATED:
--   - should_skip_peer_bus() — policy filter (pre-gate)
--   - peer_refuse_blocks() — handshake validation
--   - revoke_allow_pin() — performs CAS deletion
--   - DROP_ALLOW_ON_REFUSE, KEEP_ALLOW_ON_REFUSE (ocsp_common)
--
-- ============================================================================
local function record_peer_refuse(fingerprint, meta, resp, decision)
	if should_skip_peer_bus(decision, meta, fingerprint) then
		return false
	end
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
	-- META_ONLY causes revoke the meta/pin generation, not a possibly-mismatched body.
	local gen_resp = resp
	if META_ONLY_DROP_ALLOW[refuse_cause] then
		gen_resp = nil
	end
	local sha, recall_gen = generation_tuple(meta, gen_resp)
	if not sha or type(recall_gen) ~= "number" then
		log(
			ngx.DEBUG,
			"OCSP allow-pin keep (no generation for compare-and-delete) refuse_cause="
				.. refuse_cause
				.. " fp="
				.. fp_short
		)
		return false
	end
	-- handshake_drop=true: never wipe soft_recall_gen=0 upgrade-grace pins.
	local outcome = revoke_allow_pin(fingerprint, sha, recall_gen, refuse_cause, false, true)
	return outcome == "allow_dropped"
end

-- ============================================================================
-- MUST_STAPLE_REFUSE(fingerprint, meta, resp, detail, mode)
-- ============================================================================
-- PURPOSE:
--   Handshake-time Must-Staple refusal with soft-fuse mode awareness.
--   Records peer refusal; respects soft-fuse modes that suppress peer bus.
--
-- PARAMETERS:
--   fingerprint (string): certificate SPKI fingerprint (64-char hex)
--   meta (table|nil): metadata with must_staple flag
--   resp (string|nil): OCSP response DER body
--   detail (string|nil): refuse reason (e.g., "allow_pin_missing")
--   mode (string|nil): soft-fuse mode: "staple_only", "open", or nil (normal)
--
-- RETURNS:
--   (false, "must_staple", detail): always returns false with Must-Staple detail
--
-- SIDE EFFECTS:
--   - Calls: should_skip_peer_bus() — policy filter
--   - Calls: record_peer_refuse() — if not staple_only/open mode
--   - Logs: via record_peer_refuse (if called)
--   - Performance: ~1-5ms (policy check + optional bus write)
--
-- DESIGN NOTES:
--   - Soft-fuse: staple_only/open modes skip peer bus (local refuse only)
--   - Normal mode: publishes refuse to HTTP↔stream consensus
--   - Policy-gated: should_skip_peer_bus filters transient causes
--   - Return: always false (Must-Staple enforced), detail for logging
--   - Caller: stream/HTTP Must-Staple enforcement handlers
--
-- RELATED:
--   - should_skip_peer_bus() — policy filter
--   - record_peer_refuse() — bus publisher
--   - peer_refuse_blocks() — handshake validation
--
-- ============================================================================
local function must_staple_refuse(fingerprint, meta, resp, detail, mode)
	if mode ~= "staple_only" and mode ~= "open" then
		local d = detail or "unmet"
		if not should_skip_peer_bus(d, meta, fingerprint) then
			record_peer_refuse(fingerprint, meta, resp, d)
		end
	end
	return false, "must_staple", detail or "unmet"
end

-- Skip ngx.ocsp.validate only when ligand+paged AND live allow-pin matches this
-- generation. Ligand-alone would skip crypto after soft-fuse / pin revoke while
-- CLI canary bits still say paged — that reopens Must-Staple without fleet proof.
-- Store.canary_paged_body_ok stays ligand-only (require DAG); this is the public
-- handshake predicate re-exported as bunkerweb.ocsp.canary_paged_body_ok.
-- ============================================================================
-- CANARY_TRUST_OK(meta, fingerprint, resp)
-- ============================================================================
-- PURPOSE:
--   Validates canary paged body for skipping ngx.ocsp.validate (crypto optimization).
--   Must verify both ligand AND live allow-pin to prove fleet consensus.
--
-- PARAMETERS:
--   meta (table|nil): metadata with canary flags from store
--   fingerprint (string): certificate SPKI fingerprint (64-char hex)
--   resp (string|nil): OCSP response DER body (for generation tuple)
--
-- RETURNS:
--   (true): ligand paged + allow-pin generation match + pin fresh (safe to skip)
--   (false): mismatch or expired; must run ngx.ocsp.validate
--
-- SIDE EFFECTS:
--   - Reads: store.canary_paged_body_ok() — ligand validation
--   - Reads: read_allow_pin() — live pin validation
--   - Calls: generation_tuple(), allow_pin_matches(), allow_pin_expired()
--   - Performance: ~1-3ms (cache hit), ~2-5ms (cache miss + pin read)
--
-- DESIGN NOTES:
--   - Two-proof: ligand alone insufficient (soft-fuse race), pin alone invalid
--   - Dual validation: both ligand AND pin must agree on generation
--   - Crypto skip: only safe if fleet consensus proven via pin match
--   - Expiry guard: refused if pin expired (clock skew applied)
--   - Public export: re-exported as canary_paged_body_ok for handshake use
--   - Prevents: Must-Staple bypass via soft-fuse / pin revoke desync
--
-- RELATED:
--   - store.canary_paged_body_ok() — ligand-only check
--   - read_allow_pin() — reads fleet pin
--   - allow_pin_matches() — validates generation match
--
-- ============================================================================
local function canary_trust_ok(meta, fingerprint, resp)
	if not store.canary_paged_body_ok(meta, fingerprint, resp) then
		return false
	end
	local sha, gen = generation_tuple(ligand_or_meta(meta, fingerprint), resp)
	if not sha or type(gen) ~= "number" then
		return false
	end
	local pin = read_allow_pin(fingerprint)
	if not allow_pin_matches(pin, sha, gen) then
		return false
	end
	if allow_pin_expired(pin) then
		return false
	end
	return true
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

-- Public skip-validate: ligand+paged + live allow-pin generation match.
function _M.canary_paged_body_ok(meta, fingerprint, resp)
	return canary_trust_ok(meta, fingerprint, resp)
end

-- Back-compat: clear = drop allow pin (+ legacy refuse).
function _M.clear_peer_refuse(fingerprint)
	return drop_allow_pin(fingerprint)
end

_M.internal = {
	canary_trust_ok = canary_trust_ok,
	ensure_ocsp_bus_dirs = ensure_ocsp_bus_dirs,
	must_staple_refuse = must_staple_refuse,
	peer_refuse_blocks = peer_refuse_blocks,
}

return _M
