local ngx = ngx
local class = require "middleclass"
local clogger = require "bunkerweb.logger"
local lrucache = require "resty.lrucache"
local datastore = class("datastore")

local logger = clogger:new("DATASTORE")

local ERR = ngx.ERR
local subsystem = ngx.config.subsystem
local shared = ngx.shared

local lru, err_lru = lrucache.new(100000)
if not lru then
	logger:log(ERR, "failed to instantiate LRU cache : " .. err_lru)
end

function datastore:initialize(dict)
	if dict then
		self.dict = dict
	elseif subsystem == "http" then
		self.dict = shared.datastore
	else
		self.dict = shared.datastore_stream
	end
end

function datastore:get(key, worker)
	-- luacheck: ignore 431
	local value, err
	if worker then
		if not lru then
			return nil, "lru is not instantiated"
		end
		value, err = lru:get(key)
		return value, err or "not found"
	end
	value, err = self.dict:get(key)
	if not value and not err then
		err = "not found"
	end
	return value, err
end

function datastore:set(key, value, exptime, worker)
	if worker then
		if not lru then
			return false, "lru is not instantiated"
		end
		lru:set(key, value, exptime)
		return true, "success"
	end
	if exptime == nil or exptime < 0 then
		return self.dict:safe_set(key, value)
	else
		return self.dict:safe_set(key, value, exptime)
	end
end

function datastore:set_with_retries(key, value, exptime, max_retries)
    max_retries = max_retries or 5
    local success, err
	-- Try multiple times if we need to make room for the new value
    for i = 1, max_retries do
        if exptime == nil or exptime < 0 then
            success, err = self.dict:set(key, value)
        else
            success, err = self.dict:set(key, value, exptime)
        end
        -- Ok case
        if success then
            return true, "success"
        end
        -- Unknown error, can't do nothing
        if err ~= "no memory" then
            return false, err
        end
    end
    return false, err or "max retries reached"
end

function datastore:delete(key, worker)
	if worker then
		if not lru then
			return false, "lru is not instantiated"
		end
		lru:delete(key)
		return true, "success"
	end
	self.dict:delete(key)
	return true, "success"
end

function datastore:keys(worker)
	if worker then
		if not lru then
			return false, "lru is not instantiated"
		end
		return lru:keys(0)
	end
	return self.dict:get_keys(0)
end

function datastore:ttl(key, worker)
	if worker then
		return false, "not supported by LRU"
	end
	-- luacheck: ignore 431
	local ttl, err = self.dict:ttl(key)
	if err then
		return false, err
	end
	if not ttl then
		return true, 0
	end
	return true, ttl
end

function datastore:delete_all(pattern, worker)
	local keys
	if worker then
		if not lru then
			return false, "lru is not instantiated"
		end
		keys = lru:keys(0)
	else
		keys = self.dict:get_keys(0)
	end
	for _, key in ipairs(keys) do
		if key:match(pattern) then
			self.dict:delete(key)
		end
	end
	return true, "success"
end

-- luacheck: ignore 212
function datastore:flush_lru()
	if not lru then
		return false, "lru is not instantiated"
	end
	lru:flush_all()
end

function datastore:safe_rpush(key, value)
	local length, err = self.dict:rpush(key, value)
	if not length and err == "no memory" then
		local i = 0
		while i < 5 do
			local val
			val, err = self.dict:lpop(key)
			if not val then
				return val, err
			end
			length, err = self.dict:rpush(key, value)
			if not length and err ~= "no memory" then
				return length, err
			end
			i = i + 1
		end
	end
	return length, err
end

function datastore:lpop(key)
	return self.dict:lpop(key)
end

function datastore:llen(key)
	return self.dict:llen(key)
end

return datastore
