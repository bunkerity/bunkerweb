local M		= {}
local dns	= require "dns"
local iputils	= require "resty.iputils"
local logger	= require "logger"

function M.ip_cached_ko ()
	return ngx.shared.blacklist_ip_cache:get(ngx.var.remote_addr) == "ko"
end

function M.reverse_cached_ko ()
	return ngx.shared.blacklist_reverse_cache:get(ngx.var.remote_addr) == "ko"
end

function M.ip_cached ()
	return ngx.shared.blacklist_ip_cache:get(ngx.var.remote_addr) ~= nil
end

function M.reverse_cached ()
	return ngx.shared.blacklist_reverse_cache:get(ngx.var.remote_addr) ~= nil
end

function M.check_ip (ip_list)
	if #ip_list > 0 then
		local blacklist = iputils.parse_cidrs(ip_list)
		if iputils.ip_in_cidrs(ngx.var.remote_addr, blacklist) then
			ngx.shared.blacklist_ip_cache:set(ngx.var.remote_addr, "ko", 86400)
			logger.log(ngx.WARN, "BLACKLIST", "ip " .. ngx.var.remote_addr .. " is in blacklist")
			return true
		end
	end
	ngx.shared.blacklist_ip_cache:set(ngx.var.remote_addr, "ok", 86400)
	return false
end

function M.check_reverse (reverse_list, resolvers)
	if #reverse_list > 0 then
		local rdns = dns.get_reverse(resolvers)
		if rdns ~= "" then
			for k, v in ipairs(reverse_list) do
				if rdns:sub(-#v) == v then
					ngx.shared.blacklist_reverse_cache:set(ngx.var.remote_addr, "ko", 86400)
					logger.log(ngx.WARN, "BLACKLIST", "reverse " .. rdns .. " is in blacklist")
					return true
				end
			end
		end
	end
	ngx.shared.blacklist_reverse_cache:set(ngx.var.remote_addr, "ok", 86400)
	return false
end

return M
