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

local function fallback_touch(key)
	fallback_touch_gen = fallback_touch_gen + 1
	fallback_cache_touch[key] = fallback_touch_gen
end

local function fallback_evict_lru()
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

local function fallback_cache_get(key)
	local v = fallback_chain_cache[key]
	if v ~= nil then
		fallback_touch(key)
		return v
	end
	return nil
end

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

-- True when any non-root chain cert carries Must-Staple.
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

local function issuer_linked_chain_pem(leaf_pem, intermediate_pems)
	local blocks = issuer_linked_chain_blocks(leaf_pem, intermediate_pems)
	if type(blocks) ~= "table" or #blocks == 0 then
		return ""
	end
	note_depleted_pem_unresolved(blocks.unresolved_must_staple, blocks[1] or leaf_pem)
	return table.concat(blocks, "\n")
end

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
