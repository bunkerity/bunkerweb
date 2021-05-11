local M		= {}
local iputils	= require "resty.iputils"

function M.flush_dict (dict)
	local keys = dict:get_keys(0)
	for i, key in ipairs(keys) do
		dict:delete(key)
	end
end

function M.load_ip (path, dict)
	M.flush_dict(dict)
	local file = io.open(path, "r")
	if not file then
		ngx.log(ngx.ERR, "[INIT] can't open " .. path)
	else
		io.input(file)
		local i = 0
		for line in io.lines() do
			local continue = true
			if string.match(line, "/") then
				local lower, upper = iputils.parse_cidr(line)
				local bin_ip = lower
				while bin_ip <= upper do
					local ok, err = dict:safe_set(bin_ip, true, 0)
					if not ok then
						ngx.log(ngx.ERR, "[INIT] not enough memory allocated to load data from " .. path) 
						continue = false
						break
					end
					bin_ip = bin_ip + 1
					i = i + 1
				end
			else
				local bin_ip, bin_octets = iputils.ip2bin(line)
				dict:set(bin_ip, true, 0)
				i = i + 1
			end
			if not continue then
				break
			end
		end
		ngx.log(ngx.ERR, "[INIT] *NOT AN ERROR* loaded " .. tostring(i) .. " IPs from " .. path)
		io.close(file)
	end
end

function M.load_raw (path, dict)
	M.flush_dict(dict)
	local file = io.open(path, "r")
	if not file then
		ngx.log(ngx.ERR, "[INIT] can't open " .. path)
	else
		io.input(file)
		local i = 0
		for line in io.lines() do
			local ok, err = dict:safe_set(line, true, 0)
			if not ok then
				ngx.log(ngx.ERR, "[INIT] not enough memory allocated to load data from " .. path) 
				break
			end
			i = i + 1
		end
		ngx.log(ngx.ERR, "[INIT] *NOT AN ERROR* loaded " .. tostring(i) .. " entries from " .. path)
		io.close(file)
	end
end

return M
