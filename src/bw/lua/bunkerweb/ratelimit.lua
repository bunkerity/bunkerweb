local ngx = ngx
local ERR = ngx.ERR
local time = os.time
local date = os.date
local floor = math.floor

-- Fixed-window request counter over an arbitrary key, shared by the plugins that need to
-- count requests without the per-IP timestamp log Limit keeps for LIMIT_REQ. The log is
-- O(n) per request (n = the limit); this is O(1), which is what a global cap or a workflow
-- rate gate needs at hundreds of req/s.
-- Redis when the caller has it configured, worker shared dict otherwise, and the key
-- self-expires after one window so cardinality stays bounded by active clients.
-- ponytail: fixed window allows ~2x the rate right at a window boundary; upgrade to a
-- sliding-window counter only if precise smoothing is ever measured to matter.
local ratelimit = {}

local redis_script = [[
	local delay = tonumber(ARGV[1])
	local count = redis.pcall("INCR", KEYS[1])
	if type(count) == "table" and count["err"] ~= nil then
		redis.log(redis.LOG_WARNING, "ratelimit INCR error : " .. count["err"])
		return count
	end
	if count == 1 then
		local ret_expire = redis.pcall("EXPIRE", KEYS[1], delay)
		if type(ret_expire) == "table" and ret_expire["err"] ~= nil then
			redis.log(redis.LOG_WARNING, "ratelimit EXPIRE error : " .. ret_expire["err"])
			return ret_expire
		end
	end
	return count
]]

-- The window number, not a timestamp : every request inside the same window derives the
-- same key, which is what makes the counter shared without any coordination.
local window_key = function(prefix, window)
	return prefix .. "_" .. tostring(floor(time(date("!*t")) / window))
end

ratelimit.incr_local = function(owner, prefix, window)
	local key = window_key(prefix, window)
	local value, err = owner.datastore:get(key)
	if not value and err ~= "not found" then
		return nil, err
	end
	local count = 1
	if value then
		count = tonumber(value) + 1
	end
	-- luacheck: ignore 421
	local ok, err = owner.datastore:set_with_retries(key, tostring(count), window)
	if not ok then
		return nil, err
	end
	return count, "success"
end

ratelimit.incr_redis = function(owner, prefix, window)
	local ok, err = owner.clusterstore:connect()
	if not ok then
		return nil, err
	end
	local count
	count, err = owner.clusterstore:call("eval", redis_script, 1, window_key(prefix, window), window)
	if not count then
		owner.clusterstore:close()
		return nil, err
	end
	owner.clusterstore:close()
	return count, "success"
end

-- Increment the counter for `prefix` in the current `window` (seconds) and return its new
-- value, or nil + err. `owner` is anything exposing use_redis / clusterstore / datastore /
-- logger — every plugin instance does (see plugin.lua).
-- A Redis failure is not fatal : it logs and falls back to the worker-local dict, which
-- undercounts across instances but never blocks the request path.
ratelimit.incr = function(owner, prefix, window)
	local count
	if owner.use_redis then
		local redis_count, err = ratelimit.incr_redis(owner, prefix, window)
		if redis_count == nil then
			owner.logger:log(ERR, "ratelimit redis failed, falling back to local : " .. err)
		else
			count = redis_count
		end
	end
	if count == nil then
		local local_count, err = ratelimit.incr_local(owner, prefix, window)
		if local_count == nil then
			return nil, err
		end
		count = local_count
	end
	return count, "success"
end

return ratelimit
