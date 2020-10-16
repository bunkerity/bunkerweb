local M		= {}
local http	= require "resty.http"
local cjson	= require "cjson"

function M.get_code (antibot_uri, recaptcha_sitekey)
	return string.format([[
		<html>
			<head>
				<script src="https://www.google.com/recaptcha/api.js?render=%s"></script>
			</head>
			<body>
				<form method="POST" action="%s" id="form">
					<input type="hidden" name="token" id="token">
				</form>
				<script>
					grecaptcha.ready(function() {
						grecaptcha.execute('%s', {action: 'recaptcha'}).then(function(token) {
							document.getElementById("token").value = token;
							document.getElementById("form").submit();
						});;
					});
				</script>
			</body>
		</html>
	]], recaptcha_sitekey, antibot_uri, recaptcha_sitekey)
end

function M.check (token, recaptcha_secret)
	local httpc = http.new()
	local res, err = httpc:request_uri("https://www.google.com/recaptcha/api/siteverify", {
		ssl_verify = false,
		method = "POST",
		body = "secret=" .. recaptcha_secret .. "&response=" .. token,
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
