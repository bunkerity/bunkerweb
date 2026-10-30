local cjson = require "cjson"
local ffi = require "ffi"
local hash = require("crowdsec.cache_partition").hash
local stream_lock = require "crowdsec.lib.stream_lock"

ffi.cdef [[
int open(const char *pathname, int flags, ...);
long write(int fd, const void *buf, unsigned long count);
int close(int fd);
int getpid(void);
]]

local M = {}
local PENDING = "pending|"
local serial = 0
local error_until = {}

-- Only init and flock-protected timers access files. /cache pushes
-- replace scheduler-owned files, so checkpoints live in the existing writable state directory.
function M.new(prefix, aliases, directory)
	directory = directory or "/var/lib/bunkerweb"
	local state = {}
	local shared = ngx.shared.crowdsec_metadata or ngx.shared.crowdsec_cache
	local revision_key = "crowdsec_state_revision|" .. hash(prefix)
	local function next_revision()
		serial = serial + 1
		return hash(ffi.C.getpid() .. ":" .. serial .. ":" .. ngx.now())
	end
	local revision = shared:get(revision_key)
	if revision == nil then
		-- A missing key may be an eviction during a publication, so the next reader validates under the lock.
		shared:safe_add(revision_key, PENDING .. next_revision())
		revision = shared:get(revision_key)
	end
	local function path(kind, value)
		return directory .. "/crowdsec-" .. kind .. "-" .. hash(value) .. ".json"
	end
	local function report()
		local cache = ngx.shared.crowdsec_metadata or ngx.shared.crowdsec_cache
		local ok, err = cache:safe_add("crowdsec_state_error|" .. hash(prefix), true, 60)
		if ok or (err ~= "exists" and ngx.time() >= (error_until[prefix] or 0)) then
			if not ok then
				error_until[prefix] = ngx.time() + 60
			end
			ngx.log(ngx.ERR, "CrowdSec enforcement checkpoint unavailable or invalid [cache prefix " .. prefix .. "]")
		end
	end
	-- Returns the decoded table, or nil with why: "absent" (no file), "io" (open, read or close failed) or "invalid".
	local function read(file)
		local handle, _, code = io.open(file, "rb")
		if not handle then
			if code ~= 2 then
				report()
				return nil, "io"
			end
			return nil, "absent"
		end
		local raw = handle:read("*a")
		local closed, close_error = handle:close()
		if raw == nil or (closed == nil and close_error ~= nil) then
			report()
			return nil, "io"
		end
		local ok, data = pcall(cjson.decode, raw)
		if not ok or type(data) ~= "table" then
			report()
			return nil, "invalid"
		end
		return data
	end
	-- Highest publication sequence read from any checkpoint; a lower bound for the next one.
	local seen = 0
	-- Returns the records, or nil with why ("foreign" files count as absent), plus the publication sequence.
	local function load(expected)
		local data, why = read(path("state", expected))
		if not data then
			return nil, why
		end
		if data.prefix ~= expected then
			report()
			return nil, "absent"
		end
		if data.version ~= 1 or type(data.records) ~= "table" then
			report()
			return nil, "invalid"
		end
		for target, records in pairs(data.records) do
			if
				type(target) ~= "string"
				or #target > 256
				or not target:match("^ipv[46]_[%x:]+_[%x:%.]+$")
				or type(records) ~= "table"
			then
				report()
				return nil, "invalid"
			end
			for id, record in pairs(records) do
				if
					type(id) ~= "string"
					or #id > 133
					or type(record) ~= "table"
					or type(record[1]) ~= "number"
					or record[1] ~= record[1]
					or record[1] == math.huge
					or (record[2] ~= "ban" and record[2] ~= "captcha")
				then
					report()
					return nil, "invalid"
				end
				if record[1] <= ngx.time() then
					records[id] = nil
				end
			end
		end
		-- A file without a sequence (never written by this version) orders before every stamped file.
		local sequence = type(data.seq) == "number" and data.seq == data.seq and data.seq >= 0 and data.seq or 0
		seen = math.max(seen, sequence)
		return data.records, nil, sequence
	end
	local function write(file, data)
		serial = serial + 1
		local temporary = file .. "." .. ffi.C.getpid() .. "." .. serial .. ".tmp"
		-- O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, mode 0660 (subject to umask).
		local fd = ffi.C.open(temporary, 524481, ffi.new("int", 432))
		if fd < 0 then
			report()
			return nil
		end
		local ok, encoded = pcall(cjson.encode, data)
		local written = ok and ffi.C.write(fd, encoded, #encoded) == #encoded
		local closed = ffi.C.close(fd) == 0
		if not written or not closed or not os.rename(temporary, file) then
			os.remove(temporary)
			report()
			return nil
		end
		return true
	end

	local function unusable(why)
		return why == "io" or why == "invalid"
	end
	-- Returns the restored records and whether any file was unreadable or invalid (missing files are not failures).
	local function restore()
		local records, bound, loaded, failed, newest = {}, false, {}, false, nil
		for _, alias in ipairs(aliases) do
			local binding, why = read(path("binding", alias))
			failed = failed or unusable(why)
			if binding then
				bound = true
				if type(binding.prefix) == "string" and #binding.prefix <= 80 and not binding.prefix:find("[%c]") then
					if not loaded[binding.prefix] then
						loaded[binding.prefix] = true
						local entries_by_target, state_why, sequence = load(binding.prefix)
						failed = failed or unusable(state_why)
						if sequence and sequence > (newest or -1) then
							newest = sequence
						end
						for target, entries in pairs(entries_by_target or {}) do
							records[target] = records[target] or {}
							for id, record in pairs(entries) do
								records[target][hash(binding.prefix .. id)] = record
							end
						end
					end
				else
					report()
					failed = true
				end
			end
		end
		if not bound then
			local own, own_why = load(prefix)
			failed = failed or unusable(own_why)
			records = own or {}
		elseif not loaded[prefix] then
			-- A rotation whose binding rename failed leaves the binding behind the checkpoint just written under this
			-- prefix. Bindings keep precedence (a return to an earlier URL) unless this prefix was published later.
			-- Equal sequences cannot be ordered, so the restore fails and denies until a synchronization rewrites it.
			local own, own_why, sequence = load(prefix)
			failed = failed or unusable(own_why)
			if own and newest then
				if sequence > newest then
					records = own
				elseif sequence == newest then
					failed = true
				end
			elseif own then
				records = own
			end
		end
		return records, failed
	end
	local sequence_file, sequence_lock = directory .. "/crowdsec-sequence.json", directory .. "/crowdsec-sequence.lock"
	-- Runs fn under the global sequence lock, retrying like the stream lock does. Never takes another lock inside.
	local function with_sequence_lock(fn)
		local deadline = ngx.now() + 2
		while true do
			local ok, err = stream_lock.run(sequence_lock, fn)
			if ok then
				return true
			end
			if err ~= "busy" then
				return nil, err
			end
			if ngx.now() >= deadline then
				return nil, "busy"
			end
			ngx.sleep(0.05)
		end
	end
	-- Takes the next sequence and records it before any file is published, so a writer that dies afterwards leaves
	-- only a gap, which nothing waits for. Returns nil when the order cannot be proven; the save then fails.
	local function reserve_sequence()
		local data, why = read(sequence_file)
		local floor = seen
		if data and (type(data.seq) ~= "number" or data.seq ~= data.seq or data.seq < 0 or data.seq == math.huge) then
			report()
			data, why = nil, "invalid"
		end
		if data then
			floor = math.max(floor, data.seq)
		elseif why == "io" then
			return nil
		else
			-- No usable sequence file (fresh state directory, or a torn or corrupt one that this save rewrites): raise
			-- the floor with every checkpoint that could compete, so the order still holds after the rebuild.
			local competing = { [prefix] = true }
			local _, own_why = load(prefix)
			if own_why == "io" then
				return nil
			end
			for _, alias in ipairs(aliases) do
				local binding, binding_why = read(path("binding", alias))
				if binding_why == "io" then
					return nil
				end
				if binding and type(binding.prefix) == "string" and not competing[binding.prefix] then
					competing[binding.prefix] = true
					local _, bound_why = load(binding.prefix)
					if bound_why == "io" then
						return nil
					end
				end
			end
			floor = math.max(floor, seen)
		end
		local reserved = floor + 1
		if not write(sequence_file, { seq = reserved }) then
			return nil
		end
		return reserved
	end
	local fallback, restore_failed = restore()
	-- A pending token means a publication started and may never have finished; trust nothing until a locked read.
	-- A failed restore also stays unvalidated, so a later locked read must succeed before any fallback use.
	local validated = type(revision) == "string" and revision:sub(1, #PENDING) ~= PENDING and not restore_failed
	function state.changed()
		local current = shared:get(revision_key)
		return not validated or current == nil or current ~= revision
	end
	local failed_revision, retry_after
	function state.refresh()
		local current = shared:get(revision_key)
		if current == nil then
			report()
			return nil
		end
		if current == failed_revision and ngx.time() < retry_after then
			return nil
		end
		local records
		if validated then
			records = load(prefix)
		else
			-- The flock proves no writer is running, and checkpoints are renamed atomically, so what exists is the last
			-- complete one. Restore as the constructor does, but fail on an I/O error instead of trusting a stale fallback.
			local restored, failed = restore()
			records = not failed and restored or nil
		end
		if not records then
			failed_revision, retry_after = current, ngx.time() + 1
			return nil
		end
		fallback, revision, validated = records, current, true
		return true
	end
	function state.get(target)
		local selected
		for _, record in pairs(fallback[target] or {}) do
			if record[1] > ngx.time() and (not selected or record[2] == "ban") then
				selected = record[2]
			end
		end
		if selected then
			return selected,
				{
					source = "lapi",
					captured_at = ngx.time(),
					decisions = setmetatable({}, cjson.array_mt),
					metadata_available = false,
				}
		end
	end
	function state.prepare(startup, bootstrap)
		if startup then
			return {}
		end
		local records, why = load(prefix)
		-- An unreadable checkpoint must never be replaced by a possibly stale in-memory copy.
		if not records and bootstrap and why ~= "io" then
			records = {}
			for target, entries in pairs(fallback) do
				records[target] = {}
				for id, record in pairs(entries) do
					records[target][id] = record
				end
			end
		end
		return records
	end
	function state.save(records)
		for target, entries in pairs(records) do
			for id, record in pairs(entries) do
				if record[1] <= ngx.time() then
					entries[id] = nil
				end
			end
			if next(entries) == nil then
				records[target] = nil
			end
		end
		-- A fresh token also detects an optional-metadata eviction followed by recreation.
		-- This pending token announces the update, so waiting readers queue for the lock.
		local current = PENDING .. next_revision()
		if not shared:safe_set(revision_key, current) then
			report()
			return nil
		end
		-- The sequence orders checkpoints across prefixes (see restore). One global sequence is assigned and the files
		-- are published under one global lock, always taken inside the per-prefix stream lock, so that publication
		-- order, sequence order and binding order agree even when prefixes write at the same time.
		local checkpoint
		local locked, lock_err = with_sequence_lock(function()
			local reserved = reserve_sequence()
			if not reserved then
				return
			end
			checkpoint = { version = 1, prefix = prefix, records = records, seq = reserved }
			if not write(path("state", prefix), checkpoint) then
				checkpoint = nil
				return
			end
			for _, alias in ipairs(aliases) do
				if not write(path("binding", alias), { prefix = prefix }) then
					checkpoint = nil
					return
				end
			end
		end)
		if not locked or not checkpoint then
			if not locked and lock_err ~= "busy" then
				report()
			end
			return nil
		end
		-- A constructor can read the pending token before the rename above and keep the previous file.
		-- It trusts only this plain token, which is published after every file is complete.
		current = next_revision()
		if not shared:safe_set(revision_key, current) then
			report()
			return nil
		end
		seen = checkpoint.seq
		fallback, revision, validated = records, current, true
		return true
	end
	return state
end

return M
