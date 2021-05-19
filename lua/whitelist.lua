local M		= {}
local dns	= require "dns"
local iputils	= require "resty.iputils"
local logger	= require "logger"

function M.ip_cached_ok ()
	return ngx.shared.whitelist_ip_cache:get(ngx.var.remote_addr) == "ok"
end

function M.reverse_cached_ok ()
	return ngx.shared.whitelist_reverse_cache:get(ngx.var.remote_addr) == "ok"
end

function M.ip_cached ()
	return ngx.shared.whitelist_ip_cache:get(ngx.var.remote_addr) ~= nil
end

function M.reverse_cached ()
	return ngx.shared.whitelist_reverse_cache:get(ngx.var.remote_addr) ~= nil
end

function M.check_ip (ip_list)
	if #ip_list > 0 then
		local whitelist	= iputils.parse_cidrs(ip_list)
		if iputils.ip_in_cidrs(ngx.var.remote_addr, whitelist) then
			ngx.shared.whitelist_ip_cache:set(ngx.var.remote_addr, "ok", 86400)
			logger.log(ngx.NOTICE, "WHITELIST", "ip " .. ngx.var.remote_addr .. " is in whitelist")
			return true
		end
	end
	ngx.shared.whitelist_ip_cache:set(ngx.var.remote_addr, "ko", 86400)
	return false
end

function M.check_reverse (reverse_list, resolvers)
	if #reverse_list > 0 then
		local rdns = dns.get_reverse(resolvers)
		if rdns ~= "" then
			local whitelisted = false
			for k, v in ipairs(reverse_list) do
				if rdns:sub(-#v) == v then
					whitelisted = true
					break
				end
			end
			if whitelisted then
				local ips = dns.get_ips(rdns, resolvers)
				for k, v in ipairs(ips) do
					if v == ngx.var.remote_addr then
						ngx.shared.whitelist_reverse_cache:set(ngx.var.remote_addr, "ok", 86400)
						logger.log(ngx.NOTICE, "WHITELIST", "reverse " .. rdns .. " is in whitelist")
						return true
					end
				end
			end
		end
	end
	ngx.shared.whitelist_reverse_cache:set(ngx.var.remote_addr, "ko", 86400)
	return false
end

return M
