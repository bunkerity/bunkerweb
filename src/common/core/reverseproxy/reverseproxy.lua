local class        = require "middleclass"
local plugin       = require "bunkerweb.plugin"
local utils        = require "bunkerweb.utils"

local reverseproxy = class("reverseproxy", plugin)

function reverseproxy:initialize()
  -- Call parent initialize
  plugin.initialize(self, "reverseproxy")
end

function reverseproxy:header()
  -- Set proxy cache header if needed
  if self.variables["USE_PROXY_CACHE"] == "yes" and self.variables["PROXY_CACHE_VALID"] ~= "" then
    ngx.header["X-Proxy-Cache"] = ngx.var.upstream_cache_status
  end
  -- Get variables
  local variables, err = utils.get_multiple_variables({ "REVERSE_PROXY_HEADERS_CLIENT" })
  if variables == nil then
    return self:ret(false, err)
  end
  -- Add reverseproxy client headers
  for srv, vars in pairs(variables) do
    if srv == self.ctx.bw.server_name or srv == "global" then
      for var, value in pairs(vars) do
        if utils.regex_match(var, "REVERSE_PROXY_HEADERS_CLIENT") and value then
          local iterator, err = ngx.re.gmatch(value, "([\\w-]+) ([^;]+)")
          if not iterator then
            return self:ret(false, "Error while matching reverseproxy client headers: " .. err .. " - " .. value)
          end
          while true do
            local m, err = iterator()
            if err then
              return self:ret(false, "Error while matching reverseproxy client headers: " .. err .. " - " .. value)
            end
            if not m then
              -- No more matches
              break
            end
            ngx.header[m[1]] = m[2]
          end
        end
      end
    end
  end
  return self:ret(true, "Success")
end

return reverseproxy
