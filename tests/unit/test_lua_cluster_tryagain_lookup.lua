-- Plain Lua check of the ban lookup in bunkerweb.utils while a Redis Cluster slot migrates: the lookup script is
-- refused with TRYAGAIN, so the keys are read one by one and the verdict stays the same.
-- Run: lua tests/unit/test_lua_cluster_tryagain_lookup.lua   (from the repo root)
local root = arg[0]:match("^(.*)/tests/unit/") or "."
package.path = root .. "/src/bw/lua/?.lua;" .. package.path

local failures = 0
local test_setup
local function it(name, fn)
	test_setup()
	local ok, err = pcall(fn)
	print((ok and "PASS " or "FAIL ") .. name .. (ok and "" or (": " .. tostring(err))))
	if not ok then
		failures = failures + 1
	end
end

-- Tiny JSON for the tables these tests exchange (scalars, arrays, objects)
local json = {}
local function encode_value(v)
	local t = type(v)
	if t == "table" then
		if #v > 0 then
			local parts = {}
			for _, item in ipairs(v) do
				parts[#parts + 1] = encode_value(item)
			end
			return "[" .. table.concat(parts, ",") .. "]"
		end
		local keys = {}
		for k in pairs(v) do
			keys[#keys + 1] = k
		end
		table.sort(keys)
		local parts = {}
		for _, k in ipairs(keys) do
			parts[#parts + 1] = string.format("%q:%s", k, encode_value(v[k]))
		end
		return "{" .. table.concat(parts, ",") .. "}"
	elseif t == "string" then
		return string.format("%q", v)
	end
	return tostring(v)
end
function json.encode(v)
	return encode_value(v)
end
function json.decode(s)
	local pos = 1
	local value
	local function skip()
		pos = s:find("%S", pos) or #s + 1
	end
	local function parse_string()
		local str, stop = s:match('^"(.-)"()', pos)
		pos = stop
		return str
	end
	function value()
		skip()
		local c = s:sub(pos, pos)
		if c == "{" then
			pos = pos + 1
			local obj = {}
			skip()
			if s:sub(pos, pos) == "}" then
				pos = pos + 1
				return obj
			end
			while true do
				skip()
				local k = parse_string()
				skip()
				pos = pos + 1 -- :
				obj[k] = value()
				skip()
				local d = s:sub(pos, pos)
				pos = pos + 1
				if d == "}" then
					return obj
				end
			end
		elseif c == "[" then
			pos = pos + 1
			local arr = {}
			skip()
			if s:sub(pos, pos) == "]" then
				pos = pos + 1
				return arr
			end
			while true do
				arr[#arr + 1] = value()
				skip()
				local d = s:sub(pos, pos)
				pos = pos + 1
				if d == "]" then
					return arr
				end
			end
		elseif c == '"' then
			return parse_string()
		end
		local lit = s:match("^[%w%.%-]+", pos)
		pos = pos + #lit
		if lit == "true" then
			return true
		elseif lit == "false" then
			return false
		elseif lit == "null" then
			return nil
		end
		return tonumber(lit)
	end
	local ok, res = pcall(value)
	if not ok then
		error("invalid json: " .. tostring(res))
	end
	return res
end

-- Fake shared dicts with TTL tracking
local function new_dict()
	local data, ttls = {}, {}
	local dict = { full = false }
	function dict.get(_, k)
		return data[k]
	end
	function dict.safe_set(_, k, v, ttl)
		if dict.full and data[k] == nil then
			return false, "no memory"
		end
		data[k], ttls[k] = v, ttl
		return true
	end
	function dict.safe_add(_, k, v, ttl)
		if data[k] ~= nil then
			return false, "exists"
		end
		if dict.full then
			return false, "no memory"
		end
		data[k], ttls[k] = v, ttl
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
		data[k], ttls[k] = nil, nil
	end
	dict._data, dict._ttls = data, ttls
	return dict
end

-- ngx before any module is required; ngx.var errors while `var_guard` is on
local var_guard = false
local clock = 1700000000
-- one-shot hooks the datastore/clusterstore stubs fire; tests set them, reset_state() clears them
local bump_after_local_write
local ngx_null = setmetatable({}, {
	__tostring = function()
		return "null"
	end,
})
_G.unpack = rawget(table, "unpack")
_G.ngx = {
	null = ngx_null,
	shared = { bans_meta = new_dict(), datastore = new_dict(), internalstore = {} },
	config = { subsystem = "http" },
	thread = { kill = function() end },
	re = { match = function() end },
	var = setmetatable({}, {
		__index = function()
			if var_guard then
				error("ngx.var in ClientHello")
			end
		end,
	}),
	now = function()
		return clock
	end,
	sleep = function(seconds)
		clock = clock + seconds
	end,
	time = function()
		return 1700000000
	end,
	log = function() end,
	get_phase = function()
		return "access"
	end,
	ERR = 4,
	WARN = 5,
	INFO = 7,
	HTTP_FORBIDDEN = 403,
	HTTP_CLOSE = 444,
}
package.loaded["cjson"] = json
package.loaded["resty.random"] = {
	bytes = function(n)
		return string.rep("\171", n)
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
		return { log = function() end }
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
	new = function(list)
		return {
			match = function(_, ip)
				for _, entry in ipairs(list) do
					if entry == ip then
						return true
					end
				end
				return false
			end,
		}
	end,
}

-- Fake datastore: one table per instance; internalstore is told apart by the dict it is built over
local store, internal = {}, {}
local function make_datastore(rows)
	local obj = {}
	function obj.get(_, key)
		local row = rows[key]
		if row == nil then
			return nil, "not found"
		end
		return row.value
	end
	function obj.set_with_retries(_, key, value, ttl)
		rows[key] = { value = value, ttl = ttl or 0 }
		if bump_after_local_write and key:sub(-#bump_after_local_write) == bump_after_local_write then
			package.loaded["bunkerweb.banlease"].bump_lease_epoch(bump_after_local_write)
		end
		return true, "success"
	end
	function obj.delete(_, key)
		rows[key] = nil
		return true, "success"
	end
	function obj.keys()
		local keys = {}
		for k in pairs(rows) do
			keys[#keys + 1] = k
		end
		return keys
	end
	function obj.ttl(_, key)
		return true, rows[key] and rows[key].ttl or 0
	end
	return obj
end
local main_ds, internal_ds = make_datastore(store), make_datastore(internal)
internal_ds.get = function(_, key)
	if internal[key] == nil then
		return nil, "not found"
	end
	return internal[key].value, "success"
end
package.loaded["bunkerweb.datastore"] = {
	new = function(_, dict)
		return dict == ngx.shared.internalstore and internal_ds or main_ds
	end,
}

-- Fake Redis Cluster client: the lookup script answers per `eval_error` (nil, err) or emulates the script;
-- GET and TTL are the single-key commands the fallback uses, logged in `single_calls`.
local redis, eval_calls, single_calls = {}, 0, {}
local eval_error, get_error, in_cluster, retries_seen
package.loaded["bunkerweb.clusterstore"] = {
	new = function()
		local cs = { cluster_mode = in_cluster }
		function cs.connect()
			return true
		end
		function cs.close() end
		function cs.call(self, cmd, script, nkeys, ...)
			if cmd == "get" or cmd == "ttl" then
				single_calls[#single_calls + 1] = cmd .. " " .. script
				if get_error and cmd == "get" and script == get_error.key then
					return nil, get_error.err
				end
				local row = redis[script]
				if cmd == "get" then
					return row and row.value or ngx_null
				end
				return row and row.ttl or -2
			end
			assert(cmd == "eval")
			eval_calls = eval_calls + 1
			retries_seen = self.tryagain_retries
			if eval_error then
				return nil, eval_error
			end
			local keys = { ... }
			local with_epoch = script:find("KEYS[#KEYS]", 1, true) ~= nil
			local last = with_epoch and nkeys - 1 or nkeys
			local epoch = ngx_null
			if with_epoch and redis[keys[nkeys]] then
				epoch = redis[keys[nkeys]].value
			end
			for i = 1, last do
				local row = redis[keys[i]]
				if row then
					if with_epoch then
						return { row.value, row.ttl, i, epoch }
					end
					return { row.value, row.ttl, i }
				end
			end
			if with_epoch then
				return { ngx_null, -2, 0, epoch }
			end
			return { ngx_null, -2, 0 }
		end
		return cs
	end,
}

-- cachestore: the whitelist cache read must be the non-yielding one
package.loaded["bunkerweb.cachestore"] = {
	new = function()
		return {
			get = function()
				error("yielding cachestore:get in local_only mode")
			end,
			get_local_nolock = function()
				return true, nil
			end,
		}
	end,
}

require("bunkerweb.banlease")
local utils = require("bunkerweb.utils")
local DEFAULT_VARS = { USE_REDIS = "no", MULTISITE = "yes", CROWDSEC_BAN_REFRESH = "5m", BANS_TLS_DROP_REASONS = "" }
local variables

local function set_var(name, value)
	variables.global[name] = value
end

function test_setup()
	for _, t in ipairs({ store, redis }) do
		for k in pairs(t) do
			t[k] = nil
		end
	end
	local dict = ngx.shared.bans_meta
	for k in pairs(dict._data) do
		dict:delete(k)
	end
	dict.full = false
	for k in pairs(ngx.shared.datastore._data) do
		ngx.shared.datastore:delete(k)
	end
	clock = 1700000000
	eval_calls, single_calls, eval_error, get_error, in_cluster, retries_seen = 0, {}, nil, nil, nil, nil
	bump_after_local_write = nil
	var_guard = false
	variables = { global = {} }
	for k, v in pairs(DEFAULT_VARS) do
		variables.global[k] = v
	end
	internal.variables = { value = variables }
end

local function put(key, value, ttl)
	store[key] = { value = value, ttl = ttl or 0 }
end
local function redis_put(key, value, ttl)
	redis[key] = { value = value, ttl = ttl }
end
local function ban_json(reason)
	return json.encode({
		reason = reason,
		service = "www",
		date = 1700000000,
		country = "local",
		ban_scope = "global",
		reason_data = {},
		permanent = false,
	})
end
local function ctx()
	return { bw = { server_name = "www" } }
end

local TRYAGAIN = "TRYAGAIN Multiple keys request during rehashing of slot"

-- Cluster mode: Redis names carry the IP as a hash tag
local function cluster_on()
	in_cluster = true
	set_var("USE_REDIS", "yes")
	set_var("REDIS_CLUSTER_NODES", "redis-1:6379")
end

local function single_count(cmd)
	local n = 0
	for _, call in ipairs(single_calls) do
		if call:sub(1, #cmd) == cmd then
			n = n + 1
		end
	end
	return n
end

for _, leases in ipairs({ "5m", "0" }) do
	local mode = leases == "0" and " (leases off)" or " (leases on)"

	it("a Redis-only ban is enforced while the script gets TRYAGAIN" .. mode, function()
		cluster_on()
		set_var("CROWDSEC_BAN_REFRESH", leases)
		redis_put("bans_ip_{7.7.7.7}", ban_json("api"), 120)
		eval_error = TRYAGAIN
		local banned, reason, ttl = utils.is_banned("7.7.7.7", "www", ctx())
		assert(banned == true and reason == "api" and ttl == 120, tostring(banned) .. " " .. tostring(reason))
		assert(eval_calls == 1 and retries_seen == 0, "one script attempt, no sleeping retry of it")
		assert(single_count("get") >= 1 and single_count("ttl") == 1)
		assert(store["bans_ip_7.7.7.7"].ttl == 30, "the local copy keeps the 30 s cap")
	end)

	it("the service key is read before the global one" .. mode, function()
		cluster_on()
		set_var("CROWDSEC_BAN_REFRESH", leases)
		redis_put("bans_ip_{7.7.7.8}", ban_json("global"), 120)
		redis_put("bans_service_www_ip_{7.7.7.8}", ban_json("service"), 60)
		eval_error = TRYAGAIN
		local banned, reason, ttl = utils.is_banned("7.7.7.8", "www", ctx())
		assert(banned and reason == "service" and ttl == 60)
		assert(store["bans_service_www_ip_7.7.7.8"] and not store["bans_ip_7.7.7.8"])
	end)

	it("an unbanned address stays unbanned while the script gets TRYAGAIN" .. mode, function()
		cluster_on()
		set_var("CROWDSEC_BAN_REFRESH", leases)
		eval_error = TRYAGAIN
		local c = ctx()
		local banned, reason = utils.is_banned("7.7.7.9", "www", c)
		assert(banned == false and reason == "not banned", tostring(banned) .. " " .. tostring(reason))
		if leases ~= "0" then
			assert(c.bw.cs_redis_epoch == false, "the epoch was read too")
		end
	end)
end

it("the epoch read on the fallback path is the one recorded on ctx", function()
	cluster_on()
	redis_put("cs_epoch_{7.7.7.10}", "abc:3", 600)
	eval_error = TRYAGAIN
	local c = ctx()
	assert(utils.is_banned("7.7.7.10", "www", c) == false)
	assert(c.bw.cs_redis_epoch == "abc:3")
end)

it("a key that expires between the GET and the TTL is a miss", function()
	cluster_on()
	redis_put("bans_service_www_ip_{7.7.7.11}", ban_json("service"), -2)
	redis_put("bans_ip_{7.7.7.11}", ban_json("global"), 90)
	eval_error = TRYAGAIN
	local banned, reason, ttl = utils.is_banned("7.7.7.11", "www", ctx())
	assert(banned and reason == "global" and ttl == 90)
end)

it("a permanent Redis ban reports ttl 0 on the fallback path", function()
	cluster_on()
	redis_put("bans_ip_{7.7.7.12}", ban_json("api"), -1)
	eval_error = TRYAGAIN
	local banned, _, ttl = utils.is_banned("7.7.7.12", "www", ctx())
	assert(banned and ttl == 0)
end)

it("another script error keeps the failure path and reads nothing singly", function()
	cluster_on()
	redis_put("bans_ip_{7.7.8.1}", ban_json("api"), 120)
	eval_error = "ERR something else"
	local banned, reason = utils.is_banned("7.7.8.1", "www", ctx())
	assert(banned == nil and reason == "redis call error: ERR something else", tostring(reason))
	assert(#single_calls == 0)
end)

it("TRYAGAIN outside a cluster keeps the failure path", function()
	set_var("USE_REDIS", "yes")
	redis_put("bans_ip_7.7.8.2", ban_json("api"), 120)
	eval_error = TRYAGAIN
	local banned, reason = utils.is_banned("7.7.8.2", "www", ctx())
	assert(banned == nil and reason == "redis call error: " .. TRYAGAIN, tostring(reason))
	assert(#single_calls == 0)
end)

it("a failing single-key read takes the failure path with its error", function()
	cluster_on()
	redis_put("bans_ip_{7.7.8.3}", ban_json("api"), 120)
	eval_error = TRYAGAIN
	get_error = { key = "bans_service_www_ip_{7.7.8.3}", err = "timeout" }
	local banned, reason = utils.is_banned("7.7.8.3", "www", ctx())
	assert(banned == nil and reason == "redis call error: timeout", tostring(reason))
end)

it("a local ban still holds when the single-key read fails too", function()
	cluster_on()
	put("bans_service_www_ip_7.7.8.4", ban_json("local"), 60)
	redis_put("bans_ip_{7.7.8.4}", ban_json("api"), 120)
	eval_error = TRYAGAIN
	get_error = { key = "bans_ip_{7.7.8.4}", err = "timeout" }
	local banned, reason = utils.is_banned("7.7.8.4", "www", ctx())
	assert(banned == true and reason == "local")
end)

os.exit(failures == 0 and 0 or 1)
