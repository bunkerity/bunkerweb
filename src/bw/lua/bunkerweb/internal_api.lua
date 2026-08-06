local cdatastore = require "bunkerweb.datastore"
local http = require "resty.http"

local ngx = ngx
local shared = ngx.shared
local subsystem = ngx.config.subsystem
local internalstore = cdatastore:new(subsystem == "http" and shared.internalstore or shared.internalstore_stream)

local SOCKET = "unix:/var/run/bunkerweb/api-internal.sock"
local TIMEOUT = 5000
local INTERNAL_TOKEN_HEADER = "X-BunkerWeb-Internal-Token"

local internal_api = {}

local function get_variable(name)
	local variables, err = internalstore:get("variables", true)
	if not variables then
		return nil, "can't access variables from internalstore : " .. err
	end
	local value = variables.global and variables.global[name]
	if value == nil then
		return nil, name .. " is not configured"
	end
	return value
end

function internal_api.request(path, options)
	if type(path) ~= "string" or path:sub(1, 1) ~= "/" then
		return nil, "path must start with /"
	end
	if options ~= nil and type(options) ~= "table" then
		return nil, "options must be a table"
	end
	options = options or {}

	local server_name, err = get_variable("API_SERVER_NAME")
	if not server_name or server_name == "" then
		return nil, err or "API_SERVER_NAME is empty"
	end

	local headers = {}
	for name, value in pairs(options.headers or {}) do
		local lower_name = name:lower()
		if lower_name ~= "host" and lower_name ~= "authorization" and lower_name ~= INTERNAL_TOKEN_HEADER:lower() then
			headers[name] = value
		end
	end
	headers["Host"] = server_name
	local token, token_err = internalstore:get("internal_api_token", true)
	if not token or token == "" then
		return nil, "can't access internal API token from internalstore : " .. (token_err or "not found")
	end
	headers[INTERNAL_TOKEN_HEADER] = token

	local httpc
	httpc, err = http.new()
	if not httpc then
		return nil, "can't instantiate HTTP client : " .. tostring(err)
	end
	httpc:set_timeout(options.timeout or TIMEOUT)

	local ok
	ok, err = httpc:connect({ host = SOCKET })
	if not ok then
		httpc:close()
		return nil, "can't connect to internal API : " .. tostring(err)
	end

	local response
	response, err = httpc:request({
		method = options.method or "GET",
		path = path,
		headers = headers,
		body = options.body,
	})
	if not response then
		httpc:close()
		return nil, "internal API request failed : " .. tostring(err)
	end

	local body
	body, err = response:read_body()
	httpc:close()
	if not body then
		return nil, "can't read internal API response : " .. tostring(err)
	end
	response.body = body
	return response
end

return internal_api
