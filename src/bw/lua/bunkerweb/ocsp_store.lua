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

-- Forward decls: warm_cache tightens expires / gen against live ligand (defined below).
local ligand_or_meta
local soft_recall_gen_of
local meta_effective_expires_unix

local function l1_shm_ttl(expires_unix)
	-- Never park an undated body in L1 (would outlive stripped meta).
	if type(expires_unix) ~= "number" or expires_unix <= 0 then
		return nil
	end
	-- Drop L1 at death time (expires_unix - skew), same as resp_still_fresh.
	local remaining = expires_unix - OCSP_CLOCK_SKEW_SECONDS - ngx.time()
	if remaining <= 0 then
		return nil
	end
	if remaining > L1_MAX_TTL then
		return L1_MAX_TTL
	end
	return remaining
end

-- Pack one L1 shm entry: epoch | verified sha256 binding | soft_recall_gen | expires | DER.
local function pack_l1(epoch, verified_binding, der, expires_unix, soft_recall_gen)
	local exp = ""
	if type(expires_unix) == "number" and expires_unix > 0 then
		exp = tostring(math.floor(expires_unix))
	elseif type(expires_unix) == "string" and expires_unix:match("^%d+$") then
		exp = expires_unix
	end
	local gen = ""
	if type(soft_recall_gen) == "number" and soft_recall_gen >= 0 then
		gen = tostring(math.floor(soft_recall_gen))
	end
	return L1_MAGIC .. (epoch or "0") .. "\0" .. (verified_binding or "") .. "\0" .. gen .. "\0" .. exp .. "\0" .. der
end

-- Unpack bw3 (preferred) or legacy bw2. Returns epoch, binding, der, expires_unix, gen.
-- bw2 → gen=nil so verified trust fails closed until re-warm under bw3.
local function unpack_l1(blob)
	if type(blob) ~= "string" or #blob < 4 then
		return nil, nil, nil, nil, nil
	end
	local magic = blob:sub(1, 4)
	if magic == L1_MAGIC then
		local epoch, binding, gen_s, exp, der = blob:sub(5):match("^([^\0]*)\0([^\0]*)\0([^\0]*)\0([^\0]*)\0(.*)$")
		if type(der) ~= "string" or #der == 0 then
			return nil, nil, nil, nil, nil
		end
		if binding == "" then
			binding = nil
		end
		local expires_unix = nil
		if type(exp) == "string" and exp:match("^%d+$") then
			expires_unix = tonumber(exp)
		end
		local gen = nil
		if type(gen_s) == "string" and gen_s:match("^%d+$") then
			gen = tonumber(gen_s)
		end
		return epoch or "0", binding, der, expires_unix, gen
	end
	if magic == L1_MAGIC_V2 then
		local epoch, binding, exp, der = blob:sub(5):match("^([^\0]*)\0([^\0]*)\0([^\0]*)\0(.*)$")
		if type(der) ~= "string" or #der == 0 then
			return nil, nil, nil, nil, nil
		end
		if binding == "" then
			binding = nil
		end
		local expires_unix = nil
		if type(exp) == "string" and exp:match("^%d+$") then
			expires_unix = tonumber(exp)
		end
		-- No gen in v2 — caller must not trust verified across soft-recall.
		return epoch or "0", binding, der, expires_unix, nil
	end
	return nil, nil, nil, nil, nil
end

-- Returns der, verified_binding, epoch, expires_unix, soft_recall_gen (or nil).
local function get_l1(internalstore, fingerprint)
	if not internalstore or not fingerprint then
		return nil
	end
	local ok, blob = pcall(function()
		-- Shared dict (not per-worker LRU): one warmer refill serves every worker.
		return internalstore:get(cache_key(fingerprint))
	end)
	if not ok or type(blob) ~= "string" or #blob == 0 then
		return nil
	end

	local epoch, verified, der, expires_unix, gen = unpack_l1(blob)
	if der then
		return der, verified, epoch, expires_unix, gen
	end
	return nil
end

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
	-- Live merged death clock wins: never mark verified under a looser expires than
	-- ligand/shard min (L1 TTL and resp_still_fresh would disagree across workers).
	local live_meta = nil
	if fingerprint then
		live_meta = ligand_or_meta(nil, fingerprint)
		local tight = meta_effective_expires_unix(live_meta, nil)
		if type(tight) == "number" and tight > 0 then
			if type(expires_unix) ~= "number" or expires_unix <= 0 or expires_unix > tight then
				if mark_verified then
					mark_verified = false
				end
				expires_unix = tight
			end
		end
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
	if type(gen) ~= "number" then
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
	pcall(function()
		internalstore:set(cache_key(fingerprint), pack_l1(epoch, binding, resp, expires_unix, gen), ttl)
		-- Also clear the zone-scoped key so a prior put without the zone flag cannot linger.
		internalstore:delete(cache_key(fingerprint), true)
	end)
end

local function drop_cache(internalstore, fingerprint)
	pcall(function()
		internalstore:delete(cache_key(fingerprint))
		internalstore:delete(cache_key(fingerprint), true)
	end)
end

-- True when this L1 body is still coherent with disk + .ocsp_epoch.
-- Implemented after ligand_effective_sha (shared with HTTP); see l1_body_matches_disk.
local l1_matches_disk

-- Job-written shard metadata ({fp[1]}/{fp[2]}/{fp}/ocsp.json), or nil when absent/invalid.
-- Must stay above resolve_leaf_must_staple / cert_must_staple_bool: a local
-- referenced before its definition compiles to a nil global in LuaJIT.
-- Read ocsp.json with per-request dedup cache (ngx.ctx)
-- Avoids re-reading the same file within a single handshake
local function read_ocsp_json(fingerprint)
	if not is_fp64(fingerprint) then
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
		-- Cache the "not found" result to prevent re-reading
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

-- True only when the job recorded must_staple=true in ocsp.json (resty-invisible TLS Feature).
local function ocsp_json_must_staple(meta)
	return meta ~= nil and meta.must_staple == true
end

-- Tri-state leaf Must-Staple: TLS Feature, then ocsp.json, then unknown→nil.
-- Fail-closed gate: resolve_leaf_must_staple(...) ~= false.
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
		return false
	end
	if meta ~= nil then
		-- Job wrote meta without must_staple=true → not Must-Staple.
		return false
	end
	return nil
end

-- Boolean Must-Staple for a PEM block (leaf or intermediate).
-- fail_closed_unknown=true → treat resty miss + no ocsp.json as Must-Staple
-- (intermediate path / bag filtering). false → unknown returns false (rare).
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
	if tls == false or meta ~= nil then
		return false
	end
	return fail_closed_unknown == true
end

-- Colony floor: peers advance ocsp-floor/{fp} on publish/tombstone using CA-signed
-- this_update_unix only (not wall-clock published_unix — clocks drift across nodes).
-- Missing local this_update_unix is no opinion (do not treat as 0 vs a positive floor).
local function meta_unix_field(meta, key)
	if type(meta) ~= "table" or type(key) ~= "string" then
		return nil
	end
	local u = meta[key]
	if type(u) == "number" and u > 0 then
		return math.floor(u)
	end
	if type(u) == "string" then
		local n = tonumber(u)
		if n and n > 0 then
			return math.floor(n)
		end
	end
	return nil
end

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
local function cluster_floor_blocks(fingerprint, meta)
	if not is_fp64(fingerprint) then
		return false
	end
	local floor_rank = parse_floor_rank(read_file("/var/cache/bunkerweb/ssl/ocsp-floor/" .. fingerprint))
	if not floor_rank or floor_rank <= 0 then
		return false
	end
	local local_rank = meta_unix_field(meta, "this_update_unix")
	-- Missing local timing: no opinion — never invent 0 vs a positive floor.
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

-- Live shard must be scheduler-paged (canary handshake) before stapling.
-- Require explicit paged=true. Missing field is not canary proof
-- (restore stamps paged=false until canary succeeds).
local function shard_not_paged(meta)
	if type(meta) ~= "table" then
		return true
	end
	return meta.paged ~= true
end

-- Job tombstone writes "tombstoned": true before DER unlink / epoch bump.
-- Handshake must sample this flag (not only .ocsp_epoch), or L1 can keep
-- stapling the last GOOD while the multi-step write is mid-flight.
local function meta_tombstoned(meta)
	return type(meta) == "table" and meta.tombstoned == true
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

local function ocsp_ligand_path(fingerprint)
	return "/var/cache/bunkerweb/ssl/ocsp-ligand/" .. fingerprint
end

-- Integer soft_recall_gen from ligand / ocsp.json / allow-pin.
-- Missing key → 0 (upgrade grace so pre-gen pins still match).
-- Present but non-integer (table, bool, non-digit string, NaN, negative) → nil
-- so generation_tuple / allow-pin match fail closed (KEEP pin; no CAS revoke).
-- Job-minted counter: bumps on soft-recall so peer-refuse / allow identity
-- (der_sha256, soft_recall_gen) cannot re-match a leftover pin after re-page.
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
	return nil
end

-- Load ocsp-ligand/{fp}. Prefer this over in-shard ocsp.json for der_sha256 binding.
-- Reject when ligand.fingerprint disagrees with the path fingerprint (a self-asserted
-- fingerprint inside the file must not bless a different SPKI directory).
-- Per-request cache: avoids re-reading same ligand multiple times in one handshake
local function read_ocsp_ligand(fingerprint)
	if not is_fp64(fingerprint) then
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
	obj.soft_recall_gen = soft_recall_gen_of(obj)
	-- Cache successful decode
	if ctx and ctx.bw_ocsp_ligand_cache then
		ctx.bw_ocsp_ligand_cache[fingerprint] = obj
	end
	return obj
end

-- Merge already-read ligand with shard meta (caller reads ligand once per decision).
-- Rules (load-bearing — HTTP and stream must agree):
--   * ligand wins der_sha256 + soft_recall_gen
--   * tombstone from EITHER side forces tombstoned + paged=false
--   * paged=true only when shard meta exists AND both sides say paged
--     (missing shard meta never grants canary trust)
--   * expires_unix = min of positive values (generation authority pairs with
--     the tighter death clock, not a stale looser shard deadline)
--   * fingerprint is the path fp (never trust a self-assert alone)
local function merge_ligand(shard_meta, ligand, fingerprint)
	if not ligand then
		return shard_meta
	end
	local merged = {}
	if type(shard_meta) == "table" then
		for k, v in pairs(shard_meta) do
			merged[k] = v
		end
	end
	merged.der_sha256 = ligand.der_sha256
	merged.soft_recall_gen = ligand.soft_recall_gen
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
	local shard_exp = type(shard_meta) == "table" and tonumber(shard_meta.expires_unix) or nil
	local ligand_exp = tonumber(ligand.expires_unix)
	if shard_exp and shard_exp > 0 and ligand_exp and ligand_exp > 0 then
		merged.expires_unix = math.min(math.floor(shard_exp), math.floor(ligand_exp))
	elseif ligand_exp and ligand_exp > 0 then
		merged.expires_unix = math.floor(ligand_exp)
	elseif shard_exp and shard_exp > 0 then
		merged.expires_unix = math.floor(shard_exp)
	end
	if type(fingerprint) == "string" then
		merged.fingerprint = fingerprint
	elseif type(ligand.fingerprint) == "string" then
		merged.fingerprint = ligand.fingerprint
	end
	return merged
end

-- Effective generation meta: read ligand once then merge.
ligand_or_meta = function(meta, fingerprint)
	return merge_ligand(meta, read_ocsp_ligand(fingerprint), fingerprint)
end

-- Peer-refuse / allow generation: (der_sha256, soft_recall_gen).
-- When resp bytes are present, body SHA wins. Meta/ligand der_sha256 is only a
-- fallback for meta-only DROP causes (tombstone / serial / canary) — never for
-- probe paths that pass resp=nil after CertID/ligand refuses (that would
-- compare-and-delete the GOOD generation using meta alone).
-- Type-drift soft_recall_gen → (body, nil): incomplete identity — callers must
-- not CAS/rematch on body alone (pin returns gen_type_drift KEEP). Missing body
-- still returns nil,nil.
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

-- serial-blacklist.json bans one leaf serial until a newer GOOD is published.
-- A different serial (reissue on the same key) is allowed. Unreadable /
-- ambiguous JSON while the file exists fails closed.
-- Per-request cache: avoids re-reading and re-validating the serial blacklist per cert
local function serial_blacklist_blocks(fingerprint, resp)
	if not is_fp64(fingerprint) or type(resp) ~= "string" or resp == "" then
		return false
	end

	-- Initialize per-request cache on first use
	local ctx = ngx.ctx
	if ctx and not ctx.bw_ocsp_serial_cache then
		ctx.bw_ocsp_serial_cache = {}
	end

	-- Create cache key from fingerprint and response binding to uniquely identify this check
	-- (same fingerprint with different responses should each be checked)
	local binding = resp_binding(resp)
	local serial_cache_key = fingerprint .. "|" .. (binding or "")

	-- Check per-request cache first
	if ctx and ctx.bw_ocsp_serial_cache then
		local cached = ctx.bw_ocsp_serial_cache[serial_cache_key]
		if cached ~= nil then
			-- Cached value is boolean (true = blocked, false = allowed)
			return cached == true
		end
	end

	-- Cache miss: read and validate from disk
	local raw = read_file(
		"/var/cache/bunkerweb/ssl/"
			.. fingerprint:sub(1, 1)
			.. "/"
			.. fingerprint:sub(2, 2)
			.. "/"
			.. fingerprint
			.. "/serial-blacklist.json"
	)
	local blocked
	if not raw or raw == "" then
		-- No blacklist file: this response is allowed
		blocked = false
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
				local rest = first and raw:match('"serial_hex"%s*:%s*"[0-9A-Fa-f]+".-("serial_hex"%s*:%s*"[0-9A-Fa-f]+")')
				if rest then
					log(ngx.ERR, "OCSP serial blacklist ambiguous; refusing staple fp=" .. fingerprint:sub(1, 16) .. "...")
					blocked = true
				else
					local banned_hex = banned:upper():gsub("^0+", "")
					if banned_hex == "" then
						banned_hex = "0"
					end
					local got_hex = ocsp_resp_serial_hex(resp, banned_hex)
					if not got_hex then
						log(
							ngx.ERR,
							"OCSP serial blacklist present but response serial unreadable; refusing staple fp="
								.. fingerprint:sub(1, 16)
								.. "..."
						)
						blocked = true
					elseif got_hex == banned_hex then
						log(
							ngx.ERR,
							"OCSP serial blacklist refuse staple fp="
								.. fingerprint:sub(1, 16)
								.. "... serial_hex="
								.. banned_hex:sub(1, 16)
						)
						blocked = true
					else
						blocked = false
					end
				end
			end
		end
	end

	-- Cache result: store boolean (true = blocked, false = allowed)
	if ctx and ctx.bw_ocsp_serial_cache then
		ctx.bw_ocsp_serial_cache[serial_cache_key] = blocked
	end
	return blocked
end

-- Shared ligand verdict: one ligand read, hardened merge, body binding.
-- Single source of truth for HTTP (ssl-certificate-by-lua.conf) and stream
-- (this module). An inlined copy in the conf caused a zone-split after the
-- outside-ligand move — do not reintroduce it.
-- Returns ok, reason, meta_sha, body_sha, eff_meta.
-- Paged shards fail closed on ligand ENOENT (promote tear / missing publish).
-- Unpaged / soft-recall may still bind via in-shard der_sha256 (cutover).
local function ligand_verdict(shard_meta, fingerprint, resp)
	if not fingerprint or not is_fp64(fingerprint) then
		return false, "fingerprint_mismatch_or_missing_meta", nil, nil, shard_meta
	end
	local ligand = read_ocsp_ligand(fingerprint)
	local meta = merge_ligand(shard_meta, ligand, fingerprint)
	-- Canary-paged generations require the outside-shard ligand.
	if not ligand then
		local paged = type(shard_meta) == "table" and shard_meta.paged == true
		if paged then
			return false, "ligand_missing", nil, nil, meta
		end
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

local function ocsp_json_ligand_matches(meta, fingerprint, resp)
	local ok, reason, meta_sha, body_sha = ligand_verdict(meta, fingerprint, resp)
	return ok, reason, meta_sha, body_sha
end

-- Ligand+paged only (CLI canary stamped this body). Handshake skip-validate must
-- also require a live allow-pin generation match — see pin.canary_trust_ok /
-- bunkerweb.ocsp.canary_paged_body_ok (pin wraps this). Store stays pin-free
-- (require DAG: store cannot import pin).
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

-- Effective ligand sha for L1 disk-match (HTTP conf / stream warmer).
-- Returns sha string or nil; tombstoned / missing ligand for a paged shard → nil
-- so L1 cannot keep a body the handshake would refuse.
function _M.ligand_effective_sha(shard_meta, fingerprint)
	local ligand = read_ocsp_ligand(fingerprint)
	local eff = merge_ligand(shard_meta, ligand, fingerprint)
	if type(eff) ~= "table" then
		return nil
	end
	if eff.tombstoned == true then
		return nil
	end
	if type(shard_meta) == "table" and shard_meta.paged == true and not ligand then
		return nil
	end
	if type(eff.der_sha256) == "string" and #eff.der_sha256 == 64 then
		return eff.der_sha256:lower()
	end
	return nil
end

-- Shared HTTP↔stream L1↔disk coherence. Fail-closed like ligand_verdict:
-- corrupt meta / paged+ligand ENOENT / require-path gaps drop L1. Publish-gap keep
-- (meta+DER both gone, epoch still matches) only while outside ligand is paged=true
-- AND ligand_effective_sha names the cached binding — never bare true / ligand-only
-- after a full shard retract. HTTP conf must call this export rather than inlining.
local function l1_body_matches_disk(fingerprint, resp, stored_epoch)
	local binding = resp_binding(resp)
	if not binding then
		return false
	end
	if not fingerprint or not is_fp64(fingerprint) then
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
	pcall(function()
		local meta_path = "/var/cache/bunkerweb/ssl/"
			.. fingerprint:sub(1, 1)
			.. "/"
			.. fingerprint:sub(2, 2)
			.. "/"
			.. fingerprint
			.. "/ocsp.json"
		local f = io.open(meta_path, "r")
		if not f then
			meta_missing = true
			return
		end
		local raw = f:read("*a")
		f:close()
		if type(raw) ~= "string" or #raw == 0 then
			meta_corrupt = true
			return
		end
		local ok_decode, decoded = pcall(require("cjson").decode, raw)
		if not ok_decode or type(decoded) ~= "table" then
			meta_corrupt = true
			return
		end
		shard_meta = decoded
		if decoded.tombstoned == true then
			tombstoned = true
			return
		end
		if type(decoded.der_sha256) == "string" then
			local sha = decoded.der_sha256:lower()
			if #sha == 64 and sha:match("^[0-9a-f]+$") then
				disk_sha = sha
			end
		end
	end)
	if tombstoned or meta_corrupt then
		return false
	end

	local eff = _M.ligand_effective_sha(shard_meta, fingerprint)
	if type(eff) == "string" and #eff == 64 then
		disk_sha = eff
	elseif type(shard_meta) == "table" and shard_meta.paged == true then
		return false
	elseif eff == nil and disk_sha == nil then
		return false
	end

	if disk_sha then
		return disk_sha == binding
	end
	-- Both shard files gone: do NOT keep L1 on ligand SHA alone (staggered job
	-- delete can leave outside ligand naming the old body). Require ligand present
	-- with paged=true (active canary generation mid-promote) plus SHA match.
	if meta_missing and not read_file(ocsp_path(fingerprint)) then
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
		local ligand_sha = _M.ligand_effective_sha(nil, fingerprint)
		return type(ligand_sha) == "string" and #ligand_sha == 64 and ligand_sha == binding
	end
	return false
end

l1_matches_disk = function(_internalstore, fingerprint, resp, stored_epoch)
	return l1_body_matches_disk(fingerprint, resp, stored_epoch)
end

function _M.l1_body_matches_disk(fingerprint, resp, stored_epoch)
	return l1_body_matches_disk(fingerprint, resp, stored_epoch)
end

-- Fingerprint-hint path cannot call validate_ocsp_response (no leaf PEM).
-- Require meta.fingerprint match AND der_sha256 == sha256(body) so a swapped
-- ocsp.der under matching SPKI meta cannot be stapled.
-- Logs accept/refuse with truncated expected vs observed digests for audit.
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

-- Must-Staple may not rely on stream-private crypto-verified L1 alone.
-- Returns true, or false, raw ligand_verdict reason for OCSP_MUST_STAPLE_REFUSE.
-- Raw reason (not shared_ligand_*) so KEEP_ALLOW[ligand_missing] can hold the pin;
-- format_staple_decision still aliases to staple_decision=shared_ligand.
local function must_staple_binds_shared_ligand(meta, fingerprint, resp)
	local ok, reason = ocsp_json_ligand_matches(meta, fingerprint, resp)
	if ok then
		return true
	end
	return false, tostring(reason or "ligand_mismatch")
end

-- Absolute unix nextUpdate from job meta. Requires expires_unix (no ISO+Ns fallback).
local function meta_expires_unix(meta)
	if type(meta) ~= "table" then
		return nil
	end
	local u = meta.expires_unix
	if type(u) == "number" and u > 0 then
		return math.floor(u)
	end
	if type(u) == "string" then
		local n = tonumber(u)
		if n and n > 0 then
			return math.floor(n)
		end
	end
	return nil
end

function _M.meta_expires_unix(meta)
	return meta_expires_unix(meta)
end

-- Wall-clock stop from published_unix + max age (independent of nextUpdate).
local function meta_max_age_unix(meta)
	if type(meta) ~= "table" then
		return nil
	end
	local u = meta.max_age_unix
	if type(u) == "number" and u > 0 then
		return math.floor(u)
	end
	if type(u) == "string" then
		local n = tonumber(u)
		if n and n > 0 then
			return math.floor(n)
		end
	end
	local published = meta.published_unix
	if type(published) == "string" then
		published = tonumber(published)
	end
	if type(published) == "number" and published > 0 then
		-- Match PREVIOUS_GOOD_MAX_AGE_SECONDS in ocsp-refresh.py (24h).
		return math.floor(published) + 86400
	end
	return nil
end

-- False at death time (nextUpdate/max_age minus skew).
-- Also enforces intrinsic signed-window policy when this_update_unix is present.
-- Meta must carry a death clock (expires_unix and/or max_age/published). L1's
-- cached expires may only shorten that clock — never keep a stripped-meta DER alive.
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

local function resp_still_fresh(expires_unix, fingerprint, meta)
	meta = meta or (fingerprint and read_ocsp_json(fingerprint)) or nil
	local ok_intrinsic, why = intrinsic_timing_ok(meta)
	if not ok_intrinsic then
		log(
			ngx.ERR,
			"OCSP intrinsic timing refuse reason="
				.. tostring(why)
				.. " fp="
				.. tostring(fingerprint and fingerprint:sub(1, 16) or "?")
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
			"OCSP refuse staple: no expires_unix/max_age death clock fp="
				.. tostring(fingerprint and fingerprint:sub(1, 16) or "?")
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

meta_effective_expires_unix = function(meta, expires_unix)
	local exp = expires_unix or meta_expires_unix(meta)
	local max_age = meta_max_age_unix(meta)
	if exp and max_age then
		if max_age < exp then
			return max_age
		end
		return exp
	end
	return exp or max_age
end

-- Tri-state export for HTTP/conf callers that need unknown ≠ false vs true.
-- Returns true | false | nil (see resolve_leaf_must_staple).
function _M.resolve_leaf_must_staple(cert_pem, fingerprint)
	return resolve_leaf_must_staple(cert_pem, fingerprint)
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
	meta_effective_expires_unix = meta_effective_expires_unix,
	meta_tombstoned = meta_tombstoned,
	must_staple_binds_shared_ligand = must_staple_binds_shared_ligand,
	ocsp_json_authorizes_resp = ocsp_json_authorizes_resp,
	ocsp_json_ligand_matches = ocsp_json_ligand_matches,
	ocsp_json_must_staple = ocsp_json_must_staple,
	read_ocsp_json = read_ocsp_json,
	resolve_leaf_must_staple = resolve_leaf_must_staple,
	resp_still_fresh = resp_still_fresh,
	serial_blacklist_blocks = serial_blacklist_blocks,
	shard_not_paged = shard_not_paged,
	soft_recall_gen_of = soft_recall_gen_of,
	warm_cache = warm_cache,
}

return _M
