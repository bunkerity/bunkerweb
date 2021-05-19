local M         = {}
local session   = require "resty.session"

function M.get_challenge ()
	local charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIKLMNOPQRSTUVWXYZ0123456789"
	math.randomseed(os.clock()*os.time())
	local random = ""
	local rand = 0
	for i = 1, 20 do
		rand = math.random(1, #charset)
		random = random .. charset:sub(rand, rand)
	end
	return random
end

function M.get_code (challenge, antibot_uri, original_uri)
	-- get template
	local f = io.open("/antibot/javascript.html", "r")
	local template = f:read("*all")
	f:close()

	-- get JS code
	f = io.open("/antibot/javascript.data", "r")
	local javascript = f:read("*all")
	f:close()

	-- edit JS code
	javascript = string.format(javascript, challenge, antibot_uri, original_uri)

	-- return template + edited JS code
	return template:gsub("%%JAVASCRIPT%%", javascript)
end

function M.check (challenge, user)
	ngx.log(ngx.ERR, "debug challenge = " .. challenge)
	ngx.log(ngx.ERR, "debug user = " .. user)
	local resty_sha256 = require "resty.sha256"
	local str = require "resty.string"
	local sha256 = resty_sha256:new()
	sha256:update(challenge .. user)
	local digest = sha256:final()
	ngx.log(ngx.ERR, "debug digest = " .. str.to_hex(digest))
	return str.to_hex(digest):find("^0000") ~= nil
end

return M
