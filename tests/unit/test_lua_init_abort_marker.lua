-- Plain Lua check of the init phase (init-lua.conf, init-stream-lua.conf): a reload it rejects starts no new workers,
-- so the init phase itself has to remove the reload marker, or no reload and no generation can go on until a restart.
-- It does so only for the reconfigure that owns the marker: the master process, with the marker still holding the
-- token it found when the init phase started. Any other marker belongs to another reload and stays.
-- It also keeps that token for the workers it starts (init-worker-lua.conf removes the marker only for the same one).
-- Run: lua tests/unit/test_lua_init_abort_marker.lua   (from the repo root)
-- INIT_DIR points the test at another copy of src/common/confs.
-- luacheck: ignore 122
local root = arg[0]:match("^(.*)/tests/unit/") or "."
local dir = os.getenv("INIT_DIR") or (root .. "/src/common/confs")

local failures = 0
local MARKER = "/var/tmp/bunkerweb/reloading"
local scratch = os.tmpname()
os.remove(scratch)
assert(os.execute("mkdir -p " .. scratch))
local marker = scratch .. "/marker"

local real_open, real_remove = io.open, os.remove
os.remove = function(path)
	return real_remove(path == MARKER and marker or path)
end
-- variables.env is missing: the init phase has to abort
io.open = function(path, mode)
	if path == "/etc/nginx/variables.env" then
		return nil, "No such file or directory"
	end
	return real_open(path == MARKER and marker or path, mode)
end
-- Runs once the init phase has read the marker and is on its way to the abort: lets a test change the world there
local before_abort
io.popen = function()
	if before_abort then
		before_abort()
	end
	return {
		lines = function()
			return function() end
		end,
		close = function() end,
	}
end

local logger = {
	log = function() end,
}
package.loaded["bunkerweb.logger"] = {
	new = function()
		return logger
	end,
}
package.loaded["bunkerweb.helpers"] = {}
package.loaded["bunkerweb.datastore"] = {
	new = function()
		return {}
	end,
}
package.loaded["cjson"] = {}
local process_type = "master"
package.loaded["ngx.process"] = {
	type = function()
		return process_type
	end,
}
ngx = { INFO = 7, ERR = 4, NOTICE = 6, WARN = 5, shared = {}, config = { subsystem = "http" } }

local function it(name, fn)
	local ok, err = pcall(fn)
	print((ok and "PASS " or "FAIL ") .. name .. (ok and "" or (": " .. tostring(err))))
	if not ok then
		failures = failures + 1
	end
end

local function write_marker(content)
	if content == nil then
		real_remove(marker)
		return
	end
	local file = assert(real_open(marker, "w"))
	file:write(content)
	file:close()
end
local function read_marker()
	local file = real_open(marker, "r")
	if not file then
		return nil
	end
	local content = file:read("*a")
	file:close()
	return content
end

-- Runs the init block of the conf and reports whether it aborted
local function run_init(name)
	local file = assert(real_open(dir .. "/" .. name, "r"))
	local source = file:read("*a")
	file:close()
	local body = assert(source:match("^init_by_lua_block {\n(.*)}%s*$"), "unexpected layout")
	local chunk = assert(load(body, "=" .. name))
	local ok, err = pcall(chunk)
	assert(
		not ok and tostring(err):find("init phase aborted", 1, true),
		"the init phase did not abort: " .. tostring(err)
	)
end

for _, name in ipairs({ "init-lua.conf", "init-stream-lua.conf" }) do
	local function case(title, fn)
		it(name .. ": " .. title, function()
			process_type, before_abort = "master", nil
			package.loaded["bunkerweb.reload_marker_token"] = nil
			write_marker(nil)
			fn()
		end)
	end

	case("a rejected reconfigure removes the marker it owns and still aborts", function()
		write_marker("1.111")
		run_init(name)
		assert(read_marker() == nil, "the marker was left behind")
	end)

	case("a process that is not the master leaves the marker alone", function()
		process_type = "single"
		write_marker("1.111")
		run_init(name)
		assert(read_marker() == "1.111", "the marker of another reload was removed")
	end)

	case("a marker that changed hands since the init phase read it stays", function()
		write_marker("1.111")
		before_abort = function()
			write_marker("2.222")
		end
		run_init(name)
		assert(read_marker() == "2.222", "the marker of the reload that took over was removed")
	end)

	case("a marker created after the init phase started stays", function()
		before_abort = function()
			write_marker("2.222")
		end
		run_init(name)
		assert(read_marker() == "2.222", "a marker the init phase never saw was removed")
	end)

	case("a marker with no token has no owner and stays", function()
		write_marker("")
		run_init(name)
		assert(read_marker() == "", "an empty marker was removed")
	end)

	case("no marker: nothing to remove, and it still aborts", function()
		run_init(name)
		assert(read_marker() == nil)
	end)
end

it("init-lua.conf keeps the marker's token for the workers it starts", function()
	process_type, before_abort = "master", nil
	write_marker("1.111")
	run_init("init-lua.conf")
	assert(
		package.loaded["bunkerweb.reload_marker_token"] == "1.111",
		tostring(package.loaded["bunkerweb.reload_marker_token"])
	)
	write_marker(nil)
	run_init("init-lua.conf")
	assert(package.loaded["bunkerweb.reload_marker_token"] == false, "a stale token was kept")
end)

io.open, os.remove = real_open, real_remove
os.execute("rm -rf " .. scratch)
if failures > 0 then
	print(failures .. " failure(s)")
	os.exit(1)
end
print("all passed")
