-- Stand-in for an HTTP-only plugin that gates on the HTTP ngx_lua version at require time. The stream ngx_lua
-- reports 17, so requiring this module in the stream Lua VM raises.
if ngx.config.ngx_lua_version < 9005 then
	error("ngx_lua 0.9.5+ required")
end

local class = require "middleclass"
local plugin = require "bunkerweb.plugin"

local http_only_probe = class("http_only_probe", plugin)

function http_only_probe:initialize(ctx)
	plugin.initialize(self, "http_only_probe", ctx)
end

return http_only_probe
