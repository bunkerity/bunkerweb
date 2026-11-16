local class = require "middleclass"
local plugin = require "bunkerweb.plugin"

local hellotest = class("hellotest", plugin)

function hellotest:initialize(ctx)
	plugin.initialize(self, "hellotest", ctx)
end

-- Module-level function, no self: the hook calls it with the hello table only (nothing in it may yield).
-- A service named drop.example.com has its handshake closed, every other named service is only reported
-- ("detect" logs and lets the client through). A handshake that reaches the default server carries no service.
function hellotest.client_hello(hello)
	if hello.service == "drop.example.com" then
		return "drop", "hellotest service=" .. hello.service
	elseif hello.service then
		return "detect", "hellotest service=" .. hello.service
	end
	return nil
end

return hellotest
