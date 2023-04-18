local mlcache		= require "resty.mlcache"
local logger		= require "bunkerweb.logger"
local class     	= require "middleclass"
local cachestore	= class("cachestore")

-- Instantiate mlcache object at module level (which will be cached when running init phase)
-- TODO : custom settings
local shm		= "cachestore"
local ipc_shm	= "cachestore_ipc"
local shm_miss	= "cachestore_miss"
local shm_locks	= "cachestore_locks"
if not ngx.shared.cachestore then
	shm			= "cachestore_stream"
	ipc_shm		= "cachestore_ipc_stream"
	shm_miss	= "cachestore_miss_stream"
	shm_locks	= "cachestore_locks_stream"
end
local cache, err = mlcache.new(
	"cachestore",
	shm,
	{
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
			max_step = 0.5
		},
		ipc_shm = ipc_shm
	}
)
local module_logger = logger:new("CACHESTORE")
if not cache then
	module_logger:log(ngx.ERR, "can't instantiate mlcache : " .. err)
end

function cachestore:initialize(use_redis)
	self.cache = cache
	self.use_redis = use_redis or false
	self.logger = module_logger
end

function cachestore:get(key)
	local function callback(key)
		-- Connect to redis
		local clusterstore = require "bunkerweb.clusterstore"
		local ok, err = clusterstore:new()
		if not ok then
			return nil, "clusterstore:new() failed : " .. err, nil
		end
		local ok, err = clusterstore:connect()
		if not ok then
			return nil, "can't connect to redis : " .. err, nil
		end
		-- Exec transaction
		local calls = {
			{"get", {key}},
			{"ttl", {key}}
		}
		-- Exec transaction
		local exec, err = clusterstore:multi(calls)
		if err then
			clusterstore:close()
			return nil, "exec() failed : " .. err, nil
		end
		-- Get results
		local value = exec[1]
		if type(value) == "table" then
			clusterstore:close(redis)
			return nil, "GET error : " .. value[2], nil
		end
		local ttl = exec[2]
		if type(ttl) == "table" then
			clusterstore:close(redis)
			return nil, "TTL error : " .. ttl[2], nil
		end
		-- Return value
		clusterstore:close(redis)
		if value == ngx.null then
			value = nil
		end
		if ttl < 0 then
			ttl = ttl + 1
		end
		return value, nil, ttl
	end
	local value, err, hit_level
	if self.use_redis then
		value, err, hit_level = self.cache:get(key, nil, callback, key)
	else
		value, err, hit_level = self.cache:get(key)
	end
	if value == nil and hit_level == nil then
		return false, err
	end
	self.logger:log(ngx.INFO, "hit level for " .. key .. " = " .. tostring(hit_level))
	return true, value
end

function cachestore:set(key, value, ex)
	if self.use_redis then
		local ok, err = self.set_redis(key, value, ex)
		if not ok then
			self.logger:log(ngx.ERR, err)
		end
	end
	local ok, err = self.cache:set(key, nil, value)
	if not ok then
		return false, err
	end
	return true
end

function cachestore:set_redis(key, value, ex)
	-- Connect to redis
	local redis, err = clusterstore:connect()
	if not redis then
		return false, "can't connect to redis : " .. err
	end
	-- Set value with ttl
	local default_ex = ttl or 30
	local ok, err = redis:set(key, value, "EX", ex)
	if err then
		clusterstore:close(redis)
		return false, "GET failed : " .. err
	end
	clusterstore:close(redis)
	return true
end

function cachestore:delete(key, value, ex)
	if self.use_redis then
		local ok, err = self.del_redis(key)
		if not ok then
			self.logger:log(ngx.ERR, err)
		end
	end
	local ok, err = self.cache:delete(key)
	if not ok then
		return false, err
	end
	return true
end

function cachestore:del_redis(key)
	-- Connect to redis
	local redis, err = clusterstore:connect()
	if not redis then
		return false, "can't connect to redis : " .. err
	end
	-- Set value with ttl
	local ok, err = redis:del(key)
	if err then
		clusterstore:close(redis)
		return false, "DEL failed : " .. err
	end
	clusterstore:close(redis)
	return true
end

return cachestore
