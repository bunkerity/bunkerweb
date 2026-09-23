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
local challenge = require "crowdsec.lib.challenge"
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
-- shared dict. When those configurations target different Local APIs the caller
-- passes a short prefix so decisions, stream bookkeeping and captcha state cannot
-- bleed between them. Since the prefix became a hash of the Local API URL (port of dev
-- eda5fa2fb) EVERY deployment is prefixed, single-Local-API ones included: the prefix no
-- longer depends on how many endpoints there are, which is exactly what stopped adding an
-- endpoint from reshuffling the namespaces of all the others.
-- Two prefixes exist since the port of dev c54c49e7e: decision and stream keys keep the
-- Local API prefix bound to runtime.cache at init, while challenge state gets an explicit
-- per-service prefix handed to Allow -- several services can share one Local API, and a
-- captcha solved on one of them must not grant a pass on the next.
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

  -- captcha.New returns an instance now (port of dev c54c49e7e), so the usable/unusable
  -- answer is a field on this worker's runtime rather than a "captcha_ok" key in the shared
  -- dict. That key was the bug the arm below used to work around: an eviction, or a worker
  -- that started before init wrote it, read back nil instead of false.
  local captcha_instance, captcha_err = captcha.New(runtime.conf["SITE_KEY"], runtime.conf["SECRET_KEY"], runtime.conf["CAPTCHA_TEMPLATE_PATH"], runtime.conf["CAPTCHA_PROVIDER"])
  runtime.captcha = captcha_instance
  -- BunkerWeb exposes no SITE_KEY/SECRET_KEY, so this is the normal state here and must not be
  -- an error: a `captcha` remediation is delegated to BunkerWeb's antibot plugin instead (see
  -- delegate_captcha in Allow). Only an operator who did configure a provider gets told.
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
-- A direct authenticated read: no decision cache, stream timer, remediation or AppSec
-- application request can turn an unavailable Local API into a healthy result. Replaces the
-- Allow("127.0.0.1") the /crowdsec/ping handler used to make -- Allow now needs a per-service
-- challenge namespace the health check has no business inventing, and a cached decision for
-- 127.0.0.1 answered it without touching the Local API at all.
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
          -- Challenge state lives under a per-service prefix this timer does not know (it runs
          -- for one Local API, which several services can share), so deleting a decision clears
          -- that state on the IP's next allowed request -- see the `ok == true` arm in Allow.
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
  -- BunkerWeb local modification: the decoded decision travels back with the remediation so
  -- Allow() can name the scenario in the reason recorded on the report. Live queries only:
  -- a cache hit may retain decision evidence, but it cannot reconstruct this live response.
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

  local function finish(result_ok, action, status, response, failure, source)
    local observed = { at = ngx.time(), status = res and res.status or 0,
      action = ({ allow = true, ban = true, captcha = true, challenge = true })[action] and action or "unknown",
      error = failure }
    if runtime.cache.safe_set then
      runtime.cache:safe_set("appsec_last_observed", cjson.encode(observed))
    end
    local evidence = { source = source or "appsec", captured_at = observed.at,
      decisions = decision_cache.array(), metadata_available = true,
      appsec = { status = observed.status, action = observed.action } }
    return result_ok, action, status, response, failure, evidence
  end

  if err ~= nil or not res then
    ngx.log(ngx.ERR, "Fallback because of err: " .. tostring(err))
    return finish(ok, remediation, status_code, nil, err or "AppSec request failed", "failure_policy")
  end

  if res.status == 200 then
    ok = true
    remediation = "allow"
  elseif res.status == 403 then
    ok = false
    ngx.log(ngx.DEBUG, "Appsec body response: " .. tostring(res.body))
    -- Guarded: an unparsable 403 body used to raise out of AppSecCheck, through Allow, into
    -- helpers.lua's pcall -- which logs an ERR and serves the request UNCHECKED.
    local decoded, response = pcall(cjson.decode, res.body)
    if not decoded or type(response) ~= "table" or type(response.action) ~= "string" then
      ngx.log(ngx.ERR, "Unparsable AppSec response body, falling back: " .. tostring(response))
      return finish(false, runtime.conf["FALLBACK_REMEDIATION"], ngx.HTTP_FORBIDDEN, nil, nil, "failure_policy")
    end
    remediation = response.action
    if type(response.http_status) == "number" then
      ngx.log(ngx.DEBUG, "Got status code from APPSEC: " .. response.http_status)
      status_code = response.http_status
    else
      status_code = ngx.HTTP_FORBIDDEN
    end
    if remediation == "challenge" then
      -- CrowdSec 1.8 bot detection: the 403 carries the page to serve back on the
      -- original URI. user_body_content / user_headers / user_cookies are omitempty,
      -- so any of them can be missing -- Allow() decides what a missing body means.
      return finish(ok, remediation, status_code, {
        body = response.user_body_content,
        headers = response.user_headers,
        cookies = response.user_cookies,
      }, nil)
    end
  elseif res.status == 401 then
    ngx.log(ngx.ERR, "Unauthenticated request to APPSEC")
  else
    ngx.log(ngx.ERR, "Bad request to APPSEC (" .. res.status .. "): " .. res.body)
  end

  return finish(ok, remediation, status_code, nil, err, (res.status == 200 or res.status == 403) and "appsec" or "failure_policy")

end

-- @param ip string: the client address to judge
-- @param no_render boolean: report the remediation, never write a response body. Used by
--   SECURITY_MODE=detect, where a rendered challenge would replace the origin's response and
--   silently turn "detect" into "block" -- the dispatcher can suppress a deny STATUS, but not
--   a body already written.
-- @param antibot_provider string|nil: BunkerWeb's own antibot challenge provider to use for a
--   `captcha` remediation (CROWDSEC_CAPTCHA_PROVIDER, resolved per service by crowdsec:access()).
--   When set, a `captcha` is neither rendered here nor downgraded to FALLBACK_REMEDIATION: it is
--   handed back to the caller, which flags the request for the antibot plugin. nil or "no" keeps
--   the upstream behaviour.
-- @param challengePrefix string: per-service prefix for captcha and challenge state; decision
--   and stream keys instead use the Local API prefix bound to runtime.cache at init.
-- @return boolean ok, string msg, boolean banned, boolean served, table verdict,
--   string antibot_provider, table evidence
--   `served` means the response (AppSec challenge page, or captcha template) has already
--   been written and the caller must end the access phase with ngx.OK, not a deny status.
--   `verdict` describes the remediation for the report/ban reason -- `source` (lapi|appsec),
--   `action` (ban|captcha|challenge), `http_status`, and when LAPI metadata is available
--   `scenario`, `origin` and remaining `duration` (seconds). nil when nothing was remediated.
--   `antibot_provider` is echoed back on -- and only on -- a delegated `captcha`. It is the one
--   unambiguous signal of that path: every other return leaves it nil, so the caller never has to
--   infer "delegated" from a combination of the other four.
--   `evidence` carries bounded LAPI or AppSec details for reports; a failure-policy AppSec
--   fallback keeps its policy source here while the workflow verdict source stays `appsec`.
function csmod.Allow(ip, no_render, antibot_provider, challengePrefix)
  if runtime.conf["ENABLED"] == "false" then
    return true, "disabled"
  end

  if runtime.conf["ENABLE_INTERNAL"] == "false" and ngx.req.is_internal() then
    return true, "internal"
  end

  -- crowdsec:init() fills challenge_prefixes for exactly the scopes it fills bouncers for, and
  -- access() only reaches here with a bouncer, so this is an assertion rather than a live path.
  -- Refusing beats guessing: an empty prefix would put every service's challenge state back in
  -- one namespace, which is the bug this argument exists to close.
  if not challengePrefix or challengePrefix == "" then
    return false, "missing CrowdSec challenge namespace"
  end
  local challenge_cache = namespaced_cache(ngx.shared.crowdsec_cache, challengePrefix)

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
  local evidence = decision and decision.source == "lapi" and decision or nil
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
    local _, cached_flags = challenge_cache:get("captcha_" .. ip)
    local cached_source = flag.GetFlags(cached_flags)
    if cached_source ~= flag.APPSEC_SOURCE then
      challenge_cache:delete("captcha_" .. ip)
    end
  end

  -- check with appSec if the remediation component doesn't have decisions for the IP
  -- OR
  -- that user configured the remediation component to always check on the appSec (even if there is a decision for the IP)
  if ok == true or runtime.conf["ALWAYS_SEND_TO_APPSEC"] == true then
    if runtime.conf["APPSEC_ENABLED"] == true and ngx.var.no_appsec ~= "1" then
      local appsecOk, appsecRemediation, status_code, appsec_resp, appsec_err, appsec_evidence = csmod.AppSecCheck(ip)
      if appsec_err ~= nil then
        ngx.log(ngx.ERR, "AppSec check: " .. appsec_err)
      end
      if appsecOk == false then
        ok = false
        remediationSource = flag.APPSEC_SOURCE
        remediation = appsecRemediation
        ret_code = status_code
        appsec_response = appsec_resp
        evidence = appsec_evidence
      end
    end
  end

  -- Port of dev c54c49e7e: this worker's captcha instance, not a "captcha_ok" shared-dict key.
  -- The key came back nil rather than false whenever it had been evicted or the worker started
  -- before init wrote it, and nil ~= false silently skipped the fallback below.
  local captcha_ok = runtime.captcha ~= nil

  -- BunkerWeb local modification: a `captcha` remediation is rendered by BunkerWeb's own antibot
  -- plugin, never by the vendored CrowdSec captcha template -- BunkerWeb exposes no SITE_KEY /
  -- SECRET_KEY, so captcha.New() returns nil at init and `captcha_ok` is false on every request.
  -- Without this arm the block below rewrites every `captcha` decision into FALLBACK_REMEDIATION
  -- (`ban` in the shipped template) before anything downstream can see it, and the delegation
  -- could never happen at all.
  local delegate_captcha = antibot_provider ~= nil and antibot_provider ~= "" and antibot_provider ~= "no"

  if runtime.fallback ~= "" then
    -- if remediation is not supported, fallback
    if remediation ~= "captcha" and remediation ~= "ban" and remediation ~= "challenge" then
      remediation = runtime.fallback
    end
  end

  -- An unusable captcha must DENY, and outside the `runtime.fallback ~= ""` block on purpose
  -- (port of dev c54c49e7e): the rewrite used to target runtime.fallback from inside it, so
  -- FALLBACK_REMEDIATION=captcha left remediation == "captcha" with nothing able to render it --
  -- no arm under `if not ok` matched and the request fell out to `return true, "allow"`, served
  -- on a decision that asked for a captcha. `not delegate_captcha` is the BunkerWeb conjunct
  -- kept from the previous shape: when CROWDSEC_CAPTCHA_PROVIDER names a provider, the antibot
  -- plugin renders the challenge later in this same access phase, so "unusable here" is not
  -- "unusable at all".
  if remediation == "captcha" and not captcha_ok and not delegate_captcha then
    remediation = "ban"
  end

  -- BunkerWeb local modification: what was decided, in the shape crowdsec:access() records as
  -- the report/ban reason. Built here, after the fallback block settled `remediation`, and kept
  -- in step by the one arm below that rewrites it. Only on a remediation: the allow path is the
  -- hot path and must not allocate. A live query or cache hit may carry LAPI metadata;
  -- an AppSec verdict cannot, because its remediation did not come from a LAPI decision.
  local verdict
  if not ok then
    verdict = {
      source = remediationSource == flag.APPSEC_SOURCE and "appsec" or "lapi",
      action = remediation,
      http_status = ret_code,
    }
    if decision ~= nil and remediationSource ~= flag.APPSEC_SOURCE then
      if decision.source == "lapi" then decision = decision.decisions and decision.decisions[1] or {} end
      verdict.scenario = decision.scenario
      verdict.origin = decision.origin
      if type(decision.expires_at) == "number" then
        verdict.duration = tostring(math.max(0, math.floor(decision.expires_at - ngx.time()))) .. "s"
      end
    end
  end

  -- Before the captcha validation block on purpose: that block ends on ngx.redirect(), which
  -- writes a response just as much as a rendered page does.
  if no_render and not ok then
    return true,
      "not rendered, remediation was '" .. tostring(remediation) .. "'",
      remediation ~= "allow",
      nil,
      verdict,
      nil,
      evidence
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
        return true, "captcha delegated to the BunkerWeb antibot", false, false, verdict, antibot_provider, evidence
      end
      if remediation == "challenge" then
        -- CrowdSec 1.8 bot detection. The page is served exactly as CrowdSec sent it, on the
        -- original URI, with its own status and Set-Cookie, and the origin is never reached.
        if appsec_response ~= nil and type(appsec_response.body) == "string" and appsec_response.body ~= "" then
          ngx.log(ngx.ALERT, "[Crowdsec] challenged '" .. ip .. "' with 'appsec challenge' (by " .. flag.Flags[remediationSource] .. ")")
          challenge.apply(ret_code, appsec_response.body, appsec_response.headers, appsec_response.cookies)
          return true, "challenged", false, true, verdict, nil, evidence
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
        return true, "denied", true, nil, verdict, nil, evidence
      end
      -- if the remediation is a captcha and captcha is well configured
      if remediation == "captcha" and captcha_ok and ngx.var.uri ~= "/favicon.ico" then
          local previous_uri, flags = challenge_cache:get("captcha_"..ip)
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
              local succ, err, forcible = challenge_cache:set("captcha_"..ip, uri , 60, bit.bor(flag.VERIFY_STATE, remediationSource))
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
              return true, "CrowdSec captcha served", false, true, verdict, nil, evidence
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
