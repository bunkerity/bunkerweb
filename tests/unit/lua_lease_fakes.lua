-- Shared fakes for the lease write and instance API tests: ngx, a tiny JSON, shared dicts, the HTTP datastore,
-- utils (settings), and a clusterstore that emulates the lease scripts against a table.
-- Usage: local F = dofile(root .. "/tests/unit/lua_lease_fakes.lua")(root); then require the module under test.
return function(root)
	package.path = root .. "/src/bw/lua/?.lua;" .. package.path
	local F = { vars = {}, store = {}, stream_store = {}, redis = {}, flags = {}, hooks = {}, calls = {} }

	-- Tiny JSON for the tables these tests exchange (scalars, arrays, objects; no escapes inside strings)
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
		if type(s) ~= "string" then
			error("not a string")
		end
		local pos = 1
		local value
		local function skip()
			pos = s:find("%S", pos) or #s + 1
		end
		local function parse_string()
			local str, stop = s:match('^"(.-)"()', pos)
			if not str then
				error("bad string at " .. pos)
			end
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
					pos = pos + 1
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
			if not lit then
				error("invalid json at " .. pos)
			end
			pos = pos + #lit
			if lit == "true" then
				return true
			elseif lit == "false" then
				return false
			elseif lit == "null" then
				return nil
			end
			return tonumber(lit) or error("invalid literal " .. lit)
		end
		return value()
	end
	F.json = json

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

	local null = setmetatable({}, {
		__tostring = function()
			return "null"
		end,
	})
	F.null = null
	_G.unpack = rawget(table, "unpack")
	_G.ngx = {
		null = null,
		shared = { bans_meta = new_dict(), datastore = {}, datastore_stream = {}, internalstore = {} },
		config = { subsystem = "http" },
		now = function()
			return 1700000000
		end,
		time = function()
			return 1700000000
		end,
		log = function() end,
		ERR = 4,
		WARN = 5,
		NOTICE = 6,
		INFO = 7,
		HTTP_OK = 200,
		HTTP_BAD_REQUEST = 400,
		HTTP_NOT_FOUND = 404,
		HTTP_INTERNAL_SERVER_ERROR = 500,
		HTTP_BAD_GATEWAY = 502,
		HTTP_SERVICE_UNAVAILABLE = 503,
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

	-- Settings: F.vars holds global values only
	package.loaded["bunkerweb.utils"] = {
		get_variable = function(name)
			local value = F.vars[name]
			if value == nil then
				return nil, "not found"
			end
			return value
		end,
		is_ipv4 = function(ip)
			return type(ip) == "string" and ip:match("^%d+%.%d+%.%d+%.%d+$") ~= nil
		end,
		is_ipv6 = function(ip)
			return type(ip) == "string" and ip:find(":", 1, true) ~= nil
		end,
		get_country = function()
			return "ZZ"
		end,
		is_ip_in_networks = function()
			return true
		end,
	}

	-- HTTP datastore (the stream one is only there to prove nothing touches it)
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
			if F.flags.datastore_full then
				return false, "no memory"
			end
			rows[key] = { value = value, ttl = ttl or 0 }
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
			-- Keys that expired between the listing and the read
			for _, k in ipairs(F.flags.ghost_keys or {}) do
				keys[#keys + 1] = k
			end
			table.sort(keys)
			return keys
		end
		function obj.ttl(_, key)
			if rows[key] == nil then
				return false, "not found"
			end
			return true, rows[key].ttl
		end
		return obj
	end
	local main_ds, stream_ds = make_datastore(F.store), make_datastore(F.stream_store)
	package.loaded["bunkerweb.datastore"] = {
		new = function(_, dict)
			if dict ~= nil and dict == ngx.shared.datastore_stream then
				return stream_ds
			end
			return main_ds
		end,
	}

	-- Redis: F.redis[key] = { value, ttl }. Emulates the promote and bump scripts, GET and TTL.
	local function redis_set(key, value, ttl)
		F.redis[key] = { value = value, ttl = ttl }
	end
	function F.redis_get(key)
		return F.redis[key] and F.redis[key].value or nil
	end
	local function run_promote(keys, argv)
		local cur = F.redis_get(keys[1])
		if cur == nil then
			if argv[1] ~= "" then
				return "stale"
			end
			redis_set(keys[1], argv[2] .. ":1", 604800)
			redis_set(keys[2], argv[3], tonumber(argv[4]))
			return "ok"
		end
		if cur ~= argv[1] then
			return "stale"
		end
		redis_set(keys[2], argv[3], tonumber(argv[4]))
		return "ok"
	end
	local function run_bump(keys, argv)
		local cur = F.redis_get(keys[1])
		local inc, n
		if cur then
			inc, n = cur:match("^(.+):(%d+)$")
		end
		if inc then
			redis_set(keys[1], inc .. ":" .. (tonumber(n) + 1), 604800)
		else
			redis_set(keys[1], argv[1] .. ":1", 604800)
		end
		if keys[2] then
			F.redis[keys[2]] = nil
		end
		return 1
	end
	package.loaded["bunkerweb.clusterstore"] = {
		new = function()
			local cs = { config_error = F.flags.config_error }
			function cs.connect(self)
				if self.config_error then
					return false, "invalid redis configuration : " .. self.config_error
				end
				if F.flags.redis_down then
					return false, "connection refused"
				end
				return true
			end
			function cs.close() end
			function cs.call(_, cmd, ...)
				F.calls[#F.calls + 1] = cmd
				if F.hooks.on_call then
					F.hooks.on_call(cmd)
				end
				if F.flags.redis_call_fails then
					return nil, "timeout"
				end
				if F.flags.redis_error_reply then
					return false, "ERR boom"
				end
				if cmd == "eval" then
					local script, nkeys = ...
					local rest = { select(3, ...) }
					local keys, argv = {}, {}
					for i = 1, nkeys do
						keys[i] = rest[i]
					end
					for i = nkeys + 1, #rest do
						argv[#argv + 1] = tostring(rest[i])
					end
					if script:find('"stale"', 1, true) then
						return run_promote(keys, argv)
					end
					return run_bump(keys, argv)
				elseif cmd == "get" then
					local key = ...
					return F.redis[key] and F.redis[key].value or null
				elseif cmd == "ttl" then
					local key = ...
					if not F.redis[key] then
						return -2
					end
					return F.redis[key].ttl or -1
				end
				error("unexpected redis command " .. tostring(cmd))
			end
			return cs
		end,
	}

	-- Reset everything between tests
	function F.reset()
		for _, t in ipairs({ F.store, F.stream_store, F.redis, F.flags, F.hooks, F.calls, F.vars }) do
			for k in pairs(t) do
				t[k] = nil
			end
		end
		local dict = ngx.shared.bans_meta
		for k in pairs(dict._data) do
			dict:delete(k)
		end
		dict.full = false
		F.vars.USE_REDIS = "no"
		F.vars.CROWDSEC_BAN_REFRESH = "5m"
	end
	return F
end
