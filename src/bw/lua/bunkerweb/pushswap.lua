-- Filesystem helpers for the instance-side push endpoints.
-- Free of any ngx dependency on purpose, so it can be unit tested outside OpenResty.

local popen = io.popen
local rename = os.rename
local execute = os.execute

local pushswap = {}

-- Bookkeeping entries live inside the destination so every rename stays on one
-- filesystem: a sibling directory can be on another mount, and rename(2) across
-- filesystems fails with EXDEV. They are dot-prefixed so no wildcard include or
-- glob picks them up, and the stale-entry sweep skips anything with this prefix.
pushswap.RESERVED_PREFIX = ".bw-"

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
				stuck[#stuck + 1] = undo[i]
			end
		end
		-- DELIBERATE DIVERGENCE FROM origin/dev -- do not "reconcile" this back.
		-- dev removed the trash unconditionally here. A stuck entry is one whose OLD copy is
		-- still parked in the trash, so that unconditional `rm -rf` destroys the last remaining
		-- copy of it : that mechanism had no recovery from its own partial failure. Keep the
		-- trash whenever anything is stuck, so the parked originals survive for the caller's
		-- last-resort restore and for manual recovery after it.
		if #stuck == 0 then
			execute("rm -rf " .. quote(trash))
			return nil
		end
		-- Port of dev a0a2bb427 on top of that divergence: keeping the trash is not enough on its
		-- own. Trash is a FIXED name, and the next swap opens by removing it -- so the copy this
		-- branch just preserved is destroyed by the very next push, and the message meanwhile
		-- names the destination path, which is exactly where the entry is NOT. Move the whole
		-- trash aside under a name no later swap touches, and say where it went.
		--
		-- A bare rename, not move_entry: both names are children of the destination, so rename(2)
		-- cannot report EXDEV here, and move_entry's copy fallback would only ever fire on the
		-- disk-full case this rescue exists for, where it leaves half a copy and reports it as the
		-- whole one. os.time has second resolution, so the name takes a counter until one is free
		-- and two failures inside the same second cannot land on each other. The reserved prefix
		-- keeps the rescue out of the stale-entry sweep and out of every include glob.
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
			-- Say which it is. When the rename failed, or ten candidates were already taken
			-- inside one second, `kept` is still the trash -- a path the NEXT push removes.
			-- Reporting that as "kept" is the pre-fix message with a new wording.
			if kept == trash then
				left[#left + 1] = item.target .. " (copy still in " .. source .. ", WILL BE REMOVED by the next push)"
			else
				left[#left + 1] = item.target .. " (copy kept at " .. source .. ")"
			end
		end
		return "rollback incomplete, left in place: " .. table.concat(left, ", ")
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
		-- DEV-2b5. Port of dev 32a2985ab: the reserved prefix is this module's own bookkeeping and never
		-- travels. Where the archived source and the destination are the same path -- Linux and
		-- all-in-one -- a kept rescue copy, or a staging directory left by a worker killed
		-- mid-push, comes back inside the next archive. Placing it would re-create an entry the
		-- stale-entry sweep below is REQUIRED to skip, so it would accumulate one copy of the
		-- tree per incident and never be cleared.
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
