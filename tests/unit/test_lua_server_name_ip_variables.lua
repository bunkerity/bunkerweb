-- Plain Lua check that helpers.load_variables maps the per-service keys of a service named by an IPv4 or IPv6
-- literal (GitHub #4120): the prefix is matched literally, so ":" and "." in the service id are not pattern syntax.
-- Run: lua tests/unit/test_lua_server_name_ip_variables.lua   (from the repo root)
local root = arg[0]:match("^(.*)/tests/unit/") or "."
package.path = root .. "/src/bw/lua/?.lua;" .. package.path

local failures = 0
local function it(name, fn)
	local ok, err = pcall(fn)
	print((ok and "PASS " or "FAIL ") .. name .. (ok and "" or (": " .. tostring(err))))
	if not ok then
		failures = failures + 1
	end
end
local function eq(a, b, what)
	assert(a == b, (what or "value") .. ": expected " .. tostring(b) .. " got " .. tostring(a))
end

_G.ngx = { config = { subsystem = "http" }, var = {}, req = {}, shared = {} }
package.loaded["resty.core.base"] = { get_request = function() end }
package.loaded["bunkerweb.ctx"] = { apply_ref = function() end, stash_ref = function() end }
package.loaded["cjson"] = {
	encode = function() end,
	decode = function()
		return { MULTISITE = {}, SERVER_NAME = {} }
	end,
}
package.loaded["bunkerweb.ipaddr"] = { key = function() end }
package.loaded["bunkerweb.utils"] = {
	get_phases = function()
		return {}
	end,
	ip_is_global = function() end,
	is_ipv4 = function() end,
	is_ipv6 = function() end,
	get_variable = function() end,
}
local real_open = io.open
-- luacheck: push ignore 122
io.open = function(path, ...)
	if path == "/usr/share/bunkerweb/settings.json" then
		return {
			read = function()
				return "{}"
			end,
			close = function() end,
		}
	end
	return real_open(path, ...)
end
-- luacheck: pop
local helpers = require("bunkerweb.helpers")

local plugins = { { settings = { USE_ANTIBOT = {}, REVERSE_PROXY_HOST = { multiple = "reverse-proxy" } } } }

local function load(vars)
	local ok, variables = helpers.load_variables(vars, plugins)
	assert(ok, tostring(variables))
	return variables
end

it("an IPv6 service id keeps its per-service settings", function()
	local v = load({
		MULTISITE = "yes",
		SERVER_NAME = "2001:db8::1 www.example.com",
		["2001:db8::1_USE_ANTIBOT"] = "captcha",
		["www.example.com_USE_ANTIBOT"] = "no",
	})
	eq(v["2001:db8::1"].USE_ANTIBOT, "captcha", "ipv6 service")
	eq(v["www.example.com"].USE_ANTIBOT, "no", "hostname service")
end)

it("an IPv4 service id keeps its per-service settings and its multiple settings", function()
	local v = load({
		MULTISITE = "yes",
		SERVER_NAME = "192.0.2.10 192.0.2.1",
		["192.0.2.10_USE_ANTIBOT"] = "captcha",
		["192.0.2.10_REVERSE_PROXY_HOST_1"] = "http://backend",
	})
	eq(v["192.0.2.10"].USE_ANTIBOT, "captcha", "ipv4 service")
	eq(v["192.0.2.10"].REVERSE_PROXY_HOST_1, "http://backend", "multiple setting")
	eq(v["192.0.2.1"].USE_ANTIBOT, nil, "a prefix of another id must not leak ('.' is not a wildcard)")
end)

it("IPv6 ids that share a prefix stay apart", function()
	local v = load({
		MULTISITE = "yes",
		SERVER_NAME = "2001:db8::1 2001:db8::10",
		["2001:db8::10_USE_ANTIBOT"] = "captcha",
	})
	eq(v["2001:db8::10"].USE_ANTIBOT, "captcha", "longer id")
	eq(v["2001:db8::1"].USE_ANTIBOT, nil, "shorter id")
end)

os.exit(failures == 0 and 0 or 1)
