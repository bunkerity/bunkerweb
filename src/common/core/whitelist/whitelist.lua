local class = require "middleclass"
local env = require "resty.env"
local ipmatcher = require "resty.ipmatcher"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"

local whitelist = class("whitelist", plugin)

function whitelist:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "whitelist", ctx)
	-- Decode lists
	if ngx.get_phase() ~= "init" and self:is_needed() then
		local lists, err = self.datastore:get("plugin_whitelist_lists", true)
		if not lists then
			self.logger:log(ngx.ERR, err)
			self.lists = {}
		else
			self.lists = lists
		end
		local kinds = {
			["IP"] = {},
			["RDNS"] = {},
			["ASN"] = {},
			["USER_AGENT"] = {},
			["URI"] = {},
		}
		for kind, _ in pairs(kinds) do
			for data in self.variables["WHITELIST_" .. kind]:gmatch("%S+") do
				if not self.lists[kind] then
					self.lists[kind] = {}
				end
				table.insert(self.lists[kind], data)
			end
		end
	end
end

function whitelist:is_needed()
	-- Loading case
	if self.is_loading then
		return false
	end
	-- Request phases (no default)
	if self.is_request and (self.ctx.bw.server_name ~= "_") then
		return self.variables["USE_WHITELIST"] == "yes"
	end
	-- Other cases : at least one service uses it
	local is_needed, err = utils.has_variable("USE_WHITELIST", "yes")
	if is_needed == nil then
		self.logger:log(ngx.ERR, "can't check USE_WHITELIST variable : " .. err)
	end
	return is_needed
end

function whitelist:init()
	-- Check if init is needed
	if not self:is_needed() then
		return self:ret(true, "init not needed")
	end
	-- Read whitelists
	local whitelists = {
		["IP"] = {},
		["RDNS"] = {},
		["ASN"] = {},
		["USER_AGENT"] = {},
		["URI"] = {},
	}
	local i = 0
	for kind, _ in pairs(whitelists) do
		local f, _ = io.open("/var/cache/bunkerweb/whitelist/" .. kind .. ".list", "r")
		if f then
			for line in f:lines() do
				table.insert(whitelists[kind], line)
				i = i + 1
			end
			f:close()
		end
	end
	-- Load them into datastore
	local ok, err = self.datastore:set("plugin_whitelist_lists", whitelists, nil, true)
	if not ok then
		return self:ret(false, "can't store whitelist list into datastore : " .. err)
	end
	return self:ret(true, "successfully loaded " .. tostring(i) .. " IP/network/rDNS/ASN/User-Agent/URI")
end

function whitelist:set()
	-- Set default value
	ngx.var.is_whitelisted = "no"
	self.ctx.bw.is_whitelisted = "no"
	env.set("is_whitelisted", "no")
	-- Check if set is needed
	if not self:is_needed() then
		return self:ret(true, "whitelist not activated")
	end
	-- Check cache
	local whitelisted, err = self:check_cache()
	if whitelisted == nil then
		return self:ret(false, err)
	elseif whitelisted then
		ngx.var.is_whitelisted = "yes"
		self.ctx.bw.is_whitelisted = "yes"
		env.set("is_whitelisted", "yes")
		return self:ret(true, err)
	end
	return self:ret(true, "not in whitelist cache")
end

function whitelist:access()
	-- Check if access is needed
	if not self:is_needed() then
		return self:ret(true, "whitelist not activated")
	end
	-- Check cache
	local whitelisted, err, already_cached = self:check_cache()
	if whitelisted == nil then
		return self:ret(false, err)
	elseif whitelisted then
		ngx.var.is_whitelisted = "yes"
		self.ctx.bw.is_whitelisted = "yes"
		env.set("is_whitelisted", "yes")
		return self:ret(true, err, ngx.OK)
	end
	-- Perform checks
	local ok
	for k, _ in pairs(already_cached) do
		if not already_cached[k] then
			ok, whitelisted = self:is_whitelisted(k)
			if ok == nil then
				self.logger:log(ngx.ERR, "error while checking if " .. k .. " is whitelisted : " .. whitelisted)
			else
				ok, err = self:add_to_cache(self:kind_to_ele(k), whitelisted)
				if not ok then
					self.logger:log(ngx.ERR, "error while adding element to cache : " .. err)
				end
				if whitelisted ~= "ok" then
					ngx.var.is_whitelisted = "yes"
					self.ctx.bw.is_whitelisted = "yes"
					env.set("is_whitelisted", "yes")
					return self:ret(true, k .. " is whitelisted (info : " .. whitelisted .. ")", ngx.OK)
				end
			end
		end
	end
	-- Not whitelisted
	return self:ret(true, "not whitelisted")
end

function whitelist:preread()
	return self:access()
end

function whitelist:kind_to_ele(kind)
	if kind == "IP" then
		return "ip" .. self.ctx.bw.remote_addr
	elseif kind == "UA" then
		return "ua" .. self.ctx.bw.http_user_agent
	elseif kind == "URI" then
		return "uri" .. self.ctx.bw.uri
	end
end

function whitelist:check_cache()
	-- Check the caches
	local checks = {
		["IP"] = "ip" .. self.ctx.bw.remote_addr,
	}
	if self.ctx.bw.http_user_agent then
		checks["UA"] = "ua" .. self.ctx.bw.http_user_agent
	end
	if self.ctx.bw.uri then
		checks["URI"] = "uri" .. self.ctx.bw.uri
	end
	local already_cached = {}
	for k, _ in pairs(checks) do
		already_cached[k] = false
	end
	for k, v in pairs(checks) do
		local ok, cached = self:is_in_cache(v)
		if not ok then
			self.logger:log(ngx.ERR, "error while checking cache : " .. cached)
		elseif cached and cached ~= "ok" then
			return true, k .. " is in cached whitelist (info : " .. cached .. ")"
		end
		if ok and cached then
			already_cached[k] = true
		end
	end
	-- Check lists
	if not self.lists then
		return nil, "lists is nil"
	end
	-- Not cached/whitelisted
	return false, "not cached/whitelisted", already_cached
end

function whitelist:is_in_cache(ele)
	local ok, data = self.cachestore:get("plugin_whitelist_" .. self.ctx.bw.server_name .. ele)
	if not ok then
		return false, data
	end
	return true, data
end

function whitelist:add_to_cache(ele, value)
	local ok, err = self.cachestore:set("plugin_whitelist_" .. self.ctx.bw.server_name .. ele, value, 86400)
	if not ok then
		return false, err
	end
	return true
end

function whitelist:is_whitelisted(kind)
	if kind == "IP" then
		return self:is_whitelisted_ip()
	elseif kind == "URI" then
		return self:is_whitelisted_uri()
	elseif kind == "UA" then
		return self:is_whitelisted_ua()
	end
	return false, "unknown kind " .. kind
end

function whitelist:is_whitelisted_ip()
	-- Check if IP is in whitelist
	local ipm, err = ipmatcher.new(self.lists["IP"])
	if not ipm then
		return nil, err
	end
	local match, err = ipm:match(self.ctx.bw.remote_addr)
	if err then
		return nil, err
	end
	if match then
		return true, "ip"
	end

	-- Check if rDNS is needed
	local check_rdns = true
	if self.variables["WHITELIST_RDNS_GLOBAL"] == "yes" and not self.ctx.bw.ip_is_global then
		check_rdns = false
	end
	if check_rdns then
		-- Get rDNS
		-- luacheck: ignore 421
		local rdns_list, err = utils.get_rdns(self.ctx.bw.remote_addr)
		-- Check if rDNS is in whitelist
		if rdns_list then
			local forward_check = nil
			local rdns_suffix = nil
			for _, rdns in ipairs(rdns_list) do
				for _, suffix in ipairs(self.lists["RDNS"]) do
					if rdns:sub(-#suffix) == suffix then
						forward_check = rdns
						rdns_suffix = suffix
						break
					end
				end
				if forward_check then
					break
				end
			end
			if forward_check then
				local ip_list, err = utils.get_ips(forward_check)
				if ip_list then
					for _, ip in ipairs(ip_list) do
						if ip == self.ctx.bw.remote_addr then
							return true, "rDNS " .. rdns_suffix
						end
					end
					self.logger:log(
						ngx.WARN,
						"IP " .. self.ctx.bw.remote_addr .. " may spoof reverse DNS " .. forward_check
					)
				else
					self.logger:log(ngx.ERR, "error while getting rdns (forward check) : " .. err)
				end
			end
		else
			self.logger:log(ngx.ERR, "error while getting rdns : " .. err)
		end
	end

	-- Check if ASN is in whitelist
	if self.ctx.bw.ip_is_global then
		local asn, err = utils.get_asn(self.ctx.bw.remote_addr)
		if not asn then
			self.logger:log(ngx.ERR, "can't get ASN of IP " .. self.ctx.bw.remote_addr .. " : " .. err)
		else
			for _, bl_asn in ipairs(self.lists["ASN"]) do
				if bl_asn == tostring(asn) then
					return true, "ASN " .. bl_asn
				end
			end
		end
	end

	-- Not whitelisted
	return false, "ok"
end

function whitelist:is_whitelisted_uri()
	-- Check if URI is in whitelist
	for _, uri in ipairs(self.lists["URI"]) do
		if utils.regex_match(self.ctx.bw.uri, uri) then
			return true, "URI " .. uri
		end
	end
	-- URI is not whitelisted
	return false, "ok"
end

function whitelist:is_whitelisted_ua()
	-- Check if UA is in whitelist
	for _, ua in ipairs(self.lists["USER_AGENT"]) do
		if utils.regex_match(self.ctx.bw.http_user_agent, ua) then
			return true, "UA " .. ua
		end
	end
	-- UA is not whiteklisted
	return false, "ok"
end

return whitelist
