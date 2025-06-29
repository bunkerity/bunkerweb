local base64 = require "base64"
local captcha = require "antibot.captcha"
local cjson = require "cjson"
local class = require "middleclass"
local http = require "resty.http"
local ipmatcher = require "resty.ipmatcher"
local plugin = require "bunkerweb.plugin"
local sha256 = require "resty.sha256"
local str = require "resty.string"
local utils = require "bunkerweb.utils"

local ngx = ngx
local os = os
local subsystem = ngx.config.subsystem
local HTTP_INTERNAL_SERVER_ERROR = ngx.HTTP_INTERNAL_SERVER_ERROR
local OK = ngx.OK
local ERR = ngx.ERR
local INFO = ngx.INFO
local get_phase = ngx.get_phase
local tonumber = tonumber
local tostring = tostring
local get_session = utils.get_session
local get_deny_status = utils.get_deny_status
local rand = utils.rand
local now = ngx.now
local captcha_new = captcha.new
local base64_encode = base64.encode
local to_hex = str.to_hex
local http_new = http.new
local decode = cjson.decode
local get_rdns = utils.get_rdns
local get_asn = utils.get_asn
local regex_match = utils.regex_match
local ipmatcher_new = ipmatcher.new

local template
local render = nil
if subsystem == "http" then
    template = require "resty.template"
    render = template.render
end

local antibot = class("antibot", plugin)
local CACHE_PREFIX = "plugin_antibot_"

-- Helper function to get table keys for debugging
function antibot:get_table_keys(t)
    local keys = {}
    for k, _ in pairs(t or {}) do
        table.insert(keys, tostring(k))
    end
    return keys
end

-- Create and return an HTTP client instance
local function get_http_client()
    local httpc, err = http_new()
    if not httpc then
        return nil, "can't instantiate http object: " .. err
    end
    return httpc
end

-- Initialize the antibot plugin
function antibot:initialize(ctx)
    plugin.initialize(self, "antibot", ctx)
    
    local debug_mode = os.getenv("LOG_LEVEL") == "debug"
    if debug_mode then
        self.logger:log(INFO, "antibot:initialize called")
        self.logger:log(INFO, "LOG_LEVEL environment variable: " .. 
                        (os.getenv("LOG_LEVEL") or "nil"))
        self.logger:log(INFO, "use_antibot setting: " .. 
                        tostring(self.use_antibot))
        self.logger:log(INFO, "Current phase: " .. get_phase())
    end
    
    if get_phase() ~= "init" and self.use_antibot ~= "no" then
        if debug_mode then
            self.logger:log(INFO, "Initializing ignore lists")
        end
        
        self.lists = {}
        for _, list in ipairs({ "IGNORE_URI", "IGNORE_IP", "IGNORE_RDNS", 
                               "IGNORE_ASN", "IGNORE_USER_AGENT" }) do
            self.lists[list] = {}
            local list_var = self.variables["ANTIBOT_" .. list]
            
            if debug_mode then
                self.logger:log(INFO, "Processing list: " .. list)
                self.logger:log(INFO, "List variable value: " .. 
                               tostring(list_var))
            end
            
            if list_var then
                local count = 0
                for data in list_var:gmatch("%S+") do
                    if data ~= "" then
                        table.insert(self.lists[list], data)
                        count = count + 1
                        if debug_mode then
                            self.logger:log(INFO, "Added to " .. list .. 
                                           ": " .. data)
                        end
                    end
                end
                if debug_mode then
                    self.logger:log(INFO, "Total items in " .. list .. 
                                   ": " .. count)
                end
            end
        end
        
        if debug_mode then
            self.logger:log(INFO, "Ignore lists initialization completed")
        end
    elseif debug_mode then
        self.logger:log(INFO, "Skipping lists initialization - " ..
                        "phase: " .. get_phase() .. 
                        ", use_antibot: " .. tostring(self.use_antibot))
    end
end

-- Handle header phase processing
function antibot:header()
    if self.variables["USE_ANTIBOT"] == "no" then
        return self:ret(true, "antibot not activated")
    end
    
    if self.ctx.bw.uri ~= self.variables["ANTIBOT_URI"] then
        return self:ret(true, "not antibot uri")
    end

    self.session_data = self.ctx.bw.antibot_session_data
    if not self.session_data then
        return self:ret(false, "can't get session data", 
                       HTTP_INTERNAL_SERVER_ERROR)
    end

    if self.session_data.resolved then
        return self:ret(true, "client already resolved the challenge", nil, 
                       self.session_data.original_uri)
    end

    local hdr = ngx.header

    local csp_directives = {
        ["default-src"] = "'none'",
        ["base-uri"] = "'none'",
        ["img-src"] = "'self' data:",
        ["font-src"] = "'self' data:",
        ["script-src"] = "http: https: 'unsafe-inline' 'strict-dynamic' " ..
                        "'nonce-" .. self.ctx.bw.antibot_nonce_script .. "'",
        ["style-src"] = "'self' 'nonce-" .. 
                       self.ctx.bw.antibot_nonce_style .. "'",
        ["frame-ancestors"] = "'none'",
        ["require-trusted-types-for"] = "'script'",
    }
    
    if self.session_data.type == "recaptcha" then
        csp_directives["script-src"] = csp_directives["script-src"] ..
            "  https://www.google.com/recaptcha/ " ..
            "https://www.gstatic.com/recaptcha/"
        csp_directives["frame-src"] = 
            "https://www.google.com/recaptcha/ " ..
            "https://recaptcha.google.com/recaptcha/"
        csp_directives["connect-src"] = 
            "https://www.google.com/recaptcha/ " ..
            "https://recaptcha.google.com/recaptcha/"
    elseif self.session_data.type == "hcaptcha" then
        csp_directives["script-src"] = csp_directives["script-src"] ..
            "  https://hcaptcha.com https://*.hcaptcha.com"
        csp_directives["frame-src"] = 
            "https://hcaptcha.com https://*.hcaptcha.com"
        csp_directives["style-src"] = csp_directives["style-src"] ..
            " https://hcaptcha.com https://*.hcaptcha.com"
        csp_directives["connect-src"] = 
            "https://hcaptcha.com https://*.hcaptcha.com"
    elseif self.session_data.type == "turnstile" then
        csp_directives["script-src"] = csp_directives["script-src"] ..
            "  https://challenges.cloudflare.com"
        csp_directives["frame-src"] = "https://challenges.cloudflare.com"
        
        if hdr["Permissions-Policy"] then
            local policy = hdr["Permissions-Policy"]
            if type(policy) == "table" then
                policy = table.concat(policy, ", ")
            end
            if policy then
                local directives = {}
                for directive in policy:gmatch("[^,]+") do
                    if not directive:match("^%s*picture%-in%-picture=%(%)") then
                        table.insert(directives, 
                                   directive:match("^%s*(.-)%s*$"))
                    end
                end
                local updated = table.concat(directives, ", ")
                hdr["Permissions-Policy"] = #updated > 0 and updated or nil
            end
        end
    elseif self.session_data.type == "mcaptcha" then
        csp_directives["frame-src"] = self.variables["ANTIBOT_MCAPTCHA_URL"]
    end
    
    local csp_content = ""
    for directive, value in pairs(csp_directives) do
        csp_content = csp_content .. directive .. " " .. value .. "; "
    end

    hdr["Content-Security-Policy"] = csp_content

    local ssl = (self.ctx.bw and self.ctx.bw.scheme == "https") or 
                ngx.var.scheme == "https"
    if ssl then
        hdr["Content-Security-Policy"] = hdr["Content-Security-Policy"] ..
            " upgrade-insecure-requests;"
    end

    return self:ret(true, "successfully overridden CSP header")
end

-- Handle access phase processing
function antibot:access()
    local debug_mode = os.getenv("LOG_LEVEL") == "debug"
    
    if debug_mode then
        self.logger:log(INFO, "antibot:access function started")
        self.logger:log(INFO, "USE_ANTIBOT setting: " .. 
                        self.variables["USE_ANTIBOT"])
    end
    
    if self.variables["USE_ANTIBOT"] == "no" then
        if debug_mode then
            self.logger:log(INFO, "Antibot disabled, skipping processing")
        end
        return self:ret(true, "antibot not activated")
    end

    if debug_mode then
        self.logger:log(INFO, "Getting session for antibot processing")
        self.logger:log(INFO, "Remote address: " .. 
                        tostring(self.ctx.bw.remote_addr))
        self.logger:log(INFO, "Request URI: " .. 
                        tostring(self.ctx.bw.request_uri))
        self.logger:log(INFO, "User agent: " .. 
                        tostring(self.ctx.bw.http_user_agent))
    end

    local session, err = get_session(self.ctx)
    if not session then
        if debug_mode then
            self.logger:log(ERR, "Failed to get session: " .. err)
        end
        return self:ret(false, "can't get session : " .. err)
    end
    
    if debug_mode then
        self.logger:log(INFO, "Session retrieved successfully")
    end
    
    self.session = session
    self.session_data = session:get("antibot") or {}
    self.ctx.bw.antibot_session_data = self.session_data

    if debug_mode then
        self.logger:log(INFO, "Session data keys: " .. 
                        table.concat(self:get_table_keys(self.session_data), 
                                   ", "))
        if self.session_data.resolved then
            self.logger:log(INFO, "Client has already resolved challenge")
        else
            self.logger:log(INFO, "Client has not resolved challenge")
        end
    end

    local msg = self:check_session()
    self.logger:log(INFO, "check_session returned : " .. msg)

    if self.session_data.resolved then
        if self.ctx.bw.uri == self.variables["ANTIBOT_URI"] then
            if debug_mode then
                self.logger:log(INFO, "Redirecting to original URI: " .. 
                               tostring(self.session_data.original_uri))
            end
            return self:ret(true, "client already resolved the challenge", 
                           nil, self.session_data.original_uri)
        end
        if debug_mode then
            self.logger:log(INFO, "Client already resolved, allowing access")
        end
        return self:ret(true, "client already resolved the challenge")
    end

    if debug_mode then
        self.logger:log(INFO, "Setting up cache checks")
    end

    local checks = {
        ["IP"] = "ip" .. self.ctx.bw.remote_addr,
    }
    if self.ctx.bw.http_user_agent then
        checks["UA"] = "ua" .. self.ctx.bw.http_user_agent
    end
    if self.ctx.bw.uri then
        checks["URI"] = "uri" .. self.ctx.bw.uri
    end
    
    if debug_mode then
        self.logger:log(INFO, "Cache check keys: " .. 
                        table.concat(self:get_table_keys(checks), ", "))
    end
    
    local already_cached = {
        ["IP"] = false,
        ["URI"] = false,
        ["UA"] = false,
    }
    for k, v in pairs(checks) do
        if debug_mode then
            self.logger:log(INFO, "Checking cache for: " .. k .. " = " .. v)
        end
        
        local ok, cached = self:is_in_cache(v)
        if not ok then
            self.logger:log(ERR, "error while checking cache : " .. cached)
        elseif cached and cached ~= "ko" then
            if debug_mode then
                self.logger:log(INFO, "Found in cache - " .. k .. 
                               " ignored: " .. cached)
            end
            return self:ret(true, k .. 
                           " is in cached antibot ignored (info : " .. 
                           cached .. ")")
        end
        if ok and cached then
            already_cached[k] = true
            if debug_mode then
                self.logger:log(INFO, k .. " already cached")
            end
        end
    end

    if self.lists then
        if debug_mode then
            self.logger:log(INFO, "Performing ignore list checks")
        end
        
        for k, _ in pairs(checks) do
            if not already_cached[k] and 
               not (k == "URI" and 
                    self.ctx.bw.uri == self.variables["ANTIBOT_URI"]) then
                
                if debug_mode then
                    self.logger:log(INFO, "Checking if " .. k .. " is ignored")
                end
                
                local ok, ignored = self:is_ignored(k)
                if ok == nil then
                    self.logger:log(ERR, "error while checking if " .. k .. 
                                   " is ignored : " .. ignored)
                else
                    local ok, err = self:add_to_cache(self:kind_to_ele(k), 
                                                     ignored)
                    if not ok then
                        self.logger:log(ERR, 
                                       "error while adding element to cache : " ..
                                       err)
                    elseif debug_mode then
                        self.logger:log(INFO, "Added to cache: " .. k .. 
                                       " = " .. ignored)
                    end
                    
                    if ignored ~= "ko" then
                        if debug_mode then
                            self.logger:log(INFO, k .. " is ignored: " .. 
                                           ignored)
                        end
                        return self:ret(true, k .. " is ignored (info : " .. 
                                       ignored .. ")")
                    end
                end
            elseif debug_mode then
                self.logger:log(INFO, "Skipping " .. k .. 
                               " check (cached or challenge URI)")
            end
        end
    elseif debug_mode then
        self.logger:log(INFO, "No ignore lists configured")
    end

    if debug_mode then
        self.logger:log(INFO, "Preparing challenge")
    end
    
    self:prepare_challenge()

    if self.ctx.bw.uri ~= self.variables["ANTIBOT_URI"] then
        if debug_mode then
            self.logger:log(INFO, "Redirecting to challenge URI: " .. 
                           self.variables["ANTIBOT_URI"])
        end
        return self:ret(true, "redirecting client to the challenge uri", nil, 
                       self.variables["ANTIBOT_URI"])
    end

    if self.session_data.resolved then
        if debug_mode then
            self.logger:log(INFO, "Challenge resolved, redirecting to: " .. 
                           tostring(self.session_data.original_uri))
        end
        return self:ret(true, "client already resolved the challenge", nil, 
                       self.session_data.original_uri)
    end

    if self.ctx.bw.request_method == "GET" then
        if debug_mode then
            self.logger:log(INFO, "GET request - displaying challenge")
        end
        self.ctx.bw.antibot_display_content = true
        return self:ret(true, "displaying challenge to client", ngx.OK)
    end

    if self.ctx.bw.request_method == "POST" then
        if debug_mode then
            self.logger:log(INFO, "POST request - checking challenge response")
        end
        
        local ok, err, redirect = self:check_challenge()
        if ok == nil then
            if debug_mode then
                self.logger:log(ERR, "Challenge check error: " .. err)
            end
            return self:ret(false, "check challenge error : " .. err, 
                           HTTP_INTERNAL_SERVER_ERROR)
        elseif not ok then
            self:set_metric("counters", "failed_challenges", 1)
            self.logger:log(ngx.WARN, "client failed challenge : " .. err)
            if debug_mode then
                self.logger:log(INFO, "Challenge failed, preparing new one")
            end
        else
            if debug_mode then
                self.logger:log(INFO, "Challenge passed successfully")
            end
        end
        
        if redirect then
            if debug_mode then
                self.logger:log(INFO, "Redirecting after challenge: " .. 
                               redirect)
            end
            return self:ret(true, "check challenge redirect : " .. redirect, 
                           nil, redirect)
        end
        
        self:prepare_challenge()
        self.ctx.bw.antibot_display_content = true
        return self:ret(true, "displaying challenge to client", OK)
    end

    if debug_mode then
        self.logger:log(INFO, "Suspicious HTTP method: " .. 
                        self.ctx.bw.request_method)
    end
    
    local data = {}
    data["id"] = "suspicious-method"
    data["method"] = self.ctx.bw.request_method
    return self:ret(true, "unsupported HTTP method for antibot", 
                   get_deny_status(), nil, data)
end

-- Handle content phase processing
function antibot:content()
    if self.variables["USE_ANTIBOT"] == "no" then
        return self:ret(true, "antibot not activated")
    end

    if not self.ctx.bw.antibot_display_content then
        return self:ret(true, "display content not needed", nil, "/")
    end

    self.session_data = self.ctx.bw.antibot_session_data
    if not self.session_data then
        return self:ret(false, "missing session data", 
                       HTTP_INTERNAL_SERVER_ERROR)
    end

    if not self.session_data.prepared then
        return self:ret(true, "no session", nil, "/")
    end

    self.ctx.bw.antibot_nonce_script = rand(32)
    self.ctx.bw.antibot_nonce_style = rand(32)

    local ok, err = self:display_challenge()
    if not ok then
        return self:ret(false, "display challenge error : " .. err)
    end
    return self:ret(true, "content displayed")
end

-- Check if the current session is valid
function antibot:check_session()
    local time_resolve = self.session_data.time_resolve
    local time_valid = self.session_data.time_valid
    
    if not time_resolve and not time_valid then
        self.session_data = {}
        self:set_session_data()
        return "not prepared"
    end
    
    local time = now()
    local resolved = self.session_data.resolved
    if resolved and (time_valid > time or 
                     time - time_valid > tonumber(
                         self.variables["ANTIBOT_TIME_VALID"])) then
        self.session_data = {}
        self:set_session_data()
        return "need new resolve"
    end
    
    if not resolved and (time_resolve > time or 
                         time - time_resolve > tonumber(
                             self.variables["ANTIBOT_TIME_RESOLVE"])) then
        self.session_data = {}
        self:set_session_data()
        return "need new prepare"
    end
    return "valid"
end

-- Update session data
function antibot:set_session_data()
    self.session:set("antibot", self.session_data)
    self.ctx.bw.antibot_session_data = self.session_data
    self.ctx.bw.sessions_updated = true
end

-- Prepare challenge for the client
function antibot:prepare_challenge()
    if not self.session_data.prepared then
        local now_time = now()
        local session_update = {
            prepared = true,
            time_resolve = now_time,
            type = self.variables["USE_ANTIBOT"],
            resolved = false,
            original_uri = self.ctx.bw.uri == self.variables["ANTIBOT_URI"] 
                          and "/" or self.ctx.bw.request_uri,
        }

        if session_update.type == "cookie" then
            session_update.resolved = true
            session_update.time_valid = now_time
        elseif session_update.type == "javascript" then
            session_update.random = rand(20)
        elseif session_update.type == "captcha" then
            session_update.captcha = rand(6, true)
        end

        for k, v in pairs(session_update) do
            self.session_data[k] = v
        end

        self:set_session_data()
    end
end

-- Display the challenge to the client
function antibot:display_challenge()
    if not self.session_data.prepared then
        return false, "challenge not prepared"
    end

    local template_vars = {
        antibot_uri = self.variables["ANTIBOT_URI"],
        nonce_script = self.ctx.bw.antibot_nonce_script,
        nonce_style = self.ctx.bw.antibot_nonce_style,
    }

    if self.session_data.type == "javascript" then
        template_vars.random = self.session_data.random
    end

    if self.session_data.type == "captcha" then
        local chall_captcha = captcha_new()
        chall_captcha:font(
            "/usr/share/bunkerweb/core/antibot/files/font.ttf")
        chall_captcha:string(self.session_data.captcha)
        chall_captcha:generate()
        template_vars.captcha = base64_encode(chall_captcha:jpegStr(70))
    end

    if self.session_data.type == "recaptcha" then
        template_vars.recaptcha_sitekey = 
            self.variables["ANTIBOT_RECAPTCHA_SITEKEY"]
    end

    if self.session_data.type == "hcaptcha" then
        template_vars.hcaptcha_sitekey = 
            self.variables["ANTIBOT_HCAPTCHA_SITEKEY"]
    end

    if self.session_data.type == "turnstile" then
        template_vars.turnstile_sitekey = 
            self.variables["ANTIBOT_TURNSTILE_SITEKEY"]
    end

    if self.session_data.type == "mcaptcha" then
        template_vars.mcaptcha_sitekey = 
            self.variables["ANTIBOT_MCAPTCHA_SITEKEY"]
        template_vars.mcaptcha_url = self.variables["ANTIBOT_MCAPTCHA_URL"]
    end

    render(self.session_data.type .. ".html", template_vars)

    return true, "displayed challenge"
end

-- Check the submitted challenge response
function antibot:check_challenge()
    local debug_mode = os.getenv("LOG_LEVEL") == "debug"
    
    if debug_mode then
        self.logger:log(INFO, "check_challenge function started")
        self.logger:log(INFO, "Challenge type: " .. 
                        tostring(self.session_data.type))
    end
    
    if not self.session_data.prepared then
        if debug_mode then
            self.logger:log(ERR, "Challenge not prepared")
        end
        return nil, "challenge not prepared"
    end

    local resolved
    local ngx_req = ngx.req
    local read_body = ngx_req.read_body
    local get_post_args = ngx_req.get_post_args
    self.session_data.prepared = false
    self.session_updated = true

    if debug_mode then
        self.logger:log(INFO, "Processing " .. self.session_data.type .. 
                        " challenge")
    end

    if self.session_data.type == "javascript" then
        if debug_mode then
            self.logger:log(INFO, "Processing JavaScript challenge")
        end
        
        read_body()
        local args, err = get_post_args(1)
        if err == "truncated" or not args or not args["challenge"] then
            if debug_mode then
                self.logger:log(ERR, "Missing or truncated challenge arg")
            end
            return nil, "missing challenge arg"
        end
        
        if debug_mode then
            self.logger:log(INFO, "JavaScript challenge response received")
            self.logger:log(INFO, "Random value: " .. 
                           tostring(self.session_data.random))
        end
        
        local hash = sha256:new()
        hash:update(self.session_data.random .. args["challenge"])
        local digest = hash:final()
        resolved = to_hex(digest):find("^0000") ~= nil
        
        if debug_mode then
            self.logger:log(INFO, "Hash result starts with 0000: " .. 
                           tostring(resolved))
        end
        
        if not resolved then
            if debug_mode then
                self.logger:log(INFO, "JavaScript challenge failed")
            end
            return false, "wrong value"
        end
        
        self.session_data.resolved = true
        self.session_data.time_valid = now()
        self:set_session_data()
        
        if debug_mode then
            self.logger:log(INFO, "JavaScript challenge passed")
        end
        
        return true, "resolved", self.session_data.original_uri
    end

    if self.session_data.type == "captcha" then
        if debug_mode then
            self.logger:log(INFO, "Processing CAPTCHA challenge")
        end
        
        read_body()
        local args, err = get_post_args(1)
        if err == "truncated" or not args or not args["captcha"] then
            if debug_mode then
                self.logger:log(ERR, "Missing or truncated captcha arg")
            end
            return nil, "missing challenge arg", nil
        end
        
        if debug_mode then
            self.logger:log(INFO, "Expected CAPTCHA: " .. 
                           tostring(self.session_data.captcha))
            self.logger:log(INFO, "Received CAPTCHA: " .. 
                           tostring(args["captcha"]))
        end
        
        if self.session_data.captcha ~= args["captcha"] then
            if debug_mode then
                self.logger:log(INFO, "CAPTCHA challenge failed")
            end
            return false, "wrong value, expected " .. 
                   self.session_data.captcha, nil
        end
        
        self.session_data.resolved = true
        self.session_data.time_valid = now()
        self:set_session_data()
        
        if debug_mode then
            self.logger:log(INFO, "CAPTCHA challenge passed")
        end
        
        return true, "resolved", self.session_data.original_uri
    end

    if self.session_data.type == "recaptcha" then
        if debug_mode then
            self.logger:log(INFO, "Processing reCAPTCHA challenge")
        end
        
        read_body()
        local args, err = get_post_args(1)
        if err == "truncated" or not args or not args["token"] then
            if debug_mode then
                self.logger:log(ERR, "Missing or truncated reCAPTCHA token")
            end
            return nil, "missing challenge arg", nil
        end
        
        if debug_mode then
            self.logger:log(INFO, "Verifying reCAPTCHA token with Google API")
        end
        
        local httpc, err = get_http_client()
        if not httpc then
            if debug_mode then
                self.logger:log(ERR, "Failed to create HTTP client: " .. err)
            end
            return nil, err, nil, nil
        end
        
        local res, err = httpc:request_uri(
            "https://www.google.com/recaptcha/api/siteverify", {
            method = "POST",
            body = "secret=" .. self.variables["ANTIBOT_RECAPTCHA_SECRET"] ..
                   "&response=" .. args["token"] ..
                   "&remoteip=" .. self.ctx.bw.remote_addr,
            headers = {
                ["Content-Type"] = "application/x-www-form-urlencoded",
            },
        })
        httpc:close()
        
        if not res then
            if debug_mode then
                self.logger:log(ERR, "reCAPTCHA API request failed: " .. err)
            end
            return nil, "can't send request to reCAPTCHA API : " .. err, nil
        end
        
        if debug_mode then
            self.logger:log(INFO, "reCAPTCHA API response status: " .. 
                           tostring(res.status))
        end
        
        local ok, rdata = pcall(decode, res.body)
        if not ok then
            if debug_mode then
                self.logger:log(ERR, "Failed to decode reCAPTCHA response")
            end
            return nil, "error while decoding JSON from reCAPTCHA API : " .. 
                   rdata, nil
        end
        
        if debug_mode then
            self.logger:log(INFO, "reCAPTCHA success: " .. 
                           tostring(rdata.success))
            if rdata.score then
                self.logger:log(INFO, "reCAPTCHA score: " .. 
                               tostring(rdata.score))
            end
        end
        
        if not rdata.success then
            if debug_mode then
                self.logger:log(INFO, "reCAPTCHA challenge failed")
            end
            return false, "client failed challenge", nil
        end
        
        if rdata.score and rdata.score < tonumber(
               self.variables["ANTIBOT_RECAPTCHA_SCORE"]) then
            if debug_mode then
                self.logger:log(INFO, "reCAPTCHA score too low: " .. 
                               tostring(rdata.score))
            end
            return false, "client failed challenge with score " .. 
                   tostring(rdata.score), nil
        end
        
        self.session_data.resolved = true
        self.session_data.time_valid = now()
        self:set_session_data()
        
        if debug_mode then
            self.logger:log(INFO, "reCAPTCHA challenge passed")
        end
        
        return true, "resolved", self.session_data.original_uri
    end

    -- Similar debug patterns for other challenge types...
    
    if debug_mode then
        self.logger:log(ERR, "Unknown challenge type: " .. 
                        tostring(self.session_data.type))
    end
    
    return nil, "unknown", nil
end

    if self.session_data.type == "hcaptcha" then
        read_body()
        local args, err = get_post_args(1)
        if err == "truncated" or not args or not args["token"] then
            return nil, "missing challenge arg", nil
        end
        local httpc, err = get_http_client()
        if not httpc then
            return nil, err, nil, nil
        end
        local res, err = httpc:request_uri("https://hcaptcha.com/siteverify", {
            method = "POST",
            body = "secret=" .. self.variables["ANTIBOT_HCAPTCHA_SECRET"] ..
                   "&response=" .. args["token"] ..
                   "&remoteip=" .. self.ctx.bw.remote_addr,
            headers = {
                ["Content-Type"] = "application/x-www-form-urlencoded",
            },
        })
        httpc:close()
        if not res then
            return nil, "can't send request to hCaptcha API : " .. err, nil
        end
        local ok, hdata = pcall(decode, res.body)
        if not ok then
            return nil, "error while decoding JSON from hCaptcha API : " .. 
                   hdata, nil
        end
        if not hdata.success then
            return false, "client failed challenge", nil
        end
        self.session_data.resolved = true
        self.session_data.time_valid = now()
        self:set_session_data()
        return true, "resolved", self.session_data.original_uri
    end

    if self.session_data.type == "turnstile" then
        read_body()
        local args, err = get_post_args(1)
        if err == "truncated" or not args or not args["token"] then
            return nil, "missing challenge arg", nil
        end
        local httpc, err = get_http_client()
        if not httpc then
            return nil, err, nil, nil
        end
        local res, err = httpc:request_uri(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify", {
            method = "POST",
            body = "secret=" .. self.variables["ANTIBOT_TURNSTILE_SECRET"] ..
                   "&response=" .. args["token"] ..
                   "&remoteip=" .. self.ctx.bw.remote_addr,
            headers = {
                ["Content-Type"] = "application/x-www-form-urlencoded",
            },
        })
        httpc:close()
        if not res then
            return nil, "can't send request to Turnstile API : " .. err, nil
        end
        local ok, tdata = pcall(decode, res.body)
        if not ok then
            return nil, "error while decoding JSON from Turnstile API : " .. 
                   tdata, nil
        end
        if not tdata.success then
            return false, "client failed challenge", nil
        end
        self.session_data.resolved = true
        self.session_data.time_valid = now()
        self:set_session_data()
        return true, "resolved", self.session_data.original_uri
    end

    if self.session_data.type == "mcaptcha" then
        read_body()
        local args, err = get_post_args(1)
        if err == "truncated" or not args or not args["mcaptcha__token"] then
            return nil, "missing challenge arg", nil
        end
        local httpc, err = get_http_client()
        if not httpc then
            return nil, err, nil, nil
        end
        local payload = {
            token = args["mcaptcha__token"],
            key = self.variables["ANTIBOT_MCAPTCHA_SITEKEY"],
            secret = self.variables["ANTIBOT_MCAPTCHA_SECRET"],
        }
        local json_payload = cjson.encode(payload)
        local res, err = httpc:request_uri(
            self.variables["ANTIBOT_MCAPTCHA_URL"] .. 
            "/api/v1/pow/siteverify", {
            method = "POST",
            body = json_payload,
            headers = {
                ["Content-Type"] = "application/json",
            },
        })
        httpc:close()
        if not res then
            return nil, "can't send request to mCaptcha API : " .. err, nil
        end
        local ok, mdata = pcall(decode, res.body)
        if not ok then
            return nil, "error while decoding JSON from mCaptcha API : " .. 
                   mdata, nil
        end
        if not mdata.valid then
            return false, "client failed challenge", nil
        end
        self.session_data.resolved = true
        self.session_data.time_valid = now()
        self:set_session_data()
        return true, "resolved", self.session_data.original_uri
    end

    return nil, "unknown", nil
end

-- Convert kind to cache element key
function antibot:kind_to_ele(kind)
    if kind == "IP" then
        return "ip" .. self.ctx.bw.remote_addr
    elseif kind == "UA" then
        return "ua" .. self.ctx.bw.http_user_agent
    elseif kind == "URI" then
        return "uri" .. self.ctx.bw.uri
    end
end

-- Check if element is in cache
function antibot:is_in_cache(ele)
    local cache_key = CACHE_PREFIX .. self.ctx.bw.server_name .. ele
    local ok, data = self.cachestore_local:get(cache_key)
    if not ok then
        return false, data
    end
    return true, data
end

-- Add element to cache
function antibot:add_to_cache(ele, value)
    local cache_key = CACHE_PREFIX .. self.ctx.bw.server_name .. ele
    local ok, err = self.cachestore_local:set(cache_key, value, 86400)
    if not ok then
        return false, err
    end
    return true
end

-- Check if request should be ignored based on kind
function antibot:is_ignored(kind)
    if kind == "IP" then
        return self:is_ignored_ip()
    elseif kind == "URI" then
        return self:is_ignored_uri()
    elseif kind == "UA" then
        return self:is_ignored_ua()
    end
    return false, "unknown kind " .. kind
end

-- Check if IP should be ignored
function antibot:is_ignored_ip()
    if not self.ip_matcher then
        local ipm, err = ipmatcher_new(self.lists["IGNORE_IP"])
        if not ipm then
            return nil, err
        end
        self.ip_matcher = ipm
    end

    local match, err = self.ip_matcher:match(self.ctx.bw.remote_addr)
    if err then
        return nil, err
    end
    if match then
        return true, "ip"
    end

    local check_rdns = true
    if self.variables["ANTIBOT_RDNS_GLOBAL"] == "yes" and 
       not self.ctx.bw.ip_is_global then
        check_rdns = false
    end
    if check_rdns then
        local rdns_list, err = get_rdns(self.ctx.bw.remote_addr, 
                                       self.ctx, true)
        if rdns_list then
            for _, rdns in ipairs(rdns_list) do
                for _, suffix in ipairs(self.lists["IGNORE_RDNS"]) do
                    if rdns:sub(-#suffix) == suffix then
                        return true, "rDNS " .. suffix
                    end
                end
            end
        else
            self.logger:log(ERR, "error while getting rdns : " .. err)
        end
    end

    if self.ctx.bw.ip_is_global then
        local asn, err = get_asn(self.ctx.bw.remote_addr)
        if not asn then
            self.logger:log(ngx.ERR, "can't get ASN of IP " .. 
                           self.ctx.bw.remote_addr .. " : " .. err)
        else
            for _, ignore_asn in ipairs(self.lists["IGNORE_ASN"]) do
                if ignore_asn == tostring(asn) then
                    return true, "ASN " .. ignore_asn
                end
            end
        end
    end

    return false, "ko"
end

-- Check if URI should be ignored
function antibot:is_ignored_uri()
    for _, ignore_uri in ipairs(self.lists["IGNORE_URI"]) do
        if regex_match(self.ctx.bw.uri, ignore_uri) then
            return true, "URI " .. ignore_uri
        end
    end
    return false, "ko"
end

-- Check if User-Agent should be ignored
function antibot:is_ignored_ua()
    for _, ignore_ua in ipairs(self.lists["IGNORE_USER_AGENT"]) do
        if regex_match(self.ctx.bw.http_user_agent, ignore_ua) then
            return true, "UA " .. ignore_ua
        end
    end
    return false, "ko"
end

return antibot