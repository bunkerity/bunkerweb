local class = require("middleclass")
local cs = require("crowdsec.lib.bouncer")
local plugin = require("bunkerweb.plugin")
local utils = require("bunkerweb.utils")

local crowdsec = class("crowdsec", plugin)

local ngx = ngx
local ERR = ngx.ERR
local HTTP_INTERNAL_SERVER_ERROR = ngx.HTTP_INTERNAL_SERVER_ERROR
local HTTP_OK = ngx.HTTP_OK
local get_deny_status = utils.get_deny_status
local cs_init = cs.init
local cs_allow = cs.Allow

function crowdsec:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "crowdsec", ctx)
end

function crowdsec:init()
	-- Check if init is needed
	if self.variables["USE_CROWDSEC"] ~= "yes" or self.is_loading then
		return self:ret(true, "init not needed")
	end
	-- Init CS
	local ok, err = cs_init("/var/cache/bunkerweb/crowdsec/crowdsec.conf", "crowdsec-bunkerweb-bouncer/v1.8")
	if not ok then
		self.logger:log(ERR, "error while initializing bouncer : " .. err)
		return self:ret(false, err)
	end
	return self:ret(true, "success")
end

function crowdsec:access()
	-- Check if CS is activated
	if self.variables["USE_CROWDSEC"] ~= "yes" then
		return self:ret(true, "CrowdSec plugin not enabled")
	end
	-- Do the check
	local ok, err, banned = cs_allow(self.ctx.bw.remote_addr)
	if not ok then
		return self:ret(false, "Error while executing CrowdSec bouncer : " .. err)
	end
	if banned then
		return self:ret(true, "CrowdSec bouncer denied request", get_deny_status())
	end

	return self:ret(true, "Not denied by CrowdSec bouncer")
end

function crowdsec:api()
	if self.ctx.bw.uri == "/crowdsec/ping" and self.ctx.bw.request_method == "POST" then
		-- Check crowdsec connection
		if self.variables["USE_CROWDSEC"] ~= "yes" then
			return self:ret(true, "CrowdSec plugin is not enabled", HTTP_OK)
		end

		-- Do the check
		local ok, err = cs_allow("127.0.0.1")
		if not ok then
			return self:ret(true, "Error while executing CrowdSec bouncer : " .. err, HTTP_INTERNAL_SERVER_ERROR)
		end
		return self:ret(true, "The test request is successful", HTTP_OK)
	end
	return self:ret(false, "success")
end

return crowdsec
