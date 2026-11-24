-- Plain Lua check of bunkerweb.pushswap.swap on a push that changes nothing (BW-2450). On Linux and all-in-one the
-- archived source and the destination are the same directory, so an unchanged custom configs push used to park every
-- top-level entry with rename(2), which fails on a directory the instance user cannot write (mode 0550 here).
-- An entry whose staged copy is identical must be left alone: same inode, same mode, nothing parked. A changed entry
-- is still swapped in atomically, and a failed swap still rolls back.
-- The shortcut is opt-in (options.skip_unchanged, passed for POST /custom_configs only) and exact: same paths, same
-- entry types, same permission bits on every directory and regular file, same symlink target text, same bytes. A push
-- that only changes a mode (the scheduler restoring its failover copy) is applied. Anything unprovable falls back to
-- the swap.
-- Run: lua tests/unit/test_lua_pushswap_unchanged.lua   (from the repo root)
-- PUSHSWAP_LUA points the test at another copy of pushswap.lua.
-- luacheck: ignore 122
local root = arg[0]:match("^(.*)/tests/unit/") or "."
local path = os.getenv("PUSHSWAP_LUA") or (root .. "/src/bw/lua/bunkerweb/pushswap.lua")

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

local real_execute = os.execute
local function sh(cmd)
	local ok = real_execute(cmd)
	return ok == true or ok == 0
end
local function capture(cmd)
	local pipe = assert(io.popen(cmd))
	local out = pipe:read("*a")
	pipe:close()
	return (out:gsub("%s+$", ""))
end

if capture("id -u") == "0" then
	print("skip root bypasses directory permissions, run as an unprivileged user")
	os.exit(0)
end

local pushswap = dofile(path)
local SKIP = { skip_unchanged = true }

local scratch = capture("mktemp -d")
pushswap.STATE_ROOT = scratch .. "/state"

local function write(file, text)
	local fh = assert(io.open(file, "w"))
	fh:write(text)
	fh:close()
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
local function exists(file)
	return sh("test -e '" .. file .. "'")
end
local function stat(file)
	return capture("stat -c '%i %a' '" .. file .. "'")
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

-- Destination and staging hold the same two generations of a custom configs tree. modsec-crs is the entry the
-- instance user cannot write, the way a root:nginx 750 directory looks to it.
local function setup(name, staged_http)
	local dest = scratch .. "/" .. name
	local staging = dest .. "/.bw-staging.1"
	assert(
		sh("mkdir -p " .. dest .. "/modsec-crs " .. dest .. "/http " .. staging .. "/modsec-crs " .. staging .. "/http")
	)
	write(dest .. "/modsec-crs/arrules.conf", 'SecRule ARGS "@rx x" "id:1,pass"\n')
	write(dest .. "/http/a.conf", "old\n")
	write(staging .. "/modsec-crs/arrules.conf", 'SecRule ARGS "@rx x" "id:1,pass"\n')
	write(staging .. "/http/a.conf", staged_http or "old\n")
	-- The staged copy carries the modes the archive had, which for an unchanged tree are the destination's own.
	assert(sh("chmod 0550 " .. dest .. "/modsec-crs " .. staging .. "/modsec-crs"))
	return dest, staging
end

local function finish(dest)
	sh("chmod -R u+w '" .. dest .. "'")
end

-- an unchanged self-push touches nothing, a read-only directory included
do
	local dest, staging = setup("unchanged")
	local before = stat(dest .. "/modsec-crs")
	local ok, err = pushswap.swap(dest, staging, SKIP)
	check("unchanged push succeeds on a non-writable directory", ok == true)
	if not ok then
		print("     " .. tostring(err))
	end
	check("the non-writable directory keeps its inode and mode", stat(dest .. "/modsec-crs") == before)
	check("the non-writable directory keeps its content", read(dest .. "/modsec-crs/arrules.conf") ~= nil)
	check("the writable entry keeps its content", read(dest .. "/http/a.conf") == "old\n")
	check("staging is cleaned up", not exists(staging))
	check("trash is cleaned up", not exists(dest .. "/.bw-trash"))
	finish(dest)
end

-- a changed entry is still swapped in while the unchanged non-writable one is left alone
do
	local dest, staging = setup("changed", "new\n")
	local before = stat(dest .. "/modsec-crs")
	local ok, err = pushswap.swap(dest, staging, SKIP)
	check("a changed entry is swapped in", ok == true and read(dest .. "/http/a.conf") == "new\n")
	if not ok then
		print("     " .. tostring(err))
	end
	check("the unchanged non-writable entry is left alone", stat(dest .. "/modsec-crs") == before)
	check("no staging or trash left", not exists(staging) and not exists(dest .. "/.bw-trash"))
	finish(dest)
end

-- a new entry is placed and a stale one still swept
do
	local dest, staging = setup("shape")
	assert(sh("mkdir -p " .. staging .. "/server-http"))
	write(staging .. "/server-http/b.conf", "fresh\n")
	write(dest .. "/stale.conf", "stale\n")
	local ok = pushswap.swap(dest, staging, SKIP)
	check("a new entry is placed", ok == true and read(dest .. "/server-http/b.conf") == "fresh\n")
	check("an entry missing from the push is still swept", not exists(dest .. "/stale.conf"))
	finish(dest)
end

-- an entry that really changed inside a directory the user cannot write is still refused and rolled back
do
	local dest, staging = setup("refused")
	write(staging .. "/modsec-crs/arrules.conf", "changed\n")
	local ok, err = pushswap.swap(dest, staging, SKIP)
	check(
		"a real change in a non-writable directory is refused",
		ok == false and tostring(err):find("cannot park modsec%-crs") ~= nil
	)
	check(
		"the refused push leaves the old content",
		read(dest .. "/modsec-crs/arrules.conf") == 'SecRule ARGS "@rx x" "id:1,pass"\n'
	)
	finish(dest)
end

-- same names, different file types, extra or missing files are all changes
do
	local dest, staging = setup("shapes")
	assert(sh("chmod 0750 " .. dest .. "/modsec-crs " .. staging .. "/modsec-crs"))
	write(staging .. "/modsec-crs/extra.conf", "extra\n")
	local ok = pushswap.swap(dest, staging, SKIP)
	check("an added file is a change", ok == true and read(dest .. "/modsec-crs/extra.conf") == "extra\n")
	finish(dest)
end

-- the same push without the option (/plugins, /pro_plugins, /confs, /cache) is the old swap: it parks the entry
do
	local dest, staging = setup("scope")
	local ok, err = pushswap.swap(dest, staging)
	check("without the option an unchanged push still parks every entry", ok == false)
	check("without the option the failure is the old one", tostring(err):find("cannot park modsec%-crs") ~= nil)
	finish(dest)
end

-- a mode-only change is applied with and without the option: the shortcut compares permission bits too
do
	local dest = scratch .. "/mode"
	local staging = dest .. "/.bw-staging.1"
	assert(sh("mkdir -p " .. staging))
	write(dest .. "/hook.sh", "echo hi\n")
	write(staging .. "/hook.sh", "echo hi\n")
	assert(sh("chmod 0644 " .. dest .. "/hook.sh && chmod 0755 " .. staging .. "/hook.sh"))
	local ok = pushswap.swap(dest, staging)
	check(
		"a mode-only change is applied without the option",
		ok == true and capture("stat -c %a '" .. dest .. "/hook.sh'") == "755"
	)
	assert(sh("mkdir -p " .. staging))
	write(staging .. "/hook.sh", "echo hi\n")
	assert(sh("chmod 0600 " .. staging .. "/hook.sh"))
	ok = pushswap.swap(dest, staging, SKIP)
	check(
		"a mode-only change is applied with the option",
		ok == true and capture("stat -c %a '" .. dest .. "/hook.sh'") == "600"
	)
	-- same content and same mode is the shortcut: the inode stays
	assert(sh("mkdir -p " .. staging))
	write(staging .. "/hook.sh", "echo hi\n")
	assert(sh("chmod 0600 " .. staging .. "/hook.sh"))
	local inode = capture("stat -c %i '" .. dest .. "/hook.sh'")
	ok = pushswap.swap(dest, staging, SKIP)
	check(
		"the same content and the same mode is left alone",
		ok == true and capture("stat -c '%i %a' '" .. dest .. "/hook.sh'") == inode .. " 600"
	)
	finish(dest)
end

-- the client case: a 750 directory and a 640 file that come back unchanged keep their inode and mode
do
	local dest = scratch .. "/client"
	local staging = dest .. "/.bw-staging.1"
	assert(sh("mkdir -p " .. dest .. "/server-http " .. staging .. "/server-http"))
	write(dest .. "/server-http/probe.conf", "x\n")
	write(staging .. "/server-http/probe.conf", "x\n")
	assert(sh("chmod 0750 " .. dest .. "/server-http " .. staging .. "/server-http"))
	assert(sh("chmod 0640 " .. dest .. "/server-http/probe.conf " .. staging .. "/server-http/probe.conf"))
	local before = stat(dest .. "/server-http") .. " " .. stat(dest .. "/server-http/probe.conf")
	local ok = pushswap.swap(dest, staging, SKIP)
	check(
		"a 750 directory with a 640 file, unchanged, is left alone",
		ok == true and stat(dest .. "/server-http") .. " " .. stat(dest .. "/server-http/probe.conf") == before
	)
	finish(dest)
end

-- a directory mode that differs is a change at any depth, special bits included
do
	local dest = scratch .. "/dirmode"
	local staging = dest .. "/.bw-staging.1"
	assert(sh("mkdir -p " .. dest .. "/d/sub " .. staging .. "/d/sub"))
	write(dest .. "/d/sub/f.conf", "x\n")
	write(staging .. "/d/sub/f.conf", "x\n")
	assert(sh("chmod 0755 " .. dest .. "/d/sub && chmod 0750 " .. staging .. "/d/sub"))
	local ok = pushswap.swap(dest, staging, SKIP)
	check(
		"a nested directory mode change is applied",
		ok == true and capture("stat -c %a '" .. dest .. "/d/sub'") == "750"
	)
	assert(sh("mkdir -p " .. staging .. "/d/sub"))
	write(staging .. "/d/sub/f.conf", "x\n")
	assert(sh("chmod 2750 " .. staging .. "/d/sub"))
	ok = pushswap.swap(dest, staging, SKIP)
	check("a setgid bit is a mode change", ok == true and capture("stat -c %a '" .. dest .. "/d/sub'") == "2750")
	finish(dest)
end

-- a symlink and a regular file with the same content are a change, in both directions
do
	local dest = scratch .. "/link"
	local staging = dest .. "/.bw-staging.1"
	assert(sh("mkdir -p " .. staging))
	write(dest .. "/real.conf", "same\n")
	write(dest .. "/a.conf", "same\n")
	assert(sh("ln -s real.conf " .. staging .. "/a.conf && cp " .. dest .. "/real.conf " .. staging .. "/real.conf"))
	local ok = pushswap.swap(dest, staging, SKIP)
	check(
		"a symlink staged over a regular file with the same content is a change",
		ok == true and capture("test -L '" .. dest .. "/a.conf' && echo link") == "link"
	)
	assert(sh("mkdir -p " .. staging))
	write(staging .. "/a.conf", "same\n")
	write(staging .. "/real.conf", "same\n")
	ok = pushswap.swap(dest, staging, SKIP)
	check(
		"a regular file staged over a symlink with the same content is a change",
		ok == true and capture("test -L '" .. dest .. "/a.conf' || echo file") == "file"
	)
	finish(dest)
end

-- a symlink with another target is a change, a symlink with the same target is not, nested or not
do
	local dest = scratch .. "/target"
	local staging = dest .. "/.bw-staging.1"
	assert(sh("mkdir -p " .. staging .. " " .. dest .. "/d " .. staging .. "/d"))
	write(dest .. "/one.conf", "x\n")
	write(dest .. "/two.conf", "x\n")
	assert(sh("cp " .. dest .. "/one.conf " .. dest .. "/two.conf " .. staging .. "/"))
	assert(sh("ln -s one.conf " .. dest .. "/l.conf && ln -s two.conf " .. staging .. "/l.conf"))
	assert(sh("ln -s one.conf " .. dest .. "/d/n.conf && ln -s one.conf " .. staging .. "/d/n.conf"))
	local before = stat(dest .. "/d")
	local ok = pushswap.swap(dest, staging, SKIP)
	check(
		"a symlink with another target is a change",
		ok == true and capture("readlink '" .. dest .. "/l.conf'") == "two.conf"
	)
	check("a nested symlink with the same target is left alone", stat(dest .. "/d") == before)
	finish(dest)
end

-- anything that cannot be proven identical falls back to the swap: an unreadable file ...
do
	local dest = scratch .. "/unreadable"
	local staging = dest .. "/.bw-staging.1"
	assert(sh("mkdir -p " .. staging))
	write(dest .. "/u.conf", "same\n")
	write(staging .. "/u.conf", "same\n")
	assert(sh("chmod 0000 " .. dest .. "/u.conf"))
	local inode = capture("stat -c %i '" .. dest .. "/u.conf'")
	local ok = pushswap.swap(dest, staging, SKIP)
	check(
		"an unreadable file is not proven identical and is swapped",
		ok == true and capture("stat -c %i '" .. dest .. "/u.conf'") ~= inode and read(dest .. "/u.conf") == "same\n"
	)
	finish(dest)
end

-- ... and a missing tool: a copy of the module whose popen has no readlink cannot read a symlink target
do
	local real_popen = io.popen
	io.popen = function(cmd, mode)
		return real_popen((cmd:gsub("readlink", "readlink-not-installed")), mode)
	end
	local blind = dofile(path)
	io.popen = real_popen
	blind.STATE_ROOT = scratch .. "/state"
	local dest = scratch .. "/notool"
	local staging = dest .. "/.bw-staging.1"
	assert(sh("mkdir -p " .. staging))
	assert(sh("ln -s elsewhere " .. dest .. "/s.conf && ln -s elsewhere " .. staging .. "/s.conf"))
	local inode = capture("stat -c %i '" .. dest .. "/s.conf'")
	local ok = blind.swap(dest, staging, SKIP)
	check(
		"a missing tool is not proof of equality and the entry is swapped",
		ok == true and capture("stat -c %i '" .. dest .. "/s.conf'") ~= inode
	)
	finish(dest)
end

-- ... and a missing stat: the permission bits cannot be read, so nothing is proven
do
	local real_popen = io.popen
	io.popen = function(cmd, mode)
		return real_popen((cmd:gsub("stat %-c", "stat-not-installed -c")), mode)
	end
	local blind = dofile(path)
	io.popen = real_popen
	blind.STATE_ROOT = scratch .. "/state"
	local dest = scratch .. "/nostat"
	local staging = dest .. "/.bw-staging.1"
	assert(sh("mkdir -p " .. staging))
	write(dest .. "/s.conf", "same\n")
	write(staging .. "/s.conf", "same\n")
	assert(sh("chmod 0640 " .. dest .. "/s.conf " .. staging .. "/s.conf"))
	local inode = capture("stat -c %i '" .. dest .. "/s.conf'")
	local ok = blind.swap(dest, staging, SKIP)
	check(
		"a missing stat is not proof of equality and the entry is swapped",
		ok == true and capture("stat -c %i '" .. dest .. "/s.conf'") ~= inode
	)
	finish(dest)
end

-- where the shortcut is allowed: POST /custom_configs from the loopback peer of an instance that shares its configs
-- folder with the scheduler (Linux, or Docker with the scheduler installed, which is the all-in-one image)
do
	local allowed = pushswap.is_local_self_push
	local uri, linux, docker = "/custom_configs", "Linux", "Docker"
	check("loopback IPv4 on Linux is local", allowed(uri, linux, true, "127.0.0.1") == true)
	check("loopback IPv4 in the whole 127/8 is local", allowed(uri, linux, true, "127.255.255.254") == true)
	check("loopback IPv6 is local", allowed(uri, linux, true, "::1") == true)
	check("IPv4-mapped loopback is local", allowed(uri, docker, true, "::ffff:127.0.0.1") == true)
	for _, peer in ipairs({
		"10.0.0.2",
		"172.17.0.3",
		"192.168.1.2",
		"::2",
		"fe80::1",
		"127.0.0.256",
		"127.0.0.1.5",
		"",
	}) do
		check("peer '" .. peer .. "' is not local", allowed(uri, linux, true, peer) == false)
	end
	check("no peer is not local", allowed(uri, linux, true, nil) == false)
	check("other integrations are not local", allowed(uri, "Kubernetes", true, "127.0.0.1") == false)
	check("autoconf is not local", allowed(uri, "autoconf", true, "127.0.0.1") == false)
	check(
		"docker without the scheduler (bunkerweb image) is not local",
		allowed(uri, docker, false, "127.0.0.1") == false
	)
	check("other push URIs are not local", allowed("/plugins", linux, true, "127.0.0.1") == false)
	check("/confs is not local", allowed("/confs", linux, true, "127.0.0.1") == false)
end

-- the push as the API runs it: the options come from the verdict above
local function push(dest, staging, uri, integration, scheduler, peer)
	return pushswap.swap(
		dest,
		staging,
		{ skip_unchanged = pushswap.is_local_self_push(uri, integration, scheduler, peer) }
	)
end

-- an unchanged tree from a remote peer is swapped like any push, a non-writable directory included
do
	local dest, staging = setup("remote")
	local ok, err = push(dest, staging, "/custom_configs", "Linux", true, "10.0.0.2")
	check(
		"a remote peer gets the swap, not the shortcut",
		ok == false and tostring(err):find("cannot park modsec%-crs") ~= nil
	)
	finish(dest)
end

-- loopback on an integration that does not share the folder is swapped too
do
	local dest, staging = setup("kube")
	local ok, err = push(dest, staging, "/custom_configs", "Kubernetes", true, "127.0.0.1")
	check("loopback on Kubernetes gets the swap", ok == false and tostring(err):find("cannot park modsec%-crs") ~= nil)
	finish(dest)
	dest, staging = setup("image")
	ok, err = push(dest, staging, "/custom_configs", "Docker", false, "127.0.0.1")
	check(
		"loopback on the bunkerweb image gets the swap",
		ok == false and tostring(err):find("cannot park modsec%-crs") ~= nil
	)
	finish(dest)
end

-- loopback on a shared folder leaves the unchanged non-writable directory alone
do
	local dest, staging = setup("selfpush")
	local before = stat(dest .. "/modsec-crs")
	local ok, err = push(dest, staging, "/custom_configs", "Linux", true, "127.0.0.1")
	check("a verified local self-push succeeds on a non-writable directory", ok == true)
	if not ok then
		print("     " .. tostring(err))
	end
	check("the directory is untouched", stat(dest .. "/modsec-crs") == before)
	finish(dest)
end

-- a permission-only change is applied from a remote peer and from the local scheduler alike
do
	local dest = scratch .. "/permonly"
	local staging = dest .. "/.bw-staging.1"
	assert(sh("mkdir -p " .. staging))
	write(dest .. "/hook.conf", "same\n")
	write(staging .. "/hook.conf", "same\n")
	assert(sh("chmod 0644 " .. dest .. "/hook.conf && chmod 0755 " .. staging .. "/hook.conf"))
	local ok = push(dest, staging, "/custom_configs", "Linux", true, "192.168.1.10")
	check(
		"a permission-only change from a remote peer is applied",
		ok == true and capture("stat -c %a '" .. dest .. "/hook.conf'") == "755"
	)
	assert(sh("mkdir -p " .. staging))
	write(staging .. "/hook.conf", "same\n")
	assert(sh("chmod 0640 " .. staging .. "/hook.conf"))
	ok = push(dest, staging, "/custom_configs", "Linux", true, "127.0.0.1")
	check(
		"a permission-only change from the local scheduler is applied",
		ok == true and capture("stat -c %a '" .. dest .. "/hook.conf'") == "640"
	)
	finish(dest)
end

-- failover: scheduler/main.py sends its backup copy of /etc/bunkerweb/configs (copytree of the same tree, taken after
-- the last good reload) to POST /custom_configs over loopback, through the same archive builder. When only a mode was
-- changed since, the tree is the same and the push must still restore the modes.
do
	local dest = scratch .. "/failover"
	local staging = dest .. "/.bw-staging.1"
	assert(
		sh(
			"mkdir -p "
				.. dest
				.. "/server-http "
				.. dest
				.. "/http "
				.. staging
				.. "/server-http "
				.. staging
				.. "/http"
		)
	)
	for _, d in ipairs({ dest, staging }) do
		write(d .. "/server-http/probe.conf", "x\n")
		write(d .. "/http/a.conf", "y\n")
	end
	-- the live tree was loosened after the backup was taken, the backup holds the working 750/640 modes
	assert(sh("chmod 0755 " .. dest .. "/server-http && chmod 0644 " .. dest .. "/server-http/probe.conf"))
	assert(sh("chmod 0750 " .. staging .. "/server-http && chmod 0640 " .. staging .. "/server-http/probe.conf"))
	assert(
		sh(
			"chmod 0750 "
				.. dest
				.. "/http "
				.. staging
				.. "/http && chmod 0640 "
				.. dest
				.. "/http/a.conf "
				.. staging
				.. "/http/a.conf"
		)
	)
	local kept = stat(dest .. "/http")
	local ok, err = push(dest, staging, "/custom_configs", "Linux", true, "127.0.0.1")
	check("a failover push over loopback succeeds", ok == true)
	if not ok then
		print("     " .. tostring(err))
	end
	check(
		"a failover push restores the directory and file modes",
		capture("stat -c %a '" .. dest .. "/server-http'") == "750"
			and capture("stat -c %a '" .. dest .. "/server-http/probe.conf'") == "640"
	)
	check("the entry whose modes already match is left alone", stat(dest .. "/http") == kept)
	check("a failover push leaves no staging or trash", not exists(staging) and not exists(dest .. "/.bw-trash"))
	finish(dest)
end

-- two reads that fail are not two equal files: a handle whose read answers nil plus a message is an error, not the end
do
	local real_io_open = io.open
	local function failing(pattern)
		io.open = function(file, mode)
			local fh, err = real_io_open(file, mode)
			if fh and mode == "rb" and file:find(pattern) then
				return {
					read = function()
						return nil, "Input/output error"
					end,
					close = function()
						fh:close()
					end,
				}
			end
			return fh, err
		end
		local copy = dofile(path)
		io.open = real_io_open
		copy.STATE_ROOT = scratch .. "/state"
		return copy
	end
	for name, pattern in pairs({ ["both"] = "%.conf$", ["destination only"] = "/readerr%-dest/[^/]*%.conf$" }) do
		local broken = failing(pattern)
		local dest = scratch .. "/readerr-" .. (name == "both" and "both" or "dest")
		local staging = dest .. "/.bw-staging.1"
		assert(sh("mkdir -p " .. staging))
		write(dest .. "/r.conf", "same\n")
		write(staging .. "/r.conf", "same\n")
		local inode = capture("stat -c %i '" .. dest .. "/r.conf'")
		local ok = broken.swap(dest, staging, SKIP)
		check(
			"a read error on " .. name .. " is a change and the entry is swapped",
			ok == true and capture("stat -c %i '" .. dest .. "/r.conf'") ~= inode
		)
		finish(dest)
	end
end

-- file names that differ only by where a newline sits are different trees
do
	local dest = scratch .. "/newline"
	local staging = dest .. "/.bw-staging.1"
	assert(sh("mkdir -p " .. dest .. "/d " .. staging .. "/d"))
	for _, name in ipairs({ "a", "b", "a\nb" }) do
		write(dest .. "/d/" .. name, "x\n")
	end
	for _, name in ipairs({ "a", "b", "b\na" }) do
		write(staging .. "/d/" .. name, "x\n")
	end
	local ok = pushswap.swap(dest, staging, SKIP)
	check(
		"{a, b, 'a\\nb'} against {a, b, 'b\\na'} is a change",
		ok == true and exists(dest .. "/d/b\na") and not exists(dest .. "/d/a\nb")
	)
	-- the same names with a newline in them are equal to themselves
	assert(sh("mkdir -p " .. staging .. "/d"))
	for _, name in ipairs({ "a", "b", "b\na" }) do
		write(staging .. "/d/" .. name, "x\n")
	end
	local before = stat(dest .. "/d")
	ok = pushswap.swap(dest, staging, SKIP)
	check("identical names with a newline in one are unchanged", ok == true and stat(dest .. "/d") == before)
	finish(dest)
end

-- a hidden file and a dot-dot name are listed, so a file missing on one side is seen
do
	local dest = scratch .. "/hidden"
	local staging = dest .. "/.bw-staging.1"
	assert(sh("mkdir -p " .. dest .. "/d " .. staging .. "/d"))
	write(dest .. "/d/.hidden", "x\n")
	write(dest .. "/d/..odd", "x\n")
	write(staging .. "/d/.hidden", "x\n")
	local ok = pushswap.swap(dest, staging, SKIP)
	check(
		"a missing '..odd' name is a change",
		ok == true and exists(dest .. "/d/.hidden") and not exists(dest .. "/d/..odd")
	)
	finish(dest)
end

-- cleaning staging changes directory modes only: a staged file in a skipped entry that is a hard link to a published
-- file shares its inode, and its mode must not move
do
	local dest, staging = setup("hardlink")
	assert(sh("chmod 0640 " .. dest .. "/modsec-crs/arrules.conf"))
	-- the staged copy is the published inode itself, in a skipped entry (0550 directory, same bytes, same mode)
	assert(sh("chmod 0750 " .. staging .. "/modsec-crs"))
	assert(sh("rm " .. staging .. "/modsec-crs/arrules.conf"))
	assert(sh("ln " .. dest .. "/modsec-crs/arrules.conf " .. staging .. "/modsec-crs/arrules.conf"))
	assert(sh("chmod 0550 " .. staging .. "/modsec-crs"))
	local ok = pushswap.swap(dest, staging, SKIP)
	check("a hard-linked staged file: swap succeeds", ok == true)
	check("a hard-linked staged file: staging is gone", not exists(staging))
	check(
		"a hard-linked staged file: the published mode is unchanged",
		capture("stat -c %a '" .. dest .. "/modsec-crs/arrules.conf'") == "640"
	)
	finish(dest)
end

-- a directory that cannot be read and searched is a change, never an empty one
do
	for _, mode in ipairs({ "0000", "0300", "0100" }) do
		local dest = scratch .. "/noread" .. mode
		local staging = dest .. "/.bw-staging.1"
		assert(sh("mkdir -p " .. dest .. "/d " .. staging .. "/d"))
		write(dest .. "/d/f.conf", "x\n")
		write(staging .. "/d/f.conf", "x\n")
		assert(sh("chmod " .. mode .. " " .. dest .. "/d"))
		local inode = capture("stat -c %i '" .. dest .. "/d'")
		local ok = pushswap.swap(dest, staging, SKIP)
		-- Parking a directory needs write permission on it, so a mode without it is refused and rolled back. What
		-- matters is that the shortcut never left it in place as "unchanged".
		check(
			"a directory with mode " .. mode .. " is not proven identical",
			not (ok == true and capture("stat -c %i '" .. dest .. "/d'") == inode)
		)
		sh("chmod 0700 '" .. dest .. "/d' '" .. dest .. "/.bw-trash/d' 2>/dev/null; chmod -R u+rwx '" .. dest .. "'")
	end
end

sh("chmod -R u+w '" .. scratch .. "'; rm -rf '" .. scratch .. "'")
print(string.format("failures=%d", failures))
os.exit(failures == 0 and 0 or 1)
