local class			= require "middleclass"
local plugin		= require "bunkerweb.plugin"
local utils     	= require "bunkerweb.utils"
local datastore 	= require "bunkerweb.datastore"
local cachestore	= require "bunkerweb.cachestore"
local cjson     	= require "cjson"
local ipmatcher 	= require "resty.ipmatcher"

local blacklist = class("blacklist", plugin)

function blacklist:initialize()
	-- Call parent initialize
	plugin.initialize(self, "blacklist")
	-- Check if redis is enabled
	local use_redis, err = utils.get_variable("USE_REDIS", false)
	if not use_redis then
		self.logger:log(ngx.ERR, err)
	end
	self.use_redis = use_redis == "yes"
	-- Check if init is needed
	if ngx.get_phase() == "init" then
		local init_needed, err = utils.has_variable("USE_BLACKLIST", "yes")
		if init_needed == nil then
			self.logger:log(ngx.ERR, err)
		end
		self.init_needed = init_needed
	-- Decode lists
	else
		local lists, err = self.datastore:get("plugin_blacklist_lists")
		if not lists then
			self.logger:log(ngx.ERR, err)
		else
			self.lists = cjson.decode(lists)
		end
	end
	-- Instantiate cachestore
	self.cachestore = cachestore:new(self.use_redis)
end

function blacklist:init()
	-- Check if init is needed
	if not self.init_needed then
		return self:ret(true, "init not needed")
	end
	-- Read blacklists
	local blacklists = {
		["IP"] = {},
		["RDNS"] = {},
		["ASN"] = {},
		["USER_AGENT"] = {},
		["URI"] = {},
		["IGNORE_IP"] = {},
		["IGNORE_RDNS"] = {},
		["IGNORE_ASN"] = {},
		["IGNORE_USER_AGENT"] = {},
		["IGNORE_URI"] = {},
	}
	local i = 0
	for kind, _ in pairs(blacklists) do
		local f, err = io.open("/var/cache/bunkerweb/blacklist/" .. kind .. ".list", "r")
		if f then
			for line in f:lines() do
				table.insert(blacklists[kind], line)
				i = i + 1
			end
			f:close()
		end
	end
	-- Load them into datastore
	local ok, err = self.datastore:set("plugin_blacklist_lists", cjson.encode(blacklists))
	if not ok then
		return self:ret(false, "can't store blacklist list into datastore : " .. err)
	end
	return self:ret(true, "successfully loaded " .. tostring(i) .. " IP/network/rDNS/ASN/User-Agent/URI")
end

function blacklist:access()
	-- Check if access is needed
	if self.variables["USE_BLACKLIST"] ~= "yes" then
		return self:ret(true, "blacklist not activated")
	end
	-- Check the caches
	local checks = {
		["IP"] = "ip" .. ngx.var.remote_addr
	}
	if ngx.var.http_user_agent then
		checks["UA"] = "ua" .. ngx.var.http_user_agent
	end
	if ngx.var.uri then
		checks["URI"] = "uri" .. ngx.var.uri
	end
	local already_cached = {
		["IP"] = false,
		["URI"] = false,
		["UA"] = false
	}
	for k, v in pairs(checks) do
		local ok, cached = self:is_in_cache(v)
		if not ok then
			self.logger:log(ngx.ERR, "error while checking cache : " .. cached)
		elseif cached and cached ~= "ok" then
			return self:ret(true, k + " is in cached blacklist (info : " .. cached .. ")", utils.get_deny_status())
		end
		if cached then
			already_cached[k] = true
		end
	end
	-- Check lists
	if not self.lists then
		return self:ret(false, "lists is nil")
	end
	-- Perform checks
	for k, v in pairs(checks) do
		if not already_cached[k] then
			local ok, blacklisted = self:is_blacklisted(k)
			if ok == nil then
				self.logger:log(ngx.ERR, "error while checking if " .. k .. " is blacklisted : " .. blacklisted)
			else
				local ok, err = self:add_to_cache(self:kind_to_ele(k), blacklisted)
				if not ok then
					self.logger:log(ngx.ERR, "error while adding element to cache : " .. err)
				end
				if blacklisted ~= "ok" then
					return self:ret(true, k + " is blacklisted (info : " .. blacklisted .. ")", utils.get_deny_status())
				end
			end
		end
	end

	-- Return
	return self:ret(true, "not blacklisted")

end

function blacklist:preread()
	return self:access()
end

function blacklist:kind_to_ele(kind)
	if kind == "IP" then
		return "ip" .. ngx.var.remote_addr
	elseif kind == "UA" then
		return "ua" .. ngx.var.http_user_agent
	elseif kind == "URI" then
		return "uri" .. ngx.var.uri
	end
end

function blacklist:is_in_cache(ele)
	local ok, data = self.cachestore:get("plugin_blacklist_" .. ele)
	if not ok then
		return false, data
	end 
	return true, data
end

function blacklist:add_to_cache(ele, value)
	local ok, err = self.cachestore:set("plugin_blacklist_" .. ele, value)
	if not ok then
		return false, err
	end 
	return true
end

function blacklist:is_blacklisted(kind)
	if kind == "IP" then
		return self:is_blacklisted_ip()
	elseif kind == "URI" then
		return self:is_blacklisted_uri()
	elseif kind == "UA" then
		return self:is_blacklisted_ua()
	end
	return false, "unknown kind " .. kind
end

function blacklist:is_blacklisted_ip()
	-- Check if IP is in ignore list
	local ipm, err = ipmatcher.new(self.lists["IGNORE_IP"])
	if not ipm then
		return nil, err
	end
	local match, err = ipm:match(ngx.var.remote_addr)
	if err then
		return nil, err
	end
	if not match then
		-- Check if IP is in blacklist
		local ipm, err = ipmatcher.new(self.lists["IP"])
		if not ipm then
			return nil, err
		end
		local match, err = ipm:match(ngx.var.remote_addr)
		if err then
			return nil, err
		end
		if match then
			return true, "ip"
		end
	end

	-- Check if rDNS is needed
	local check_rdns = true
	local is_global, err = utils.ip_is_global(ngx.var.remote_addr)
	if self.variables["BLACKLIST_RDNS_GLOBAL"] == "yes" then
		if is_global == nil then
			return nil, err
		end
		if not is_global then
			check_rdns = false
		end
	end
	if check_rdns then
		-- Get rDNS
		local rdns_list, err = utils.get_rdns(ngx.var.remote_addr)
		if not rdns_list then
			return false, err
		end
		-- Check if rDNS is in ignore list
		local ignore = false
		for i, ignore_suffix in ipairs(self.lists["IGNORE_RDNS"]) do
			for j, rdns in ipairs(rdns_list) do
				if rdns:sub(-#ignore_suffix) == ignore_suffix then
					ignore = true
					break
				end
			end
			if ignore then
				break
			end
		end
		-- Check if rDNS is in blacklist
		if not ignore then
			for i, suffix in ipairs(self.lists["RDNS"]) do
				for j, rdns in ipairs(rdns_list) do
					if rdns:sub(-#suffix) == suffix then
						return true, "rDNS " .. suffix
					end
				end
			end
		end
	end

	-- Check if ASN is in ignore list
	if is_global then
		local asn, err = utils.get_asn(ngx.var.remote_addr)
		if not asn then
			self.logger:log(ngx.ERR, "7")
			return nil, err
		end
		local ignore = false
		for i, ignore_asn in ipairs(self.lists["IGNORE_ASN"]) do
			if ignore_asn == tostring(asn) then
				ignore = true
				break
			end
		end
		-- Check if ASN is in blacklist
		if not ignore then
			for i, bl_asn in ipairs(self.lists["ASN"]) do
				if bl_asn == tostring(asn) then
					return true, "ASN " .. bl_asn
				end
			end
		end
	end

	-- Not blacklisted
	return false, "ok"
end

function blacklist:is_blacklisted_uri()
	-- Check if URI is in ignore list
	local ignore = false
	for i, ignore_uri in ipairs(self.lists["IGNORE_URI"]) do
		if ngx.var.uri:match(ignore_uri) then
			ignore = true
			break
		end
	end
	-- Check if URI is in blacklist
	if not ignore then
		for i, uri in ipairs(self.lists["URI"]) do
			if ngx.var.uri:match(uri) then
				return true, "URI " .. uri
			end
		end
	end
	-- URI is not blacklisted
	return false, "ok"
end

function blacklist:is_blacklisted_ua()
	-- Check if UA is in ignore list
	local ignore = false
	for i, ignore_ua in ipairs(self.lists["IGNORE_USER_AGENT"]) do
		if ngx.var.http_user_agent:match(ignore_ua) then
			ignore = true
			break
		end
	end
	-- Check if UA is in blacklist
	if not ignore then
		for i, ua in ipairs(self.lists["USER_AGENT"]) do
			if ngx.var.http_user_agent:match(ua) then
				return true, "UA " .. ua
			end
		end
	end
	-- UA is not blacklisted
	return false, "ok"
end

return blacklist