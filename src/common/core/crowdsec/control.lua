-- CrowdSec management runs only through the authenticated BunkerWeb instance API.
local http = require "resty.http"
local json = require("cjson.safe").new()
json.decode_array_with_array_mt(true)
local control = {}

local function list()
	return setmetatable({}, json.array_mt)
end

local function text(value, limit)
	return type(value) == "string" and value:sub(1, limit or 512) or nil
end

local function integer(value)
	return type(value) == "number" and value > 0 and value <= 9007199254740991 and value == math.floor(value)
end

local function array(value)
	if value == json.null then
		return list()
	end
	if type(value) ~= "table" or getmetatable(value) ~= json.array_mt then
		return nil
	end
	for key in pairs(value) do
		if not integer(key) or key > #value then
			return nil
		end
	end
	return value
end

local function decision(value)
	if type(value) ~= "table" or not integer(value.id) then
		return nil
	end
	if not text(value.scope) or not text(value.value) or not text(value.type) then
		return nil
	end
	return {
		id = value.id,
		scope = text(value.scope, 32),
		value = text(value.value, 128),
		type = text(value.type, 64),
		origin = text(value.origin),
		scenario = text(value.scenario),
		duration = text(value.duration, 128),
		uuid = text(value.uuid, 128),
	}
end

local function decisions(value)
	local items = array(value)
	if not items then
		return nil
	end
	local result = list()
	for _, item in ipairs(items) do
		local safe = decision(item)
		if not safe then
			return nil
		end
		result[#result + 1] = safe
	end
	return result
end

local function safe_alert(value)
	if type(value) ~= "table" or not integer(value.id) then
		return nil
	end
	if value.source ~= nil and value.source ~= json.null and type(value.source) ~= "table" then
		return nil
	end
	local source = type(value.source) == "table" and value.source or {}
	local alert_decisions = decisions(value.decisions == nil and list() or value.decisions)
	local events = array(value.events == nil and list() or value.events)
	if not alert_decisions or not events then
		return nil
	end
	local safe = {
		id = value.id,
		scenario = text(value.scenario),
		message = text(value.message, 2048),
		start_at = text(value.start_at, 64),
		stop_at = text(value.stop_at, 64),
		source = {},
		decisions = alert_decisions,
		events = list(),
	}
	for _, key in ipairs({ "ip", "range", "scope", "value", "cn", "as_name", "as_number" }) do
		safe.source[key] = text(source[key])
	end
	local allowed = {
		source_ip = true,
		http_path = true,
		http_verb = true,
		http_status = true,
		target_fqdn = true,
		service = true,
		log_type = true,
	}
	for index, event in ipairs(events) do
		if index > 50 then
			break
		end
		if type(event) == "table" then
			local entry = { timestamp = text(event.timestamp, 64), meta = list() }
			local metadata = array(event.meta == nil and list() or event.meta)
			if not metadata then
				return nil
			end
			for _, meta in ipairs(metadata) do
				if type(meta) == "table" and allowed[meta.key] then
					entry.meta[#entry.meta + 1] = { key = meta.key, value = text(meta.value, 1024) }
				end
			end
			safe.events[#safe.events + 1] = entry
		end
	end
	return safe
end

local function safe_allowlist(value)
	if type(value) ~= "table" or type(value.name) ~= "string" or value.name == "" or #value.name > 512 then
		return nil
	end
	if value.console_managed ~= nil and type(value.console_managed) ~= "boolean" then
		return nil
	end
	local items = array(value.items)
	if not items then
		return nil
	end
	local safe = {
		name = value.name,
		description = text(value.description),
		console_managed = value.console_managed == true,
		created_at = text(value.created_at, 64),
		updated_at = text(value.updated_at, 64),
		items = list(),
		total = #items,
		limit = 200,
	}
	for index, item in ipairs(items) do
		if type(item) ~= "table" or type(item.value) ~= "string" or item.value == "" or #item.value > 128 then
			return nil
		end
		if item.expiration ~= nil and item.expiration ~= json.null and type(item.expiration) ~= "string" then
			return nil
		end
		if index <= safe.limit then
			safe.items[#safe.items + 1] = {
				value = item.value,
				description = text(item.description),
				created_at = text(item.created_at, 64),
				expiration = text(item.expiration, 64),
			}
		end
	end
	return safe
end

function control.run(conf, _cache, action, params)
	params = params or {}
	if type(params) ~= "table" then
		return nil, "Invalid CrowdSec request", 400
	end
	local endpoint = conf.API_URL or ""
	local authority = endpoint:match("^https?://([^/]+)")
	if not authority or authority:find("@", 1, true) or endpoint:find("[%c?#]") then
		return nil, "No valid CrowdSec Local API configured", 409
	end
	endpoint = endpoint:gsub("/+$", "")
	local token
	local function request(method, path, body, management)
		local client = http.new()
		local now = ngx.now or ngx.time
		local timeout = math.max(conf.REQUEST_TIMEOUT or 1000, 5000)
		local deadline = now() + timeout / 1000
		client:set_timeout(timeout)
		local headers = { ["X-Api-Key"] = conf.API_KEY, ["Content-Type"] = "application/json" }
		if management then
			headers = { Authorization = "Bearer " .. token, ["Content-Type"] = "application/json" }
		end
		-- CrowdSec's machine login rejects user agents with more than one slash.
		headers["User-Agent"] = "crowdsec-bunkerweb-manager/1.0"
		local parsed = client:parse_uri(endpoint .. "/v1/" .. path, false)
		if not parsed then
			client:close()
			return nil, "Invalid CrowdSec Local API URL"
		end
		local scheme, host, port, uri, query_string = parsed[1], parsed[2], parsed[3], parsed[4], parsed[5]
		local options = {
			scheme = scheme,
			host = host,
			port = port,
			path = uri,
			query = query_string,
			ssl_server_name = host,
			method = method,
			headers = headers,
			body = body and json.encode(body),
			ssl_verify = true,
		}
		local connected = client:connect(options)
		if not connected then
			client:close()
			return nil, "CrowdSec Local API is unreachable"
		end
		local response = client:request(options)
		if not response then
			client:close()
			return nil, "CrowdSec Local API is unreachable"
		end
		if response.status ~= 200 then
			client:close()
			return nil,
				"CrowdSec " .. method .. " " .. path:match("^[^?]+") .. " returned HTTP " .. tostring(response.status)
		end
		local maximum = 16 * 1024 * 1024
		local content_length = response.headers and response.headers["Content-Length"]
		if type(content_length) == "string" and tonumber(content_length) and tonumber(content_length) > maximum then
			client:close()
			return nil, "CrowdSec response exceeds the supported size"
		end
		local chunks, size = {}, 0
		while true do
			if now() >= deadline then
				client:close()
				return nil, "CrowdSec response timed out"
			end
			client:set_timeout(math.max(1, (deadline - now()) * 1000))
			local chunk, err = response.body_reader(math.min(65536, maximum - size + 1))
			if err then
				client:close()
				return nil, "Unable to read the CrowdSec response"
			end
			if not chunk then
				break
			end
			size = size + #chunk
			if size > maximum then
				client:close()
				return nil, "CrowdSec response exceeds the supported size"
			end
			chunks[#chunks + 1] = chunk
		end
		client:close()
		local decoded = json.decode(table.concat(chunks))
		if decoded == nil then
			return nil, "CrowdSec returned invalid JSON"
		end
		return decoded
	end
	local function login()
		local result, err = request(
			"POST",
			"watchers/login",
			{ machine_id = conf.MANAGEMENT_LOGIN, password = conf.MANAGEMENT_PASSWORD }
		)
		if not result then
			return nil, err
		end
		if
			type(result) ~= "table"
			or not text(result.token, 16384)
			or #result.token > 16384
			or result.token:find("[%c]")
		then
			return nil, "CrowdSec returned an invalid management token"
		end
		token = result.token
		return true
	end
	local function query(filters)
		local result, err = request("GET", "decisions?" .. ngx.encode_args(filters))
		if not result then
			return nil, err
		end
		local items = decisions(result)
		if not items then
			return nil, "CrowdSec returned invalid decisions"
		end
		return items
	end
	if action == "decisions" then
		local limit, offset = params.limit or 50, params.offset or 0
		if
			not integer(limit)
			or limit > 200
			or type(offset) ~= "number"
			or offset < 0
			or offset ~= math.floor(offset)
		then
			return nil, "Invalid decision pagination", 400
		end
		local filters = {}
		for _, pair in ipairs({ { "ip", "ip" }, { "origin", "origins" }, { "scenario", "scenarios_containing" } }) do
			local value = params[pair[1]]
			if value ~= nil then
				if type(value) ~= "string" or #value > 512 or value:find("[%c]") then
					return nil, "Invalid decision filter", 400
				end
				if value ~= "" then
					filters[pair[2]] = value
				end
			end
		end
		if filters.ip then
			filters.contains = "true"
		end
		local items, err = query(filters)
		if not items then
			return nil, err, 502
		end
		table.sort(items, function(a, b)
			return a.id > b.id
		end)
		local page = list()
		for i = offset + 1, math.min(#items, offset + limit) do
			page[#page + 1] = items[i]
		end
		return { decisions = page, total = #items, offset = offset, limit = limit, observed_at = ngx.time() }, nil, 200
	end
	if action ~= "alerts" and action ~= "unban" and action ~= "allowlists" and action ~= "allowlistcheck" then
		return nil, "Unknown CrowdSec operation", 400
	end
	if
		not conf.MANAGEMENT_LOGIN
		or conf.MANAGEMENT_LOGIN == ""
		or not conf.MANAGEMENT_PASSWORD
		or conf.MANAGEMENT_PASSWORD == ""
	then
		return nil, "CrowdSec management credentials are not configured", 403
	end
	if action == "allowlists" or action == "allowlistcheck" then
		local limit, offset = params.limit or 50, params.offset or 0
		if
			not integer(limit)
			or limit > 200
			or type(offset) ~= "number"
			or offset < 0
			or offset ~= math.floor(offset)
		then
			return nil, "Invalid allowlist pagination", 400
		end
		if
			action == "allowlistcheck"
			and (type(params.ip) ~= "string" or params.ip == "" or #params.ip > 64 or params.ip:find("[^%x:.]"))
		then
			return nil, "An IP is required to check allowlists", 400
		end
		local ok, err = login()
		if not ok then
			return nil, err, 502
		end
		local path = action == "allowlistcheck" and "allowlists/check/" .. params.ip or "allowlists?with_content=true"
		local result
		result, err = request("GET", path, nil, true)
		if not result then
			return nil, err, 502
		end
		if action == "allowlistcheck" then
			-- CrowdSec omits both fields for a negative match, returning exactly {}.
			local empty = type(result) == "table" and getmetatable(result) ~= json.array_mt and next(result) == nil
			if not empty and (type(result) ~= "table" or type(result.allowlisted) ~= "boolean") then
				return nil, "CrowdSec returned an invalid allowlist check", 502
			end
			return {
				ip = params.ip,
				allowlisted = result.allowlisted == true,
				reason = text(result.reason, 2048),
				observed_at = ngx.time(),
			},
				nil,
				200
		end
		local items = array(result)
		if not items then
			return nil, "CrowdSec returned invalid allowlists", 502
		end
		local all = list()
		for _, item in ipairs(items) do
			local safe = safe_allowlist(item)
			if not safe then
				return nil, "CrowdSec returned invalid allowlist data", 502
			end
			all[#all + 1] = safe
		end
		table.sort(all, function(a, b)
			return a.name < b.name
		end)
		local page = list()
		for index = offset + 1, math.min(#all, offset + limit) do
			page[#page + 1] = all[index]
		end
		return { allowlists = page, total = #all, offset = offset, limit = limit, observed_at = ngx.time() }, nil, 200
	end
	if action == "alerts" then
		local path
		if params.alert_id ~= nil then
			if not integer(params.alert_id) then
				return nil, "Invalid alert ID", 400
			end
			path = "alerts/" .. string.format("%.0f", params.alert_id)
		else
			if type(params.ip) ~= "string" or params.ip == "" or #params.ip > 64 or params.ip:find("[^%x:.]") then
				return nil, "An IP is required to investigate alerts", 400
			end
			path = "alerts?" .. ngx.encode_args({ ip = params.ip, limit = 50 })
		end
		local ok, err = login()
		if not ok then
			return nil, err, 502
		end
		local result
		result, err = request("GET", path, nil, true)
		if not result then
			return nil, err, 502
		end
		if params.alert_id then
			local alert = safe_alert(result)
			if not alert then
				return nil, "CrowdSec returned an invalid alert", 502
			end
			return { alert = alert, observed_at = ngx.time() }, nil, 200
		end
		local items = array(result)
		if not items then
			return nil, "CrowdSec returned invalid alerts", 502
		end
		local alerts = list()
		for i, item in ipairs(items) do
			if i > 50 then
				break
			end
			local alert = safe_alert(item)
			if not alert then
				return nil, "CrowdSec returned an invalid alert", 502
			end
			alerts[#alerts + 1] = alert
		end
		return { alerts = alerts, limit = 50, observed_at = ngx.time() }, nil, 200
	end
	if
		not integer(params.decision_id)
		or (params.scope ~= "Ip" and params.scope ~= "Range" and params.scope ~= "ip" and params.scope ~= "range")
		or type(params.value) ~= "string"
		or #params.value > 128
		or params.value == ""
		or params.value:find("[%c]")
		or type(params.decision_type) ~= "string"
		or #params.decision_type > 64
	then
		return nil, "A decision ID and its selected IP/range and type are required", 400
	end
	local selected = { scope = params.scope:lower(), value = params.value, contains = "false" }
	local items, err = query(selected)
	if not items then
		return nil, err, 502
	end
	local match
	for _, item in ipairs(items) do
		if item.id == params.decision_id then
			if
				item.scope:lower() ~= params.scope:lower()
				or item.value ~= params.value
				or item.type ~= params.decision_type
			then
				return nil, "The selected CrowdSec decision has changed; refresh before removing it", 409
			end
			match = item
		end
	end
	if not match then
		return nil, "The selected decision is no longer active; refresh the investigation", 409
	end
	local ok
	ok, err = login()
	if not ok then
		return nil, err, 502
	end
	local result
	result, err = request("DELETE", "decisions/" .. string.format("%.0f", params.decision_id), nil, true)
	if not result then
		return nil, err .. "; removal outcome is unknown, refresh before retrying", 502
	end
	if type(result) ~= "table" or (tonumber(result.nbDeleted) ~= 1 and tonumber(result.nbDeleted) ~= 0) then
		return nil, "CrowdSec did not confirm removal; refresh before retrying", 502
	end
	local remaining_filters = { contains = "true" }
	remaining_filters[params.scope:lower() == "ip" and "ip" or "range"] = params.value
	local remaining
	remaining = query(remaining_filters)
	if not remaining then
		return nil, "Removal was submitted but verification failed; refresh the investigation", 502
	end
	for _, item in ipairs(remaining) do
		if item.id == params.decision_id then
			return nil, "CrowdSec still reports the selected decision as active", 502
		end
	end
	return {
		removed = true,
		already_absent = tonumber(result.nbDeleted) == 0,
		decision = match,
		remaining_decisions = remaining,
		observed_at = ngx.time(),
		propagation = {
			status = "pending",
			mode = conf.MODE,
			interval = conf.MODE == "stream" and conf.UPDATE_FREQUENCY or conf.CACHE_EXPIRATION,
		},
	},
		nil,
		200
end

return control
