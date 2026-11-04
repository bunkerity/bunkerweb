-- Run with FLOCK_FIXTURE_DIR pointing at the copied generator.py and compiled flockffi.c fixtures.
-- luacheck: ignore 122
local lane = assert(os.getenv("FLOCK_FIXTURE_DIR"), "set FLOCK_FIXTURE_DIR")
local scenario = arg[1] or "gap"
local root = "."
dofile(root .. "/tests/unit/lua_lease_fakes.lua")(root)
package.cpath = lane .. "/?.so;" .. package.cpath
local libc = require "flockffi"
local scratch = os.tmpname()
local real_open, real_remove, real_execute, real_popen = io.open, os.remove, os.execute, io.popen
real_remove(scratch)
local dest = scratch .. "/nginx"
local staging = dest .. "/.bw-staging.1.1"
local generating = scratch .. "/generating"
local function map(path)
	path = path:gsub("/var/tmp/bunkerweb_needs_config", scratch .. "/needs_config")
	path = path:gsub("/etc/nginx", dest)
	path = path:gsub("/var/tmp/bunkerweb/generating", generating)
	path = path:gsub("/var/tmp/bunkerweb[^/]*", scratch .. "/tmp")
	return path
end
local function write(path, content)
	local f = assert(real_open(path, "w"))
	f:write(content or "")
	f:close()
end
local function exists(path)
	local f = real_open(path, "r")
	if f then
		f:close()
	end
	return f ~= nil
end
local payload = scratch .. "/payload"
assert(
	real_execute(
		"mkdir -p " .. scratch .. "/tmp " .. staging .. "/http " .. dest .. "/http " .. scratch .. "/render/http"
	)
)
for base, value in pairs({ [dest] = "old", [staging] = "push", [scratch .. "/render"] = "gen" }) do
	write(base .. "/variables.env", value)
	write(base .. "/http/a.conf", value)
end
assert(real_execute("cp -a " .. staging .. " " .. payload))
io.open = function(path, mode)
	return real_open(map(path), mode)
end
os.remove = function(path)
	return real_remove(map(path))
end
os.execute = function(command)
	if command:find("tar xzf", 1, true) then
		assert(real_execute("rm -rf " .. staging .. "; cp -a " .. payload .. " " .. staging))
		return 0
	end
	local ok = real_execute(map(command))
	return ok and 0 or 1
end
io.popen = function(command)
	if command:find("modsecurity_audit", 1, true) then
		return {
			read = function()
				return "ModSecurity audit preflight successful\n"
			end,
			close = function() end,
		}
	end
	return real_popen(map(command))
end
local actual_fopen = libc.fopen
libc.fopen = function(path, mode)
	return actual_fopen(map(path), mode)
end
package.loaded["ffi"] = {
	C = libc,
	os = "Linux",
	cdef = function() end,
	errno = function()
		return libc.errno()
	end,
}
package.loaded["bit"] = {}
package.loaded["middleclass"] = function()
	return {}
end
package.loaded["bunkerweb.helpers"] = {}
package.loaded["ngx.process"] = {}
package.loaded["resty.signal"] = {}
package.loaded["resty.sha256"] = {
	new = function()
		return {}
	end,
}
package.loaded["resty.upload"] = {
	new = function()
		return {
			set_timeout = function() end,
			read = function()
				return "eof"
			end,
		}
	end,
}
local held, unlocks = false, 0
package.loaded["resty.lock"] = {
	new = function()
		return {
			lock = function()
				assert(not held)
				held = true
				return 0
			end,
			unlock = function()
				assert(held)
				held = false
				unlocks = unlocks + 1
				return true
			end,
		}
	end,
}
local clock = 0
ngx.now = function()
	return clock
end
ngx.sleep = function(seconds)
	clock = clock + seconds
end
ngx.req = {}
ngx.worker = {
	pid = function()
		return 1
	end,
}
ngx.var = { connection = 1 }
local pushswap = require "bunkerweb.pushswap"
pushswap.SENTINEL_DESTINATION = dest
pushswap.STATE_ROOT = scratch .. "/state"
pushswap.digest_file = function()
	return "archive-A"
end
pushswap.applied_path = function()
	return scratch .. "/state/applied"
end
local real_swap = pushswap.swap
local swap_calls = 0
pushswap.swap = function(destination, incoming)
	swap_calls = swap_calls + 1
	return real_swap(map(destination), map(incoming))
end
local logs = {}
package.loaded["bunkerweb.logger"] = {
	new = function()
		return {
			log = function(_, _, message)
				logs[#logs + 1] = message
			end,
		}
	end,
}
local api = dofile(os.getenv("API_LUA") or "src/bw/lua/bunkerweb/api.lua")
local self = setmetatable({ ctx = { bw = { uri = "/confs" } } }, { __index = api })
local function push()
	local code, response = api.global.POST["^/confs$"](self)
	print("PUSH", code, response.msg, "elapsed", clock, "swap calls", swap_calls, "unlocks", unlocks)
	assert(not held, "swap lock leaked")
	return code, response.msg
end
local function lock_available()
	local f = assert(actual_fopen(generating, "re"))
	local result = libc.flock(libc.fileno(f), 6)
	libc.fclose(f)
	return result == 0
end
local function tree()
	local file = assert(real_open(dest .. "/variables.env"))
	local text = file:read("*a")
	file:close()
	return text
end
local function generate(mode)
	assert(real_execute("python3 " .. lane .. "/generator.py " .. mode .. " " .. scratch))
end
local function run()
	write(generating)
	if scenario == "gap" then
		local write_applied = pushswap.write_applied
		pushswap.write_applied = function(...)
			generate("probe")
			return write_applied(...)
		end
		assert(push() == 200)
		local code, message = push()
		print("REPEATED", code, message, "TREE", tree())
		assert(code == 200 and message:find("already applied", 1, true))
		assert(tree() == "push", "already applied acknowledged over a different tree")
		assert(exists(scratch .. "/generator-blocked"), "generator entered between swap and digest write")
	elseif scenario == "sequential" then
		assert(push() == 200)
		assert(pushswap.read_applied("/etc/nginx") == "archive-A")
		generate("production")
		assert(tree() == "SERVER_NAME=new.example.com\n")
		assert(pushswap.read_applied("/etc/nginx") == nil, "generator retained stale push digest")
		local code, message = push()
		assert(code == 200 and not message:find("already applied", 1, true))
		assert(tree() == "push", "identical archive not restored after generation")
	elseif scenario == "raise" or scenario == "failure" then
		local during_write
		pushswap.write_applied = function()
			during_write = held and not lock_available()
			if scenario == "raise" then
				error("injected digest raise")
			end
			return false, "injected digest failure"
		end
		local ran, code = pcall(push)
		print("DIGEST RESULT", ran, code, "swap held", held, "flock available", lock_available())
		assert(ran and code == 200, "digest failure escaped the handler")
		assert(during_write, "both locks must span digest write")
		assert(lock_available(), "generating flock leaked after digest failure")
		local logged = false
		for _, entry in ipairs(logs) do
			if entry:find("cannot record the applied digest for /etc/nginx:", 1, true) then
				logged = true
			end
		end
		assert(logged, "digest failure must keep its existing log line")
	else
		error("unknown scenario")
	end
	assert(lock_available(), "generating flock leaked")
	assert(not held, "swap lock leaked")
	print("PASS", scenario)
end
local ok, failure = pcall(run)
real_execute("rm -rf " .. scratch)
assert(ok, failure)
