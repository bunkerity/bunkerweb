local M		= {}
local http	= require "resty.http"
local cjson	= require "cjson"

function M.get_code (antibot_uri, recaptcha_sitekey)
	-- get template
	local f = io.open("/opt/bunkerized-nginx/antibot/recaptcha.html", "r")
	local template = f:read("*all")
	f:close()

	-- get recaptcha code
	f = io.open("/opt/bunkerized-nginx/antibot/recaptcha-head.data", "r")
	local recaptcha_head = f:read("*all")
	f:close()
	f = io.open("/opt/bunkerized-nginx/antibot/recaptcha-body.data", "r")
	local recaptcha_body = f:read("*all")
	f:close()

	-- edit recaptcha code
	recaptcha_head = string.format(recaptcha_head, recaptcha_sitekey)
	recaptcha_body = string.format(recaptcha_body, antibot_uri, recaptcha_sitekey)

	-- return template + edited recaptcha code
	return template:gsub("%%RECAPTCHA_HEAD%%", recaptcha_head):gsub("%%RECAPTCHA_BODY%%", recaptcha_body)
end

function M.check (token, recaptcha_secret)
	local httpc = http.new()
	local res, err = httpc:request_uri("https://www.google.com/recaptcha/api/siteverify", {
		ssl_verify = false,
		method = "POST",
		body = "secret=" .. recaptcha_secret .. "&response=" .. token .. "&remoteip=" .. ngx.var.remote_addr,
		headers = { ["Content-Type"] = "application/x-www-form-urlencoded" }
	})
	if not res then
		return 0.0
	end
	local data = cjson.decode(res.body)
	if not data.success then
		return 0.0
	end
	return data.score
end

return M
