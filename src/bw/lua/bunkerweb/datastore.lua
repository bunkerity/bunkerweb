local class     = require "middleclass"
local lrucache 	= require "resty.lrucache"
local datastore = class("datastore")

local lru, err = lrucache.new(10000)
if not lru then
	require "bunkerweb.logger":new("DATASTORE"):log(ngx.ERR, "failed to instantiate LRU cache : " .. (err or "unknown error"))
end

function datastore:initialize()
	self.dict = ngx.shared.datastore
	if not self.dict then
		self.dict = ngx.shared.datastore_stream
	end
end

function datastore:get(key, worker)
	if worker then
		local value, err = lru:get(key)
		return value, err or "not found"
	end
	local value, err = self.dict:get(key)
	if not value and not err then
		err = "not found"
	end
	return value, err
end

function datastore:set(key, value, exptime, worker)
	if worker then
		lru:set(key, value, exptime)
		return true, "success"
	end
	exptime = exptime or 0
	return self.dict:safe_set(key, value, exptime)
end

function datastore:delete(key, worker)
	if worker then
		lru:delete(key)
		return true, "success"
	end
	self.dict:delete(key)
	return true, "success"
end

function datastore:keys(worker)
	if worker then
		return lru:keys(0)
	end
	return self.dict:get_keys(0)
end

function datastore:ttl(key)
	if worker then
		return false, "no supported for LRU"
	end
	local ttl, err = self.dict:ttl(key)
	if not ttl then
		return false, err
	end
	return true, ttl
end

function datastore:delete_all(pattern, worker)
	local keys = {}
	if worker then
		lru:keys(0)
	else
		local keys = self.dict:get_keys(0)
	end
	for i, key in ipairs(keys) do
		if key:match(pattern) then
			self.dict:delete(key)
		end
	end
	return true, "success"
end

function datastore:flush_lru()
	lru:flush_all()
end

return datastore
