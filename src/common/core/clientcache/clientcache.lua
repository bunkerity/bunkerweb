local class       = require "middleclass"
local plugin      = require "bunkerweb.plugin"
local utils       = require "bunkerweb.utils"

local clientcache = class("clientcache", plugin)

function clientcache:initialize()
  -- Call parent initialize
  plugin.initialize(self, "clientcache")
end

function clientcache:header()
  -- Override Cache-Control header if needed
  if self.variables["USE_CLIENT_CACHE"] == "yes" then
    local keep_upstream_headers = utils.get_variable("KEEP_UPSTREAM_HEADERS")
    if ngx.header["Cache-Control"] == nil or keep_upstream_headers ~= "*" and utils.regex_match(keep_upstream_headers, "(^| )Cache-Control($| )") == nil then
      ngx.header["Cache-Control"] = ngx.var.cache_control
    end
  end
  return self:ret(true, "Success")
end

return clientcache
