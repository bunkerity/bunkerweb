-- Plain Lua check of the per-service ClientHello hook for plugins (CORE-1): registration in init_worker, the call
-- inside banlease.tls_drop_hook (drop, detect, fail open, nothing yields), and the two ssl_client_hello_by_lua_block
-- templates run as real fragments (a hook plugin is called once per handshake, a plugin without the hook still runs
-- in the legacy default-server loop).
-- Run: lua tests/unit/test_lua_client_hello_plugins.lua   (from the repo root)
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

local function new_dict()
	local data = {}
	local dict = { _data = data, last_ttl = {} }
	function dict.get(_, k)
		return data[k]
	end
	function dict.safe_set(_, k, v, ttl)
		data[k] = v
		dict.last_ttl[k] = ttl
		return true
	end
	function dict.safe_add(_, k, v, ttl)
		if data[k] ~= nil then
			return false, "exists"
		end
		data[k] = v
		dict.last_ttl[k] = ttl
		return true
	end
	function dict.incr(_, k, v, init)
		if data[k] == nil then
			if init == nil then
				return nil, "not found"
			end
			data[k] = init
		end
		data[k] = data[k] + v
		return data[k]
	end
	function dict.delete(_, k)
		data[k] = nil
	end
	return dict
end

local raw, fam, quic, ext_error, exited, logs, pp_addr, raw_calls
local worker_id = 0
local var_touched
_G.ngx = {
	shared = { bans_meta = new_dict(), metrics_datastore = new_dict(), internalstore = {} },
	worker = {
		id = function()
			return worker_id
		end,
	},
	-- a plugin hook must never reach for the request variables: the ClientHello has no request
	var = setmetatable({}, {
		__index = function()
			var_touched = true
			error("ngx.var is not available at the ClientHello")
		end,
	}),
	log = function(level, ...)
		logs[#logs + 1] = { level = level, msg = table.concat({ ... }) }
	end,
	exit = function(code)
		exited[#exited + 1] = code
	end,
	ERROR = -1,
	ERR = 4,
	WARN = 5,
	INFO = 7,
	HTTP_CLOSE = 444,
}
package.loaded["cjson"] = { encode = function() end, decode = function() end }
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
package.loaded["ngx.ssl"] = {
	raw_client_addr = function()
		raw_calls = raw_calls + 1
		return raw, fam
	end,
	proxy_protocol_addr = function()
		return pp_addr
	end,
}
package.loaded["resty.ipmatcher"] = {
	parse_ipv4 = function()
		return false
	end,
	parse_ipv6 = function()
		return false
	end,
	new = function(networks)
		return {
			match = function(_, addr)
				for _, network in ipairs(networks) do
					local prefix = network:match("^(%d+%.%d+%.%d+%.)0/24$")
					if addr == network or (prefix and addr:sub(1, #prefix) == prefix) then
						return true
					end
				end
				return false
			end,
		}
	end,
}
package.loaded["ngx.ssl.clienthello"] = {
	get_client_hello_ext = function()
		if ext_error then
			return nil, "boom"
		end
		return quic and "\0" or nil
	end,
}

local vars
local utils_stub = {
	get_variable = function(name)
		if vars[name] == nil then
			return nil, "not found"
		end
		return vars[name], "success"
	end,
	is_banned_local = function()
		return false, "not banned", nil
	end,
	is_ip_whitelisted = function()
		return false, "ip"
	end,
}
package.loaded["bunkerweb.utils"] = utils_stub
-- Redis and any cosocket are out of reach in the ClientHello: touching them fails the handshake path loudly
package.loaded["bunkerweb.clusterstore"] = setmetatable({}, {
	__index = function()
		error("the ClientHello must not reach Redis")
	end,
})

local banlease = require("bunkerweb.banlease")

-- A plugin module as the core finds it: package.preload plays the plugin directory
local calls, modules
local function plugin(id, fn)
	modules[id] = fn
	package.preload[id .. "/" .. id] = function()
		return { client_hello = fn, name = id }
	end
	package.loaded[id .. "/" .. id] = nil
end

reset = function()
	for _, dict in pairs({ ngx.shared.bans_meta, ngx.shared.metrics_datastore }) do
		for k in pairs(dict._data) do
			dict._data[k] = nil
		end
		dict.last_ttl = {}
	end
	for id in pairs(modules or {}) do
		package.preload[id .. "/" .. id] = nil
		package.loaded[id .. "/" .. id] = nil
	end
	modules, calls = {}, {}
	vars = { BANS_TLS_DROP_REASONS = "", USE_REDIS = "no", SECURITY_MODE = "block" }
	raw, fam, quic, ext_error, exited, logs, pp_addr = "\1\2\3\4", "inet", false, false, {}, {}, nil
	raw_calls, var_touched, worker_id = 0, false, 0
	if banlease.register_client_hello_plugins then
		banlease.register_client_hello_plugins({})
	end
end

-- A plugin that records its calls and returns the given verdict
local function recorder(id, verdict, reason)
	plugin(id, function(hello)
		calls[#calls + 1] = { id = id, hello = hello }
		return verdict, reason
	end)
end

local service = "svc.example.com"

it("capability flag is exported", function()
	eq(banlease.CLIENT_HELLO_PLUGIN_HOOK, 1)
end)

it("registration keeps the plugins that export a client_hello function, in order", function()
	recorder("alpha")
	recorder("beta")
	package.preload["gamma/gamma"] = function()
		return { name = "gamma" } -- a plugin without the hook
	end
	package.preload["delta/delta"] = function()
		return { client_hello = "not a function" }
	end
	package.preload["broken/broken"] = function()
		error("syntax error in plugin")
	end
	local ids = banlease.register_client_hello_plugins({ "beta", "gamma", "delta", "broken", "missing", "alpha" })
	eq(table.concat(ids, ","), "beta,alpha")
	assert(banlease.is_client_hello_plugin("alpha") and banlease.is_client_hello_plugin("beta"))
	assert(not banlease.is_client_hello_plugin("gamma") and not banlease.is_client_hello_plugin("broken"))
	assert(not banlease.is_client_hello_plugin("missing"))
	for _, id in ipairs({ "gamma", "delta", "broken" }) do
		package.preload[id .. "/" .. id] = nil
		package.loaded[id .. "/" .. id] = nil
	end
end)

it("registering again replaces the list (a new worker, a reload)", function()
	recorder("alpha")
	recorder("beta")
	banlease.register_client_hello_plugins({ "alpha" })
	banlease.register_client_hello_plugins({ "beta" })
	assert(not banlease.is_client_hello_plugin("alpha") and banlease.is_client_hello_plugin("beta"))
end)

it("plugins run in the registered order; a nil verdict lets the next one run", function()
	recorder("alpha")
	recorder("beta")
	recorder("gamma")
	banlease.register_client_hello_plugins({ "gamma", "alpha", "beta" })
	assert(banlease.tls_drop_hook(service, false, false, nil) == nil)
	eq(#calls, 3)
	eq(calls[1].id .. calls[2].id .. calls[3].id, "gammaalphabeta")
	eq(#exited, 0)
end)

it("the hello table carries the service, the canonical address, the packed bytes, the family and the flags", function()
	recorder("alpha")
	banlease.register_client_hello_plugins({ "alpha" })
	banlease.tls_drop_hook(service, false, false, nil)
	local h = calls[1].hello
	eq(h.service, service)
	eq(h.ip, "1.2.3.4")
	eq(h.raw, "\1\2\3\4")
	eq(h.family, "inet")
	eq(h.quic, false)
	eq(h.proxy_protocol, false)
	eq(h.real_ip, false)
	eq(h.trusted, nil)
end)

it("an IPv6 peer is the RFC 5952 text, an IPv4-mapped one stays IPv6 text like $remote_addr", function()
	recorder("alpha")
	banlease.register_client_hello_plugins({ "alpha" })
	raw, fam = "\32\1\13\184\0\0\0\0\0\0\0\0\0\0\0\1", "inet6"
	banlease.tls_drop_hook(service, false, false, nil)
	eq(calls[1].hello.ip, "2001:db8::1")
	eq(calls[1].hello.family, "inet6")
	eq(calls[1].hello.raw, raw)
end)

it("the default server calls the hook with service = nil", function()
	recorder("alpha")
	banlease.register_client_hello_plugins({ "alpha" })
	banlease.tls_drop_hook(nil, false, false, nil)
	eq(#calls, 1)
	eq(calls[1].hello.service, nil)
end)

it("runs with the default settings, where the core's own drop is off", function()
	recorder("alpha")
	banlease.register_client_hello_plugins({ "alpha" })
	eq(vars.BANS_TLS_DROP_REASONS, "")
	banlease.tls_drop_hook(service, false, false, nil)
	eq(#calls, 1)
end)

it("a plugin drop exits the handshake once, counts the drop and logs the reason once a minute", function()
	recorder("alpha", "drop", "idle handshakes: 31 of 31")
	recorder("beta")
	banlease.register_client_hello_plugins({ "alpha", "beta" })
	worker_id = 3
	eq(banlease.tls_drop_hook(service, false, false, nil), true)
	eq(#exited, 1)
	eq(exited[1], ngx.ERROR)
	eq(#calls, 1, "the first drop is final")
	eq(ngx.shared.metrics_datastore:get("tls_drops_plugin_alpha_3"), 1)
	eq(#logs, 1)
	eq(logs[1].level, ngx.WARN)
	assert(logs[1].msg:find("alpha", 1, true) and logs[1].msg:find("1.2.3.4", 1, true))
	assert(logs[1].msg:find("idle handshakes: 31 of 31", 1, true), logs[1].msg)
	eq(banlease.tls_drop_hook(service, false, false, nil), true)
	eq(#exited, 2)
	eq(#logs, 1, "second drop: no second warning")
	eq(ngx.shared.metrics_datastore:get("tls_drops_plugin_alpha_3"), 2)
end)

it("a drop with a missing or odd reason still drops", function()
	recorder("alpha", "drop", { not_text = true })
	banlease.register_client_hello_plugins({ "alpha" })
	eq(banlease.tls_drop_hook(service, false, false, nil), true)
	eq(#exited, 1)
end)

it("a plugin detect only logs: no exit, no drop metric, the next plugin still runs", function()
	recorder("alpha", "detect", "would drop")
	recorder("beta")
	banlease.register_client_hello_plugins({ "alpha", "beta" })
	eq(banlease.tls_drop_hook(service, false, false, nil), nil)
	eq(#exited, 0)
	eq(#calls, 2)
	eq(next(ngx.shared.metrics_datastore._data), nil)
	eq(#logs, 1)
	assert(logs[1].msg:find("would drop", 1, true) and logs[1].msg:find("detect", 1, true), logs[1].msg)
	banlease.tls_drop_hook(service, false, false, nil)
	eq(#logs, 1, "rate limited")
end)

it("an error in a plugin fails open: logged once, the next plugin runs, nothing is dropped", function()
	plugin("alpha", function()
		error("boom")
	end)
	recorder("beta")
	banlease.register_client_hello_plugins({ "alpha", "beta" })
	eq(banlease.tls_drop_hook(service, false, false, nil), nil)
	eq(#exited, 0)
	eq(#calls, 1)
	eq(#logs, 1)
	eq(logs[1].level, ngx.ERR)
	assert(logs[1].msg:find("alpha", 1, true) and logs[1].msg:find("boom", 1, true), logs[1].msg)
	banlease.tls_drop_hook(service, false, false, nil)
	eq(#logs, 1, "a plugin that raises on every handshake does not flood the log")
end)

it("any other return value is not a drop", function()
	for _, value in ipairs({ "banana", true, 1, "DROP", false, "" }) do
		reset()
		recorder("alpha", value)
		banlease.register_client_hello_plugins({ "alpha" })
		eq(banlease.tls_drop_hook(service, false, false, nil), nil, tostring(value))
		eq(#exited, 0, tostring(value))
	end
end)

it("the core's own drop wins: the plugins are not called", function()
	vars.BANS_TLS_DROP_REASONS = "crowdsec"
	utils_stub.is_banned_local = function()
		return true, "crowdsec", 4
	end
	recorder("alpha")
	banlease.register_client_hello_plugins({ "alpha" })
	eq(banlease.tls_drop_hook(service, false, false, nil), true)
	eq(#exited, 1)
	eq(#calls, 0)
	utils_stub.is_banned_local = function()
		return false, "not banned", nil
	end
end)

it("the core's detect verdict is not a drop: the plugins still run", function()
	vars.BANS_TLS_DROP_REASONS = "crowdsec"
	vars.SECURITY_MODE = "detect"
	utils_stub.is_banned_local = function()
		return true, "crowdsec", 4
	end
	recorder("alpha")
	banlease.register_client_hello_plugins({ "alpha" })
	eq(banlease.tls_drop_hook(service, false, false, nil), nil)
	eq(#exited, 0)
	eq(#calls, 1)
	utils_stub.is_banned_local = function()
		return false, "not banned", nil
	end
end)

it("a QUIC hello reaches the plugins with quic = true; an unreadable extension list skips them", function()
	recorder("alpha")
	banlease.register_client_hello_plugins({ "alpha" })
	quic = true
	banlease.tls_drop_hook(service, false, false, nil)
	eq(#calls, 1)
	eq(calls[1].hello.quic, true)
	ext_error = true
	banlease.tls_drop_hook(service, false, false, nil)
	eq(#calls, 1, "fail open: not classified, not offered")
end)

it("PROXY protocol or real IP without trusted networks: the address is unknown, the flags say so", function()
	recorder("alpha")
	banlease.register_client_hello_plugins({ "alpha" })
	pp_addr = "9.9.9.9"
	banlease.tls_drop_hook(service, true, false, nil)
	banlease.tls_drop_hook(service, false, true, nil)
	eq(#calls, 2)
	for _, call in ipairs(calls) do
		eq(call.hello.ip, nil)
		eq(call.hello.raw, "\1\2\3\4")
	end
	eq(calls[1].hello.proxy_protocol, true)
	eq(calls[2].hello.real_ip, true)
end)

it("PROXY protocol behind a trusted proxy: ip is the PROXY address", function()
	recorder("alpha")
	banlease.register_client_hello_plugins({ "alpha" })
	pp_addr = "9.9.9.9"
	banlease.tls_drop_hook(service, true, true, "1.2.3.0/24")
	eq(calls[1].hello.ip, "9.9.9.9")
	eq(calls[1].hello.trusted, "1.2.3.0/24")
	eq(calls[1].hello.raw, "\1\2\3\4", "raw stays the peer")
end)

it("nothing yields: no request variable, no Redis, no sleep or cosocket is touched", function()
	recorder("alpha", "detect", "x")
	recorder("beta", "drop", "y")
	banlease.register_client_hello_plugins({ "alpha", "beta" })
	ngx.sleep, ngx.socket, ngx.thread = nil, nil, nil
	eq(banlease.tls_drop_hook(service, false, false, nil), true)
	eq(var_touched, false)
end)

it("no behaviour change when no plugin exports the hook: no address read, no work", function()
	eq(banlease.tls_drop_hook(service, false, false, nil), nil)
	eq(raw_calls, 0)
	eq(#logs, 0)
	eq(#exited, 0)
	eq(next(ngx.shared.metrics_datastore._data), nil)
	eq(next(ngx.shared.bans_meta._data), nil)
	eq(banlease.tls_drop_hook(nil, false, false, nil), nil)
end)

-- The templates, run as real fragments ---------------------------------------------------------------------------

local function read(path)
	local f = assert(io.open(root .. "/" .. path, "r"))
	local text = f:read("*a")
	f:close()
	return text
end

-- The Lua body of the ssl_client_hello_by_lua_block of a template, with its Jinja expressions filled in
local function client_hello_block(path)
	local text = read(path)
	local _, open_end = text:find("ssl_client_hello_by_lua_block%s*{")
	assert(open_end, "no ssl_client_hello_by_lua_block in " .. path)
	local depth, pos = 1, open_end + 1
	while depth > 0 do
		local c = text:sub(pos, pos)
		assert(c ~= "", "unbalanced block")
		if c == "{" then
			depth = depth + 1
		elseif c == "}" then
			depth = depth - 1
		end
		pos = pos + 1
	end
	local body = text:sub(open_end + 1, pos - 2)
	body = body:gsub('{{ "true" if USE_PROXY_PROTOCOL == "yes" else "false" }}', "false")
	body = body:gsub('{{ "true" if USE_REAL_IP == "yes" else "false" }}', "false")
	body = body:gsub("{{ tls_drop_trusted }}", "nil")
	body = body:gsub('{{ SERVER_NAME%.split%(" "%)%[0%] }}', service)
	assert(not body:find("{{", 1, true), "an expression is left in the block: " .. tostring(body:match("{{.-}}")))
	return assert(load(body, "=" .. path))
end

local legacy_calls, order_error
local order
package.loaded["bunkerweb.datastore"] = {
	new = function()
		return {
			get = function(_, key)
				assert(key == "plugins_order")
				if order_error then
					return nil, order_error
				end
				return order
			end,
		}
	end,
}
package.loaded["bunkerweb.logger"] = {
	new = function()
		return { log = function() end }
	end,
}
package.loaded["bunkerweb.helpers"] = {
	require_plugin = function(id)
		local module = package.loaded[id .. "/" .. id]
		if not module then
			return nil, "plugin " .. id .. " doesn't have LUA code"
		end
		return module, "ok"
	end,
	new_plugin = function(module)
		return true, { module = module }
	end,
	call_plugin = function(obj, method)
		legacy_calls[#legacy_calls + 1] = obj.module.name .. ":" .. method
		return true, { ret = true, msg = "ok" }
	end,
}

-- A plugin module that has the hook and the legacy method, like antiddos on a hook core
local function hook_and_legacy(id, verdict)
	plugin(id, function(hello)
		calls[#calls + 1] = { id = id, hello = hello }
		return verdict
	end)
	package.preload[id .. "/" .. id] = function()
		return { client_hello = modules[id], ssl_client_hello_default = function() end, name = id }
	end
	package.loaded[id .. "/" .. id] = nil
	package.loaded[id .. "/" .. id] = require(id .. "/" .. id)
end
local function legacy_only(id)
	package.loaded[id .. "/" .. id] = { ssl_client_hello_default = function() end, name = id }
end

local default_block = client_hello_block("src/common/confs/default-server-http.conf")
local server_block = client_hello_block("src/common/confs/server-http/ssl-certificate-lua.conf")

local function setup_default_server(verdict)
	hook_and_legacy("antiddos", verdict)
	legacy_only("misc")
	order = { ssl_client_hello_default = { "antiddos", "misc" } }
	legacy_calls, order_error = {}, nil
	banlease.register_client_hello_plugins({ "antiddos" })
end

it(
	"default server: a hook plugin is called once, through the hook only; a plugin without the hook still runs",
	function()
		setup_default_server(nil)
		default_block()
		eq(#calls, 1, "the hook plugin ran once")
		eq(calls[1].hello.service, nil)
		eq(#legacy_calls, 1)
		eq(legacy_calls[1], "misc:ssl_client_hello_default", "the legacy loop skipped the hook plugin")
		package.loaded["antiddos/antiddos"], package.loaded["misc/misc"] = nil, nil
	end
)

it("default server: a plugin drop ends the handshake before the legacy loop", function()
	setup_default_server("drop")
	default_block()
	eq(#exited, 1)
	eq(#calls, 1)
	eq(#legacy_calls, 0)
	package.loaded["antiddos/antiddos"], package.loaded["misc/misc"] = nil, nil
end)

it("default server: with no hook plugin registered the legacy loop runs every plugin as before", function()
	setup_default_server(nil)
	banlease.register_client_hello_plugins({})
	default_block()
	eq(#calls, 0)
	eq(#legacy_calls, 2)
	eq(legacy_calls[1], "antiddos:ssl_client_hello_default")
	package.loaded["antiddos/antiddos"], package.loaded["misc/misc"] = nil, nil
end)

it("exactly once per handshake: no SNI, an unknown SNI (default server) and a known SNI (the service)", function()
	setup_default_server(nil)
	default_block() -- no SNI: nginx serves the default server
	default_block() -- unknown SNI: the same default server
	server_block() -- known SNI: the service's own block
	eq(#calls, 3, "one plugin call per handshake")
	eq(
		tostring(calls[1].hello.service)
			.. ","
			.. tostring(calls[2].hello.service)
			.. ","
			.. tostring(calls[3].hello.service),
		"nil,nil," .. service
	)
	eq(#legacy_calls, 2, "only the plugin without the hook, once per default-server handshake")
	package.loaded["antiddos/antiddos"], package.loaded["misc/misc"] = nil, nil
end)

it("service block: calls the hook once with the service name and nothing else", function()
	local seen = {}
	local real = banlease.tls_drop_hook
	banlease.tls_drop_hook = function(...)
		seen[#seen + 1] = { ... }
		return real(...)
	end
	server_block()
	banlease.tls_drop_hook = real
	eq(#seen, 1)
	eq(seen[1][1], service)
	eq(seen[1][2], false)
	eq(seen[1][3], false)
	eq(seen[1][4], nil)
end)

if failures > 0 then
	print(failures .. " test(s) failed")
	os.exit(1)
end
