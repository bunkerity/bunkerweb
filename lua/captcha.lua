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
	return string.format([[
		<html>
			<head>
			</head>
			<body>
				<form method="POST" action="%s">
				Img = <img src="data:image/jpeg;base64,%s" /><br />
				Enter captcha : <input type="text" name="captcha" /><br />
				<input type="submit" value="send" />
				</form>
			</body>
		</html>
	]], antibot_uri, base64.encode(img))
end

function M.check (captcha_user, captcha_valid)
	return captcha_user == captcha_valid
end

return M
