local dns		= require "dns"
local ip_list 		= {%WHITELIST_IP_LIST%}
local reverse_list	= {%WHITELIST_REVERSE_LIST%}
local ip		= ngx.var.remote_addr

function ip_cached_ok ()
	return ngx.shared.whitelist_ip_cache:get(ip) == "ok"
end

function reverse_cached_ok ()
	return ngx.shared.whitelist_reverse_cache:get(ip) == "ok"
end

function ip_cached ()
	return ngx.shared.whitelist_ip_cache:get(ip) ~= nil
end

function reverse_cached ()
	return ngx.shared.whitelist_reverse_cache:get(ip) ~= nil
end

function check_ip ()
	for k, v in ipairs(ip_list) do
		if v == ip then
			ngx.shared.whitelist_ip_cache:set(ip, "ok", 86400)
			return true
		end
	end
	ngx.shared.whitelist_ip_cache:set(ip, "ko", 86400)
	return false
end

function check_reverse ()
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
					return true
				end
			end
		end
	end
	ngx.shared.whitelist_reverse_cache:set(ip, "ko", 86400)
	return false
end
