-- Plain Lua check of the ban lookup with leases, epochs and resolved markers in bunkerweb.utils.
-- Run: lua tests/unit/test_lua_is_banned_leases.lua   (from the repo root)
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
-- one-shot hooks the datastore/clusterstore stubs fire; tests set them, reset_state() clears them
local bump_after_local_write, bump_during_eval, bump_marker_during_eval
local ngx_null = setmetatable({}, {
	__tostring = function()
		return "null"
	end,
})
_G.unpack = rawget(table, "unpack")
_G.ngx = {
	null = ngx_null,
	shared = { bans_meta = new_dict(), internalstore = {} },
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
		return 1700000000
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

-- Fake Redis and clusterstore, emulating the lookup script
local redis, redis_calls, last_eval_nkeys = {}, 0, nil
package.loaded["bunkerweb.clusterstore"] = {
	new = function()
		local cs = {}
		function cs.connect()
			return true
		end
		function cs.close() end
		function cs.call(_, cmd, script, nkeys, ...)
			assert(cmd == "eval")
			redis_calls = redis_calls + 1
			last_eval_nkeys = nkeys
			local keys = { ... }
			local banlease = package.loaded["bunkerweb.banlease"]
			if bump_during_eval then
				banlease.bump_lease_epoch(bump_during_eval)
				bump_during_eval = nil
			end
			if bump_marker_during_eval then
				banlease.bump_marker_epoch(bump_marker_during_eval)
				bump_marker_during_eval = nil
			end
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

local banlease = require("bunkerweb.banlease")
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
	redis_calls, last_eval_nkeys = 0, nil
	bump_after_local_write, bump_during_eval, bump_marker_during_eval = nil, nil, nil
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
local function local_get(key)
	return store[key] and store[key].value or nil
end
local function le(ip)
	return banlease.lease_epoch(ip, true)
end
local function lease_json(reason, epoch)
	return json.encode({
		reason = reason,
		service = "www",
		ban_scope = "global",
		reason_data = {},
		permanent = false,
		kind = "crowdsec_lease",
		lease_epoch = epoch,
	})
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
local function seq_delta()
	return ngx.shared.bans_meta._data["epoch_seq"] or 0
end
local function count_meta_keys()
	local n = 0
	for _ in pairs(ngx.shared.bans_meta._data) do
		n = n + 1
	end
	return n
end
local function meta_ttl(key)
	return ngx.shared.bans_meta._ttls[key]
end
local function whitelist_service(name, ip)
	variables.global.SERVER_NAME = name
	variables.global.USE_WHITELIST = "yes"
	variables[name] = { USE_WHITELIST = "yes" }
	internal["plugin_whitelist_lists_" .. name] = { value = { IP = { ip } } }
end

it("explicit service beats explicit global beats lease service beats lease global", function()
	put("bans_cs_ip_1.1.1.1", lease_json("crowdsec", le("1.1.1.1")), 60)
	put("bans_cs_service_www_ip_1.1.1.1", lease_json("crowdsec", le("1.1.1.1")), 60)
	assert(select(2, utils.is_banned("1.1.1.1", "www")) == "crowdsec")
	put("bans_ip_1.1.1.1", ban_json("manual"), 60)
	assert(select(2, utils.is_banned("1.1.1.1", "www")) == "manual")
	put("bans_service_www_ip_1.1.1.1", ban_json("ui"), 60)
	assert(select(2, utils.is_banned("1.1.1.1", "www")) == "ui")
end)

it("a lease copy with a stale lease epoch counts as absent", function()
	put("bans_cs_ip_2.2.2.2", lease_json("crowdsec", le("2.2.2.2")), 60)
	assert(utils.is_banned("2.2.2.2", "www") == true, "valid while the epoch matches")
	banlease.bump_lease_epoch("2.2.2.2")
	assert(utils.is_banned("2.2.2.2", "www") == false)
end)

it("a lease without any lease epoch counts as absent", function()
	put("bans_cs_ip_3.3.3.3", lease_json("crowdsec", 123), 60)
	assert(utils.is_banned("3.3.3.3", "www") == false)
	put("bans_cs_ip_3.3.3.4", lease_json("crowdsec", le("3.3.3.4")), 60)
	assert(utils.is_banned("3.3.3.4", "www") == true, "the same lease with an epoch counts")
end)

it("explicit bans with Redis on keep their reason, ttl and permanent flag", function()
	set_var("USE_REDIS", "yes")
	redis_put("bans_ip_4.4.4.4", ban_json("api"), -1)
	local banned, reason, ttl = utils.is_banned("4.4.4.4", "www", ctx())
	assert(banned and reason == "api" and ttl == 0)
end)

it("explicit service ban with Redis on keeps its reason and ttl", function()
	set_var("USE_REDIS", "yes")
	redis_put("bans_service_www_ip_4.4.4.5", ban_json("manual"), 120)
	local banned, reason, ttl = utils.is_banned("4.4.4.5", "www", ctx())
	assert(banned and reason == "manual" and ttl == 120)
	assert(store["bans_service_www_ip_4.4.4.5"].ttl == 30, "local copy keeps the 30 s cap")
end)

it("Redis lookup records the Redis epoch on ctx, false when missing", function()
	set_var("USE_REDIS", "yes")
	local c = ctx()
	utils.is_banned("5.5.5.5", "www", c)
	assert(c.bw.cs_redis_epoch == false)
	redis_put("cs_epoch_5.5.5.5", "abc:3", 600)
	utils.is_banned("5.5.5.5", "www", c)
	assert(c.bw.cs_redis_epoch == "abc:3")
end)

it("a nil-epoch rehydration loses to a concurrent remove_lease (post-write fence)", function()
	set_var("USE_REDIS", "yes")
	redis_put("bans_cs_ip_6.6.6.2", lease_json("crowdsec", 1), 60)
	assert(utils.is_banned("6.6.6.2", "www", ctx()) == true, "without a concurrent removal the lease holds")
	redis_put("bans_cs_ip_6.6.6.5", lease_json("crowdsec", 1), 60)
	-- the datastore stub calls banlease.bump_lease_epoch(ip) right after the copy is set
	bump_after_local_write = "6.6.6.5"
	assert(utils.is_banned("6.6.6.5", "www", ctx()) == false)
	assert(local_get("bans_cs_ip_6.6.6.5") == nil)
	bump_after_local_write = nil
end)

it("a Redis lease hit rehydrates a local copy fenced by a created epoch", function()
	set_var("USE_REDIS", "yes")
	redis_put("bans_cs_ip_6.6.6.3", lease_json("crowdsec", 1), 60)
	local banned, reason = utils.is_banned("6.6.6.3", "www", ctx())
	assert(banned and reason == "crowdsec")
	local copy = json.decode(local_get("bans_cs_ip_6.6.6.3"))
	assert(copy.lease_epoch == banlease.lease_epoch("6.6.6.3", false), "copy embeds the current lease epoch")
	assert(utils.is_banned_local("6.6.6.3", "www") == true, "the copy is valid locally")
	banlease.bump_lease_epoch("6.6.6.3")
	assert(utils.is_banned_local("6.6.6.3", "www") == false, "and stale once the epoch moves")
end)

it("lease keys and the epoch key are not looked up when CROWDSEC_BAN_REFRESH is 0", function()
	set_var("USE_REDIS", "yes")
	set_var("CROWDSEC_BAN_REFRESH", "0")
	local c = ctx()
	utils.is_banned("6.6.6.4", "www", c)
	assert(last_eval_nkeys == 2 and c.bw.cs_redis_epoch == nil, "same Redis work as 1.6.x")
	set_var("CROWDSEC_BAN_REFRESH", "5m")
end)

it("a Redis lease hit after a lease epoch bump during the lookup is discarded", function()
	set_var("USE_REDIS", "yes")
	redis_put("bans_cs_ip_6.6.6.1", lease_json("crowdsec", 1), 60)
	assert(utils.is_banned("6.6.6.1", "www", ctx()) == true, "without a bump the Redis lease holds")
	redis_put("bans_cs_ip_6.6.6.6", lease_json("crowdsec", 1), 60)
	bump_during_eval = "6.6.6.6" -- the clusterstore stub calls banlease.bump_lease_epoch(ip) inside call()
	assert(utils.is_banned("6.6.6.6", "www", ctx()) == false)
	assert(local_get("bans_cs_ip_6.6.6.6") == nil, "no local copy")
end)

it("defaults allocate nothing in bans_meta", function()
	set_var("BANS_TLS_DROP_REASONS", "")
	local before = count_meta_keys()
	utils.is_banned("7.7.7.6", "www", ctx())
	assert(count_meta_keys() == before)
end)

it("a marker never outlives the local copy that produced it", function()
	set_var("USE_REDIS", "yes")
	set_var("BANS_TLS_DROP_REASONS", "manual")
	put("bans_ip_7.7.7.5", ban_json("manual"), 4) -- local copy with 4 s left
	utils.is_banned("7.7.7.5", "www", ctx())
	assert(meta_ttl("rs_www_7.7.7.5") and meta_ttl("rs_www_7.7.7.5") <= 4)
end)

it("access-phase hit with Redis on publishes a resolved marker with rank", function()
	set_var("USE_REDIS", "yes")
	set_var("BANS_TLS_DROP_REASONS", "crowdsec")
	redis_put("bans_cs_ip_7.7.7.7", lease_json("crowdsec", 1), 60)
	utils.is_banned("7.7.7.7", "www", ctx())
	local m = banlease.read_marker("www", "7.7.7.7")
	assert(m and m.id == "crowdsec" and m.rank == 4 and m.epoch == banlease.marker_epoch("7.7.7.7"))
	assert(banlease.read_marker("", "7.7.7.7"), "global-rank hits also publish the default-server marker")
end)

it("free-form reasons publish no marker", function()
	set_var("USE_REDIS", "yes")
	set_var("BANS_TLS_DROP_REASONS", "manual")
	redis_put("bans_ip_7.7.7.3", ban_json("manual"), 60)
	utils.is_banned("7.7.7.3", "www", ctx())
	assert(banlease.read_marker("www", "7.7.7.3"), "canonical reasons publish")
	redis_put("bans_ip_7.7.7.4", ban_json("custom plugin reason"), 60)
	utils.is_banned("7.7.7.4", "www", ctx())
	assert(banlease.read_marker("www", "7.7.7.4") == nil)
end)

it("no marker is published when the marker epoch moved during the lookup", function()
	set_var("USE_REDIS", "yes")
	set_var("BANS_TLS_DROP_REASONS", "manual")
	redis_put("bans_ip_8.8.8.7", ban_json("manual"), 60)
	utils.is_banned("8.8.8.7", "www", ctx())
	assert(banlease.read_marker("www", "8.8.8.7"), "published when nothing moved")
	redis_put("bans_ip_8.8.8.8", ban_json("manual"), 60)
	bump_marker_during_eval = "8.8.8.8"
	utils.is_banned("8.8.8.8", "www", ctx())
	assert(banlease.read_marker("www", "8.8.8.8") == nil)
end)

it("add_ban with no marker epoch allocates nothing", function()
	set_var("USE_REDIS", "no")
	local before = count_meta_keys()
	utils.add_ban("9.9.9.8", "manual", 60)
	assert(count_meta_keys() == before)
end)

it("add_ban and remove_ban move the marker epoch twice", function()
	set_var("USE_REDIS", "no")
	local e0 = banlease.marker_epoch("9.9.9.9", true)
	local s0 = seq_delta()
	utils.add_ban("9.9.9.9", "manual", 60)
	local e1 = banlease.marker_epoch("9.9.9.9")
	assert(e1 ~= e0 and seq_delta() - s0 >= 2)
	utils.remove_ban("9.9.9.9")
	assert(banlease.marker_epoch("9.9.9.9") ~= e1)
end)

it("is_banned_local keeps precedence and never touches Redis", function()
	set_var("USE_REDIS", "yes")
	put("bans_cs_service_www_ip_10.0.0.1", lease_json("crowdsec", le("10.0.0.1")), 60)
	put("bans_ip_10.0.0.1", ban_json("bad behavior"), 60)
	local banned, reason, rank = utils.is_banned_local("10.0.0.1", "www")
	assert(banned and reason == "bad behavior" and rank == 2)
	assert(redis_calls == 0)
end)

it("is_banned_local without a service only looks at the global keys", function()
	put("bans_service_www_ip_10.0.0.2", ban_json("ui"), 60)
	assert(utils.is_banned_local("10.0.0.2", nil) == false)
	put("bans_cs_ip_10.0.0.2", lease_json("crowdsec", le("10.0.0.2")), 60)
	local banned, reason, rank = utils.is_banned_local("10.0.0.2", nil)
	assert(banned and reason == "crowdsec" and rank == 4)
end)

it("is_ip_whitelisted local_only with a nil service still finds a per-service whitelist", function()
	whitelist_service("www", "12.0.0.1")
	assert(utils.is_ip_whitelisted("12.0.0.1", nil, { local_only = true }) == true)
end)

it("is_ip_whitelisted local_only with a nil service never reads ngx.var", function()
	whitelist_service("www", "12.0.0.1")
	var_guard = true
	local ok = utils.is_ip_whitelisted("11.0.0.1", nil, { local_only = true })
	var_guard = false
	assert(ok == false)
end)

it("is_ip_whitelisted local_only returns the error instead of falling through", function()
	whitelist_service("www", "12.0.0.1")
	internal["plugin_whitelist_lists_www"] = nil
	local ok, info = utils.is_ip_whitelisted("12.0.0.1", "www", { local_only = true })
	assert(ok == nil and info:find("can't get whitelist lists", 1, true))
end)

os.exit(failures == 0 and 0 or 1)
