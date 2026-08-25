local class = require "middleclass"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"

local ssl = class("ssl", plugin)

local ngx = ngx
local sub = string.sub
local public_authority = utils.public_authority
local HTTP_MOVED_PERMANENTLY = ngx.HTTP_MOVED_PERMANENTLY

local ACME_CHALLENGE_PREFIX = "/.well-known/acme-challenge/"

function ssl:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "ssl", ctx)
end

function ssl:access()
	-- ssl runs before letsencrypt in the access chain (order.json: ssl 0, letsencrypt 2), so its
	-- whitelist never gets the chance to run and the challenge is answered with a 301. ACME servers
	-- follow it, which silently makes an HTTP-01 validation depend on port 443 being reachable and
	-- on the TLS handshake working for a name that has no certificate yet.
	if self.ctx.bw.uri ~= nil and sub(self.ctx.bw.uri, 1, #ACME_CHALLENGE_PREFIX) == ACME_CHALLENGE_PREFIX then
		return self:ret(true, "no redirect to HTTPS for the ACME challenge")
	end

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
		-- `http_host` is the authority the client used, port included, which is why this redirect
		-- works on a default install: 8443 is published as 443, so dropping the client's :80 and
		-- adding nothing lands on the right place. That contract only holds while this service
		-- listens where the fleet does. When it declared HTTPS ports of its own, the rendered port
		-- IS the reachable one and the redirect has to carry it -- otherwise it points at 443,
		-- where this service has no listener at all. public_authority() returns `http_host`
		-- unchanged for every service that did not move.
		local authority = public_authority(self.ctx.bw.http_host, "HTTPS_PORT", self.ctx.bw.server_name)
		return self:ret(
			true,
			"redirect to HTTPS",
			HTTP_MOVED_PERMANENTLY,
			"https://" .. authority .. self.ctx.bw.request_uri
		)
	end
	return self:ret(true, "no redirect to HTTPS needed")
end

return ssl
