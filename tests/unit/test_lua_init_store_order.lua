-- Plain Lua check of the order of the init phase (init-lua.conf, init-stream-lua.conf): everything that can reject the
-- configuration has to run before the internalstore is flushed, or a rejected reload leaves the old workers serving
-- from a store that is partly emptied. It also checks the reload marker across the two init phases of one master: a
-- phase that succeeds leaves the marker to the workers, a phase that aborts removes the marker it owns.
-- Any error raised in the init block, not only an explicit abort, has to remove the marker it owns and fail the init.
-- Run: lua tests/unit/test_lua_init_store_order.lua   (from the repo root)
-- INIT_DIR points the test at another copy of src/common/confs, HELPERS_FILE at another copy of helpers.lua.
-- luacheck: ignore 122
local root = arg[0]:match("^(.*)/tests/unit/") or "."
local dir = os.getenv("INIT_DIR") or (root .. "/src/common/confs")
local helpers_file = os.getenv("HELPERS_FILE") or (root .. "/src/bw/lua/bunkerweb/helpers.lua")

local failures = 0
local MARKER = "/var/tmp/bunkerweb/reloading"
local VARIABLES = "/etc/nginx/variables.env"
local ORDER = "/usr/share/bunkerweb/core/order.json"
local scratch = os.tmpname()
os.remove(scratch)
assert(os.execute("mkdir -p " .. scratch))
local marker = scratch .. "/marker"
local variables = scratch .. "/variables.env"
local order_json = scratch .. "/order.json"

local real_open, real_remove, real_lines = io.open, os.remove, io.lines
local unreadable_plugin, failed_read_plugin
local function remap(path)
	if path == MARKER then
		return marker
	end
	if path == VARIABLES then
		return variables
	end
	if path == ORDER then
		return order_json
	end
	return path
end
os.remove = function(path)
	return real_remove(remap(path))
end
io.open = function(path, mode)
	if path == unreadable_plugin then
		return nil, "Permission denied", 13
	end
	if path == failed_read_plugin then
		return {
			read = function()
				return nil, "Input/output error"
			end,
			close = function() end,
		}
	end
	return real_open(remap(path), mode)
end
io.lines = function(path, ...)
	return real_lines(remap(path), ...)
end
-- Plugin directories the init phase finds: one when a test sets plugin_dirs
local plugin_dirs
io.popen = function(command)
	local pending = command:find("/usr/share/bunkerweb/core", 1, true) and plugin_dirs or nil
	return {
		lines = function()
			return function()
				local dir_found = pending
				pending = nil
				return dir_found
			end
		end,
		close = function() end,
	}
end

-- What the init phase did to the store, in order
local calls
local flush_result
local cachestore_error
-- Raised by the stubbed load_plugin (a plugin that fails to require) and by cjson.encode (the plugin order log)
local load_plugin_error
local encode_error
-- Logs of the init phase, and the helpers it runs with: the stubs below, or the real module
local logs
local error_logs
local saved_plugins
local real_helpers
local order_result
-- Runs while the init phase flushes the store: lets a test change the world there
local on_flush
package.loaded["bunkerweb.logger"] = {
	new = function()
		return {
			log = function(_, level, msg)
				if level == ngx.ERR then
					table.insert(error_logs, msg)
				end
				table.insert(logs, msg)
			end,
		}
	end,
}
local stub_helpers = {
	load_plugin = function()
		if load_plugin_error then
			error(load_plugin_error, 0)
		end
		return false, "no plugin"
	end,
	load_variables = function()
		return true, {}
	end,
	order_plugins = function()
		return true, order_result, { global = {}, per_site = {} }
	end,
}
package.loaded["bunkerweb.helpers"] = stub_helpers
package.loaded["bunkerweb.datastore"] = {
	new = function()
		return {
			flush_lru = function()
				table.insert(calls, "flush_lru")
				if on_flush then
					on_flush()
				end
				return flush_result[1], flush_result[2]
			end,
			delete_all = function(_, key)
				table.insert(calls, "delete_all " .. key)
				return true, "success"
			end,
			set = function(_, key, value)
				if key == "plugins" then
					saved_plugins = value
				end
				table.insert(calls, "set " .. key)
				return true, "success"
			end,
		}
	end,
}
package.loaded["bunkerweb.cachestore"] = {
	new = function()
		if cachestore_error then
			error(cachestore_error, 0)
		end
		return {
			purge = function()
				table.insert(calls, "purge")
				return true
			end,
		}
	end,
}
local valid_plugin_json =
	'{"id":"testplugin","name":"Test","description":"Test plugin","version":"1","settings":{},"stream":"yes"}'
package.loaded["testplugin/testplugin"] = { new = function() end, access = function() end }
package.loaded["cjson"] = {
	encode = function()
		if encode_error then
			error(encode_error, 0)
		end
		return "[]"
	end,
	decode = function(text)
		if text == valid_plugin_json then
			return {
				id = "testplugin",
				name = "Test",
				description = "Test plugin",
				version = "1",
				settings = {},
				stream = "yes",
			}
		end
		if text == "false" then
			return false
		end
		if text:find("INVALID", 1, true) then
			error("Expected value but found invalid token at character 1", 0)
		end
		return {}
	end,
}
package.loaded["ngx.process"] = {
	type = function()
		return "master"
	end,
}
ngx = { INFO = 7, ERR = 4, NOTICE = 6, WARN = 5, shared = {}, config = { subsystem = "http" } }

-- The real helpers.lua, on stubbed dependencies
package.loaded["resty.core.base"] = { get_request = function() end }
package.loaded["bunkerweb.ctx"] = { apply_ref = function() end, stash_ref = function() end }
package.loaded["bunkerweb.utils"] = {
	get_phases = function()
		return { "init", "access", "log" }
	end,
}
real_helpers = assert(loadfile(helpers_file))()

local function it(name, fn)
	local ok, err = pcall(fn)
	print((ok and "PASS " or "FAIL ") .. name .. (ok and "" or (": " .. tostring(err))))
	if not ok then
		failures = failures + 1
	end
end

local function write(path, content)
	if content == nil then
		real_remove(path)
		return
	end
	local file = assert(real_open(path, "w"))
	file:write(content)
	file:close()
end
local function read(path)
	local file = real_open(path, "r")
	if not file then
		return nil
	end
	local content = file:read("*a")
	file:close()
	return content
end

-- Runs the init block of the conf. Returns true when it ran to the end, false and the error otherwise
local function run_init(name)
	local file = assert(real_open(dir .. "/" .. name, "r"))
	local source = file:read("*a")
	file:close()
	local body = assert(source:match("^init_by_lua_block {\n(.*)}%s*$"), "unexpected layout")
	return pcall(assert(load(body, "=" .. name)))
end
local function aborted(name)
	local ok, err = run_init(name)
	assert(
		not ok and tostring(err):find("init phase aborted", 1, true),
		"the init phase did not abort: " .. tostring(err)
	)
end
local function logged(text)
	for _, line in ipairs(logs) do
		if line:find(text, 1, true) then
			return true
		end
	end
	return false
end
local function touched_store()
	return table.concat(calls, ", ")
end

local confs = { "init-lua.conf", "init-stream-lua.conf" }
local function reset()
	calls, flush_result, cachestore_error, on_flush = {}, { true, "success" }, nil, nil
	logs, error_logs, load_plugin_error, encode_error, plugin_dirs = {}, {}, nil, nil, nil
	unreadable_plugin, failed_read_plugin, saved_plugins = nil, nil, nil
	order_result = { init = {}, global = {}, per_site = {} }
	package.loaded["bunkerweb.helpers"] = stub_helpers
	write(order_json, "{}")
	write(variables, "SERVER_NAME=www.example.com\n")
	write(marker, nil)
end

for _, name in ipairs(confs) do
	local function case(title, fn)
		it(name .. ": " .. title, function()
			reset()
			fn()
		end)
	end

	case("a configuration that loads swaps the store and keeps the marker for its workers", function()
		write(marker, "1.111")
		local ok, err = run_init(name)
		assert(ok, tostring(err))
		assert(read(marker) == "1.111", "a successful init removed the marker")
		assert(
			touched_store():find("flush_lru", 1, true) and touched_store():find("set plugins_order", 1, true),
			touched_store()
		)
	end)

	case("a rejected variables file aborts before the store is touched", function()
		write(variables, nil)
		aborted(name)
		assert(#calls == 0, "the store was touched: " .. touched_store())
	end)

	case("a store that cannot be flushed aborts before anything is deleted or written", function()
		write(marker, "1.111")
		flush_result = { false, "lru is not instantiated" }
		aborted(name)
		assert(touched_store() == "flush_lru", "the store was touched: " .. touched_store())
		assert(read(marker) == nil, "the rejected cycle left its marker")
	end)

	case("a cachestore that cannot be built aborts before the store is flushed", function()
		write(marker, "1.111")
		cachestore_error = "can't instantiate mlcache"
		aborted(name)
		assert(#calls == 0, "the store was flushed before the cachestore failed: " .. touched_store())
		assert(read(marker) == nil, "the rejected cycle left its marker")
		assert(logged("can't instantiate mlcache") and logged("stack traceback"), "the error was not logged")
	end)

	case("a plugin whose require raises aborts, removes the marker and leaves the store untouched", function()
		write(marker, "1.111")
		plugin_dirs = "/etc/bunkerweb/plugins/broken"
		load_plugin_error = "error loading module 'broken/broken'"
		aborted(name)
		assert(#calls == 0, "the store was touched: " .. touched_store())
		assert(read(marker) == nil, "the rejected cycle left its marker")
		assert(logged("error loading module 'broken/broken'") and logged("stack traceback"), "the error was not logged")
	end)

	case("a raise after the flush still aborts and removes the marker", function()
		write(marker, "1.111")
		order_result = { init = {}, global = { access = { "x" } }, per_site = {} }
		encode_error = "cannot encode the order"
		aborted(name)
		assert(touched_store():find("flush_lru", 1, true), "the raise came before the flush: " .. touched_store())
		assert(read(marker) == nil, "the rejected cycle left its marker")
		assert(logged("cannot encode the order"), "the error was not logged")
	end)

	case("a raise leaves a marker that holds another token", function()
		write(marker, "1.111")
		order_result = { init = {}, global = { access = { "x" } }, per_site = {} }
		encode_error = "cannot encode the order"
		on_flush = function()
			write(marker, "2.222")
		end
		aborted(name)
		assert(read(marker) == "2.222", "the marker of another cycle was removed")
	end)

	case("an error is logged once, an explicit abort adds no traceback", function()
		write(variables, nil)
		aborted(name)
		assert(not logged("stack traceback"), "an explicit abort logged a traceback")
		reset()
		cachestore_error = "can't instantiate mlcache"
		aborted(name)
		local count = 0
		for _, line in ipairs(logs) do
			if line:find("can't instantiate mlcache", 1, true) then
				count = count + 1
			end
		end
		assert(count == 1, "the error was logged " .. count .. " times")
	end)

	local function use_plugin(content)
		plugin_dirs = scratch
		write(scratch .. "/plugin.json", content)
		package.loaded["bunkerweb.helpers"] = {
			load_plugin = real_helpers.load_plugin,
			load_variables = stub_helpers.load_variables,
			order_plugins = real_helpers.order_plugins,
		}
		write(marker, "1.111")
	end

	for _, fixture in ipairs({
		{ "invalid JSON", "INVALID", "invalid JSON at" },
		{ "missing required fields", "{}", "missing field(s)" },
		{ "a scalar JSON value", "false", "expected an object" },
		{ "an unreadable file", valid_plugin_json, "Permission denied", "open" },
		{ "a failed read", valid_plugin_json, "Input/output error", "read" },
	}) do
		for _, changed_token in ipairs({ false, true }) do
			case(
				fixture[1]
					.. " aborts before flush, logs once and releases only its token (takeover="
					.. tostring(changed_token)
					.. ")",
				function()
					use_plugin(fixture[2])
					if fixture[4] == "open" then
						unreadable_plugin = scratch .. "/plugin.json"
					end
					if fixture[4] == "read" then
						failed_read_plugin = scratch .. "/plugin.json"
					end
					if changed_token then
						-- Replace the marker after init captured it, before the plugin fails.
						local original_load = package.loaded["bunkerweb.helpers"].load_plugin
						package.loaded["bunkerweb.helpers"].load_plugin = function(path)
							write(marker, "2.222")
							return original_load(path)
						end
					end
					aborted(name)
					assert(#calls == 0, "the store was touched: " .. touched_store())
					assert(read(marker) == (changed_token and "2.222" or nil), "wrong marker ownership")
					assert(#error_logs == 1, "expected one ERR line: " .. table.concat(error_logs, " | "))
					assert(logged(scratch .. "/plugin.json") and logged(fixture[3]), table.concat(logs, " | "))
					assert(not logged("stack traceback"), "the plugin error raised instead of explicitly aborting")
				end
			)
		end
	end

	case("a directory without plugin.json is skipped and the init succeeds", function()
		use_plugin(nil)
		local ok, err = run_init(name)
		assert(ok, tostring(err))
		assert(#saved_plugins == 0, "a non-plugin was loaded")
		assert(#error_logs == 0, table.concat(error_logs, " | "))
		assert(read(marker) == "1.111", "successful init removed the worker marker")
	end)

	case("a valid plugin loads with its access handler", function()
		use_plugin(valid_plugin_json)
		local ok, err = run_init(name)
		assert(ok, tostring(err))
		assert(#saved_plugins == 1 and saved_plugins[1].id == "testplugin", "the valid plugin was skipped")
		assert(saved_plugins[1].phases[1] == "access", "the access handler was lost")
		assert(#error_logs == 0, table.concat(error_logs, " | "))
		assert(read(marker) == "1.111", "successful init removed the worker marker")
	end)

	case("an invalid order.json aborts with the decode error, not a concat raise", function()
		write(marker, "1.111")
		write(order_json, "INVALID")
		package.loaded["bunkerweb.helpers"] = {
			load_plugin = stub_helpers.load_plugin,
			load_variables = stub_helpers.load_variables,
			order_plugins = real_helpers.order_plugins,
		}
		aborted(name)
		assert(#calls == 0, "the store was touched: " .. touched_store())
		assert(read(marker) == nil, "the rejected cycle left its marker")
		assert(
			logged("invalid order.json : Expected value"),
			"the decode error was not logged: " .. table.concat(logs, " | ")
		)
		assert(not logged("stack traceback"), "the invalid order.json raised instead of returning an error")
	end)
end

-- One master runs the http init and the stream init of the same reload against the same marker
for _, pair in ipairs({ { "init-lua.conf", "init-stream-lua.conf" }, { "init-stream-lua.conf", "init-lua.conf" } }) do
	local first, second = pair[1], pair[2]
	it(first .. " loads, then " .. second .. " aborts: the marker of the rejected cycle goes", function()
		reset()
		write(marker, "1.111")
		local ok, err = run_init(first)
		assert(ok, tostring(err))
		assert(read(marker) == "1.111", "the first phase removed the marker")
		flush_result = { false, "lru is not instantiated" }
		aborted(second)
		assert(read(marker) == nil, "the marker of the rejected cycle was left behind")
	end)
end

it("an abort with no marker (first start) is a no-op", function()
	reset()
	flush_result = { false, "lru is not instantiated" }
	aborted("init-lua.conf")
	assert(read(marker) == nil)
end)

it("an abort leaves a marker that holds another token", function()
	reset()
	write(marker, "1.111")
	flush_result = { false, "lru is not instantiated" }
	-- The marker changes hands after the init phase read it
	on_flush = function()
		write(marker, "2.222")
	end
	aborted("init-lua.conf")
	assert(read(marker) == "2.222", "the marker of another cycle was removed")
end)

-- The helpers return their errors, they do not raise them
it("helpers.order_plugins returns the decode error of an invalid order.json", function()
	reset()
	write(order_json, "INVALID")
	local ok, err = pcall(real_helpers.order_plugins, {}, {})
	assert(ok, "order_plugins raised: " .. tostring(err))
	local result, message = real_helpers.order_plugins({}, {})
	assert(result == false and type(message) == "string", tostring(message))
	assert(message == "invalid order.json : Expected value but found invalid token at character 1", message)
end)

it("helpers.load_plugin returns the decode error of an invalid plugin.json", function()
	reset()
	local plugin_json = scratch .. "/plugin.json"
	write(plugin_json, "INVALID")
	local ok, err = pcall(real_helpers.load_plugin, plugin_json)
	assert(ok, "load_plugin raised: " .. tostring(err))
	local result, message = real_helpers.load_plugin(plugin_json)
	assert(result == false and type(message) == "string", tostring(message))
	assert(message:find("invalid JSON at " .. plugin_json .. " : Expected value", 1, true), message)
end)

io.open, io.lines, os.remove = real_open, real_lines, real_remove
os.execute("rm -rf " .. scratch)
if failures > 0 then
	print(failures .. " failure(s)")
	os.exit(1)
end
print("all passed")
