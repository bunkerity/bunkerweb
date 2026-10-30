local get_variable = require("bunkerweb.utils").get_variable
local open = io.open
local match = string.match
local sub = string.sub

local acme = {}

local PREFIX = "/.well-known/acme-challenge/"

function acme.is_challenge_uri(ctx)
	local uri = ctx and ctx.bw and ctx.bw.uri
	-- Both access hooks call this on every request; string.match is a LuaJIT NYI, so the cheap
	-- prefix comparison has to reject the general path before any pattern runs.
	return type(uri) == "string" and sub(uri, 1, #PREFIX) == PREFIX
end

function acme.is_http_challenge(ctx)
	if not acme.is_challenge_uri(ctx) then
		return false
	end
	local token = match(ctx.bw.uri, "^/%.well%-known/acme%-challenge/([A-Za-z0-9_%-]+)$")
	if
		not token
		or get_variable("AUTO_LETS_ENCRYPT", true, ctx) ~= "yes"
		or get_variable("LETS_ENCRYPT_CHALLENGE", true, ctx) ~= "http"
		or get_variable("LETS_ENCRYPT_PASSTHROUGH", true, ctx) ~= "no"
	then
		return false
	end
	local file = open("/var/tmp/bunkerweb/lets-encrypt/.well-known/acme-challenge/" .. token, "rb")
	if not file then
		return false
	end
	-- A bounded read rejects directories, unreadable files and empty/stale token placeholders.
	local byte = file:read(1)
	file:close()
	return byte ~= nil and byte ~= ""
end

return acme
