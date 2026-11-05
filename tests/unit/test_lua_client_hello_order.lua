-- Plain Lua check of how a plugin joins the ssl_client_hello phase: a module-level client_hello() function puts the
-- phase in plugin.phases, and the order comes from the ssl_client_hello key of core/order.json and from
-- PLUGINS_ORDER_SSL_CLIENT_HELLO. Runs the real helpers.lua and the real order.json on the phase list of the real
-- utils.lua.
-- Run: lua tests/unit/test_lua_client_hello_order.lua   (from the repo root)
-- luacheck: ignore 122
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
local function join(list)
	return table.concat(list or {}, ",")
end

local F = dofile(root .. "/tests/unit/lua_lease_fakes.lua")(root)
local json = F.json

-- The phase list of the shipped utils.lua, not a copy of it
local function read(path)
	local f = assert(io.open(path, "r"))
	local text = f:read("*a")
	f:close()
	return text
end
local utils_src = read(root .. "/src/bw/lua/bunkerweb/utils.lua")
local phases_literal =
	assert(utils_src:match("utils%.get_phases = function%(%)%s*return (%b{})"), "get_phases not found")
local PHASES = assert(load("return " .. phases_literal))()

package.loaded["resty.core.base"] = { get_request = function() end }
package.loaded["bunkerweb.ctx"] = { apply_ref = function() end, stash_ref = function() end }
package.loaded["bunkerweb.utils"] = {
	get_phases = function()
		return PHASES
	end,
}

-- order_plugins reads the order file at its installed path
local real_open = io.open
io.open = function(path, mode)
	if path == "/usr/share/bunkerweb/core/order.json" then
		return real_open(root .. "/src/common/core/order.json", mode)
	end
	return real_open(path, mode)
end
local helpers = dofile(root .. "/src/bw/lua/bunkerweb/helpers.lua")
io.open = real_open

local scratch = os.tmpname()
os.remove(scratch)
assert(os.execute("mkdir -p " .. scratch))
local function plugin_json(id)
	local path = scratch .. "/" .. id .. ".json"
	local f = assert(io.open(path, "w"))
	f:write(json.encode({ id = id, name = id, description = id, version = "1.0", settings = {}, stream = "no" }))
	f:close()
	return path
end
local function module(id, fields)
	fields.new = function() end
	package.loaded[id .. "/" .. id] = fields
end

it("the shipped phase list has ssl_client_hello, next to the default-server one", function()
	local seen = {}
	for i, phase in ipairs(PHASES) do
		seen[phase] = i
	end
	assert(seen.ssl_client_hello, "ssl_client_hello is a phase")
	assert(seen.ssl_client_hello_default)
end)

it("a module-level client_hello function makes the plugin join the ssl_client_hello phase", function()
	module("hooked", { client_hello = function() end })
	local ok, plugin = helpers.load_plugin(plugin_json("hooked"))
	assert(ok, tostring(plugin))
	eq(join(plugin.phases), "ssl_client_hello")
end)

it("a plugin with only the legacy method is not in the ssl_client_hello phase, and the reverse", function()
	module("legacy", { ssl_client_hello_default = function() end })
	local ok, plugin = helpers.load_plugin(plugin_json("legacy"))
	assert(ok, tostring(plugin))
	eq(join(plugin.phases), "ssl_client_hello_default")
	module("both", { ssl_client_hello_default = function() end, client_hello = function() end })
	local _, both = helpers.load_plugin(plugin_json("both"))
	eq(join(both.phases), "ssl_client_hello,ssl_client_hello_default")
end)

it("a method named ssl_client_hello is not the hook", function()
	module("misnamed", { ssl_client_hello = function() end })
	local _, plugin = helpers.load_plugin(plugin_json("misnamed"))
	eq(join(plugin.phases), "")
end)

local function plugin_with(id, phases)
	return { id = id, phases = phases }
end

it("order.json has an ssl_client_hello key and the plugins join the phase in alphabetical order by default", function()
	local order = json.decode(read(root .. "/src/common/core/order.json"))
	assert(type(order.ssl_client_hello) == "table", "order.json needs an ssl_client_hello list")
	local plugins = {
		plugin_with("zeta", { "ssl_client_hello" }),
		plugin_with("alpha", { "ssl_client_hello", "access" }),
		plugin_with("beta", { "access" }),
	}
	local ok, result = helpers.order_plugins(plugins, { global = {} })
	assert(ok, tostring(result))
	eq(join(result.ssl_client_hello), "alpha,zeta")
	eq(join(result.global.ssl_client_hello), "alpha,zeta")
end)

it("PLUGINS_ORDER_SSL_CLIENT_HELLO reorders the phase; unknown ids are reported as missing", function()
	local plugins = {
		plugin_with("alpha", { "ssl_client_hello" }),
		plugin_with("beta", { "ssl_client_hello" }),
		plugin_with("gamma", { "ssl_client_hello" }),
	}
	local ok, result, missing =
		helpers.order_plugins(plugins, { global = { PLUGINS_ORDER_SSL_CLIENT_HELLO = "gamma ghost alpha" } })
	assert(ok, tostring(result))
	eq(join(result.ssl_client_hello), "gamma,alpha,beta")
	assert(missing.global.ssl_client_hello.ghost, "an id that is not a plugin of the phase is reported")
end)

it("the other phases keep their order", function()
	local plugins = {
		plugin_with("alpha", { "ssl_client_hello", "ssl_client_hello_default" }),
		plugin_with("misc", { "ssl_client_hello_default" }),
	}
	local ok, result = helpers.order_plugins(plugins, { global = {} })
	assert(ok, tostring(result))
	eq(join(result.ssl_client_hello_default), "misc,alpha", "the order.json entry of misc still leads")
end)

os.execute("rm -rf " .. scratch)
if failures > 0 then
	print(failures .. " test(s) failed")
	os.exit(1)
end
