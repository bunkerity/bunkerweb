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
	return string.format([[
		<html>
			<head>
			</head>
			<body>
				<script>
					async function digestMessage(message) {
						const msgUint8 = new TextEncoder().encode(message);
						const hashBuffer = await crypto.subtle.digest('SHA-256', msgUint8);
						const hashArray = Array.from(new Uint8Array(hashBuffer));
						const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
						return hashHex;
					}
					(async () => {
						const digestHex = await digestMessage('%s');
						xhr = new XMLHttpRequest();
						xhr.open('POST', '%s');
						xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
						xhr.onload = function() {
							if (xhr.status === 200) {
								window.location.replace('%s');
							}
						};
						xhr.send(encodeURI('challenge=' + digestHex));
					})();
				</script>
			</body>
		</html>
	]], challenge, antibot_uri, original_uri)
end

function M.check (challenge, user)
	local resty_sha256 = require "resty.sha256"
	local str = require "resty.string"
	local sha256 = resty_sha256:new()
	sha256:update(challenge)
	local digest = sha256:final()
	return str.to_hex(digest) == user
end

return M
