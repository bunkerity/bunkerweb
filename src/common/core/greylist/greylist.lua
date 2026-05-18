local class = require "middleclass"
local ipmatcher = require "resty.ipmatcher"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"

local greylist = class("greylist", plugin)

local ngx = ngx
local ERR = ngx.ERR
local INFO = ngx.INFO
local get_phase = ngx.get_phase
local has_variable = utils.has_variable
local get_deny_status = utils.get_deny_status
local get_rdns = utils.get_rdns
local get_asn = utils.get_asn
local regex_match = utils.regex_match
local get_variable = utils.get_variable
local deduplicate_list = utils.deduplicate_list
local ipmatcher_new = ipmatcher.new
local tostring = tostring
local open = io.open

function greylist:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "greylist", ctx)
	-- Decode lists
	if get_phase() ~= "init" and self:is_needed() then
		local internalstore_lists, err =
			self.internalstore:get("plugin_greylist_lists_" .. self.ctx.bw.server_name, true)
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
		local kinds = {
			["IP"] = {},
			["RDNS"] = {},
			["ASN"] = {},
			["USER_AGENT"] = {},
			["URI"] = {},
		}
		for kind, _ in pairs(kinds) do
			if not self.lists[kind] then
				self.lists[kind] = {}
			end
			for data in self.variables["GREYLIST_" .. kind]:gmatch("%S+") do
				if data ~= "" then
					table.insert(self.lists[kind], data)
				end
			end
			self.lists[kind] = deduplicate_list(self.lists[kind])
		end
	end
end

function greylist:is_needed()
	-- Loading case
	if self.is_loading then
		return false
	end
	-- Request phases (no default)
	if self.is_request and (self.ctx.bw.server_name ~= "_") then
		return self.variables["USE_GREYLIST"] == "yes"
	end
	-- Other cases : at least one service uses it
	local is_needed, err = has_variable("USE_GREYLIST", "yes")
	if is_needed == nil then
		self.logger:log(ERR, "can't check USE_GREYLIST variable : " .. err)
	end
	return is_needed
end

function greylist:init()
	-- Check if init is needed
	if not self:is_needed() then
		return self:ret(true, "init not needed")
	end

	-- Read greylists
	local greylists = {
		["IP"] = {},
		["RDNS"] = {},
		["ASN"] = {},
		["USER_AGENT"] = {},
		["URI"] = {},
	}

	local server_name, err = get_variable("SERVER_NAME", false)
	if not server_name then
		return self:ret(false, "can't get SERVER_NAME variable : " .. err)
	end

	-- Iterate over each kind and server
	local i = 0
	for key in server_name:gmatch("%S+") do
		for kind, _ in pairs(greylists) do
			local file_path = "/var/cache/bunkerweb/greylist/" .. key .. "/" .. kind .. ".list"
			local f = open(file_path, "r")
			if f then
				for line in f:lines() do
					if line ~= "" then
						table.insert(greylists[kind], line)
						i = i + 1
					end
				end
				f:close()
			end
			greylists[kind] = deduplicate_list(greylists[kind])
		end

		-- Load service specific ones into internalstore
		local ok
		ok, err = self.internalstore:set("plugin_greylist_lists_" .. key, greylists, nil, true)
		if not ok then
			return self:ret(false, "can't store greylist " .. key .. " list into internalstore : " .. err)
		end

		self.logger:log(
			INFO,
			"successfully loaded " .. tostring(i) .. " IP/network/rDNS/ASN/User-Agent/URI for the service: " .. key
		)

		i = 0
		greylists = {
			["IP"] = {},
			["RDNS"] = {},
			["ASN"] = {},
			["USER_AGENT"] = {},
			["URI"] = {},
		}
	end
	return self:ret(true, "successfully loaded all IP/network/rDNS/ASN/User-Agent/URI")
end

function greylist:access()
	-- Check if access is needed
	if not self:is_needed() then
		return self:ret(true, "access not needed")
	end
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
	local already_cached = {
		["IP"] = false,
		["URI"] = false,
		["UA"] = false,
	}
	for k, v in pairs(checks) do
		local ok, cached = self:is_in_cache(v)
		if not ok then
			self.logger:log(ERR, "error while checking cache : " .. cached)
		elseif cached and cached ~= "ko" then
			return self:ret(true, k .. " is in cached greylist (info : " .. cached .. ")")
		end
		if ok and cached then
			already_cached[k] = true
		end
	end
	-- Check lists
	if not self.lists then
		return self:ret(false, "lists is nil")
	end
	-- Perform checks
	for k, _ in pairs(checks) do
		if not already_cached[k] then
			local ok, greylisted = self:is_greylisted(k)
			if ok == nil then
				self.logger:log(ERR, "error while checking if " .. k .. " is greylisted : " .. greylisted)
			else
				-- luacheck: ignore 421
				local ok, err = self:add_to_cache(self:kind_to_ele(k), greylisted)
				if not ok then
					self.logger:log(ERR, "error while adding element to cache : " .. err)
				end
				if greylisted ~= "ko" then
					return self:ret(true, k .. " is in greylist")
				end
			end
		end
	end

	-- Return
	self:set_metric("counters", "failed_greylist", 1)
	return self:ret(true, "not in greylist", get_deny_status())
end

function greylist:preread()
	return self:access()
end

function greylist:kind_to_ele(kind)
	if kind == "IP" then
		return "ip" .. self.ctx.bw.remote_addr
	elseif kind == "UA" then
		return "ua" .. self.ctx.bw.http_user_agent
	elseif kind == "URI" then
		return "uri" .. self.ctx.bw.uri
	end
end

function greylist:is_greylisted(kind)
	if kind == "IP" then
		return self:is_greylisted_ip()
	elseif kind == "URI" then
		return self:is_greylisted_uri()
	elseif kind == "UA" then
		return self:is_greylisted_ua()
	end
	return false, "unknown kind " .. kind
end

function greylist:is_greylisted_ip()
	-- Check if IP is in greylist
	local ipm, err = ipmatcher_new(self.lists["IP"])
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
	if self.variables["GREYLIST_RDNS_GLOBAL"] == "yes" and not self.ctx.bw.ip_is_global then
		check_rdns = false
	end
	if check_rdns then
		-- Get rDNS
		-- luacheck: ignore 421
		local rdns_list, err = get_rdns(self.ctx.bw.remote_addr, self.ctx, true)
		-- Check if rDNS is in greylist
		if rdns_list then
			for _, rdns in ipairs(rdns_list) do
				for _, suffix in ipairs(self.lists["RDNS"]) do
					if rdns:sub(-#suffix) == suffix then
						return true, "rDNS " .. suffix
					end
				end
			end
		else
			self.logger:log(ERR, "error while getting rdns : " .. err)
		end
	end

	-- Check if ASN is in greylist
	if self.ctx.bw.ip_is_global then
		local asn, err = get_asn(self.ctx.bw.remote_addr)
		if not asn then
			self.logger:log(ERR, "can't get ASN of IP " .. self.ctx.bw.remote_addr .. " : " .. err)
		else
			for _, bl_asn in ipairs(self.lists["ASN"]) do
				if bl_asn == tostring(asn) then
					return true, "ASN " .. bl_asn
				end
			end
		end
	end

	-- Not greylisted
	return false, "ko"
end

function greylist:is_greylisted_uri()
	-- Check if URI is in greylist
	for _, uri in ipairs(self.lists["URI"]) do
		if regex_match(self.ctx.bw.uri, uri) then
			return true, "URI " .. uri
		end
	end
	-- URI is not greylisted
	return false, "ko"
end

function greylist:is_greylisted_ua()
	-- Check if UA is in greylist
	for _, ua in ipairs(self.lists["USER_AGENT"]) do
		if regex_match(self.ctx.bw.http_user_agent, ua) then
			return true, "UA " .. ua
		end
	end
	-- UA is not greylisted
	return false, "ko"
end

function greylist:is_in_cache(ele)
	local ok, data = self.cachestore_local:get("plugin_greylist_" .. self.ctx.bw.server_name .. ele)
	if not ok then
		return false, data
	end
	return true, data
end

function greylist:add_to_cache(ele, value)
	local ok, err = self.cachestore_local:set("plugin_greylist_" .. self.ctx.bw.server_name .. ele, value, 86400)
	if not ok then
		return false, err
	end
	return true
end

return greylist
