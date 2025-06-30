local class = require "middleclass"
local ipmatcher = require "resty.ipmatcher"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"

local blacklist = class("blacklist", plugin)

local ngx = ngx
local ERR = ngx.ERR
local INFO = ngx.INFO
local get_phase = ngx.get_phase
local has_variable = utils.has_variable
local get_deny_status = utils.get_deny_status
local get_rdns = utils.get_rdns
local get_asn = utils.get_asn
local regex_match = utils.regex_match
local get_variable = utils.get_variable
local deduplicate_list = utils.deduplicate_list
local ipmatcher_new = ipmatcher.new
local tostring = tostring
local open = io.open

-- Debug logging function that checks LOG_LEVEL environment variable
local function debug_log(logger, message)
    local log_level = os.getenv("LOG_LEVEL")
    if log_level == "debug" then
        logger:log(INFO, "[DEBUG] " .. message)
    end
end

-- Initialize the blacklist plugin with context
function blacklist:initialize(ctx)
    -- Call parent initialize
    plugin.initialize(self, "blacklist", ctx)
    debug_log(self.logger, "Blacklist plugin initializing for server: " .. 
             (self.ctx.bw.server_name or "unknown"))
    
    -- Decode lists
    if get_phase() ~= "init" and self:is_needed() then
        debug_log(self.logger, "Loading blacklist data from datastore")
        local datastore_lists, err = self.datastore:get(
            "plugin_blacklist_lists_" .. self.ctx.bw.server_name, true
        )
        if not datastore_lists then
            self.logger:log(ERR, err)
            self.lists = {}
            debug_log(self.logger, "Failed to load blacklist data, using empty lists")
        else
            self.lists = datastore_lists
            debug_log(self.logger, "Successfully loaded blacklist data from datastore")
        end
        local kinds = {
            ["IP"] = {},
            ["RDNS"] = {},
            ["ASN"] = {},
            ["USER_AGENT"] = {},
            ["URI"] = {},
            ["IGNORE_IP"] = {},
            ["IGNORE_RDNS"] = {},
            ["IGNORE_ASN"] = {},
            ["IGNORE_USER_AGENT"] = {},
            ["IGNORE_URI"] = {},
        }
        for kind, _ in pairs(kinds) do
            if not self.lists[kind] then
                self.lists[kind] = {}
            end
            for data in self.variables["BLACKLIST_" .. kind]:gmatch("%S+") do
                if data ~= "" then
                    table.insert(self.lists[kind], data)
                end
            end
            self.lists[kind] = deduplicate_list(self.lists[kind])
            if #self.lists[kind] > 0 then
                debug_log(self.logger, "Loaded " .. #self.lists[kind] .. 
                         " entries for " .. kind .. " from variables")
            end
        end
        debug_log(self.logger, "Blacklist initialization completed")
    else
        debug_log(self.logger, "Blacklist initialization skipped - not needed or init phase")
    end
end

-- Check if blacklist functionality is needed for current context
function blacklist:is_needed()
    -- Loading case
    if self.is_loading then
        debug_log(self.logger, "Blacklist not needed - loading phase")
        return false
    end
    -- Request phases (no default)
    if self.is_request and (self.ctx.bw.server_name ~= "_") then
        local needed = self.variables["USE_BLACKLIST"] == "yes"
        debug_log(self.logger, "Blacklist needed for request: " .. tostring(needed))
        return needed
    end
    -- Other cases : at least one service uses it
    local is_needed, err = has_variable("USE_BLACKLIST", "yes")
    if is_needed == nil then
        self.logger:log(ERR, "can't check USE_BLACKLIST variable : " .. err)
        debug_log(self.logger, "Error checking USE_BLACKLIST variable: " .. err)
    else
        debug_log(self.logger, "Blacklist needed (global check): " .. tostring(is_needed))
    end
    return is_needed
end

-- Initialize blacklist data from cache files
function blacklist:init()
    -- Check if init is needed
    if not self:is_needed() then
        debug_log(self.logger, "Blacklist init not needed")
        return self:ret(true, "init not needed")
    end

    debug_log(self.logger, "Starting blacklist initialization from cache files")

    -- Read blacklists
    local blacklists = {
        ["IP"] = {},
        ["RDNS"] = {},
        ["ASN"] = {},
        ["USER_AGENT"] = {},
        ["URI"] = {},
        ["IGNORE_IP"] = {},
        ["IGNORE_RDNS"] = {},
        ["IGNORE_ASN"] = {},
        ["IGNORE_USER_AGENT"] = {},
        ["IGNORE_URI"] = {},
    }

    local server_name, err = get_variable("SERVER_NAME", false)
    if not server_name then
        return self:ret(false, "can't get SERVER_NAME variable : " .. err)
    end

    -- Iterate over each kind and server
    local i = 0
    for key in server_name:gmatch("%S+") do
        debug_log(self.logger, "Loading blacklists for service: " .. key)
        for kind, _ in pairs(blacklists) do
            local file_path = "/var/cache/bunkerweb/blacklist/" .. key .. 
                             "/" .. kind .. ".list"
            debug_log(self.logger, "Checking file: " .. file_path)
            local f = open(file_path, "r")
            if f then
                local count = 0
                for line in f:lines() do
                    if line ~= "" then
                        table.insert(blacklists[kind], line)
                        i = i + 1
                        count = count + 1
                    end
                end
                f:close()
                debug_log(self.logger, "Loaded " .. count .. " entries from " .. 
                         kind .. ".list for " .. key)
            else
                debug_log(self.logger, "File not found: " .. file_path)
            end
            blacklists[kind] = deduplicate_list(blacklists[kind])
        end

        -- Load service specific ones into datastore
        local ok
        ok, err = self.datastore:set("plugin_blacklist_lists_" .. key, 
                                    blacklists, nil, true)
        if not ok then
            return self:ret(false, "can't store blacklist " .. key .. 
                          " list into datastore : " .. err)
        end

        self.logger:log(
            INFO,
            "successfully loaded " .. tostring(i) .. 
            " IP/network/rDNS/ASN/User-Agent/URI for the service: " .. key
        )

        i = 0
        blacklists = {
            ["IP"] = {},
            ["RDNS"] = {},
            ["ASN"] = {},
            ["USER_AGENT"] = {},
            ["URI"] = {},
            ["IGNORE_IP"] = {},
            ["IGNORE_RDNS"] = {},
            ["IGNORE_ASN"] = {},
            ["IGNORE_USER_AGENT"] = {},
            ["IGNORE_URI"] = {},
        }
    end
    return self:ret(true, "successfully loaded all " .. 
                  "IP/network/rDNS/ASN/User-Agent/URI")
end

-- Process access phase blacklist checks
function blacklist:access()
    -- Check if access is needed
    if not self:is_needed() then
        debug_log(self.logger, "Blacklist access check not needed")
        return self:ret(true, "access not needed")
    end
    
    debug_log(self.logger, "Starting blacklist access checks for IP: " .. 
             (self.ctx.bw.remote_addr or "unknown"))
    
    -- Check the caches
    local checks = {
        ["IP"] = "ip" .. self.ctx.bw.remote_addr,
    }
    if self.ctx.bw.http_user_agent then
        checks["UA"] = "ua" .. self.ctx.bw.http_user_agent
        debug_log(self.logger, "Will check User-Agent: " .. 
                 self.ctx.bw.http_user_agent)
    end
    if self.ctx.bw.uri then
        checks["URI"] = "uri" .. self.ctx.bw.uri
        debug_log(self.logger, "Will check URI: " .. self.ctx.bw.uri)
    end
    local already_cached = {
        ["IP"] = false,
        ["URI"] = false,
        ["UA"] = false,
    }
    for k, v in pairs(checks) do
        local ok, cached = self:is_in_cache(v)
        if not ok then
            self.logger:log(ERR, "error while checking cache : " .. cached)
            debug_log(self.logger, "Cache check error for " .. k .. ": " .. cached)
        elseif cached and cached ~= "ok" then
            debug_log(self.logger, "Found " .. k .. " in blacklist cache: " .. cached)
            local data = self:get_data(cached)
            self:set_metric("counters", "failed_" .. data.id, 1)
            return self:ret(
                true,
                k .. " is in cached blacklist (info : " .. cached .. ")",
                get_deny_status(),
                nil,
                data
            )
        end
        if ok and cached then
            already_cached[k] = true
            debug_log(self.logger, "Found " .. k .. " in cache as: " .. cached)
        else
            debug_log(self.logger, "No cache entry found for " .. k)
        end
    end
    -- Check lists
    if not self.lists then
        return self:ret(false, "lists is nil")
    end
    -- Perform checks
    for k, _ in pairs(checks) do
        if not already_cached[k] then
            debug_log(self.logger, "Performing live blacklist check for: " .. k)
            local ok, blacklisted = self:is_blacklisted(k)
            if ok == nil then
                self.logger:log(ERR, "error while checking if " .. k .. 
                              " is blacklisted : " .. blacklisted)
                debug_log(self.logger, "Error checking " .. k .. ": " .. blacklisted)
            else
                -- luacheck: ignore 421
                local ok, err = self:add_to_cache(self:kind_to_ele(k), 
                                                blacklisted)
                if not ok then
                    self.logger:log(ERR, "error while adding element to " .. 
                                  "cache : " .. err)
                    debug_log(self.logger, "Cache add error for " .. k .. ": " .. err)
                else
                    debug_log(self.logger, "Added " .. k .. " to cache with result: " .. 
                             blacklisted)
                end
                if blacklisted ~= "ok" then
                    debug_log(self.logger, "BLOCKED - " .. k .. " is blacklisted: " .. 
                             blacklisted)
                    local data = self:get_data(blacklisted)
                    self:set_metric("counters", "failed_" .. data.id, 1)
                    return self:ret(
                        true,
                        k .. " is blacklisted (info : " .. blacklisted .. ")",
                        get_deny_status(),
                        nil,
                        data
                    )
                else
                    debug_log(self.logger, "ALLOWED - " .. k .. " passed blacklist check")
                end
            end
        else
            debug_log(self.logger, "Skipping " .. k .. " check - already cached")
        end
    end

    -- Return
    debug_log(self.logger, "All blacklist checks passed - allowing request")
    return self:ret(true, "not blacklisted")
end

-- Handle preread phase (stream mode)
function blacklist:preread()
    return self:access()
end

-- Convert check kind to cache element key
function blacklist:kind_to_ele(kind)
    if kind == "IP" then
        return "ip" .. self.ctx.bw.remote_addr
    elseif kind == "UA" then
        return "ua" .. self.ctx.bw.http_user_agent
    elseif kind == "URI" then
        return "uri" .. self.ctx.bw.uri
    end
end

-- Check if element is in local cache
function blacklist:is_in_cache(ele)
    local ok, data = self.cachestore_local:get(
        "plugin_blacklist_" .. self.ctx.bw.server_name .. ele
    )
    if not ok then
        return false, data
    end
    return true, data
end

-- Add element to local cache with TTL
function blacklist:add_to_cache(ele, value)
    local ok, err = self.cachestore_local:set(
        "plugin_blacklist_" .. self.ctx.bw.server_name .. ele, value, 86400
    )
    if not ok then
        return false, err
    end
    return true
end

-- Dispatch blacklist check to appropriate handler
function blacklist:is_blacklisted(kind)
    if kind == "IP" then
        return self:is_blacklisted_ip()
    elseif kind == "URI" then
        return self:is_blacklisted_uri()
    elseif kind == "UA" then
        return self:is_blacklisted_ua()
    end
    return false, "unknown kind " .. kind
end

-- Check if IP address is blacklisted (includes rDNS and ASN checks)
function blacklist:is_blacklisted_ip()
    debug_log(self.logger, "Starting IP blacklist check for: " .. 
             self.ctx.bw.remote_addr)
    
    -- Check if IP is in ignore list
    debug_log(self.logger, "Checking IP against ignore list (" .. 
             #self.lists["IGNORE_IP"] .. " entries)")
    local ipm, err = ipmatcher_new(self.lists["IGNORE_IP"])
    if not ipm then
        debug_log(self.logger, "Error creating IP ignore matcher: " .. err)
        return nil, err
    end
    local match, err = ipm:match(self.ctx.bw.remote_addr)
    if err then
        debug_log(self.logger, "Error matching IP against ignore list: " .. err)
        return nil, err
    end
    if not match then
        -- Check if IP is in blacklist
        debug_log(self.logger, "IP not in ignore list, checking blacklist (" .. 
                 #self.lists["IP"] .. " entries)")
        ipm, err = ipmatcher.new(self.lists["IP"])
        if not ipm then
            debug_log(self.logger, "Error creating IP blacklist matcher: " .. err)
            return nil, err
        end
        match, err = ipm:match(self.ctx.bw.remote_addr)
        if err then
            debug_log(self.logger, "Error matching IP against blacklist: " .. err)
            return nil, err
        end
        if match then
            debug_log(self.logger, "IP BLOCKED - found in blacklist")
            return true, "ip"
        else
            debug_log(self.logger, "IP not found in blacklist")
        end
    else
        debug_log(self.logger, "IP found in ignore list - skipping further IP checks")
    end

    -- Check if rDNS is needed
    local check_rdns = true
    if self.variables["BLACKLIST_RDNS_GLOBAL"] == "yes" and 
       not self.ctx.bw.ip_is_global then
        check_rdns = false
        debug_log(self.logger, "Skipping rDNS check - IP is not global and " .. 
                 "BLACKLIST_RDNS_GLOBAL is enabled")
    end
    if check_rdns then
        debug_log(self.logger, "Starting rDNS check")
        -- Get rDNS
        -- luacheck: ignore 421
        local rdns_list, err = get_rdns(self.ctx.bw.remote_addr, 
                                      self.ctx, true)
        if rdns_list then
            debug_log(self.logger, "Found " .. #rdns_list .. " rDNS entries: " .. 
                     table.concat(rdns_list, ", "))
            -- Check if rDNS is in ignore list
            local ignore = false
            for _, rdns in ipairs(rdns_list) do
                for _, suffix in ipairs(self.lists["IGNORE_RDNS"]) do
                    if rdns:sub(-#suffix) == suffix then
                        ignore = true
                        debug_log(self.logger, "rDNS " .. rdns .. 
                                 " matches ignore suffix: " .. suffix)
                        break
                    end
                end
            end
            -- Check if rDNS is in blacklist
            if not ignore then
                debug_log(self.logger, "Checking rDNS against blacklist (" .. 
                         #self.lists["RDNS"] .. " entries)")
                for _, rdns in ipairs(rdns_list) do
                    for _, suffix in ipairs(self.lists["RDNS"]) do
                        if rdns:sub(-#suffix) == suffix then
                            debug_log(self.logger, "rDNS BLOCKED - " .. rdns .. 
                                     " matches blacklist suffix: " .. suffix)
                            return true, "rDNS " .. suffix
                        end
                    end
                end
                debug_log(self.logger, "rDNS check passed - no matches found")
            else
                debug_log(self.logger, "rDNS check skipped - found in ignore list")
            end
        else
            self.logger:log(ERR, "error while getting rdns : " .. err)
            debug_log(self.logger, "Error getting rDNS: " .. err)
        end
    end

    -- Check if ASN is in ignore list
    if self.ctx.bw.ip_is_global then
        debug_log(self.logger, "Starting ASN check for global IP")
        local asn, err = get_asn(self.ctx.bw.remote_addr)
        if not asn then
            self.logger:log(ngx.ERR, "can't get ASN of IP " .. 
                          self.ctx.bw.remote_addr .. " : " .. err)
            debug_log(self.logger, "Error getting ASN: " .. err)
        else
            debug_log(self.logger, "Found ASN: " .. tostring(asn))
            local ignore = false
            for _, ignore_asn in ipairs(self.lists["IGNORE_ASN"]) do
                if ignore_asn == tostring(asn) then
                    ignore = true
                    debug_log(self.logger, "ASN " .. tostring(asn) .. 
                             " found in ignore list")
                    break
                end
            end
            -- Check if ASN is in blacklist
            if not ignore then
                debug_log(self.logger, "Checking ASN against blacklist (" .. 
                         #self.lists["ASN"] .. " entries)")
                for _, bl_asn in ipairs(self.lists["ASN"]) do
                    if bl_asn == tostring(asn) then
                        debug_log(self.logger, "ASN BLOCKED - " .. tostring(asn) .. 
                                 " found in blacklist")
                        return true, "ASN " .. bl_asn
                    end
                end
                debug_log(self.logger, "ASN check passed - not in blacklist")
            else
                debug_log(self.logger, "ASN check skipped - found in ignore list")
            end
        end
    else
        debug_log(self.logger, "Skipping ASN check - IP is not global")
    end

    -- Not blacklisted
    debug_log(self.logger, "IP blacklist check completed - IP is allowed")
    return false, "ok"
end

-- Check if URI is blacklisted using regex patterns
function blacklist:is_blacklisted_uri()
    debug_log(self.logger, "Starting URI blacklist check for: " .. 
             (self.ctx.bw.uri or "unknown"))
    
    -- Check if URI is in ignore list
    debug_log(self.logger, "Checking URI against ignore list (" .. 
             #self.lists["IGNORE_URI"] .. " patterns)")
    local ignore = false
    for _, ignore_uri in ipairs(self.lists["IGNORE_URI"]) do
        if regex_match(self.ctx.bw.uri, ignore_uri) then
            ignore = true
            debug_log(self.logger, "URI matches ignore pattern: " .. ignore_uri)
            break
        end
    end
    -- Check if URI is in blacklist
    if not ignore then
        debug_log(self.logger, "Checking URI against blacklist (" .. 
                 #self.lists["URI"] .. " patterns)")
        for _, uri in ipairs(self.lists["URI"]) do
            if regex_match(self.ctx.bw.uri, uri) then
                debug_log(self.logger, "URI BLOCKED - matches pattern: " .. uri)
                return true, "URI " .. uri
            end
        end
        debug_log(self.logger, "URI check passed - no patterns matched")
    else
        debug_log(self.logger, "URI check skipped - found in ignore list")
    end
    -- URI is not blacklisted
    return false, "ok"
end

-- Check if User-Agent is blacklisted using regex patterns
function blacklist:is_blacklisted_ua()
    debug_log(self.logger, "Starting User-Agent blacklist check for: " .. 
             (self.ctx.bw.http_user_agent or "unknown"))
    
    -- Check if UA is in ignore list
    debug_log(self.logger, "Checking User-Agent against ignore list (" .. 
             #self.lists["IGNORE_USER_AGENT"] .. " patterns)")
    local ignore = false
    for _, ignore_ua in ipairs(self.lists["IGNORE_USER_AGENT"]) do
        if regex_match(self.ctx.bw.http_user_agent, ignore_ua) then
            ignore = true
            debug_log(self.logger, "User-Agent matches ignore pattern: " .. ignore_ua)
            break
        end
    end
    -- Check if UA is in blacklist
    if not ignore then
        debug_log(self.logger, "Checking User-Agent against blacklist (" .. 
                 #self.lists["USER_AGENT"] .. " patterns)")
        for _, ua in ipairs(self.lists["USER_AGENT"]) do
            if regex_match(self.ctx.bw.http_user_agent, ua) then
                debug_log(self.logger, "User-Agent BLOCKED - matches pattern: " .. ua)
                return true, "UA " .. ua
            end
        end
        debug_log(self.logger, "User-Agent check passed - no patterns matched")
    else
        debug_log(self.logger, "User-Agent check skipped - found in ignore list")
    end
    -- UA is not blacklisted
    return false, "ok"
end

-- Extract structured data from blacklist match information
-- luacheck: ignore 212
function blacklist:get_data(blacklisted)
    debug_log(self.logger, "Extracting data from blacklist match: " .. blacklisted)
    local data = {}
    if blacklisted:lower() == "ip" then
        data["id"] = "ip"
        debug_log(self.logger, "Extracted IP blacklist data")
    else
        local id, value = blacklisted:match("^(%w+) (.+)$")
        if id and value then
            id = id:lower()
            data["id"] = id
            data[id] = value
            debug_log(self.logger, "Extracted " .. id .. " blacklist data: " .. value)
        else
            debug_log(self.logger, "Failed to parse blacklist match data")
        end
    end
    return data
end

return blacklist