local class = require "middleclass"
local plugin = require "bunkerweb.plugin"
local resolver = require "resty.dns.resolver"
local utils = require "bunkerweb.utils"

local dnsbl = class("dnsbl", plugin)

local ngx = ngx
local ERR = ngx.ERR
local NOTICE = ngx.NOTICE
local spawn = ngx.thread.spawn
local wait = ngx.thread.wait
local arpa_str = resolver.arpa_str
local get_ips = utils.get_ips
local has_variable = utils.has_variable
local get_deny_status = utils.get_deny_status
local kill_all_threads = utils.kill_all_threads

local is_in_dnsbl = function(addr, server)
	local request = arpa_str(addr):gsub("%.in%-addr%.arpa", ""):gsub("%.ip6%.arpa", "") .. "." .. server
	local ips, err = get_ips(request, false, nil, true)
	if not ips then
		return nil, server, err
	end
	for _, ip in ipairs(ips) do
		if ip:find "^127%.0%.0%." then
			return true, server
		end
	end
	return false, server
end

function dnsbl:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "dnsbl", ctx)
end

function dnsbl:init_worker()
	-- Check if loading
	if self.is_loading then
		return self:ret(false, "BW is loading")
	end
	-- Check if at least one service uses it
	local is_needed, err = has_variable("USE_DNSBL", "yes")
	if is_needed == nil then
		return self:ret(false, "can't check USE_DNSBL variable : " .. err)
	elseif not is_needed then
		return self:ret(true, "no service uses DNSBL, skipping init_worker")
	end
	-- Loop on DNSBL list
	local threads = {}
	for server in self.variables["DNSBL_LIST"]:gmatch("%S+") do
		-- Create thread
		local thread = spawn(is_in_dnsbl, "127.0.0.2", server)
		threads[server] = thread
	end
	-- Wait for threads
	for data, thread in pairs(threads) do
		-- luacheck: ignore 421
		local ok, result, server, err = wait(thread)
		if not ok then
			self.logger:log(ERR, "error while waiting thread of " .. data .. " check : " .. result)
		elseif result == nil then
			self.logger:log(ERR, "error while sending DNS request to " .. server .. " : " .. err)
		elseif not result then
			self.logger:log(ERR, "dnsbl check for " .. server .. " failed")
		else
			self.logger:log(NOTICE, "dnsbl check for " .. server .. " is successful")
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
	if not self.ctx.bw.ip_is_global then
		return self:ret(true, "client IP is not global, skipping DNSBL check")
	end
	-- Check if IP is in cache
	local ok, cached = self:is_in_cache(self.ctx.bw.remote_addr)
	if not ok then
		return self:ret(false, "error while checking cache : " .. cached)
	elseif cached then
		if cached == "ok" then
			return self:ret(true, "client IP " .. self.ctx.bw.remote_addr .. " is in DNSBL cache (not blacklisted)")
		end
		self:set_metric("counters", "failed_dnsbl", 1)
		return self:ret(
			true,
			"client IP " .. self.ctx.bw.remote_addr .. " is in DNSBL cache (server = " .. cached .. ")",
			get_deny_status(),
			nil,
			{
				id = "dnsbl",
				dnsbl = cached,
			}
		)
	end
	-- Loop on DNSBL list
	local threads = {}
	for server in self.variables["DNSBL_LIST"]:gmatch("%S+") do
		-- Create thread
		local thread = spawn(is_in_dnsbl, self.ctx.bw.remote_addr, server)
		threads[server] = thread
	end
	-- Wait for threads
	local ret_threads = nil
	local ret_err = nil
	local ret_server = nil
	while true do
		-- Compute threads to wait
		local wait_threads = {}
		for _, thread in pairs(threads) do
			table.insert(wait_threads, thread)
		end
		-- No server reported IP
		if #wait_threads == 0 then
			break
		end
		-- Wait for first thread
		-- luacheck: ignore 421
		local ok, result, server, err = wait(unpack(wait_threads))
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
			self.logger:log(ERR, "error while sending DNS request to " .. server .. " : " .. err)
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
			for _, thread in pairs(threads) do
				table.insert(wait_threads, thread)
			end
			kill_all_threads(wait_threads)
		end
		-- Blacklisted by a server : add to cache and deny access
		if ret_threads then
			local ok, err = self:add_to_cache(self.ctx.bw.remote_addr, ret_server)
			if not ok then
				return self:ret(false, "error while adding element to cache : " .. err)
			end
			return self:ret(
				true,
				"IP is blacklisted by " .. ret_server,
				get_deny_status(),
				nil,
				{ id = "dnsbl", dnsbl = ret_server }
			)
		end
		-- Error case
		return self:ret(false, ret_err)
	end
	-- IP is not in DNSBL
	local ok, err = self:add_to_cache(self.ctx.bw.remote_addr, "ok")
	if not ok then
		return self:ret(false, "IP is not in DNSBL (error = " .. err .. ")")
	end
	return self:ret(true, "IP is not in DNSBL")
end

function dnsbl:preread()
	return self:access()
end

function dnsbl:is_in_cache(ip)
	local ok, data = self.cachestore_local:get("plugin_dnsbl_" .. self.ctx.bw.server_name .. ip)
	if not ok then
		return false, data
	end
	return true, data
end

function dnsbl:add_to_cache(ip, value)
	local ok, err = self.cachestore_local:set("plugin_dnsbl_" .. self.ctx.bw.server_name .. ip, value, 86400)
	if not ok then
		return false, err
	end
	return true
end

return dnsbl
