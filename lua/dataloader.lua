local M		= {}
local iputils	= require "resty.iputils"

function M.load_ip (path, dict)
	local file = io.open(path, "r")
	if not file then
		ngx.log(ngx.ERR, "[INIT] can't open " .. path)
	else
		io.input(file)
		local i = 0
		for line in io.lines() do
			if string.match(line, "/") then
				local lower, upper = iputils.parse_cidr(line)
				local bin_ip = lower
				while bin_ip <= upper do
					dict:set(bin_ip, true, 0)
					bin_ip = bin_ip + 1
					i = i + 1
				end
			else
				local bin_ip, bin_octets = iputils.ip2bin(line)
				dict:set(bin_ip, true, 0)
				i = i + 1
			end
		end
		ngx.log(ngx.ERR, "[INIT] loaded " .. tostring(i) .. " IPs from " .. path)
		io.close(file)
	end
end

return M
