local class			= require "middleclass"
local plugin		= require "bunkerweb.plugin"
local utils     	= require "bunkerweb.utils"
local datastore 	= require "bunkerweb.datastore"
local cachestore	= require "bunkerweb.cachestore"
local cjson     	= require "cjson"
local ipmatcher 	= require "resty.ipmatcher"
local env			= require "resty.env"

local whitelist = class("whitelist", plugin)

function whitelist:initialize()
	-- Call parent initialize
    plugin.initialize(self, "whitelist")
	-- Check if redis is enabled
	local use_redis, err = utils.get_variable("USE_REDIS", false)
	if not use_redis then
		self.logger:log(ngx.ERR, err)
	end
	self.use_redis = use_redis == "yes"
	-- Check if init is needed
	if ngx.get_phase() == "init" then
		local init_needed, err = utils.has_variable("USE_WHITELIST", "yes")
		if init_needed == nil then
			self.logger:log(ngx.ERR, err)
		end
		self.init_needed = init_needed
	-- Decode lists
	else
		local lists, err = self.datastore:get("plugin_whitelist_lists")
		if not lists then
			self.logger:log(ngx.ERR, err)
		else
			self.lists = cjson.decode(lists)
		end
	end
	-- Instantiate cachestore
	self.cachestore = cachestore:new(self.use_redis)
end

function whitelist:init()
	-- Check if init is needed
	if not self.init_needed then
		return self:ret(true, "init not needed")
	end
	-- Read whitelists
	local whitelists = {
		["IP"] = {},
		["RDNS"] = {},
		["ASN"] = {},
		["USER_AGENT"] = {},
		["URI"] = {}
	}
	local i = 0
	for kind, _ in pairs(whitelists) do
		local f, err = io.open("/var/cache/bunkerweb/whitelist/" .. kind .. ".list", "r")
		if f then
			for line in f:lines() do
				table.insert(whitelists[kind], line)
				i = i + 1
			end
			f:close()
		end
	end
	-- Load them into datastore
	local ok, err = self.datastore:set("plugin_whitelist_lists", cjson.encode(whitelists))
	if not ok then
		return self:ret(false, "can't store whitelist list into datastore : " .. err)
	end
	return self:ret(true, "successfully loaded " .. tostring(i) .. " IP/network/rDNS/ASN/User-Agent/URI")
end

function whitelist:set()
	-- Set default value
	ngx.var.is_whitelisted = "no"
	env.set("is_whitelisted", "no")
	-- Check if set is needed
	if self.variables["USE_WHITELIST"] ~= "yes" then
		return self:ret(true, "whitelist not activated")
	end
	-- Check cache
	local whitelisted, err = self:check_cache()
	if whitelisted == nil then
		return self:ret(false, err)
	elseif whitelisted then
		ngx.var.is_whitelisted = "yes"
		env.set("is_whitelisted", "yes")
		return self:ret(true, err)
	end
	return self:ret(true, "not in whitelist cache")
end

function whitelist:access()
	-- Check if access is needed
	if self.variables["USE_WHITELIST"] ~= "yes" then
		return self:ret(true, "whitelist not activated")
	end
	-- Check cache
	local whitelisted, err, already_cached = self:check_cache()
	if whitelisted == nil then
		return self:ret(false, err)
	elseif whitelisted then
		ngx.var.is_whitelisted = "yes"
		env.set("is_whitelisted", "yes")
		return self:ret(true, err, ngx.OK)
	end
	-- Perform checks
	for k, v in pairs(already_cached) do
		if not already_cached[k] then
			local ok, whitelisted = self:is_whitelisted(k)
			if ok == nil then
				self.logger:log(ngx.ERR, "error while checking if " .. k .. " is whitelisted : " .. err)
			else
				local ok, err = self:add_to_cache(self:kind_to_ele(k), whitelisted)
				if not ok then
					self.logger:log(ngx.ERR, "error while adding element to cache : " .. err)
				end
				if whitelisted ~= "ok" then
					ngx.var.is_whitelisted = "yes"
					env.set("is_whitelisted", "yes")
					return self:ret(true, k + " is whitelisted (info : " .. whitelisted .. ")", ngx.OK)
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
		return "ip" .. ngx.var.remote_addr
	elseif kind == "UA" then
		return "ua" .. ngx.var.http_user_agent
	elseif kind == "URI" then
		return "uri" .. ngx.var.uri
	end
end

function whitelist:check_cache()
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
			return true, k + " is in cached whitelist (info : " .. cached .. ")"
		end
		if cached then
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
	local ok, data = self.cachestore:get("plugin_whitelist_" .. ele)
	if not ok then
		return false, data
	end 
	return true, data
end

function whitelist:add_to_cache(ele, value)
	local ok, err = self.cachestore:set("plugin_whitelist_" .. ele, value)
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
	if self.variables["WHITELIST_RDNS_GLOBAL"] == "yes" then
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
		-- Check if rDNS is in whitelist
		for i, suffix in ipairs(self.lists["RDNS"]) do
			for j, rdns in ipairs(rdns_list) do
				if rdns:sub(-#suffix) == suffix then
					return true, "rDNS " .. suffix
				end
			end
		end
	end

	-- Check if ASN is in whitelist
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

	-- Not whitelisted
	return false, "ok"
end

function whitelist:is_whitelisted_uri()
	-- Check if URI is in whitelist
	for i, uri in ipairs(self.lists["URI"]) do
		if ngx.var.uri:match(uri) then
			return true, "URI " .. uri
		end
	end
	-- URI is not whitelisted
	return false, "ok"
end

function whitelist:is_whitelisted_ua()
	-- Check if UA is in whitelist
	for i, ua in ipairs(self.lists["USER_AGENT"]) do
		if ngx.var.http_user_agent:match(ua) then
			return true, "UA " .. ua
		end
	end
	-- UA is not whiteklisted
	return false, "ok"
end

return whitelist