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

function _M:init()
	-- Check if init is needed
	local init_needed, err = utils.has_variable("USE_LIMIT_REQ", "yes")
	if init_needed == nil then
		return false, err
	end
	if not init_needed then
		return true, "no service uses Limit for requests, skipping init"
	end
	-- Get variables
	local variables, err = utils.get_multiple_variables({"LIMIT_REQ_URL", "LIMIT_REQ_RATE"})
	if variables == nil then
		return false, err
	end
	-- Store URLs and rates
	local data = {}
	local i = 0
	for srv, vars in pairs(variables) do
		for var, value in pairs(vars) do
			if var:match("LIMIT_REQ_URL") then
				local url = value
				local rate = vars[var:gsub("URL", "RATE")]
				if data[srv] == nil then
					data[srv] = {}
				end
				data[srv][url] = rate
				i = i + 1
			end
		end
	end
	local ok, err = datastore:set("plugin_limit_rules", cjson.encode(data))
	if not ok then
		return false, err
	end
	return true, "successfully loaded " .. tostring(i) .. " limit rules for requests"
end

function _M:access()
	-- Check if access is needed
	local access_needed, err = utils.get_variable("USE_LIMIT_REQ")
	if access_needed == nil then
		return false, err, nil, nil
	end
	if access_needed ~= "yes" then
		return true, "Limit for request not activated", nil, nil
	end
	
	-- Don't go further if URL is not limited
	local limited = false
	local all_rules, err = datastore:get("plugin_limit_rules")
	if not all_rules then
		return false, err, nil, nil
	end
	all_rules = cjson.decode(all_rules)
	local limited = false
	local rate = ""
	if not limited and all_rules[ngx.var.server_name] then
		for k, v in pairs(all_rules[ngx.var.server_name]) do
			if ngx.var.uri:match(k) and k ~= "/" then
				limited = true
				rate = all_rules[ngx.var.server_name][k]
				break
			end
		end
	end
	if all_rules.global and not limited then
		for k, v in pairs(all_rules.global) do
			if ngx.var.uri:match(k) and k ~= "/" then
				limited = true
				rate = all_rules.global[k]
				break
			end
		end
	end
	if not limited then
		if all_rules[ngx.var.server_name] and all_rules[ngx.var.server_name]["/"] then
			limited = true
			rate = all_rules[ngx.var.server_name]["/"]
		elseif all_rules.global and all_rules.global["/"] then
			limited = true
			rate = all_rules.global["/"]
		end
		if not limited then
			return true, "URL " .. ngx.var.uri .. " is not limited by a rule, skipping check", nil, nil
		end
	end

	-- Get the rate
	local _, _, rate_max, rate_time = rate:find("(%d+)r/(.)")

	-- Get current requests timestamps
	local requests, err = datastore:get("plugin_limit_cache_" .. ngx.var.server_name .. ngx.var.remote_addr .. ngx.var.uri)
	if not requests and err ~= "not found" then
		return false, err, nil, nil
	elseif err == "not found" then
		requests = "{}"
	end
	
	-- Compute new timestamps
	local new_timestamps = {}
	local current_timestamp = os.time(os.date("!*t"))
	local delay = 0
	if rate_time == "s" then
		delay = 1
	elseif rate_time == "m" then
		delay = 60
	elseif rate_time == "h" then
		delay = 3600
	elseif rate_time == "d" then
		delay = 86400
	end
	for i, timestamp in ipairs(cjson.decode(requests)) do
		if current_timestamp - timestamp <= delay then
			table.insert(new_timestamps, timestamp)
		end
	end
	-- Only insert the new timestamp if client is not limited already to avoid infinite insert
	if #new_timestamps <= tonumber(rate_max) then
		table.insert(new_timestamps, current_timestamp)
	end

	-- Save the new timestamps
	local ok, err = datastore:set("plugin_limit_cache_" .. ngx.var.server_name .. ngx.var.remote_addr .. ngx.var.uri, cjson.encode(new_timestamps), delay)
	if not ok then
		return false, "can't update timestamps : " .. err, nil, nil
	end
	
	-- Deny if the rate is higher than the one defined in rule
	if #new_timestamps > tonumber(rate_max) then
		return true, "client IP " .. ngx.var.remote_addr .. " is limited for URL " .. ngx.var.uri .. " (current rate = " .. tostring(#new_timestamps) .. "r/" .. rate_time .. " and max rate = " .. rate .. ")", true, ngx.HTTP_TOO_MANY_REQUESTS
	end
	
	-- Limit not reached
	return true, "client IP " .. ngx.var.remote_addr .. " is not limited for URL " .. ngx.var.uri .. " (current rate = " .. tostring(#new_timestamps) .. "r/" .. rate_time .. " and max rate = " .. rate .. ")", nil, nil
end

return _M
