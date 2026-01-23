local class = require "middleclass"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"

local ngx = ngx
local ERR = ngx.ERR
local INFO = ngx.INFO
local OK = ngx.OK
local get_phase = ngx.get_phase
local has_variable = utils.has_variable
local get_variable = utils.get_variable
local get_multiple_variables = utils.get_multiple_variables
local regex_match = utils.regex_match
local open = io.open
local tostring = tostring
local decode_base64 = ngx.decode_base64

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
	self.policies = {
		rule = {},
		header = {},
		footer = {},
		sitemap = {},
	}
	if get_phase() ~= "init" and self:is_needed() then
		local server_name = self.ctx.bw.server_name
		local robots_rules, err = self.internalstore:get("plugin_robotstxt_rules_" .. server_name, true)
		if not robots_rules then
			self.logger:log(ERR, err)
		else
			-- Create a copy of the table to avoid modifying the shared internalstore reference
			for _, rule in ipairs(robots_rules) do
				table.insert(self.policies.rule, rule)
			end
		end

		-- Get all rules and sitemaps from environment variables
		local variables, err = get_multiple_variables({
			"ROBOTSTXT_RULE",
			"ROBOTSTXT_HEADER",
			"ROBOTSTXT_FOOTER",
			"ROBOTSTXT_SITEMAP",
			"ROBOTSTXT_IGNORE_RULE",
		})
		if variables == nil then
			return self:ret(false, err)
		end

		local multisite, err = get_variable("MULTISITE", false)
		if not multisite then
			return self:ret(false, "can't get MULTISITE variable : " .. err)
		end
		if multisite == "no" then
			server_name = "global"
		end

		-- Add rules and sitemaps from environment variables
		local sorted_vars = {}
		for var, _ in pairs(variables[server_name] or {}) do
			if var:match("^ROBOTSTXT_") then
				table.insert(sorted_vars, var)
			end
		end

		-- Natural sort for variables like ROBOTSTXT_RULE, ROBOTSTXT_RULE_1, ROBOTSTXT_RULE_2, ROBOTSTXT_RULE_10
		table.sort(sorted_vars, function(a, b)
			-- Try to split into <base>_<number>
			local base_a, num_a = a:match("^(.-)_(%d+)$")
			local base_b, num_b = b:match("^(.-)_(%d+)$")

			-- If no numeric suffix, keep full string as base and use 0
			base_a, num_a = base_a or a, tonumber(num_a) or 0
			base_b, num_b = base_b or b, tonumber(num_b) or 0

			if base_a ~= base_b then
				return base_a < base_b
			end
			if num_a ~= num_b then
				return num_a < num_b
			end
			-- Final tie-break to keep sort stable for exact same base/num
			return a < b
		end)

		local ignore_rules = {}
		for _, var in ipairs(sorted_vars) do
			local value = variables[server_name][var]
			if value ~= "" then
				local policy_key = string.lower(string.gsub(string.gsub(var, "^ROBOTSTXT_", ""), "_%d+$", ""))
				if policy_key == "rule" then
					table.insert(self.policies.rule, value)
				elseif policy_key == "sitemap" then
					table.insert(self.policies.sitemap, value)
				elseif policy_key == "header" then
					local decoded = decode_base64(value)
					table.insert(self.policies.header, decoded or value)
				elseif policy_key == "footer" then
					local decoded = decode_base64(value)
					table.insert(self.policies.footer, decoded or value)
				elseif policy_key == "ignore_rule" then
					table.insert(ignore_rules, value)
				end
			end
		end

		-- Apply ignore rules filtering if provided
		if ignore_rules and #ignore_rules > 0 then
			local filtered_rules = {}
			for _, rule in ipairs(self.policies.rule) do
				if not is_ignored(rule, ignore_rules) then
					table.insert(filtered_rules, rule)
				end
			end
			self.policies.rule = filtered_rules
		end

		self.logger:log(
			INFO,
			"loaded "
				.. tostring(#self.policies.rule)
				.. " rules and "
				.. tostring(#self.policies.sitemap)
				.. " sitemaps for the service: "
				.. self.ctx.bw.server_name
		)
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

	local server_name, err = get_variable("SERVER_NAME", false)
	if not server_name then
		return self:ret(false, "can't get SERVER_NAME variable : " .. err)
	end

	-- Iterate over each kind and server
	for srv in server_name:gmatch("%S+") do
		-- Read rules from files
		local rule_files = {
			"/var/cache/bunkerweb/robotstxt/" .. srv .. "/darkvisitors.list",
			"/var/cache/bunkerweb/robotstxt/" .. srv .. "/rules.list",
		}
		local rules = {}
		for _, file_path in ipairs(rule_files) do
			local f = open(file_path, "r")
			if f then
				local is_darkvisitors_list = (
					file_path == "/var/cache/bunkerweb/robotstxt/" .. srv .. "/darkvisitors.list"
				)
				local first_line_skipped = false
				for line in f:lines() do
					if is_darkvisitors_list and not first_line_skipped then
						first_line_skipped = true
						-- Skip this line
					elseif line ~= "" then
						table.insert(rules, line)
					end
				end
				f:close()
			end
		end

		-- Load rules into internalstore
		local ok
		ok, err = self.internalstore:set("plugin_robotstxt_rules_" .. srv, rules, nil, true)
		if not ok then
			return self:ret(false, "can't store robotstxt rules for " .. srv .. " into internalstore : " .. err)
		end

		self.logger:log(INFO, "successfully loaded " .. tostring(#rules) .. " rules for the service: " .. srv)
	end

	return self:ret(true, "successfully loaded all robots.txt rules from files")
end

function robotstxt:access()
	if self.ctx.bw.uri == "/robots.txt" and self:is_needed() then
		local rules = self.policies.rule or {}
		local sitemaps = self.policies.sitemap or {}
		local headers = self.policies.header or {}
		local footers = self.policies.footer or {}

		-- If no rules are set, use the default rule
		if #rules == 0 then
			rules = { "User-agent: *", "Disallow: /" }
		end

		ngx.header["Content-Type"] = "text/plain; charset=utf-8"
		local output = {}
		table.insert(output, "# robots.txt generated by BunkerWeb (https://bunkerweb.io)")

		if #headers > 0 then
			for _, h in ipairs(headers) do
				table.insert(output, h)
			end
		end

		if #rules > 0 then
			for _, rule in ipairs(rules) do
				table.insert(output, rule)
			end
		end

		if #sitemaps > 0 then
			for _, sitemap in ipairs(sitemaps) do
				table.insert(output, "Sitemap: " .. sitemap)
			end
		end

		if #footers > 0 then
			for _, f in ipairs(footers) do
				table.insert(output, f)
			end
		end

		ngx.say(table.concat(output, "\n"))
		return self:ret(true, "served robots.txt", OK)
	end
	return self:ret(true, "success")
end

return robotstxt
