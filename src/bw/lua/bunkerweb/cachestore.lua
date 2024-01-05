local ngx = ngx
local class = require "middleclass"
local clogger = require "bunkerweb.logger"
local clusterstore = require "bunkerweb.clusterstore"
local mlcache = require "resty.mlcache"
local utils = require "bunkerweb.utils"
local cachestore = class("cachestore")

local logger = clogger:new("CACHESTORE")

local subsystem = ngx.config.subsystem
local ERR = ngx.ERR
local INFO = ngx.INFO
local null = ngx.null
local get_ctx_obj = utils.get_ctx_obj
local is_cosocket_available = utils.is_cosocket_available

-- Instantiate mlcache object at module level (which will be cached when running init phase)
-- TODO : custom settings
local shm = "cachestore"
local ipc_shm = "cachestore_ipc"
local shm_miss = "cachestore_miss"
local shm_locks = "cachestore_locks"
if subsystem == "stream" then
	shm = "cachestore_stream"
	ipc_shm = "cachestore_ipc_stream"
	shm_miss = "cachestore_miss_stream"
	shm_locks = "cachestore_locks_stream"
end
local cache, err = mlcache.new("cachestore", shm, {
	lru_size = 100,
	ttl = 30,
	neg_ttl = 0.1,
	shm_set_tries = 3,
	shm_miss = shm_miss,
	shm_locks = shm_locks,
	resty_lock_opts = {
		exptime = 30,
		timeout = 5,
		step = 0.001,
		ratio = 2,
		max_step = 0.5,
	},
	ipc_shm = ipc_shm,
})
if not cache then
	logger:log(ERR, "can't instantiate mlcache : " .. err)
end

function cachestore:initialize(use_redis, ctx, pool)
	self.use_redis = use_redis or false
	if self.use_redis then
		if ctx then
			self.clusterstore = get_ctx_obj("clusterstore", ctx)
		else
			self.clusterstore = clusterstore:new(pool)
		end
	end
end

function cachestore:get(key)
	-- luacheck: ignore 432
	local callback = function(key, cs)
		-- Connect to redis
		-- luacheck: ignore 431
		local ok, err, _ = cs:connect(true)
		if not ok then
			return nil, "can't connect to redis : " .. err, nil
		end
		-- Redis script to get value + ttl
		local redis_script = [[
			local ret_get = redis.pcall("GET", KEYS[1])
			if type(ret_get) == "table" and ret_get["err"] ~= nil then
				redis.log(redis.LOG_WARNING, "BUNKERWEB CACHESTORE GET error : " .. ret_get["err"])
				return ret_get
			end
			local ret_ttl = redis.pcall("TTL", KEYS[1])
			if type(ret_ttl) == "table" and ret_ttl["err"] ~= nil then
				redis.log(redis.LOG_WARNING, "BUNKERWEB CACHESTORE DEL error : " .. ret_ttl["err"])
				return ret_ttl
			end
			return {ret_get, ret_ttl}
		]]
		local ret, err = cs:call("eval", redis_script, 1, key)
		if not ret then
			cs:close()
			return nil, err, nil
		end
		-- Extract values
		cs:close()
		if ret[1] == null then
			ret[1] = nil
			ret[2] = -1
		elseif ret[2] < 0 then
			ret[2] = ret[2] + 1
		end
		return ret[1], nil, ret[2]
	end
	local callback_no_miss = function()
		return nil, nil, -1
	end
	-- luacheck: ignore 431
	local value, err, hit_level
	if self.use_redis and is_cosocket_available() then
		value, err, hit_level = cache:get(key, nil, callback, key, self.clusterstore)
	else
		value, err, hit_level = cache:get(key, nil, callback_no_miss)
	end
	if value == nil and err ~= nil then
		return false, err
	end
	logger:log(INFO, "hit level for " .. key .. " = " .. tostring(hit_level))
	return true, value
end

function cachestore:set(key, value, ex)
	-- luacheck: ignore 431
	local ok, err
	if self.use_redis and is_cosocket_available() then
		ok, err = self:set_redis(key, value, ex)
		if not ok then
			logger:log(ERR, err)
		end
	end
	if ex then
		ok, err = cache:set(key, { ttl = ex }, value)
	else
		ok, err = cache:set(key, nil, value)
	end
	if not ok then
		return false, err
	end
	return true
end

function cachestore:set_redis(key, value, ex)
	-- Connect to redis
	-- luacheck: ignore 431
	local ok, err, _ = self.clusterstore:connect()
	if not ok then
		return false, "can't connect to redis : " .. err
	end
	-- Set value with ttl
	local default_ex = ex or 30
	local _, err = self.clusterstore:call("set", key, value, "EX", default_ex)
	if err then
		self.clusterstore:close()
		return false, "SET failed : " .. err
	end
	self.clusterstore:close()
	return true
end

function cachestore:delete(key)
	-- luacheck: ignore 431
	local ok, err
	if self.use_redis and is_cosocket_available() then
		ok, err = self:del_redis(key)
		if not ok then
			logger:log(ERR, err)
		end
	end
	ok, err = cache:delete(key)
	if not ok then
		return false, err
	end
	return true
end

function cachestore:del_redis(key)
	-- Connect to redis
	-- luacheck: ignore 431
	local ok, err = self.clusterstore:connect()
	if not ok then
		return false, "can't connect to redis : " .. err
	end
	-- Set value with ttl
	local _, err = self.clusterstore:del(key)
	if err then
		self.clusterstore:close()
		return false, "DEL failed : " .. err
	end
	self.clusterstore:close()
	return true
end

-- luacheck: ignore 212
function cachestore:purge()
	return cache:purge(true)
end

-- luacheck: ignore 212
function cachestore:update()
	return cache:update()
end

return cachestore
