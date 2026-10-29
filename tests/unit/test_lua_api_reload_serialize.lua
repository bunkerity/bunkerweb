-- Plain Lua check of POST /reload (bunkerweb.api) against the generator's install and against other reloads: the
-- reload creates its marker exclusively before it probes the generating lock (flock, faked here), waits for a marker
-- that is already there instead of sharing it, backs off while a generator installs, never signals nginx in the
-- middle of one or while another reload is in flight, and does not go on when it cannot create its marker or probe
-- the lock.
-- Run: lua tests/unit/test_lua_api_reload_serialize.lua   (from the repo root)
-- API_LUA points the test at another copy of api.lua.
-- luacheck: ignore 122
local root = arg[0]:match("^(.*)/tests/unit/") or "."
local F = dofile(root .. "/tests/unit/lua_lease_fakes.lua")(root)

local failures = 0
local RELOADING, GENERATING = "/var/tmp/bunkerweb/reloading", "/var/tmp/bunkerweb/generating"

-- The two marker files live in a scratch directory
local scratch = os.tmpname()
os.remove(scratch)
assert(os.execute("mkdir -p " .. scratch))
local real_open, real_remove = io.open, os.remove
local function mapped(path)
	if path == RELOADING or path == GENERATING then
		return scratch .. "/" .. path:match("[^/]+$")
	end
	return path
end
local uptime_content = "1000.25 100.00\n"
local refuse_marker_write = false
local on_marker_read
local fail_marker_io = nil -- "fputs" or "fclose": that call fails after the marker was created
io.open = function(path, mode)
	if path == "/proc/uptime" then
		if not uptime_content then
			return nil, "uptime unavailable"
		end
		return {
			read = function()
				return uptime_content
			end,
			close = function() end,
		}
	end
	local file = real_open(mapped(path), mode)
	if file and path == RELOADING and on_marker_read then
		return {
			read = function(_, ...)
				local content, err = file:read(...)
				if content then
					on_marker_read(content)
				end
				return content, err
			end,
			close = function()
				file:close()
			end,
		}
	end
	return file
end
os.remove = function(path)
	return real_remove(mapped(path))
end

local function write(path, content)
	local file = assert(real_open(mapped(path), "w"))
	file:write(content)
	file:close()
end
local function exists(path)
	local file = real_open(mapped(path), "r")
	if file then
		file:close()
	end
	return file ~= nil
end

-- Fake clock: sleeping advances it, and the test can act while the reload waits
local clock, on_sleep = 1000, nil
local marker_mtime = 1000
local real_time = os.time
os.time = function()
	return math.floor(clock)
end
ngx.now = function()
	return clock
end
ngx.sleep = function(seconds)
	clock = clock + seconds
	if on_sleep then
		on_sleep(clock)
	end
end
local request_start = 1000
ngx.req = {
	get_uri_args = function()
		return {}
	end,
	start_time = function()
		return request_start
	end,
}

local signals, nginx_test_ok, hup_during_install, nginx_tests, signal_times = {}, true, false, 0, {}
-- The generating lock is held while its file says so. The api probes it with fopen + flock through LuaJIT's ffi.
local probe_errno, fopen_errno
local held_errno = 11
local last_errno = 0
local function lock_held()
	local file = real_open(mapped(GENERATING), "r")
	if not file then
		return false
	end
	local content = file:read("*a")
	file:close()
	return content == "held"
end
package.loaded["ffi"] = {
	os = "Linux",
	cdef = function() end,
	errno = function()
		return last_errno
	end,
	C = {
		fopen = function(path, mode)
			if path == RELOADING then
				-- O_CREAT | O_EXCL: the marker is created by this call or not at all
				assert(mode == "wxe", "the marker must be created exclusively, not with mode " .. tostring(mode))
				if refuse_marker_write then
					last_errno = 13
					return nil
				end
				if exists(RELOADING) then
					last_errno = 17
					return nil
				end
				write(RELOADING, "")
				return { marker = true, content = "" }
			end
			assert(path == GENERATING and mode == "re", "unexpected fopen " .. tostring(path) .. " " .. tostring(mode))
			if F.on_generating_open then
				local hook = F.on_generating_open
				F.on_generating_open = nil
				hook()
			end
			if fopen_errno then
				last_errno = fopen_errno
				return nil
			end
			if not exists(GENERATING) then
				last_errno = 2
				return nil
			end
			return {}
		end,
		fputs = function(text, file)
			assert(file.marker, "fputs on something that is not the marker")
			if fail_marker_io == "fputs" then
				return -1
			end
			file.content = file.content .. text
			return 1
		end,
		fileno = function()
			return 7
		end,
		fclose = function(file)
			if file and file.marker then
				write(RELOADING, file.content)
				if fail_marker_io == "fclose" then
					return -1
				end
			end
			return 0
		end,
		flock = function(_, operation)
			if operation == 8 then
				return 0
			end
			assert(operation == 5, "the probe must be a shared, non-blocking lock")
			if probe_errno then
				last_errno = probe_errno
				return -1
			end
			if lock_held() then
				last_errno = held_errno
				return -1
			end
			return 0
		end,
	},
}
package.loaded["resty.signal"] = {
	kill = function(_, sig)
		signals[#signals + 1] = sig
		signal_times[#signal_times + 1] = clock
		hup_during_install = hup_during_install or lock_held()
		return true
	end,
}
package.loaded["ngx.process"] = {
	get_master_pid = function()
		return 1
	end,
}
package.loaded["resty.lock"] = {
	new = function()
		return {
			lock = function()
				return 0
			end,
			unlock = function()
				return true
			end,
		}
	end,
}
package.loaded["bit"] = {}
package.loaded["middleclass"] = function(name)
	return { name = name }
end
package.loaded["bunkerweb.helpers"] = {}
package.loaded["bunkerweb.pushswap"] = {}
package.loaded["resty.upload"] = {}
io.popen = function(command)
	if command:find("stat ", 1, true) then
		return {
			read = function()
				return tostring(marker_mtime)
			end,
			close = function() end,
		}
	end
	nginx_tests = nginx_tests + 1
	local output
	if command:find("modsecurity_audit", 1, true) then
		output = "ModSecurity audit preflight successful\n"
	elseif nginx_test_ok then
		output = "nginx: the configuration file /etc/nginx/nginx.conf test is successful\n"
	else
		output = "nginx: [emerg] unknown directive\n"
	end
	return {
		read = function()
			return output
		end,
		close = function() end,
	}
end

local logs = {}
package.loaded["bunkerweb.logger"] = {
	new = function()
		return {
			log = function(_, level, message)
				logs[#logs + 1] = { level, message }
			end,
		}
	end,
}
local api_path = os.getenv("API_LUA")
local api
if api_path then
	api = dofile(api_path)
else
	api = require("bunkerweb.api")
end
local function load_api()
	return dofile(api_path or (root .. "/src/bw/lua/bunkerweb/api.lua"))
end
local self = setmetatable({ ctx = { bw = {} } }, { __index = api })

local function reset()
	clock, on_sleep, nginx_test_ok, hup_during_install, request_start = 1000, nil, true, false, 1000
	fail_marker_io = nil
	marker_mtime = 1000
	uptime_content = "1000.25 100.00\n"
	on_marker_read = nil
	logs = {}
	signals, nginx_tests, refuse_marker_write, probe_errno, fopen_errno, signal_times = {}, 0, false, nil, nil, {}
	os.execute("rm -rf " .. mapped(RELOADING))
	F.on_generating_open = nil
	real_remove(mapped(RELOADING))
	real_remove(mapped(GENERATING))
	F.reset()
end

local function reload(module)
	return (module or api).global.POST["^/reload"](self)
end

local function it(name, fn)
	reset()
	local ok, err = pcall(fn)
	print((ok and "PASS " or "FAIL ") .. name .. (ok and "" or (": " .. tostring(err))))
	if not ok then
		failures = failures + 1
	end
end

local function hold_lock()
	write(GENERATING, "held")
end

it("a reload with no generator signals nginx and leaves the marker for the new workers", function()
	local status = reload()
	assert(status == 200, "status " .. tostring(status))
	assert(#signals == 1 and signals[1] == "HUP", "signals " .. #signals)
	assert(exists(RELOADING), "marker missing")
end)

it("a lock file nobody holds does not hold the reload back", function()
	write(GENERATING, "")
	assert(reload() == 200)
	assert(#signals == 1 and clock == 1000, "waited " .. (clock - 1000) .. "s")
end)

it("a reload waits for a generator that is installing and only then signals nginx", function()
	hold_lock()
	local seen_marker
	on_sleep = function(now)
		seen_marker = (seen_marker or false) or exists(RELOADING)
		assert(#signals == 0, "signalled during the install")
		if now >= 1000.5 then
			write(GENERATING, "")
		end
	end
	local status = reload()
	assert(status == 200, "status " .. tostring(status))
	assert(not hup_during_install, "nginx was signalled while the generator held its lock")
	assert(seen_marker ~= nil, "the reload never waited")
	assert(not seen_marker, "the marker stayed published while the reload backed off")
	assert(#signals == 1, "signals " .. #signals)
	assert(exists(RELOADING), "marker missing")
end)

it("a reload that keeps meeting a generator answers 503 without signalling and without a marker", function()
	hold_lock()
	local status = reload()
	assert(status == 503, "status " .. tostring(status))
	assert(#signals == 0, "signals " .. #signals)
	assert(nginx_tests == 0, "the configuration was tested")
	assert(not exists(RELOADING), "marker left behind")
	assert(clock >= 1002, "gave up after " .. (clock - 1000) .. "s")
end)

it("a generator that takes its lock right after the marker was written is seen", function()
	F.on_generating_open = function()
		hold_lock()
		assert(exists(RELOADING), "the reload had not published its marker before it probed the lock")
	end
	on_sleep = function()
		assert(not exists(RELOADING), "marker published while the generator installs")
		assert(#signals == 0, "signalled during the install")
		write(GENERATING, "")
	end
	local status = reload()
	assert(F.on_generating_open == nil, "the reload never probed the lock")
	assert(status == 200, "status " .. tostring(status))
	assert(not hup_during_install, "nginx was signalled while the generator held its lock")
	assert(#signals == 1, "signals " .. #signals)
end)

it("a marker that cannot be written refuses the reload: no configuration test, no signal", function()
	refuse_marker_write = true
	local status = reload()
	assert(status == 500, "status " .. tostring(status))
	assert(#signals == 0, "nginx was signalled without a marker")
	assert(nginx_tests == 0, "the configuration was tested")
	assert(not exists(RELOADING))
end)

for _, failing in ipairs({ "fputs", "fclose" }) do
	it("a token that cannot be written (" .. failing .. ") takes the marker back and refuses the reload", function()
		fail_marker_io = failing
		local status = reload()
		assert(status == 500, "status " .. tostring(status))
		assert(#signals == 0, "nginx was signalled without a marker")
		assert(nginx_tests == 0, "the configuration was tested")
		assert(not exists(RELOADING), "marker left behind")
		fail_marker_io = nil
		assert(reload() == 200, "the next reload is blocked")
		assert(#signals == 1, "signals " .. #signals)
	end)
end

it("a directory in the marker's place refuses the reload", function()
	assert(os.execute("mkdir " .. mapped(RELOADING)))
	local status = reload()
	assert(status == 500, "status " .. tostring(status))
	assert(#signals == 0, "nginx was signalled without a marker")
	assert(nginx_tests == 0, "the configuration was tested")
	os.execute("rmdir " .. mapped(RELOADING))
end)

it("a lock that cannot be opened refuses the reload and takes the marker back", function()
	fopen_errno = 13
	local status = reload()
	assert(status == 500, "status " .. tostring(status))
	assert(#signals == 0 and nginx_tests == 0)
	assert(not exists(RELOADING), "marker left behind")
end)

it("a lock that cannot be probed refuses the reload and takes the marker back", function()
	write(GENERATING, "")
	probe_errno = 9
	local status = reload()
	assert(status == 500, "status " .. tostring(status))
	assert(#signals == 0 and nginx_tests == 0)
	assert(not exists(RELOADING), "marker left behind")
end)

it("a rejected configuration test removes the marker it published and does not signal", function()
	nginx_test_ok = false
	local status = reload()
	assert(status == 500, "status " .. tostring(status))
	assert(#signals == 0)
	assert(not exists(RELOADING), "marker left behind")
end)

local function marker_content()
	local file = real_open(mapped(RELOADING), "r")
	if not file then
		return nil
	end
	local content = file:read("*a")
	file:close()
	return content
end

it("the marker is created holding a token", function()
	assert(reload() == 200)
	local token = marker_content()
	assert(token and token:match("^%d+%.%d+%.1000$"), "token " .. tostring(token))
end)

it("a reload that finds a marker waits for it to go and does not signal before", function()
	write(RELOADING, "previous.1")
	local gone_at
	on_sleep = function(now)
		assert(#signals == 0, "signalled while the previous reload was in flight")
		assert(nginx_tests == 0, "the configuration was tested while the previous reload was in flight")
		assert(marker_content() == "previous.1", "the marker of the reload in flight was touched")
		if now >= 1002 and not gone_at then
			gone_at = now
			real_remove(mapped(RELOADING))
		end
	end
	local status = reload()
	assert(status == 200, "status " .. tostring(status))
	assert(gone_at, "the reload never waited")
	assert(#signals == 1 and signal_times[1] >= gone_at, "signalled before the marker was gone")
	local token = marker_content()
	assert(token and token ~= "previous.1", "the reload kept the marker of the previous one: " .. tostring(token))
end)

it(
	"a reload never shares the marker: with one already there it answers 503, signals nothing, touches nothing",
	function()
		write(RELOADING, "previous.1")
		local status = reload()
		assert(status == 503, "status " .. tostring(status))
		assert(#signals == 0, "signals " .. #signals)
		assert(nginx_tests == 0, "the configuration was tested")
		assert(marker_content() == "previous.1", "the marker of the reload in flight was removed or replaced")
		assert(clock >= 1004, "gave up after " .. (clock - 1000) .. "s")
		assert(clock < 1004.5, "waited " .. (clock - 1000) .. "s")
	end
)

it("the 503 says what to do when no reload is running", function()
	write(RELOADING, "previous.1")
	local response
	self.response = function(_, status, level, message)
		response = { status, level, message }
		return status
	end
	reload()
	rawset(self, "response", nil)
	assert(response and response[1] == 503, "no 503")
	assert(response[3]:find("a reload is in progress", 1, true), response[3])
	assert(response[3]:find("restart BunkerWeb or remove", 1, true), response[3])
	assert(response[3]:find("cleared automatically once it is older than 5 minutes", 1, true), response[3])
end)

it("the wait counts from the start of the request, not from the end of the swap lock wait", function()
	write(RELOADING, "previous.1")
	request_start = 997
	assert(reload() == 503)
	assert(clock < 1001.5, "waited " .. (clock - 1000) .. "s on top of the 3s spent before")
end)

it("the marker of a reload in flight is still there after a rejected configuration test of the next one", function()
	write(RELOADING, "previous.1")
	nginx_test_ok = false
	assert(reload() == 503)
	assert(marker_content() == "previous.1")
end)

it(
	"a reload that loses the race for the marker while it backs off from a generator waits instead of sharing it",
	function()
		hold_lock()
		local step = 0
		on_sleep = function()
			step = step + 1
			assert(#signals == 0, "signalled with the other reload's marker in place")
			if step == 1 then
				-- the generator is done and another reload has taken the marker in the meantime
				write(GENERATING, "")
				write(RELOADING, "other.2")
			elseif step == 3 then
				real_remove(mapped(RELOADING))
			end
		end
		local status = reload()
		assert(status == 200, "status " .. tostring(status))
		assert(step >= 3, "the reload did not wait")
		assert(#signals == 1)
		assert(marker_content() ~= "other.2")
	end
)

it("two reloads one after the other: the second one signals only once the first one's marker is gone", function()
	assert(reload() == 200)
	local first = marker_content()
	assert(first, "first marker missing")
	local gone_at
	on_sleep = function(now)
		assert(#signals == 1, "second signal while the first reload was in flight")
		if now >= 1003 and not gone_at then
			gone_at = now
			real_remove(mapped(RELOADING))
		end
	end
	assert(reload() == 200)
	assert(#signals == 2 and signal_times[2] >= gone_at, "second HUP before the first marker was gone")
	assert(marker_content() ~= first, "second reload shares the first marker")
end)

it("a stale token is removed, warns once and reloads", function()
	write(RELOADING, "1000.1.699")
	assert(reload() == 200, "stale marker blocked the reload")
	assert(#signals == 1)
	assert(marker_content() ~= "1000.1.699")
	local warnings = 0
	for _, entry in ipairs(logs) do
		if entry[2]:find("orphaned reload marker", 1, true) then
			assert(entry[1] == ngx.WARN)
			warnings = warnings + 1
		end
	end
	assert(warnings == 1, "warnings " .. warnings)
end)

for _, token in ipairs({ "990.1.990", "1060.1.1060", "700.1.700" }) do
	it("a fresh, future or boundary token stays: " .. token, function()
		write(RELOADING, token)
		marker_mtime = 1
		-- Keep the boundary exactly 300 seconds old while the wait deadline expires.
		if token == "700.1.700" then
			request_start = 996
		end
		assert(reload() == 503)
		assert(#signals == 0)
		assert(marker_content() == token)
	end)
end

it("a wall clock step of 600 seconds keeps a one second old marker", function()
	clock, request_start = 1600, 1600
	write(RELOADING, "1000.1.999")
	assert(reload() == 503)
	assert(#signals == 0)
	assert(marker_content() == "1000.1.999")
end)

for _, token in ipairs({ "699.1", "", "garbled", "1.1.bad", "1.1.1.1", "1.1.1\n" }) do
	it("a legacy or unparsable token stays despite its old mtime: " .. token, function()
		write(RELOADING, token)
		marker_mtime = 1
		assert(reload() == 503)
		assert(#signals == 0)
		assert(marker_content() == token)
	end)
end

for _, content in ipairs({ false, "", "invalid" }) do
	it("an unavailable or malformed uptime keeps the marker: " .. tostring(content), function()
		uptime_content = content
		write(RELOADING, "1.1.1")
		assert(reload() == 503)
		assert(#signals == 0)
		assert(marker_content() == "1.1.1")
	end)
end

it("an unavailable uptime writes a legacy token", function()
	uptime_content = false
	assert(reload() == 200)
	assert(marker_content():match("^%d+%.%d+$"), marker_content())
end)

it("a token replaced after the stale read is kept", function()
	write(RELOADING, "1000.1.699")
	on_marker_read = function(content)
		if content == "1000.1.699" then
			write(RELOADING, "1000.2.1000")
		end
	end
	assert(reload() == 503)
	assert(#signals == 0)
	assert(marker_content() == "1000.2.1000", "fresh replacement was removed")
end)

-- EWOULDBLOCK is 35 on the BSDs and macOS: the module reads ffi.os when it loads
it("on BSD a lock held by the generator (errno 35) is seen as a running generator", function()
	package.loaded["ffi"].os = "BSD"
	local ok, bsd_api = pcall(load_api)
	package.loaded["ffi"].os, held_errno = "Linux", 35
	assert(ok, bsd_api)
	hold_lock()
	local status = reload(bsd_api)
	held_errno = 11
	assert(status == 503, "status " .. tostring(status))
	assert(#signals == 0, "signalled during the install")
	assert(not exists(RELOADING), "marker left behind")
end)

io.open, os.remove, os.time = real_open, real_remove, real_time
os.execute("rm -rf " .. scratch)
if failures > 0 then
	print(failures .. " failure(s)")
	os.exit(1)
end
print("all passed")
