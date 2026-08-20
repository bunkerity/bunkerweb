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

-- Bookkeeping entries live inside the destination so every rename stays on one
-- filesystem: a sibling directory can be on another mount, and rename(2) across
-- filesystems fails with EXDEV. They are dot-prefixed so no wildcard include or
-- glob picks them up, and the stale-entry sweep skips anything with this prefix.
pushswap.RESERVED_PREFIX = ".bw-"

local APPLIED = ".bw-applied"
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

-- Remove every NON-reserved top-level entry of destination.
--
-- Exists so the caller's last-resort restore never has to write `rm -rf <destination>/*`. That
-- glob happens to skip dotfiles, which is what kept the parked originals in .bw-trash alive
-- across the restore -- but a recovery path must not rest on an unstated property of shell
-- globbing. One `shopt -s dotglob`, one rewrite to `find -delete`, and the wipe would silently
-- destroy the very thing it exists to preserve, with nothing failing at the time.
-- This names what it deletes and reuses the same reserved-prefix predicate as the stale-entry
-- sweep, so there is one definition of "ours" rather than two that can drift apart.
function pushswap.clear(destination)
	for _, name in ipairs(list_entries(destination)) do
		if not is_reserved(name) then
			local entry = destination .. "/" .. name
			if not run("rm -rf " .. quote(entry)) then
				return false, "cannot remove " .. name
			end
		end
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

function pushswap.applied_path(destination)
	return destination .. "/" .. APPLIED
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
	local fh, err = open(pushswap.applied_path(destination), "w")
	if not fh then
		return false, err
	end
	fh:write(hex, "\n")
	fh:close()
	return true
end

-- Replace the top-level entries of destination with those of staging.
--
-- Returns: true                       on success
--          false, message, incomplete on failure, where `incomplete` is true when the ordered
--                                     undo could NOT put the destination back to its pre-swap
--                                     state. Only that case needs the caller's backup.
-- The destination directory itself is never renamed: it may be a mount point,
-- and renaming a mount point fails with EBUSY. Each entry is swapped with a
-- rename, so a consumer resolving a path either sees the old entry or the new
-- one, never a partially copied tree.
function pushswap.swap(destination, staging)
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
				stuck[#stuck + 1] = undo[i].to
			end
		end
		-- DELIBERATE DIVERGENCE FROM origin/dev -- do not "reconcile" this back.
		-- dev removes the trash unconditionally here. A stuck entry is one whose OLD copy is
		-- still parked in the trash, so that unconditional `rm -rf` destroys the last remaining
		-- copy of it : dev's mechanism has no recovery from its own partial failure. Keep the
		-- trash whenever anything is stuck, so the parked originals survive for the caller's
		-- last-resort restore and for manual recovery after it.
		if #stuck == 0 then
			execute("rm -rf " .. quote(trash))
		end
		if #stuck > 0 then
			return "rollback incomplete, left in place: " .. table.concat(stuck, ", ")
		end
		return nil
	end

	-- DELIBERATE DIVERGENCE FROM origin/dev -- do not "reconcile" this back.
	-- Third return value: whether the rollback left the destination half applied. The caller
	-- decides between "already back to the pre-swap tree, do nothing" and "last resort, restore
	-- from the backup" on this boolean and never on the message -- the message's tail carries
	-- entry names, so substring-matching it would misclassify on a filename.
	local function abort(message)
		local incomplete = rollback()
		if incomplete then
			return false, message .. " (" .. incomplete .. ")", true
		end
		return false, message, false
	end

	local incoming = {}
	for _, name in ipairs(list_entries(staging)) do
		incoming[name] = true
		local target = destination .. "/" .. name
		if existing[name] then
			local parked = trash .. "/" .. name
			local ok, err = move_entry(target, parked)
			if not ok then
				return abort("cannot park " .. name .. ": " .. tostring(err))
			end
			undo[#undo + 1] = { from = parked, to = target }
		end
		local ok, err = move_entry(staging .. "/" .. name, target)
		if not ok then
			return abort("cannot place " .. name .. ": " .. tostring(err))
		end
		undo[#undo + 1] = { from = target, to = staging .. "/" .. name }
	end

	for name in pairs(existing) do
		if not incoming[name] and not is_reserved(name) then
			local parked = trash .. "/" .. name
			local ok, err = move_entry(destination .. "/" .. name, parked)
			if not ok then
				return abort("cannot sweep " .. name .. ": " .. tostring(err))
			end
			undo[#undo + 1] = { from = parked, to = destination .. "/" .. name }
		end
	end

	execute("rm -rf " .. quote(trash) .. " " .. quote(staging))
	return true
end

return pushswap
