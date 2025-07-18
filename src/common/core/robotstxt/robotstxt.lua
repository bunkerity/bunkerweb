local class = require "middleclass"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"

local ngx = ngx
local ERR = ngx.ERR
local INFO = ngx.INFO
local get_phase = ngx.get_phase
local has_variable = utils.has_variable
local get_variable = utils.get_variable
local get_multiple_variables = utils.get_multiple_variables
local regex_match = utils.regex_match
local open = io.open
local tostring = tostring

local robotstxt = class("robotstxt", plugin)

local function is_ignored(rule, ignore_rules)
	for _, ignore_pattern in ipairs(ignore_rules) do
		if regex_match(rule, ignore_pattern) then
			return true
		end
	end
	return false
end

function robotstxt:initialize(ctx)
	plugin.initialize(self, "robotstxt", ctx)
	if get_phase() ~= "init" and self:is_needed() then
		local robot_policies, err = self.datastore:get("plugin_robotstxt_policies_" .. self.ctx.bw.server_name, true)
		if not robot_policies then
			self.logger:log(ERR, err)
			self.robot_policies = {}
		else
			self.robot_policies = robot_policies
		end
		if not self.robot_policies["rule"] then
			self.robot_policies["rule"] = {}
		end
		if not self.robot_policies["sitemap"] then
			self.robot_policies["sitemap"] = {}
		end

		-- Get ignore rules from environment variables
		local ignore_rules = {}
		for data in self.variables["ROBOTSTXT_IGNORE_RULES"]:gmatch("[^\r\n]+") do
			if data ~= "" then
				table.insert(ignore_rules, data)
			end
		end

		if #ignore_rules > 0 then
			local filtered_rules = {}
			for _, rule in ipairs(self.robot_policies["rule"]) do
				if not is_ignored(rule, ignore_rules) then
					table.insert(filtered_rules, rule)
				end
			end
			self.robot_policies["rule"] = filtered_rules
		end

		-- Add rules from environment variables
		for data in self.variables["ROBOTSTXT_RULE"]:gmatch("[^\r\n]+") do
			if data ~= "" and not is_ignored(data, ignore_rules) then
				table.insert(self.robot_policies["rule"], data)
			end
		end
		-- Add sitemaps from environment variables
		for data in self.variables["ROBOTSTXT_SITEMAP"]:gmatch("[^\r\n]+") do
			if data ~= "" then
				table.insert(self.robot_policies["sitemap"], data)
			end
		end
	end
end

function robotstxt:is_needed()
	-- Loading case
	if self.is_loading then
		return false
	end
	-- Request phases (no default)
	if self.is_request and (self.ctx.bw.server_name ~= "_") then
		return self.variables["USE_ROBOTSTXT"] == "yes"
	end
	-- Other cases : at least one service uses it
	local is_needed, err = has_variable("USE_ROBOTSTXT", "yes")
	if is_needed == nil then
		self.logger:log(ERR, "can't check USE_ROBOTSTXT variable : " .. err)
	end
	return is_needed
end

function robotstxt:init()
	-- Check if init is needed
	if not self:is_needed() then
		return self:ret(true, "init not needed")
	end

	-- Get all server names
	local server_name, err = get_variable("SERVER_NAME", false)
	if not server_name then
		return self:ret(false, "can't get SERVER_NAME variable : " .. err)
	end

	-- Get all rules and sitemaps from environment variables
	local variables, err = get_multiple_variables({
		"ROBOTSTXT_RULE",
		"ROBOTSTXT_SITEMAP",
		"ROBOTSTXT_IGNORE_RULES",
	})
	if variables == nil then
		return self:ret(false, err)
	end

	-- Iterate over each server
	for key in server_name:gmatch("%S+") do
		local policies = {
			["rule"] = {},
			["sitemap"] = {},
		}
		-- Read downloaded rules
		local file_path = "/var/cache/bunkerweb/robotstxt/" .. key .. "/rules.list"
		local f = open(file_path, "r")
		if f then
			for line in f:lines() do
				if line ~= "" then
					table.insert(policies["rule"], line)
				end
			end
			f:close()
		end

		-- Add rules and sitemaps from environment variables
		if variables[key] then
			for var, value in pairs(variables[key]) do
				if value ~= "" then
					local policy_key = string.lower(string.gsub(string.gsub(var, "^ROBOTSTXT_", ""), "_%d+$", ""))
					if policy_key == "rule" then
						policies.rule[#policies.rule + 1] = value
					elseif policy_key == "sitemap" then
						policies.sitemap[#policies.sitemap + 1] = value
					end
				end
			end
		end

		-- Get ignore rules for this service
		local ignore_rules = {}
		if variables[key] and variables[key]["ROBOTSTXT_IGNORE_RULES"] then
			for data in string.gmatch(variables[key]["ROBOTSTXT_IGNORE_RULES"], "[^\r\n]+") do
				if data ~= "" then
					table.insert(ignore_rules, data)
				end
			end
		end

		if #ignore_rules > 0 then
			local filtered_rules = {}
			for _, rule in ipairs(policies.rule) do
				if not is_ignored(rule, ignore_rules) then
					table.insert(filtered_rules, rule)
				end
			end
			policies.rule = filtered_rules
		end

		-- Load policies into datastore
		local ok
		ok, err = self.datastore:set("plugin_robotstxt_policies_" .. key, policies, nil, true)
		if not ok then
			return self:ret(false, "can't store robotstxt policies for " .. key .. " into datastore : " .. err)
		end

		self.logger:log(
			INFO,
			"successfully loaded "
				.. tostring(#policies.rule + #policies.sitemap)
				.. " policies for the service: "
				.. key
		)
	end
	return self:ret(true, "successfully loaded all robots.txt policies")
end

local function sanitize_rules(rules)
	local seen = {}
	local sanitized = {}
	local has_user_agent = false
	for _, rule in ipairs(rules) do
		local trimmed = rule:match("^%s*(.-)%s*$")
		if not seen[trimmed] then
			seen[trimmed] = true
			table.insert(sanitized, trimmed)
			if trimmed:lower():find("^user%-agent:") then
				has_user_agent = true
			end
		end
	end
	if not has_user_agent and #sanitized > 0 then
		table.insert(sanitized, 1, "User-agent: *")
	end
	return sanitized
end

local function sanitize_sitemaps(sitemaps)
	local seen = {}
	local sanitized = {}
	for _, url in ipairs(sitemaps) do
		local trimmed = url:match("^%s*(.-)%s*$")
		if trimmed ~= "" then
			-- Force HTTPS for sitemaps
			if trimmed:match("^http://") then
				trimmed = trimmed:gsub("^http://", "https://")
			end
			if not seen[trimmed] then
				seen[trimmed] = true
				table.insert(sanitized, trimmed)
			end
		end
	end
	return sanitized
end

function robotstxt:access()
	if self.ctx.bw.uri == "/robots.txt" and self:is_needed() then
		local rules = self.robot_policies and self.robot_policies["rule"] or {}
		local sitemaps = self.robot_policies and self.robot_policies["sitemap"] or {}

		-- If no rules are set, use the default rule
		if #rules == 0 then
			rules = { "User-agent: *", "Disallow: /" }
		end

		local sanitized_rules = sanitize_rules(rules)
		local sanitized_sitemaps = sanitize_sitemaps(sitemaps)

		local header = "# robots.txt generated by BunkerWeb (https://bunkerweb.io)"
		ngx.header["Content-Type"] = "text/plain; charset=utf-8"
		local output = {}
		table.insert(output, header)

		for _, rule in ipairs(sanitized_rules) do
			table.insert(output, rule)
		end
		for _, sitemap in ipairs(sanitized_sitemaps) do
			table.insert(output, "Sitemap: " .. sitemap)
		end
		ngx.say(table.concat(output, "\n"))
		return ngx.exit(ngx.HTTP_OK)
	end
	return self:ret(true, "success")
end

return robotstxt
