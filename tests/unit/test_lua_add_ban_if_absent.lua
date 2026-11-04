-- Plain Lua check of utils.add_ban(..., { if_absent = true }): the insert-only ban write (CORE-3). It never replaces a
-- ban of either store, never leaves a local copy next to a Redis ban it could not see, and removes only its own
-- Redis key. Without opts the write is unchanged.
-- The Redis stand-in applies SET (NX, EX) and the compare-and-delete script for real, and lets a test run code at any
-- Redis call or local add: that is how the administrative interleavings and the outage are injected.
-- Run: lua tests/unit/test_lua_add_ban_if_absent.lua   (from the repo root)
local root = arg[0]:match("^(.*)/tests/unit/") or "."
package.path = root .. "/src/bw/lua/?.lua;" .. package.path

local failures = 0
local reset
local function it(name, fn)
	reset()
	local ok, err = pcall(fn)
	print((ok and "PASS " or "FAIL ") .. name .. (ok and "" or (": " .. tostring(err))))
	if not ok then
		failures = failures + 1
	end
end
local function eq(a, b, what)
	assert(a == b, (what or "value") .. ": expected " .. tostring(b) .. " got " .. tostring(a))
end

-- A tiny JSON, taken from the lease fakes; everything else those fakes install is replaced below
local json = dofile(root .. "/tests/unit/lua_lease_fakes.lua")(root).json
package.loaded["bunkerweb.utils"] = nil
package.loaded["bunkerweb.datastore"] = nil
package.loaded["bunkerweb.clusterstore"] = nil

local null = setmetatable({}, {})
local clock, current_phase, sleeps = 0, "access", 0
local hooks, flags, logs = {}, {}, {}
local function new_dict()
	local data, expiry = {}, {}
	local dict = { _data = data, _expiry = expiry }
	function dict.get(_, k)
		if expiry[k] and clock >= expiry[k] then
			data[k], expiry[k] = nil, nil
		end
		return data[k]
	end
	function dict.safe_set(_, k, v)
		data[k] = v
		return true
	end
	function dict.safe_add(_, k, v, ttl)
		if hooks.lock_try and k:sub(1, 9) == "ban_lock_" then
			hooks.lock_try(k, v)
		end
		if dict:get(k) ~= nil then
			return false, "exists"
		end
		data[k], expiry[k] = v, ttl and clock + ttl
		return true
	end
	function dict.incr(_, k, v)
		if data[k] == nil then
			return nil, "not found"
		end
		data[k] = data[k] + v
		return data[k]
	end
	function dict.delete(_, k)
		data[k], expiry[k] = nil, nil
		if hooks.unlocked and k:sub(1, 9) == "ban_lock_" then
			hooks.unlocked(k)
		end
	end
	return dict
end

-- Every random id is different: the compare-and-delete tells our write from another one by it
local random_counter = 0
local with_stream_store = true
local function install_ngx()
	_G.ngx = {
		null = null,
		shared = {
			bans_meta = new_dict(),
			datastore = new_dict(),
			internalstore = {},
			datastore_stream = with_stream_store and {} or nil,
		},
		config = { subsystem = "http" },
		thread = { kill = function() end },
		re = { match = function() end },
		var = {},
		now = function()
			return 1700000000 + clock
		end,
		sleep = function(delay)
			sleeps = sleeps + 1
			clock = clock + delay
			if hooks.sleep then
				hooks.sleep(delay)
			end
		end,
		time = function()
			return 1700000000
		end,
		log = function() end,
		get_phase = function()
			return current_phase
		end,
		ERR = 4,
		WARN = 5,
		INFO = 7,
		HTTP_FORBIDDEN = 403,
		HTTP_CLOSE = 444,
		ERROR = -1,
	}
end
install_ngx()
package.loaded["cjson"] = json
package.loaded["resty.random"] = {
	bytes = function(n)
		random_counter = random_counter + 1
		return string.rep(string.char(random_counter % 256), n)
	end,
}
package.loaded["resty.string"] = {
	to_hex = function(s)
		return (s:gsub(".", function(c)
			return string.format("%02x", c:byte())
		end))
	end,
}
package.loaded["bunkerweb.logger"] = {
	new = function()
		return {
			log = function(_, level, message)
				logs[#logs + 1] = { level = level, message = message }
			end,
		}
	end,
}
package.loaded["bunkerweb.mmdb"] = {}
package.loaded["resty.dns.resolver"] = {}
package.loaded["resty.session"] = { start = function() end }
package.loaded["resty.ipmatcher"] = {
	parse_ipv4 = function(ip)
		return ip:match("^%d+%.%d+%.%d+%.%d+$") ~= nil
	end,
	parse_ipv6 = function(ip)
		return ip:find(":", 1, true) ~= nil
	end,
	new = function()
		return {
			match = function()
				return false
			end,
		}
	end,
}
local quic_ext
package.loaded["ngx.ssl.clienthello"] = {
	get_client_hello_ext = function()
		return quic_ext
	end,
}
local peer_raw = "\1\2\3\4"
package.loaded["ngx.ssl"] = {
	raw_client_addr = function()
		return peer_raw, "inet"
	end,
	proxy_protocol_addr = function() end,
}

-- Datastores: rows[key] = { value, ttl }. `hooks.before_add(store, key)` runs just before a create-only write.
local rows, stream_rows, internal = {}, {}, {}
local adds, sets = {}, {}
local function make_datastore(store, name)
	local obj = {}
	function obj.get(_, key)
		if store[key] == nil then
			return nil, "not found"
		end
		local value = store[key].value
		if hooks.after_get then
			hooks.after_get(name, key)
		end
		return value
	end
	function obj.set_with_retries(_, key, value, ttl)
		if hooks.before_set then
			hooks.before_set(name, key)
		end
		sets[#sets + 1] = name .. ":" .. key
		store[key] = { value = value, ttl = ttl }
		return true, "success"
	end
	function obj.add_with_retries(_, key, value, ttl)
		adds[#adds + 1] = name .. ":" .. key
		if hooks.before_add then
			hooks.before_add(name, key)
		end
		if flags.datastore_full == name then
			return false, "no memory"
		end
		if store[key] ~= nil then
			return false, "exists"
		end
		store[key] = { value = value, ttl = ttl }
		return true, "success"
	end
	function obj.delete(_, key)
		if hooks.before_delete then
			hooks.before_delete(name, key)
		end
		store[key] = nil
		return true, "success"
	end
	function obj.keys()
		local keys = {}
		for k in pairs(store) do
			keys[#keys + 1] = k
		end
		return keys
	end
	function obj.ttl(_, key)
		return true, store[key] and store[key].ttl or 0
	end
	return obj
end
local main_ds, stream_ds, internal_ds =
	make_datastore(rows, "main"), make_datastore(stream_rows, "stream"), make_datastore(internal, "internal")
local function datastore_for(dict)
	if dict ~= nil and dict == ngx.shared.internalstore then
		return internal_ds
	elseif dict ~= nil and dict == ngx.shared.datastore_stream then
		return stream_ds
	end
	return main_ds
end
package.loaded["bunkerweb.datastore"] = {
	new = function(_, dict)
		return datastore_for(dict)
	end,
}

-- Redis: redis[key] = { value, ttl }. `hooks.before_redis(cmd, args)` and `hooks.after_redis(cmd, args)` run around a
-- command. flags.set_fail: SET never applied, error reply. flags.set_lost: SET applied, reply lost.
local redis, rcalls = {}, {}
local function redis_ttl(args)
	for i, a in ipairs(args) do
		if a == "EX" then
			return tonumber(args[i + 1])
		end
	end
	return -1
end
local function has_arg(args, name)
	for _, a in ipairs(args) do
		if a == name then
			return true
		end
	end
	return false
end
package.loaded["bunkerweb.clusterstore"] = {
	new = function()
		local cs = { config_error = flags.config_error }
		function cs.connect(self)
			if self.config_error then
				return false, "invalid redis configuration : " .. self.config_error
			end
			if flags.redis_down then
				return false, "connection refused"
			end
			return true
		end
		function cs.close() end
		function cs.call(_, cmd, ...)
			local args = { ... }
			rcalls[#rcalls + 1] = { cmd = cmd, args = args }
			if hooks.before_redis then
				hooks.before_redis(cmd, args)
			end
			local result
			if cmd == "set" then
				local key, value = args[1], args[2]
				if flags.set_fail then
					return nil, "timeout"
				end
				if has_arg(args, "NX") and redis[key] ~= nil then
					result = null
				else
					redis[key] = { value = value, ttl = redis_ttl(args) }
					result = "OK"
				end
				if flags.set_lost then
					return nil, "timeout"
				end
			elseif cmd == "get" then
				if flags.get_fail then
					return nil, "timeout"
				end
				result = redis[args[1]] and redis[args[1]].value or null
			elseif cmd == "del" then
				redis[args[1]] = nil
				result = 1
			elseif cmd == "eval" then
				local script, nkeys = args[1], args[2]
				local keys, argv = {}, {}
				for i = 1, nkeys do
					keys[i] = args[2 + i]
				end
				for i = 3 + nkeys, #args do
					argv[#argv + 1] = args[i]
				end
				if script:find("TTL", 1, true) then
					-- the ban lookup of is_banned (no lease epoch)
					result = { null, -2, 0 }
					for i, key in ipairs(keys) do
						if redis[key] then
							result = { redis[key].value, redis[key].ttl, i }
							break
						end
					end
				elseif script:find("DEL", 1, true) then
					-- the compare-and-delete: the shipped script itself runs, on a two-command Redis
					assert(nkeys == 1 and #argv == 1, "compare-and-delete takes one key and one value")
					if flags.eval_fail then
						return nil, "timeout"
					end
					local env = {
						KEYS = keys,
						ARGV = argv,
						redis = {
							call = function(op, key)
								if op == "GET" then
									return redis[key] and redis[key].value or false
								elseif op == "DEL" then
									local existed = redis[key] ~= nil
									redis[key] = nil
									return existed and 1 or 0
								end
								error("unexpected redis command " .. tostring(op))
							end,
						},
					}
					result = assert(load(script, "=script", "t", env))()
				else
					error("unexpected script " .. script)
				end
			else
				error("unexpected redis command " .. tostring(cmd))
			end
			if hooks.after_redis then
				hooks.after_redis(cmd, args)
			end
			return result
		end
		return cs
	end,
}

local function load_utils(stream)
	if stream ~= with_stream_store then
		with_stream_store = stream
		install_ngx()
	end
	package.loaded["bunkerweb.utils"] = nil
	package.loaded["bunkerweb.banlease"] = nil
	local utils = require("bunkerweb.utils")
	utils.is_ip_whitelisted = function()
		return false
	end
	return utils, require("bunkerweb.banlease")
end
local utils, banlease = load_utils(true)

local function set_variables(vars)
	internal["variables"] = { value = { global = vars } }
end
reset = function()
	for _, t in ipairs({
		rows,
		stream_rows,
		redis,
		rcalls,
		adds,
		sets,
		hooks,
		flags,
		logs,
		ngx.shared.datastore._data,
		ngx.shared.datastore._expiry,
	}) do
		for k in pairs(t) do
			t[k] = nil
		end
	end
	for k in pairs(ngx.shared.bans_meta._data) do
		ngx.shared.bans_meta._data[k] = nil
	end
	clock, current_phase, sleeps = 0, "access", 0
	quic_ext = nil
	peer_raw = "\1\2\3\4"
	set_variables({ USE_REDIS = "yes", REDIS_CLUSTER_NODES = "", SECURITY_MODE = "block", BANS_TLS_DROP_REASONS = "" })
end

local IP = "1.2.3.4"
local KEY = "bans_ip_" .. IP
local function ban_json(reason, permanent, extra)
	local data = {
		reason = reason,
		service = "unknown",
		date = 1700000000,
		country = "local",
		ban_scope = "global",
		reason_data = {},
		permanent = permanent or false,
	}
	for k, v in pairs(extra or {}) do
		data[k] = v
	end
	return json.encode(data)
end
local function put_local(key, reason, permanent)
	rows[key] = { value = ban_json(reason, permanent), ttl = (not permanent) and 600 or nil }
end
local function put_redis(key, reason, permanent)
	redis[key] = { value = ban_json(reason, permanent), ttl = permanent and -1 or 600 }
end
local function local_reason(store, key)
	return store[key] and json.decode(store[key].value).reason or nil
end
local function count_redis(cmd)
	local n = 0
	for _, c in ipairs(rcalls) do
		if c.cmd == cmd then
			n = n + 1
		end
	end
	return n
end
local function guard_ban(ip)
	return utils.add_ban(ip or IP, "antiddos", 300, nil, nil, "global", { rule = "idle" }, { if_absent = true })
end

it("capability flag is exported", function()
	eq(utils.ADD_BAN_IF_ABSENT, 1)
end)

it("a fresh address is added in Redis (NX with EX) and in every local copy", function()
	local status = guard_ban()
	eq(status, "added")
	eq(local_reason(rows, KEY), "antiddos")
	eq(local_reason(stream_rows, KEY), "antiddos", "secondary local copy")
	assert(redis[KEY], "Redis key written")
	eq(redis[KEY].ttl, 300)
	eq(rows[KEY].ttl, 300)
	eq(rows[KEY].value, redis[KEY].value, "the local copy is the Redis value")
	local set = rcalls[1]
	eq(set.cmd, "set")
	assert(has_arg(set.args, "NX") and has_arg(set.args, "EX"), "SET NX EX")
	eq(#adds, 2, "primary and secondary created with add")
	eq(#sets, 0, "no overwriting write in the if_absent path")
end)

it("the value carries a random id, different on every write", function()
	guard_ban("1.2.3.4")
	guard_ban("1.2.3.5")
	local a = json.decode(redis["bans_ip_1.2.3.4"].value).nonce
	local b = json.decode(redis["bans_ip_1.2.3.5"].value).nonce
	assert(type(a) == "string" and #a >= 32, "id is at least 128 bits of hex")
	assert(a ~= b, "ids differ")
end)

it("a permanent if_absent ban is SET NX without EX and keeps no local ttl", function()
	local status = utils.add_ban(IP, "antiddos", 0, nil, nil, "global", {}, { if_absent = true })
	eq(status, "added")
	assert(not has_arg(rcalls[1].args, "EX"), "no EX")
	eq(redis[KEY].ttl, -1)
	eq(rows[KEY].ttl, nil)
	eq(json.decode(rows[KEY].value).permanent, true)
end)

it("service scope writes the service key", function()
	local status = utils.add_ban(IP, "antiddos", 300, "www", nil, "service", {}, { if_absent = true })
	eq(status, "added")
	assert(rows["bans_service_www_ip_" .. IP] and redis["bans_service_www_ip_" .. IP])
	assert(rows[KEY] == nil)
end)

it("an existing permanent ban in both stores survives", function()
	put_local(KEY, "manual", true)
	put_redis(KEY, "manual", true)
	local before_local, before_redis = rows[KEY].value, redis[KEY].value
	eq(guard_ban(), "exists")
	eq(rows[KEY].value, before_local)
	eq(redis[KEY].value, before_redis)
	eq(count_redis("set"), 0, "an existing local ban ends the call before Redis")
end)

it("an existing timed ban with another reason survives (Redis only)", function()
	put_redis(KEY, "bad behavior", false)
	local before = redis[KEY].value
	eq(guard_ban(), "exists")
	eq(redis[KEY].value, before)
	eq(rows[KEY], nil, "no local copy written")
	eq(stream_rows[KEY], nil)
	eq(#adds, 0)
end)

it("an existing service-scope ban survives", function()
	local key = "bans_service_www_ip_" .. IP
	put_local(key, "manual", false)
	put_redis(key, "manual", false)
	local before = rows[key].value
	eq(utils.add_ban(IP, "antiddos", 300, "www", nil, "service", {}, { if_absent = true }), "exists")
	eq(rows[key].value, before)
	eq(local_reason(redis, key), "manual")
end)

it("a local-only permanent ban survives and Redis stays empty", function()
	put_local(KEY, "manual", true)
	eq(guard_ban(), "exists")
	eq(next(redis), nil, "Redis has no key")
	eq(#rcalls, 0, "Redis is not asked")
	eq(local_reason(rows, KEY), "manual")
end)

it("Redis off: local check and one atomic add, no Redis call", function()
	set_variables({ USE_REDIS = "no", SECURITY_MODE = "block" })
	eq(guard_ban(), "added")
	eq(#rcalls, 0)
	eq(local_reason(rows, KEY), "antiddos")
	put_local("bans_ip_9.9.9.9", "manual", true)
	eq(guard_ban("9.9.9.9"), "exists")
	eq(local_reason(rows, "bans_ip_9.9.9.9"), "manual")
end)

it("Redis off: an administrative write between the check and the add is kept", function()
	set_variables({ USE_REDIS = "no", SECURITY_MODE = "block" })
	hooks.before_add = function(name, key)
		if name == "main" and not rows[key] then
			rows[key] = { value = ban_json("manual", true), ttl = nil }
		end
	end
	eq(guard_ban(), "exists")
	eq(local_reason(rows, KEY), "manual")
	eq(stream_rows[KEY], nil, "no secondary copy next to a ban we did not write")
end)

it("two concurrent if_absent calls write once (Redis on)", function()
	local results = {}
	local nested = false
	hooks.before_redis = function(cmd)
		if cmd == "set" and not nested then
			nested = true
			results.inner = guard_ban()
		end
	end
	results.outer = guard_ban()
	local added = (results.inner == "added" and 1 or 0) + (results.outer == "added" and 1 or 0)
	eq(added, 1, "exactly one added: " .. tostring(results.inner) .. "/" .. tostring(results.outer))
	eq(results.inner, "added")
	eq(results.outer, "exists")
	eq(local_reason(rows, KEY), "antiddos")
	eq(redis[KEY].value, rows[KEY].value, "the surviving ban is the one that won NX")
end)

it("two concurrent if_absent calls write once (Redis off)", function()
	set_variables({ USE_REDIS = "no", SECURITY_MODE = "block" })
	local results = {}
	local nested = false
	-- The other call runs whole between our first check and our lock attempt; a held lock section never yields
	hooks.lock_try = function()
		if not nested then
			nested = true
			results.inner = guard_ban()
		end
	end
	results.outer = guard_ban()
	eq(results.inner, "added")
	eq(results.outer, "exists")
end)

-- Administrative interleavings. The administrator is utils.add_ban without opts: it writes the local copies, then
-- publishes to Redis with a plain SET.
local function admin_ban(reason)
	return utils.add_ban(IP, reason or "manual", 0)
end

it("admin local write between our check and our add, publication after our NX: the admin ban wins", function()
	local admin_json
	hooks.before_redis = function(cmd)
		if cmd == "set" and not admin_json then
			-- the administrator's local write lands; its Redis publication is still in flight
			admin_json = ban_json("manual", true)
			rows[KEY] = { value = admin_json, ttl = nil }
			stream_rows[KEY] = { value = admin_json, ttl = nil }
		end
	end
	eq(guard_ban(), "exists")
	eq(rows[KEY].value, admin_json, "the local administrative value stays")
	eq(redis[KEY], nil, "our own Redis key was removed by the compare-and-delete")
	-- the delayed publication arrives
	redis[KEY] = { value = admin_json, ttl = -1 }
	eq(local_reason(redis, KEY), "manual")
	eq(local_reason(rows, KEY), "manual")
end)

it("admin local write after a failed NX against an older Redis ban: the admin local ban stays", function()
	put_redis(KEY, "bad behavior", false)
	local older = redis[KEY].value
	local admin_json = ban_json("manual", true)
	hooks.before_redis = function(cmd)
		if cmd == "set" then
			rows[KEY] = { value = admin_json, ttl = nil }
		end
	end
	eq(guard_ban(), "exists")
	eq(rows[KEY].value, admin_json, "we never touched the local copy")
	eq(redis[KEY].value, older, "NX left the older Redis ban")
	-- the administrator's publication overwrites Redis afterwards
	redis[KEY] = { value = admin_json, ttl = -1 }
	eq(local_reason(redis, KEY), "manual")
end)

it("admin writes between our NX and our primary add: the administrator's Redis key is never deleted", function()
	local admin_json = ban_json("manual", true)
	hooks.after_redis = function(cmd)
		if cmd == "set" and not hooks.done then
			hooks.done = true
			-- complete administrative add_ban: local copies, then a plain SET over our NX key
			rows[KEY] = { value = admin_json, ttl = nil }
			stream_rows[KEY] = { value = admin_json, ttl = nil }
			redis[KEY] = { value = admin_json, ttl = -1 }
		end
	end
	eq(guard_ban(), "exists")
	eq(rows[KEY].value, admin_json)
	eq(stream_rows[KEY].value, admin_json)
	eq(redis[KEY].value, admin_json, "the id no longer matches: the compare-and-delete leaves it")
	eq(count_redis("eval"), 1, "the compare-and-delete ran")
end)

it("admin writes between our NX and our secondary add: every administrative value is kept", function()
	local admin_json = ban_json("manual", true)
	hooks.before_add = function(name)
		if name == "stream" and not hooks.done then
			hooks.done = true
			rows[KEY] = { value = admin_json, ttl = nil } -- overwrites our primary copy too
			stream_rows[KEY] = { value = admin_json, ttl = nil }
			redis[KEY] = { value = admin_json, ttl = -1 }
		end
	end
	local status = guard_ban()
	assert(status == "added" or status == "exists", status)
	eq(rows[KEY].value, admin_json)
	eq(stream_rows[KEY].value, admin_json, "the secondary add did not replace the administrator's copy")
	eq(redis[KEY].value, admin_json)
end)

it("admin writes after ours overwrite every store", function()
	eq(guard_ban(), "added")
	admin_ban("manual")
	eq(local_reason(rows, KEY), "manual")
	eq(local_reason(stream_rows, KEY), "manual")
	eq(local_reason(redis, KEY), "manual")
end)

it("a Redis-held manual ban: exists, no local copy, and the core still drops it at the TLS ClientHello", function()
	set_variables({
		USE_REDIS = "yes",
		SECURITY_MODE = "block",
		BANS_TLS_DROP_REASONS = "manual",
		REDIS_CLUSTER_NODES = "",
	})
	put_redis(KEY, "manual", true)
	eq(guard_ban(), "exists")
	eq(rows[KEY], nil, "no local copy written")
	eq(stream_rows[KEY], nil)
	-- the access phase resolves the ban and publishes its marker, then the ClientHello decides from it
	local banned, reason = utils.is_banned(IP, nil, { bw = {} })
	assert(banned == true and reason == "manual", tostring(reason))
	local verdict, id = banlease.tls_drop_decision(nil, false, false, nil)
	eq(verdict, "drop")
	eq(id, "manual")
end)

-- A different instance writes only Redis; this instance's local stores never see its administrative write.
for _, phase in ipairs({ "after NX", "after local add" }) do
	it("remote admin overwrites " .. phase .. ": manual reason remains authoritative", function()
		set_variables({
			USE_REDIS = "yes",
			SECURITY_MODE = "block",
			BANS_TLS_DROP_REASONS = "manual",
			REDIS_CLUSTER_NODES = "",
		})
		local admin_json = ban_json("manual", true)
		local function overwrite()
			redis[KEY] = { value = admin_json, ttl = -1 }
		end
		if phase == "after NX" then
			hooks.after_redis = function(cmd)
				if cmd == "set" then
					overwrite()
				end
			end
		else
			hooks.before_redis = function(cmd)
				if cmd == "get" then
					eq(local_reason(rows, KEY), "antiddos", "primary already published")
					eq(local_reason(stream_rows, KEY), "antiddos", "secondary already published")
					overwrite()
				end
			end
		end
		eq(guard_ban(), "exists")
		eq(rows[KEY], nil, "stale primary removed")
		eq(stream_rows[KEY], nil, "stale secondary removed")
		eq(redis[KEY].value, admin_json, "permanent remote ban unchanged")
		eq(count_redis("get"), 1, "one ownership check")
		hooks.before_redis, hooks.after_redis = nil, nil
		local banned, reason = utils.is_banned(IP, nil, { bw = {} })
		assert(banned == true and reason == "manual", tostring(reason))
		local verdict, id = banlease.tls_drop_decision(nil, false, false, nil)
		eq(verdict, "drop")
		eq(id, "manual")
	end)
end

it("remote unban between NX and ownership check removes both new local copies", function()
	hooks.after_redis = function(cmd)
		if cmd == "set" then
			redis[KEY] = nil
		end
	end
	eq(guard_ban(), "exists")
	eq(rows[KEY], nil)
	eq(stream_rows[KEY], nil)
	eq(redis[KEY], nil)
	eq(utils.is_banned(IP, nil, { bw = {} }), false)
	eq(banlease.tls_drop_decision(nil, false, false, nil), nil)
end)

it("ownership read error removes local copies and reports error", function()
	flags.get_fail = true
	eq(guard_ban(), "error")
	eq(rows[KEY], nil)
	eq(stream_rows[KEY], nil)
	eq(local_reason(redis, KEY), "antiddos", "unknown Redis outcome keeps ordinary TTL")
end)

it("ownership cleanup keeps local values another administrator replaced", function()
	local admin_json = ban_json("manual", true)
	hooks.before_redis = function(cmd)
		if cmd == "get" then
			rows[KEY] = { value = admin_json, ttl = nil }
			stream_rows[KEY] = { value = admin_json, ttl = nil }
			redis[KEY] = { value = admin_json, ttl = -1 }
		end
	end
	eq(guard_ban(), "exists")
	eq(rows[KEY].value, admin_json)
	eq(stream_rows[KEY].value, admin_json)
	eq(redis[KEY].value, admin_json)
end)

it("Redis down: error, no local write", function()
	flags.redis_down = true
	local status, msg = guard_ban()
	eq(status, "error")
	assert(msg, "a message names the failure")
	eq(rows[KEY], nil)
	eq(stream_rows[KEY], nil)
	eq(#adds, 0)
end)

it("Redis outage with a pre-existing Redis manual ban: error, then the manual ban is the one lookups see", function()
	set_variables({
		USE_REDIS = "yes",
		SECURITY_MODE = "block",
		BANS_TLS_DROP_REASONS = "manual",
		REDIS_CLUSTER_NODES = "",
	})
	put_redis(KEY, "manual", true)
	flags.redis_down = true
	eq(guard_ban(), "error")
	eq(rows[KEY], nil, "nothing local could shadow the Redis ban")
	flags.redis_down = nil
	local banned, reason = utils.is_banned(IP, nil, { bw = {} })
	assert(banned == true and reason == "manual", tostring(reason))
	eq(banlease.tls_drop_decision(nil, false, false, nil), "drop")
end)

it("a SET error reply is an unknown outcome: error, no local write", function()
	flags.set_fail = true
	eq(guard_ban(), "error")
	eq(rows[KEY], nil)
	eq(redis[KEY], nil)
end)

it("a lost SET reply whose NX landed: error, no local write, the key is an ordinary ban with its ttl", function()
	flags.set_lost = true
	eq(guard_ban(), "error")
	eq(rows[KEY], nil)
	assert(redis[KEY] and redis[KEY].ttl == 300, "the Redis key expires with its ttl")
end)

it("a Redis configuration error is an error, not a local-only ban", function()
	flags.config_error = "bad nodes"
	eq(guard_ban(), "error")
	eq(rows[KEY], nil)
end)

it("an unreadable USE_REDIS setting is an error and writes nothing", function()
	internal["variables"] = { value = { global = {} } }
	eq(guard_ban(), "error")
	eq(rows[KEY], nil)
	eq(#rcalls, 0)
end)

it("a full local dict after our NX: our Redis key is removed and the call reports an error", function()
	flags.datastore_full = "main"
	eq(guard_ban(), "error")
	eq(redis[KEY], nil, "compare-and-delete removed our key")
	eq(rows[KEY], nil)
end)

it("a failed secondary copy only warns: the ban is added", function()
	flags.datastore_full = "stream"
	eq(guard_ban(), "added")
	eq(local_reason(rows, KEY), "antiddos")
	eq(stream_rows[KEY], nil)
	assert(redis[KEY])
end)

it("a failed compare-and-delete still reports exists and leaves the local value", function()
	local admin_json = ban_json("manual", true)
	hooks.before_add = function(name, key)
		if name == "main" and not rows[key] then
			rows[key] = { value = admin_json, ttl = nil }
		end
	end
	flags.eval_fail = true
	eq(guard_ban(), "exists")
	eq(rows[KEY].value, admin_json)
	assert(redis[KEY] and redis[KEY].ttl == 300, "our key is left to expire")
end)

it("remote unban: the surviving state is the one an ordinary add_ban leaves", function()
	local function snapshot()
		return {
			local_ttl = rows[KEY].ttl,
			redis_ttl = redis[KEY].ttl,
			reason = local_reason(rows, KEY),
			same_value = rows[KEY].value == redis[KEY].value,
			secondary = stream_rows[KEY] ~= nil,
		}
	end
	utils.add_ban("1.2.3.4", "antiddos", 300)
	local ordinary = snapshot()
	utils.remove_ban(IP)
	reset()
	eq(guard_ban(), "added")
	local ours = snapshot()
	for k, v in pairs(ordinary) do
		eq(ours[k], v, "field " .. k)
	end
	-- another instance deletes the Redis key: this instance keeps its local copy until it expires, as for any ban
	redis[KEY] = nil
	eq(local_reason(rows, KEY), "antiddos")
	eq(utils.is_banned_local(IP), true)
	-- and an unban here clears both stores
	utils.remove_ban(IP)
	eq(rows[KEY], nil)
	eq(stream_rows[KEY], nil)
	eq(redis[KEY], nil)
end)

it("a marker epoch that exists is fenced around an if_absent write", function()
	local before = banlease.marker_epoch(IP, true)
	assert(before, "marker epoch created")
	guard_ban()
	assert(banlease.marker_epoch(IP, false) ~= before, "the marker epoch moved")
end)

it("an invalid address is an error and writes nothing", function()
	local status, msg = utils.add_ban("not an ip", "antiddos", 300, nil, nil, "global", {}, { if_absent = true })
	eq(status, "error")
	eq(msg, "invalid IP address")
	eq(#rcalls, 0)
	eq(next(rows), nil)
end)

it("an IPv4-mapped IPv6 spelling is the same ban as the IPv4 one", function()
	put_local(KEY, "manual", true)
	eq(guard_ban("::ffff:1.2.3.4"), "exists")
end)

it("without opts the write is unchanged: overwriting set, then a plain Redis SET", function()
	put_local(KEY, "bad behavior", false)
	put_redis(KEY, "bad behavior", false)
	local ok, msg = utils.add_ban(IP, "manual", 120, nil, nil, "global", { a = 1 })
	eq(ok, true)
	eq(msg, "success")
	eq(local_reason(rows, KEY), "manual", "overwritten")
	eq(local_reason(redis, KEY), "manual")
	eq(#adds, 0, "no create-only write")
	eq(#rcalls, 1)
	assert(not has_arg(rcalls[1].args, "NX"), "plain SET")
	eq(json.decode(rows[KEY].value).nonce, nil, "no id in an ordinary ban")
	eq(rows[KEY].ttl, 120)
	eq(redis[KEY].ttl, 120)
end)

it("opts without if_absent behaves as no opts", function()
	local ok = utils.add_ban(IP, "manual", 120, nil, nil, "global", {}, {})
	eq(ok, true)
	eq(#adds, 0)
	assert(not has_arg(rcalls[1].args, "NX"))
end)

it("no secondary store at all (production HTTP VM): the ban is still added", function()
	utils, banlease = load_utils(false)
	reset()
	eq(guard_ban(), "added")
	eq(local_reason(rows, KEY), "antiddos")
	eq(next(stream_rows), nil)
	utils, banlease = load_utils(true)
end)

-- Local lock uses a separate raw shared-dict key, as it does between nginx workers.
local LOCK = "ban_lock_" .. IP
local function logged(fragment)
	for _, entry in ipairs(logs) do
		if entry.level == ngx.WARN and entry.message:find(fragment, 1, true) then
			return true
		end
	end
	return false
end
local function conflict()
	hooks.before_redis = function(cmd)
		if cmd == "get" then
			redis[KEY] = nil
		end
	end
end

for _, target in ipairs({ "main", "stream" }) do
	it("lock: failed administrative Redis publication between cleanup read and delete preserves " .. target, function()
		conflict()
		local admin, admin_ok, admin_msg, injected
		hooks.after_get = function(name, key)
			if name ~= target or key ~= KEY or not rows[KEY] and target == "main" then
				return
			end
			hooks.after_get = nil
			injected = true
			admin = coroutine.create(function()
				flags.set_fail = true
				admin_ok, admin_msg = utils.add_ban(IP, "manual", 0)
				flags.set_fail = nil
			end)
			hooks.sleep = function()
				coroutine.yield("waiting for cleanup")
			end
			assert(coroutine.resume(admin))
			hooks.unlocked = function()
				hooks.unlocked = nil
				if coroutine.status(admin) ~= "dead" then
					assert(coroutine.resume(admin))
				end
			end
		end
		local status = guard_ban()
		assert(injected, "writer injected after local ownership read")
		eq(status, "exists")
		eq(coroutine.status(admin), "dead", "administrative call finished")
		eq(admin_ok, false, "manual Redis publication failed")
		assert(admin_msg:find("redis SET failed", 1, true), admin_msg)
		eq(redis[KEY], nil, "no Redis copy can restore the manual ban")
		eq(local_reason(rows, KEY), "manual", "primary survives")
		eq(local_reason(stream_rows, KEY), "manual", "secondary survives")
		local banned, reason = utils.is_banned(IP)
		eq(banned, true)
		eq(reason, "manual")
		assert(sleeps > 0, "writer waited for cleanup instead of interleaving its local writes")
	end)
end

it("lock: cleanup waits for a writer and rereads both local records", function()
	conflict()
	hooks.after_redis = function(cmd)
		if cmd == "get" then
			assert(ngx.shared.datastore:safe_add(LOCK, "writer", 1))
		end
	end
	hooks.sleep = function()
		eq(local_reason(rows, KEY), "antiddos", "cleanup has not deleted yet")
		ngx.shared.datastore:delete(LOCK)
		flags.set_fail = true
		eq(utils.add_ban(IP, "manual", 0), false)
		flags.set_fail = nil
		hooks.sleep = nil
	end
	eq(guard_ban(), "exists")
	assert(sleeps > 0, "cleanup waited for writer")
	eq(local_reason(rows, KEY), "manual")
	eq(local_reason(stream_rows, KEY), "manual")
end)

it("lock: dead holder expires and cleanup acquires its own token", function()
	conflict()
	hooks.after_redis = function(cmd)
		if cmd == "get" then
			assert(ngx.shared.datastore:safe_add(LOCK, "dead writer", 0.003))
		end
	end
	local cleanup_token
	hooks.before_delete = function(_, key)
		if key == KEY then
			cleanup_token = ngx.shared.datastore:get(LOCK)
			assert(cleanup_token and cleanup_token ~= "dead writer", "cleanup owns live token")
		end
	end
	eq(guard_ban(), "exists")
	assert(sleeps >= 3 and clock <= 0.05, "expiry recovered within wait bound")
	assert(cleanup_token)
	eq(rows[KEY], nil)
	eq(stream_rows[KEY], nil)
	eq(ngx.shared.datastore:get(LOCK), nil, "released")
end)

local function logged_error(fragment)
	for _, entry in ipairs(logs) do
		if entry.level == ngx.ERR and entry.message:find(fragment, 1, true) then
			return true
		end
	end
	return false
end
local function nothing_written()
	eq(next(rows), nil, "primary untouched")
	eq(next(stream_rows), nil, "secondary untouched")
	eq(next(redis), nil, "Redis untouched")
	eq(#rcalls, 0, "no Redis command")
	eq(#sets + #adds, 0, "no local write")
end
local LOCK_PHASES = { "access", "content", "timer", "preread", "log", "header_filter", "init_worker" }
local function check_wait(test_phase, attempts)
	assert(attempts > 1 and attempts <= 256, "bounded retries")
	if test_phase == "log" or test_phase == "header_filter" or test_phase == "init_worker" then
		eq(sleeps, 0, "phase cannot sleep")
	else
		assert(sleeps > 0 and clock <= 0.051, "bounded sleep")
	end
	eq(ngx.shared.datastore:get(LOCK), "other writer", "failed acquirer never releases holder")
end

for _, test_phase in ipairs(LOCK_PHASES) do
	it("lock [rev 10]: ordinary writer that cannot lock writes nothing and fails in " .. test_phase, function()
		current_phase = test_phase
		assert(ngx.shared.datastore:safe_add(LOCK, "other writer", 1))
		local attempts = 0
		hooks.lock_try = function()
			attempts = attempts + 1
		end
		local ok, msg = utils.add_ban(IP, "manual", 120)
		eq(ok, false)
		eq(msg, "ban lock unavailable")
		nothing_written()
		assert(logged_error("local ban lock"), "failure logged at ERROR")
		check_wait(test_phase, attempts)
	end)

	it("lock [rev 10]: remove_ban that cannot lock deletes nothing and fails in " .. test_phase, function()
		eq(utils.add_ban(IP, "manual", 0), true)
		local service_key = "bans_service_example.com_ip_" .. IP
		put_local(service_key, "manual", true)
		stream_rows[service_key] = rows[service_key]
		put_redis(service_key, "manual", true)
		local before = { main = rows[KEY].value, stream = stream_rows[KEY].value, redis = redis[KEY].value }
		for k in pairs(rcalls) do
			rcalls[k] = nil
		end
		current_phase = test_phase
		assert(ngx.shared.datastore:safe_add(LOCK, "other writer", 1))
		local attempts = 0
		hooks.lock_try = function()
			attempts = attempts + 1
		end
		local ok, msg = utils.remove_ban(IP)
		eq(ok, false)
		eq(msg, "ban lock unavailable")
		eq(rows[KEY].value, before.main, "primary kept")
		eq(stream_rows[KEY].value, before.stream, "secondary kept")
		eq(redis[KEY].value, before.redis, "Redis kept")
		assert(rows[service_key] and stream_rows[service_key] and redis[service_key], "service-scope bans kept")
		eq(#rcalls, 0, "no Redis command")
		assert(logged_error("local ban lock"), "failure logged at ERROR")
		check_wait(test_phase, attempts)
	end)

	it("lock [rev 10]: Redis-hit lookup that cannot lock skips its cache write in " .. test_phase, function()
		put_redis(KEY, "manual", true)
		current_phase = test_phase
		assert(ngx.shared.datastore:safe_add(LOCK, "other writer", 1))
		local attempts = 0
		hooks.lock_try = function()
			attempts = attempts + 1
		end
		local banned, reason = utils.is_banned(IP)
		eq(banned, true, "Redis still answers")
		eq(reason, "manual")
		eq(rows[KEY], nil, "no local cache write")
		eq(stream_rows[KEY], nil, "no secondary cache write")
		eq(#sets + #adds, 0, "no local write")
		assert(logged("cache write"), "skip logged")
		check_wait(test_phase, attempts)
	end)
end

it("lock [rev 10]: insert-only writer that cannot lock writes no local copy and removes its Redis key", function()
	hooks.after_redis = function(cmd)
		if cmd == "set" then
			assert(ngx.shared.datastore:safe_add(LOCK, "other writer", 1))
		end
	end
	local status, msg = guard_ban()
	eq(status, "error")
	assert(msg:find("ban lock unavailable", 1, true), msg)
	eq(next(rows), nil, "primary untouched")
	eq(next(stream_rows), nil, "secondary untouched")
	eq(redis[KEY], nil, "our own Redis key removed")
	eq(#sets + #adds, 0, "no local write")
	assert(logged_error("local ban lock"), "failure logged at ERROR")
	eq(ngx.shared.datastore:get(LOCK), "other writer")
end)

it(
	"lock [rev 10]: cleanup holds the lock after its ownership read, writer exhausts its wait, Redis SET fails",
	function()
		conflict()
		local writer_ok, writer_msg, injected, local_during
		hooks.after_get = function(name, key)
			-- the first read of our own record by the cleanup, under its lock
			if name ~= "main" or key ~= KEY or ngx.shared.datastore:get(LOCK) == nil then
				return
			end
			hooks.after_get = nil
			injected = true
			flags.set_fail = true
			writer_ok, writer_msg = utils.add_ban(IP, "manual", 0)
			flags.set_fail = nil
			local_during = rows[KEY] and json.decode(rows[KEY].value).reason
		end
		local status = guard_ban()
		assert(injected, "writer ran after the cleanup's ownership read")
		assert(sleeps > 0 and clock <= 0.051, "writer exhausted its bounded wait")
		eq(writer_ok, false)
		eq(writer_msg, "ban lock unavailable")
		eq(local_during, "antiddos", "writer wrote nothing next to the cleanup")
		eq(status, "exists")
		-- Nothing was written, so nothing was lost: the cleanup removed only its own record
		eq(rows[KEY], nil)
		eq(stream_rows[KEY], nil)
		eq(redis[KEY], nil)
		local banned, reason = utils.is_banned(IP)
		eq(banned, false)
		eq(reason, "not banned")
		eq(ngx.shared.datastore:get(LOCK), nil, "cleanup released its lock")
	end
)

for _, get_error in ipairs({ false, true }) do
	it("lock: cleanup timeout skips both deletes and logs, GET error=" .. tostring(get_error), function()
		conflict()
		hooks.before_redis = function(cmd)
			if cmd == "get" then
				redis[KEY] = nil
				flags.get_fail = get_error
				assert(ngx.shared.datastore:safe_add(LOCK, "busy writer", 1))
			end
		end
		eq(guard_ban(), "exists", "cleanup failure always answers exists")
		eq(local_reason(rows, KEY), "antiddos", "primary left to expire")
		eq(local_reason(stream_rows, KEY), "antiddos", "secondary left to expire")
		assert(sleeps > 0 and clock <= 0.051, "cleanup bounded wait")
		assert(logged("local ban lock"), "skipped cleanup logged")
		eq(ngx.shared.datastore:get(LOCK), "busy writer")
	end)
end

it("lock: remove waits then guards both local deletions, releasing before Redis", function()
	eq(utils.add_ban(IP, "manual", 120), true)
	assert(ngx.shared.datastore:safe_add(LOCK, "writer", 1))
	hooks.sleep = function()
		hooks.sleep = nil
		ngx.shared.datastore:delete(LOCK)
	end
	hooks.before_delete = function(_, key)
		if key == KEY then
			assert(ngx.shared.datastore:get(LOCK), "local removal holds lock")
		end
	end
	hooks.before_redis = function()
		eq(ngx.shared.datastore:get(LOCK), nil, "Redis outside lock")
	end
	eq(utils.remove_ban(IP), true)
	assert(sleeps > 0)
	eq(rows[KEY], nil)
	eq(stream_rows[KEY], nil)
	eq(redis[KEY], nil)
end)

it("lock: Redis-hit cache waits then writes under lock, Redis remains outside", function()
	put_redis(KEY, "manual", true)
	hooks.after_redis = function(cmd)
		if cmd == "eval" then
			assert(ngx.shared.datastore:safe_add(LOCK, "writer", 1))
		end
	end
	hooks.sleep = function()
		hooks.sleep = nil
		ngx.shared.datastore:delete(LOCK)
	end
	hooks.before_set = function(_, key)
		if key == KEY then
			assert(ngx.shared.datastore:get(LOCK), "cache write holds lock")
		end
	end
	local banned, reason = utils.is_banned(IP)
	eq(banned, true)
	eq(reason, "manual")
	assert(sleeps > 0)
	eq(local_reason(rows, KEY), "manual")
	eq(ngx.shared.datastore:get(LOCK), nil)
end)

it("lock: ordinary and insert-only local writes hold one lock, released before Redis", function()
	hooks.before_set = function(_, key)
		if key == KEY then
			assert(ngx.shared.datastore:get(LOCK), "ordinary local write holds lock")
		end
	end
	hooks.before_add = function(_, key)
		if key == KEY then
			assert(ngx.shared.datastore:get(LOCK), "insert-only local write holds lock")
		end
	end
	hooks.before_redis = function()
		eq(ngx.shared.datastore:get(LOCK), nil, "Redis outside lock")
	end
	eq(utils.add_ban(IP, "manual", 120), true)
	utils.remove_ban(IP)
	eq(guard_ban(), "added")
end)

it("lock: expired holder must not release a successor's token", function()
	hooks.before_set = function(name, key)
		if name == "main" and key == KEY then
			assert(ngx.shared.datastore:get(LOCK), "writer owns a token")
			clock = clock + 2
			assert(ngx.shared.datastore:safe_add(LOCK, "successor", 1))
		end
	end
	eq(utils.add_ban(IP, "manual", 120), true)
	eq(ngx.shared.datastore:get(LOCK), "successor")
end)

os.exit(failures == 0 and 0 or 1)
