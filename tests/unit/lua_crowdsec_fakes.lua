-- luacheck: ignore 122 143
-- Fakes for the CrowdSec plugin tests: clock, shared dicts, a JSON that keeps array_mt and cjson.null, the module
-- stubs the vendored bouncer needs, a Local API fake, and loaders for the real plugin, bouncer and control modules.
-- Needs the globals lua_lease_fakes.lua installs (ngx, the bunkerweb.utils stub), so load that first.
-- Usage: local H = dofile(root .. "/tests/unit/lua_crowdsec_fakes.lua")(root)
return function(root)
	package.path = root .. "/src/common/core/?.lua;" .. package.path
	local H = { sleeps = {}, requests = {}, hooks = {}, lock_busy = 0, conf = {} }

	-- Clock: sleeping moves it forward
	H.clock = 1700000000
	ngx.now = function()
		return H.clock
	end
	ngx.time = function()
		return math.floor(H.clock)
	end
	ngx.sleep = function(seconds)
		H.sleeps[#H.sleeps + 1] = seconds
		H.clock = H.clock + seconds
	end
	ngx.var = { hostname = "node-a", uri = "/" }
	ngx.timer = {
		at = function()
			return true
		end,
	}
	ngx.worker = {
		id = function()
			return 0
		end,
	}
	ngx.ALERT, ngx.DEBUG = 2, 8
	ngx.HTTP_FORBIDDEN = 403
	ngx.encode_args = function(args)
		local keys = {}
		for k in pairs(args) do
			keys[#keys + 1] = k
		end
		table.sort(keys)
		local parts = {}
		for _, k in ipairs(keys) do
			parts[#parts + 1] = k .. "=" .. tostring(args[k])
		end
		return table.concat(parts, "&")
	end

	-- JSON with cjson.null and array_mt, as the vendored modules expect
	local cjson = { null = setmetatable({}, {
		__tostring = function()
			return "null"
		end,
	}), array_mt = {} }
	local function decode(s)
		local pos = 1
		local value
		local function skip()
			pos = s:find("%S", pos) or #s + 1
		end
		local function parse_string()
			pos = pos + 1
			local out = {}
			while true do
				local c = s:sub(pos, pos)
				if c == "" then
					error("unterminated string")
				elseif c == '"' then
					pos = pos + 1
					return table.concat(out)
				elseif c == "\\" then
					local n = s:sub(pos + 1, pos + 1)
					local map = { n = "\n", t = "\t", r = "\r", ['"'] = '"', ["\\"] = "\\", ["/"] = "/" }
					out[#out + 1] = map[n] or n
					pos = pos + 2
				else
					out[#out + 1] = c
					pos = pos + 1
				end
			end
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
				local arr = setmetatable({}, cjson.array_mt)
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
			local lit = s:match("^[%w%.%-%+]+", pos)
			if not lit then
				error("invalid json at " .. pos)
			end
			pos = pos + #lit
			if lit == "true" then
				return true
			elseif lit == "false" then
				return false
			elseif lit == "null" then
				return cjson.null
			end
			return tonumber(lit) or error("invalid literal " .. lit)
		end
		return value()
	end
	local function encode(v)
		local t = type(v)
		if v == cjson.null or v == nil then
			return "null"
		elseif t == "table" then
			if getmetatable(v) == cjson.array_mt or #v > 0 then
				local parts = {}
				for _, item in ipairs(v) do
					parts[#parts + 1] = encode(item)
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
				parts[#parts + 1] = encode(tostring(k)) .. ":" .. encode(v[k])
			end
			return "{" .. table.concat(parts, ",") .. "}"
		elseif t == "string" then
			return '"' .. v:gsub('[%c"\\]', function(c)
				return string.format("\\u%04x", c:byte())
			end) .. '"'
		elseif t == "number" and math.type(v) == "integer" then
			return string.format("%d", v)
		end
		return tostring(v)
	end
	cjson.decode, cjson.encode = decode, encode
	function cjson.new()
		return {
			decode = decode,
			encode = encode,
			null = cjson.null,
			array_mt = cjson.array_mt,
			decode_array_with_array_mt = function() end,
		}
	end
	H.cjson = cjson

	-- Shared dict that records TTLs
	function H.new_dict()
		local d = { data = {}, ttls = {}, full = false }
		function d.get(self, k)
			return self.data[k]
		end
		function d.set(self, k, v, ttl)
			if self.full then
				return false, "no memory"
			end
			self.data[k], self.ttls[k] = v, ttl
			return true
		end
		d.safe_set = d.set
		function d.delete(self, k)
			self.data[k], self.ttls[k] = nil, nil
		end
		function d.incr(self, k, v, init)
			if self.data[k] == nil then
				if init == nil then
					return nil, "not found"
				end
				self.data[k] = init
			end
			self.data[k] = self.data[k] + v
			return self.data[k]
		end
		return d
	end

	-- Vendored bouncer dependencies
	local function mask_for(cidr)
		return (0xFFFFFFFF << (32 - cidr)) & 0xFFFFFFFF
	end
	local masks = {}
	for cidr = 32, 0, -1 do
		masks[#masks + 1] = mask_for(cidr)
	end
	package.loaded["crowdsec.lib.iputils"] = {
		netmasks_by_key_type = { ipv4 = masks },
		splitRange = function(range)
			local ip, cidr = range:match("^([^/]+)/(%d+)")
			return ip, tonumber(cidr)
		end,
		parseIPAddress = function(ip)
			local a, b, c, d = tostring(ip):match("^(%d+)%.(%d+)%.(%d+)%.(%d+)$")
			if not a then
				return nil, false
			end
			return ((tonumber(a) * 256 + tonumber(b)) * 256 + tonumber(c)) * 256 + tonumber(d), true
		end,
		cidrToInt = function(cidr)
			return tostring(mask_for(cidr))
		end,
		ipv4_band = function(ip, mask)
			return math.tointeger(tonumber(ip)) & math.tointeger(tonumber(mask))
		end,
	}
	package.loaded["crowdsec.lib.stream_lock"] = {
		run = function(_, callback)
			if H.lock_busy > 0 then
				H.lock_busy = H.lock_busy - 1
				return nil, "busy"
			end
			H.lock_runs = (H.lock_runs or 0) + 1
			if not pcall(callback) then
				return nil, "Stream synchronization failed"
			end
			return true
		end,
	}
	package.loaded["crowdsec.lib.config"] = {
		loadConfig = function()
			local conf = {}
			for k, v in pairs(H.conf) do
				conf[k] = v
			end
			conf.EXCLUDE_LOCATION = {}
			for _, v in ipairs(H.conf.EXCLUDE_LOCATION or {}) do
				conf.EXCLUDE_LOCATION[#conf.EXCLUDE_LOCATION + 1] = v
			end
			return conf
		end,
	}
	package.loaded["crowdsec.lib.captcha"] = {
		New = function()
			return nil, "not configured"
		end,
	}
	package.loaded["crowdsec.lib.flag"] =
		{ BOUNCER_SOURCE = 1, APPSEC_SOURCE = 2, VERIFY_STATE = 4, VALIDATED_STATE = 8, Flags = {} }
	package.loaded["crowdsec.lib.utils"] = {
		table_len = function(t)
			local n = 0
			for _ in pairs(t) do
				n = n + 1
			end
			return n
		end,
	}
	package.loaded["crowdsec.lib.ban"] = {}
	package.loaded["crowdsec.lib.url"] = {
		parse = function()
			return {}
		end,
	}
	package.loaded["bit32"] = {
		bor = function(a, b)
			return a | b
		end,
	}
	package.loaded["crowdsec.cache_partition"] = {
		hash = function(str)
			local sum = 7
			for i = 1, #str do
				sum = (sum * 31 + str:byte(i)) % 2 ^ 32
			end
			return string.format("%064x", math.floor(sum))
		end,
		api_url = function()
			return "http://lapi:8080"
		end,
		prefixes = function(urls)
			local out = {}
			for _, u in ipairs(urls) do
				out[u] = ""
			end
			return out, 1
		end,
		challenge_prefix = function(scope)
			return "ch_" .. scope
		end,
	}

	-- HTTP client fake serving both the bouncer (request_uri) and control.lua (parse_uri/connect/request)
	H.lapi = function()
		return 200, "null"
	end
	H.control_http = function()
		return 404, "null"
	end
	package.loaded["resty.http"] = {
		new = function()
			local client = {}
			function client.set_timeout() end
			function client.set_timeouts() end
			function client.close() end
			function client.request_uri(_, link, opts)
				H.requests[#H.requests + 1] = link
				if H.hooks.before_response then
					H.hooks.before_response(link)
				end
				local status, body = H.lapi(link, opts)
				if status == nil then
					return nil, "connection refused"
				end
				return { status = status, body = body }
			end
			function client.parse_uri(_, uri)
				local scheme, host, port, path, query = uri:match("^(https?)://([^:/]+):?(%d*)(/[^?]*)%??(.*)$")
				return { scheme, host, tonumber(port), path, query }
			end
			function client.connect()
				return true
			end
			function client.request(_, options)
				H.requests[#H.requests + 1] = options.method .. " " .. options.path .. "?" .. (options.query or "")
				local status, body = H.control_http(options.method, options.path, options.query or "", options.body)
				local sent = false
				return {
					status = status,
					headers = {},
					body_reader = function()
						if sent then
							return nil
						end
						sent = true
						return body
					end,
				}
			end
			return client
		end,
	}

	-- Settings and helpers of bunkerweb.utils used by the plugin
	H.settings = { multisite = "no", services = { "global" } }
	local U = package.loaded["bunkerweb.utils"]
	U.has_variable = function()
		return true
	end
	U.get_multiple_variables = function()
		local out = {}
		for _, name in ipairs(H.settings.services) do
			out[name] = { USE_CROWDSEC = "yes" }
		end
		return out
	end
	U.get_deny_status = function()
		return 403
	end
	U.get_security_mode = function(ctx)
		return ctx.security_mode or "block"
	end
	U.parse_duration = function(value)
		if value == nil or value == "" then
			return nil
		end
		local number, suffix = tostring(value):match("^(%d+)(%a*)$")
		local factor = ({ [""] = 1, s = 1, m = 60, h = 3600, d = 86400 })[suffix]
		return tonumber(number) * factor
	end
	local get_variable = U.get_variable
	U.get_variable = function(name, ...)
		if name == "MULTISITE" then
			return H.settings.multisite
		end
		return get_variable(name, ...)
	end

	-- Loaders
	function H.load_bouncer(conf)
		H.conf = conf
		H.requests, H.sleeps, H.lock_busy, H.hooks = {}, {}, 0, {}
		ngx.shared.crowdsec_cache = H.new_dict()
		ngx.shared.crowdsec_metadata = H.new_dict()
		package.preload["crowdsec.lib.bouncer"] = nil
		package.loaded["crowdsec.lib.bouncer"] = nil
		package.loaded["crowdsec.lib.decision_cache"] = nil
		-- The bouncer always gets the real lease module, whatever stub the plugin test installed
		package.loaded["bunkerweb.banlease"] = H.banlease
		local saved = package.loaded["cjson"]
		package.loaded["cjson"] = cjson
		local bouncer = require("crowdsec.lib.bouncer")
		package.loaded["cjson"] = saved
		assert(bouncer.init("conf", "agent", nil))
		return bouncer
	end

	function H.load_control()
		package.loaded["crowdsec.control"] = nil
		package.loaded["cjson.safe"] = cjson
		return require("crowdsec.control")
	end

	-- Plugin machinery: middleclass, bunkerweb.plugin and the rendered configuration file
	package.loaded["middleclass"] = function(_, parent)
		local class = {}
		class.__index = class
		for k, v in pairs(parent or {}) do
			class[k] = v
		end
		class.new = function(self, ctx)
			local object = setmetatable({}, self)
			object:initialize(ctx)
			return object
		end
		return class
	end
	package.loaded["bunkerweb.plugin"] = {
		initialize = function(self, _, ctx)
			self.ctx = ctx
			self.variables = ctx.vars or {}
			self.is_loading = false
			self.is_request = true
			self.logger = {
				log = function(_, level, msg)
					H.logs[#H.logs + 1] = { level, msg }
				end,
			}
		end,
		ret = function(_, ok, msg, status, redirect, data)
			return { ret = ok, msg = msg, status = status, redirect = redirect, data = data }
		end,
	}
	H.logs = {}
	local real_open = io.open
	io.open = function(path, mode)
		if type(path) == "string" and path:find("^/var/cache/bunkerweb/crowdsec/") then
			local contents = H.conf_content
			if contents == nil then
				return nil
			end
			return {
				read = function()
					return contents
				end,
				close = function() end,
			}
		end
		return real_open(path, mode)
	end
	H.conf_content = "API_URL=http://lapi:8080\n"

	-- opts.banlease: module to hand the plugin; opts.bouncer: module new_bouncer() returns
	function H.load_plugin(opts)
		package.loaded["bunkerweb.banlease"] = opts.banlease
		package.preload["crowdsec.lib.bouncer"] = function()
			return opts.bouncer
		end
		package.loaded["crowdsec.lib.bouncer"] = nil
		package.loaded["crowdsec.crowdsec"] = nil
		package.loaded["cjson.safe"] = cjson
		local plugin = require("crowdsec.crowdsec")
		return plugin
	end

	function H.new_ctx(extra)
		local ctx = {
			bw = { server_name = "a.example.com", remote_addr = "1.2.3.4", uri = "/", request_method = "GET" },
			vars = { USE_CROWDSEC = "yes", CROWDSEC_BAN_REFRESH = "5m" },
		}
		for k, v in pairs(extra or {}) do
			ctx[k] = v
		end
		return ctx
	end

	return H
end
