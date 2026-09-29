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
local ligand_or_meta = store.ligand_or_meta
local shard_not_paged = store.shard_not_paged
local soft_recall_gen_of = store.soft_recall_gen_of

-- Transient allow-pin TTL when expires_unix is absent (align with L1).
local ALLOW_PIN_TTL_SECONDS = L1_MAX_TTL

-- DROP/KEEP tables live in ocsp_common (STAPLE_POLICY). Prefix rules stay here:
-- canary_* defaults DROP; shared_ligand_* DROP unless KEEP on the stripped suffix.
-- Invariant: every cause should_skip_peer_bus returns true for must also be KEEP.

local function ocsp_allow_path(fingerprint)
	return "/var/cache/bunkerweb/ssl/ocsp-allow/" .. fingerprint
end

-- Legacy refuse path — job-side cleanup only after the allow-pin invert.
local function ocsp_refuse_path_legacy(fingerprint)
	return "/var/cache/bunkerweb/ssl/ocsp-refuse/" .. fingerprint
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
	obj.soft_recall_gen = soft_recall_gen_of(obj)
	return obj
end

-- Read allow-pin with per-request dedup cache (ngx.ctx)
-- Avoids re-reading the same file within a single handshake
local function read_allow_pin(fingerprint)
	if not is_fp64(fingerprint) then
		return nil
	end

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
-- ran soft_recall_gen_of — nil means type drift on the pin file, never match).
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

-- Scan ocsp-allow for .ocsp_revoke.{fp}.* claim litter (worker death mid-revoke).
local function list_allow_pin_claims(fingerprint)
	local claims = {}
	if not is_fp64(fingerprint) then
		return claims
	end
	local prefix = ".ocsp_revoke." .. fingerprint .. "."
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

-- If a claim still holds want (sha, gen) and the live pin path is empty, restore it.
local function try_reclaim_orphan_claim(fingerprint, want_sha, want_g)
	local path = ocsp_allow_path(fingerprint)
	if path_exists(path) then
		return false
	end
	for _, claim in ipairs(list_allow_pin_claims(fingerprint)) do
		local pin = decode_allow_pin(read_file(claim))
		if allow_pin_matches(pin, want_sha, want_g) then
			if restore_claimed_pin(claim, path) then
				return true
			end
		end
	end
	return false
end

-- Check if allow-pin has a claim with per-request dedup cache (ngx.ctx)
-- Avoids repeated expensive lfs.dir scans within a single handshake
local function allow_pin_has_claim(fingerprint)
	-- Initialize per-request cache on first use
	local ctx = ngx.ctx
	if ctx and not ctx.bw_ocsp_claim_cache then
		ctx.bw_ocsp_claim_cache = {}
	end

	-- Check per-request cache first
	if ctx and ctx.bw_ocsp_claim_cache then
		local cached = ctx.bw_ocsp_claim_cache[fingerprint]
		if cached ~= nil then
			-- Cache stores: false (no claims) or true (claims exist)
			return cached == true
		end
	end

	-- Cache miss: scan directory
	local has_claims = #list_allow_pin_claims(fingerprint) > 0
	if ctx and ctx.bw_ocsp_claim_cache then
		ctx.bw_ocsp_claim_cache[fingerprint] = has_claims
	end
	return has_claims
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
--   | "allow_drop_eacces" | "allow_drop_failed" | "allow_kept_gen0_grace"
-- handshake_drop=true: refuse to CAS soft_recall_gen=0 upgrade-grace pins
-- (only job drop_allow_pin may clear those). Soft-recall not_paged cleanup
-- passes handshake_drop=false so leftover gen-0 pins can still be revoked.
local function revoke_allow_pin(fingerprint, want_sha, want_gen, refuse_cause, quiet, handshake_drop)
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
		return "allow_kept_gen0_grace"
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
-- Compare-and-stamp: refuse overwrite when on-disk soft_recall_gen is strictly
-- newer (lagging canary must not clobber N+1 with N).
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
	-- Best-effort CAS: re-check immediately before rename (still TOCTOU vs another
	-- writer, but closes the common lagging-canary clobber of a newer pin).
	local existing = decode_allow_pin(read_file(path))
	if existing and type(existing.soft_recall_gen) == "number" and existing.soft_recall_gen > gen then
		return false, "stale_gen"
	end
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
	-- Re-check after write: a restamp may have landed while we wrote tmp.
	existing = decode_allow_pin(read_file(path))
	if existing and type(existing.soft_recall_gen) == "number" and existing.soft_recall_gen > gen then
		os.remove(tmp)
		return false, "stale_gen"
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
	-- Soft-recall / unpaged: revoke leftover allow for THIS (sha, gen) only so
	-- a lagging worker cannot erase a re-canaried pin (same DER, newer gen).
	-- handshake_drop=false: soft-recall cleanup may clear leftover gen-0 pins.
	if type(meta) == "table" and (shard_not_paged(meta) or meta.unpaged_after_nongood == true) then
		revoke_allow_pin(fingerprint, sha, recall_gen, "not_paged", quiet, false)
		-- Non-nil so a caller that skips shard_not_paged cannot staple this generation.
		return "not_paged"
	end
	local pin = read_allow_pin(fingerprint)
	if not pin then
		-- Worker death mid-revoke may leave a matching claim with an empty live path.
		if try_reclaim_orphan_claim(fingerprint, sha, recall_gen) then
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
		or d == "issuer_unavailable"
		or d == "validate_exhausted"
		or d == "response_empty"
		or d == "force_ffi_pending"
		or d == "peer_refuse_unavailable"
		or (type(eff) == "table" and eff.paged ~= true)
		or ((d == "set_staple_failed" or d == "set_staple_exception") and type(eff) == "table" and eff.paged == true)
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
	local sha, recall_gen = generation_tuple(meta, resp)
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

-- Keep old name for warmer compatibility.
local function ocsp_refuse_path(fingerprint)
	return ocsp_allow_path(fingerprint)
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
