local ngx = ngx
local ngx_req = ngx.req
local shared = ngx.shared
local bit = require "bit"
local cdatastore = require "bunkerweb.datastore"
local cjson = require "cjson"
local class = require "middleclass"
local clogger = require "bunkerweb.logger"
local helpers = require "bunkerweb.helpers"
local process = require "ngx.process"
local pushswap = require "bunkerweb.pushswap"
local reslock = require "resty.lock"
local rsignal = require "resty.signal"
local upload = require "resty.upload"
local utils = require "bunkerweb.utils"

local api = class("api")

local datastore = cdatastore:new()
local internalstore = cdatastore:new(shared.internalstore)
local logger = clogger:new("API")

local get_country = utils.get_country
local get_variable = utils.get_variable
local is_ip_in_networks = utils.is_ip_in_networks
local is_ipv4 = utils.is_ipv4
local is_ipv6 = utils.is_ipv6

local RESERVED_SERVICE_NAMES = {
	["unknown"] = true,
	["Web UI"] = true,
	["bwcli"] = true,
	["default server"] = true,
	[""] = true,
}
-- local run = shell.run
local NOTICE = ngx.NOTICE
local ERR = ngx.ERR
local HTTP_OK = ngx.HTTP_OK
local HTTP_INTERNAL_SERVER_ERROR = ngx.HTTP_INTERNAL_SERVER_ERROR
local HTTP_BAD_REQUEST = ngx.HTTP_BAD_REQUEST
local HTTP_SERVICE_UNAVAILABLE = ngx.HTTP_SERVICE_UNAVAILABLE
local HTTP_NOT_FOUND = ngx.HTTP_NOT_FOUND
local kill = rsignal.kill
local get_master_pid = process.get_master_pid
local execute = os.execute
local open = io.open
local read_body = ngx_req.read_body
local get_body_data = ngx_req.get_body_data
local get_body_file = ngx_req.get_body_file
local decode = cjson.decode
local encode = cjson.encode
local match = string.match
local require_plugin = helpers.require_plugin
local new_plugin = helpers.new_plugin
local call_plugin = helpers.call_plugin

local function file_exists(path)
	local file = open(path, "r")
	if file then
		file:close()
		return true
	end
	return false
end

local function get_nginx_bin()
	local candidates = { "/usr/sbin/nginx", "/usr/local/sbin/nginx", "/usr/bin/nginx", "/usr/local/bin/nginx" }
	for _, candidate in ipairs(candidates) do
		if file_exists(candidate) then
			return candidate
		end
	end
	return "nginx"
end

local function get_nginx_conf()
	local candidates = { "/etc/nginx/nginx.conf", "/usr/local/etc/nginx/nginx.conf" }
	for _, candidate in ipairs(candidates) do
		if file_exists(candidate) then
			return candidate
		end
	end
	return "/etc/nginx/nginx.conf"
end

api.global = { GET = {}, POST = {}, PUT = {}, DELETE = {} }

-- Constant-time string comparison to mitigate timing attacks
local function secure_compare(a, b)
	if not a or not b then
		return false
	end
	if #a ~= #b then
		return false
	end
	local diff = 0
	for i = 1, #a do
		diff = bit.bor(diff, bit.bxor(a:byte(i), b:byte(i)))
	end
	return diff == 0
end

function api:is_allowed_token()
	-- If no token configured, allow
	if not self.api_token or self.api_token == "" then
		return true, "ok"
	end
	local headers = ngx_req.get_headers(tonumber((get_variable("MAX_HEADERS", false))) or 100)
	local auth = headers["authorization"] or headers["Authorization"]
	local provided = auth and auth:match("^[Bb]earer%s+(.+)$") or nil
	if not provided then
		return false, "missing API token"
	end
	if not secure_compare(provided, self.api_token) then
		return false, "invalid API token"
	end
	return true, "ok"
end

function api:initialize(ctx)
	self.ctx = ctx
	local data, err = get_variable("API_WHITELIST_IP", false)
	self.ips = {}
	self.api_token = nil
	if not data then
		logger:log(ERR, "can't get API_WHITELIST_IP variable : " .. err)
	else
		for ip in data:gmatch("%S+") do
			table.insert(self.ips, ip)
		end
	end

	-- Load optional API token (from internalstore variables, same pattern as whitelist)
	local tok = get_variable("API_TOKEN", false)
	if tok and tok ~= "" then
		self.api_token = tok
	end
end

-- luacheck: ignore 212
function api:log_cmd(cmd, status, stdout, stderr)
	local level = NOTICE
	local prefix = "success"
	if status ~= 0 then
		level = ERR
		prefix = "error"
	end
	logger:log(level, prefix .. " while running command " .. cmd)
	logger:log(level, "stdout = " .. stdout)
	logger:log(level, "stdout = " .. stderr)
end

-- TODO : use this if we switch to OpenResty
function api:cmd(cmd)
	-- Non-blocking command
	-- luacheck: ignore 113
	local ok, stdout, stderr, reason, status = run(cmd, nil, 10000)
	self:log_cmd(cmd, status, stdout, stderr)
	-- Timeout
	if ok == nil then
		return nil, reason
	end
	-- Other cases : exit 0, exit !0 and killed by signal
	return status == 0, reason, status
end

-- luacheck: ignore 212
function api:response(http_status, api_status, msg)
	local resp = {}
	resp["status"] = api_status
	resp["msg"] = msg
	return http_status, resp
end

api.global.GET["^/ping$"] = function(self)
	return self:response(HTTP_OK, "success", "pong")
end

api.global.GET["^/health$"] = function(self)
	-- Loading state must have priority (startup-like behavior)
	local data, err = get_variable("IS_LOADING", false)
	if not data then
		logger:log(ERR, "can't get IS_LOADING variable : " .. err)
		return self:response(HTTP_OK, "success", "loading")
	end
	if data == "yes" then
		return self:response(HTTP_OK, "success", "loading")
	end

	-- Check if reload indicator file exists
	local f = open("/var/tmp/bunkerweb_reloading", "r")
	if f then
		f:close()
		return self:response(HTTP_OK, "success", "reloading")
	end

	return self:response(HTTP_OK, "success", "ok")
end

-- Both the swap and the reload path take one instance-wide lock: "nginx -t" and the master's
-- reconfiguration both re-read the pushed trees, and a rename sequence that is part way through
-- exposes a tree that is neither the old one nor the new one.
--
-- resty.lock over a shared dict, not a lock file: exclusion across workers is what a shared dict
-- gives by construction, and the entry expires on its own if a worker dies holding it. A file
-- lock has to hand-roll both, and a stale-file break cannot be made atomic with the shell.
--
-- A wait spends the caller's budget and only ever bounds the loser, which never performs the
-- work: it answers 503, and the scheduler retries that. So the wait has to stay under the budget,
-- because a caller that runs out instead records a failure and marks the instance down for a swap
-- that is running, and it should sit as close under it as request overhead allows, because the
-- wait is what the retries have to cover. A reload is called with
-- max(RELOAD_MIN_TIMEOUT, 3 * services), five seconds by default, and the retry is three attempts
-- two seconds apart, so a lock held longer than 3 * wait + 4 seconds is a reload that is given up
-- on: thirteen seconds at a wait of three, seven at a wait of one. That retry belongs to the
-- scheduler's caller alone; a reload driven straight through the API client reads the 503 as a
-- failed reload. A push carries the folder budget, which is sized for the archive rather than for
-- a config test, so it can afford to queue longer.
--
-- The expiry is the other way round, and it is the one number here that has to be generous.
-- resty.lock releases by deleting the key without checking who owns it, so a critical section
-- that outlives the expiry releases the lock of whoever took it next, and two swaps run at once.
-- The critical section is renames, one "nginx -t" on the reload path, and on the first push after
-- a container start a copy of whatever overlayfs refuses to rename out of the image layer. No
-- caller measures that, so this is a ceiling and not a derivation: fifteen minutes is past any
-- swap that is still making progress. Overshooting costs availability, and only after a worker
-- was killed holding the lock: pushes and reloads answer 503 until the key expires while the
-- instance keeps serving the configuration it already has.
local SWAP_LOCK_KEY = "pushswap"
local SWAP_LOCK_EXPTIME = 900
local RELOAD_LOCK_WAIT = 3
local PUSH_LOCK_WAIT = 10

local function acquire_swap_lock(seconds)
	local lock, err = reslock:new("worker_lock", { timeout = seconds, exptime = SWAP_LOCK_EXPTIME })
	if not lock then
		logger:log(ERR, "cannot create the swap lock: " .. tostring(err))
		return nil
	end
	local elapsed
	elapsed, err = lock:lock(SWAP_LOCK_KEY)
	if not elapsed then
		logger:log(ERR, "cannot take the swap lock: " .. tostring(err))
		return nil
	end
	return lock
end

-- The body returns the response triple instead of sending it, so the wrapper has one
-- place to release the swap lock whichever way the reload ends.
local function reload_locked(test_arg)
	if test_arg ~= "no" then
		-- Check Nginx configuration
		logger:log(NOTICE, "Checking Nginx configuration")
		local nginx_bin = get_nginx_bin()
		local nginx_conf = get_nginx_conf()
		local command = nginx_bin .. " -t -e /var/log/bunkerweb/error.log -c " .. nginx_conf .. " 2>&1"
		local handle = io.popen(command)
		local result = handle:read("*a")
		handle:close()

		-- Check for success message in output regardless of exit code
		if string.match(result, "configuration file .+ test is successful") then
			logger:log(NOTICE, "Nginx configuration is valid")
		elseif
			string.match(result, "syntax is ok")
			and string.match(result, "Permission denied")
			and (string.match(result, "nginx.pid") or string.match(result, "/var/log/nginx/error.log"))
		then
			logger:log(NOTICE, "Nginx configuration syntax is valid (non-root permission warnings ignored)")
		else
			return HTTP_INTERNAL_SERVER_ERROR, "error", "config check failed: " .. result
		end
	end

	-- Reload Nginx
	logger:log(NOTICE, "Reloading Nginx")
	-- Send HUP signal to master process
	local ok, err = kill(get_master_pid(), "HUP")
	if not ok then
		-- FreeBSD package mode runs nginx master as root; fallback to sudo-managed rc reload.
		if err == "Operation not permitted" then
			local rc = execute("sudo -n /usr/sbin/service bunkerweb reload >/dev/null 2>&1")
			if rc == 0 or rc == true then
				return HTTP_OK, "success", "reload successful"
			end
		end
		return HTTP_INTERNAL_SERVER_ERROR, "error", "err = " .. err
	end

	-- Create temporary file to indicate reconfiguration
	local file, err = open("/var/tmp/bunkerweb_reloading", "w")
	if file then
		file:write(tostring(os.time()))
		file:close()
	else
		logger:log(ERR, "Failed to create reload indicator file: " .. err)
	end

	return HTTP_OK, "success", "reload successful"
end

api.global.POST["^/reload"] = function(self)
	-- Get test argument
	local args = ngx.req.get_uri_args()
	local test_arg = args.test or "yes"

	local lock = acquire_swap_lock(RELOAD_LOCK_WAIT)
	if not lock then
		return self:response(HTTP_SERVICE_UNAVAILABLE, "error", "a push swap is in progress")
	end
	-- pcall so an error inside the section still releases the lock: leaving it held costs every
	-- later push and reload until it expires.
	local ran, status, level, message = pcall(reload_locked, test_arg)
	lock:unlock()
	if not ran then
		return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", "reload failed: " .. tostring(status))
	end
	return self:response(status, level, message)
end

api.global.POST["^/stop$"] = function(self)
	-- Send QUIT signal to master process
	local ok, err = kill(get_master_pid(), "QUIT")
	if not ok then
		return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", "err = " .. err)
	end
	return self:response(HTTP_OK, "success", "stop successful")
end

api.global.POST["^/confs$"] = function(self)
	-- Everything this request owns on disk carries the worker and the connection. A name built
	-- from the URI alone is shared by every push to that URI, and two of them then write into one
	-- file: the scheduler retries a push while the first attempt may still be uploading, and a
	-- second scheduler or the UI reaches the same instance on its own.
	local request_id = tostring(ngx.worker.pid()) .. "." .. tostring(ngx.var.connection)
	local tmp = "/var/tmp/bunkerweb/api_" .. self.ctx.bw.uri:sub(2) .. "." .. request_id .. ".tar.gz"
	local destination = "/usr/share/bunkerweb/" .. self.ctx.bw.uri:sub(2)
	if self.ctx.bw.uri == "/confs" then
		destination = "/etc/nginx"
	elseif self.ctx.bw.uri == "/data" then
		destination = "/data"
	elseif self.ctx.bw.uri == "/cache" then
		destination = "/var/cache/bunkerweb"
	elseif self.ctx.bw.uri == "/custom_configs" then
		destination = "/etc/bunkerweb/configs"
	elseif self.ctx.bw.uri == "/plugins" then
		destination = "/etc/bunkerweb/plugins"
	elseif self.ctx.bw.uri == "/pro_plugins" then
		destination = "/etc/bunkerweb/pro/plugins"
	end
	local form, err = upload:new(4096)
	if not form then
		return self:response(HTTP_BAD_REQUEST, "error", err)
	end
	form:set_timeout(1000)
	local file, err = open(tmp, "w+")
	if not file then
		return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", err)
	end
	while true do
		-- luacheck: ignore 421
		local typ, res, err = form:read()
		if not typ then
			-- A body that stops mid-upload leaves a partial archive under a name only this
			-- request uses, so nothing later truncates it: it has to go now or every aborted
			-- push adds one file to the directory Nginx also writes its client bodies into.
			file:close()
			os.remove(tmp)
			return self:response(HTTP_BAD_REQUEST, "error", err)
		end
		if typ == "eof" then
			break
		end
		if typ == "body" then
			file:write(res)
		end
	end
	file:flush()
	file:close()
	-- An unchanged push is the common case: the scheduler sends these directories on
	-- every start whether or not their content changed. Skipping it means a live
	-- worker never loses its plugin tree for a push that would change nothing.
	local digest = pushswap.digest_file(tmp)
	if digest and pushswap.read_applied(destination) == digest then
		os.remove(tmp)
		return self:response(HTTP_OK, "success", "already applied at " .. destination)
	end

	-- Extract into a staging area inside the destination first: it validates the
	-- archive before anything is touched, and keeps every later rename on the same
	-- filesystem even when the destination is a mount point.
	--
	-- The name carries the worker and the connection because the scheduler pushes several
	-- folders to one instance at the same time, and a shared staging path means one push
	-- extracts into, and deletes, another one's tree. The reserved prefix keeps it out of the
	-- stale-entry sweep. Connection numbers do not repeat, so a directory left behind by a
	-- worker that died mid-push is never reused: the swap clears it on the normal failure paths,
	-- and where the archived source is the destination the archive does carry it back, but the
	-- swap skips reserved names on the way in so it is never placed again. A killed worker still
	-- leaks one directory.
	local staging = destination .. "/" .. pushswap.RESERVED_PREFIX .. "staging." .. request_id
	local extract = "rm -rf '"
		.. staging
		.. "' && mkdir -p '"
		.. staging
		.. "' && tar xzf '"
		.. tmp
		.. "' -C '"
		.. staging
		.. "'"
	if execute(extract) ~= 0 then
		execute("rm -rf '" .. staging .. "'")
		os.remove(tmp)
		return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", "cannot extract archive")
	end

	-- Extraction only added this request's own staging directory, which nothing else reads or
	-- writes. The destructive part starts here, so this is where the lock has to be held.
	local lock = acquire_swap_lock(PUSH_LOCK_WAIT)
	if not lock then
		execute("rm -rf '" .. staging .. "'")
		os.remove(tmp)
		return self:response(HTTP_SERVICE_UNAVAILABLE, "error", "another push swap is in progress")
	end

	-- pcall so an error inside the section still releases the lock: leaving it held costs every
	-- later push and reload until it expires.
	local ran, ok, err = pcall(pushswap.swap, destination, staging)
	if ran and ok and digest then
		local written, write_err = pushswap.write_applied(destination, digest)
		if not written then
			-- Only costs a redundant push next loop, but it is invisible otherwise.
			logger:log(ERR, "cannot record the applied digest for " .. destination .. ": " .. tostring(write_err))
		end
	end
	lock:unlock()
	os.remove(tmp)
	if not ran then
		return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", "swap failed: " .. tostring(ok))
	end
	if not ok then
		return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", err)
	end

	return self:response(HTTP_OK, "success", "saved data at " .. destination)
end

api.global.POST["^/data$"] = api.global.POST["^/confs$"]

api.global.POST["^/cache$"] = api.global.POST["^/confs$"]

api.global.POST["^/custom_configs$"] = api.global.POST["^/confs$"]

api.global.POST["^/plugins$"] = api.global.POST["^/confs$"]

api.global.POST["^/pro_plugins$"] = api.global.POST["^/confs$"]

api.global.POST["^/unban$"] = function(self)
	read_body()
	local data = get_body_data()
	if not data then
		local data_file = get_body_file()
		if data_file then
			local file, err = open(data_file)
			if not file then
				return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", err)
			end
			data = file:read("*a")
			file:close()
		end
	end
	local ok, ip = pcall(decode, data)
	if not ok then
		return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", "can't decode JSON : " .. ip)
	end

	-- Validate IP address
	if not ip["ip"] or (not is_ipv4(ip["ip"]) and not is_ipv6(ip["ip"])) then
		return self:response(HTTP_BAD_REQUEST, "error", "invalid IP address")
	end

	local ban_scope = ip["ban_scope"] or "global"
	local service = ip["service"]
	local response_msg = "ip " .. ip["ip"] .. " unbanned"

	-- Validate ban scope
	if ban_scope ~= "global" and ban_scope ~= "service" then
		logger:log(ERR, "Invalid ban scope: " .. ban_scope .. ", defaulting to global")
		ban_scope = "global"
	end

	-- For service-specific unbans, validate the service
	if ban_scope == "service" then
		if not service or RESERVED_SERVICE_NAMES[service] then
			logger:log(ERR, "Invalid service name for service-specific unban, defaulting to global unban")
			ban_scope = "global"
			service = nil
		else
			response_msg = response_msg .. " for service " .. service
		end
	end

	-- Use utils.remove_ban to remove the ban(s)
	local ok, err = utils.remove_ban(ip["ip"], service, ban_scope)
	if not ok then
		return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", "failed to remove ban: " .. err)
	end

	return self:response(HTTP_OK, "success", response_msg)
end

api.global.POST["^/ban$"] = function(self)
	read_body()
	local data = get_body_data()
	if not data then
		local data_file = get_body_file()
		if data_file then
			local file, err = open(data_file)
			if not file then
				return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", err)
			end
			data = file:read("*a")
			file:close()
		end
	end
	local ok, ip = pcall(decode, data)
	if not ok then
		return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", "can't decode JSON : " .. ip)
	end
	local ban = {
		ip = "",
		exp = 86400,
		reason = "manual",
		service = "unknown",
		country = "local",
		ban_scope = "global", -- Default to global for consistency
	}

	-- Copy values from request
	ban.ip = ip["ip"]
	if ip["exp"] then
		ban.exp = ip["exp"]
	end
	if ip["reason"] then
		ban.reason = ip["reason"]
	end
	if ip["service"] then
		ban.service = ip["service"]
	end
	if ip["ban_scope"] then
		ban.ban_scope = ip["ban_scope"]
	end

	-- Validate IP address
	if not ban.ip or (not is_ipv4(ban.ip) and not is_ipv6(ban.ip)) then
		return self:response(HTTP_BAD_REQUEST, "error", "invalid IP address")
	end

	-- Validate expiration
	if ban.exp and (type(ban.exp) ~= "number" or ban.exp < 0) then
		return self:response(HTTP_BAD_REQUEST, "error", "exp must be a non-negative number")
	end

	-- Validate ban scope
	if ban.ban_scope ~= "global" and ban.ban_scope ~= "service" then
		logger:log(ERR, "Invalid ban scope: " .. ban.ban_scope .. ", defaulting to global")
		ban.ban_scope = "global"
	end

	-- Validate service name for service-specific bans
	if ban.ban_scope == "service" then
		if RESERVED_SERVICE_NAMES[ban.service] then
			logger:log(ERR, "Invalid service name: " .. ban.service .. ", defaulting to global ban")
			ban.ban_scope = "global"
			ban.service = "unknown"
		end
	end

	local country, err = get_country(ban["ip"])
	if not country then
		country = "unknown"
		logger:log(ERR, "can't get country code " .. err)
	end
	ban.country = country

	-- Use utils.add_ban to ensure ban is applied to datastore and Redis
	local ok, err = utils.add_ban(ban.ip, ban.reason, ban.exp, ban.service, ban.country, ban.ban_scope)
	if not ok then
		return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", "failed to add ban: " .. err)
	end

	-- Create a more informative response message
	local scope_text = ban.ban_scope == "global" and "globally" or ("for service " .. ban.service)
	local duration_text = not ban["exp"] and "permanently" or ("for " .. ban["exp"] .. " seconds")
	return self:response(HTTP_OK, "success", "ip " .. ip["ip"] .. " banned " .. scope_text .. " " .. duration_text)
end

api.global.GET["^/bans$"] = function(self)
	local data = {}
	-- Get system-wide bans
	for _, k in ipairs(datastore:keys()) do
		if k:find("^bans_ip_") then
			local result, err = datastore:get(k)
			if err then
				return self:response(
					HTTP_INTERNAL_SERVER_ERROR,
					"error",
					"can't access " .. k .. " from datastore : " .. result
				)
			end
			local ok, ttl = datastore:ttl(k)
			if not ok then
				return self:response(
					HTTP_INTERNAL_SERVER_ERROR,
					"error",
					"can't access ttl " .. k .. " from datastore : " .. ttl
				)
			end
			local ban_data
			ok, ban_data = pcall(decode, result)
			if not ok then
				ban_data = { reason = result, service = "unknown", date = 0, ban_scope = "global" }
			end

			-- Check for permanent ban flag and override TTL if set
			if ban_data["permanent"] then
				ttl = 0
			end

			table.insert(data, {
				ip = k:sub(9, #k),
				reason = ban_data["reason"],
				service = ban_data["service"],
				date = ban_data["date"],
				country = ban_data["country"],
				ban_scope = ban_data["ban_scope"] or "global",
				exp = math.floor(ttl),
				permanent = ban_data["permanent"] or false,
			})
		elseif k:find("^bans_service_") then
			-- Service-specific ban (format: bans_service_<servicename>_ip_<ipaddress>)
			local result, err = datastore:get(k)
			if err then
				return self:response(
					HTTP_INTERNAL_SERVER_ERROR,
					"error",
					"can't access " .. k .. " from datastore : " .. result
				)
			end
			local ok, ttl = datastore:ttl(k)
			if not ok then
				return self:response(
					HTTP_INTERNAL_SERVER_ERROR,
					"error",
					"can't access ttl " .. k .. " from datastore : " .. ttl
				)
			end

			-- Extract service and IP from the key
			local service, ip = k:match("^bans_service_(.-)_ip_(.+)$")
			if service and ip then
				local ban_data
				ok, ban_data = pcall(decode, result)
				if not ok then
					ban_data = { reason = result, service = service, date = 0, ban_scope = "service" }
				end

				-- Check for permanent ban flag and override TTL if set
				if ban_data["permanent"] then
					ttl = 0
				end

				table.insert(data, {
					ip = ip,
					reason = ban_data["reason"],
					service = service,
					date = ban_data["date"],
					country = ban_data["country"],
					ban_scope = "service",
					exp = math.floor(ttl),
					permanent = ban_data["permanent"] or false,
				})
			end
		end
	end
	return self:response(HTTP_OK, "success", data)
end

api.global.GET["^/variables$"] = function(self)
	local variables, err = internalstore:get("variables", true)
	if not variables then
		return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", "can't access variables from internalstore : " .. err)
	end
	return self:response(HTTP_OK, "success", variables)
end

function api:is_allowed_ip()
	if is_ip_in_networks(self.ctx.bw.remote_addr, self.ips) then
		return true, "ok"
	end
	return false, "IP is not in API_WHITELIST_IP"
end

function api:do_api_call()
	if self.global[self.ctx.bw.request_method] ~= nil then
		for uri, api_fun in pairs(self.global[self.ctx.bw.request_method]) do
			if match(self.ctx.bw.uri, uri) then
				local status, resp = api_fun(self)
				local ret = true
				if status ~= HTTP_OK then
					ret = false
				end
				if #resp["msg"] == 0 then
					resp["msg"] = ""
				elseif type(resp["msg"]) == "table" then
					resp["data"] = resp["msg"]
					resp["msg"] = resp["status"]
				end
				return ret, resp["msg"], status, encode(resp)
			end
		end
	end
	local list, err = internalstore:get("plugins", true)
	if not list then
		local _, resp = self:response(HTTP_INTERNAL_SERVER_ERROR, "error", "can't list loaded plugins : " .. err)
		return false, resp["msg"], HTTP_INTERNAL_SERVER_ERROR, encode(resp)
	end
	for _, plugin in ipairs(list) do
		local plugin_lua, _ = require_plugin(plugin.id)
		if plugin_lua and plugin_lua.api ~= nil then
			local ok, plugin_obj = new_plugin(plugin_lua, self.ctx)
			if not ok then
				logger:log(ERR, "can't instantiate " .. plugin.id .. " : " .. plugin_obj)
			else
				local ret
				ok, ret = call_plugin(plugin_obj, "api")
				if not ok then
					logger:log(ERR, "error while executing " .. plugin.id .. ":api() : " .. ret)
				else
					if ret.ret then
						local resp = {}
						if ret.status == HTTP_OK then
							resp["status"] = "success"
						else
							resp["status"] = "error"
						end
						resp["msg"] = ret.msg
						return ret.status == HTTP_OK, resp["status"], ret.status, encode(resp)
					end
				end
			end
		end
	end
	local resp = {}
	resp["status"] = "error"
	resp["msg"] = "not found"
	return false, "error", HTTP_NOT_FOUND, encode(resp)
end

return api
