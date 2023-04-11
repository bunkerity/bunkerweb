local mlcache	= require "resty.mlcache"
local clogger	= require "bunkerweb.logger"
local class     = require "middleclass"
local datastore	= class("datastore")

-- Instantiate mlcache objects at module level (which will be cached when running init phase)
-- TODO : shm_miss, shm_locks
local shm		= "datastore"
local ipc_shm	= "datastore_ipc"
if not ngx.shared.datastore then
	shm		= "datastore_stream"
	ipc_shm	= "datastore_ipc_stream"
end
local store, err = mlcache.new(
	"datastore",
	shm,
	{
		lru_size = 100,
		ttl = 0,
		neg_ttl = 0,
		shm_set_tries = 1,
		ipc_shm = ipc_shm
	}
)
local logger = clogger:new("DATASTORE")
if not store then
	logger:log(ngx.ERR, "can't instantiate mlcache : " .. err)
end

function datastore:new()
	self.store = store
	self.logger = logger
end

function datastore:get(key)
	local value, err, hit_level = self.store:get(key)
	if err then
		return false, err
	end
	self.logger:log(ngx.INFO, "hit level for " .. key .. " = " .. tostring(hit_level))
	return true, value
end

function datastore:set(key, value)
	local ok, err = self.store:set(key, nil, value)
	if not ok then
		return false, err
	end
	return true
end

local datastore = { dict = ngx.shared.datastore }

if not datastore.dict then
	datastore.dict = ngx.shared.datastore_stream
end

datastore.get = function(self, key)
	local value, err = self.dict:get(key)
	if not value and not err then
		err = "not found"
	end
	return value, err
end

datastore.set = function(self, key, value, exptime)
	exptime = exptime or 0
	return self.dict:safe_set(key, value, exptime)
end

datastore.keys = function(self)
	return self.dict:get_keys(0)
end

datastore.delete = function(self, key)
	self.dict:delete(key)
	return true, "success"
end

datastore.exp = function(self, key)
	local ttl, err = self.dict:ttl(key)
	if not ttl then
		return false, err
	end
	return true, ttl
end

datastore.delete_all = function(self, pattern)
	local keys = self.dict:get_keys(0)
	for i, key in ipairs(keys) do
		if key:match(pattern) then
			self.dict:delete(key)
		end
	end
	return true, "success"
end

return datastore
