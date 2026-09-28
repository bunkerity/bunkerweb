-- Off-handshake L1 warmer (timer + shared-dict lease).
-- Part of bunkerweb.ocsp; other modules use the .internal table, callers use bunkerweb.ocsp.
local _M = {}

local ngx = ngx

local common = require("bunkerweb.ocsp_common").internal
local current_ocsp_epoch = common.current_ocsp_epoch
local is_fp64 = common.is_fp64
local log = common.log
local ocsp_path = common.ocsp_path
local read_file = common.read_file

local store = require("bunkerweb.ocsp_store").internal
local drop_cache = store.drop_cache
local ligand_or_meta = store.ligand_or_meta
local meta_effective_expires_unix = store.meta_effective_expires_unix
local meta_tombstoned = store.meta_tombstoned
local ocsp_json_ligand_matches = store.ocsp_json_ligand_matches
local read_ocsp_json = store.read_ocsp_json
local resp_still_fresh = store.resp_still_fresh
local serial_blacklist_blocks = store.serial_blacklist_blocks
local shard_not_paged = store.shard_not_paged
local warm_cache = store.warm_cache

local pin = require("bunkerweb.ocsp_pin").internal
local ensure_ocsp_bus_dirs = pin.ensure_ocsp_bus_dirs
local peer_refuse_blocks = pin.peer_refuse_blocks

local chain = require("bunkerweb.ocsp_chain").internal
local openssl_multi_staple_ready = chain.openssl_multi_staple_ready
local refresh_multi_staple_vote = chain.refresh_multi_staple_vote

local maybe_rearm_l1_warmer

local L1_WARMER_INTERVAL = 5
local L1_WARMER_RESCAN = 60
-- Must be well under L1_MAX_TTL so failover re-warms before shm entries expire.
local L1_WARMER_LEASE_TTL = math.max(L1_WARMER_INTERVAL * 3, 20)
local L1_WARMER_LEASE_KEY = "TLS:SSL:ocsp_l1_warmer_lease"
local l1_warmer_started = false
local l1_warmer_no_add_logged = false
local l1_warmer_last_epoch = nil
local l1_warmer_last_full = 0
-- Store the warmer was armed with; lets a handshake re-arm it after a failed reschedule.
local l1_warmer_store = nil
local l1_warmer_rearm_at = 0
local L1_WARMER_REARM_INTERVAL = 5

local function warmer_lease_token()
	local wid = (ngx.worker and ngx.worker.id and ngx.worker.id()) or 0
	local pid = (ngx.worker and ngx.worker.pid and ngx.worker.pid()) or 0
	return tostring(wid) .. ":" .. tostring(pid)
end

-- True when this worker holds (or just claimed) the scan lease for this subsystem.
local function claim_l1_warmer_lease(internalstore)
	if not internalstore then
		return false
	end
	local token = warmer_lease_token()
	local cur = nil
	pcall(function()
		cur = internalstore:get(L1_WARMER_LEASE_KEY)
	end)
	if cur == token then
		pcall(function()
			internalstore:set(L1_WARMER_LEASE_KEY, token, L1_WARMER_LEASE_TTL)
		end)
		return true
	end
	if cur ~= nil and cur ~= "" then
		return false
	end
	-- Lease free: only shared-dict add is atomic. set-then-recheck lets two
	-- workers both observe an empty key and both scan. If add is missing,
	-- skip this tick (return false) instead of racing.
	local claimed = false
	pcall(function()
		local dict = internalstore.dict
		if dict and dict.add then
			claimed = dict:add(L1_WARMER_LEASE_KEY, token, L1_WARMER_LEASE_TTL) and true or false
			return
		end
		if not l1_warmer_no_add_logged then
			l1_warmer_no_add_logged = true
			log(ngx.ERR, "OCSP L1 warmer lease has no dict.add; skipping scan to avoid a set/recheck race")
		end
		claimed = false
	end)
	return claimed
end

-- Directory order only (no Must-Staple priority). warm_l1_from_disk sorts
-- must_staple=true shards first so a short lease still warms fail-closed leaves.
local function list_ocsp_fingerprints()
	local fps = {}
	local root = "/var/cache/bunkerweb/ssl"
	local ok_lfs, lfs = pcall(require, "lfs")
	if ok_lfs and lfs and lfs.dir then
		local ok_root, iter = pcall(lfs.dir, root)
		if ok_root and iter then
			for a in iter do
				if type(a) == "string" and #a == 1 and a:match("^[0-9a-f]$") then
					local path_a = root .. "/" .. a
					local ok_a, iter_a = pcall(lfs.dir, path_a)
					if ok_a and iter_a then
						for b in iter_a do
							if type(b) == "string" and #b == 1 and b:match("^[0-9a-f]$") then
								local path_b = path_a .. "/" .. b
								local ok_b, iter_b = pcall(lfs.dir, path_b)
								if ok_b and iter_b then
									for fp in iter_b do
										if is_fp64(fp) then
											fps[#fps + 1] = fp
										end
									end
								end
							end
						end
					end
				end
			end
		end
		return fps
	end
	local ok_p, pipe = pcall(io.popen, "find " .. root .. " -mindepth 3 -maxdepth 3 -type d 2>/dev/null")
	if not ok_p or not pipe then
		return fps
	end
	for line in pipe:lines() do
		local fp = line:match("([0-9a-f]+)$")
		if is_fp64(fp) then
			fps[#fps + 1] = fp
		end
	end
	pipe:close()
	return fps
end

-- Load one paged shard into L1 without crypto validate (outside ligand + allow-pin
-- are enough for the handshake authorize path). Runs off the TLS critical path only.
-- Do not re-warm generations the handshake would refuse (allow-pin missing/mismatch
-- or serial-blacklist): that churns shm and forces refuse/drop on every hit.
local function warm_one_shard(internalstore, fingerprint)
	if not internalstore or not is_fp64(fingerprint) then
		return false
	end
	local meta = read_ocsp_json(fingerprint)
	meta = ligand_or_meta(meta, fingerprint)
	if not meta or meta_tombstoned(meta) or shard_not_paged(meta) then
		drop_cache(internalstore, fingerprint)
		return false
	end
	if not resp_still_fresh(nil, fingerprint, meta) then
		drop_cache(internalstore, fingerprint)
		return false
	end
	local resp = read_file(ocsp_path(fingerprint))
	if type(resp) ~= "string" or resp == "" then
		drop_cache(internalstore, fingerprint)
		return false
	end
	local ligand_ok = ocsp_json_ligand_matches(meta, fingerprint, resp)
	if not ligand_ok then
		drop_cache(internalstore, fingerprint)
		return false
	end
	if peer_refuse_blocks(fingerprint, meta, resp, true) then
		drop_cache(internalstore, fingerprint)
		return false
	end
	if serial_blacklist_blocks(fingerprint, resp) then
		drop_cache(internalstore, fingerprint)
		return false
	end
	-- mark_verified=false: no leaf PEM here; handshake may still authorize via meta.
	warm_cache(internalstore, fingerprint, resp, false, meta_effective_expires_unix(meta))
	return true
end

-- Scan the OCSP cache tree and warm every paged GOOD shard into this subsystem's L1.
-- list_ocsp_fingerprints is directory order. This warmer sorts Must-Staple
-- shards first (ocsp.json must_staple=true) so a lease that expires mid-scan
-- still covers fail-closed leaves before optional ones.
-- Returns warmed count.
function _M.warm_l1_from_disk(internalstore)
	if not internalstore then
		return 0
	end
	local fps = list_ocsp_fingerprints()
	-- Read each ocsp.json once: reading inside the comparator cost O(n log n) disk
	-- reads, and a file changing mid-sort made the order inconsistent, so table.sort
	-- raised "invalid order function" and the whole pass was lost.
	local is_must = {}
	for _, fp in ipairs(fps) do
		local meta = read_ocsp_json(fp)
		is_must[fp] = type(meta) == "table" and meta.must_staple == true
	end
	table.sort(fps, function(a, b)
		if is_must[a] ~= is_must[b] then
			return is_must[a]
		end
		return a < b
	end)
	local warmed = 0
	for _, fp in ipairs(fps) do
		local ok, did = pcall(warm_one_shard, internalstore, fp)
		if ok and did then
			warmed = warmed + 1
		end
	end
	if warmed > 0 then
		log(
			ngx.INFO,
			"OCSP L1 warmer loaded " .. tostring(warmed) .. " shard(s) subsystem=" .. tostring(ngx.config.subsystem)
		)
	end
	return warmed
end

-- Start a recurring timer (once per worker Lua VM). A shared-dict lease picks
-- one scanner so N workers do not all walk disk; lease expiry lets another
-- worker take over if the holder dies before L1_MAX_TTL.
function _M.start_l1_warmer(internalstore)
	if not internalstore then
		return false
	end
	if l1_warmer_started then
		return true
	end
	if not ngx.timer or not ngx.timer.at then
		return false
	end
	-- Off handshake: ensure allow/ligand/legacy-refuse dirs exist (job writes pins).
	if not ensure_ocsp_bus_dirs() then
		log(ngx.ERR, "OCSP could not provision ocsp-allow/ocsp-ligand dirs; allow-pin bus may fail")
	end
	-- Publish multi-staple attach capability for ocsp-refresh (intermediate fetch gate).
	pcall(openssl_multi_staple_ready)
	l1_warmer_started = true
	l1_warmer_store = internalstore

	local function tick(premature)
		if premature then
			return
		end
		-- Refresh this worker's multi-staple colony vote (MIN across live workers).
		pcall(refresh_multi_staple_vote)
		if claim_l1_warmer_lease(internalstore) then
			local epoch = current_ocsp_epoch()
			local now = ngx.time()
			-- Re-warm on publish (epoch bump) or periodically so shm TTL expiry
			-- does not push the next handshake onto a cold ocsp.der read.
			local need = epoch ~= l1_warmer_last_epoch or (now - l1_warmer_last_full) >= L1_WARMER_RESCAN
			if need then
				l1_warmer_last_epoch = epoch
				l1_warmer_last_full = now
				pcall(_M.warm_l1_from_disk, internalstore)
			end
		end
		local ok, err = ngx.timer.at(L1_WARMER_INTERVAL, tick)
		if not ok then
			l1_warmer_started = false
			log(ngx.ERR, "OCSP L1 warmer reschedule failed: " .. tostring(err))
		end
	end

	-- Stagger first tick by worker id so startup claims are not a thundering herd.
	local wid = (ngx.worker and ngx.worker.id and ngx.worker.id()) or 0
	local delay = (tonumber(wid) or 0) * 0.05
	local ok, err = ngx.timer.at(delay, tick)
	if not ok then
		l1_warmer_started = false
		log(ngx.ERR, "OCSP L1 warmer start failed: " .. tostring(err))
		return false
	end
	log(
		ngx.INFO,
		"OCSP L1 warmer armed worker="
			.. tostring(wid)
			.. " lease_ttl="
			.. tostring(L1_WARMER_LEASE_TTL)
			.. "s subsystem="
			.. tostring(ngx.config.subsystem)
	)
	return true
end

-- A failed ngx.timer.at reschedule used to stop the warmer for the worker's lifetime.
-- Handshakes re-arm it (throttled) once it has been started at least once.
maybe_rearm_l1_warmer = function()
	if l1_warmer_started or not l1_warmer_store then
		return
	end
	if ngx.worker and ngx.worker.exiting and ngx.worker.exiting() then
		return
	end
	local now = ngx.now()
	if now - l1_warmer_rearm_at < L1_WARMER_REARM_INTERVAL then
		return
	end
	l1_warmer_rearm_at = now
	pcall(_M.start_l1_warmer, l1_warmer_store)
end

_M.internal = {
	maybe_rearm_l1_warmer = maybe_rearm_l1_warmer,
}

return _M
