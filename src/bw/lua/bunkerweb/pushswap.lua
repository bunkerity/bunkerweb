-- Filesystem helpers for the instance-side push endpoints.
-- Free of any ngx dependency on purpose, so it can be unit tested outside OpenResty.
local sha256 = require "resty.sha256"
local str = require "resty.string"

local to_hex = str.to_hex
local open = io.open
local popen = io.popen
local rename = os.rename
local execute = os.execute

local pushswap = {}

-- The staging and trash directories live inside the destination so every rename stays
-- on one filesystem: a sibling directory can be on another mount, and rename(2) across
-- filesystems fails with EXDEV. They are dot-prefixed so no wildcard include or glob
-- picks them up, and the stale-entry sweep skips anything with this prefix. An entry
-- carrying the prefix is therefore never swept, which is why both plugin-id validators
-- refuse it as a plugin name.
pushswap.RESERVED_PREFIX = ".bw-"

-- A swap replaces the top-level entries one rename at a time, so a push cut short (SIGKILL, OOM,
-- container restart) leaves entries of two generations side by side. For the destination nginx
-- reads its configuration from, the swap keeps this sentinel in the destination from before its
-- first move until after its last one, and the startup scripts regenerate instead of keeping a tree
-- that carries it. It has the reserved prefix, so the sweep skips it and it is never placed from
-- an archive. Keep the name in step with sync_tree.INSTALL_SENTINEL.
pushswap.INSTALL_SENTINEL = pushswap.RESERVED_PREFIX .. "install-incomplete"
pushswap.SENTINEL_DESTINATION = "/etc/nginx"

-- The applied digest describes a destination, it is never part of one. On Linux and
-- all-in-one the archived source directory and the receiver destination are the same
-- path, so a marker written inside would become a member of the next archive and no
-- digest could ever match again: the unchanged-push fast path would never fire exactly
-- where the push is a no-op. It lives under a state root every component already owns,
-- keyed by destination. Anything that rewrites a destination behind the swap's back
-- must delete that key, or the instance keeps claiming a digest it no longer holds.
pushswap.STATE_ROOT = "/var/tmp/bunkerweb/pushswap"

local CHUNK = 65536

local function quote(path)
	return "'" .. path:gsub("'", "'\\''") .. "'"
end

local function list_entries(path)
	local entries = {}
	-- popen is used only to list a directory; the swap itself is rename(2).
	local pipe = popen("ls -A1 " .. quote(path) .. " 2>/dev/null")
	if not pipe then
		return entries
	end
	for name in pipe:lines() do
		if name ~= "" then
			entries[#entries + 1] = name
		end
	end
	pipe:close()
	return entries
end

local function is_reserved(name)
	return name:sub(1, #pushswap.RESERVED_PREFIX) == pushswap.RESERVED_PREFIX
end

-- os.execute returns a status number on LuaJIT and a boolean on Lua 5.2+.
local function run(cmd)
	local ok = execute(cmd)
	if type(ok) == "number" then
		return ok == 0
	end
	return ok == true
end

-- Move one directory entry, preferring rename(2) so the replacement is atomic.
--
-- overlayfs, which every container integration runs on, cannot rename a directory
-- that still lives in the image's lower layer and reports EXDEV. Anything shipped
-- in the image hits this on the first push after a container starts. Falling back
-- to a copy keeps that case working; the original is only dropped once the copy
-- succeeded, so the entry is still recoverable if a later one fails.
local function move_entry(from, to)
	local ok, err = rename(from, to)
	if ok then
		return true
	end
	-- cp would descend into an existing directory instead of replacing it, so a
	-- destination that is somehow still occupied is a hard failure, not a merge.
	if run("test -e " .. quote(to)) then
		return false, err
	end
	if not run("cp -a " .. quote(from) .. " " .. quote(to)) then
		return false, err
	end
	if not run("rm -rf " .. quote(from)) then
		return false, err
	end
	return true
end

-- Entry type of one path, read with the shell builtin tests, readlink and stat, never by following a link:
-- "d" or "f" plus a newline and the permission bits in octal (`stat -c %a`, special bits included) for a
-- directory or a regular file, "o" for anything else, and "l:<target>" plus a newline for a symlink, so two
-- links compare equal only when their target text is and a symlink's own mode is never read. nil when the
-- path is missing or the answer is not complete, a stat that is absent or fails included. Only the tools this
-- module already needs are used: sh, plus readlink and stat from the same coreutils (busybox on Alpine) as
-- ls, cp, rm and test.
local KIND_SCRIPT = [[if [ -L "$1" ]; then printf l:; readlink -- "$1"; ]]
	.. [[elif [ -d "$1" ]; then echo d; stat -c %a "$1"; ]]
	.. [[elif [ -f "$1" ]; then echo f; stat -c %a "$1"; elif [ -e "$1" ]; then echo o; else echo m; fi]]

local function entry_kind(path)
	local pipe = popen("sh -c '" .. KIND_SCRIPT .. "' sh " .. quote(path) .. " 2>/dev/null")
	if not pipe then
		return nil
	end
	local out = pipe:read("*a")
	pipe:close()
	if out and (out == "o\n" or out:find("^[df]\n[0-7]+\n$") or out:find("^l:.*\n$")) then
		return out
	end
	return nil
end

-- Names inside a directory, NUL-terminated by the shell: a file name can hold anything but NUL, so splitting
-- ls output on newlines would let {a, b, "a\nb"} and {a, b, "b\na"} list the same lines. The glob covers
-- every name but . and .. . The directory must be readable and searchable, or the loop would see nothing and
-- an unreadable directory would pass for an empty one. The trailing "ok" follows the last NUL, so output cut
-- short is told apart from a finished listing. Only sh builtins are used, dash and busybox ash alike.
local LIST_SCRIPT = [[[ -d "$1" ] && [ -r "$1" ] && [ -x "$1" ] || exit 0
for f in "$1"/* "$1"/.[!.]* "$1"/..?*; do
if [ -e "$f" ] || [ -L "$f" ]; then printf '%s\000' "${f##*/}"; fi
done
printf ok]]

-- Names inside a directory, or nil when it could not be listed in full.
local function list_checked(path)
	local pipe = popen("sh -c " .. quote(LIST_SCRIPT) .. " sh " .. quote(path) .. " 2>/dev/null")
	if not pipe then
		return nil
	end
	local out = pipe:read("*a")
	pipe:close()
	if not out then
		return nil
	end
	local names, start = {}, 1
	while true do
		local nul = out:find("\0", start, true)
		if not nul then
			break
		end
		names[#names + 1] = out:sub(start, nul - 1)
		start = nul + 1
	end
	if out:sub(start) ~= "ok" then
		return nil
	end
	return names
end

-- A read that fails answers nil plus a message, like the end of the file answers nil alone: an error is never
-- taken for the end, or two files that cannot be read would compare equal.
local function same_bytes(first, second)
	local one = open(first, "rb")
	if not one then
		return false
	end
	local two = open(second, "rb")
	if not two then
		one:close()
		return false
	end
	local same = true
	while true do
		local left, left_err = one:read(CHUNK)
		local right, right_err = two:read(CHUNK)
		if left_err or right_err or left ~= right then
			same = false
			break
		end
		if not left then
			break
		end
	end
	one:close()
	two:close()
	return same
end

local MAX_COMPARE_DEPTH = 32

-- True only when both trees are proven identical: the same relative paths, the same entry type at each, the
-- same permission bits for every directory and regular file, the same target text for every symlink, the
-- same bytes for every regular file. Anything else, an error, an unreadable path or a type it cannot compare
-- (device, socket, fifo) answers false, and the entry is then swapped as it always was.
--
-- The modes are compared as they are on disk: the staged copy was extracted under the umask of the worker
-- (`tar xzf`), so a mode the umask would have changed shows up as a difference and the entry is swapped, never
-- skipped. That keeps a push that only changes a mode, such as the scheduler restoring its failover copy of
-- the same files over the same loopback connection, from being recorded as applied without having been.
-- Owners are not compared: the extracting user owns every staged entry, so they could never match a
-- directory owned by root, and an owner cannot be carried by the archive anyway (the scheduler sets uid and
-- gid to 0). Symlinks have no mode of their own that matters, only their target.
local function same_tree(first, second, depth)
	if depth > MAX_COMPARE_DEPTH then
		return false
	end
	local kind = entry_kind(first)
	if not kind or kind ~= entry_kind(second) then
		return false
	end
	local type = kind:sub(1, 1)
	if type == "f" then
		return same_bytes(first, second)
	elseif type ~= "d" then
		return kind:sub(1, 2) == "l:"
	end
	local names, others = list_checked(first), list_checked(second)
	if not names or not others or #names ~= #others then
		return false
	end
	local known = {}
	for _, name in ipairs(names) do
		known[name] = true
	end
	for _, name in ipairs(others) do
		if not known[name] then
			return false
		end
	end
	for _, name in ipairs(names) do
		if not same_tree(first .. "/" .. name, second .. "/" .. name, depth + 1) then
			return false
		end
	end
	return true
end

-- Where the shortcut is allowed: the scheduler and the instance share /etc/bunkerweb/configs, so the archive the
-- scheduler pushes is a copy of the destination itself. All of these must hold:
--   * the push is POST /custom_configs,
--   * the integration is Linux, or Docker (the all-in-one image and the bunkerweb image both carry "Docker"),
--   * the scheduler is installed on this very filesystem, which the bunkerweb image never has,
--   * the TCP peer is loopback. `peer` is the raw peer address ($realip_remote_addr), never $remote_addr: the
--     realip module can rewrite the latter from a header the sender controls.
-- Anything else, and any doubt, answers false and the push is swapped entry by entry as it always was.
pushswap.SCHEDULER_MARKER = "/usr/share/bunkerweb/scheduler/main.py"

local SHARED_CONFIGS_INTEGRATIONS = { Linux = true, Docker = true }

local function is_loopback(peer)
	if type(peer) ~= "string" then
		return false
	end
	peer = peer:lower():gsub("^::ffff:", "")
	if peer == "::1" then
		return true
	end
	local first, second, third, fourth = peer:match("^(%d%d?%d?)%.(%d%d?%d?)%.(%d%d?%d?)%.(%d%d?%d?)$")
	return first == "127" and tonumber(second) <= 255 and tonumber(third) <= 255 and tonumber(fourth) <= 255
end

function pushswap.is_local_self_push(uri, integration, scheduler_present, peer)
	return uri == "/custom_configs"
		and SHARED_CONFIGS_INTEGRATIONS[integration] == true
		and scheduler_present == true
		and is_loopback(peer)
end

function pushswap.digest_file(path)
	local fh = open(path, "rb")
	if not fh then
		return nil, "cannot open " .. path
	end
	local hash = sha256:new()
	while true do
		local chunk = fh:read(CHUNK)
		if not chunk or chunk == "" then
			break
		end
		hash:update(chunk)
	end
	fh:close()
	return to_hex(hash:final())
end

-- Distinct destinations must never collapse onto one key: every non-alphanumeric run
-- becomes a single separator, which keeps the fixed set of destinations apart and the
-- file name readable when an operator has to look at it.
local function state_key(destination)
	local key = destination:gsub("[^%w]+", "_")
	return key
end

function pushswap.applied_path(destination)
	return pushswap.STATE_ROOT .. "/" .. state_key(destination) .. ".applied"
end

local function invalidate_applied(destination)
	os.remove(pushswap.applied_path(destination))
end

function pushswap.read_applied(destination)
	local fh = open(pushswap.applied_path(destination), "r")
	if not fh then
		return nil
	end
	local hex = fh:read("*l")
	fh:close()
	if not hex or hex == "" then
		return nil
	end
	return hex
end

function pushswap.write_applied(destination, hex)
	if not run("mkdir -p " .. quote(pushswap.STATE_ROOT)) then
		return false, "cannot create " .. pushswap.STATE_ROOT
	end
	local fh, err = open(pushswap.applied_path(destination), "w")
	if not fh then
		return false, err
	end
	fh:write(hex, "\n")
	fh:close()
	return true
end

-- A skipped (unchanged) entry stays in staging with the modes it was extracted with, a directory without write
-- permission included, and rm cannot empty such a directory: the owner gets write permission back first.
-- Directories only: removing a file needs write and search on its parent, never on the file, and a staged file
-- can share its inode with a published one (hard link), so chmod -R would change the published file's mode.
-- find does not follow symlinks, and chmod never sees a file or a link here.
local function drop_staging(staging)
	execute("find " .. quote(staging) .. " -type d -exec chmod u+rwx {} \\; 2>/dev/null; rm -rf " .. quote(staging))
end

-- Replace the top-level entries of destination with those of staging.
-- The destination directory itself is never renamed: it may be a mount point,
-- and renaming a mount point fails with EBUSY. Each entry is swapped with a
-- rename, so a consumer resolving a path either sees the old entry or the new
-- one, never a partially copied tree.
--
-- options.skip_unchanged leaves an existing top-level entry alone when its staged copy is proven identical
-- (same_tree). Only a verified local self-push asks for it (is_local_self_push). Where the archived source
-- is the destination (Linux package, all-in-one) that push sends back what is already there, and parking such
-- an entry needs write permission on it for a change that does not exist. Every other push, and a custom
-- configs push without the option, swaps each entry exactly as before.
function pushswap.swap(destination, staging, options)
	-- A failed swap leaves the destination between the two trees. Dropping the applied
	-- marker before touching anything means the next push cannot be answered "already
	-- applied" for a tree that was only half replaced; the caller rewrites it on success.
	invalidate_applied(destination)

	-- Created before the first move. One that is already there (a cut-short install, by the
	-- generator or an earlier push) is not ours to clear when this swap is rolled back.
	local sentinel, sentinel_is_ours
	if destination == pushswap.SENTINEL_DESTINATION then
		sentinel = destination .. "/" .. pushswap.INSTALL_SENTINEL
		local present = open(sentinel, "r")
		if present then
			present:close()
		else
			local created, err = open(sentinel, "w")
			if not created then
				return false, "cannot create " .. sentinel .. ": " .. tostring(err)
			end
			created:close()
			sentinel_is_ours = true
		end
	end

	local existing = {}
	for _, name in ipairs(list_entries(destination)) do
		existing[name] = true
	end

	local trash = destination .. "/" .. pushswap.RESERVED_PREFIX .. "trash"
	execute("rm -rf " .. quote(trash) .. " && mkdir -p " .. quote(trash))

	-- Every rename is recorded so a failure part-way through can be undone in
	-- reverse. A placement must be undone before the park it sits on top of:
	-- restoring the old entry while the new one still occupies the name fails
	-- with ENOTEMPTY, which would leave the destination half applied.
	local undo = {}
	local function rollback()
		local stuck = {}
		for i = #undo, 1, -1 do
			local ok = move_entry(undo[i].from, undo[i].to)
			if not ok then
				stuck[#stuck + 1] = undo[i]
			end
		end
		if #stuck == 0 then
			execute("rm -rf " .. quote(trash))
			return nil
		end
		-- Whatever could not be moved back is still at its recorded source. For a parked old
		-- entry that source is inside trash, and it is then the only surviving copy. Trash is a
		-- fixed name that the next swap opens by removing, so the copy has to leave it, and the
		-- message has to name where it went or it points at a path that will not be there.
		--
		-- A bare rename, not move_entry: both names are children of the destination so rename(2)
		-- cannot report EXDEV here, and the copy fallback would only ever fire on the disk-full
		-- case this rescue exists for, where it leaves half a copy and reports it as the whole
		-- one. os.time has second resolution, so the name takes a counter until one is free and
		-- two failures inside one second cannot land on each other.
		local kept = trash
		local base = destination .. "/" .. pushswap.RESERVED_PREFIX .. "rescue." .. tostring(os.time())
		for i = 0, 9 do
			local candidate = i == 0 and base or (base .. "." .. i)
			if not run("test -e " .. quote(candidate)) then
				if rename(trash, candidate) then
					kept = candidate
				end
				break
			end
		end
		local left = {}
		for _, item in ipairs(stuck) do
			-- The entry an operator has to repair is the destination one either way: a park that
			-- could not be restored left the old copy in the parked tree, a placement that could
			-- not be undone left the new entry live in the destination.
			local source = item.from
			if kept ~= trash and source:sub(1, #trash + 1) == trash .. "/" then
				source = kept .. source:sub(#trash + 1)
			end
			left[#left + 1] = item.target .. " (copy kept at " .. source .. ")"
		end
		return "rollback incomplete, left in place: " .. table.concat(left, ", ")
	end

	local function abort(message)
		local incomplete = rollback()
		if incomplete then
			return false, message .. " (" .. incomplete .. ")"
		end
		-- The old tree is back in full, so it is as consistent as it was before this swap.
		if sentinel_is_ours then
			os.remove(sentinel)
		end
		-- A complete rollback put every entry back, so staging holds nothing anyone still needs
		-- and nothing else refers to it. Left behind it is a reserved name the sweep never
		-- clears, and where the archived source is the destination it comes back in the next
		-- archive.
		drop_staging(staging)
		return false, message
	end

	local incoming = {}
	for _, name in ipairs(list_entries(staging)) do
		-- The reserved prefix is this module's own bookkeeping and never travels. Where the
		-- archived source and the destination are the same path, a kept rescue copy or a staging
		-- directory left by a worker that died mid-push comes back inside the archive; placing it
		-- would re-create an entry the sweep is required to skip, so it would grow every push and
		-- never be cleared.
		if not is_reserved(name) then
			incoming[name] = true
			local target = destination .. "/" .. name
			local unchanged = options and options.skip_unchanged and existing[name]
			-- The unchanged entry stays as it is and its staged copy goes with staging.
			if not (unchanged and same_tree(target, staging .. "/" .. name, 0)) then
				if existing[name] then
					local parked = trash .. "/" .. name
					local ok, err = move_entry(target, parked)
					if not ok then
						return abort("cannot park " .. name .. ": " .. tostring(err))
					end
					undo[#undo + 1] = { from = parked, to = target, target = target }
				end
				local ok, err = move_entry(staging .. "/" .. name, target)
				if not ok then
					return abort("cannot place " .. name .. ": " .. tostring(err))
				end
				undo[#undo + 1] = { from = target, to = staging .. "/" .. name, target = target }
			end
		end
	end

	for name in pairs(existing) do
		if not incoming[name] and not is_reserved(name) then
			local parked = trash .. "/" .. name
			local ok, err = move_entry(destination .. "/" .. name, parked)
			if not ok then
				return abort("cannot sweep " .. name .. ": " .. tostring(err))
			end
			undo[#undo + 1] = { from = parked, to = destination .. "/" .. name, target = destination .. "/" .. name }
		end
	end

	-- Every entry is in place.
	if sentinel then
		os.remove(sentinel)
	end
	execute("rm -rf " .. quote(trash))
	drop_staging(staging)
	return true
end

return pushswap
