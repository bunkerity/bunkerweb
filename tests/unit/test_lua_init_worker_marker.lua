-- Plain Lua check of the worker side of the reload marker (init-worker-lua.conf): the workers of a reload remove the
-- marker once they are up, and only while it still holds the token the master kept for them (init-lua.conf). A marker
-- of another reload, or one found by a worker started with no marker of its own, stays. The removal happens under the
-- ready lock, and only once readiness was published: a failed publication keeps the marker.
-- Run: lua tests/unit/test_lua_init_worker_marker.lua   (from the repo root)
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
local events, logs, on_read = {}, {}, nil
os.remove = function(path)
	if path == MARKER then
		events[#events + 1] = "remove"
	end
	return real_remove(path == MARKER and marker or path)
end
io.open = function(path, mode)
	local file, err = real_open(path == MARKER and marker or path, mode)
	if file and path == MARKER and mode == "r" and on_read then
		-- Runs once the content is read, before the caller acts on it
		local read = file.read
		local close = file.close
		return {
			read = function(_, ...)
				return read(file, ...)
			end,
			close = function()
				local hook = on_read
				on_read = nil
				local res = close(file)
				hook()
				return res
			end,
		}
	end
	return file, err
end

local logger = {
	log = function(_, level, msg)
		logs[#logs + 1] = { level = level, msg = msg }
	end,
}
local variables = { IS_LOADING = "no", TIMERS_LOG_LEVEL = "info" }
local timers, worker = {}, { id = 0 }
package.loaded["bunkerweb.logger"] = {
	new = function()
		return logger
	end,
}
package.loaded["bunkerweb.helpers"] = {}
package.loaded["bunkerweb.utils"] = {
	get_variable = function(name)
		return variables[name]
	end,
}
local ready, locks, fail_set, on_set, on_unlock = {}, {}, false, nil, nil
package.loaded["bunkerweb.datastore"] = {
	new = function()
		return {
			get = function(_, key)
				if key ~= "plugins_order" then
					return ready[key], ready[key] == nil and "not found" or nil
				end
				return { init_workers = {}, init_worker = {}, timer = {} }
			end,
			set = function(_, key, value)
				if on_set then
					local hook = on_set
					on_set = nil
					hook()
				end
				if fail_set then
					return false, "no memory"
				end
				ready[key] = value
				return true
			end,
		}
	end,
}
package.loaded["resty.lock"] = {
	new = function()
		return {
			lock = function(self, key)
				if locks[key] then
					return nil, "timeout"
				end
				locks[key], self.key = true, key
				return 0
			end,
			unlock = function(self)
				locks[self.key] = nil
				events[#events + 1] = "unlock"
				if on_unlock then
					local hook = on_unlock
					on_unlock = nil
					hook()
				end
				return true
			end,
		}
	end,
}
ngx = {
	INFO = 7,
	ERR = 4,
	NOTICE = 6,
	WARN = 5,
	shared = { internalstore = {} },
	config = { subsystem = "http" },
	worker = {
		id = function()
			return worker.id
		end,
		pid = function()
			return 4242
		end,
	},
	timer = {
		at = function(delay, fn)
			timers[#timers + 1] = { delay = delay, fn = fn }
			return true
		end,
	},
}

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

local source
do
	local file = assert(real_open(dir .. "/init-worker-lua.conf", "r"))
	source = file:read("*a")
	file:close()
end
local body = assert(source:match("\ninit_worker_by_lua_block {\n(.*)}%s*$"), "unexpected layout")

-- Starts a worker the way nginx does, with the token its master kept, and runs its ready timer
local function spawn_worker(token, id, loading)
	local saved_token = package.loaded["bunkerweb.reload_marker_token"]
	local saved_timers, saved_id, saved_loading = timers, worker.id, variables.IS_LOADING
	package.loaded["bunkerweb.reload_marker_token"] = token
	timers, worker.id = {}, id or 0
	variables.IS_LOADING = loading and "yes" or "no"
	assert(load(body, "=init-worker-lua.conf"))()
	local ran
	for _, timer in ipairs(timers) do
		if timer.delay == 5 then
			timer.fn(false)
			ran = true
			break
		end
	end
	package.loaded["bunkerweb.reload_marker_token"] = saved_token
	timers, worker.id, variables.IS_LOADING = saved_timers, saved_id, saved_loading
	assert(ran or loading, "the ready timer was never started")
end
local function start_worker(token, id, loading)
	ready, fail_set, on_unlock, on_read, events, logs = {}, false, nil, nil, {}, {}
	locks, on_set = {}, nil
	spawn_worker(token, id, loading)
end
local function index_of(name)
	for i, event in ipairs(events) do
		if event == name then
			return i
		end
	end
end

it("the workers of a reload remove the marker that holds their token", function()
	write_marker("1.111")
	start_worker("1.111")
	assert(read_marker() == nil, "the marker was left behind")
end)

it("a marker of another reload stays", function()
	write_marker("2.222")
	start_worker("1.111")
	assert(read_marker() == "2.222", "the marker of the other reload was removed")
end)

it("a worker started with no marker of its own never removes one", function()
	write_marker("2.222")
	start_worker(false)
	assert(read_marker() == "2.222", "a marker was removed by a worker that had none")
	start_worker(nil)
	assert(read_marker() == "2.222", "a marker was removed by a worker that knows no token")
end)

it("an empty marker stays", function()
	write_marker("")
	start_worker("1.111")
	assert(read_marker() == "")
end)

it("no marker: nothing to remove", function()
	write_marker(nil)
	start_worker("1.111")
	assert(read_marker() == nil)
end)

it("while loading nothing is scheduled, and worker 0 clears the marker of its reload", function()
	write_marker("1.111")
	start_worker("1.111", 1, true)
	assert(read_marker() == "1.111", "a worker other than 0 removed the marker")
	start_worker("1.111", 0, true)
	assert(read_marker() == nil, "the marker of a reload that ended in the loading state was left behind")
	write_marker("2.222")
	start_worker("1.111", 0, true)
	assert(read_marker() == "2.222")
end)

it("the marker is removed while the ready lock is still held", function()
	write_marker("1.111")
	start_worker("1.111")
	assert(read_marker() == nil, "the marker was left behind")
	assert(index_of("remove"), "the marker was never removed")
	assert(index_of("unlock"), "the lock was never released")
	assert(index_of("remove") < index_of("unlock"), "the marker was removed after the lock was released")
end)

it("a failed readiness publication keeps the marker and says so", function()
	write_marker("1.111")
	ready, fail_set, on_unlock, on_read, events, logs = {}, true, nil, nil, {}, {}
	spawn_worker("1.111")
	assert(read_marker() == "1.111", "the marker was removed although readiness was not published")
	assert(not index_of("remove"), "the marker was removed")
	local logged
	for _, line in ipairs(logs) do
		if line.level == ngx.ERR and line.msg:find("keeping", 1, true) then
			logged = true
		end
	end
	assert(logged, "no error saying the marker is kept")
end)

it("failed publication, two workers, a new reload's marker in between: it is never removed", function()
	write_marker("1.111")
	ready, fail_set, events, logs = {}, true, {}, {}
	-- The second worker takes the ready lock as soon as the first one lets it go
	on_unlock = function()
		spawn_worker("1.111", 1)
	end
	-- Whoever reads the old token is overtaken: another reload replaces the marker before the removal
	on_read = function()
		write_marker("2.222")
	end
	spawn_worker("1.111")
	-- With readiness failed nobody reads the marker; the new one only exists if a read happened
	assert(read_marker() ~= nil, "the marker of the new reload was removed")
end)

it("readiness published: one worker removes the marker, the other finds the work done", function()
	write_marker("1.111")
	ready, fail_set, events, logs = {}, false, {}, {}
	on_unlock = function()
		-- the first worker is done: a new reload created its marker, the second worker now runs
		write_marker("2.222")
		spawn_worker("1.111", 1)
	end
	spawn_worker("1.111")
	assert(read_marker() == "2.222", "the second worker removed the marker of the new reload")
end)

for _, old_token in ipairs({ false, "1.111" }) do
	it("late readiness from cycle " .. tostring(old_token) .. " cannot strand the next reload's marker", function()
		write_marker(old_token or nil)
		start_worker(old_token)
		-- The next master's init clears shared misc_ keys while old ready timers are still pending.
		ready = {}
		write_marker("2.222")
		spawn_worker(old_token, 1)
		assert(read_marker() == "2.222", "an old worker removed the next reload's marker")
		spawn_worker("2.222")
		assert(read_marker() == nil, "old readiness made the next reload skip its marker release")
		-- An old worker finishing even later must not erase the new cycle's published readiness.
		spawn_worker(old_token, 2)
		write_marker("3.333")
		events = {}
		spawn_worker("2.222", 1)
		assert(read_marker() == "3.333", "a ready worker removed a foreign marker")
		assert(#events == 1 and events[1] == "unlock", "the ready cycle ran initialization again")
	end)
end

it("a slow old cycle cannot exhaust the next cycle's ready lock wait", function()
	write_marker("1.111")
	start_worker("1.111")
	ready = {}
	write_marker("2.222")
	-- The old timer still holds its lock while the next cycle's timers exhaust their wait.
	on_set = function()
		spawn_worker("2.222")
		spawn_worker("2.222", 1)
	end
	spawn_worker("1.111", 1)
	assert(read_marker() == nil, "all new workers timed out on the old cycle's lock, leaving their marker")
end)

io.open, os.remove = real_open, real_remove
os.execute("rm -rf " .. scratch)
if failures > 0 then
	print(failures .. " failure(s)")
	os.exit(1)
end
print("all passed")
