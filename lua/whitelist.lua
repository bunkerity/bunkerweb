local M			= {}
local dns		= require "dns"
local iputils		= require "resty.iputils"
local ip_list 		= {%WHITELIST_IP_LIST%}
local reverse_list	= {%WHITELIST_REVERSE_LIST%}
local ip		= ngx.var.remote_addr

function M.ip_cached_ok ()
	return ngx.shared.whitelist_ip_cache:get(ip) == "ok"
end

function M.reverse_cached_ok ()
	return ngx.shared.whitelist_reverse_cache:get(ip) == "ok"
end

function M.ip_cached ()
	return ngx.shared.whitelist_ip_cache:get(ip) ~= nil
end

function M.reverse_cached ()
	return ngx.shared.whitelist_reverse_cache:get(ip) ~= nil
end

function M.check_ip ()
	if #ip_list > 0 then
		local whitelist = iputils.parse_cidrs(ip_list)
		if iputils.ip_in_cidrs(ip, whitelist) then
			ngx.shared.whitelist_ip_cache:set(ip, "ok", 86400)
			ngx.log(ngx.WARN, "ip " .. ip .. " is in whitelist")
			return true
		end
	end
	ngx.shared.whitelist_ip_cache:set(ip, "ko", 86400)
	return false
end

function M.check_reverse ()
	if #reverse_list > 0 then
		local rdns = dns.get_reverse()
		if rdns ~= "" then
			local whitelisted = false
			for k, v in ipairs(reverse_list) do
				if rdns:sub(-#v) == v then
					whitelisted = true
					break
				end
			end
			if whitelisted then
				local ips = dns.get_ips(rdns)
				for k, v in ipairs(ips) do
					if v == ip then
						ngx.shared.whitelist_reverse_cache:set(ip, "ok", 86400)
						ngx.log(ngx.WARN, "reverse " .. rdns .. " is in whitelist")
						return true
					end
				end
			end
		end
	end
	ngx.shared.whitelist_reverse_cache:set(ip, "ko", 86400)
	return false
end

return M
