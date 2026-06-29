local ngx = ngx
local class = require "middleclass"
local clogger = require "bunkerweb.logger"
local lrucache = require "resty.lrucache"
local datastore = class("datastore")

local logger = clogger:new("DATASTORE")

local ERR = ngx.ERR
local subsystem = ngx.config.subsystem
local shared = ngx.shared
local match = string.match

-- Default slot count for the per-worker LRU shared by all datastore instances.
-- Overridden via the DATASTORE_LRU_SIZE global setting on the first worker-LRU
-- read/write once the variables store has been populated (lazy: utils.get_variable
-- depends on this very module so resolution is deferred to first call).
local DEFAULT_DATASTORE_LRU = 1000

local lru, err_lru = lrucache.new(DEFAULT_DATASTORE_LRU)
if not lru then
	logger:log(ERR, "failed to instantiate LRU cache : " .. err_lru)
end

-- Parse a count value with optional SI shorthand suffix: "1000", "1k", "10K", "1m".
-- k/K = x1000, m/M = x1_000_000. Returns the integer count, or nil if value is
-- missing or unparsable.
local function parse_count(value)
	if value == nil or value == "" then
		return nil
	end
	local num_str, suffix = match(tostring(value), "^(%d+)([kKmM]?)$")
	if not num_str then
		return nil
	end
	local num = tonumber(num_str)
	if not num then
		return nil
	end
	if suffix == "k" or suffix == "K" then
		return num * 1000
	elseif suffix == "m" or suffix == "M" then
		return num * 1000000
	end
	return num
end

-- Migrate every live entry from the old LRU into a freshly-sized one, preserving
-- per-entry user_flags. The only entries present at resize time are the permanent
-- bootstrap keys (variables/plugins/plugin_*/plugins_order) written during
-- init_by_lua before any request-time TTL cache exists, so re-inserting with
-- ttl=nil keeps them permanent. get_keys/get are direct lrucache calls (no
-- datastore re-entry), so the lru_configuring guard is unaffected.
local function migrate_lru(old_lru, new_lru)
	for _, key in ipairs(old_lru:get_keys(0)) do
		local value, _, flags = old_lru:get(key)
		if value ~= nil then
			new_lru:set(key, value, nil, flags)
		end
	end
	return new_lru
end

local lru_configured = false
local lru_configuring = false
local function ensure_lru_sized()
	if lru_configured or lru_configuring then
		return
	end
	lru_configuring = true
	-- Lazy require to avoid circular load (utils requires this module at the top).
	local ok_utils, utils = pcall(require, "bunkerweb.utils")
	if not ok_utils or type(utils.get_variable) ~= "function" then
		lru_configuring = false
		return
	end
	-- utils.get_variable reads internalstore via the worker LRU, which re-enters
	-- this module; the lru_configuring guard short-circuits the recursion.
	local value = utils.get_variable("DATASTORE_LRU_SIZE", false)
	lru_configuring = false
	if value == nil then
		-- Variables not yet populated; retry on next call.
		return
	end
	lru_configured = true
	local size = parse_count(value)
	-- Only ever grow the shared bootstrap LRU. A size at or below the default could
	-- LRU-evict the init-time bootstrap entries (variables/plugins/...) and deadlock
	-- startup (bug #3618), so sizes <= default keep the safe default-sized cache.
	if not size or size <= DEFAULT_DATASTORE_LRU then
		return
	end
	local new_lru, err = lrucache.new(size)
	if not new_lru then
		logger:log(ERR, "failed to resize datastore LRU to " .. size .. " : " .. err)
		return
	end
	-- Carry existing entries over before swapping so init-time bootstrap data
	-- (written into the old LRU during init_by_lua) survives the resize.
	lru = lru and migrate_lru(lru, new_lru) or new_lru
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
		ensure_lru_sized()
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
		ensure_lru_sized()
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
	for _ = 1, max_retries do
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
		return lru:get_keys(0)
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
		keys = lru:get_keys(0)
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
