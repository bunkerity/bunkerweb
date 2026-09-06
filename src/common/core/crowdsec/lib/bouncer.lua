package.path = package.path .. ";./?.lua"

local config = require "crowdsec.lib.config"
local iputils = require "crowdsec.lib.iputils"
local http = require "resty.http"
local cjson = require "cjson"
local captcha = require "crowdsec.lib.captcha"
local flag = require "crowdsec.lib.flag"
local utils = require "crowdsec.lib.utils"
local ban = require "crowdsec.lib.ban"
local challenge = require "crowdsec.lib.challenge"
local url = require "crowdsec.lib.url"
-- BunkerWeb local modification: pull MAX_HEADERS from BW config so
-- ngx.req.get_headers() does not silently truncate at 100 when operators raise it.
local bw_utils = require "bunkerweb.utils"
local bit
if _VERSION == "Lua 5.1" then bit = require "bit" else bit = require "bit32" end

-- contain runtime = {}
local runtime = {}
-- remediations are stored in cache as int (shared dict tags)
-- we need to translate IDs to text with this.
runtime.remediations = {}
runtime.remediations["1"] = "ban"
runtime.remediations["2"] = "captcha"


runtime.timer_started = false

local csmod = {}

local PASSTHROUGH = "passthrough"
local DENY = "deny"

local APPSEC_API_KEY_HEADER = "x-crowdsec-appsec-api-key"
local APPSEC_IP_HEADER = "x-crowdsec-appsec-ip"
local APPSEC_HOST_HEADER = "x-crowdsec-appsec-host"
local APPSEC_VERB_HEADER = "x-crowdsec-appsec-verb"
local APPSEC_URI_HEADER = "x-crowdsec-appsec-uri"
local APPSEC_USER_AGENT_HEADER = "x-crowdsec-appsec-user-agent"
local REMEDIATION_API_KEY_HEADER = 'x-api-key'

-- BunkerWeb local modification: BunkerWeb loads one private copy of this module per
-- distinct per-service configuration, and they all share the single crowdsec_cache
-- shared dict. When those configurations target different Local APIs the caller
-- passes a short prefix so decisions, stream bookkeeping and captcha state cannot
-- bleed between them. Deployments with a single Local API pass nothing and keep
-- upstream's exact keys, so the request path pays no extra concatenation.
local function namespaced_cache(dict, prefix)
  return {
    get = function(_, key) return dict:get(prefix .. key) end,
    set = function(_, key, value, exptime, flags)
      return dict:set(prefix .. key, value, exptime or 0, flags or 0)
    end,
    delete = function(_, key) return dict:delete(prefix .. key) end,
  }
end

-- init function
function csmod.init(configFile, userAgent, cachePrefix) -- BW local mod: cachePrefix
  local conf, err = config.loadConfig(configFile)
  if conf == nil then
    return nil, err
  end
  runtime.conf = conf
  runtime.userAgent = userAgent
  runtime.cache = ngx.shared.crowdsec_cache
  if cachePrefix and cachePrefix ~= "" then -- BW local mod
    runtime.cache = namespaced_cache(runtime.cache, cachePrefix)
  end
  runtime.fallback = runtime.conf["FALLBACK_REMEDIATION"]

  if runtime.conf["ENABLED"] == "false" then
    return "Disabled", nil
  end

  if runtime.conf["REDIRECT_LOCATION"] == "/" then
    ngx.log(ngx.ERR, "redirect location is set to '/' this will lead into infinite redirection")
  end

  local captcha_ok = true
  local err = captcha.New(runtime.conf["SITE_KEY"], runtime.conf["SECRET_KEY"], runtime.conf["CAPTCHA_TEMPLATE_PATH"], runtime.conf["CAPTCHA_PROVIDER"])
  if err ~= nil then
    -- ngx.log(ngx.ERR, "error loading captcha plugin: " .. err)
    captcha_ok = false
  end
  local succ, err, forcible = runtime.cache:set("captcha_ok", captcha_ok)
  if not succ then
    ngx.log(ngx.ERR, "failed to add captcha state key in cache: "..err)
  end
  if forcible then
    ngx.log(ngx.ERR, "Lua shared dict (crowdsec cache) is full, please increase dict size in config")
  end


  -- local err = ban.new(runtime.conf["BAN_TEMPLATE_PATH"], runtime.conf["REDIRECT_LOCATION"], runtime.conf["RET_CODE"])
  -- if err ~= nil then
  --   ngx.log(ngx.ERR, "error loading ban plugins: " .. err)
  -- end

  if runtime.conf["REDIRECT_LOCATION"] ~= "" then
    table.insert(runtime.conf["EXCLUDE_LOCATION"], runtime.conf["REDIRECT_LOCATION"])
  end

  if runtime.conf["SSL_VERIFY"] == "false" then
    runtime.conf["SSL_VERIFY"] = false
  else
    runtime.conf["SSL_VERIFY"] = true
  end

  if runtime.conf["ALWAYS_SEND_TO_APPSEC"] == "false" then
    runtime.conf["ALWAYS_SEND_TO_APPSEC"] = false
  else
    runtime.conf["ALWAYS_SEND_TO_APPSEC"] = true
  end

  runtime.conf["APPSEC_ENABLED"] = false

  if runtime.conf["APPSEC_URL"] ~= "" then
    local u = url.parse(runtime.conf["APPSEC_URL"])
    runtime.conf["APPSEC_ENABLED"] = true
    runtime.conf["APPSEC_HOST"] = u.host
    if u.port ~= nil then
      runtime.conf["APPSEC_HOST"] = runtime.conf["APPSEC_HOST"] .. ":" .. u.port
    end
    ngx.log(ngx.NOTICE, "APPSEC is enabled on '" .. runtime.conf["APPSEC_HOST"] .. "'")
  end


  -- if stream mode, add callback to stream_query and start timer
  if runtime.conf["MODE"] == "stream" then
    local succ, err, forcible = runtime.cache:set("startup", true)
    if not succ then
      ngx.log(ngx.ERR, "failed to add startup key in cache: "..err)
    end
    if forcible then
      ngx.log(ngx.ERR, "Lua shared dict (crowdsec cache) is full, please increase dict size in config")
    end
    local succ, err, forcible = runtime.cache:set("first_run", true)
    if not succ then
      ngx.log(ngx.ERR, "failed to add first_run key in cache: "..err)
    end
    if forcible then
      ngx.log(ngx.ERR, "Lua shared dict (crowdsec cache) is full, please increase dict size in config")
    end
  end

  if runtime.conf["API_URL"] == "" and  runtime.conf["APPSEC_URL"] == "" then
    ngx.log(ngx.ERR, "Neither API_URL or APPSEC_URL are defined, remediation component will not do anything")
  end

  if runtime.conf["API_URL"] == "" and  runtime.conf["APPSEC_URL"] ~= "" then
    ngx.log(ngx.ERR, "Only APPSEC_URL is defined, local API decisions will be ignored")
  end



  return true, nil
end


function csmod.validateCaptcha(captcha_res, remote_ip)
  return captcha.Validate(captcha_res, remote_ip)
end


local function get_remediation_http_request(link)
  local httpc = http.new()
  if runtime.conf['MODE'] == 'stream' then
    httpc:set_timeout(runtime.conf['STREAM_REQUEST_TIMEOUT'])
  else
    httpc:set_timeout(runtime.conf['REQUEST_TIMEOUT'])
  end
  local res, err = httpc:request_uri(link, {
    method = "GET",
    headers = {
      ['Connection'] = 'close',
      [REMEDIATION_API_KEY_HEADER] = runtime.conf["API_KEY"],
      ['User-Agent'] = runtime.userAgent
    },
    ssl_verify = runtime.conf["SSL_VERIFY"]
  })
  httpc:close()
  return res, err
end

local function parse_duration(duration)
  local match, err = ngx.re.match(duration, "^((?<hours>[0-9]+)h)?((?<minutes>[0-9]+)m)?(?<seconds>[0-9]+)")
  local ttl = 0
  if not match then
    if err then
      return ttl, err
    end
  end
  if match["hours"] ~= nil and match["hours"] ~= false then
    local hours = tonumber(match["hours"])
    ttl = ttl + (hours * 3600)
  end
  if match["minutes"] ~= nil and match["minutes"] ~= false then
    local minutes = tonumber(match["minutes"])
    ttl = ttl + (minutes * 60)
  end
  if match["seconds"] ~= nil and match["seconds"] ~= false then
    local seconds = tonumber(match["seconds"])
    ttl = ttl + seconds
  end
  return ttl, nil
end

local function get_remediation_id(remediation)
  for key, value in pairs(runtime.remediations) do
    if value == remediation then
      return tonumber(key)
    end
  end
  return nil
end

local function item_to_string(item, scope)
  local ip, cidr, ip_version
  if scope:lower() == "ip" then
    ip = item
  end
  if scope:lower() == "range" then
    ip, cidr = iputils.splitRange(item, scope)
  end

  local ip_network_address, is_ipv4 = iputils.parseIPAddress(ip)
  if ip_network_address == nil then
    return nil
  end
  if is_ipv4 then
    ip_version = "ipv4"
    if cidr == nil then
      cidr = 32
    end
  else
    ip_version = "ipv6"
    ip_network_address = ip_network_address.uint32[3]..":"..ip_network_address.uint32[2]..":"..ip_network_address.uint32[1]..":"..ip_network_address.uint32[0]
    if cidr == nil then
      cidr = 128
    end
  end

  if ip_version == nil then
    return "normal_"..item
  end
  local ip_netmask = iputils.cidrToInt(cidr, ip_version)
  return ip_version.."_"..ip_netmask.."_"..ip_network_address
end

local function set_refreshing(value)
  local succ, err, forcible = runtime.cache:set("refreshing", value)
  if not succ then
    error("Failed to set refreshing key in cache: "..err)
  end
  if forcible then
    ngx.log(ngx.ERR, "Lua shared dict (crowdsec cache) is full, please increase dict size in config")
  end
end

local function stream_query(premature)
  -- As this function is running inside coroutine (with ngx.timer.at),
  -- we need to raise error instead of returning them

  if runtime.conf["API_URL"] == "" then
    return
  end

  ngx.log(ngx.DEBUG, "running timers: " .. tostring(ngx.timer.running_count()) .. " | pending timers: " .. tostring(ngx.timer.pending_count()))

  if premature then
    ngx.log(ngx.DEBUG, "premature run of the timer, returning")
    return
  end

  local refreshing = runtime.cache:get("refreshing")

  if refreshing == true then
    ngx.log(ngx.DEBUG, "another worker is refreshing the data, returning")
    local ok, err = ngx.timer.at(runtime.conf["UPDATE_FREQUENCY"], stream_query)
    if not ok then
      error("Failed to create the timer: " .. (err or "unknown"))
    end
    return
  end

  local last_refresh = runtime.cache:get("last_refresh")
  if last_refresh ~= nil then
      -- local last_refresh_time = tonumber(last_refresh)
      local now = ngx.time()
      if now - last_refresh < runtime.conf["UPDATE_FREQUENCY"] then
        ngx.log(ngx.DEBUG, "last refresh was less than " .. runtime.conf["UPDATE_FREQUENCY"] .. " seconds ago, returning")
        local ok, err = ngx.timer.at(runtime.conf["UPDATE_FREQUENCY"], stream_query)
        if not ok then
          error("Failed to create the timer: " .. (err or "unknown"))
        end
        return
      end
  end

  set_refreshing(true)

  local is_startup = runtime.cache:get("startup")
  ngx.log(ngx.DEBUG, "Stream Query from worker : " .. tostring(ngx.worker.id()) .. " with startup "..tostring(is_startup) .. " | premature: " .. tostring(premature))
  local link = runtime.conf["API_URL"] .. "/v1/decisions/stream?startup=" .. tostring(is_startup)
  local res, err = get_remediation_http_request(link)
  if not res then
    local ok, err2 = ngx.timer.at(runtime.conf["UPDATE_FREQUENCY"], stream_query)
    if not ok then
      set_refreshing(false)
      error("Failed to create the timer: " .. (err2 or "unknown"))
    end
    set_refreshing(false)
    error("request failed: ".. err)
  end

  local succ, err, forcible = runtime.cache:set("last_refresh", ngx.time())
  if not succ then
    error("Failed to set last_refresh key in cache: "..err)
  end
  if forcible then
    ngx.log(ngx.ERR, "Lua shared dict (crowdsec cache) is full, please increase dict size in config")
  end

  local status = res.status
  local body = res.body

  ngx.log(ngx.DEBUG, "Response:" .. tostring(status) .. " | " .. tostring(body))

  if status~=200 then
    local ok, err = ngx.timer.at(runtime.conf["UPDATE_FREQUENCY"], stream_query)
    if not ok then
      set_refreshing(false)
      error("Failed to create the timer: " .. (err or "unknown"))
    end
    set_refreshing(false)
    error("HTTP error while request to Local API '" .. status .. "' with message (" .. tostring(body) .. ")")
  end

  local decisions = cjson.decode(body)
  -- process deleted decisions
  if type(decisions.deleted) == "table" then
      for i, decision in pairs(decisions.deleted) do
        if decision.type == "captcha" then
          runtime.cache:delete("captcha_" .. decision.value)
        end
        local key = item_to_string(decision.value, decision.scope)
        runtime.cache:delete(key)
        ngx.log(ngx.DEBUG, "Deleting '" .. key .. "'")
      end
  end

  -- process new decisions
  if type(decisions.new) == "table" then
    for i, decision in pairs(decisions.new) do
      if runtime.conf["BOUNCING_ON_TYPE"] == decision.type or runtime.conf["BOUNCING_ON_TYPE"] == "all" then
        local ttl, err = parse_duration(decision.duration)
        if err ~= nil then
          ngx.log(ngx.ERR, "[Crowdsec] failed to parse ban duration '" .. decision.duration .. "' : " .. err)
        end
        local remediation_id = get_remediation_id(decision.type)
        if remediation_id == nil then
          remediation_id = get_remediation_id(runtime.fallback)
        end
        local key = item_to_string(decision.value, decision.scope)
        local succ, err, forcible = runtime.cache:set(key, false, ttl, remediation_id)
        if not succ then
          ngx.log(ngx.ERR, "failed to add ".. decision.value .." : "..err)
        end
        if forcible then
          ngx.log(ngx.ERR, "Lua shared dict (crowdsec cache) is full, please increase dict size in config")
        end
        ngx.log(ngx.DEBUG, "Adding '" .. key .. "' in cache for '" .. ttl .. "' seconds")
      end
    end
  end

  -- not startup anymore after first callback
  local succ, err, forcible = runtime.cache:set("startup", false)
  if not succ then
    ngx.log(ngx.ERR, "failed to set startup key in cache: "..err)
  end
  if forcible then
    ngx.log(ngx.ERR, "Lua shared dict (crowdsec cache) is full, please increase dict size in config")
  end


  local ok, err = ngx.timer.at(runtime.conf["UPDATE_FREQUENCY"], stream_query)
  if not ok then
    set_refreshing(false)
    error("Failed to create the timer: " .. (err or "unknown"))
  end

  set_refreshing(false)
  ngx.log(ngx.DEBUG, "end of stream_query")
  return nil
end

local function live_query(ip)
  if runtime.conf["API_URL"] == "" then
    return true, nil, nil
  end
  local link = runtime.conf["API_URL"] .. "/v1/decisions?ip=" .. ip
  local res, err = get_remediation_http_request(link)
  if not res then
    return true, nil, "request failed: ".. err
  end

  local status = res.status
  local body = res.body
  if status~=200 then
    return true, nil, "Http error " .. status .. " while talking to LAPI (" .. link .. ")"
  end
  if body == "null" then -- no result from API, no decision for this IP
    -- set ip in cache and DON'T block it
    local key = item_to_string(ip, "ip")
    local succ, err, forcible = runtime.cache:set(key, true, runtime.conf["CACHE_EXPIRATION"], 1)
    if not succ then
      ngx.log(ngx.ERR, "failed to add ip '" .. ip .. "' in cache: "..err)
    end
    if forcible then
      ngx.log(ngx.ERR, "Lua shared dict (crowdsec cache) is full, please increase dict size in config")
    end
    return true, nil, nil
  end
  local decision = cjson.decode(body)[1]

  if runtime.conf["BOUNCING_ON_TYPE"] == decision.type or runtime.conf["BOUNCING_ON_TYPE"] == "all" then
    local remediation_id = get_remediation_id(decision.type)
    if remediation_id == nil then
      remediation_id = get_remediation_id(runtime.fallback)
    end
    local key = item_to_string(decision.value, decision.scope)
    local succ, err, forcible = runtime.cache:set(key, false, runtime.conf["CACHE_EXPIRATION"], remediation_id)
    if not succ then
      ngx.log(ngx.ERR, "failed to add ".. decision.value .." : "..err)
    end
    if forcible then
      ngx.log(ngx.ERR, "Lua shared dict (crowdsec cache) is full, please increase dict size in config")
    end
    ngx.log(ngx.DEBUG, "Adding '" .. key .. "' in cache for '" .. runtime.conf["CACHE_EXPIRATION"] .. "' seconds")
    -- BunkerWeb local modification: the decoded decision travels back with the remediation so
    -- Allow() can name the scenario in the reason recorded on the report. Live queries only:
    -- the cache stores a remediation id and nothing else, so a cache hit has no scenario to give.
    return false, decision.type, nil, decision
  else
    return true, nil, nil
  end
end

local function get_body()

  -- the LUA module requires a content-length header to read a body for HTTP 2/3 requests, although it's not mandatory.
  -- This means that we will likely miss body, but AFAIK, there's no workaround for this.
  -- do not even try to read the body if there's no content-length as the LUA API will throw an error
  if ngx.req.http_version() >= 2 and ngx.var.http_content_length == nil then
    ngx.log(ngx.DEBUG, "No content-length header in request")
    return nil
  end
  ngx.req.read_body()
  local body = ngx.req.get_body_data()
  if body == nil then
    local bodyfile = ngx.req.get_body_file()
    if bodyfile then
      local fh, err = io.open(bodyfile, "r")
      if fh then
        body = fh:read("*a")
        fh:close()
      end
    end
  end
  return body
end

function csmod.GetCaptchaTemplate()
  return captcha.GetTemplate()
end

function csmod.GetCaptchaBackendKey()
  return captcha.GetCaptchaBackendKey()
end

function csmod.SetupStream()
  -- if it stream mode and startup start timer
  if runtime.conf["API_URL"] == "" then
    return
  end
  ngx.log(ngx.DEBUG, "timer started: " .. tostring(runtime.timer_started) .. " in worker " .. tostring(ngx.worker.id()))
  if runtime.timer_started == false and runtime.conf["MODE"] == "stream" then
    local ok, err
    ok, err = ngx.timer.at(runtime.conf["UPDATE_FREQUENCY"], stream_query)
    if not ok then
      return true, nil, "Failed to create the timer: " .. (err or "unknown")
    end
    runtime.timer_started = true
    ngx.log(ngx.DEBUG, "Timer launched")
  end
end

function csmod.allowIp(ip)
  if runtime.conf == nil then
    return true, nil, "Configuration is bad, cannot run properly"
  end

  if runtime.conf["API_URL"] == "" then
    return true, nil, nil
  end

  csmod.SetupStream()

  local key = item_to_string(ip, "ip")
  if key == nil then
    return true, nil, "Check failed '" .. ip .. "' has no valid IP address"
  end
  local key_parts = {}
  for i in key.gmatch(key, "([^_]+)") do
    table.insert(key_parts, i)
  end

  local key_type = key_parts[1]
  if key_type == "normal" then
    local in_cache, remediation_id = runtime.cache:get(key)
    if in_cache ~= nil then -- we have it in cache
      ngx.log(ngx.DEBUG, "'" .. key .. "' is in cache")
      return in_cache, runtime.remediations[tostring(remediation_id)], nil
    end
  end

  local ip_network_address = key_parts[3]
  local netmasks = iputils.netmasks_by_key_type[key_type]
  for i, netmask in pairs(netmasks) do
    local item
    if key_type == "ipv4" then
      item = key_type.."_"..netmask.."_"..iputils.ipv4_band(ip_network_address, netmask)
    end
    if key_type == "ipv6" then
      item = key_type.."_"..table.concat(netmask, ":").."_"..iputils.ipv6_band(ip_network_address, netmask)
    end
    local in_cache, remediation_id = runtime.cache:get(item)
    if in_cache ~= nil then -- we have it in cache
      ngx.log(ngx.DEBUG, "'" .. key .. "' is in cache")
      return in_cache, runtime.remediations[tostring(remediation_id)], nil
    end
  end

  -- if live mode, query lapi
  if runtime.conf["MODE"] == "live" then
    local ok, remediation, err, decision = live_query(ip)
    return ok, remediation, err, decision
  end
  return true, nil, nil
end


function csmod.AppSecCheck(ip)
  local httpc = http.new()
  httpc:set_timeouts(runtime.conf["APPSEC_CONNECT_TIMEOUT"], runtime.conf["APPSEC_SEND_TIMEOUT"], runtime.conf["APPSEC_PROCESS_TIMEOUT"])

  local uri = ngx.var.request_uri
  local headers = ngx.req.get_headers(tonumber((bw_utils.get_variable("MAX_HEADERS", false))) or 100) -- BW local mod

  -- overwrite headers with crowdsec appsec require headers
  headers[APPSEC_IP_HEADER] = ip
  headers[APPSEC_HOST_HEADER] = ngx.var.http_host
  headers[APPSEC_VERB_HEADER] = ngx.var.request_method
  headers[APPSEC_URI_HEADER] = uri
  headers[APPSEC_USER_AGENT_HEADER] = ngx.var.http_user_agent
  headers[APPSEC_API_KEY_HEADER] = runtime.conf["API_KEY"]

  -- set CrowdSec APPSEC Host
  headers["host"] = runtime.conf["APPSEC_HOST"]

  local ok, remediation, status_code = true, "allow", 200
  if runtime.conf["APPSEC_FAILURE_ACTION"] == DENY then
    ok = false
    remediation = runtime.conf["FALLBACK_REMEDIATION"]
  end

  local method = "GET"

  local body = get_body()
  if body ~= nil then
    if #body > 0 then
      method = "POST"
      if headers["content-length"] == nil then
        headers["content-length"] = tostring(#body)
      end
    end
  else
    headers["content-length"] = nil
  end

  local res, err = httpc:request_uri(runtime.conf["APPSEC_URL"], {
    method = method,
    headers = headers,
    body = body,
    ssl_verify = runtime.conf["SSL_VERIFY"],
  })
  httpc:close()

  if err ~= nil then
    ngx.log(ngx.ERR, "Fallback because of err: " .. err)
    return ok, remediation, status_code, nil, err
  end

  if res.status == 200 then
    ok = true
    remediation = "allow"
  elseif res.status == 403 then
    ok = false
    ngx.log(ngx.DEBUG, "Appsec body response: " .. res.body)
    -- Guarded: an unparsable 403 body used to raise out of AppSecCheck, through Allow, into
    -- helpers.lua's pcall -- which logs an ERR and serves the request UNCHECKED.
    local decoded, response = pcall(cjson.decode, res.body)
    if not decoded then
      ngx.log(ngx.ERR, "Unparsable AppSec response body, falling back: " .. tostring(response))
      return false, runtime.conf["FALLBACK_REMEDIATION"], ngx.HTTP_FORBIDDEN, nil, nil
    end
    remediation = response.action
    if response.http_status ~= nil then
      ngx.log(ngx.DEBUG, "Got status code from APPSEC: " .. response.http_status)
      status_code = response.http_status
    else
      status_code = ngx.HTTP_FORBIDDEN
    end
    if remediation == "challenge" then
      -- CrowdSec 1.8 bot detection: the 403 carries the page to serve back on the
      -- original URI. user_body_content / user_headers / user_cookies are omitempty,
      -- so any of them can be missing -- Allow() decides what a missing body means.
      return ok, remediation, status_code, {
        body = response.user_body_content,
        headers = response.user_headers,
        cookies = response.user_cookies,
      }, nil
    end
  elseif res.status == 401 then
    ngx.log(ngx.ERR, "Unauthenticated request to APPSEC")
  else
    ngx.log(ngx.ERR, "Bad request to APPSEC (" .. res.status .. "): " .. res.body)
  end

  return ok, remediation, status_code, nil, err

end

-- @param ip string: the client address to judge
-- @param no_render boolean: report the remediation, never write a response body. Two callers
--   need this: crowdsec:api()'s /crowdsec/ping connectivity probe, which would otherwise get a
--   challenge or captcha page spliced into its JSON answer, and SECURITY_MODE=detect, where a
--   rendered challenge would replace the origin's response and silently turn "detect" into
--   "block" -- the dispatcher can suppress a deny STATUS, but not a body already written.
-- @param antibot_provider string|nil: BunkerWeb's own antibot challenge provider to use for a
--   `captcha` remediation (CROWDSEC_CAPTCHA_PROVIDER, resolved per service by crowdsec:access()).
--   When set, a `captcha` is neither rendered here nor downgraded to FALLBACK_REMEDIATION: it is
--   handed back to the caller, which flags the request for the antibot plugin. nil or "no" keeps
--   the upstream behaviour.
-- @return boolean ok, string msg, boolean banned, boolean served, table verdict,
--   string antibot_provider
--   `served` means the response (AppSec challenge page, or captcha template) has already
--   been written and the caller must end the access phase with ngx.OK, not a deny status.
--   `verdict` describes the remediation for the report/ban reason -- `source` (lapi|appsec),
--   `action` (ban|captcha|challenge), `http_status`, and on a live LAPI decision `scenario`,
--   `origin` and `duration`. nil when nothing was remediated.
--   `antibot_provider` is echoed back on -- and only on -- a delegated `captcha`. It is the one
--   unambiguous signal of that path: every other return leaves it nil, so the caller never has to
--   infer "delegated" from a combination of the other four.
function csmod.Allow(ip, no_render, antibot_provider)
  if runtime.conf["ENABLED"] == "false" then
    return true, "disabled"
  end

  if runtime.conf["ENABLE_INTERNAL"] == "false" and ngx.req.is_internal() then
    return true, "internal"
  end

  local remediationSource = flag.BOUNCER_SOURCE
  local ret_code = nil
  local appsec_response = nil

  if utils.table_len(runtime.conf["EXCLUDE_LOCATION"]) > 0 then
    for k, v in pairs(runtime.conf["EXCLUDE_LOCATION"]) do
      if ngx.var.uri == v then
        ngx.log(ngx.ERR,  "whitelisted location: " .. v)
        return true, "whitelisted " .. v
      end
      local uri_to_check = v
      if utils.ends_with(uri_to_check, "/") == false then
        uri_to_check = uri_to_check .. "/"
      end
      if utils.starts_with(ngx.var.uri, uri_to_check) then
        -- BunkerWeb local modification: this arm logged and fell through, so every
        -- CROWDSEC_EXCLUDE_LOCATION entry only ever matched the exact URI and the
        -- documented prefix form silently bounced anyway. Upstream v1.0.18 exits here
        -- (lib/crowdsec.lua, ngx.exit(ngx.DECLINED)); this fork returns instead because
        -- the BunkerWeb plugin dispatcher owns the exit.
        ngx.log(ngx.ERR,  "whitelisted location: " .. uri_to_check)
        return true, "whitelisted " .. uri_to_check
      end
    end
  end

  local ok, remediation, err, decision = csmod.allowIp(ip)
  if err ~= nil then
    ngx.log(ngx.ERR, "[Crowdsec] bouncer error: " .. err)
  end

  -- if the ip is now allowed, try to delete its captcha state in cache.
  -- Only a state created for a LAPI decision is dropped here: an AppSec captcha does not
  -- depend on the IP having a decision, so deleting it would destroy the pending verification
  -- (or the validated grace period) on every single request and make the captcha impossible to
  -- solve -- which also made the :748 loop fix below inert for the AppSec source. Second half
  -- of upstream v1.0.18's captcha/AppSec loop fix (lib/crowdsec.lua).
  if ok == true then
    local _, cached_flags = runtime.cache:get("captcha_" .. ip)
    local cached_source = flag.GetFlags(cached_flags)
    if cached_source ~= flag.APPSEC_SOURCE then
      runtime.cache:delete("captcha_" .. ip)
    end
  end

  -- check with appSec if the remediation component doesn't have decisions for the IP
  -- OR
  -- that user configured the remediation component to always check on the appSec (even if there is a decision for the IP)
  if ok == true or runtime.conf["ALWAYS_SEND_TO_APPSEC"] == true then
    if runtime.conf["APPSEC_ENABLED"] == true and ngx.var.no_appsec ~= "1" then
      local appsecOk, appsecRemediation, status_code, appsec_resp, appsec_err = csmod.AppSecCheck(ip)
      if appsec_err ~= nil then
        ngx.log(ngx.ERR, "AppSec check: " .. appsec_err)
      end
      if appsecOk == false then
        ok = false
        remediationSource = flag.APPSEC_SOURCE
        remediation = appsecRemediation
        ret_code = status_code
        appsec_response = appsec_resp
      end
    end
  end

  local captcha_ok = runtime.cache:get("captcha_ok")

  -- BunkerWeb local modification: a `captcha` remediation is rendered by BunkerWeb's own antibot
  -- plugin, never by the vendored CrowdSec captcha template -- BunkerWeb exposes no SITE_KEY /
  -- SECRET_KEY, so captcha.New() fails at init and `captcha_ok` is false on every request. Without
  -- this arm the block below rewrites every `captcha` decision into FALLBACK_REMEDIATION (`ban` in
  -- the shipped template) before anything downstream can see it, and the delegation could never
  -- happen at all.
  local delegate_captcha = antibot_provider ~= nil and antibot_provider ~= "" and antibot_provider ~= "no"

  if runtime.fallback ~= "" then
    -- if we can't use captcha, fallback
    -- BunkerWeb local modification: `not captcha_ok` and not upstream's `captcha_ok == false`.
    -- `captcha_ok` comes back nil, not false, whenever the key is absent from the shared dict (an
    -- eviction, a worker that started before init wrote it), and nil ~= false: the fallback then
    -- did not fire, the captcha block below was skipped because nil is falsy, no arm inside
    -- `if not ok` matched, and the request fell out to `return true, "allow"` -- served, on a
    -- decision that asked for a captcha. Reachable only through AppSec until now; widening
    -- BOUNCING_ON_TYPE to `all` routes every LAPI captcha decision through here.
    if remediation == "captcha" and not captcha_ok and not delegate_captcha then
      remediation = runtime.fallback
    end

    -- if remediation is not supported, fallback
    if remediation ~= "captcha" and remediation ~= "ban" and remediation ~= "challenge" then
      remediation = runtime.fallback
    end
  end

  -- BunkerWeb local modification: what was decided, in the shape crowdsec:access() records as
  -- the report/ban reason. Built here, after the fallback block settled `remediation`, and kept
  -- in step by the one arm below that rewrites it. Only on a remediation: the allow path is the
  -- hot path and must not allocate. The LAPI fields exist on a live query only -- a cache hit
  -- stores a remediation id and nothing else -- and never for an AppSec verdict, whose
  -- remediation did not come from a decision at all.
  local verdict
  if not ok then
    verdict = {
      source = remediationSource == flag.APPSEC_SOURCE and "appsec" or "lapi",
      action = remediation,
      http_status = ret_code,
    }
    if decision ~= nil and remediationSource ~= flag.APPSEC_SOURCE then
      verdict.scenario = decision.scenario
      verdict.origin = decision.origin
      verdict.duration = decision.duration
    end
  end

  -- Before the captcha validation block on purpose: that block ends on ngx.redirect(), which
  -- writes a response just as much as a rendered page does.
  if no_render and not ok then
    return true,
      "not rendered, remediation was '" .. tostring(remediation) .. "'",
      remediation ~= "allow",
      nil,
      verdict
  end

  if captcha_ok then -- if captcha can be use (configuration is valid)
    -- we check if the IP need to validate its captcha before checking it against crowdsec local API
    local previous_uri, flags = runtime.cache:get("captcha_"..ip)
    local source, state_id, err = flag.GetFlags(flags)
    local body = get_body()

    -- nil body means it was likely not a post, abort here because the user hasn't provided a captcha solution

    if previous_uri ~= nil and state_id == flag.VERIFY_STATE and body ~= nil then
        local captcha_res = ngx.req.get_post_args()[csmod.GetCaptchaBackendKey()] or 0
        if captcha_res ~= 0 then
            local valid, err = csmod.validateCaptcha(captcha_res, ip)
            if err ~= nil then
              ngx.log(ngx.ERR, "Error while validating captcha: " .. err)
            end
            if valid == true then
                -- if the captcha is valid and has been applied by the application security component
                -- then we delete the state from the cache because from the bouncing part, if the user solve the captcha
                -- we will not propose a captcha until the 'CAPTCHA_EXPIRATION'.
                -- But for the Application security component, we serve the captcha each time the user trigger it.
                if source == flag.APPSEC_SOURCE then
                  runtime.cache:delete("captcha_"..ip)
                else
                  local succ, err, forcible = runtime.cache:set("captcha_"..ip, previous_uri, runtime.conf["CAPTCHA_EXPIRATION"], bit.bor(flag.VALIDATED_STATE, source) )
                  if not succ then
                    ngx.log(ngx.ERR, "failed to add key about captcha for ip '" .. ip .. "' in cache: "..err)
                  end
                  if forcible then
                    ngx.log(ngx.ERR, "Lua shared dict (crowdsec cache) is full, please increase dict size in config")
                  end
                end
                -- captcha is valid, we redirect the IP to its previous URI but in GET method
                ngx.req.set_method(ngx.HTTP_GET)
                return ngx.redirect(previous_uri)
            else
                ngx.log(ngx.ALERT, "Invalid captcha from " .. ip)
            end
        end
    end
  end
  if not ok then
      -- BunkerWeb local modification: hand a `captcha` remediation to BunkerWeb's antibot rather
      -- than render CrowdSec's own template. First arm on purpose -- `captcha_ok` is false here, so
      -- without it the request falls past the captcha arm below and out of `if not ok` into
      -- `return true, "allow"`: a fail-open on the exact decision this feature exists for.
      -- Nothing is written and nothing is denied: crowdsec:access() flags the request and lets the
      -- plugin chain continue, and the antibot plugin renders the challenge later in the same
      -- access phase (it runs after crowdsec, core/order.json).
      if delegate_captcha and remediation == "captcha" then
        ngx.log(
          ngx.ALERT,
          "[Crowdsec] challenged '"
            .. ip
            .. "' with the BunkerWeb antibot ('"
            .. antibot_provider
            .. "') for a 'captcha' remediation (by "
            .. flag.Flags[remediationSource]
            .. ")"
        )
        return true, "captcha delegated to the BunkerWeb antibot", false, false, verdict, antibot_provider
      end
      if remediation == "challenge" then
        -- CrowdSec 1.8 bot detection. The page is served exactly as CrowdSec sent it, on the
        -- original URI, with its own status and Set-Cookie, and the origin is never reached.
        if appsec_response ~= nil and type(appsec_response.body) == "string" and appsec_response.body ~= "" then
          ngx.log(ngx.ALERT, "[Crowdsec] challenged '" .. ip .. "' with 'appsec challenge' (by " .. flag.Flags[remediationSource] .. ")")
          challenge.apply(ret_code, appsec_response.body, appsec_response.headers, appsec_response.cookies)
          return true, "challenged", false, true, verdict
        end
        -- Never fail open on a malformed envelope: an empty body would be served as a blank
        -- page with the origin skipped, which looks like a broken site and hides the cause.
        -- `ban` and not runtime.fallback: `captcha` is also a valid FALLBACK_REMEDIATION
        -- (lib/config.lua) and, with captcha_ok false as it always is here, it would fall
        -- through every arm below to `return true, "allow"` -- a fail-open in the branch whose
        -- whole point is that there is none.
        ngx.log(ngx.ERR, "[Crowdsec] 'appsec challenge' for '" .. ip .. "' carried no challenge body, falling back to 'ban'")
        remediation = "ban"
        verdict.action = remediation
      end
      if remediation == "ban" then
        ngx.log(ngx.ALERT, "[Crowdsec] denied '" .. ip .. "' with '"..remediation.."' (by " .. flag.Flags[remediationSource] .. ")")
        -- ban.apply(ret_code)
        return true, "denied", true, nil, verdict
      end
      -- if the remediation is a captcha and captcha is well configured
      if remediation == "captcha" and captcha_ok and ngx.var.uri ~= "/favicon.ico" then
          local previous_uri, flags = runtime.cache:get("captcha_"..ip)
          local source, state_id, err = flag.GetFlags(flags)
          -- we check if the IP is already in cache for captcha and not yet validated
          -- A captcha solved for a LAPI decision grants no free pass on the AppSec (and the
          -- other way round), so a validated state only counts for the source that asked for
          -- it. The previous `remediationSource == flag.APPSEC_SOURCE` re-served the captcha
          -- on every single AppSec request: an infinite loop, fixed upstream in v1.0.18.
          if previous_uri == nil or state_id ~= flag.VALIDATED_STATE or source ~= remediationSource then
              ngx.header.content_type = "text/html"
              ngx.header.cache_control = "no-cache"
              ngx.say(csmod.GetCaptchaTemplate())
              local uri = ngx.var.uri
              -- in case its not a GET request, we prefer to fallback on referer
              if ngx.req.get_method() ~= "GET" then
                local headers, err = ngx.req.get_headers(tonumber((bw_utils.get_variable("MAX_HEADERS", false))) or 100) -- BW local mod
                for k, v in pairs(headers) do
                  if k == "referer" then
                    uri = v
                  end
                end
              end
              local succ, err, forcible = runtime.cache:set("captcha_"..ip, uri , 60, bit.bor(flag.VERIFY_STATE, remediationSource))
              if not succ then
                ngx.log(ngx.ERR, "failed to add key about captcha for ip '" .. ip .. "' in cache: "..err)
              end
              if forcible then
                ngx.log(ngx.ERR, "Lua shared dict (crowdsec cache) is full, please increase dict size in config")
              end
              ngx.log(ngx.ALERT, "[Crowdsec] denied '" .. ip .. "' with '"..remediation.."'")
              -- Upstream returns nothing here; in this fork crowdsec:access() reads the first
              -- return value and concatenates the second into an error message, so a bare
              -- return raised "attempt to concatenate a nil value" under helpers.lua's pcall
              -- and the request was then served UNCHECKED. Report the captcha page instead.
              return true, "CrowdSec captcha served", false, true, verdict
          end
      end
  end
  return true, "allow"
end


-- Use it if you are able to close at shuttime
function csmod.close()
end

return csmod
