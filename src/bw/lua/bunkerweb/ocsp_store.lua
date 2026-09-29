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

-- Disk paths and pin bus use lowercase hex (job + ocsp_pin). is_fp64 allows
-- A-F; normalize before path join / cache key / fingerprint equality checks.
local function fp64_or_nil(fingerprint)
	if not is_fp64(fingerprint) then
		return nil
	end
	return fingerprint:lower()
end

-- Harden unix timestamps: digit-only strings / finite positive numbers
-- (no tonumber("1e20") / "inf" surprises). Shared by expires, thisUpdate, max_age.
local function positive_unix(v)
	if type(v) == "number" then
		if v ~= v or v == math.huge or v == -math.huge or v <= 0 then
			return nil
		end
		return math.floor(v)
	end
	if type(v) == "string" and v:match("^%d+$") then
		local n = tonumber(v)
		if n and n > 0 then
			return n
		end
	end
	return nil
end

-- Forward decls: warm_cache tightens expires / gen against live ligand (defined below).
local ligand_or_meta
local soft_recall_gen_of
local meta_effective_expires_unix
local read_ocsp_json
local read_ocsp_ligand

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
	if not internalstore then
		return nil
	end
	fingerprint = fp64_or_nil(fingerprint)
	if not fingerprint then
		return nil
	end
	local key = cache_key(fingerprint)
	if not key then
		return nil
	end
	local ok, blob = pcall(function()
		-- Shared dict (not per-worker LRU): one warmer refill serves every worker.
		return internalstore:get(key)
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
	fingerprint = fp64_or_nil(fingerprint)
	-- Live merged death clock wins: never mark verified under a looser expires than
	-- ligand/shard min (L1 TTL and resp_still_fresh would disagree across workers).
	-- Must merge shard ocsp.json too — ligand-only merge drops a tighter shard
	-- expires / soft_recall_gen when the ligand omits or is looser.
	local live_meta = nil
	if fingerprint then
		live_meta = ligand_or_meta(nil, fingerprint)
		-- Never re-warm a tombstoned generation (ligand may tombstone before shard).
		if type(live_meta) == "table" and live_meta.tombstoned == true then
			return
		end
		local tight = meta_effective_expires_unix(live_meta, nil)
		if type(tight) ~= "number" or tight <= 0 then
			-- Stripped meta+ligand: never park from caller/L1 expires alone.
			return
		end
		if type(expires_unix) ~= "number" or expires_unix <= 0 then
			-- Adopt live death clock. Caller had no clock to disagree with —
			-- do not demote verified (post-validate parks often pass shard-only
			-- meta_effective which is nil when only the ligand carries expires).
			expires_unix = tight
		elseif expires_unix > tight then
			-- Caller/L1 claimed a looser deadline than live merge — demote.
			if mark_verified then
				mark_verified = false
			end
			expires_unix = tight
		end
		-- expires_unix <= tight: keep caller's tighter clock and verified bit.
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
	-- When live meta/ligand is present, its gen wins (caller can lag a soft-recall bump).
	-- soft_recall_gen_of(nil) is upgrade-grace 0 — do not treat that as live authority.
	if type(live_meta) == "table" then
		local live_gen = soft_recall_gen_of(live_meta)
		if type(live_gen) == "number" then
			if type(gen) == "number" and gen ~= live_gen and mark_verified then
				-- Gen drift: park DER for reuse but do not claim verified trust.
				binding = nil
				mark_verified = false
			end
			gen = live_gen
		else
			-- Live type-drift (false sentinel / invalid): never park a gen that
			-- soft_recall_gen_of would refuse to match — clear gen + verified.
			binding = nil
			mark_verified = false
			gen = nil
		end
	elseif type(gen) ~= "number" then
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
	local key = fingerprint and cache_key(fingerprint) or nil
	if not key then
		return
	end
	pcall(function()
		internalstore:set(key, pack_l1(epoch, binding, resp, expires_unix, gen), ttl)
		-- Clear per-worker LRU so a prior worker-scoped put cannot shadow shared dict.
		internalstore:delete(key, true)
	end)
end

local function drop_cache(internalstore, fingerprint)
	fingerprint = fp64_or_nil(fingerprint)
	local key = fingerprint and cache_key(fingerprint) or nil
	if not key then
		return
	end
	pcall(function()
		internalstore:delete(key)
		internalstore:delete(key, true)
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
read_ocsp_json = function(fingerprint)
	fingerprint = fp64_or_nil(fingerprint)
	if not fingerprint then
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
		-- missing or empty (truncate): both cache as absent for this request.
		-- l1_body_matches_disk distinguishes empty via read_file's second return.
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

-- Tri-state leaf Must-Staple: TLS Feature, then ocsp.json positive, then unknown→nil.
-- Fail-closed gate: resolve_leaf_must_staple(...) ~= false.
-- meta without must_staple=true must NOT invent false when TLS Feature is unknown
-- (parse miss / unrecognized text) — aligns with HTTP leaf_requires tls_known rule.
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
		-- Resty positively parsed: no Must-Staple (extension absent or non-MS features).
		return false
	end
	-- tls == nil: unknown — do not trust "meta present without must_staple=true" as
	-- proven-false (job may omit the flag; resty may have failed).
	return nil
end

-- Boolean Must-Staple for a PEM block (leaf or intermediate).
-- fail_closed_unknown=true → treat resty miss + no positive json as Must-Staple
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
	if tls == false then
		return false
	end
	-- tls == nil: same as resolve_leaf — meta-without-flag is not proven-false.
	return fail_closed_unknown == true
end

-- Colony floor: peers advance ocsp-floor/{fp} on publish/tombstone using CA-signed
-- this_update_unix only (not wall-clock published_unix — clocks drift across nodes).
-- Missing local this_update_unix is no opinion (do not treat as 0 vs a positive floor).
local function meta_unix_field(meta, key)
	if type(meta) ~= "table" or type(key) ~= "string" then
		return nil
	end
	return positive_unix(meta[key])
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
-- Always sample live shard timing; caller meta can claim a higher this_update than
-- disk and fail-open colony floor during a lagging publish.
local function cluster_floor_blocks(fingerprint, _meta)
	fingerprint = fp64_or_nil(fingerprint)
	if not fingerprint then
		return false
	end
	local floor_rank = parse_floor_rank(read_file("/var/cache/bunkerweb/ssl/ocsp-floor/" .. fingerprint))
	if not floor_rank or floor_rank <= 0 then
		return false
	end
	local local_rank = meta_unix_field(read_ocsp_json(fingerprint), "this_update_unix")
	-- Missing live timing: no opinion — never invent 0 vs a positive floor,
	-- and never trust caller meta over a retracted/lagging shard.
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

-- Live view must be scheduler-paged (canary handshake) before stapling.
-- Require explicit paged=true. Missing field is not canary proof
-- (restore stamps paged=false until canary succeeds).
-- When fingerprint is provided, sample live ligand_or_meta so shard-only
-- caller meta cannot claim paged=true while the ligand is still unpaged/missing
-- (merge requires both sides — see merge_ligand).
local function shard_not_paged(meta, fingerprint)
	if fingerprint then
		local live = ligand_or_meta(nil, fingerprint)
		if type(live) ~= "table" then
			return true
		end
		meta = live
	end
	if type(meta) ~= "table" then
		return true
	end
	return meta.paged ~= true
end

-- Job tombstone writes "tombstoned": true before DER unlink / epoch bump.
-- Handshake must sample this flag (not only .ocsp_epoch), or L1 can keep
-- stapling the last GOOD while the multi-step write is mid-flight.
-- Optional fingerprint samples live shard + outside ligand via ligand_or_meta
-- (caller meta can lag a shard tombstone written before the ligand flips).
local function meta_tombstoned(meta, fingerprint)
	if type(meta) == "table" and meta.tombstoned == true then
		return true
	end
	if fingerprint then
		local live = ligand_or_meta(nil, fingerprint)
		if type(live) == "table" and live.tombstoned == true then
			return true
		end
	end
	return false
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

-- Disk paths and pin bus use lowercase hex (job + ocsp_pin). is_fp64 allows
-- A-F; normalize before path join / cache key / fingerprint equality checks.
local function ocsp_ligand_path(fingerprint)
	return "/var/cache/bunkerweb/ssl/ocsp-ligand/" .. fingerprint:lower()
end

-- Integer soft_recall_gen from ligand / ocsp.json / allow-pin.
-- Missing key → 0 (upgrade grace so pre-gen pins still match).
-- Present but non-integer (table, bool, non-digit string, NaN, negative) → nil
-- so generation_tuple / allow-pin match fail closed (KEEP pin; no CAS revoke).
-- Job-minted counter: bumps on soft-recall so peer-refuse / allow identity
-- (der_sha256, soft_recall_gen) cannot re-match a leftover pin after re-page.
--
-- Callers that must distinguish omit from explicit 0 (publish-gap keep) must
-- inspect the raw ligand field before soft_recall_gen_of — read_ocsp_ligand
-- leaves soft_recall_gen=nil when the JSON key was absent, and stores false
-- when the key was present but non-integer (so a later call here cannot
-- mistake invalid for omit→0).
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
	-- false sentinel (read_ocsp_ligand) and any other non-number → type drift.
	return nil
end

-- Load ocsp-ligand/{fp}. Prefer this over in-shard ocsp.json for der_sha256 binding.
-- Reject when ligand.fingerprint disagrees with the path fingerprint (a self-asserted
-- fingerprint inside the file must not bless a different SPKI directory).
-- Per-request cache: avoids re-reading same ligand multiple times in one handshake
read_ocsp_ligand = function(fingerprint)
	fingerprint = fp64_or_nil(fingerprint)
	if not fingerprint then
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
	-- Preserve key presence. soft_recall_gen_of maps omitted→0 for allow-pin
	-- upgrade grace, but publish-gap keep requires an *explicit* key on the
	-- ligand object (nil here means omitted — see l1_body_matches_disk).
	-- Assigning soft_recall_gen_of(obj) unconditionally turned every omit into
	-- 0 and made the publish-gap nil-check dead (fail-open mid-promote).
	-- Present-but-invalid must NOT become nil: a later soft_recall_gen_of would
	-- treat that as omit→0 (upgrade grace) and rematch leftover gen-0 pins.
	-- Sentinel false → soft_recall_gen_of returns nil (type-drift / fail closed).
	local raw_gen = obj.soft_recall_gen
	if raw_gen == nil then
		obj.soft_recall_gen = nil
	else
		local normalized = soft_recall_gen_of(obj)
		if type(normalized) == "number" then
			obj.soft_recall_gen = normalized
		else
			obj.soft_recall_gen = false
		end
	end
	-- Cache successful decode
	if ctx and ctx.bw_ocsp_ligand_cache then
		ctx.bw_ocsp_ligand_cache[fingerprint] = obj
	end
	return obj
end

-- Harden expires_unix the same way as soft_recall_gen / thisUpdate (positive_unix).
local positive_expires_unix = positive_unix

-- Merge already-read ligand with shard meta (caller reads ligand once per decision).
-- Rules (load-bearing — HTTP and stream must agree):
--   * ligand wins der_sha256; soft_recall_gen only when ligand key is present
--     (omit must not clobber shard gen→upgrade-grace 0 and rematch leftover pins)
--   * tombstone from EITHER side forces tombstoned + paged=false
--   * paged=true only when shard meta exists AND both sides say paged
--     (missing shard meta never grants canary trust)
--   * expires_unix = min of positive values (generation authority pairs with
--     the tighter death clock, not a stale looser shard deadline)
--   * fingerprint is the path fp (never trust a self-assert alone)
local function merge_ligand(shard_meta, ligand, fingerprint)
	if not ligand then
		-- Shallow copy: read_ocsp_json caches the shard table in ngx.ctx; returning
		-- it by reference lets a caller mutate poison the rest of the request.
		if type(shard_meta) ~= "table" then
			return shard_meta
		end
		local copy = {}
		for k, v in pairs(shard_meta) do
			copy[k] = v
		end
		if type(fingerprint) == "string" then
			copy.fingerprint = fingerprint:lower()
		end
		return copy
	end
	local merged = {}
	if type(shard_meta) == "table" then
		for k, v in pairs(shard_meta) do
			merged[k] = v
		end
	end
	merged.der_sha256 = ligand.der_sha256
	-- Present ligand gen (number / false sentinel) wins. Omitted key leaves shard
	-- gen intact — unconditional nil assign turned soft-recall shard gen=N into
	-- omit→0 and rematched leftover gen-0 pins while ligand lagged the bump.
	if ligand.soft_recall_gen ~= nil then
		merged.soft_recall_gen = ligand.soft_recall_gen
	end
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
	local shard_exp = type(shard_meta) == "table" and positive_expires_unix(shard_meta.expires_unix) or nil
	local ligand_exp = positive_expires_unix(ligand.expires_unix)
	if shard_exp and ligand_exp then
		merged.expires_unix = math.min(shard_exp, ligand_exp)
	elseif ligand_exp then
		merged.expires_unix = ligand_exp
	elseif shard_exp then
		merged.expires_unix = shard_exp
	end
	if type(fingerprint) == "string" then
		-- Path fp wins; lowercase so ligand_verdict equality is case-stable.
		merged.fingerprint = fingerprint:lower()
	elseif type(ligand.fingerprint) == "string" then
		merged.fingerprint = ligand.fingerprint:lower()
	end
	return merged
end

-- Effective generation meta: read ligand once then merge.
-- Always sample live shard via read_ocsp_json (per-request cached). Caller meta
-- can lag a shard-first tombstone / soft_recall_gen bump / expires tighten;
-- preferring it fail-opened freshness, tombstone, generation, and floor checks.
-- Disk absent/unreadable → nil shard (do not resurrect caller over a retract).
ligand_or_meta = function(_meta, fingerprint)
	return merge_ligand(read_ocsp_json(fingerprint), read_ocsp_ligand(fingerprint), fingerprint)
end

-- Live soft_recall_gen after ligand↔shard merge. HTTP and stream must share this:
-- ligand-only soft_recall_gen_of rematches leftover gen-0 pins when the ligand
-- omits the key while the shard already holds a bumped gen (same class as
-- merge_ligand omit-keeps-shard). Missing meta+ligand → upgrade-grace 0.
-- Type-drift (false sentinel / invalid) → nil (fail closed).
local function live_soft_recall_gen(fingerprint)
	fingerprint = fp64_or_nil(fingerprint)
	if not fingerprint then
		return nil
	end
	local live = ligand_or_meta(nil, fingerprint)
	if type(live) ~= "table" then
		return 0
	end
	return soft_recall_gen_of(live)
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
	fingerprint = fp64_or_nil(fingerprint)
	if not fingerprint or type(resp) ~= "string" or resp == "" then
		return false
	end

	-- Initialize per-request cache on first use
	local ctx = ngx.ctx
	if ctx and not ctx.bw_ocsp_serial_cache then
		ctx.bw_ocsp_serial_cache = {}
	end

	-- Cache key needs a stable body id. When resp_binding fails, do NOT key as
	-- "fp|" — distinct unreadable DERs would collide and a prior "allowed"
	-- (no blacklist file) could fail-open a later banned body.
	local binding = resp_binding(resp)
	local serial_cache_key = nil
	if binding then
		serial_cache_key = fingerprint .. "|" .. binding
	end

	-- Check per-request cache first
	if serial_cache_key and ctx and ctx.bw_ocsp_serial_cache then
		local cached = ctx.bw_ocsp_serial_cache[serial_cache_key]
		if cached ~= nil then
			-- Cached value is boolean (true = blocked, false = allowed)
			return cached == true
		end
	end

	-- Cache miss: read and validate from disk
	local raw, why = read_file(
		"/var/cache/bunkerweb/ssl/"
			.. fingerprint:sub(1, 1)
			.. "/"
			.. fingerprint:sub(2, 2)
			.. "/"
			.. fingerprint
			.. "/serial-blacklist.json"
	)
	local blocked
	if not raw then
		-- Missing file: no ban. Empty (truncate race) = present-but-unreadable → refuse.
		if why == "empty" then
			log(ngx.ERR, "OCSP serial blacklist empty; refusing staple fp=" .. fingerprint:sub(1, 16) .. "...")
			blocked = true
		else
			blocked = false
		end
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
				local rest = first
					and raw:match('"serial_hex"%s*:%s*"[0-9A-Fa-f]+".-("serial_hex"%s*:%s*"[0-9A-Fa-f]+")')
				if rest then
					log(
						ngx.ERR,
						"OCSP serial blacklist ambiguous; refusing staple fp=" .. fingerprint:sub(1, 16) .. "..."
					)
					blocked = true
				else
					local banned_hex = banned:upper():gsub("^0+", "")
					if banned_hex == "" then
						banned_hex = "0"
					end
					-- want_hex hit → banned. want miss + parseable body → not banned.
					-- Unreadable DER (no serials at all) → refuse (fail closed).
					local got_hex = ocsp_resp_serial_hex(resp, banned_hex)
					if got_hex == banned_hex then
						log(
							ngx.ERR,
							"OCSP serial blacklist refuse staple fp="
								.. fingerprint:sub(1, 16)
								.. "... serial_hex="
								.. banned_hex:sub(1, 16)
						)
						blocked = true
					elseif not ocsp_resp_serial_hex(resp) then
						log(
							ngx.ERR,
							"OCSP serial blacklist present but response serial unreadable; refusing staple fp="
								.. fingerprint:sub(1, 16)
								.. "..."
						)
						blocked = true
					else
						blocked = false
					end
				end
			end
		end
	end

	-- Cache result: store boolean (true = blocked, false = allowed).
	-- Skip when binding is nil (no stable key — see above).
	if serial_cache_key and ctx and ctx.bw_ocsp_serial_cache then
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
	fingerprint = fp64_or_nil(fingerprint)
	if not fingerprint then
		return false, "fingerprint_mismatch_or_missing_meta", nil, nil, shard_meta
	end
	-- Live shard wins over caller meta (stale caller can miss a shard-first tombstone).
	local live_shard = read_ocsp_json(fingerprint)
	local ligand = read_ocsp_ligand(fingerprint)
	local meta = merge_ligand(live_shard, ligand, fingerprint)
	-- Canary-paged generations require the outside-shard ligand.
	if not ligand then
		local paged = type(live_shard) == "table" and live_shard.paged == true
		if paged then
			return false, "ligand_missing", nil, nil, meta
		end
	end
	-- Tombstone from either side (merge forces tombstoned=true). Callers often
	-- only sample shard ocsp.json before this — ligand-first tombstone must refuse.
	if type(meta) == "table" and meta.tombstoned == true then
		return false, "tombstoned", nil, nil, meta
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
-- Live shard wins over caller meta (same contract as ligand_verdict).
function _M.ligand_effective_sha(_shard_meta, fingerprint)
	local live_shard = read_ocsp_json(fingerprint)
	local ligand = read_ocsp_ligand(fingerprint)
	local eff = merge_ligand(live_shard, ligand, fingerprint)
	if type(eff) ~= "table" then
		return nil
	end
	if eff.tombstoned == true then
		return nil
	end
	if type(live_shard) == "table" and live_shard.paged == true and not ligand then
		return nil
	end
	if type(eff.der_sha256) == "string" then
		local sha = eff.der_sha256:lower()
		if #sha == 64 and sha:match("^[0-9a-f]+$") then
			return sha
		end
	end
	return nil
end

-- Shared HTTP↔stream L1↔disk coherence. Fail-closed like ligand_verdict:
-- corrupt meta / paged+ligand ENOENT / require-path gaps drop L1. Publish-gap keep
-- (meta+DER both gone, epoch still matches) only while outside ligand is paged=true
-- with an explicit soft_recall_gen and der_sha256 matching the cached binding —
-- never bare ligand SHA after a full shard retract. HTTP conf must call this
-- export rather than inlining.
local function l1_body_matches_disk(fingerprint, resp, stored_epoch)
	local binding = resp_binding(resp)
	if not binding then
		return false
	end
	fingerprint = fp64_or_nil(fingerprint)
	if not fingerprint then
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
	do
		local meta_path = "/var/cache/bunkerweb/ssl/"
			.. fingerprint:sub(1, 1)
			.. "/"
			.. fingerprint:sub(2, 2)
			.. "/"
			.. fingerprint
			.. "/ocsp.json"
		-- Use shared read_file so empty (truncate race) ≠ missing (ENOENT).
		local raw, why = read_file(meta_path)
		if not raw then
			if why == "empty" then
				meta_corrupt = true
			else
				meta_missing = true
			end
		else
			local ok_decode, decoded = pcall(require("cjson").decode, raw)
			if not ok_decode or type(decoded) ~= "table" then
				meta_corrupt = true
			else
				shard_meta = decoded
				if decoded.tombstoned == true then
					tombstoned = true
				elseif type(decoded.der_sha256) == "string" then
					local sha = decoded.der_sha256:lower()
					if #sha == 64 and sha:match("^[0-9a-f]+$") then
						disk_sha = sha
					end
				end
			end
		end
	end
	if tombstoned or meta_corrupt then
		return false
	end

	-- Shard meta+DER both gone: publish-gap keep only (never bare ligand SHA).
	-- Must run before ligand_effective_sha, which would otherwise accept any
	-- ligand der_sha256 and skip paged + explicit soft_recall_gen gates.
	if meta_missing then
		-- Clean publish-gap: both meta and DER gone (ENOENT). Empty DER is a
		-- truncate race, not absence — same as empty ocsp.json → drop L1.
		local der_raw, der_why = read_file(ocsp_path(fingerprint))
		if der_raw then
			-- DER without ocsp.json: not a clean publish-gap; drop L1.
			return false
		end
		if der_why == "empty" then
			return false
		end
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
		if ligand.tombstoned == true then
			return false
		end
		local ligand_sha = ligand.der_sha256
		return type(ligand_sha) == "string"
			and #ligand_sha == 64
			and ligand_sha:match("^[0-9a-f]+$") ~= nil
			and ligand_sha == binding
	end

	local eff = _M.ligand_effective_sha(shard_meta, fingerprint)
	if type(eff) == "string" and #eff == 64 and eff:match("^[0-9a-f]+$") then
		disk_sha = eff
	elseif type(shard_meta) == "table" and shard_meta.paged == true then
		return false
	elseif read_ocsp_ligand(fingerprint) then
		-- Ligand present but effective sha nil → tombstoned (or refuse-shaped).
		-- Never fall back to in-shard der_sha256 while outside ligand refuses.
		return false
	elseif disk_sha == nil then
		return false
	end

	return disk_sha == binding
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
	return positive_expires_unix(meta.expires_unix)
end

function _M.meta_expires_unix(meta)
	return meta_expires_unix(meta)
end

-- Wall-clock stop from published_unix + max age (independent of nextUpdate).
local function meta_max_age_unix(meta)
	if type(meta) ~= "table" then
		return nil
	end
	local max_age = positive_unix(meta.max_age_unix)
	if max_age then
		return max_age
	end
	local published = positive_unix(meta.published_unix)
	if published then
		-- Match PREVIOUS_GOOD_MAX_AGE_SECONDS in ocsp-refresh.py (24h).
		return published + 86400
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
	-- Overlay outside ligand so freshness uses the same min(expires) as
	-- warm_cache / merge_ligand. ligand_or_meta always samples live shard
	-- (caller meta ignored — can lag tombstone / expires tighten).
	local fp = fp64_or_nil(fingerprint)
	if fp then
		meta = ligand_or_meta(nil, fp)
	elseif type(meta) ~= "table" then
		meta = nil
	end
	-- After ligand merge: refuse if either side tombstoned (callers often only
	-- checked shard ocsp.json before calling).
	if type(meta) == "table" and meta.tombstoned == true then
		return false, "tombstoned"
	end
	local ok_intrinsic, why = intrinsic_timing_ok(meta)
	if not ok_intrinsic then
		log(
			ngx.ERR,
			"OCSP intrinsic timing refuse reason=" .. tostring(why) .. " fp=" .. tostring(fp and fp:sub(1, 16) or "?")
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
			"OCSP refuse staple: no expires_unix/max_age death clock fp=" .. tostring(fp and fp:sub(1, 16) or "?")
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

-- Meta death clock first; L1 expires_unix may only tighten, never extend or
-- invent a clock when meta/ligand is stripped (matches resp_still_fresh).
meta_effective_expires_unix = function(meta, expires_unix)
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
		-- No meta/ligand death clock: do not keep a stripped-meta DER alive via L1.
		return nil
	end
	if type(expires_unix) == "number" and expires_unix > 0 and expires_unix < exp then
		return math.floor(expires_unix)
	end
	return exp
end

-- Tri-state export for HTTP/conf callers that need unknown ≠ false vs true.
-- Returns true | false | nil (see resolve_leaf_must_staple).
function _M.resolve_leaf_must_staple(cert_pem, fingerprint)
	return resolve_leaf_must_staple(cert_pem, fingerprint)
end

function _M.serial_blacklist_blocks(fingerprint, resp)
	return serial_blacklist_blocks(fingerprint, resp)
end

function _M.meta_tombstoned(meta, fingerprint)
	return meta_tombstoned(meta, fingerprint)
end

-- Public colony-floor gate (HTTP must call this — do not reintroduce a loose
-- tonumber inline that accepts "1e20" / inf and forks Must-Staple closes).
function _M.cluster_floor_blocks(fingerprint, meta)
	return cluster_floor_blocks(fingerprint, meta)
end

-- Public freshness gate (HTTP must call this — do not reintroduce a shard-only
-- inline that ignores ligand min(expires) / tombstone).
function _M.resp_still_fresh(expires_unix, fingerprint, meta)
	return resp_still_fresh(expires_unix, fingerprint, meta)
end

-- Public live gen (HTTP must call this — do not reintroduce ligand-only soft_recall
-- that ignores shard gen when the ligand omits the key).
function _M.live_soft_recall_gen(fingerprint)
	return live_soft_recall_gen(fingerprint)
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
	live_soft_recall_gen = live_soft_recall_gen,
	-- pin.ligand_or_meta wrapper caches via these (same ngx.ctx table as read path).
	merge_ligand = merge_ligand,
	meta_effective_expires_unix = meta_effective_expires_unix,
	meta_tombstoned = meta_tombstoned,
	must_staple_binds_shared_ligand = must_staple_binds_shared_ligand,
	ocsp_json_authorizes_resp = ocsp_json_authorizes_resp,
	ocsp_json_ligand_matches = ocsp_json_ligand_matches,
	ocsp_json_must_staple = ocsp_json_must_staple,
	read_ocsp_json = read_ocsp_json,
	read_ocsp_ligand = read_ocsp_ligand,
	resolve_leaf_must_staple = resolve_leaf_must_staple,
	resp_still_fresh = resp_still_fresh,
	serial_blacklist_blocks = serial_blacklist_blocks,
	shard_not_paged = shard_not_paged,
	soft_recall_gen_of = soft_recall_gen_of,
	warm_cache = warm_cache,
}

return _M
