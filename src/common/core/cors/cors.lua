local class = require "middleclass"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"

local cors = class("cors", plugin)

local ngx = ngx
local HTTP_NO_CONTENT = ngx.HTTP_NO_CONTENT
local regex_match = utils.regex_match
local get_deny_status = utils.get_deny_status

-- Log debug messages only when LOG_LEVEL environment variable is set to "debug"
local function debug_log(logger, message)
    if os.getenv("LOG_LEVEL") == "debug" then
        logger:log(ngx.NOTICE, "[DEBUG] " .. message)
    end
end

function cors:initialize(ctx)
    -- Initialize the CORS plugin with configuration mappings and context setup.
    -- This function establishes the plugin instance, configures header mappings
    -- for both standard and preflight requests, and prepares the plugin state
    -- for processing CORS requests. Called once during plugin instantiation.
    
    plugin.initialize(self, "cors", ctx)
    
    debug_log(ngx, "CORS: Starting plugin initialization")
    debug_log(ngx, "CORS: Plugin name: cors")
    debug_log(ngx, "CORS: Context provided: " .. (ctx and "yes" or "no"))
    
    -- Configure header mappings for all CORS-related response headers
    -- These headers are sent with every CORS response when configured
    self.all_headers = {
        ["CORS_EXPOSE_HEADERS"] = "Access-Control-Expose-Headers",
        ["CROSS_ORIGIN_OPENER_POLICY"] = "Cross-Origin-Opener-Policy",
        ["CROSS_ORIGIN_EMBEDDER_POLICY"] = "Cross-Origin-Embedder-Policy",
        ["CROSS_ORIGIN_RESOURCE_POLICY"] = "Cross-Origin-Resource-Policy",
    }
    
    -- Configure header mappings specifically for preflight OPTIONS requests
    -- These headers inform the browser about allowed methods, headers, etc.
    self.preflight_headers = {
        ["CORS_MAX_AGE"] = "Access-Control-Max-Age",
        ["CORS_ALLOW_CREDENTIALS"] = "Access-Control-Allow-Credentials",
        ["CORS_ALLOW_METHODS"] = "Access-Control-Allow-Methods",
        ["CORS_ALLOW_HEADERS"] = "Access-Control-Allow-Headers",
    }
    
    debug_log(ngx, "CORS: Configured " .. 
              table.getn(self.all_headers) .. " standard headers")
    debug_log(ngx, "CORS: Configured " .. 
              table.getn(self.preflight_headers) .. " preflight headers")
    
    -- Log all configured header mappings
    for variable, header in pairs(self.all_headers) do
        debug_log(ngx, "CORS: Standard header mapping: " .. 
                  variable .. " -> " .. header)
    end
    
    for variable, header in pairs(self.preflight_headers) do
        debug_log(ngx, "CORS: Preflight header mapping: " .. 
                  variable .. " -> " .. header)
    end
    
    debug_log(ngx, "CORS: Plugin initialization completed successfully")
end

function cors:header()
    -- Process and set all CORS-related HTTP response headers based on request
    -- type and configuration. Handles both preflight OPTIONS requests and
    -- standard requests, setting appropriate headers for cross-origin access
    -- control, caching directives, and security policies. Returns processing
    -- status and descriptive message for logging and debugging purposes.
    
    debug_log(ngx, "CORS: Starting header processing phase")
    debug_log(ngx, "CORS: Request method: " .. 
              (self.ctx.bw.request_method or "unknown"))
    debug_log(ngx, "CORS: Request URI: " .. 
              (ngx.var.request_uri or "unknown"))
    
    -- Check if CORS processing is enabled in configuration
    if self.variables["USE_CORS"] ~= "yes" then
        debug_log(ngx, "CORS: CORS disabled in configuration, " ..
                  "USE_CORS = " .. (self.variables["USE_CORS"] or "nil"))
        return self:ret(true, "service doesn't use CORS")
    end
    
    debug_log(ngx, "CORS: CORS enabled, checking for Origin header")
    
    -- Skip processing if no Origin header is present (not a cross-origin request)
    if not self.ctx.bw.http_origin then
        debug_log(ngx, "CORS: No Origin header found in request")
        debug_log(ngx, "CORS: Request headers available: " ..
                  (ngx.var.http_host and "Host" or "") .. " " ..
                  (ngx.var.http_user_agent and "User-Agent" or ""))
        return self:ret(true, "origin header not present")
    end
    
    debug_log(ngx, "CORS: Processing cross-origin request")
    debug_log(ngx, "CORS: Origin header value: " .. 
              self.ctx.bw.http_origin)
    debug_log(ngx, "CORS: Server name: " .. 
              (self.ctx.bw.server_name or "unknown"))
    debug_log(ngx, "CORS: HTTPS configured: " .. 
              (self.ctx.bw.https_configured or "unknown"))
    
    -- Always include Vary header to prevent inappropriate caching
    -- This ensures browsers don't cache responses inappropriately across origins
    local ngx_header = ngx.header
    local vary = ngx_header.Vary
    
    debug_log(ngx, "CORS: Current Vary header: " .. 
              (vary and tostring(vary) or "none"))
    
    if vary then
        if type(vary) == "string" then
            ngx_header.Vary = { vary, "Origin" }
            debug_log(ngx, "CORS: Extended existing Vary header (string)")
        else
            table.insert(vary, "Origin")
            ngx_header.Vary = vary
            debug_log(ngx, "CORS: Extended existing Vary header (table)")
        end
    else
        ngx_header.Vary = "Origin"
        debug_log(ngx, "CORS: Set new Vary header to Origin")
    end

    -- Configure Access-Control-Allow-Origin header based on policy
    local allow_origin_config = self.variables["CORS_ALLOW_ORIGIN"]
    debug_log(ngx, "CORS: CORS_ALLOW_ORIGIN config: " .. 
              (allow_origin_config or "nil"))
    
    if allow_origin_config == "*" then
        ngx_header["Access-Control-Allow-Origin"] = "*"
        debug_log(ngx, "CORS: Set wildcard origin (allowing all)")
    elseif allow_origin_config == "self" then
        local self_origin
        if self.ctx.bw.https_configured == "yes" then
            self_origin = "https://" .. self.ctx.bw.server_name
        else
            self_origin = "http://" .. self.ctx.bw.server_name
        end
        ngx_header["Access-Control-Allow-Origin"] = self_origin
        debug_log(ngx, "CORS: Set self origin: " .. self_origin)
    else
        ngx_header["Access-Control-Allow-Origin"] = self.ctx.bw.http_origin
        debug_log(ngx, "CORS: Set requesting origin: " .. 
                  self.ctx.bw.http_origin)
    end
    
    -- Set all configured standard CORS headers
    local headers_set = 0
    for variable, header in pairs(self.all_headers) do
        local value = self.variables[variable]
        if value and value ~= "" then
            ngx_header[header] = value
            headers_set = headers_set + 1
            debug_log(ngx, "CORS: Set header " .. header .. " = " .. value)
        else
            debug_log(ngx, "CORS: Skipped empty header " .. header .. 
                      " (variable: " .. variable .. ")")
        end
    end
    
    debug_log(ngx, "CORS: Set " .. headers_set .. " standard headers total")
    
    -- Handle preflight OPTIONS requests with additional headers
    if self.ctx.bw.request_method == "OPTIONS" then
        debug_log(ngx, "CORS: Processing preflight OPTIONS request")
        debug_log(ngx, "CORS: Setting preflight-specific headers")
        
        local preflight_headers_set = 0
        for variable, header in pairs(self.preflight_headers) do
            if variable == "CORS_ALLOW_CREDENTIALS" then
                if self.variables["CORS_ALLOW_CREDENTIALS"] == "yes" then
                    ngx_header[header] = "true"
                    preflight_headers_set = preflight_headers_set + 1
                    debug_log(ngx, "CORS: Enabled credentials support")
                else
                    debug_log(ngx, "CORS: Credentials disabled")
                end
            else
                local value = self.variables[variable]
                if value and value ~= "" then
                    ngx_header[header] = value
                    preflight_headers_set = preflight_headers_set + 1
                    debug_log(ngx, "CORS: Set preflight header " .. 
                              header .. " = " .. value)
                else
                    debug_log(ngx, "CORS: Skipped empty preflight header " ..
                              header .. " (variable: " .. variable .. ")")
                end
            end
        end
        
        -- Set response metadata for preflight responses
        ngx_header["Content-Type"] = "text/html; charset=UTF-8"
        ngx_header["Content-Length"] = "0"
        
        debug_log(ngx, "CORS: Set " .. preflight_headers_set .. 
                  " preflight headers total")
        debug_log(ngx, "CORS: Set Content-Type and Content-Length")
        
        return self:ret(true, "edited headers for preflight request")
    end
    
    debug_log(ngx, "CORS: Completed standard request header processing")
    
    return self:ret(true, "edited headers for standard request")
end

function cors:access()
    -- Control request access based on CORS origin validation and policy
    -- enforcement. Validates requesting origins against configured patterns,
    -- denies unauthorized cross-origin requests when configured to do so,
    -- and handles preflight OPTIONS requests with appropriate status codes.
    -- Increments security metrics for monitoring and alerting purposes.
    
    debug_log(ngx, "CORS: Starting access control phase")
    debug_log(ngx, "CORS: Client IP: " .. 
              (ngx.var.remote_addr or "unknown"))
    debug_log(ngx, "CORS: Request method: " .. 
              (self.ctx.bw.request_method or "unknown"))
    debug_log(ngx, "CORS: Request URI: " .. 
              (ngx.var.request_uri or "unknown"))
    
    -- Skip access control if CORS is disabled
    if self.variables["USE_CORS"] ~= "yes" then
        debug_log(ngx, "CORS: CORS disabled, allowing all requests")
        debug_log(ngx, "CORS: USE_CORS setting: " .. 
                  (self.variables["USE_CORS"] or "nil"))
        return self:ret(true, "service doesn't use CORS")
    end

    debug_log(ngx, "CORS: CORS enabled, validating origin")
    debug_log(ngx, "CORS: Origin from request: " .. 
              (self.ctx.bw.http_origin or "none"))

    -- Determine the effective allowed origin pattern
    local allow_origin = self.variables["CORS_ALLOW_ORIGIN"]
    local original_allow_origin = allow_origin
    
    if allow_origin == "self" then
        if self.ctx.bw.https_configured == "yes" then
            allow_origin = "https://" .. self.ctx.bw.server_name
        else
            allow_origin = "http://" .. self.ctx.bw.server_name
        end
        debug_log(ngx, "CORS: Resolved 'self' to: " .. allow_origin)
    end
    
    debug_log(ngx, "CORS: Original allow_origin config: " .. 
              (original_allow_origin or "nil"))
    debug_log(ngx, "CORS: Effective allow_origin pattern: " .. 
              (allow_origin or "nil"))
    debug_log(ngx, "CORS: CORS_DENY_REQUEST setting: " .. 
              (self.variables["CORS_DENY_REQUEST"] or "nil"))

    -- Validate origin and deny unauthorized requests if configured
    local should_deny = (self.ctx.bw.http_origin and 
                        self.variables["CORS_DENY_REQUEST"] == "yes" and
                        allow_origin ~= "*")
    
    if should_deny then
        debug_log(ngx, "CORS: Checking origin against pattern")
        debug_log(ngx, "CORS: Testing: " .. self.ctx.bw.http_origin .. 
                  " against " .. allow_origin)
        
        local origin_matches = regex_match(self.ctx.bw.http_origin, allow_origin)
        
        debug_log(ngx, "CORS: Origin match result: " .. 
                  (origin_matches and "true" or "false"))
        
        if not origin_matches then
            debug_log(ngx, "CORS: Origin validation failed")
            debug_log(ngx, "CORS: Incrementing failed_cors metric")
            debug_log(ngx, "CORS: Preparing denial response")
            
            -- Record security metric for monitoring
            self:set_metric("counters", "failed_cors", 1)
            
            debug_log(ngx, "CORS: Returning denial status: " .. 
                      tostring(get_deny_status()))
            
            return self:ret(
                true,
                "origin " .. self.ctx.bw.http_origin .. 
                " is not allowed, denying access",
                get_deny_status(),
                nil,
                {
                    id = "origin",
                    origin = self.ctx.bw.http_origin,
                }
            )
        else
            debug_log(ngx, "CORS: Origin validation successful")
        end
    else
        if not self.ctx.bw.http_origin then
            debug_log(ngx, "CORS: No origin header, allowing request")
        elseif self.variables["CORS_DENY_REQUEST"] ~= "yes" then
            debug_log(ngx, "CORS: Denial disabled, allowing request")
        elseif allow_origin == "*" then
            debug_log(ngx, "CORS: Wildcard origin, allowing request")
        end
    end
    
    -- Handle preflight OPTIONS requests with 204 No Content response
    if (self.ctx.bw.request_method == "OPTIONS" and 
        self.ctx.bw.http_origin) then
        debug_log(ngx, "CORS: Processing preflight OPTIONS request")
        debug_log(ngx, "CORS: Returning 204 No Content status")
        debug_log(ngx, "CORS: Headers will be set in header phase")
        return self:ret(true, "preflight request", HTTP_NO_CONTENT)
    end
    
    debug_log(ngx, "CORS: Allowing standard cross-origin request")
    debug_log(ngx, "CORS: Access control phase completed successfully")
    
    return self:ret(true, "standard request")
end

return cors