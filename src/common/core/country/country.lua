local cjson = require "cjson"
local class = require "middleclass"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"

local country = class("country", plugin)

local get_country = utils.get_country
local get_deny_status = utils.get_deny_status
local decode = cjson.decode
local encode = cjson.encode

-- Log debug messages only when LOG_LEVEL environment variable is set to "debug"
local function debug_log(logger, message)
    if os.getenv("LOG_LEVEL") == "debug" then
        logger:log(NOTICE, "[DEBUG] " .. message)
    end
end

-- Convert space-separated string to a set for efficient lookups
local function string_to_set(str)
    local set = {}
    if str and str ~= "" then
        for item in str:gmatch("%S+") do
            set[item] = true
        end
    end
    return set
end

-- Initialize the country plugin with context and precomputed country sets
function country:initialize(ctx)
    plugin.initialize(self, "country", ctx)
    
    debug_log(self.logger, "Initializing country plugin")
    
    # Initialize whitelist and blacklist sets once for performance
    self.whitelist = string_to_set(self.variables["WHITELIST_COUNTRY"])
    self.blacklist = string_to_set(self.variables["BLACKLIST_COUNTRY"])
    
    debug_log(self.logger, "Whitelist countries: " .. 
              (self.variables["WHITELIST_COUNTRY"] or "none"))
    debug_log(self.logger, "Blacklist countries: " .. 
              (self.variables["BLACKLIST_COUNTRY"] or "none"))
end

-- Main access control function that checks client IP against country rules
function country:access()
    debug_log(self.logger, "Starting country access check for IP: " .. 
              self.ctx.bw.remote_addr)
    
    # Don't go further if nothing is enabled
    if (self.variables["WHITELIST_COUNTRY"] == "" and 
        self.variables["BLACKLIST_COUNTRY"] == "") then
        debug_log(self.logger, "Country plugin not activated")
        return self:ret(true, "country not activated")
    end

    # Check if IP is in cache
    local _, data = self:is_in_cache(self.ctx.bw.remote_addr)
    if data then
        debug_log(self.logger, "Found IP in cache: " .. 
                  self.ctx.bw.remote_addr)
        data = decode(data)
        if data.result == "ok" then
            debug_log(self.logger, "Cache indicates IP is allowed, country: " .. 
                      data.country)
            return self:ret(
                true,
                "client IP "
                    .. self.ctx.bw.remote_addr
                    .. " is in country cache (not blacklisted, country = "
                    .. data.country
                    .. ")"
            )
        end
        debug_log(self.logger, "Cache indicates IP is blocked, country: " .. 
                  data.country)
        self:set_metric("counters", "failed_country", 1)
        return self:ret(
            true,
            "client IP "
                .. self.ctx.bw.remote_addr
                .. " is in country cache (blacklisted, country = "
                .. data.country
                .. ")",
            get_deny_status(),
            nil,
            {
                id = "country",
                country = data.country,
            }
        )
    end

    # Don't go further if IP is not global
    if not self.ctx.bw.ip_is_global then
        debug_log(self.logger, "IP is not global: " .. 
                  self.ctx.bw.remote_addr)
        local ok, err = self:add_to_cache(self.ctx.bw.remote_addr, 
                                          "unknown", "ok")
        if not ok then
            return self:ret(false, 
                           "error while adding ip to cache : " .. err)
        end
        return self:ret(true, "client IP " .. self.ctx.bw.remote_addr .. 
                       " is not global, skipping check")
    end

    # Get the country of client
    debug_log(self.logger, "Looking up country for IP: " .. 
              self.ctx.bw.remote_addr)
    local country_data, err = get_country(self.ctx.bw.remote_addr)
    if not country_data then
        debug_log(self.logger, "Failed to get country for IP: " .. 
                  self.ctx.bw.remote_addr .. ", error: " .. err)
        return self:ret(false, "can't get country of client IP " .. 
                       self.ctx.bw.remote_addr .. " : " .. err)
    end
    
    debug_log(self.logger, "Detected country: " .. country_data .. 
              " for IP: " .. self.ctx.bw.remote_addr)

    # Process whitelist first
    if self.variables["WHITELIST_COUNTRY"] ~= "" then
        debug_log(self.logger, "Checking whitelist for country: " .. 
                  country_data)
        if self.whitelist[country_data] then
            debug_log(self.logger, "Country " .. country_data .. 
                      " is whitelisted")
            local ok
            ok, err = self:add_to_cache(self.ctx.bw.remote_addr, 
                                        country_data, "ok")
            if not ok then
                return self:ret(false, 
                               "error while adding item to cache : " .. err)
            end
            return self:ret(
                true,
                "client IP " .. self.ctx.bw.remote_addr .. 
                " is whitelisted (country = " .. country_data .. ")"
            )
        end

        debug_log(self.logger, "Country " .. country_data .. 
                  " is not in whitelist, blocking")
        local ok
        ok, err = self:add_to_cache(self.ctx.bw.remote_addr, 
                                    country_data, "ko")
        if not ok then
            return self:ret(false, 
                           "error while adding item to cache : " .. err)
        end
        self:set_metric("counters", "failed_country", 1)
        return self:ret(
            true,
            "client IP " .. self.ctx.bw.remote_addr .. 
            " is not whitelisted (country = " .. country_data .. ")",
            get_deny_status(),
            nil,
            {
                id = "country",
                country = country_data,
            }
        )
    end

    # And then blacklist
    if self.variables["BLACKLIST_COUNTRY"] ~= "" then
        debug_log(self.logger, "Checking blacklist for country: " .. 
                  country_data)
        if self.blacklist[country_data] then
            debug_log(self.logger, "Country " .. country_data .. 
                      " is blacklisted, blocking")
            local ok
            ok, err = self:add_to_cache(self.ctx.bw.remote_addr, 
                                        country_data, "ko")
            if not ok then
                return self:ret(false, 
                               "error while adding item to cache : " .. err)
            end
            self:set_metric("counters", "failed_country", 1)
            return self:ret(
                true,
                "client IP " .. self.ctx.bw.remote_addr .. 
                " is blacklisted (country = " .. country_data .. ")",
                get_deny_status(),
                nil,
                {
                    id = "country",
                    country = country_data,
                }
            )
        end
    end

    # Country IP is not in blacklist
    debug_log(self.logger, "Country " .. country_data .. 
              " is allowed, caching result")
    local ok, err = self:add_to_cache(self.ctx.bw.remote_addr, 
                                      country_data, "ok")
    if not ok then
        return self:ret(false, "error while caching IP " .. 
                       self.ctx.bw.remote_addr .. " : " .. err)
    end
    return self:ret(
        true,
        "client IP " .. self.ctx.bw.remote_addr .. 
        " is not blacklisted (country = " .. country_data .. ")"
    )
end

-- Handle preread phase by delegating to access function
function country:preread()
    return self:access()
end

-- Check if an IP address is already cached with country information
function country:is_in_cache(ip)
    local ok, data = self.cachestore_local:get("plugin_country_" .. 
                                               self.ctx.bw.server_name .. ip)
    if not ok then
        return false, data
    end
    return true, data
end

-- Add IP address and country result to cache for performance optimization
function country:add_to_cache(ip, country_data, result)
    local ok, err = self.cachestore_local:set(
        "plugin_country_" .. self.ctx.bw.server_name .. ip,
        encode({ country = country_data, result = result }),
        86400
    )
    if not ok then
        return false, err
    end
    return true
end

return country