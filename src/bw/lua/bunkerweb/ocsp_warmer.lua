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
-- Renew mid-walk so a long MS-first scan cannot outlive the lease TTL.
local L1_WARMER_LEASE_HEARTBEAT_EVERY = 32
local L1_WARMER_LEASE_KEY = "TLS:SSL:ocsp_l1_warmer_lease"
-- Mid-scan resume: "epoch|fp" so the next holder continues MS-first mid-list.
-- On resume, any Must-Staple that re-sorts before the cursor is still warmed
-- (re-sort must not + complete=true skip MS). Epoch is a string (job time_ns()).
local L1_WARMER_RESUME_KEY = "TLS:SSL:ocsp_l1_warmer_resume"
local l1_warmer_started = false
local l1_warmer_no_add_logged = false
local l1_warmer_last_epoch = nil
local l1_warmer_last_full = 0
-- Store the warmer was armed with; lets a handshake re-arm it after a failed reschedule.
local l1_warmer_store = nil
local l1_warmer_rearm_at = 0
local L1_WARMER_REARM_INTERVAL = 5

-- Canonical string form of .ocsp_epoch (never tonumber — ns tokens lose precision).
local function normalize_epoch(epoch)
	if type(epoch) == "string" and epoch ~= "" then
		local token = epoch:match("^%s*(%S+)")
		if token then
			return token
		end
	end
	return tostring(current_ocsp_epoch() or "0")
end

local function warmer_lease_token()
	local wid = (ngx.worker and ngx.worker.id and ngx.worker.id()) or 0
	local pid = (ngx.worker and ngx.worker.pid and ngx.worker.pid()) or 0
	return tostring(wid) .. ":" .. tostring(pid)
end

local function read_warm_resume(internalstore)
	local raw = nil
	pcall(function()
		raw = internalstore:get(L1_WARMER_RESUME_KEY)
	end)
	if type(raw) ~= "string" then
		return nil, nil
	end
	-- Epoch is %S+ (digit ns string); do not coerce with tonumber.
	-- Accept A-F then lower so uppercase writers still resume.
	local epoch_s, fp = raw:match("^(%S+)|([0-9a-fA-F]+)$")
	if not epoch_s or not fp then
		return nil, nil
	end
	fp = fp:lower()
	if not is_fp64(fp) then
		return nil, nil
	end
	return epoch_s, fp
end

local function write_warm_resume(internalstore, epoch, fp)
	epoch = normalize_epoch(epoch)
	if type(fp) == "string" then
		fp = fp:lower()
	end
	if not internalstore or epoch == "" or not is_fp64(fp) then
		return
	end
	pcall(function()
		-- Outlive one lease TTL so the next holder can pick up after failover.
		internalstore:set(L1_WARMER_RESUME_KEY, epoch .. "|" .. fp, L1_WARMER_LEASE_TTL * 3)
	end)
end

local function clear_warm_resume(internalstore)
	if not internalstore then
		return
	end
	pcall(function()
		internalstore:delete(L1_WARMER_RESUME_KEY)
	end)
end

-- Renew only while this worker still holds the token.
-- Prefer dict:expire (TTL only) — set-after-get can overwrite a peer that
-- claimed via add after our TTL expired (lease steal). After expire,
-- re-get must still show our token (expire can extend a peer's claim if TTL
-- died between the first get and expire). Without expire: ownership check
-- only (never set).
local function renew_l1_warmer_lease(internalstore)
	if not internalstore then
		return false
	end
	local token = warmer_lease_token()
	local cur = nil
	pcall(function()
		cur = internalstore:get(L1_WARMER_LEASE_KEY)
	end)
	if cur ~= token then
		return false
	end
	local renewed = false
	pcall(function()
		local dict = internalstore.dict
		if dict and dict.expire then
			-- Returns false/nil when the key is already gone (peer may claim next).
			if not dict:expire(L1_WARMER_LEASE_KEY, L1_WARMER_LEASE_TTL) then
				return
			end
			-- Confirm we still own the value (expire may have extended a peer's add).
			local again = internalstore:get(L1_WARMER_LEASE_KEY)
			renewed = again == token
			return
		end
		-- No dict.expire: never set() to extend — get→set races a peer's add and
		-- steals the lease. Ownership check only; TTL stays at the original claim.
		local again = internalstore:get(L1_WARMER_LEASE_KEY)
		renewed = again == token
	end)
	return renewed
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
		return renew_l1_warmer_lease(internalstore)
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

-- Module-level fingerprint list cache (survives across warm cycles).
-- Fingerprint list is expensive to scan (10-50ms per cycle); cache until epoch changes.
local cached_fingerprints = nil
local cached_fingerprints_epoch = nil
local cached_fingerprints_timeout = 0
-- Align with RESCAN so new shards appear without waiting 5 minutes.
local FPS_CACHE_TTL = L1_WARMER_RESCAN

-- Nested hex dirs, or find fallback restricted to root/a/b/fp64.
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
											-- Canonical lower: resume/L1 keys are lower; mixed-case
											-- dirs would miss resume match and diverge from ocsp_path.
											fps[#fps + 1] = fp:lower()
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
	-- Quote root for the shell; accept only root/<hex>/<hex>/<fp64> lines (no
	-- trailing-hex suffix thrash from crafted directory names).
	local ok_p, pipe = pcall(io.popen, "find '" .. root .. "' -mindepth 3 -maxdepth 3 -type d 2>/dev/null")
	if not ok_p or not pipe then
		return fps
	end
	local prefix = root .. "/"
	for line in pipe:lines() do
		if type(line) == "string" and line:sub(1, #prefix) == prefix then
			local rest = line:sub(#prefix + 1)
			local a, b, fp = rest:match("^([0-9a-f])/([0-9a-f])/([0-9a-fA-F]+)$")
			if a and b and is_fp64(fp) then
				fps[#fps + 1] = fp:lower()
			end
		end
	end
	pipe:close()
	return fps
end

-- Get cached fingerprint list, rescanning only on epoch change or timeout.
-- Returns a shallow copy so MS-first sort cannot mutate the module cache.
local function get_cached_fingerprints(current_epoch)
	current_epoch = normalize_epoch(current_epoch)
	local now = ngx.now()

	if cached_fingerprints and cached_fingerprints_epoch == current_epoch and now < cached_fingerprints_timeout then
		local copy = {}
		for i, fp in ipairs(cached_fingerprints) do
			copy[i] = fp
		end
		return copy
	end

	cached_fingerprints = list_ocsp_fingerprints()
	-- Never cache an empty scan: a transient lfs/find miss must not suppress
	-- re-enumeration for a full FPS_CACHE_TTL (and must not pair with complete=true).
	if #cached_fingerprints == 0 then
		cached_fingerprints = nil
		cached_fingerprints_epoch = nil
		cached_fingerprints_timeout = 0
		log(ngx.DEBUG, "OCSP L1 warmer fingerprint scan empty epoch=" .. tostring(current_epoch))
		return {}
	end
	cached_fingerprints_epoch = current_epoch
	cached_fingerprints_timeout = now + FPS_CACHE_TTL
	log(
		ngx.DEBUG,
		"OCSP L1 warmer rescanned fingerprints: " .. #cached_fingerprints .. " certs epoch=" .. tostring(current_epoch)
	)

	local copy = {}
	for i, fp in ipairs(cached_fingerprints) do
		copy[i] = fp
	end
	return copy
end

-- Load one paged shard into L1 without crypto validate (outside ligand + allow-pin
-- are enough for the handshake authorize path). Runs off the TLS critical path only.
-- Do not re-warm generations the handshake would refuse (allow-pin missing/mismatch
-- or serial-blacklist): that churns shm and forces refuse/drop on every hit.
-- pre_meta: optional ligand-merged meta from the sort pass (avoids a second ocsp.json read).
-- walk_epoch: string .ocsp_epoch sampled at scan start (packed into L1; see warm_cache).
local function warm_one_shard(internalstore, fingerprint, pre_meta, walk_epoch)
	if not internalstore or not is_fp64(fingerprint) then
		return false
	end
	local meta = pre_meta
	if type(meta) ~= "table" then
		meta = ligand_or_meta(read_ocsp_json(fingerprint), fingerprint)
	end
	if not meta or meta_tombstoned(meta, fingerprint) or shard_not_paged(meta, fingerprint) then
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
	local ligand_ok, ligand_reason = ocsp_json_ligand_matches(meta, fingerprint, resp)
	if not ligand_ok then
		-- ligand_missing is KEEP (promote/ENOENT tear): skip without drop_cache and
		-- signal incomplete so we retry before RESCAN once the ligand appears.
		if ligand_reason == "ligand_missing" then
			log(
				ngx.NOTICE,
				"OCSP L1 warmer skip ligand_missing fp="
					.. fingerprint:sub(1, 16)
					.. "... subsystem="
					.. tostring(ngx.config.subsystem)
			)
			return false, "pin_transient"
		end
		drop_cache(internalstore, fingerprint)
		return false
	end
	local pin_refuse = peer_refuse_blocks(fingerprint, meta, resp, true)
	if pin_refuse then
		-- Transient / soft-recall KEEP: skip warm but do not churn a handshake-verified L1.
		-- Second return lets the walk avoid stamping complete (retry before RESCAN).
		if
			pin_refuse == "allow_pin_claim_inflight"
			or pin_refuse == "allow_pin_expired"
			or pin_refuse == "allow_pin_missing"
			or pin_refuse == "gen_type_drift"
		then
			log(
				ngx.NOTICE,
				"OCSP L1 warmer skip pin-transient cause="
					.. tostring(pin_refuse)
					.. " fp="
					.. fingerprint:sub(1, 16)
					.. "... subsystem="
					.. tostring(ngx.config.subsystem)
			)
			return false, "pin_transient"
		end
		drop_cache(internalstore, fingerprint)
		log(
			ngx.NOTICE,
			"OCSP L1 warmer skip allow-pin/refuse cause="
				.. tostring(pin_refuse)
				.. " fp="
				.. fingerprint:sub(1, 16)
				.. "... subsystem="
				.. tostring(ngx.config.subsystem)
		)
		return false
	end
	if serial_blacklist_blocks(fingerprint, resp) then
		drop_cache(internalstore, fingerprint)
		log(
			ngx.NOTICE,
			"OCSP L1 warmer skip serial-blacklist fp="
				.. fingerprint:sub(1, 16)
				.. "... subsystem="
				.. tostring(ngx.config.subsystem)
		)
		return false
	end
	-- mark_verified=false: no leaf PEM here; handshake may still authorize via meta.
	-- Stamp walk_epoch (not live current_ocsp_epoch) so a mid-scan publish bump
	-- cannot make early shards look coherent against a newer .ocsp_epoch.
	warm_cache(internalstore, fingerprint, resp, false, meta_effective_expires_unix(meta), walk_epoch)
	return true
end

-- Scan the OCSP cache tree and warm every paged GOOD shard into this subsystem's L1.
-- Must-Staple first (ligand-merged, still paged). Successful mid-scan renews
-- checkpoint a resume cursor so the next holder continues mid-list (loss itself
-- never writes — avoids clobbering a peer). Returns warmed_count, complete
-- (false → caller must not stamp last_epoch).
function _M.warm_l1_from_disk(internalstore, epoch)
	-- Incomplete: never let callers stamp last_epoch on a no-op / failed walk.
	if not internalstore then
		return 0, false
	end
	epoch = normalize_epoch(epoch)
	-- Wall-clock + index heartbeats: slow shard I/O or sparse MS indices must
	-- not outlive LEASE_TTL between renews (index-only missed when MS-gated).
	local last_hb_at = ngx.now()
	local hb_interval = L1_WARMER_LEASE_TTL / 2
	-- Declared before try_renew: once set, successful renews clear the resume
	-- cursor while we still own (failover must not skip earlier non-MS
	-- pin_transient shards then stamp complete=true).
	local pin_transient_skip = false
	local function renew_due(n_since_start, every)
		if every and n_since_start > 0 and (n_since_start % every) == 0 then
			return true
		end
		return (ngx.now() - last_hb_at) >= hb_interval
	end
	local function try_renew(resume_hint)
		-- Never write resume after renew failure: a post-loss set can clobber a
		-- peer's newer cursor (or resurrect one they cleared). Checkpoint only
		-- while we still own, after a successful renew.
		if not renew_l1_warmer_lease(internalstore) then
			return false
		end
		last_hb_at = ngx.now()
		if pin_transient_skip then
			-- Drop cursor under lease so the next holder restarts from index 1.
			clear_warm_resume(internalstore)
		elseif resume_hint then
			write_warm_resume(internalstore, epoch, resume_hint)
		end
		return true
	end
	-- Heartbeat before enumeration: a hung lfs.dir must not outlive the lease
	-- with no renew until the next index/time gate.
	if not try_renew(nil) then
		return 0, false
	end
	-- Read resume BEFORE enumeration: a slow list_ocsp_fingerprints can outlive
	-- resume TTL; keep locals + refresh TTL before the scan.
	local resume_epoch, resume_fp = read_warm_resume(internalstore)
	local sort_resume_hint = (resume_epoch == epoch and resume_fp) or nil
	if not try_renew(sort_resume_hint) then
		return 0, false
	end
	local fps = get_cached_fingerprints(epoch)
	if not try_renew(sort_resume_hint) then
		return 0, false
	end
	-- Transient empty scan (or no shards yet): do not clear a failover cursor or
	-- stamp complete — otherwise last_epoch suppresses warm until RESCAN.
	if #fps == 0 then
		return 0, false
	end
	-- Read each shard's effective meta once for sort + warm (ligand overlay).
	-- Heartbeat during this pass: large fleets can exceed LEASE_TTL on json alone.
	local is_must = {}
	local meta_by_fp = {}
	for i, fp in ipairs(fps) do
		-- i=32,64,... (same cadence as before) plus wall-clock.
		if renew_due(i, L1_WARMER_LEASE_HEARTBEAT_EVERY) then
			if not try_renew(sort_resume_hint) then
				-- Sort incomplete; keep last owned checkpoint (may be sort_resume_hint).
				return 0, false
			end
		end
		local meta = ligand_or_meta(read_ocsp_json(fp), fp)
		meta_by_fp[fp] = meta
		is_must[fp] = type(meta) == "table"
			and meta.must_staple == true
			and not meta_tombstoned(meta, fp)
			and not shard_not_paged(meta, fp)
	end
	table.sort(fps, function(a, b)
		if is_must[a] ~= is_must[b] then
			return is_must[a]
		end
		return a < b
	end)

	-- Renew again after sort prep before the warm walk (prep may have been long).
	if not try_renew(sort_resume_hint) then
		return 0, false
	end

	local start_i = 1
	if resume_epoch == epoch and resume_fp then
		for i, fp in ipairs(fps) do
			if fp == resume_fp then
				start_i = i
				log(
					ngx.NOTICE,
					"OCSP L1 warmer resume at fp="
						.. resume_fp:sub(1, 16)
						.. "... index="
						.. tostring(i)
						.. " subsystem="
						.. tostring(ngx.config.subsystem)
				)
				break
			end
		end
	end

	local warmed = 0
	local ms_pcall_fail = false
	local function note_warm_result(ok, did, detail, fp)
		if not ok then
			log(
				ngx.ERR,
				"OCSP L1 warmer shard error fp="
					.. fp:sub(1, 16)
					.. "... err="
					.. tostring(did)
					.. " subsystem="
					.. tostring(ngx.config.subsystem)
			)
			if is_must[fp] then
				ms_pcall_fail = true
			end
		elseif did then
			warmed = warmed + 1
		elseif detail == "pin_transient" then
			pin_transient_skip = true
		end
	end
	-- MS-first re-sort can move Must-Staple fps before resume_fp. Warm those
	-- before the suffix walk; otherwise clear_warm_resume + complete=true would
	-- skip them until RESCAN (cold L1 for MS under load).
	if start_i > 1 then
		for i = 1, start_i - 1 do
			local fp = fps[i]
			-- Heartbeat on every index (not only is_must): sparse MS used to skip
			-- all i%32 gates when non-must landed on those indices.
			if renew_due(i, L1_WARMER_LEASE_HEARTBEAT_EVERY) then
				if not try_renew(resume_fp or fp) then
					return warmed, false
				end
			end
			if is_must[fp] then
				local ok, did, detail = pcall(warm_one_shard, internalstore, fp, meta_by_fp[fp], epoch)
				note_warm_result(ok, did, detail, fp)
			end
		end
		if not try_renew(resume_fp or fps[start_i]) then
			return warmed, false
		end
	end

	for i = start_i, #fps do
		local fp = fps[i]
		-- Heartbeat before each chunk so a long walk cannot outlive LEASE_TTL.
		local since = i - start_i
		if renew_due(since, L1_WARMER_LEASE_HEARTBEAT_EVERY) then
			if not try_renew(fp) then
				log(
					ngx.NOTICE,
					"OCSP L1 warmer lost lease mid-scan after "
						.. tostring(warmed)
						.. " shard(s); at fp="
						.. fp:sub(1, 16)
						.. "... (last owned checkpoint kept) subsystem="
						.. tostring(ngx.config.subsystem)
				)
				return warmed, false
			end
		end
		local ok, did, detail = pcall(warm_one_shard, internalstore, fp, meta_by_fp[fp], epoch)
		note_warm_result(ok, did, detail, fp)
	end
	-- Final ownership check: lease can die inside the last warm_one_shard while a
	-- peer claims and writes a resume — clearing then would wipe their cursor and
	-- a stale complete=true would stamp last_epoch on this worker.
	-- Do NOT write resume_hint=tail_fp: an EOF cursor makes the next holder
	-- MS-prefix + last-shard only, then complete=true while skipping non-MS.
	if not try_renew(nil) then
		return warmed, false
	end
	clear_warm_resume(internalstore)
	if warmed > 0 then
		log(
			ngx.INFO,
			"OCSP L1 warmer loaded " .. tostring(warmed) .. " shard(s) subsystem=" .. tostring(ngx.config.subsystem)
		)
	end
	-- MS pcall throws and transient pin skips must not stamp a "complete" pass
	-- (otherwise cold L1 waits a full RESCAN after pins appear).
	if ms_pcall_fail or pin_transient_skip then
		return warmed, false
	end
	return warmed, true
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
		-- No timer API: do not leave a store that handshake rearm will thrash.
		l1_warmer_store = nil
		return false
	end
	-- Off handshake: ensure allow/ligand/legacy-refuse dirs exist (job writes pins).
	if not ensure_ocsp_bus_dirs() then
		log(ngx.ERR, "OCSP could not provision ocsp-allow/ocsp-ligand dirs; allow-pin bus may fail")
	end
	-- Publish multi-staple attach capability for ocsp-refresh (intermediate fetch gate).
	pcall(openssl_multi_staple_ready)
	-- Remember store before arming so maybe_rearm can retry if timer.at fails.
	l1_warmer_store = internalstore

	local function tick(premature)
		if premature then
			return
		end
		-- Colony vote: every worker must refresh (MIN across live peers), not only
		-- the lease holder — a leaf-only worker still needs to publish "0".
		pcall(refresh_multi_staple_vote)
		if claim_l1_warmer_lease(internalstore) then
			-- Re-provision bus dirs on claim (vanished pin dirs after arm).
			pcall(ensure_ocsp_bus_dirs)
			local epoch = normalize_epoch(current_ocsp_epoch())
			local now = ngx.time()
			-- Re-warm on publish (epoch bump) or periodically so shm TTL expiry
			-- does not push the next handshake onto a cold ocsp.der read.
			local need = epoch ~= l1_warmer_last_epoch or (now - l1_warmer_last_full) >= L1_WARMER_RESCAN
			if need then
				-- Stamp last_full from walk start so a long scan does not stretch
				-- effective RESCAN by wall-clock duration. Epoch only after complete.
				local walk_started = now
				local ok_warm, _, complete = pcall(_M.warm_l1_from_disk, internalstore, epoch)
				if ok_warm and complete == true then
					l1_warmer_last_epoch = epoch
					l1_warmer_last_full = walk_started
				end
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
	-- Only after the first timer.at succeeds — otherwise maybe_rearm thinks we
	-- are armed while no tick will ever claim the lease.
	l1_warmer_started = true
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
-- Handshakes re-arm it (throttled) once a store was bound (even if start failed).
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
