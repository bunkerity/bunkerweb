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

-- Replace the top-level entries of destination with those of staging.
-- The destination directory itself is never renamed: it may be a mount point,
-- and renaming a mount point fails with EBUSY. Each entry is swapped with a
-- rename, so a consumer resolving a path either sees the old entry or the new
-- one, never a partially copied tree.
function pushswap.swap(destination, staging)
	-- A failed swap leaves the destination between the two trees. Dropping the applied
	-- marker before touching anything means the next push cannot be answered "already
	-- applied" for a tree that was only half replaced; the caller rewrites it on success.
	invalidate_applied(destination)

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
		-- A complete rollback put every entry back, so staging holds nothing anyone still needs
		-- and nothing else refers to it. Left behind it is a reserved name the sweep never
		-- clears, and where the archived source is the destination it comes back in the next
		-- archive.
		execute("rm -rf " .. quote(staging))
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

	execute("rm -rf " .. quote(trash) .. " " .. quote(staging))
	return true
end

return pushswap
