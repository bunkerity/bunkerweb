-- Run from the repository root: lua tests/unit/test_lua_bunkernet_proxy.lua
-- Exercise the real BunkerNet request method with an HTTP client double.
local source = arg[1] or "src/common/core/bunkernet/bunkernet.lua"
local env, options, sent, credentials, closed
local function reset(values)
	env, options, sent, credentials, closed = values, nil, nil, nil, false
end
os.getenv = function(key)
	return env[key]
end
package.loaded["middleclass"] = function()
	return {}
end
package.loaded["bunkerweb.plugin"] = {}
package.loaded["bunkerweb.utils"] = {
	normalize_ip = function(ip)
		if ip:match("^%d+%.%d+%.%d+%.%d+$") or ip:find(":", 1, true) then
			return ip
		end
	end,
	is_ip_in_networks = function(ip, networks)
		return ip == "192.0.2.10" and networks[1] == "192.0.2.0/24"
	end,
}
package.loaded["cjson"] = {
	encode = function()
		return "{}"
	end,
	decode = function()
		return {}
	end,
}
ngx = {
	encode_base64 = function(value)
		credentials = value
		return "encoded"
	end,
}
package.loaded["resty.http"] = {
	new = function()
		return {
			set_timeout = function(_, timeout)
				assert(timeout == 5000)
			end,
			parse_uri = function(_, url)
				local scheme, authority = url:match("^(https?)://([^/]+)")
				assert(scheme and authority)
				local host, port = authority:match("^(%[[^%]]+%]):(%d+)$")
				if not host then
					host, port = authority:match("^([^:]+):(%d+)$")
				end
				return { scheme, host or authority, tonumber(port) or (scheme == "https" and 443 or 80) }
			end,
			set_proxy_options = function(_, value)
				options = value
			end,
			request_uri = function(_, url, params)
				sent = url
				assert(params.headers["Proxy-Authorization"] == nil)
				return { status = 200, body = "{}" }
			end,
			close = function()
				closed = true
			end,
		}
	end,
}
-- The OS metadata is unrelated to the proxy behavior.
io.popen = function()
	return nil
end
local bunkernet = assert(loadfile(source))()
local function request(values, url)
	reset(values)
	local instance = { variables = { BUNKERNET_SERVER = url }, version = "test" }
	local ok, err = bunkernet.request(instance, "GET", "/ping", {})
	assert(closed)
	return ok, err
end

local https = "https://api.example.com"
local http = "http://api.example.com"
local proxy = "http://proxy.example.com:3128"

assert(request({}, https))
assert(options == nil and sent == https .. "/ping")

assert(request({ HTTPS_PROXY = proxy }, https))
assert(options.https_proxy == proxy and options.https_proxy_authorization == nil)

assert(request({ HTTP_PROXY = proxy }, http))
assert(options.http_proxy == proxy and options.http_proxy_authorization == nil)

assert(request({ HTTP_PROXY = proxy }, https))
assert(options == nil and sent)

assert(request({ HTTPS_PROXY = proxy, https_proxy = "" }, https))
assert(options == nil and sent)

assert(request({ HTTPS_PROXY = "http://other.example.com", https_proxy = proxy }, https))
assert(options.https_proxy == proxy)

local auth_proxy = "http://us%65r:p%40ss%3Aword+%2B@proxy.example.com:3128"
assert(request({ HTTPS_PROXY = auth_proxy }, https))
assert(options.https_proxy == proxy and options.https_proxy_authorization == "Basic encoded")
assert(credentials == "user:p@ss:word++")

assert(request({ HTTP_PROXY = auth_proxy }, http))
assert(options.http_proxy == proxy and options.http_proxy_authorization == "Basic encoded")
assert(credentials == "user:p@ss:word++")

assert(request({ HTTPS_PROXY = "http://user:pass@[2001:db8::1]:3128/" }, https))
assert(options.https_proxy == "http://[2001:db8::1]:3128")
assert(credentials == "user:pass")

for _, no_proxy in ipairs({ "*", ".example.com", " api.example.com ", "api.example.com:80" }) do
	assert(request({ HTTP_PROXY = auth_proxy, NO_PROXY = no_proxy }, http))
	assert(options == nil and credentials == nil and sent)
end
assert(request({ HTTPS_PROXY = auth_proxy, NO_PROXY = ".example.com", no_proxy = "" }, https))
assert(options.https_proxy == proxy)

assert(request({ HTTPS_PROXY = auth_proxy, NO_PROXY = "api.example.com:80" }, https))
assert(options.https_proxy == proxy)

assert(request({ HTTPS_PROXY = auth_proxy, NO_PROXY = "192.0.2.0/24" }, "https://192.0.2.10"))
assert(options == nil and sent)

assert(request({ HTTPS_PROXY = auth_proxy, NO_PROXY = "[2001:db8::1]:443" }, "https://[2001:db8::1]"))
assert(options == nil and sent)

assert(request({ HTTPS_PROXY = auth_proxy, NO_PROXY = "example.com" }, "https://notexample.com"))
assert(options.https_proxy == proxy)

for _, invalid in ipairs({ "https://user:secret@proxy.example.com", "http://user:secret@", "http://user:secret@proxy.example.com:abc" }) do
	local ok, err = request({ HTTPS_PROXY = invalid }, https)
	assert(not ok and not sent and not options)
	assert(err == "invalid BunkerNet proxy URL (expected an HTTP proxy URL)")
	assert(not err:find("secret", 1, true))
end
print("BunkerNet proxy regression checks passed")
