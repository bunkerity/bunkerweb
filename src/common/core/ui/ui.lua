local class = require "middleclass"
local plugin = require "bunkerweb.plugin"

local ui = class("ui", plugin)

function ui:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "ui", ctx)
end

function ui:set()
	local https_configured = self.variables["USE_UI"]
	if https_configured == "yes" then
		self.ctx.bw.https_configured = "yes"
	end
	return self:ret(true, "set https_configured to " .. https_configured)
end

return ui