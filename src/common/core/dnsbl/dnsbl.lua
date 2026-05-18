local class = require "middleclass"
local ipmatcher = require "resty.ipmatcher"
local plugin = require "bunkerweb.plugin"
local resolver = require "resty.dns.resolver"
local utils = require "bunkerweb.utils"

local dnsbl = class("dnsbl", plugin)

local ngx = ngx
local ERR = ngx.ERR
local INFO = ngx.INFO
local NOTICE = ngx.NOTICE
local get_phase = ngx.get_phase
local spawn = ngx.thread.spawn
local wait = ngx.thread.wait
local arpa_str = resolver.arpa_str
local get_ips = utils.get_ips
local has_variable = utils.has_variable
local get_deny_status = utils.get_deny_status
local kill_all_threads = utils.kill_all_threads
local deduplicate_list = utils.deduplicate_list
local get_variable = utils.get_variable
local ipmatcher_new = ipmatcher.new

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
	-- Decode ignore lists during request phases when needed
	local phase = get_phase()
	if phase ~= "init" and phase ~= "timer" and self:is_needed() then
		-- Load pre-downloaded lists from internalstore if available
		local internalstore_lists, err = self.internalstore:get("plugin_dnsbl_lists_" .. self.ctx.bw.server_name, true)
		if not internalstore_lists then
			self.logger:log(ERR, err)
			self.lists = {}
		else
			-- Create a deep copy to avoid modifying the shared internalstore reference
			self.lists = {}
			for kind, list in pairs(internalstore_lists) do
				self.lists[kind] = {}
				for _, item in ipairs(list) do
					table.insert(self.lists[kind], item)
				end
			end
		end
		-- Ensure kinds and merge with variable values
		local kinds = { ["IGNORE_IP"] = {} }
		for kind, _ in pairs(kinds) do
			if not self.lists[kind] then
				self.lists[kind] = {}
			end
			for data in (self.variables["DNSBL_" .. kind] or ""):gmatch("%S+") do
				if data ~= "" then
					table.insert(self.lists[kind], data)
				end
			end
			self.lists[kind] = deduplicate_list(self.lists[kind])
		end
	end
end

function dnsbl:is_needed()
	-- Loading case
	if self.is_loading then
		return false
	end
	-- Request phases (no default)
	if self.is_request and (self.ctx.bw.server_name ~= "_") then
		return self.variables["USE_DNSBL"] == "yes"
	end
	-- Other cases : at least one service uses it
	local is_needed, err = has_variable("USE_DNSBL", "yes")
	if is_needed == nil then
		self.logger:log(ERR, "can't check USE_DNSBL variable : " .. err)
	end
	return is_needed
end

function dnsbl:init()
	-- Check if init is needed
	if not self:is_needed() then
		return self:ret(true, "init not needed")
	end

	-- Only IGNORE_IP is supported for now
	local lists = { ["IGNORE_IP"] = {} }

	local server_name, err = get_variable("SERVER_NAME", false)
	if not server_name then
		return self:ret(false, "can't get SERVER_NAME variable : " .. err)
	end

	-- Iterate over each server and load cache files
	local i = 0
	for key in server_name:gmatch("%S+") do
		for kind, _ in pairs(lists) do
			local file_path = "/var/cache/bunkerweb/dnsbl/" .. key .. "/" .. kind .. ".list"
			local f = io.open(file_path, "r")
			if f then
				for line in f:lines() do
					if line ~= "" then
						table.insert(lists[kind], line)
						i = i + 1
					end
				end
				f:close()
			end
			lists[kind] = deduplicate_list(lists[kind])
		end

		-- Store service-specific lists into internalstore
		local ok
		ok, err = self.internalstore:set("plugin_dnsbl_lists_" .. key, lists, nil, true)
		if not ok then
			return self:ret(false, "can't store dnsbl " .. key .. " lists into internalstore : " .. err)
		end

		self.logger:log(INFO, "successfully loaded " .. tostring(i) .. " IGNORE_IP entries for the service: " .. key)

		i = 0
		lists = { ["IGNORE_IP"] = {} }
	end
	return self:ret(true, "successfully loaded DNSBL IGNORE_IP lists")
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

	-- Ignore specific IPs/networks if configured
	if self.lists and self.lists["IGNORE_IP"] and #self.lists["IGNORE_IP"] > 0 then
		local ipm, err = ipmatcher_new(self.lists["IGNORE_IP"])
		if not ipm then
			self.logger:log(ERR, "error while building DNSBL ignore matcher: " .. err)
		else
			local match, merr = ipm:match(self.ctx.bw.remote_addr)
			if merr then
				self.logger:log(ERR, "error while matching DNSBL ignore list: " .. merr)
			elseif match then
				-- Cache as OK to avoid repeated checks
				local ok_cache, err_cache = self:add_to_cache(self.ctx.bw.remote_addr, "ok")
				if not ok_cache then
					self.logger:log(ERR, "error while adding element to cache : " .. err_cache)
				end
				return self:ret(true, "client IP " .. self.ctx.bw.remote_addr .. " is ignored for DNSBL checks")
			end
		end
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
