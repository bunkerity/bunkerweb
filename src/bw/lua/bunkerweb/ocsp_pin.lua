-- Allow-pin bus (HTTP <-> stream) and peer-refuse DROP/KEEP rules.
-- Part of bunkerweb.ocsp; other modules use the .internal table, callers use bunkerweb.ocsp.
local _M = {}

local ngx = ngx

local common = require("bunkerweb.ocsp_common").internal
local OCSP_CLOCK_SKEW_SECONDS = common.OCSP_CLOCK_SKEW_SECONDS
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

-- Handshake refuse causes that DROP the allow pin (sibling Must-Staple fails until re-canary).
-- Never-write / keep-pin causes leave the canary allow in place (timing/colony/soft-recall).
-- Keys are raw refuse_cause strings BEFORE runbook alias collapse.
--
-- DROP = semantic poison about this body vs leaf / colony / canary (sibling must
--   fail closed until a new generation is canary-paged).
-- KEEP = this worker's view of pin state or its own clock. Must not erase a pin
--   every zone shares (stale reader / skewed clock → fleet Must-Staple outage).
--   Local handshake still refuses; only the shared pin survives.
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
	-- Raw ligand_verdict binding failures (HTTP/stream pass these without prefix).
	der_sha256_mismatch = true,
	missing_der_sha256 = true,
	invalid_der_sha256 = true,
	fingerprint_mismatch_or_missing_meta = true,
	canary_refused = true,
	-- intermediate_must_staple_libssl is KEEP (aligned with colony): a single
	-- OpenSSL 3.5 worker must not compare-and-delete the fleet allow-pin during
	-- mixed-version rollouts. Local handshake still refuses.
}
-- Keep allow pin (do not revoke) — sibling may still staple; local-only / temporary.
-- Invariant: every cause should_skip_peer_bus returns true for must also be KEEP
-- (or the skip arm never reaches record_peer_refuse). skip ⊆ KEEP.
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
	ligand_missing = true,
	-- Runbook alias collapse of ligand_* — callers must pass raw ligand_verdict;
	-- if they pass normalize_staple_decision output, KEEP (do not DROP on ENOENT).
	shared_ligand = true,
	peer_refuse_unavailable = true,
	fingerprint_chain_unavailable = true,
	multi_staple_attach_failed = true,
	-- Local chain-presentation defect. Do not DROP a pin the sibling may still staple.
	issuer_unresolved_must_staple = true,
	thisUpdate_future = true,
	thisUpdate_stale = true,
	lifetime_invalid = true,
	lifetime_too_long = true,
	thisUpdate_unreadable = true,
}

local function ocsp_allow_path(fingerprint)
	return "/var/cache/bunkerweb/ssl/ocsp-allow/" .. fingerprint
end

-- Legacy refuse path — job-side cleanup only after the allow-pin invert.
local function ocsp_refuse_path_legacy(fingerprint)
	return "/var/cache/bunkerweb/ssl/ocsp-refuse/" .. fingerprint
end

-- DROP causes that may revoke using meta.der_sha256 when resp is nil (meta names
-- the poisoned generation). Body-poison causes require resp bytes so a probe
-- refuse cannot CAS-delete the live pin via meta alone.
local META_ONLY_DROP_ALLOW = {
	tombstoned = true,
	serial_blacklisted = true,
	cluster_floor = true,
	canary_refused = true,
}

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

local function read_allow_pin(fingerprint)
	if not is_fp64(fingerprint) then
		return nil
	end
	return decode_allow_pin(read_file(ocsp_allow_path(fingerprint)))
end

-- True when the pin names exactly this generation (der_sha256, soft_recall_gen).
local function allow_pin_matches(pin, want_sha, want_g)
	return type(pin) == "table" and pin.der_sha256 == want_sha and (tonumber(pin.soft_recall_gen) or 0) == want_g
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
--   | "allow_drop_eacces" | "allow_drop_failed"
local function revoke_allow_pin(fingerprint, want_sha, want_gen, refuse_cause, quiet)
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
	-- Soft-recall / unpaged: revoke leftover allow for THIS (sha, gen) only so
	-- a lagging worker cannot erase a re-canaried pin (same DER, newer gen).
	if type(meta) == "table" and (shard_not_paged(meta) or meta.unpaged_after_nongood == true) then
		revoke_allow_pin(fingerprint, sha, recall_gen, "not_paged", quiet)
		-- Non-nil so a caller that skips shard_not_paged cannot staple this generation.
		return "not_paged"
	end
	local pin = read_allow_pin(fingerprint)
	if not pin then
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
	if pin.der_sha256 ~= sha or (tonumber(pin.soft_recall_gen) or 0) ~= recall_gen then
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

-- Handshake refuse: DROP allow pin for DROP_ALLOW causes via compare-and-delete.
-- refuse_cause is the raw pre-alias detail (logged); runbook staple_decision=
-- stays separate. Pin-state / clock causes are KEEP — this worker's view must
-- not revoke a pin HTTP, stream, and every sibling rely on.
local function record_peer_refuse(fingerprint, meta, resp, decision)
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
	if not sha then
		log(
			ngx.DEBUG,
			"OCSP allow-pin keep (no generation for compare-and-delete) refuse_cause="
				.. refuse_cause
				.. " fp="
				.. fp_short
		)
		return false
	end
	local outcome = revoke_allow_pin(fingerprint, sha, recall_gen, refuse_cause, false)
	return outcome == "allow_dropped"
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
		or d == "peer_refuse_unavailable"
		or (type(eff) == "table" and eff.paged ~= true)
		or ((d == "set_staple_failed" or d == "set_staple_exception") and type(eff) == "table" and eff.paged == true)
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

-- Back-compat: clear = drop allow pin (+ legacy refuse).
function _M.clear_peer_refuse(fingerprint)
	return drop_allow_pin(fingerprint)
end

_M.internal = {
	ensure_ocsp_bus_dirs = ensure_ocsp_bus_dirs,
	must_staple_refuse = must_staple_refuse,
	peer_refuse_blocks = peer_refuse_blocks,
}

return _M
