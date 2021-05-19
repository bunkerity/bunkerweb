local M		= {}
local captcha	= require "misc.captcha"
local base64	= require "misc.base64"

function M.get_challenge ()
	local cap = captcha.new()
	cap:font("/usr/local/lib/lua/misc/Vera.ttf")
	cap:generate()
	return cap:jpegStr(70), cap:getStr()
end

function M.get_code (img, antibot_uri)
	-- get template
	local f = io.open("/antibot/captcha.html", "r")
	local template = f:read("*all")
	f:close()

	-- get captcha code
	f = io.open("/antibot/captcha.data", "r")
	local captcha_data = f:read("*all")
	f:close()

	-- edit captcha code
	captcha_data = string.format(captcha_data, antibot_uri, base64.encode(img))

	-- return template + edited captcha code
	return template:gsub("%%CAPTCHA%%", captcha_data)
end

function M.check (captcha_user, captcha_valid)
	return captcha_user == captcha_valid
end

return M
