local class = require "middleclass"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"

local reversescan = class("reversescan", plugin)

local ngx = ngx
local spawn = ngx.thread.spawn
local wait = ngx.thread.wait
local ngx_socket = ngx.socket
local kill_all_threads = utils.kill_all_threads
local get_deny_status = utils.get_deny_status
local tonumber = tonumber
local WARN = ngx.WARN

function reversescan:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "reversescan", ctx)
end

function reversescan:access()
	-- Check if access is needed
	if self.variables["USE_REVERSE_SCAN"] ~= "yes" then
		return self:ret(true, "reverse scan not activated")
	end
	-- Loop on ports
	local threads = {}
	local ret_threads = nil
	local ret_err = nil
	-- One failure is enough to know the cachestore is unusable for this request. A Redis that
	-- drops packets rather than refusing them makes every call pay REDIS_TIMEOUT in full
	-- (1000 ms by default), so retrying it once per port would cost #REVERSE_SCAN_PORTS
	-- timeouts here plus as many again in the write loop below -- 12 s on the access path with
	-- the default six ports, i.e. a connection-holding vector under a flood of new IPs.
	local cache_down = false
	for port in self.variables["REVERSE_SCAN_PORTS"]:gmatch("%S+") do
		-- Check if the scan is already cached
		local cached = nil
		if not cache_down then
			-- A cachestore failure must not skip the scan. This used to abort access() with
			-- ret(false), which the plugin runner logs and steps over -- so an unreachable or
			-- desynced Redis silently turned reverse scan off and the request was served
			-- unscanned. The cache is an optimization; losing it costs a round of connects,
			-- not the enforcement.
			local ok, data = self:is_in_cache(self.ctx.bw.remote_addr .. ":" .. port)
			if ok then
				cached = data
			else
				self.logger:log(WARN, "error getting info from cachestore : " .. data .. ", scanning anyway")
				cache_down = true
			end
		end
		if cached == "open" then
			-- Deny access if port opened
			ret_threads = true
			ret_err = "port " .. port .. " is opened for IP " .. self.ctx.bw.remote_addr
			self:set_metric("counters", "failed_" .. port, 1)
			break
			-- Perform scan in a thread
		elseif not cached then
			local thread = spawn(
				self.scan,
				self.ctx.bw.remote_addr,
				tonumber(port),
				tonumber(self.variables["REVERSE_SCAN_TIMEOUT"])
			)
			threads[port] = thread
		end
	end
	if ret_threads ~= nil then
		if #threads > 0 then
			local wait_threads = {}
			for _, thread in pairs(threads) do
				table.insert(wait_threads, thread)
			end
			kill_all_threads(wait_threads)
		end
		-- Open port case
		if ret_threads then
			return self:ret(true, ret_err, get_deny_status())
		end
		-- Error case
		return self:ret(false, ret_err)
	end
	-- Check results of threads
	ret_threads = nil
	ret_err = nil
	local results = {}
	while true do
		-- Compute threads to wait
		local wait_threads = {}
		for _, thread in pairs(threads) do
			table.insert(wait_threads, thread)
		end
		-- No port opened
		if #wait_threads == 0 then
			break
		end
		-- Wait for first thread
		local ok, open, port = wait(unpack(wait_threads))
		-- Error case
		if not ok then
			ret_threads = false
			ret_err = "error while waiting thread : " .. open
			break
		end
		port = tostring(port)
		-- Remove thread from list
		threads[port] = nil
		-- Add result to cache
		local result = "close"
		if open then
			result = "open"
		end
		results[port] = result
		-- Port is opened
		if open then
			ret_threads = true
			ret_err = "port " .. port .. " is opened for IP " .. self.ctx.bw.remote_addr
			self:set_metric("counters", "failed_" .. port, 1)
			break
		end
	end
	-- Kill running threads
	if #threads > 0 then
		local wait_threads = {}
		for _, thread in pairs(threads) do
			table.insert(wait_threads, thread)
		end
		kill_all_threads(wait_threads)
	end
	-- Cache results, best effort. Returning here discarded a verdict the scan had already
	-- reached : with a port confirmed open, a failing cachestore write threw the deny away
	-- and the request was served 200. Persisting the result is a nice-to-have, denying is not.
	-- Skipped wholesale once a read has already failed : writing to a store we just watched
	-- time out would pay that timeout again, once per port, for nothing.
	if not cache_down then
		for port, result in pairs(results) do
			local ok, err = self:add_to_cache(self.ctx.bw.remote_addr .. ":" .. port, result)
			if not ok then
				self.logger:log(WARN, "error while adding element to cache : " .. err)
			end
		end
	end
	if ret_threads ~= nil then
		-- Open port case
		if ret_threads then
			return self:ret(true, ret_err, get_deny_status())
		end
		-- Error case
		return self:ret(false, ret_err)
	end
	-- No port opened
	return self:ret(true, "no port open for IP " .. self.ctx.bw.remote_addr)
end

function reversescan:preread()
	return self:access()
end

function reversescan.scan(ip, port, timeout)
	local tcpsock = ngx_socket.tcp()
	tcpsock:settimeout(timeout)
	local ok, _ = tcpsock:connect(ip, port)
	tcpsock:close()
	if not ok then
		return false, port
	end
	return true, port
end

function reversescan:is_in_cache(ip_port)
	local ok, data = self.cachestore:get("plugin_reverse_scan_" .. ip_port)
	if not ok then
		return false, data
	end
	return true, data
end

function reversescan:add_to_cache(ip_port, value)
	local ok, err = self.cachestore:set("plugin_reverse_scan_" .. ip_port, value, 86400)
	if not ok then
		return false, err
	end
	return true
end

return reversescan
