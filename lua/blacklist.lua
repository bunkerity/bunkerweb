local M			= {}
local dns		= require "dns"
local ip_list 		= {%BLACKLIST_IP_LIST%}
local reverse_list	= {%BLACKLIST_REVERSE_LIST%}
local ip		= ngx.var.remote_addr

function M.ip_cached_ko ()
	return ngx.shared.blacklist_ip_cache:get(ip) == "ko"
end

function M.reverse_cached_ko ()
	return ngx.shared.blacklist_reverse_cache:get(ip) == "ko"
end

function M.ip_cached ()
	return ngx.shared.blacklist_ip_cache:get(ip) ~= nil
end

function M.reverse_cached ()
	return ngx.shared.blacklist_reverse_cache:get(ip) ~= nil
end

function M.check_ip ()
	for k, v in ipairs(ip_list) do
		if v == ip then
			ngx.shared.blacklist_ip_cache:set(ip, "ko", 86400)
			ngx.log(ngx.WARN, "ip " .. ip .. " is in blacklist")
			return true
		end
	end
	ngx.shared.blacklist_ip_cache:set(ip, "ok", 86400)
	return false
end

function M.check_reverse ()
	local rdns = dns.get_reverse()
	if rdns ~= "" then
		for k, v in ipairs(reverse_list) do
			if rdns:sub(-#v) == v then
				ngx.shared.blacklist_reverse_cache:set(ip, "ko", 86400)
				ngx.log(ngx.WARN, "reverse " .. rdns .. " is in blacklist")
				return true
			end
		end
	end
	ngx.shared.blacklist_reverse_cache:set(ip, "ok", 86400)
	return false
end

return M
