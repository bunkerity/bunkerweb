local M		= {}
local logger	= require "logger"

function M.decr (key, delay)
	local function callback (premature, key)
		if premature then
			ngx.shared.limit_req:delete(key)
			return
		end
		local value, flags = ngx.shared.limit_req:get(key)
		if value ~= nil then
			if value - 1 == 0 then
				ngx.shared.limit_req:delete(key)
				return
			end
			ngx.shared.limit_req:set(key, value-1, 0)
		end
	end
	local hdl, err = ngx.timer.at(delay, callback, key)
	if not ok then
		logger.log(ngx.ERR, "REQ LIMIT", "can't setup decrement timer : " .. err)
		return false
	end
	return true
end

function M.incr (key)
	local newval, err, forcible = ngx.shared.limit_req:incr(key, 1, 0, 0)
	if not newval then
		logger.log(ngx.ERR, "REQ LIMIT", "can't increment counter : " .. err)
		return false
	end
	return true
end

function M.check (url, rate)
	if url == "/" or url == ngx.var.request_uri then
		local key = ngx.var.remote_addr .. url
		local rate_split = rate:gmatch("([^/]+)")
		local max = rate_split[1]
		local unit = rate_split[2]
		local delay = 0
		if unit == "s" then
			delay = 1
		elseif unit == "m" then
			delay = 60
		elseif unit == "h" then
			delay = 3600
		elseif unit == "d" then
			delay = 86400
		end
		if M.incr(key) then
			local current, flags = ngx.shared.limit_req:get(key)
			if M.decr(key, delay) then
				if current > max then
					logger.log(ngx.WARN, "REQ LIMIT", "ip " .. ngx.var.remote_addr .. " has reached the limit : " .. current .. "/" .. unit .. " (max = " .. rate .. ")")
					return true
				end
			else
				ngx.shared.limit_req:set(key, current-1, 0)
			end
		end
	end
	return false	
end

return M
