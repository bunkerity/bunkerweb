local class      = require "middleclass"
local plugin     = require "bunkerweb.plugin"
local utils      = require "bunkerweb.utils"
local cachestore = require "bunkerweb.cachestore"
local cjson      = require "cjson"
local resolver   = require "resty.dns.resolver"

local dnsbl      = class("dnsbl", plugin)

function dnsbl:initialize()
	-- Call parent initialize
	plugin.initialize(self, "dnsbl")
end

function dnsbl:init_worker()
	-- Check if loading
	if self.is_loading then
		return self:ret(false, "BW is loading")
	end
	-- Check if at least one service uses it
	local is_needed, err = utils.has_variable("USE_DNSBL", "yes")
	if is_needed == nil then
		return self:ret(false, "can't check USE_DNSBL variable : " .. err)
	elseif not is_needed then
		return self:ret(true, "no service uses DNSBL, skipping init_worker")
	end
	-- Loop on DNSBL list
	local threads = {}
	for server in self.variables["DNSBL_LIST"]:gmatch("%S+") do
		-- Create thread
		local thread = ngx.thread.spawn(self.is_in_dnsbl, self, "127.0.0.2", server)
		threads[server] = thread
	end
	-- Wait for threads
	for dnsbl, thread in pairs(threads) do
		local ok, result, server, err = ngx.thread.wait(thread)
		if not ok then
			self.logger:log(ngx.ERR, "error while waiting thread of " .. dnsbl .. " check : " .. result)
		elseif result == nil then
			self.logger:log(ngx.ERR, "error while sending DNS request to " .. server .. " : " .. err)
		elseif not result then
			self.logger:log(ngx.ERR, "dnsbl check for " .. server .. " failed")
		else
			self.logger:log(ngx.NOTICE, "dnsbl check for " .. server .. " is successful")
		end
	end
	return self:ret(true, "success")
end

function dnsbl:access()
	-- Check if access is needed
	if self.variables["USE_DNSBL"] ~= "yes" then
		return self:ret(true, "dnsbl not activated")
	end
	if self.variables["DNSBL_LIST"] == "" then
		return self:ret(true, "dnsbl list is empty")
	end
	-- Don't go further if IP is not global
	if not ngx.ctx.bw.ip_is_global then
		return self:ret(true, "client IP is not global, skipping DNSBL check")
	end
	-- Check if IP is in cache
	local ok, cached = self:is_in_cache(ngx.ctx.bw.remote_addr)
	if not ok then
		return self:ret(false, "error while checking cache : " .. cached)
	elseif cached then
		if cached == "ok" then
			return self:ret(true, "client IP " .. ngx.ctx.bw.remote_addr .. " is in DNSBL cache (not blacklisted)")
		end
		return self:ret(true, "client IP " .. ngx.ctx.bw.remote_addr .. " is in DNSBL cache (server = " .. cached .. ")",
			utils.get_deny_status())
	end
	-- Loop on DNSBL list
	local threads = {}
	for server in self.variables["DNSBL_LIST"]:gmatch("%S+") do
		-- Create thread
		local thread = ngx.thread.spawn(self.is_in_dnsbl, self, ngx.ctx.bw.remote_addr, server)
		threads[server] = thread
	end
	-- Wait for threads
	local ret_threads = nil
	local ret_err = nil
	local ret_server = nil
	while true do
		-- Compute threads to wait
		local wait_threads = {}
		for dnsbl, thread in pairs(threads) do
			table.insert(wait_threads, thread)
		end
		-- No server reported IP
		if #wait_threads == 0 then
			break
		end
		-- Wait for first thread
		local ok, result, server, err = ngx.thread.wait(unpack(wait_threads))
		-- Error case
		if not ok then
			ret_threads = false
			ret_err = "error while waiting thread : " .. result
			break
		end
		-- Remove thread from list
		threads[server] = nil
		-- DNS error
		if result == nil then
			self.logger:log(ngx.ERR, "error while sending DNS request to " .. server .. " : " .. err)
		end
		-- IP is in DNSBL
		if result then
			ret_threads = true
			ret_err = "IP is blacklisted by " .. server
			ret_server = server
			break
		end
	end
	if ret_threads ~= nil then
		-- Kill other threads
		if #threads > 0 then
			local wait_threads = {}
			for dnsbl, thread in pairs(threads) do
				table.insert(wait_threads, thread)
			end
			utils.kill_all_threads(wait_threads)
		end
		-- Blacklisted by a server : add to cache and deny access
		if ret_threads then
			local ok, err = self:add_to_cache(ngx.ctx.bw.remote_addr, ret_server)
			if not ok then
				return self:ret(false, "error while adding element to cache : " .. err)
			end
			return self:ret(true, "IP is blacklisted by " .. ret_server, utils.get_deny_status())
		end
		-- Error case
		return self:ret(false, ret_err)
	end
	-- IP is not in DNSBL
	local ok, err = self:add_to_cache(ngx.ctx.bw.remote_addr, "ok")
	if not ok then
		return self:ret(false, "IP is not in DNSBL (error = " .. err .. ")")
	end
	return self:ret(true, "IP is not in DNSBL")
end

function dnsbl:preread()
	return self:access()
end

function dnsbl:is_in_cache(ip)
	local ok, data = self.cachestore:get("plugin_dnsbl_" .. ngx.ctx.bw.server_name .. ip)
	if not ok then
		return false, data
	end
	return true, data
end

function dnsbl:add_to_cache(ip, value)
	local ok, err = self.cachestore:set("plugin_dnsbl_" .. ngx.ctx.bw.server_name .. ip, value, 86400)
	if not ok then
		return false, err
	end
	return true
end

function dnsbl:is_in_dnsbl(ip, server)
	local request = resolver.arpa_str(ip):gsub("%.in%-addr%.arpa", ""):gsub("%.ip6%.arpa", "") .. "." .. server
	local ips, err = utils.get_ips(request, false)
	if not ips then
		return nil, server, err
	end
	for i, ip in ipairs(ips) do
		if ip:find("^127%.0%.0%.") then
			return true, server
		end
	end
	return false, server
end

return dnsbl
