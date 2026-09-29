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
local function ligand_or_meta(_meta, fingerprint)
	return ligand_or_meta_uncached(nil, fingerprint)
end

-- DROP/KEEP tables live in ocsp_common (STAPLE_POLICY). Prefix rules stay here:
-- canary_* defaults DROP; shared_ligand_* DROP unless KEEP on the stripped suffix.
-- Invariant: every cause should_skip_peer_bus returns true for must also be KEEP.

local function ocsp_allow_path(fingerprint)
	-- Lowercase so uppercase hex cannot fork a parallel pin path vs the job.
	return "/var/cache/bunkerweb/ssl/ocsp-allow/" .. fingerprint:lower()
end

-- Legacy refuse path — job-side cleanup only after the allow-pin invert.
local function ocsp_refuse_path_legacy(fingerprint)
	return "/var/cache/bunkerweb/ssl/ocsp-refuse/" .. fingerprint:lower()
end

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

local function allow_pin_claim_path(fingerprint)
	return allow_pin_tmp_path(fingerprint, "revoke")
end

-- Destroy or disarm a sticky claim so try_reclaim cannot restore it.
-- Order: unlink → rename out of .ocsp_revoke.* → poison decode with "{}".
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

-- Unconditional drop (job / admin / soft-recall cleanup that already knows the
-- generation is gone). Handshake refuse paths must use revoke_allow_pin instead.
-- Checks os.remove's nil,err return — pcall alone never sees EACCES.
-- Also sweeps .ocsp_revoke.{fp}.* claim litter: leaving it let try_reclaim
-- resurrect a pin the job/admin just cleared (worker-death mid-revoke debris).
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
-- Returns outcome: "allow_dropped" | "allow_kept_gen_moved" | "allow_absent"
--   | "allow_drop_eacces" | "allow_drop_failed" | "allow_kept_gen0_grace"
-- handshake_drop=true: refuse to CAS soft_recall_gen=0 upgrade-grace pins
-- (only job drop_allow_pin may clear those). Soft-recall not_paged cleanup
-- passes handshake_drop=false so leftover gen-0 pins can still be revoked.
-- Per-request revoke cache avoids re-runs in the same handshake.
-- Always destroy the claim on successful DROP — leaving it let
-- try_reclaim_orphan_claim restore a just-revoked pin for up to ~60s.
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
-- Reject NaN / ±inf so a corrupt pin cannot claim immortality.
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
