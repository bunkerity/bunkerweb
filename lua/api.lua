local M		= {}
local api_uri	= ngx.var.api_uri
local api_list	= {}

api_list["^/reload$"] = function ()
	return os.execute("/usr/sbin/nginx -s reload") == 0
end

function M.is_api_call ()
	if ngx.var.request_uri:sub(1, #api_uri) .. "/" == api_uri .. "/" then
		for uri, code in pairs(api_list) do
			if string.match(ngx.var.request_uri:sub(#api_uri + 1), uri) then
				return true
			end
		end
	end
	return false
end

function M.do_api_call ()
	for uri, code in pairs(api_list) do
		if string.match(ngx.var.request_uri:sub(#api_uri + 1), uri) then
			return code()
		end
	end
end

return M
