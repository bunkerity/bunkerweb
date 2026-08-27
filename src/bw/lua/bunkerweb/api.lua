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
local HTTP_NOT_FOUND = ngx.HTTP_NOT_FOUND
-- Literal: lua-nginx-module has no ngx.HTTP_PRECONDITION_FAILED constant.
local HTTP_PRECONDITION_FAILED = 412
local HTTP_SERVICE_UNAVAILABLE = ngx.HTTP_SERVICE_UNAVAILABLE
-- Held while POST /confs replaces a destination tree, waited on by POST /reload : the swap is a
-- `rm -rf dest/* && cp -R staging/. dest/`, so a reload landing in the middle of it makes NGINX
-- read a half-written tree.
local SWAP_LOCK_KEY = "api_swap_in_progress"
local SWAP_LOCK_TTL = 120
local SWAP_WAIT_TIMEOUT = 30
-- How long POST /reload waits for proof that NGINX adopted the new cycle before it stops
-- believing the signal and asks `nginx -t` instead. A refusal is immediate (the [emerg] is
-- logged in the same second as the SIGHUP), so this only ever expires on a slow success.
local RELOAD_CONFIRM_TIMEOUT = 2
local kill = rsignal.kill
local get_master_pid = process.get_master_pid
local execute = os.execute
local open = io.open
local remove = os.remove
-- Set by the entrypoint when a restart kept its configuration: the instance serves and enforces
-- normally but still owes the scheduler a fresh push. Cleared by POST /confs.
local NEEDS_CONFIG_PATH = "/var/tmp/bunkerweb_needs_config"
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

-- Run `nginx -t` and report whether the configuration on disk is loadable, plus its raw output.
local function test_nginx_conf()
	local command = get_nginx_bin() .. " -t -e /var/log/bunkerweb/error.log -c " .. get_nginx_conf() .. " 2>&1"
	local handle = io.popen(command)
	local result = handle:read("*a")
	handle:close()

	-- Check for success message in output regardless of exit code
	if string.match(result, "configuration file .+ test is successful") then
		return true, result
	end
	if
		string.match(result, "syntax is ok")
		and string.match(result, "Permission denied")
		and (string.match(result, "nginx.pid") or string.match(result, "/var/log/nginx/error.log"))
	then
		logger:log(NOTICE, "Nginx configuration syntax is valid (non-root permission warnings ignored)")
		return true, result
	end
	return false, result
end

-- Decide whether the reload we just signalled actually happened.
--
-- A SIGHUP that lands is not a reload that took : NGINX parses the new configuration in the
-- master AFTER the signal, and when it refuses it logs [emerg] and keeps serving the old cycle.
-- The signal still succeeded, which is why a refused reload used to answer 200 "reload
-- successful" -- and why DISABLE_CONFIGURATION_TESTING masked it outright: the pre-test was the
-- only thing on this path that ever produced a verdict, so skipping it left nothing to fail.
--
-- Cheap signal first : a master that accepted the new cycle forks fresh workers and immediately
-- tells the old ones -- us, this request is served by one -- to shut down, so
-- ngx.worker.exiting() flips within milliseconds. The wait expiring is NOT proof of failure: a
-- refusal is immediate while a success can be slow, because init_by_lua rebuilds the whole
-- BunkerWeb runtime in the master on a large configuration. So an unconfirmed reload falls back
-- to `nginx -t`, which answers for real, and which only runs on the path that needed it.
local function confirm_reload()
	local deadline = ngx.now() + RELOAD_CONFIRM_TIMEOUT
	while not ngx.worker.exiting() do
		if ngx.now() >= deadline then
			local ok, output = test_nginx_conf()
			if not ok then
				return false, output
			end
			return true, "unconfirmed after " .. RELOAD_CONFIRM_TIMEOUT .. "s but the configuration tests clean"
		end
		ngx.sleep(0.05)
	end
	return true, "workers rotated"
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

	-- A restart that kept its configuration is serving it, and still enforcing every plugin --
	-- `is_loading` is what gates those, and it is deliberately not set here. It does still want a
	-- fresh configuration from the scheduler, which is what this state asks for. Reported after
	-- `reloading` so a push already landing does not earn a second one.
	f = open(NEEDS_CONFIG_PATH, "r")
	if f then
		f:close()
		return self:response(HTTP_OK, "success", "needs_config")
	end

	return self:response(HTTP_OK, "success", "ok")
end

api.global.POST["^/reload"] = function(self)
	-- Never reload on top of a half-replaced configuration. A push writes the tree file by file,
	-- so a reload that overlaps it either fails its own `nginx -t` or, worse, succeeds and runs
	-- init_by_lua against a truncated variables.env : the plugins then keep whatever rules they
	-- could build from that partial read until something reloads them again, which is how a
	-- service kept serving traffic with its rate limit silently absent. Waiting is deliberate --
	-- answering 503 instead would make the caller treat the push as failed and roll it back.
	local swap_deadline = ngx.now() + SWAP_WAIT_TIMEOUT
	while internalstore:get(SWAP_LOCK_KEY) do
		if ngx.now() >= swap_deadline then
			logger:log(
				ERR,
				"a configuration swap is still in progress after " .. SWAP_WAIT_TIMEOUT .. "s, refusing to reload"
			)
			return self:response(HTTP_SERVICE_UNAVAILABLE, "error", "a configuration swap is still in progress")
		end
		ngx.sleep(0.1)
	end

	-- Get test argument
	local args = ngx.req.get_uri_args()
	local test_arg = args.test or "yes"

	if test_arg ~= "no" then
		-- Check Nginx configuration
		logger:log(NOTICE, "Checking Nginx configuration")
		local ok, result = test_nginx_conf()
		if not ok then
			return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", "config check failed: " .. result)
		end
		logger:log(NOTICE, "Nginx configuration is valid")
	end

	-- Reload Nginx
	logger:log(NOTICE, "Reloading Nginx")
	-- Send HUP signal to master process
	local ok, err = kill(get_master_pid(), "HUP")
	if not ok then
		-- FreeBSD package mode runs nginx master as root; fallback to sudo-managed rc reload.
		local rc
		if err == "Operation not permitted" then
			rc = execute("sudo -n /usr/sbin/service bunkerweb reload >/dev/null 2>&1")
		end
		if rc ~= 0 and rc ~= true then
			return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", "err = " .. err)
		end
	end

	-- The signal landing says nothing about the reload succeeding : see confirm_reload().
	local reloaded, detail = confirm_reload()
	if not reloaded then
		logger:log(ERR, "Nginx refused the reload and is still serving the previous configuration : " .. detail)
		return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", "reload refused by nginx: " .. detail)
	end
	logger:log(NOTICE, "Nginx reloaded (" .. detail .. ")")

	-- Create temporary file to indicate reconfiguration
	local file, err = open("/var/tmp/bunkerweb_reloading", "w")
	if file then
		file:write(tostring(os.time()))
		file:close()
	else
		logger:log(ERR, "Failed to create reload indicator file: " .. err)
	end

	return self:response(HTTP_OK, "success", "reload successful")
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
	local tmp = "/var/tmp/bunkerweb/api_" .. self.ctx.bw.uri:sub(2) .. ".tar.gz"
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
			file:close()
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
	-- Staging lives INSIDE the destination, and that is load-bearing rather than tidy : every entry
	-- leaves it via rename(2), and rename(2) across filesystems fails with EXDEV. /var/tmp and the
	-- destination are routinely different mounts, so staging outside would send every single rename
	-- down the copy fallback -- the swap would stop being atomic while looking exactly the same.
	-- Do NOT "align" this with the /var/tmp convention used elsewhere in this file.
	local staging = destination .. "/" .. pushswap.RESERVED_PREFIX .. "staging"
	-- The backup is a copy, never a rename, so it has no such constraint and stays out of the tree.
	local backup = "/var/tmp/bunkerweb/backup_" .. self.ctx.bw.uri:sub(2)

	-- Hold the swap lock across everything destructive -- backup, extract, swap AND any restore.
	-- The upload above never touches the destination. Releasing between a failed swap and the
	-- restore would open a reload window onto a half-undone tree. The TTL is the backstop for a
	-- worker that dies mid-swap : without it a lost unlock would block every reload for good.
	internalstore:set(SWAP_LOCK_KEY, tostring(ngx.now()), SWAP_LOCK_TTL)

	local function fail(message)
		execute("rm -rf " .. staging .. " " .. backup)
		remove(tmp)
		internalstore:delete(SWAP_LOCK_KEY)
		return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", message)
	end

	-- Backup BEFORE extracting : staging now lives inside the destination, so backing up after it
	-- exists would copy the incoming tree into the backup as well -- doubling the copy and making
	-- the "pre-swap state" contain the post-swap payload.
	--
	-- The backup is the only complete pre-swap tree, and after an incomplete rollback it is the
	-- only recovery there is, so a push that cannot establish its recovery point must not proceed
	-- to the destructive part. Refusing to start beats failing halfway through a config swap.
	-- (dev suppresses both the reason and the failure here with `2>/dev/null; true`.)
	if execute("rm -rf " .. backup .. " && mkdir -p " .. backup .. " && cp -R " .. destination .. "/. " .. backup .. "/") ~= 0 then
		return fail("cannot create the pre-swap backup, refusing to push")
	end

	-- Extract next : it validates the archive before any consumer-visible entry is touched.
	if execute("rm -rf " .. staging .. " && mkdir -p " .. staging .. " && tar xzf " .. tmp .. " -C " .. staging) ~= 0 then
		return fail("cannot extract archive")
	end

	local swapped, swap_err, rollback_incomplete = pushswap.swap(destination, staging)
	if not swapped then
		if not rollback_incomplete then
			-- The ordered undo put the tree back to its pre-swap state. Restoring on top of that
			-- could only make it worse, so the backup goes unused.
			return fail("cannot swap configuration : " .. tostring(swap_err))
		end
		-- Last resort. Clear before replacing : the restore is a `cp -R`, which merges into an
		-- existing directory rather than replacing it, and the destination is now a mix of old and
		-- new entries. Merging over that would leave a directory holding the new files PLUS every
		-- old file the new version deleted -- worse than either state alone.
		-- pushswap.clear() deletes the non-reserved entries by name; it is used instead of
		-- `rm -rf <destination>/*` so that keeping the parked originals in .bw-trash does not
		-- depend on the unstated fact that a shell glob skips dotfiles.
		local cleared, clear_err = pushswap.clear(destination)
		local restored = cleared and execute("cp -R " .. backup .. "/. " .. destination .. "/") == 0
		if not restored then
			logger:log(
				ERR,
				"restore from backup FAILED after an incomplete rollback at "
					.. destination
					.. " : "
					.. tostring(clear_err or "copy failed")
					.. " -- originals are parked in "
					.. destination
					.. "/"
					.. pushswap.RESERVED_PREFIX
					.. "trash"
			)
			return fail("swap failed and the restore failed too : " .. tostring(swap_err))
		end
		logger:log(ERR, "swap rolled back incompletely at " .. destination .. ", restored from backup : " .. tostring(swap_err))
		return fail("cannot swap configuration, restored from backup : " .. tostring(swap_err))
	end

	execute("rm -rf " .. backup)
	remove(tmp)
	internalstore:delete(SWAP_LOCK_KEY)

	-- The configuration tree itself has landed, so a restart that was waiting for one is served.
	-- Only /confs clears it: /cache, /data, /plugins and friends reuse this handler but carry
	-- something else, and clearing on those would stop the scheduler re-pushing the configuration
	-- this instance is actually missing.
	if self.ctx.bw.uri == "/confs" then
		-- Check the result: nginx can only unlink this if it owns it, and /var/tmp is sticky. A
		-- silent failure here means the instance keeps asking for a configuration it already has,
		-- and the scheduler keeps pushing the whole fleet, forever.
		local ok, err = remove(NEEDS_CONFIG_PATH)
		if not ok and err and not err:find("No such file") then
			logger:log(ERR, "can't remove " .. NEEDS_CONFIG_PATH .. " : " .. err)
		end
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
	local not_after
	if self.ctx.bw.remote_addr == "unix:" and ip["not_after"] ~= nil then
		not_after = ip["not_after"]
		if type(not_after) ~= "number" or not_after <= 0 or not_after ~= not_after or not_after == math.huge then
			return self:response(HTTP_BAD_REQUEST, "error", "not_after must be a finite positive number")
		end
	end
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
	local ok, err = utils.remove_ban(ip["ip"], service, ban_scope, not_after)
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
	local not_after
	if self.ctx.bw.remote_addr == "unix:" and ip["not_after"] ~= nil then
		not_after = ip["not_after"]
		if type(not_after) ~= "number" or not_after <= 0 or not_after ~= not_after or not_after == math.huge then
			return self:response(HTTP_BAD_REQUEST, "error", "not_after must be a finite positive number")
		end
	end
	local ban = {
		ip = "",
		exp = 86400,
		reason = "manual",
		service = "unknown",
		country = "local",
		ban_scope = "global", -- Default to global for consistency
		reason_data = {},
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
	if type(ip["reason_data"]) == "table" then
		ban.reason_data = ip["reason_data"]
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
		if not ban.service or RESERVED_SERVICE_NAMES[ban.service] then
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
	local ok, err =
		utils.add_ban(ban.ip, ban.reason, ban.exp, ban.service, ban.country, ban.ban_scope, ban.reason_data, not_after)
	if not ok then
		return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", "failed to add ban: " .. err)
	end

	-- Create a more informative response message
	local scope_text = ban.ban_scope == "global" and "globally" or ("for service " .. ban.service)
	local duration_text = not ban["exp"] and "permanently" or ("for " .. ban["exp"] .. " seconds")
	return self:response(HTTP_OK, "success", "ip " .. ip["ip"] .. " banned " .. scope_text .. " " .. duration_text)
end

api.global.GET["^/bans$"] = function(self)
	local status, response = utils.with_ban_snapshot_lock(function()
		local snapshot_time = os.time()
		-- Every coherent read receives a new epoch. This also orders snapshots
		-- whose local Redis cache changed through expiry or lazy refresh.
		local generation_epoch, epoch_err = utils.next_ban_snapshot_epoch()
		if generation_epoch == nil then
			return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", epoch_err)
		end

		local data = {}
		for _, key in ipairs(datastore:keys()) do
			local service, ip = key:match("^bans_service_(.-)_ip_(.+)$")
			local scope = service and "service" or "global"
			ip = ip or key:match("^bans_ip_(.+)$")
			if ip then
				local result, err = datastore:get(key)
				if result then
					local ttl_ok, ttl = datastore:ttl(key)
					if not ttl_ok then
						return self:response(
							HTTP_INTERNAL_SERVER_ERROR,
							"error",
							"can't access ttl " .. key .. " : " .. ttl
						)
					end
					local decoded, ban_data = pcall(decode, result)
					if not decoded or type(ban_data) ~= "table" then
						ban_data = { reason = result, service = service or "unknown", date = 0 }
					end

					local permanent = ban_data.permanent == true
					local expires_at = 0
					if not permanent then
						expires_at = tonumber(ban_data.expires_at) or (snapshot_time + math.floor(ttl))
					end
					if permanent or (ttl > 0 and expires_at > snapshot_time) then
						table.insert(data, {
							ip = ip,
							reason = ban_data.reason,
							service = service or ban_data.service,
							date = ban_data.date,
							country = ban_data.country,
							ban_scope = scope,
							exp = permanent and 0 or math.max(math.floor(expires_at - snapshot_time), 0),
							expires_at = expires_at,
							permanent = permanent,
							reason_data = type(ban_data.reason_data) == "table" and ban_data.reason_data or {},
						})
					end
				elseif err ~= "not found" then
					return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", "can't access " .. key .. " : " .. err)
				end
			end
		end
		-- Optional ?start=&length= window, modelled on /metrics/requests/query. Without it the
		-- whole set is returned, which is the pre-1.7 contract (~16 MB of JSON at 100k bans).
		-- ponytail: this bounds the RESPONSE, not the work — datastore:keys() above still
		-- materializes every key in the dict and does a get+ttl per ban, blocking, on every call.
		-- Raising that ceiling means indexing bans outside the shared dict.
		local total = #data
		local args = ngx_req.get_uri_args and ngx_req.get_uri_args() or {}
		local length = tonumber(args.length)
		if length and length >= 0 then
			local start_idx = tonumber(args.start) or 0
			if start_idx < 0 then
				start_idx = 0
			end
			-- dict key order is not stable between calls, so page over a deterministic order or a
			-- client walking the pages would see the same ban twice and miss another.
			table.sort(data, function(a, b)
				if a.ip ~= b.ip then
					return a.ip < b.ip
				end
				if a.ban_scope ~= b.ban_scope then
					return a.ban_scope < b.ban_scope
				end
				return tostring(a.service) < tostring(b.service)
			end)
			local page = {}
			for index = start_idx + 1, math.min(start_idx + length, total) do
				table.insert(page, data[index])
			end
			data = page
		end

		local snapshot_status, snapshot_response = self:response(HTTP_OK, "success", data)
		snapshot_response.generation_epoch = generation_epoch
		snapshot_response.snapshot_time = snapshot_time
		snapshot_response.total = total
		return snapshot_status, snapshot_response
	end)
	if not status then
		return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", response)
	end
	return status, response
end

api.global.GET["^/variables$"] = function(self)
	local variables, err = internalstore:get("variables", true)
	if not variables then
		return self:response(HTTP_INTERNAL_SERVER_ERROR, "error", "can't access variables from internalstore : " .. err)
	end
	return self:response(HTTP_OK, "success", variables)
end

-- Web cache (proxy_cache) management -----------------------------------------
-- Shared on-disk cache zone for the reverseproxy plugin (keys_zone=proxycache).
local PROXY_CACHE_DIR = "/var/tmp/bunkerweb/proxy_cache"
local MAX_PROXY_CACHE_PURGE_URLS = 100
local MAX_PROXY_CACHE_URL_LENGTH = 8192
local MAX_PROXY_CACHE_KEY_TEMPLATE_LENGTH = 4096
local MAX_PROXY_CACHE_KEY_LENGTH = 16384

-- Rebuild the nginx proxy_cache key string for a URL by expanding the
-- URL-derivable nginx variables of PROXY_CACHE_KEY (default $scheme$host$request_uri).
-- Non-URL-derivable variables ($cookie_*, $http_*, ...) cannot be reproduced
-- from a URL alone, so we error out rather than purge the wrong entry.
local function reconstruct_cache_key(url, key_template)
	key_template = key_template or "$scheme$host$request_uri"
	if type(key_template) ~= "string" or #key_template == 0 then
		return nil, "invalid PROXY_CACHE_KEY template"
	end
	if #key_template > MAX_PROXY_CACHE_KEY_TEMPLATE_LENGTH then
		return nil, "PROXY_CACHE_KEY template is too long"
	end

	local scheme, authority, uri = url:match("^([Hh][Tt][Tt][Pp][Ss]?)://([^/?#]+)(.*)$")
	if not scheme then
		return nil, "invalid url: " .. tostring(url)
	end
	scheme = scheme:lower()
	authority = authority:lower()
	if authority:find("@", 1, true) or uri:find("#", 1, true) then
		return nil, "invalid url: credentials and fragments are not supported"
	end
	if uri == "" then
		uri = "/"
	elseif uri:sub(1, 1) == "?" then
		uri = "/" .. uri
	elseif uri:sub(1, 1) ~= "/" then
		return nil, "invalid url: " .. tostring(url)
	end

	local host, port = authority, nil
	if authority:sub(1, 1) == "[" then
		local bracket = authority:find("]", 2, true)
		if not bracket then
			return nil, "invalid url authority: " .. authority
		end
		host = authority:sub(1, bracket)
		local suffix = authority:sub(bracket + 1)
		if suffix ~= "" then
			port = suffix:match("^:(%d+)$")
			if not port then
				return nil, "invalid url port"
			end
		end
	else
		local name, parsed_port = authority:match("^(.-):(%d+)$")
		if name then
			host, port = name, parsed_port
		elseif authority:find(":", 1, true) then
			return nil, "invalid url authority: " .. authority
		end
	end
	if host == "" or (port and (tonumber(port) < 1 or tonumber(port) > 65535)) then
		return nil, "invalid url authority: " .. authority
	end

	local path = uri:match("^([^?]*)") or uri
	local args = uri:match("%?(.*)$") or ""
	local subst = {
		["$scheme"] = scheme,
		["$host"] = host,
		["$http_host"] = authority,
		["$request_uri"] = uri,
		["$uri"] = path,
		["$args"] = args,
		["$query_string"] = args,
	}
	local unknown
	local function substitute(open_brace, name, close_brace)
		local var = "$" .. open_brace .. name .. close_brace
		if (open_brace == "{") ~= (close_brace == "}") then
			unknown = var
			return var
		end
		local value = subst["$" .. name]
		if value == nil then
			unknown = var
			return var
		end
		return value
	end
	local key = key_template:gsub("%$({?)([%w_]+)(}?)", substitute)
	if unknown then
		return nil, "PROXY_CACHE_KEY uses non-URL-derivable variable " .. unknown
	end
	if #key > MAX_PROXY_CACHE_KEY_LENGTH then
		return nil, "reconstructed cache key is too long"
	end
	return key
end

api.global.POST["^/proxy%-cache/purge$"] = function(self)
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
	local ok, body = pcall(decode, data)
	if not ok or type(body) ~= "table" then
		return self:response(HTTP_BAD_REQUEST, "error", "can't decode JSON body")
	end

	local scope = body.scope or "url"

	-- Purge everything through ngx_cache_purge. This keeps the on-disk cache and
	-- the shared keys_zone index in sync and avoids shell-based file deletion.
	if scope == "all" then
		local res = ngx.location.capture("/_proxy-cache/purge-all", { method = ngx.HTTP_POST })
		if not res or res.status ~= HTTP_OK then
			return self:response(
				HTTP_INTERNAL_SERVER_ERROR,
				"error",
				"native cache purge failed (status " .. tostring(res and res.status or "nil") .. ")"
			)
		end
		return self:response(HTTP_OK, "success", { scope = "all", purged = true })
	end

	if scope ~= "url" then
		return self:response(HTTP_BAD_REQUEST, "error", "invalid scope (use 'all' or 'url')")
	end

	if type(body.urls) ~= "table" or #body.urls == 0 then
		return self:response(HTTP_BAD_REQUEST, "error", "scope 'url' requires a non-empty 'urls' array")
	end
	if #body.urls > MAX_PROXY_CACHE_PURGE_URLS then
		return self:response(HTTP_BAD_REQUEST, "error", "too many URLs (maximum 100)")
	end

	-- Purge each URL by its exact cache key via the native proxy_cache_purge
	-- directive in the internal /_proxy-cache/purge location (index-aware).
	local purged, not_found, errors = 0, 0, {}
	for _, item in ipairs(body.urls) do
		local url = type(item) == "table" and item.url or item
		local key_template = type(item) == "table" and item.key or nil
		if type(url) ~= "string" then
			errors[#errors + 1] = "invalid url entry"
		elseif #url > MAX_PROXY_CACHE_URL_LENGTH then
			errors[#errors + 1] = "url is too long"
		else
			local key, kerr = reconstruct_cache_key(url, key_template)
			if not key then
				errors[#errors + 1] = kerr
			else
				ngx_req.set_header("X-BW-Purge-Key", key)
				local res = ngx.location.capture("/_proxy-cache/purge")
				if res and res.status == HTTP_OK then
					purged = purged + 1
				elseif res and (res.status == HTTP_NOT_FOUND or res.status == HTTP_PRECONDITION_FAILED) then
					-- 412 is how ngx_cache_purge says "key not in cache" by default
					-- (`cache_purge_legacy_status` is on unless turned off); 404 is the same answer
					-- with it off. Accept both: purging an entry that is not cached -- which is every
					-- purge issued right after a purge-all -- is a no-op, not a failure. Counting it
					-- as an error failed the whole call with 500, which the API turned into 503 and
					-- the UI into "Error purging web cache".
					not_found = not_found + 1
				else
					errors[#errors + 1] = "purge failed for "
						.. url
						.. " (status "
						.. tostring(res and res.status or "nil")
						.. ")"
				end
			end
		end
	end

	if #errors > 0 then
		-- Also to the instance log: the caller (API -> UI) only surfaces "error", so a purge that
		-- fails on this side left nothing to debug with anywhere.
		logger:log(ERR, "proxy cache purge failed : " .. table.concat(errors, ", "))
		return self:response(
			HTTP_INTERNAL_SERVER_ERROR,
			"error",
			{ purged = purged, not_found = not_found, errors = errors }
		)
	end
	return self:response(HTTP_OK, "success", { purged = purged, not_found = not_found })
end

api.global.GET["^/proxy%-cache/status$"] = function(self)
	-- Per-instance view of the shared proxy_cache zone: is it present on disk,
	-- how many entries and how many bytes. USE_PROXY_CACHE is multisite, so
	-- "enabled" here means the zone directory exists (nginx creates it when any
	-- service enables the cache).
	local enabled, file_count, size_bytes = false, 0, 0
	local handle = io.popen(
		"if [ -d '"
			.. PROXY_CACHE_DIR
			.. "' ]; then printf 'yes %s %s' "
			.. "\"$(find '"
			.. PROXY_CACHE_DIR
			.. "' -type f 2>/dev/null | wc -l | tr -d ' ')\" "
			.. "\"$(du -sb '"
			.. PROXY_CACHE_DIR
			.. "' 2>/dev/null | cut -f1)\"; else printf 'no 0 0'; fi"
	)
	if handle then
		local out = handle:read("*a") or ""
		handle:close()
		local present, count, size = out:match("^(%S+)%s+(%S+)%s+(%S+)")
		enabled = present == "yes"
		file_count = tonumber(count) or 0
		size_bytes = tonumber(size) or 0
	end
	return self:response(HTTP_OK, "success", {
		enabled = enabled,
		path = PROXY_CACHE_DIR,
		file_count = file_count,
		size_bytes = size_bytes,
	})
end

function api:is_allowed_ip()
	-- The internal API socket is already confined to /var/run/bunkerweb and
	-- still passes the server-level Host and bearer-token checks.
	if self.ctx.bw.remote_addr == "unix:" then
		return true, "ok"
	end
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
				if type(resp["msg"]) == "table" then
					resp["data"] = resp["msg"]
					resp["msg"] = resp["status"]
				elseif #resp["msg"] == 0 then
					resp["msg"] = ""
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
