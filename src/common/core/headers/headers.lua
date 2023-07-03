local class   = require "middleclass"
local plugin  = require "bunkerweb.plugin"
local utils   = require "bunkerweb.utils"

local headers = class("headers", plugin)

function headers:initialize()
  -- Call parent initialize
  plugin.initialize(self, "headers")
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
end

function headers:header()
  -- Override upstream headers if needed
  local ssl = utils.get_variable("AUTO_LETS_ENCRYPT", true) == "yes" or
      utils.get_variable("USE_CUSTOM_SSL", true) == "yes" or
      utils.get_variable("GENERATE_SELF_SIGNED_SSL", true) == "yes"
  for variable, header in pairs(self.all_headers) do
    if ngx.header[header] == nil or self.variables[variable] and self.variables["KEEP_UPSTREAM_HEADERS"] ~= "*" and utils.regex_match(self.variables["KEEP_UPSTREAM_HEADERS"], "(^| )" .. header .. "($| )") == nil then
      if (header ~= "Strict-Transport-Security" or ssl) then
        if header == "Content-Security-Policy" and self.variables["CONTENT_SECURITY_POLICY_REPORT_ONLY"] == "yes" then
          ngx.header["Content-Security-Policy-Report-Only"] = self.variables[variable]
        else
          ngx.header[header] = self.variables[variable]
        end
      end
    end
  end
  -- Get variables
  local variables, err = utils.get_multiple_variables({ "CUSTOM_HEADER" })
  if variables == nil then
    return self:ret(false, err)
  end
  -- Add custom headers
  for srv, vars in pairs(variables) do
    if srv == self.ctx.bw.server_name or srv == "global" then
      for var, value in pairs(vars) do
        if utils.regex_match(var, "CUSTOM_HEADER") and value then
          local m = utils.regex_match(value, "([\\w-]+): ([^,]+)")
          if m then
            ngx.header[m[1]] = m[2]
          end
        end
      end
    end
  end
  -- Remove headers
  if self.variables["REMOVE_HEADERS"] ~= "" then
    local iterator, err = ngx.re.gmatch(self.variables["REMOVE_HEADERS"], "([\\w-]+)")
    if not iterator then
      return self:ret(false, "Error while matching remove headers: " .. err)
    end
    while true do
      local m, err = iterator()
      if err then
        return self:ret(false, "Error while matching remove headers: " .. err)
      end
      if not m then
        -- No more remove headers
        break
      end
      ngx.header[m[1]] = nil
    end
  end
  return self:ret(true, "Edited headers for request")
end

return headers
