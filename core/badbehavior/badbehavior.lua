local _M = {}
_M.__index = _M

local utils		= require "utils"
local datastore	= require "datastore"
local logger	= require "logger"
local cjson		= require "cjson"

function _M.new()
	local self = setmetatable({}, _M)
	return self, nil
end

function _M:log()
	self.use			= utils.get_variable("USE_BAD_BEHAVIOR")
	self.ban_time		= utils.get_variable("BAD_BEHAVIOR_BAN_TIME")
	self.status_codes	= utils.get_variable("BAD_BEHAVIOR_STATUS_CODES")
	self.threshold		= utils.get_variable("BAD_BEHAVIOR_THRESHOLD")
	self.count_time		= utils.get_variable("BAD_BEHAVIOR_COUNT_TIME")
	if self.use ~= "yes" then
		return true, "bad behavior not activated"
	end
	if not self.status_codes:match(tostring(ngx.status)) then
		return true, "not increasing counter"
	end
	local count, err = datastore:get("plugin_badbehavior_count_" .. ngx.var.remote_addr)
	if not count and err ~= "not found" then
		return false, "can't get counts from the datastore : " .. err
	end
	local new_count = 1
	if count ~= nil then
		new_count = count + 1
	end
	local ok, err = datastore:set("plugin_badbehavior_count_" .. ngx.var.remote_addr, new_count)
	if not ok then
		return false, "can't save counts to the datastore : " .. err
	end
	local function decrease_callback(premature, ip)
		local count, err = datastore:get("plugin_badbehavior_count_" .. ip)
		if err then
			logger.log(ngx.ERR, "BAD-BEHAVIOR", "(decrease_callback) Can't get counts from the datastore : " .. err)
			return
		end
		if not count then
			logger.log(ngx.ERR, "BAD-BEHAVIOR", "(decrease_callback) Count is null")
			return
		end
		local new_count = count - 1
		if new_count <= 0 then
			datastore:delete("plugin_badbehavior_count_" .. ip)
			return
		end
		local ok, err = datastore:set("plugin_badbehavior_count_" .. ip, new_count)
		if not ok then
			logger.log(ngx.ERR, "BAD-BEHAVIOR", "(decrease_callback) Can't save counts to the datastore : " .. err)
		end
	end
	local hdr, err = ngx.timer.at(tonumber(self.count_time), decrease_callback, ngx.var.remote_addr)
	if not ok then
		return false, "can't create decrease timer : " .. err
	end
	if new_count > tonumber(self.threshold) then
		local ok, err = datastore:set("bans_ip_" .. ngx.var.remote_addr, "bad behavior", tonumber(self.ban_time))
		if not ok then
			return false, "can't save ban to the datastore : " .. err
		end
		logger.log(ngx.WARN, "BAD-BEHAVIOR", "IP " .. ngx.var.remote_addr .. " is banned for " .. tostring(self.ban_time) .. "s (" .. tostring(new_count) .. "/" .. tostring(self.threshold) .. ")")
	end
	return true, "success"
end

return _M
