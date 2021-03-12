local M		= {}
local resolver	= require "resty.dns.resolver"
local resolvers = {%DNS_RESOLVERS%}
local ip	= ngx.var.remote_addr

function M.get_reverse()
	local r, err = resolver:new{nameservers=resolvers, retrans=2, timeout=2000}
	if not r then
		return ""
	end
	local rdns = ""
	local answers, err = r:reverse_query(ip)
	if answers ~= nil and not answers.errcode then
		for ak, av in ipairs(answers) do
			if av.ptrdname then
				rdns = av.ptrdname
				break
			end
		end
	end
	return rdns
end

function M.get_ips(fqdn)
	local r, err = resolver:new{nameservers=resolvers, retrans=2, timeout=2000}
	if not r then
		return ""
	end
	local ips = {}
	local answers, err, tries = r:query(fqdn, nil, {})
	if answers ~= nil then
		for ak, av in ipairs(answers) do
			if av.address then
				table.insert(ips, av.address)
			end
		end
	end
	return ips
end

function M.ip_to_arpa()
	return resolver.arpa_str(ip):gsub("%.in%-addr%.arpa", ""):gsub("%.ip6%.arpa", "")
end

return M
