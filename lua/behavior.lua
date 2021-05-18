local M	= {}

function M.is_banned ()
	return ngx.shared.behavior_ban:get(ngx.var.remote_addr) == true
end

function M.count (status_codes, threshold, count_time, ban_time)
	for k, v in ipairs(status_codes) do
		if v == tostring(ngx.status) then
			local count = ngx.shared.behavior_count:get(ngx.var.remote_addr)
			if count == nil then
				count = 0
			end
			count = count + 1
			local ok, err = ngx.shared.behavior_count:set(ngx.var.remote_addr, count, count_time)
			if not ok then
				ngx.log(ngx.ERR, "[BEHAVIOR] not enough memory allocated to behavior_ip_count")
				return
			end
			if count >= threshold then
				ngx.log(ngx.NOTICE, "[BEHAVIOR] threshold reached for " .. ngx.var.remote_addr .. " (" .. count .. " / " .. threshold .. ") : IP is banned for " .. ban_time .. " seconds")
				local ok, err = ngx.shared.behavior_ban:safe_set(ngx.var.remote_addr, true, ban_time)
				if not ok then
					ngx.log(ngx.ERR, "[BEHAVIOR] not enough memory allocated to behavior_ip_ban")
					return
				end
			end
			break
		end
	end
end

return M
