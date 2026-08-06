local cdatastore = require "bunkerweb.datastore"
local cjson = require "cjson"
local internal_api = require "bunkerweb.internal_api"
local resty_lock = require "resty.lock"

local ngx = ngx
local syncstore = cdatastore:new(ngx.shared.ban_sync_stream)
local worker = ngx.worker
local wall_time = ngx.now or ngx.time
local decode = cjson.decode
local encode = cjson.encode

local SNAPSHOT_KEY = "ban_snapshot"
local COMMIT_LOCK_KEY = "ban_snapshot_commit"
local COMMIT_LOCK_OPTIONS = { timeout = 0.05, exptime = 5 }
local INTERNAL_API_TIMEOUT = 1000

local ban_sync = {}

local function is_nonnegative_integer(value)
	return type(value) == "number" and value >= 0 and value % 1 == 0
end

local function build_snapshot(payload)
	if
		type(payload) ~= "table"
		or payload.status ~= "success"
		or type(payload.data) ~= "table"
		or not is_nonnegative_integer(payload.generation_epoch)
		or type(payload.snapshot_time) ~= "number"
		or payload.snapshot_time <= 0
	then
		return nil, "invalid /bans response"
	end

	local now = wall_time()
	local bans = {}
	local count = 0
	for _, ban in ipairs(payload.data) do
		if type(ban) ~= "table" or type(ban.ip) ~= "string" or ban.ip == "" then
			return nil, "invalid ban in /bans response"
		end
		if ban.ban_scope ~= "global" and ban.ban_scope ~= "service" then
			return nil, "invalid ban scope in /bans response"
		end

		local key = "bans_ip_" .. ban.ip
		local service = ban.service or "unknown"
		if ban.ban_scope == "service" then
			if type(ban.service) ~= "string" or ban.service == "" then
				return nil, "invalid service ban in /bans response"
			end
			key = "bans_service_" .. ban.service .. "_ip_" .. ban.ip
		end
		if bans[key] ~= nil then
			return nil, "duplicate ban in /bans response"
		end

		local permanent = ban.permanent == true
		local expires_at = tonumber(ban.expires_at)
		if permanent then
			expires_at = 0
		elseif not expires_at or expires_at <= 0 then
			return nil, "invalid absolute ban expiry in /bans response"
		end

		-- Absolute expiries make transport and scheduling delay consume, rather
		-- than extend, a timed ban.
		if permanent or expires_at > now then
			bans[key] = {
				reason = ban.reason,
				service = service,
				date = tonumber(ban.date) or 0,
				country = ban.country or "unknown",
				ban_scope = ban.ban_scope,
				reason_data = type(ban.reason_data) == "table" and ban.reason_data or {},
				permanent = permanent,
				expires_at = expires_at,
			}
			count = count + 1
		end
	end

	return {
		generation_epoch = payload.generation_epoch,
		source_snapshot_time = payload.snapshot_time,
		bans = bans,
	},
		count
end

local function publish_snapshot(snapshot, encoded)
	local lock, err = resty_lock:new("cachestore_locks_stream", COMMIT_LOCK_OPTIONS)
	if not lock then
		return false, "can't create Stream ban snapshot commit lock : " .. tostring(err)
	end
	local elapsed
	elapsed, err = lock:lock(COMMIT_LOCK_KEY)
	if elapsed == nil then
		return false, "can't acquire Stream ban snapshot commit lock : " .. tostring(err)
	end

	-- The compare and single-key safe_set are local, bounded, and non-yielding.
	-- A delayed response can therefore never overwrite a newer committed epoch.
	local call_ok, result, result_err = pcall(function()
		local current_raw, current_err = syncstore:get(SNAPSHOT_KEY)
		if current_raw then
			local decoded_ok, current = pcall(decode, current_raw)
			if not decoded_ok or type(current) ~= "table" or not is_nonnegative_integer(current.generation_epoch) then
				return false, "invalid committed Stream ban snapshot"
			end
			if snapshot.generation_epoch < current.generation_epoch then
				return true, "stale snapshot ignored"
			elseif snapshot.generation_epoch == current.generation_epoch then
				return true, "snapshot already current"
			end
		elseif current_err ~= "not found" then
			return false, "can't read committed Stream ban snapshot : " .. tostring(current_err)
		end

		local ok
		ok, err = syncstore:set(SNAPSHOT_KEY, encoded)
		if not ok then
			return false, "can't publish Stream ban snapshot without eviction : " .. tostring(err)
		end
		return true, "success"
	end)
	local unlock_ok, unlock_err = lock:unlock()
	if not call_ok then
		return false, "Stream ban snapshot commit raised : " .. tostring(result)
	end
	if not unlock_ok then
		return false, "can't release Stream ban snapshot commit lock : " .. tostring(unlock_err)
	end
	return result, result_err
end

function ban_sync.reconcile()
	if worker.id() ~= 0 then
		return true, "skipped"
	end

	local call_ok, response, err = pcall(internal_api.request, "/bans", {
		timeout = INTERNAL_API_TIMEOUT,
	})
	if not call_ok then
		return false, "internal API request raised : " .. tostring(response)
	end
	if not response then
		return false, err
	end
	if response.status ~= 200 then
		return false, "internal API returned HTTP " .. tostring(response.status)
	end

	local decoded_ok, payload = pcall(decode, response.body)
	if not decoded_ok then
		return false, "can't decode /bans response : " .. tostring(payload)
	end
	local snapshot, count = build_snapshot(payload)
	if not snapshot then
		return false, count
	end
	local encoded_ok, encoded = pcall(encode, snapshot)
	if not encoded_ok then
		return false, "can't encode Stream ban snapshot : " .. tostring(encoded)
	end

	local ok, publish_err = publish_snapshot(snapshot, encoded)
	if not ok then
		return false, publish_err
	end
	return true, "synchronized " .. tostring(count) .. " bans"
end

return ban_sync
