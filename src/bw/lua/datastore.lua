
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
