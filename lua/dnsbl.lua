local M		= {}
local dns	= require "dns"
local logger	= require "logger"
local iputils	= require "resty.iputils"

function M.cached_ko ()
	return ngx.shared.dnsbl_cache:get(ngx.var.remote_addr) == "ko"
end

function M.cached ()
	return ngx.shared.dnsbl_cache:get(ngx.var.remote_addr) ~= nil
end

function M.check (dnsbls, resolvers)
	local local_ips = iputils.parse_cidrs({"127.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "10.0.0.0/8"})
	if iputils.ip_in_cidrs(ngx.var.remote_addr, local_ips) then
		ngx.shared.dnsbl_cache:set(ngx.var.remote_addr, "ok", 86400)
		return false
	end
	local rip = dns.ip_to_arpa()
	for k, v in ipairs(dnsbls) do
		local req = rip .. "." .. v
		local ips = dns.get_ips(req, resolvers)
		for k2, v2 in ipairs(ips) do
			local a,b,c,d = v2:match("([%d]+).([%d]+).([%d]+).([%d]+)")
			if a == "127" then
				ngx.shared.dnsbl_cache:set(ngx.var.remote_addr, "ko", 86400)
				logger.log(ngx.WARN, "DNSBL", "ip " .. ngx.var.remote_addr .. " is in DNSBL " .. v)
				return true
			end
		end
	end
	ngx.shared.dnsbl_cache:set(ngx.var.remote_addr, "ok", 86400)
	return false
end

return M
