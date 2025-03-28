local cjson = require "cjson"
local class = require "middleclass"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"

local country = class("country", plugin)

local get_country = utils.get_country
local get_deny_status = utils.get_deny_status
local decode = cjson.decode
local encode = cjson.encode

-- Helper function to convert space-separated string to a set
local function string_to_set(str)
	local set = {}
	if str and str ~= "" then
		for item in str:gmatch("%S+") do
			set[item] = true
		end
	end
	return set
end

function country:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "country", ctx)

	-- Initialize whitelist and blacklist sets once
	self.whitelist = string_to_set(self.variables["WHITELIST_COUNTRY"])
	self.blacklist = string_to_set(self.variables["BLACKLIST_COUNTRY"])
end

function country:access()
	-- Don't go further if nothing is enabled
	if self.variables["WHITELIST_COUNTRY"] == "" and self.variables["BLACKLIST_COUNTRY"] == "" then
		return self:ret(true, "country not activated")
	end

	-- Check if IP is in cache
	local _, data = self:is_in_cache(self.ctx.bw.remote_addr)
	if data then
		data = decode(data)
		if data.result == "ok" then
			return self:ret(
				true,
				"client IP "
					.. self.ctx.bw.remote_addr
					.. " is in country cache (not blacklisted, country = "
					.. data.country
					.. ")"
			)
		end
		self:set_metric("counters", "failed_country", 1)
		return self:ret(
			true,
			"client IP "
				.. self.ctx.bw.remote_addr
				.. " is in country cache (blacklisted, country = "
				.. data.country
				.. ")",
			get_deny_status(),
			nil,
			{
				id = "country",
				country = data.country,
			}
		)
	end

	-- Don't go further if IP is not global
	if not self.ctx.bw.ip_is_global then
		local ok, err = self:add_to_cache(self.ctx.bw.remote_addr, "unknown", "ok")
		if not ok then
			return self:ret(false, "error while adding ip to cache : " .. err)
		end
		return self:ret(true, "client IP " .. self.ctx.bw.remote_addr .. " is not global, skipping check")
	end

	-- Get the country of client
	local country_data, err = get_country(self.ctx.bw.remote_addr)
	if not country_data then
		return self:ret(false, "can't get country of client IP " .. self.ctx.bw.remote_addr .. " : " .. err)
	end

	-- Process whitelist first
	if self.variables["WHITELIST_COUNTRY"] ~= "" then
		if self.whitelist[country_data] then
			local ok
			ok, err = self:add_to_cache(self.ctx.bw.remote_addr, country_data, "ok")
			if not ok then
				return self:ret(false, "error while adding item to cache : " .. err)
			end
			return self:ret(
				true,
				"client IP " .. self.ctx.bw.remote_addr .. " is whitelisted (country = " .. country_data .. ")"
			)
		end

		local ok
		ok, err = self:add_to_cache(self.ctx.bw.remote_addr, country_data, "ko")
		if not ok then
			return self:ret(false, "error while adding item to cache : " .. err)
		end
		self:set_metric("counters", "failed_country", 1)
		return self:ret(
			true,
			"client IP " .. self.ctx.bw.remote_addr .. " is not whitelisted (country = " .. country_data .. ")",
			get_deny_status(),
			nil,
			{
				id = "country",
				country = country_data,
			}
		)
	end

	-- And then blacklist
	if self.variables["BLACKLIST_COUNTRY"] ~= "" then
		if self.blacklist[country_data] then
			local ok
			ok, err = self:add_to_cache(self.ctx.bw.remote_addr, country_data, "ko")
			if not ok then
				return self:ret(false, "error while adding item to cache : " .. err)
			end
			self:set_metric("counters", "failed_country", 1)
			return self:ret(
				true,
				"client IP " .. self.ctx.bw.remote_addr .. " is blacklisted (country = " .. country_data .. ")",
				get_deny_status(),
				nil,
				{
					id = "country",
					country = country_data,
				}
			)
		end
	end

	-- Country IP is not in blacklist
	local ok, err = self:add_to_cache(self.ctx.bw.remote_addr, country_data, "ok")
	if not ok then
		return self:ret(false, "error while caching IP " .. self.ctx.bw.remote_addr .. " : " .. err)
	end
	return self:ret(
		true,
		"client IP " .. self.ctx.bw.remote_addr .. " is not blacklisted (country = " .. country_data .. ")"
	)
end

function country:preread()
	return self:access()
end

function country:is_in_cache(ip)
	local ok, data = self.cachestore_local:get("plugin_country_" .. self.ctx.bw.server_name .. ip)
	if not ok then
		return false, data
	end
	return true, data
end

function country:add_to_cache(ip, country_data, result)
	local ok, err = self.cachestore_local:set(
		"plugin_country_" .. self.ctx.bw.server_name .. ip,
		encode({ country = country_data, result = result }),
		86400
	)
	if not ok then
		return false, err
	end
	return true
end

return country
