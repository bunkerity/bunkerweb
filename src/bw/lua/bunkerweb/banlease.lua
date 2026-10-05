local cjson = require("cjson")
local random = require("resty.random")
local rstring = require("resty.string")

local decode = cjson.decode
local encode = cjson.encode
local format = string.format
local byte = string.byte
local ngx = ngx

local banlease = {}

banlease.RANK = { explicit_service = 1, explicit_global = 2, lease_service = 3, lease_global = 4 }

local REASON_IDS = {
	["crowdsec"] = "crowdsec",
	["bad behavior"] = "bad_behavior",
	["manual"] = "manual",
	["ui"] = "ui",
	["api"] = "api",
}
local KNOWN_IDS = {}
for _, id in pairs(REASON_IDS) do
	KNOWN_IDS[id] = true
end

function banlease.reason_id(reason)
	return REASON_IDS[reason]
end

function banlease.is_known_id(id)
	return KNOWN_IDS[id] == true
end

function banlease.lease_key(ip, service)
	if service then
		return "bans_cs_service_" .. service .. "_ip_" .. ip
	end
	return "bans_cs_ip_" .. ip
end

function banlease.is_lease_key(key)
	return key:sub(1, 8) == "bans_cs_"
end

function banlease.meta()
	return ngx.shared.bans_meta
end

local EPOCH_KEY_TTL = 86400

-- Every write to bans_meta uses safe_set/safe_add, so nothing in this dict is ever evicted to make room: when the
-- dict is full a write fails instead. epoch_seq therefore never disappears and never repeats a value.
-- A missing epoch_seq (first use) is created once with safe_add; a failed creation means "no epochs" (fail open).
local function next_seq(dict)
	local seq = dict:incr("epoch_seq", 1)
	if seq then
		return seq
	end
	dict:safe_add("epoch_seq", 0)
	return dict:incr("epoch_seq", 1)
end

local function get_epoch(prefix, ip, create)
	local dict = banlease.meta()
	if not dict then
		return nil
	end
	local key = prefix .. ip
	local value = dict:get(key)
	if value ~= nil or not create then
		return value
	end
	local seq, err = next_seq(dict)
	if not seq then
		return nil, err
	end
	local ok = dict:safe_add(key, seq, EPOCH_KEY_TTL)
	if not ok then
		return dict:get(key)
	end
	return seq
end

-- Always creates the key. On any failure the key is deleted (delete never needs memory): a missing epoch never
-- equals a captured one, so every holder of the old value is fenced.
local function bump_epoch(prefix, ip)
	local dict = banlease.meta()
	if not dict then
		return nil, "no bans_meta dict"
	end
	local key = prefix .. ip
	local seq, err = next_seq(dict)
	if seq then
		local ok, set_err = dict:safe_set(key, seq, EPOCH_KEY_TTL)
		if ok then
			return seq
		end
		err = set_err
	end
	dict:delete(key)
	return nil, err
end

-- Create-only: nil when the key already exists (another worker created it) or cannot be written
function banlease.create_lease_epoch(ip)
	local dict = banlease.meta()
	if not dict then
		return nil
	end
	local seq = next_seq(dict)
	if not seq or not dict:safe_add("le_" .. ip, seq, EPOCH_KEY_TTL) then
		return nil
	end
	return seq
end

function banlease.lease_epoch(ip, create)
	return get_epoch("le_", ip, create)
end

function banlease.marker_epoch(ip, create)
	return get_epoch("me_", ip, create)
end

function banlease.bump_lease_epoch(ip)
	return bump_epoch("le_", ip)
end

function banlease.bump_marker_epoch(ip)
	return bump_epoch("me_", ip)
end

-- Explicit ban mutations: only fence markers that can exist, so nothing is allocated while TLS drop is off
function banlease.bump_marker_epoch_if_present(ip)
	local dict = banlease.meta()
	if not dict or dict:get("me_" .. ip) == nil then
		return nil
	end
	return bump_epoch("me_", ip)
end

function banlease.read_marker(service, ip)
	local dict = banlease.meta()
	if not dict then
		return nil
	end
	local raw = dict:get("rs_" .. (service or "") .. "_" .. ip)
	if not raw then
		return nil
	end
	local ok, marker = pcall(decode, raw)
	if not ok or type(marker) ~= "table" then
		return nil
	end
	return marker
end

function banlease.write_marker(service, ip, id, rank, epoch, ttl)
	local dict = banlease.meta()
	if not dict then
		return false
	end
	return dict:safe_set("rs_" .. (service or "") .. "_" .. ip, encode({ id = id, rank = rank, epoch = epoch }), ttl)
			and true
		or false
end

function banlease.format_raw_addr(packed, family)
	if type(packed) ~= "string" then
		return nil, "no address"
	end
	if family == "inet" and #packed == 4 then
		return format("%d.%d.%d.%d", byte(packed, 1, 4))
	end
	if family ~= "inet6" or #packed ~= 16 then
		return nil, "unsupported address family"
	end
	if packed:sub(1, 12) == string.rep("\0", 10) .. "\255\255" then
		return format("%d.%d.%d.%d", byte(packed, 13, 16))
	end
	local words = {}
	for i = 1, 16, 2 do
		local hi, lo = byte(packed, i, i + 1)
		words[#words + 1] = hi * 256 + lo
	end
	-- RFC 5952: compress the longest run (2 or more) of zero words
	local best_start, best_len, cur_start, cur_len = 0, 0, 0, 0
	for i = 1, 8 do
		if words[i] == 0 then
			if cur_len == 0 then
				cur_start = i
			end
			cur_len = cur_len + 1
			if cur_len > best_len then
				best_start, best_len = cur_start, cur_len
			end
		else
			cur_len = 0
		end
	end
	local parts = {}
	local i = 1
	while i <= 8 do
		if best_len >= 2 and i == best_start then
			parts[#parts + 1] = (i == 1) and ":" or ""
			i = i + best_len
			if i > 8 then
				parts[#parts + 1] = ""
			end
		else
			parts[#parts + 1] = format("%x", words[i])
			i = i + 1
		end
	end
	return table.concat(parts, ":")
end

function banlease.new_incarnation()
	local bytes = random.bytes(16, true)
	if not bytes then
		return nil, "no random bytes"
	end
	return rstring.to_hex(bytes)
end

-- The Redis epoch lives 7 days (604800 s) and is renewed by every bump or promotion.
-- KEYS[1] epoch, KEYS[2] lease ; ARGV[1] captured epoch ("" = checked and absent), ARGV[2] new incarnation,
-- ARGV[3] lease value, ARGV[4] ttl
local PROMOTE_SCRIPT = [[
	local cur = redis.call("GET", KEYS[1])
	if not cur then
		if ARGV[1] ~= "" then return "stale" end -- the epoch existed at capture and vanished since: fence
		redis.call("SET", KEYS[1], ARGV[2] .. ":1", "EX", 604800)
		redis.call("SET", KEYS[2], ARGV[3], "EX", tonumber(ARGV[4]))
		return "ok"
	end
	if cur ~= ARGV[1] then return "stale" end
	redis.call("SET", KEYS[2], ARGV[3], "EX", tonumber(ARGV[4]))
	return "ok"
]]

-- KEYS[1] epoch, KEYS[2] optional lease ; ARGV[1] new incarnation
local BUMP_SCRIPT = [[
	local cur = redis.call("GET", KEYS[1])
	local inc, n = nil, nil
	if cur then inc, n = string.match(cur, "^(.+):(%d+)$") end
	if inc then
		redis.call("SET", KEYS[1], inc .. ":" .. (tonumber(n) + 1), "EX", 604800)
	else
		redis.call("SET", KEYS[1], ARGV[1] .. ":1", "EX", 604800)
	end
	if KEYS[2] then redis.call("DEL", KEYS[2]) end
	return 1
]]

local PROVENANCE_FIELDS = { "id", "origin", "scenario", "type", "scope", "value", "expires_at", "remediation" }
local MAX_DECISIONS = 10
local MAX_REASON_DATA = 4096

function banlease.build_lease(evidence, now, refresh)
	if type(evidence) ~= "table" or evidence.source ~= "lapi" or evidence.remediation ~= "ban" then
		return nil, "not a LAPI ban"
	end
	local decisions = type(evidence.decisions) == "table" and evidence.decisions or {}
	local ban_expires
	for _, decision in ipairs(decisions) do
		if
			decision.remediation == "ban"
			and decision.id ~= nil
			and type(decision.expires_at) == "number"
			and decision.expires_at > now
			and (not ban_expires or decision.expires_at > ban_expires)
		then
			ban_expires = decision.expires_at
		end
	end
	if not ban_expires then
		return nil, "no live ban decision"
	end
	-- Never 0: a zero TTL means permanent
	local ttl = math.max(1, math.floor(math.min(ban_expires - now, refresh)))
	local provenance = {}
	for i = 1, math.min(#decisions, MAX_DECISIONS) do
		local row = {}
		for _, field in ipairs(PROVENANCE_FIELDS) do
			row[field] = decisions[i][field]
		end
		provenance[i] = row
	end
	return ttl,
		{
			version = 1,
			source = "lapi",
			lease = true,
			instance = evidence.instance,
			connection = evidence.connection,
			service_scope = evidence.service_scope,
			remediation = "ban",
			captured_at = evidence.captured_at,
			decisions = provenance,
		}
end

-- reason_data of a listed row is at most MAX_REASON_DATA bytes once encoded: the last decisions go first, then
-- everything but the identifying fields.
function banlease.cap_reason_data(reason_data)
	if type(reason_data) ~= "table" then
		return {}
	end
	local ok, encoded = pcall(encode, reason_data)
	if ok and #encoded <= MAX_REASON_DATA then
		return reason_data
	end
	local decisions = reason_data.decisions
	if ok and type(decisions) == "table" then
		while #decisions > 0 and #encoded > MAX_REASON_DATA do
			decisions[#decisions] = nil
			ok, encoded = pcall(encode, reason_data)
			if not ok then
				break
			end
		end
		if ok and #encoded <= MAX_REASON_DATA then
			return reason_data
		end
	end
	return {
		version = reason_data.version,
		lease = reason_data.lease,
		instance = reason_data.instance,
		connection = reason_data.connection,
		service_scope = reason_data.service_scope,
		truncated = true,
	}
end

-- The GET /bans row of a decoded ban or lease. A permanent ban reports exp 0.
function banlease.ban_row(kind, ip, service, ban_scope, data, ttl)
	if data.permanent then
		ttl = 0
	end
	return {
		ip = ip,
		reason = data.reason,
		service = service or data.service,
		date = data.date,
		country = data.country,
		ban_scope = ban_scope,
		exp = math.floor(ttl),
		permanent = data.permanent or false,
		kind = kind,
		reason_data = banlease.cap_reason_data(data.reason_data),
	}
end

local function use_redis()
	local value, err = require("bunkerweb.utils").get_variable("USE_REDIS", false)
	if not value then
		return nil, "can't get USE_REDIS variable : " .. tostring(err)
	end
	return value == "yes"
end

-- One EVAL on a fresh connection. Returns the reply, or nil and the reason.
local function redis_eval(script, keys, argv)
	local store = require("bunkerweb.clusterstore"):new()
	local ok, err = store:connect()
	if not ok then
		return nil, err
	end
	local args = { script, #keys }
	for _, key in ipairs(keys) do
		args[#args + 1] = key
	end
	for _, arg in ipairs(argv) do
		args[#args + 1] = arg
	end
	local reply, call_err = store:call("eval", unpack(args))
	store:close()
	if type(reply) ~= "string" and type(reply) ~= "number" then
		return nil, call_err or "unexpected reply"
	end
	return reply
end

local function scoped_service(service, ban_scope)
	return ban_scope == "service" and service or nil
end

function banlease.promote_lease(ip, service, ban_scope, ttl, reason_data, country, captured)
	-- A missing epoch never equals a captured one: no epoch means no lease
	local current = banlease.lease_epoch(ip, false)
	if type(captured) ~= "table" or current == nil or current ~= captured.lease_epoch then
		return false, "stale"
	end
	local key = banlease.lease_key(ip, scoped_service(service, ban_scope))
	local value = encode({
		reason = "crowdsec",
		service = service or "unknown",
		date = os.time(),
		country = country or "local",
		ban_scope = ban_scope,
		reason_data = reason_data,
		permanent = false,
		kind = "crowdsec_lease",
		lease_epoch = captured.lease_epoch,
	})
	local status = "written"
	local redis_on, err = use_redis()
	if redis_on == nil then
		return false, err
	end
	if redis_on then
		if captured.redis_epoch == nil then
			status = "local_only"
		else
			local incarnation, inc_err = banlease.new_incarnation()
			if not incarnation then
				return false, inc_err
			end
			local rediskeys = require("bunkerweb.rediskeys")
			local cluster = rediskeys.cluster_mode()
			local reply = redis_eval(PROMOTE_SCRIPT, { rediskeys.cs_epoch(ip, cluster), rediskeys.ban(key, cluster) }, {
				captured.redis_epoch or "",
				incarnation,
				value,
				ttl,
			})
			if reply == "stale" then
				return false, "stale"
			elseif reply ~= "ok" then
				status = "local_only"
			end
		end
	end
	-- The Redis call yielded: a removal that ran meanwhile wins
	if banlease.lease_epoch(ip, false) ~= captured.lease_epoch then
		return false, "stale"
	end
	local ok, set_err = require("bunkerweb.datastore"):new():set_with_retries(key, value, ttl)
	if not ok then
		return false, "datastore:set_with_retries() error : " .. tostring(set_err)
	end
	local meta = banlease.meta()
	if meta then
		if service then
			meta:delete("rs_" .. service .. "_" .. ip)
		end
		meta:delete("rs__" .. ip)
	end
	return true, status
end

function banlease.bump_redis_epoch(ip)
	local redis_on, err = use_redis()
	if redis_on == nil then
		return false, err
	end
	if not redis_on then
		return true
	end
	local incarnation, inc_err = banlease.new_incarnation()
	if not incarnation then
		return false, inc_err
	end
	local rediskeys = require("bunkerweb.rediskeys")
	local reply, redis_err = redis_eval(
		BUMP_SCRIPT,
		{ rediskeys.cs_epoch(ip, rediskeys.cluster_mode()) },
		{ incarnation }
	)
	if not reply then
		return false, redis_err
	end
	return true
end

function banlease.remove_lease(ip, service, ban_scope)
	local key = banlease.lease_key(ip, scoped_service(service, ban_scope))
	-- Before anything that can yield
	banlease.bump_lease_epoch(ip)
	banlease.bump_marker_epoch(ip)
	require("bunkerweb.datastore"):new():delete(key)
	local detail = { redis = "disabled" }
	local failure
	local redis_on, err = use_redis()
	if redis_on == nil then
		failure = err
	elseif redis_on then
		local incarnation, inc_err = banlease.new_incarnation()
		if incarnation then
			local rediskeys = require("bunkerweb.rediskeys")
			local cluster = rediskeys.cluster_mode()
			local reply, redis_err = redis_eval(
				BUMP_SCRIPT,
				{ rediskeys.cs_epoch(ip, cluster), rediskeys.ban(key, cluster) },
				{ incarnation }
			)
			if reply then
				detail.redis = "deleted"
			else
				failure = "redis: " .. tostring(redis_err)
			end
		else
			failure = "redis: " .. tostring(inc_err)
		end
	end
	-- A promotion or a lookup that yielded around the removal must find the epochs moved
	banlease.bump_lease_epoch(ip)
	banlease.bump_marker_epoch(ip)
	if failure then
		return false, failure
	end
	return true, detail
end

-- The local lease copy first (it only counts while its epoch is current), else with Redis on an exact read of that
-- one key. Returns the row, or nil and the error, plus whether Redis was read.
function banlease.lookup_lease(ip, service, ban_scope)
	local scope_service = scoped_service(service, ban_scope)
	local key = banlease.lease_key(ip, scope_service)
	local datastore = require("bunkerweb.datastore"):new()
	local raw = datastore:get(key)
	if raw then
		local ok, data = pcall(decode, raw)
		if ok and type(data) == "table" then
			local epoch = banlease.lease_epoch(ip, false)
			local valid = not banlease.meta() or (epoch ~= nil and data.lease_epoch == epoch)
			local ttl_ok, ttl = datastore:ttl(key)
			if valid and ttl_ok then
				local row = banlease.ban_row("crowdsec_lease", ip, scope_service, ban_scope, data, ttl)
				row.source = "local"
				return row, nil, false
			end
		end
	end
	local redis_on, err = use_redis()
	if redis_on == nil then
		return nil, err, false
	end
	if not redis_on then
		return nil, nil, false
	end
	local rediskeys = require("bunkerweb.rediskeys")
	local store = require("bunkerweb.clusterstore"):new()
	local connected, connect_err = store:connect()
	if not connected then
		return nil, "can't connect to redis : " .. tostring(connect_err), true
	end
	local redis_key = rediskeys.ban(key, rediskeys.cluster_mode())
	local value, get_err = store:call("get", redis_key)
	if value == nil or value == false then
		store:close()
		return nil, "redis GET failed : " .. tostring(get_err), true
	end
	if value == ngx.null then
		store:close()
		return nil, nil, true
	end
	local ttl, ttl_err = store:call("ttl", redis_key)
	store:close()
	if type(ttl) ~= "number" then
		return nil, "redis TTL failed : " .. tostring(ttl_err), true
	end
	-- -2: the key expired between the two calls
	if ttl == -2 then
		return nil, nil, true
	end
	local ok, data = pcall(decode, value)
	if not ok or type(data) ~= "table" then
		return nil, "can't decode the lease from redis", true
	end
	local row = banlease.ban_row("crowdsec_lease", ip, scope_service, ban_scope, data, math.max(ttl, 0))
	row.source = "redis"
	return row, nil, true
end

-- ClientHello drop. Nothing below may yield: no Redis, no cosocket, no mlcache callback, no resty.lock, no sleep, no
-- ngx.var. Every unknown means "do not drop": the access phase stays authoritative.
-- Returns "drop" | "detect" | nil, the canonical reason id and the client IP.
local function decide(service, proxy_protocol, real_ip)
	if proxy_protocol or real_ip then
		return nil
	end
	local utils = require("bunkerweb.utils")
	local ctx = service and { bw = { server_name = service } } or nil
	local reasons = utils.get_variable("BANS_TLS_DROP_REASONS", service ~= nil, ctx)
	if reasons == nil or reasons == "" then
		return nil -- off, or unreadable: fail open
	end
	local redis_on = utils.get_variable("USE_REDIS", false)
	if redis_on == nil then
		return nil
	end
	local security_mode = utils.get_variable("SECURITY_MODE", service ~= nil, ctx)
	if security_mode == nil then
		return nil
	end
	-- QUIC transport parameters: never dropped here in this release, the access phase enforces the ban
	local quic, quic_err = require("ngx.ssl.clienthello").get_client_hello_ext(57)
	if quic or quic_err then
		return nil
	end
	local ip = banlease.format_raw_addr(require("ngx.ssl").raw_client_addr())
	if not ip then
		return nil
	end
	local banned, reason, rank = utils.is_banned_local(ip, service)
	if banned == nil then
		return nil
	end
	local id
	if redis_on == "yes" then
		-- A local hit cannot prove that no better ban lives only in Redis: only the resolved marker, written by the
		-- access phase after its full lookup, counts, and a missing epoch never matches.
		local marker = banlease.read_marker(service or "", ip)
		local current = marker and banlease.marker_epoch(ip, false)
		if not marker or current == nil or marker.epoch ~= current then
			return nil
		end
		id = marker.id
		if banned and rank < marker.rank then
			id = banlease.reason_id(reason)
		end
	elseif banned then
		id = banlease.reason_id(reason)
	end
	if not id or not (" " .. reasons .. " "):find(" " .. id .. " ", 1, true) then
		return nil
	end
	local dict = banlease.meta()
	local memo = "wl_" .. (service or "") .. "_" .. ip
	if dict and dict:get(memo) then
		return nil
	end
	local whitelisted = utils.is_ip_whitelisted(ip, service, { local_only = true })
	if whitelisted ~= false then
		-- Only a positive result is remembered: a stale one lets the handshake through, the access phase decides
		if whitelisted == true and dict then
			dict:safe_set(memo, true, 10)
		end
		return nil
	end
	if security_mode == "detect" then
		return "detect", id, ip
	end
	return "drop", id, ip
end

function banlease.tls_drop_decision(service, proxy_protocol, real_ip)
	local ok, verdict, id, ip = pcall(decide, service, proxy_protocol, real_ip)
	if not ok then
		return nil
	end
	return verdict, id, ip
end

function banlease.tls_drop_hook(service, proxy_protocol, real_ip)
	local verdict, id, ip = banlease.tls_drop_decision(service, proxy_protocol, real_ip)
	if not verdict then
		return
	end
	local dict = banlease.meta()
	local warn = dict and dict:safe_add("tw_" .. ip, true, 60)
	if verdict == "detect" then
		if warn then
			ngx.log(ngx.WARN, "[BANS] detect mode: would drop banned IP ", ip, " (", id, ") at the TLS ClientHello")
		end
		return
	end
	local metrics = ngx.shared.metrics_datastore
	if metrics then
		-- No "_counter_" in the name: the metrics timer never restores or overwrites it
		metrics:incr("tls_drops_" .. id .. "_" .. ngx.worker.id(), 1, 0)
	end
	if warn then
		ngx.log(ngx.WARN, "[BANS] dropped banned IP ", ip, " (", id, ") at the TLS ClientHello")
	end
	ngx.exit(ngx.ERROR)
	return true
end

return banlease
