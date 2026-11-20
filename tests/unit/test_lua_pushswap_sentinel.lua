-- Plain Lua check of bunkerweb.pushswap.swap against an interrupted push: while /etc/nginx is being swapped the
-- destination carries the install sentinel, a push cut short leaves it, a complete one (or a rollback that put the old
-- tree back) clears it, and the sentinel inside a pushed archive is never placed.
-- Run: lua tests/unit/test_lua_pushswap_sentinel.lua   (from the repo root)
-- PUSHSWAP_LUA points the test at another copy of pushswap.lua.
-- luacheck: ignore 122
local root = arg[0]:match("^(.*)/tests/unit/") or "."
local path = os.getenv("PUSHSWAP_LUA") or (root .. "/src/bw/lua/bunkerweb/pushswap.lua")
local SENTINEL = ".bw-install-incomplete"

package.loaded["resty.sha256"] = {
	new = function()
		return {}
	end,
}
package.loaded["resty.string"] = {
	to_hex = function(s)
		return s
	end,
}

-- rename and execute are captured by pushswap when it loads, so the fakes go in before the load
local real_rename, real_execute = os.rename, os.execute
local renames, fail_from, fail_only, crash_at, block_cp, on_rename = 0, nil, nil, nil, false, nil
os.rename = function(from, to)
	renames = renames + 1
	if on_rename then
		on_rename()
	end
	if fail_only and renames == fail_only then
		return nil, "boom"
	end
	if crash_at and renames == crash_at then
		error("killed")
	end
	if fail_from and renames >= fail_from then
		return nil, "boom"
	end
	return real_rename(from, to)
end
os.execute = function(cmd)
	if block_cp and cmd:find("^cp %-a") then
		return false
	end
	return real_execute(cmd)
end
local pushswap = dofile(path)

local scratch = os.tmpname()
os.remove(scratch)
assert(real_execute("mkdir -p " .. scratch))
pushswap.STATE_ROOT = scratch .. "/state"

local function write(file, text)
	local fh = assert(io.open(file, "w"))
	fh:write(text)
	fh:close()
end
local function exists(file)
	local fh = io.open(file, "r")
	if fh then
		fh:close()
	end
	return fh ~= nil
end
local function read(file)
	local fh = io.open(file, "r")
	if not fh then
		return nil
	end
	local text = fh:read("*a")
	fh:close()
	return text
end

local failures = 0
local function check(name, cond)
	if cond then
		print("ok   " .. name)
	else
		print("FAIL " .. name)
		failures = failures + 1
	end
end

-- destination with an old generation, staging with a new one that also carries the sentinel and a stale entry
local function setup(name, old_sentinel)
	local dest = scratch .. "/" .. name
	local staging = dest .. "/.bw-staging.1"
	assert(real_execute("mkdir -p " .. dest .. "/http " .. staging .. "/http"))
	write(dest .. "/variables.env", "old\n")
	write(dest .. "/http/a.conf", "old\n")
	write(dest .. "/gone.conf", "old\n")
	write(staging .. "/variables.env", "new\n")
	write(staging .. "/http/a.conf", "new\n")
	write(staging .. "/" .. SENTINEL, "from archive\n")
	if old_sentinel then
		write(dest .. "/" .. SENTINEL, "")
	end
	pushswap.SENTINEL_DESTINATION = dest
	renames, fail_from, fail_only, crash_at, block_cp, on_rename = 0, nil, nil, nil, false, nil
	return dest, staging
end

-- a complete push
do
	local dest, staging = setup("complete")
	local ok = pushswap.swap(dest, staging)
	check("complete push succeeds", ok == true)
	check(
		"complete push installs the new generation",
		read(dest .. "/variables.env") == "new\n" and not exists(dest .. "/gone.conf")
	)
	check("complete push leaves no sentinel", not exists(dest .. "/" .. SENTINEL))
end

-- a stale sentinel from an earlier cut-short install does not survive a complete push
do
	local dest, staging = setup("stale", true)
	pushswap.swap(dest, staging)
	check("complete push clears a stale sentinel", not exists(dest .. "/" .. SENTINEL))
end

-- the sentinel is in place before the first move
do
	local dest, staging = setup("early")
	local seen
	on_rename = function()
		if seen == nil then
			seen = exists(dest .. "/" .. SENTINEL)
		end
	end
	pushswap.swap(dest, staging)
	check("sentinel exists before the first rename", seen == true)
end

-- a push killed in the middle (a rename that raises) leaves it, and the pushed one is never taken from the archive
do
	local dest, staging = setup("killed")
	crash_at = 3
	local ran = pcall(pushswap.swap, dest, staging)
	check("killed push raised", ran == false)
	check("killed push leaves the sentinel", exists(dest .. "/" .. SENTINEL))
	check("killed push leaves the sentinel empty of archive content", read(dest .. "/" .. SENTINEL) == "")
end

-- a placement that fails with a complete rollback: old tree is back, the sentinel this push created goes
do
	local dest, staging = setup("rollback")
	fail_only, block_cp = 3, true -- the 3rd rename is a placement; the rollback renames succeed
	local ok = pushswap.swap(dest, staging)
	check("failed placement reports failure", ok == false)
	check(
		"complete rollback restored the old tree",
		read(dest .. "/variables.env") == "old\n"
			and read(dest .. "/http/a.conf") == "old\n"
			and exists(dest .. "/gone.conf")
	)
	check("complete rollback removes the sentinel it created", not exists(dest .. "/" .. SENTINEL))
end

-- complete rollback keeps a sentinel that was there before the push
do
	local dest, staging = setup("rollback_stale", true)
	fail_only, block_cp = 3, true
	pushswap.swap(dest, staging)
	check("complete rollback keeps a sentinel that predates the push", exists(dest .. "/" .. SENTINEL))
end

-- a rollback that cannot put everything back leaves it
do
	local dest, staging = setup("stuck")
	fail_from, block_cp = 3, true
	local ok = pushswap.swap(dest, staging)
	check("stuck rollback reports failure", ok == false)
	check("stuck rollback leaves the sentinel", exists(dest .. "/" .. SENTINEL))
end

-- any other destination is untouched by the mechanism
do
	local dest, staging = setup("other")
	pushswap.SENTINEL_DESTINATION = "/etc/nginx"
	crash_at = 3
	pcall(pushswap.swap, dest, staging)
	check("other destinations get no sentinel", not exists(dest .. "/" .. SENTINEL))
end

real_execute("rm -rf " .. scratch)
print(string.format("failures=%d", failures))
os.exit(failures == 0 and 0 or 1)
