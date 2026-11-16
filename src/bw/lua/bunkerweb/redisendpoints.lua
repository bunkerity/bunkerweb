local redisendpoints = {}

-- Lua cosockets require brackets even when the port is a separate argument.
function redisendpoints.socket_host(host)
	if host and host:find(":", 1, true) and host:sub(1, 1) ~= "[" then
		return "[" .. host .. "]"
	end
	return host
end

function redisendpoints.parse_endpoint(value, default_port)
	local host, port = value:match("^(%[.+%]):(%d+)$")
	if not host then
		host, port = value:match("^([^:]+):(%d+)$")
	end
	return redisendpoints.socket_host(host or value), tonumber(port) or default_port
end

return redisendpoints
