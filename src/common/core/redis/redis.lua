local _M = {}
_M.__index = _M

local utils		= require "utils"
local datastore	= require "datastore"
local logger	= require "logger"
local cjson		= require "cjson"
local resolver	= require "resty.dns.resolver"

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
	-- TODO : check redis connectivity
	return true, "redis ping successful"
end

return _M
