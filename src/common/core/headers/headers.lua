local class   = require "middleclass"
local plugin  = require "bunkerweb.plugin"
local utils   = require "bunkerweb.utils"

local headers = class("headers", plugin)

function headers:initialize(ctx)
  -- Call parent initialize
  plugin.initialize(self, "headers", ctx)
  self.all_headers = {
    ["STRICT_TRANSPORT_SECURITY"] = "Strict-Transport-Security",
    ["CONTENT_SECURITY_POLICY"] = "Content-Security-Policy",
    ["REFERRER_POLICY"] = "Referrer-Policy",
    ["PERMISSIONS_POLICY"] = "Permissions-Policy",
    ["FEATURE_POLICY"] = "Feature-Policy",
    ["X_FRAME_OPTIONS"] = "X-Frame-Options",
    ["X_CONTENT_TYPE_OPTIONS"] = "X-Content-Type-Options",
    ["X_XSS_PROTECTION"] = "X-XSS-Protection"
  }
	-- Load data from datastore if needed
	if ngx.get_phase() ~= "init" then
		-- Get custom headers from datastore
		local custom_headers, err = self.datastore:get("plugin_headers_custom_headers", true)
		if not custom_headers then
			self.logger:log(ngx.ERR, err)
			return
		end
		self.custom_headers = {}
		-- Extract global headers
		if custom_headers.global then
			for k, v in pairs(custom_headers.global) do
				self.custom_headers[k] = v
			end
		end
		-- Extract and overwrite if needed server headers
		if custom_headers[self.ctx.bw.server_name] then
			for k, v in pairs(custom_headers[self.ctx.bw.server_name]) do
				self.custom_headers[k] = v
			end
		end
	end
end

function headers:init()
	-- Get variables
	local variables, err = utils.get_multiple_variables({ "CUSTOM_HEADER" })
	if variables == nil then
		return self:ret(false, err)
	end
	-- Store custom headers name and value
	local data = {}
	local i = 0
	for srv, vars in pairs(variables) do
		for var, value in pairs(vars) do
      if data[srv] == nil then
        data[srv] = {}
      end
      local m = utils.regex_match(value, "([\\w-]+): ([^,]+)")
      if m then
        data[srv][m[1]] = m[2]
      end
      i = i + 1
		end
	end
	local ok, err = self.datastore:set("plugin_headers_custom_headers", data, nil, true)
	if not ok then
		return self:ret(false, err)
	end
	return self:ret(true, "successfully loaded " .. tostring(i) .. " custom headers")
end

function headers:header()
  -- Override upstream headers if needed
  local ssl = self.ctx.bw.scheme == "https"
  for variable, header in pairs(self.all_headers) do
    if ngx.header[header] == nil or (self.variables[variable] ~= "" and self.variables["KEEP_UPSTREAM_HEADERS"] ~= "*" and utils.regex_match(self.variables["KEEP_UPSTREAM_HEADERS"], "(^| )" .. header .. "($| )") == nil) then
      if (header ~= "Strict-Transport-Security" or ssl) then
        if header == "Content-Security-Policy" and self.variables["CONTENT_SECURITY_POLICY_REPORT_ONLY"] == "yes" then
          ngx.header["Content-Security-Policy-Report-Only"] = self.variables[variable]
        else
          ngx.header[header] = self.variables[variable]
        end
      end
    end
  end
  -- Add custom headers
  for header, value in pairs(self.custom_headers) do
    ngx.header[header] = value
  end
  -- Remove headers
  if self.variables["REMOVE_HEADERS"] ~= "" then
    for header in self.variables["REMOVE_HEADERS"]:gmatch("%S+") do
      ngx.header[header] = nil
    end
  end
  return self:ret(true, "edited headers for request")
end

return headers
