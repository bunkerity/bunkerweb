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

	local undo = {}
	local function rollback()
		for i = #undo, 1, -1 do
			rename(undo[i].from, undo[i].to)
		end
		execute("rm -rf " .. quote(trash))
	end

	local incoming = {}
	for _, name in ipairs(list_entries(staging)) do
		incoming[name] = true
		local target = destination .. "/" .. name
		if existing[name] then
			local parked = trash .. "/" .. name
			local ok, err = rename(target, parked)
			if not ok then
				rollback()
				return false, "cannot park " .. name .. ": " .. tostring(err)
			end
			undo[#undo + 1] = { from = parked, to = target }
		end
		local ok, err = rename(staging .. "/" .. name, target)
		if not ok then
			rollback()
			return false, "cannot place " .. name .. ": " .. tostring(err)
		end
	end

	for name in pairs(existing) do
		if not incoming[name] and not is_reserved(name) then
			local parked = trash .. "/" .. name
			local ok, err = rename(destination .. "/" .. name, parked)
			if not ok then
				rollback()
				return false, "cannot sweep " .. name .. ": " .. tostring(err)
			end
			undo[#undo + 1] = { from = parked, to = destination .. "/" .. name }
		end
	end

	execute("rm -rf " .. quote(trash) .. " " .. quote(staging))
	return true
end

return pushswap
