local _M = {}
_M.__index = _M

local utils			= require "utils"
local datastore		= require "datastore"
local logger		= require "logger"
local cjson			= require "cjson"
local resolver		= require "resty.dns.resolver"
local clusterstore	= require "clusterstore"

function _M.new()
	local self = setmetatable({}, _M)
	return self, nil
end

function _M:init()
	-- Check if init is needed
	local use_redis, err = utils.get_variable("USE_REDIS", false)
	if use_redis == nil then
		return false, "can't check USE_REDIS variable : " .. err
	end
	if use_redis ~= "yes" then
		return true, "redis not used"
	end
	-- Check redis connection
	local redis_client, err = clusterstore:connect()
	if not redis_client then
		return false, "can't connect to redis server"
	end
	local ok, err = redis_client:ping()
	if err then
		clusterstore:close(redis_client)
		return false, "error while sending ping command : " .. err
	end
	if not ok then
		clusterstore:close(redis_client)
		return false, "ping command failed"
	end
	clusterstore:close(redis_client)
	return true, "redis ping successful"
end

return _M
