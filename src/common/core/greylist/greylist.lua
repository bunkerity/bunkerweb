local class			= require "middleclass"
local plugin		= require "bunkerweb.plugin"
local utils     	= require "bunkerweb.utils"
local cachestore	= require "bunkerweb.cachestore"
local cjson			= require "cjson"
local ipmatcher		= require "resty.ipmatcher"

local greylist = class("greylist", plugin)

function greylist:initialize()
	-- Call parent initialize
	plugin.initialize(self, "greylist")
	-- Check if redis is enabled
	local use_redis, err = utils.get_variable("USE_REDIS", false)
	if not use_redis then
		self.logger:log(ngx.ERR, err)
	end
	self.use_redis = use_redis == "yes"
	-- Check if init is needed
	if ngx.get_phase() == "init" then
		local init_needed, err = utils.has_variable("USE_GREYLIST", "yes")
		if init_needed == nil then
			self.logger:log(ngx.ERR, err)
		end
		self.init_needed = init_needed
	-- Decode lists
	elseif self.variables["USE_GREYLIST"] == "yes" then
		local lists, err = self.datastore:get("plugin_greylist_lists")
		if not lists then
			self.logger:log(ngx.ERR, err)
		else
			self.lists = cjson.decode(lists)
		end
	end
	-- Instantiate cachestore
	self.cachestore = cachestore:new(self.use_redis)
end

function greylist:init()
	-- Check if init is needed
	if not self.init_needed then
		return self:ret(true, "init not needed")
	end
	-- Read blacklists
	local greylists = {
		["IP"] = {},
		["RDNS"] = {},
		["ASN"] = {},
		["USER_AGENT"] = {},
		["URI"] = {},
	}
	local i = 0
	for kind, _ in pairs(greylists) do
		local f, err = io.open("/var/cache/bunkerweb/greylist/" .. kind .. ".list", "r")
		if f then
			for line in f:lines() do
				table.insert(greylists[kind], line)
				i = i + 1
			end
			f:close()
		end
	end
	-- Load them into datastore
	local ok, err = self.datastore:set("plugin_greylist_lists", cjson.encode(greylists))
	if not ok then
		return self:ret(false, "can't store greylist list into datastore : " .. err)
	end
	return self:ret(true, "successfully loaded " .. tostring(i) .. " bad IP/network/rDNS/ASN/User-Agent/URI")
end

function greylist:access()
	-- Check if access is needed
	if self.variables["USE_GREYLIST"] ~= "yes" then
		return self:ret(true, "greylist not activated")
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
		local cached, err = self:is_in_cache(v)
		if not cached and err ~= "success" then
			self.logger:log(ngx.ERR, "error while checking cache : " .. err)
		elseif cached and cached ~= "ok" then
			return self:ret(true, k + " is in cached greylist", utils.get_deny_status())
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
			local greylisted, err = self:is_greylisted(k)
			if greylisted == nil then
				self.logger:log(ngx.ERR, "error while checking if " .. k .. " is greylisted : " .. err)
			else
				local ok, err = self:add_to_cache(self:kind_to_ele(k), greylisted or "ok")
				if not ok then
					self.logger:log(ngx.ERR, "error while adding element to cache : " .. err)
				end
				if greylisted == "ko" then
					return self:ret(true, k + " is not in greylist", utils.get_deny_status())
				end
			end
		end
	end

	-- Return
	return self:ret(true, "greylisted")
end

function greylist:preread()
	return self:access()
end

function greylist:kind_to_ele(kind)
	if kind == "IP" then
		return "ip" .. ngx.var.remote_addr
	elseif kind == "UA" then
		return "ua" .. ngx.var.http_user_agent
	elseif kind == "URI" then
		return "uri" .. ngx.var.uri
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
			return nil, err
		end
		-- Check if rDNS is in greylist
		for i, suffix in ipairs(self.lists["RDNS"]) do
			for j, rdns in ipairs(rdns_list) do
				if rdns:sub(-#suffix) == suffix then
					return true, "rDNS " .. suffix
				end
			end
		end
	end

	-- Check if ASN is in greylist
	if is_global then
		local asn, err = utils.get_asn(ngx.var.remote_addr)
		if not asn then
			return nil, err
		end
		for i, bl_asn in ipairs(self.lists["ASN"]) do
			if bl_asn == tostring(asn) then
				return true, "ASN " .. bl_asn
			end
		end
	end

	-- Not greylisted
	return false, "ko"
end

function greylist:is_greylisted_uri()
	-- Check if URI is in blacklist
	for i, uri in ipairs(self.lists["URI"]) do
		if ngx.var.uri:match(uri) then
			return true, "URI " .. uri
		end
	end
	-- URI is not greylisted
	return false, "ko"
end

function greylist:is_greylisted_ua()
	-- Check if UA is in greylist
	for i, ua in ipairs(self.lists["USER_AGENT"]) do
		if ngx.var.http_user_agent:match(ua) then
			return true, "UA " .. ua
		end
	end
	-- UA is not greylisted
	return false, "ko"
end

function greylist:is_in_cache(ele)
	local ok, data = self.cachestore:get("plugin_greylist_" .. ele)
	if not ok then
		return false, data
	end 
	return true, data
end

function greylist:add_to_cache(ele, value)
	local ok, err = self.cachestore:set("plugin_greylist_" .. ele, value)
	if not ok then
		return false, err
	end 
	return true
end

return greylist