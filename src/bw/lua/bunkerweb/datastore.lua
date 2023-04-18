local class     = require "middleclass"
local datastore	= class("datastore")

function datastore:initialize()
	self.dict = ngx.shared.datastore
	if not self.dict then
		self.dict = ngx.shared.datastore_stream
	end
end

function datastore:get(key)
	local value, err = self.dict:get(key)
	if not value and not err then
		err = "not found"
	end
	return value, err
end

function datastore:set(key, value, exptime)
	exptime = exptime or 0
	return self.dict:safe_set(key, value, exptime)
end

function datastore:delete(key)
	self.dict:delete(key)
	return true, "success"
end

function datastore:keys()
	return self.dict:get_keys(0)
end

function datastore:exp(key)
	local ttl, err = self.dict:ttl(key)
	if not ttl then
		return false, err
	end
	return true, ttl
end

function datastore:delete_all(pattern)
	local keys = self.dict:get_keys(0)
	for i, key in ipairs(keys) do
		if key:match(pattern) then
			self.dict:delete(key)
		end
	end
	return true, "success"
end

return datastore