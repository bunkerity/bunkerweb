local M		= {}
local redis	= require "resty.redis"

local mt = { __index = M }

function M.new(self, name, data_dict, redis_client, type)
	return setmetatable({
		__name = name,
		__data_dict = data_dict,
		__redis_client = redis_client,
		__type = type
	}, mt)
end

function M.check(self, data)
	-- without redis
	if self.__data_dict ~= nil and self.__redis_client == nil then
		if self.__type == "simple" then
			local value, flags = self.__data_dict:get(data)
			return value ~= nil
		elseif self.__type == "match" then
			local patterns = self.__data_dict:get_keys(0)
			for i, pattern in ipairs(patterns) do
				if string.match(data, pattern) then
					return true
				end
			end
		end

	-- with redis
	elseif self.__data_dict == nil and self.__redis_client ~= nil then
		if self.__type == "simple" then
			local res, err = self.__redis_client:get(self.__name .. "_" .. data)
			return res and res ~= ngx.null
		elseif self.__type == "match" then
			local patterns = self.__redis_client:keys(self.__name .. "_*")
			if patterns then
				for i, pattern in ipairs(patterns) do
					if string.match(data, pattern) then
						return true
					end
				end
			end
		end
	end

	return false

end

return M
