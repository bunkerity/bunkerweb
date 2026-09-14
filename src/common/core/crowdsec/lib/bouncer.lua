package.path = package.path .. ";./?.lua"

local config = require "crowdsec.lib.config"
local decision_cache = require "crowdsec.lib.decision_cache"
local stream_lock = require "crowdsec.lib.stream_lock"
local cache_partition = require "crowdsec.cache_partition"
local iputils = require "crowdsec.lib.iputils"
local http = require "resty.http"
local cjson = require "cjson"
local decision_json = cjson.new()
decision_json.decode_array_with_array_mt(true)
local captcha = require "crowdsec.lib.captcha"
local flag = require "crowdsec.lib.flag"
local utils = require "crowdsec.lib.utils"
local ban = require "crowdsec.lib.ban"
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
-- shared dict. Decision/stream keys use a Local API prefix; challenge keys use
-- an explicit service/config prefix passed to Allow, never request-global state.
local function namespaced_cache(dict, prefix)
  return {
    get = function(_, key) return dict:get(prefix .. key) end,
    set = function(_, key, value, exptime, flags)
      return dict:set(prefix .. key, value, exptime or 0, flags or 0)
    end,
    delete = function(_, key) return dict:delete(prefix .. key) end,
    safe_set = function(_, key, value, exptime) return dict:safe_set(prefix .. key, value, exptime or 0) end,
    incr = function(_, key, value, initial) return dict:incr(prefix .. key, value, initial) end,
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
  runtime.metadata = ngx.shared.crowdsec_metadata
  if runtime.metadata and cachePrefix and cachePrefix ~= "" then
    runtime.metadata = namespaced_cache(runtime.metadata, cachePrefix)
  end
  runtime.decisions = decision_cache.new(runtime.cache, runtime.metadata)
  runtime.stream_lock_path = "/var/run/bunkerweb/crowdsec-" .. cache_partition.hash(cachePrefix or conf.API_URL or "") .. ".lock"
  runtime.fallback = runtime.conf["FALLBACK_REMEDIATION"]

  if runtime.conf["ENABLED"] == "false" then
    return "Disabled", nil
  end

  if runtime.conf["REDIRECT_LOCATION"] == "/" then
    ngx.log(ngx.ERR, "redirect location is set to '/' this will lead into infinite redirection")
  end

  local captcha_instance, captcha_err = captcha.New(runtime.conf["SITE_KEY"], runtime.conf["SECRET_KEY"], runtime.conf["CAPTCHA_TEMPLATE_PATH"], runtime.conf["CAPTCHA_PROVIDER"])
  runtime.captcha = captcha_instance
  if not captcha_instance and runtime.conf["CAPTCHA_PROVIDER"] ~= nil and runtime.conf["CAPTCHA_PROVIDER"] ~= "" then
    ngx.log(ngx.ERR, "captcha configuration rejected, captcha remediations fall back to ban: " .. tostring(captcha_err))
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
    runtime.cache:incr("startup_request", 1, 0)
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
  if not runtime.captcha then return false, "captcha is not configured" end
  return runtime.captcha.Validate(captcha_res, remote_ip)
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

-- A direct authenticated read: no decision cache, stream timer, remediation or
-- AppSec application request can turn an unavailable LAPI into a healthy result.
function csmod.Health()
  if not runtime.conf then return false, "CrowdSec configuration is not loaded" end
  if runtime.conf["API_URL"] == "" then
    return runtime.conf["APPSEC_ENABLED"], "No Local API configured; AppSec health is not checked", false
  end
  local res, err = get_remediation_http_request(runtime.conf["API_URL"] .. "/v1/decisions?ip=127.0.0.1")
  if err or not res then return false, "Local API request failed" end
  if res.status ~= 200 then return false, "Local API returned HTTP " .. tostring(res.status) end
  local ok, decisions = pcall(cjson.decode, res.body)
  if not ok or (decisions ~= cjson.null and (type(decisions) ~= "table" or not res.body:match("^%s*%["))) then
    return false, "Invalid Local API response"
  end
  return true, nil, true
end

local function item_to_string(item, scope)
  if type(item) ~= "string" or type(scope) ~= "string" then return nil end
  local ip, cidr, ip_version
  if scope:lower() == "ip" then
    ip = item
  end
  if scope:lower() == "range" then
    if not item:match("^[^/]+/%d+$") then return nil end
    ip, cidr = iputils.splitRange(item, scope)
  end
  if not ip or not ip:match("^[%x:%.]+$") then return nil end

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
  if not cidr or cidr < 0 or cidr > (is_ipv4 and 32 or 128) then return nil end
  local ip_netmask = iputils.cidrToInt(cidr, ip_version)
  if is_ipv4 then
    ip_network_address = iputils.ipv4_band(ip_network_address, tonumber(ip_netmask))
  else
    ip_network_address = iputils.ipv6_band(ip_network_address, iputils.netmasks_by_key_type.ipv6[129 - cidr])
  end
  return ip_version.."_"..ip_netmask.."_"..ip_network_address
end

local function sync_status(err)
  if err then
    runtime.cache:safe_set("last_sync_error", err)
  else
    runtime.cache:safe_set("last_successful_sync", ngx.time())
    runtime.cache:delete("last_sync_error")
  end
end

local function decode_decisions(body, stream)
  local ok, decisions = pcall(decision_json.decode, body)
  if not ok then return nil end
  if not stream and decisions == cjson.null then return {} end
  if type(decisions) ~= "table" then return nil end
  if stream then
    if not body:match("^%s*{") then return nil end
    for _, name in ipairs({"new", "deleted"}) do
      local group = decisions[name]
      if group ~= nil and group ~= cjson.null and (type(group) ~= "table" or getmetatable(group) ~= cjson.array_mt) then return nil end
    end
    if decisions.new == nil and decisions.deleted == nil then return nil end
  elseif getmetatable(decisions) ~= cjson.array_mt then
    return nil
  end
  local groups = stream and {decisions.new or cjson.null, decisions.deleted or cjson.null} or {decisions}
  for i, group in ipairs(groups) do
    if group ~= cjson.null then
      for key, decision in pairs(group) do
        if type(key) ~= "number" or type(decision) ~= "table" or type(decision.scope) ~= "string"
          or type(decision.value) ~= "string" or type(decision.type) ~= "string" or #decision.type > 64
          or not decision_cache.identity(decision) then return nil end
        local scope = decision.scope:lower()
        if scope == "ip" or scope == "range" then
          if not item_to_string(decision.value, scope) then return nil end
          if (not stream or i == 1) and not decision_cache.duration(decision.duration) then return nil end
        end
      end
    end
  end
  return decisions
end

local function apply_decision(decision, deleted, key, max_ttl, generation)
  local scope = decision.scope:lower()
  if scope ~= "ip" and scope ~= "range" then return true end
  if runtime.conf["BOUNCING_ON_TYPE"] ~= "all" and runtime.conf["BOUNCING_ON_TYPE"] ~= decision.type then return true end
  local ttl = not deleted and decision_cache.duration(decision.duration) or nil
  if max_ttl then ttl = math.min(ttl, max_ttl) end
  local remediation = decision.type
  if remediation ~= "ban" and remediation ~= "captcha" then remediation = runtime.fallback end
  return runtime.decisions.update(key or item_to_string(decision.value, scope), decision, remediation, ttl, deleted, generation)
end

local function stream_query(premature)
  if premature or runtime.conf["API_URL"] == "" then return end
  -- Schedule before I/O/decoding so an invalid response cannot stop synchronization.
  local scheduled = ngx.timer.at(runtime.conf["UPDATE_FREQUENCY"], stream_query)
  if not scheduled then sync_status("Failed to schedule Local API synchronization") end
  local locked, lock_err = stream_lock.run(runtime.stream_lock_path, function()
    local last = runtime.cache:get("last_refresh")
    if last and ngx.time() - last < runtime.conf["UPDATE_FREQUENCY"] then return end
    local startup_request = runtime.cache:get("startup_request")
    local startup = runtime.cache:get("startup") == true or startup_request ~= runtime.cache:get("startup_completed")
    runtime.cache:safe_set("last_refresh", ngx.time())
    local res, err = get_remediation_http_request(runtime.conf["API_URL"] .. "/v1/decisions/stream?startup=" .. tostring(startup))
    if err or not res then
      sync_status("Local API request failed")
    elseif res.status ~= 200 then
      sync_status("Local API returned HTTP " .. tostring(res.status))
    else
      local decisions = decode_decisions(res.body, true)
      if not decisions then
        sync_status("Invalid Local API response")
      else
        local applied, generation = true, nil
        if startup then
          -- Publish a fresh snapshot only after all its enforcement records fit.
          generation = runtime.cache:incr("v2_generation_counter", 1, 0)
          if not generation then applied = false end
        end
        if applied then
          for _, group in ipairs({"deleted", "new"}) do
            if type(decisions[group]) == "table" then
              for _, decision in ipairs(decisions[group]) do
                if not apply_decision(decision, group == "deleted", nil, nil, generation) then applied = false; break end
              end
            end
            if not applied then break end
          end
        end
        if applied and generation then applied = runtime.cache:safe_set("v2_generation", generation) end
        if applied then
          if startup then
            -- Record exactly the captured request. A concurrent reload increments
            -- startup_request, so even a racing Boolean clear cannot erase it.
            runtime.cache:safe_set("startup_completed", startup_request)
            if startup_request == runtime.cache:get("startup_request") then runtime.cache:safe_set("startup", false) end
          end
          sync_status(nil)
        else
          runtime.cache:safe_set("startup", true)
          sync_status("Local decision cache is full")
        end
      end
    end
  end)
  if not locked and lock_err ~= "busy" then sync_status(lock_err) end
end

local function live_query(ip)
  local res, err = get_remediation_http_request(runtime.conf["API_URL"] .. "/v1/decisions?ip=" .. ip)
  if err or not res then
    sync_status("Local API request failed")
    return true, nil, "Local API request failed"
  end
  if res.status ~= 200 then
    err = "Local API returned HTTP " .. tostring(res.status)
    sync_status(err)
    return true, nil, err
  end
  local decisions = decode_decisions(res.body, false)
  if not decisions then
    sync_status("Invalid Local API response")
    return true, nil, "Invalid Local API response"
  end
  local key = item_to_string(ip, "ip")
  runtime.decisions.clear(key)
  local applied, remediation = true, nil
  local evidence = {source = "lapi", captured_at = ngx.time(), decisions = decision_cache.array(), metadata_available = true}
  for _, decision in ipairs(decisions) do
    local scope = decision.scope:lower()
    if (scope == "ip" or scope == "range") and (runtime.conf["BOUNCING_ON_TYPE"] == "all" or runtime.conf["BOUNCING_ON_TYPE"] == decision.type) then
      if not apply_decision(decision, false, key, runtime.conf["CACHE_EXPIRATION"]) then applied = false end
      local candidate = decision.type
      if candidate ~= "ban" and candidate ~= "captcha" then candidate = runtime.fallback end
      if not remediation or candidate == "ban" then remediation = candidate end
      local captured = {expires_at = ngx.time() + decision_cache.duration(decision.duration)}
      for _, name in ipairs({"id", "origin", "scenario", "type", "scope", "value"}) do
        local value = decision[name]
        if type(value) == "string" then captured[name] = value:sub(1, 512)
        elseif type(value) == "number" then captured[name] = value end
      end
      evidence.decisions[#evidence.decisions + 1] = captured
      evidence.matched_target = evidence.matched_target or decision.value
    end
  end
  if not remediation then runtime.cache:safe_set("v2_allowed_" .. key, true, runtime.conf["CACHE_EXPIRATION"]) end
  if applied then sync_status(nil) else sync_status("Local decision cache is full") end
  return remediation == nil, remediation, nil, evidence
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
  return runtime.captcha and runtime.captcha.GetTemplate()
end

function csmod.GetCaptchaBackendKey()
  return runtime.captcha and runtime.captcha.GetCaptchaBackendKey()
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
  local key_type, _, address = key:match("^([^_]+)_([^_]+)_(.+)$")
  local selected, evidence
  for _, mask in ipairs(iputils.netmasks_by_key_type[key_type]) do
    local target
    if key_type == "ipv4" then
      target = key_type .. "_" .. mask .. "_" .. iputils.ipv4_band(address, mask)
    else
      target = key_type .. "_" .. table.concat(mask, ":") .. "_" .. iputils.ipv6_band(address, mask)
    end
    local remediation, matched = runtime.decisions.get(target)
    if remediation then
      if not selected or remediation == "ban" then selected = remediation end
      if not evidence then evidence = matched else
        evidence.metadata_available = evidence.metadata_available and matched.metadata_available
        for _, decision in ipairs(matched.decisions) do evidence.decisions[#evidence.decisions + 1] = decision end
      end
    end
  end
  if selected then return false, selected, nil, evidence end
  if runtime.conf["MODE"] == "live" then
    if runtime.cache:get("v2_allowed_" .. key) then return true end
    return live_query(ip)
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

  local observation = {at = ngx.time(), status = res and res.status or 0}
  local source = "appsec"
  if err or not res then
    err, source = "AppSec request failed", "failure_policy"
  elseif res.status == 200 then
    ok, remediation = true, "allow"
  elseif res.status == 403 then
    local decoded, response = pcall(cjson.decode, res.body)
    if decoded and type(response) == "table" and type(response.action) == "string" then
      ok = false
      remediation = response.action
      status_code = type(response.http_status) == "number" and response.http_status or ngx.HTTP_FORBIDDEN
    else
      err, source = "Invalid AppSec response", "failure_policy"
    end
  else
    err, source = "AppSec returned HTTP " .. tostring(res.status), "failure_policy"
  end
  -- Only known action labels and the response status leave this boundary.
  local known = {allow = true, ban = true, captcha = true, challenge = true}
  observation.action = known[remediation] and remediation or "unknown"
  observation.error = err
  runtime.cache:safe_set("appsec_last_observed", cjson.encode(observation))
  local evidence = {source = source, captured_at = observation.at, decisions = decision_cache.array(), metadata_available = true,
    appsec = {status = observation.status, action = observation.action}}
  return ok, remediation, status_code, err, evidence

end

function csmod.Allow(ip, challengePrefix)
  if runtime.conf["ENABLED"] == "false" then
    return true, "disabled"
  end

  if runtime.conf["ENABLE_INTERNAL"] == "false" and ngx.req.is_internal() then
    return true, "internal"
  end

  if not challengePrefix or challengePrefix == "" then
    return false, "missing CrowdSec challenge namespace"
  end
  local challenge_cache = namespaced_cache(ngx.shared.crowdsec_cache, challengePrefix)

  local remediationSource = flag.BOUNCER_SOURCE
  local ret_code = nil

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
        ngx.log(ngx.ERR,  "whitelisted location: " .. uri_to_check)
      end
    end
  end

  local ok, remediation, err, evidence = csmod.allowIp(ip)
  if err ~= nil then
    ngx.log(ngx.ERR, "[Crowdsec] bouncer error: " .. err)
  end

  -- if the ip is now allowed, try to delete its captcha state in cache
  if ok == true then
    challenge_cache:delete("captcha_" .. ip)
  end

  -- check with appSec if the remediation component doesn't have decisions for the IP
  -- OR
  -- that user configured the remediation component to always check on the appSec (even if there is a decision for the IP)
  if ok == true or runtime.conf["ALWAYS_SEND_TO_APPSEC"] == true then
    if runtime.conf["APPSEC_ENABLED"] == true and ngx.var.no_appsec ~= "1" then
      local appsecOk, appsecRemediation, status_code, err, appsec_evidence = csmod.AppSecCheck(ip)
      if err ~= nil then
        ngx.log(ngx.ERR, "AppSec check: " .. err)
      end
      if appsecOk == false then
        ok = false
        remediationSource = flag.APPSEC_SOURCE
        remediation = appsecRemediation
        ret_code = status_code
        evidence = appsec_evidence
      end
    end
  end

  local captcha_ok = runtime.captcha ~= nil

  if runtime.fallback ~= "" then
    -- if remediation is not supported, fallback
    if remediation ~= "captcha" and remediation ~= "ban" then
      remediation = runtime.fallback
    end
  end

  -- An unusable captcha must deny even when the configured fallback is captcha.
  if remediation == "captcha" and not captcha_ok then
    remediation = "ban"
  end

  if captcha_ok then -- if captcha can be use (configuration is valid)
    -- we check if the IP need to validate its captcha before checking it against crowdsec local API
    local previous_uri, flags = challenge_cache:get("captcha_"..ip)
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
                  challenge_cache:delete("captcha_"..ip)
                else
                  local succ, err, forcible = challenge_cache:set("captcha_"..ip, previous_uri, runtime.conf["CAPTCHA_EXPIRATION"], bit.bor(flag.VALIDATED_STATE, source) )
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
      if remediation == "ban" then
        ngx.log(ngx.ALERT, "[Crowdsec] denied '" .. ip .. "' with '"..remediation.."' (by " .. flag.Flags[remediationSource] .. ")")
        -- ban.apply(ret_code)
        evidence = evidence or {source = "lapi", captured_at = ngx.time(), decisions = decision_cache.array(), metadata_available = false}
        evidence.remediation = "ban"
        return true, "denied", true, evidence
      end
      -- if the remediation is a captcha and captcha is well configured
      if remediation == "captcha" and captcha_ok and ngx.var.uri ~= "/favicon.ico" then
          local previous_uri, flags = challenge_cache:get("captcha_"..ip)
          local source, state_id, err = flag.GetFlags(flags)
          -- we check if the IP is already in cache for captcha and not yet validated
          if previous_uri == nil or state_id ~= flag.VALIDATED_STATE or remediationSource == flag.APPSEC_SOURCE then
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
              local succ, err, forcible = challenge_cache:set("captcha_"..ip, uri , 60, bit.bor(flag.VERIFY_STATE, remediationSource))
              if not succ then
                ngx.log(ngx.ERR, "failed to add key about captcha for ip '" .. ip .. "' in cache: "..err)
              end
              if forcible then
                ngx.log(ngx.ERR, "Lua shared dict (crowdsec cache) is full, please increase dict size in config")
              end
              ngx.log(ngx.ALERT, "[Crowdsec] denied '" .. ip .. "' with '"..remediation.."'")
              return
          end
      end
  end
  return true, "allow"
end


function csmod.Control(action, params)
  return require("crowdsec.control").run(runtime.conf, runtime.cache, action, params)
end

function csmod.ConnectionInfo()
  local conf = runtime.conf or {}
  local function safe_url(value)
    if type(value) ~= "string" then return "" end
    local scheme, authority, path = value:match("^([%a][%w+%.%-]*)://([^/?#]+)([^?#]*)")
    if not scheme or (scheme:lower() ~= "http" and scheme:lower() ~= "https") then return "" end
    authority = authority:match("([^@]+)$")
    if not authority or authority:find("[%s%c%%\\]") or path:find("[%s%c\\]") then return "" end
    if not authority:match("^[%w%.%-]+:?%d*$") and not authority:match("^%[[%x:%.]+%]:?%d*$") then return "" end
    return scheme:lower() .. "://" .. authority .. path
  end
  local info = {lapi_url = safe_url(conf.API_URL), appsec_url = safe_url(conf.APPSEC_URL), mode = conf.MODE,
    update_frequency = conf.UPDATE_FREQUENCY, cache_expiration = conf.CACHE_EXPIRATION,
    management_configured = type(conf.MANAGEMENT_LOGIN) == "string" and conf.MANAGEMENT_LOGIN ~= ""
      and type(conf.MANAGEMENT_PASSWORD) == "string" and conf.MANAGEMENT_PASSWORD ~= ""}
  if runtime.cache then
    info.last_successful_sync = runtime.cache:get("last_successful_sync")
    info.last_sync_error = runtime.cache:get("last_sync_error")
    local raw = runtime.cache:get("appsec_last_observed")
    if raw then
      local ok, observed = pcall(cjson.decode, raw)
      if ok then info.appsec_last_observed = observed end
    end
  end
  return info
end

-- Use it if you are able to close at shuttime
function csmod.close()
end

return csmod
