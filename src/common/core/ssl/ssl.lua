local class = require "middleclass"
local plugin = require "bunkerweb.plugin"

local ssl = class("ssl", plugin)

local ngx = ngx
local HTTP_MOVED_PERMANENTLY = ngx.HTTP_MOVED_PERMANENTLY

function ssl:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "ssl", ctx)
end

function ssl:access()
	-- Check if we need to redirect to HTTPS
	if
		self.ctx.bw.scheme == "http"
		and (
			(
				(self.ctx.bw.https_configured == "yes" and self.variables["AUTO_REDIRECT_HTTP_TO_HTTPS"] == "yes")
				or self.variables["REDIRECT_HTTP_TO_HTTPS"] == "yes"
			)
			and self.ctx.bw.request_uri ~= nil
			and self.ctx.bw.http_host ~= nil
		)
	then
		return self:ret(
			true,
			"redirect to HTTPS",
			HTTP_MOVED_PERMANENTLY,
			"https://" .. self.ctx.bw.http_host .. self.ctx.bw.request_uri
		)
	end
	return self:ret(true, "no redirect to HTTPS needed")
end

return ssl
