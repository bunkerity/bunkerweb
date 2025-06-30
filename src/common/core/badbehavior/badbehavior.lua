local cjson = require "cjson"
local class = require "middleclass"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"

local badbehavior = class("badbehavior", plugin)

local ngx = ngx
local ERR = ngx.ERR
local WARN = ngx.WARN
local NOTICE = ngx.NOTICE
local worker = ngx.worker
local add_ban = utils.add_ban
local is_whitelisted = utils.is_whitelisted
local is_banned = utils.is_banned
local get_country = utils.get_country
local get_security_mode = utils.get_security_mode
local tostring = tostring
local time = os.time
local date = os.date
local encode = cjson.encode
local decode = cjson.decode

-- Debug logging helper function
-- Log debug messages only when LOG_LEVEL environment variable is set to "debug"
local function debug_log(logger, message)
    if os.getenv("LOG_LEVEL") == "debug" then
        logger:log(NOTICE, "[DEBUG] " .. message)
    end
end

-- Initialize the badbehavior plugin
-- Sets up the plugin with the given context
function badbehavior:initialize(ctx)
    plugin.initialize(self, "badbehavior", ctx)
    debug_log(self.logger, "badbehavior plugin initialized")
end

-- Main log function that handles bad behavior detection
-- Processes HTTP responses and increments counters for bad status codes
function badbehavior:log()
    debug_log(self.logger, "Starting log function for IP: " .. 
              (self.ctx.bw.remote_addr or "unknown"))
    
    -- Check if we are whitelisted
    if is_whitelisted(self.ctx) then
        debug_log(self.logger, "Client is whitelisted, skipping bad behavior check")
        return self:ret(true, "client is whitelisted")
    end
    
    -- Check if bad behavior is activated
    if self.variables["USE_BAD_BEHAVIOR"] ~= "yes" then
        debug_log(self.logger, "Bad behavior feature is not activated")
        return self:ret(true, "bad behavior not activated")
    end
    
    -- Check if we have a bad status code
    local current_status = tostring(ngx.status)
    if not self.variables["BAD_BEHAVIOR_STATUS_CODES"]:match(current_status) then
        debug_log(self.logger, "Status code " .. current_status .. 
                  " is not in bad behavior list")
        return self:ret(true, "not increasing counter")
    end
    
    debug_log(self.logger, "Bad status code detected: " .. current_status)
    
    -- Check if we are already banned
    if is_banned(self.ctx.bw.remote_addr, self.ctx.bw.server_name) then
        debug_log(self.logger, "IP is already banned")
        return self:ret(true, "already banned")
    end
    
    -- Get security mode
    local security_mode = get_security_mode(self.ctx)
    debug_log(self.logger, "Security mode: " .. (security_mode or "unknown"))
    
    -- Get country
    local country = "local"
    local err
    if self.ctx.bw.ip_is_global then
        country, err = get_country(self.ctx.bw.remote_addr)
        if not country then
            country = "unknown"
            self.logger:log(ERR, "can't get country code " .. err)
        end
    end
    debug_log(self.logger, "Country detected: " .. country)
    
    -- Add incr operation so timer can manage it
    local status = tostring(ngx.status)
    local ban_scope = self.variables["BAD_BEHAVIOR_BAN_SCOPE"]
    local ban_time = tonumber(self.variables["BAD_BEHAVIOR_BAN_TIME"])
    
    debug_log(self.logger, "Adding increment operation with ban_scope: " .. 
              ban_scope .. ", ban_time: " .. ban_time)

    local ok, err = self.datastore.dict:rpush(
        "plugin_badbehavior_incr",
        encode({
            ip = self.ctx.bw.remote_addr,
            count_time = tonumber(self.variables["BAD_BEHAVIOR_COUNT_TIME"]),
            ban_time = ban_time,
            threshold = tonumber(self.variables["BAD_BEHAVIOR_THRESHOLD"]),
            use_redis = self.use_redis,
            server_name = self.ctx.bw.server_name,
            security_mode = security_mode,
            country = country,
            timestamp = time(date("!*t")),
            status = status,
            ban_scope = ban_scope,
        })
    )
    if not ok then
        debug_log(self.logger, "Failed to add increment operation: " .. err)
        return self:ret(false, "can't add incr operation : " .. err)
    end
    
    debug_log(self.logger, "Successfully added increment operation")
    
    self:set_metric("counters", "status_" .. status, 1)
    self:set_metric("counters", "ip_" .. self.ctx.bw.remote_addr, 1)
    self:set_metric("counters", "url_" .. self.ctx.bw.request_uri, 1)
    self:set_metric("tables", "increments", {
        date = self.ctx.bw.start_time,
        id = self.ctx.bw.request_id,
        ip = self.ctx.bw.remote_addr,
        server_name = self.ctx.bw.server_name,
        status = status,
        method = self.ctx.bw.request_method,
        url = self.ctx.bw.request_uri,
    })
    
    debug_log(self.logger, "Metrics updated for bad behavior detection")
    return self:ret(true, "success")
end

-- Default log function for HTTP phase
-- Calls the main log function
function badbehavior:log_default()
    debug_log(self.logger, "log_default called")
    return self:log()
end

-- Stream log function for TCP/UDP phase
-- Calls the main log function
function badbehavior:log_stream()
    debug_log(self.logger, "log_stream called")
    return self:log()
end

-- Timer function that processes increment and decrement operations
-- Handles ban logic and counter management, runs only on worker 0
function badbehavior:timer()
    -- Only execute on worker 0
    if worker.id() ~= 0 then
        debug_log(self.logger, "Skipping timer on worker " .. worker.id())
        return self:ret(true, "skipped")
    end
    
    debug_log(self.logger, "Starting timer function on worker 0")

    -- Our ret values
    local ret = true
    local ret_err = "success"

    -- List of counters
    local counters = {}
    local timestamp = time(date("!*t"))

    -- Loop on decrease operations
    local decr_len, decr_len_err = self.datastore:llen(
        "plugin_badbehavior_decr")
    if decr_len == nil then
        debug_log(self.logger, "Failed to get decr list length: " .. decr_len_err)
        return self:ret(false, "can't get decr list length : " .. 
                        decr_len_err)
    end
    
    debug_log(self.logger, "Processing " .. decr_len .. " decrease operations")
    
    for i = 1, decr_len do
        -- Pop operation
        local decr, decr_err = self.datastore:lpop("plugin_badbehavior_decr")
        if decr == nil then
            debug_log(self.logger, "Failed to pop decr operation " .. i .. 
                      ": " .. decr_err)
            return self:ret(false, "can't get decr list element : " .. 
                            decr_err)
        end
        decr = decode(decr)
        debug_log(self.logger, "Processing decr for IP: " .. decr["ip"] .. 
                  " at timestamp: " .. decr["timestamp"])
        
        if timestamp > decr["timestamp"] then
            -- Call decrease
            local ok, err = self:decrease(
                decr["ip"],
                decr["count_time"],
                decr["threshold"],
                decr["use_redis"],
                decr["server_name"],
                decr["status"],
                decr["old_counter"],
                decr["ban_scope"]
            )
            if not ok then
                ret = false
                ret_err = "can't decrease counter : " .. err
                debug_log(self.logger, "Decrease failed: " .. err)
            else
                debug_log(self.logger, "Successfully decreased counter for IP: " .. 
                          decr["ip"])
            end
        else
            -- Add back to list
            local ok, err = self.datastore.dict:rpush(
                "plugin_badbehavior_decr", encode(decr))
            if not ok then
                ret = false
                ret_err = "can't add decr list element : " .. err
                debug_log(self.logger, "Failed to re-add decr operation: " .. err)
            else
                debug_log(self.logger, "Re-added decr operation for later processing")
            end
        end
    end

    -- Loop on increase operations
    local incr_len, incr_err = self.datastore:llen("plugin_badbehavior_incr")
    if not incr_len then
        debug_log(self.logger, "Failed to get incr list length: " .. incr_err)
        return self:ret(false, "can't get incr list length : " .. incr_err)
    end
    
    debug_log(self.logger, "Processing " .. incr_len .. " increase operations")
    
    for i = 1, incr_len do
        local incr_json, lpop_err = self.datastore:lpop(
            "plugin_badbehavior_incr")
        if not incr_json then
            debug_log(self.logger, "Failed to pop incr operation " .. i .. 
                      ": " .. lpop_err)
            return self:ret(false, "can't get incr list element : " .. 
                            lpop_err)
        end
        local incr = decode(incr_json)
        local ip = incr.ip
        local count_time = incr.count_time
        local ban_time = incr.ban_time
        local threshold = incr.threshold
        local use_redis = incr.use_redis
        local server_name = incr.server_name
        local security_mode = incr.security_mode
        local country = incr.country
        local status = incr.status
        local ban_scope = incr.ban_scope or "global"
        
        debug_log(self.logger, "Processing incr for IP: " .. ip .. 
                  " with threshold: " .. threshold)
        
        local counter, counter_err = self:increase(
            ip,
            count_time,
            ban_time,
            threshold,
            use_redis,
            server_name,
            security_mode,
            country,
            status,
            ban_scope
        )
        if not counter then
            ret = false
            ret_err = "can't increase counter : " .. counter_err
            debug_log(self.logger, "Increase failed for IP " .. ip .. ": " .. 
                      counter_err)
        else
            debug_log(self.logger, "Counter increased for IP " .. ip .. 
                      " to: " .. counter)
            
            -- Add decrease later
            local decr_payload = {
                ip = ip,
                old_counter = counter,
                count_time = count_time,
                threshold = threshold,
                use_redis = use_redis,
                timestamp = timestamp + count_time,
                server_name = server_name,
                status = status,
                ban_scope = ban_scope,
            }
            local ok, err = self.datastore.dict:rpush(
                "plugin_badbehavior_decr", encode(decr_payload))
            if not ok then
                ret = false
                ret_err = "can't add decr list element : " .. err
                debug_log(self.logger, "Failed to add decr payload: " .. err)
            else
                debug_log(self.logger, "Added decr payload for future processing")
            end
            -- Save counter info indexed by "ip_serverName"
            local counter_key = ip
            if ban_scope == "service" then
                counter_key = server_name .. "_" .. ip
            end
            counters[counter_key] = {
                ip = ip,
                counter = counter,
                count_time = count_time,
                ban_time = ban_time,
                threshold = threshold,
                use_redis = use_redis,
                server_name = server_name,
                security_mode = security_mode,
                country = country,
                status = status,
                ban_scope = ban_scope,
            }
        end
    end

    -- Add bans if needed
    local bans_processed = 0
    for _, data in pairs(counters) do
        debug_log(self.logger, "Checking ban threshold for IP " .. data.ip .. 
                  ": " .. data.counter .. "/" .. data.threshold)
        
        if data.counter >= data.threshold then
            bans_processed = bans_processed + 1
            if data.security_mode == "block" then
                local ok, err = add_ban(data.ip, "bad behavior", 
                                        data.ban_time, data.server_name, 
                                        data.country, data.ban_scope)
                if not ok then
                    ret = false
                    ret_err = "can't save ban : " .. err
                    debug_log(self.logger, "Failed to add ban for IP " .. data.ip .. 
                              ": " .. err)
                else
                    local ban_duration = data.ban_time == 0 and 
                        "permanently" or "for " .. data.ban_time .. "s"
                    debug_log(self.logger, "Successfully banned IP " .. data.ip .. 
                              " " .. ban_duration)
                    self.logger:log(
                        WARN,
                        string.format(
                            "IP %s is banned %s (%s/%s) on server %s " ..
                            "with scope %s",
                            data.ip,
                            ban_duration,
                            tostring(data.counter),
                            tostring(data.threshold),
                            data.server_name,
                            data.ban_scope
                        )
                    )
                end
            else
                local detection_msg = data.ban_time == 0 and 
                    "permanently" or "for " .. data.ban_time .. "s"
                debug_log(self.logger, "Detected ban condition for IP " .. data.ip .. 
                          " but not blocking due to security mode")
                self.logger:log(
                    WARN,
                    string.format(
                        "detected IP %s ban %s (%s/%s) on server %s " ..
                        "with scope %s",
                        data.ip,
                        detection_msg,
                        tostring(data.counter),
                        tostring(data.threshold),
                        data.server_name,
                        data.ban_scope
                    )
                )
            end
        end
    end
    
    debug_log(self.logger, "Timer completed. Processed " .. bans_processed .. 
              " ban decisions")
    return self:ret(ret, ret_err)
end

-- Increase counter for an IP address
-- Increments the bad behavior counter for the given IP and parameters
-- luacheck: ignore 212
function badbehavior:increase(
    ip,
    count_time,
    ban_time,
    threshold,
    use_redis,
    server_name,
    security_mode,
    country,
    status,
    ban_scope
)
    debug_log(self.logger, "Increasing counter for IP: " .. ip .. 
              " with ban_scope: " .. ban_scope)
    
    -- Declare counter
    local counter = false
    local key_suffix = ip
    if ban_scope == "service" then
        key_suffix = server_name .. "_" .. ip
    end

    -- Redis case
    if use_redis then
        debug_log(self.logger, "Using Redis for counter increase")
        local redis_counter, err = self:redis_increase(ip, count_time, 
                                                       ban_time, server_name, 
                                                       ban_scope)
        if not redis_counter then
            debug_log(self.logger, "Redis increase failed, falling back to local: " .. 
                      err)
            self.logger:log(ERR, 
                "(increase) redis_increase failed, falling back to local : " .. 
                err)
        else
            counter = redis_counter
            debug_log(self.logger, "Redis counter increased to: " .. counter)
        end
    end
    
    -- Local case
    if not counter then
        debug_log(self.logger, "Using local datastore for counter increase")
        local local_counter, err = self.datastore:get(
            "plugin_badbehavior_count_" .. key_suffix)
        if not local_counter and err ~= "not found" then
            debug_log(self.logger, "Failed to get local counter: " .. err)
            self.logger:log(ERR, 
                "(increase) can't get counts from the datastore : " .. err)
        end
        if local_counter == nil then
            local_counter = 0
        end
        counter = local_counter + 1
        debug_log(self.logger, "Local counter increased from " .. local_counter .. 
                  " to " .. counter)
    end
    
    -- Store local counter
    local ok, err = self.datastore:set("plugin_badbehavior_count_" .. 
                                       key_suffix, counter, count_time)
    if not ok then
        debug_log(self.logger, "Failed to store local counter: " .. err)
        self.logger:log(ERR, 
            "(increase) can't save counts to the datastore : " .. err)
        return false, err
    end
    
    debug_log(self.logger, "Successfully stored counter value: " .. counter)
    
    self.logger:log(
        NOTICE,
        "increased counter for IP "
            .. ip
            .. " ("
            .. tostring(counter)
            .. "/"
            .. tostring(threshold)
            .. ") on server "
            .. server_name
            .. " (status "
            .. status
            .. ", scope "
            .. ban_scope
            .. ")"
    )
    return counter, "success"
end

-- Decrease counter for an IP address
-- Decrements the bad behavior counter for the given IP and parameters
function badbehavior:decrease(ip, count_time, threshold, use_redis, 
                              server_name, status, old_counter, ban_scope)
    debug_log(self.logger, "Decreasing counter for IP: " .. ip .. 
              " from old_counter: " .. old_counter)
    
    -- Declare counter
    local counter = false
    local key_suffix = ip
    if ban_scope == "service" then
        key_suffix = server_name .. "_" .. ip
    end

    -- Redis case
    if use_redis then
        debug_log(self.logger, "Using Redis for counter decrease")
        local redis_counter, err = self:redis_decrease(ip, count_time, 
                                                       server_name, ban_scope)
        if not redis_counter then
            debug_log(self.logger, "Redis decrease failed, falling back to local: " .. 
                      err)
            self.logger:log(ERR, 
                "(decrease) redis_decrease failed, falling back to local : " .. 
                err)
        else
            counter = redis_counter
            debug_log(self.logger, "Redis counter decreased to: " .. counter)
        end
    end
    
    -- Local case
    if not counter then
        debug_log(self.logger, "Using local datastore for counter decrease")
        local local_counter, err = self.datastore:get(
            "plugin_badbehavior_count_" .. key_suffix)
        if not local_counter and err ~= "not found" then
            debug_log(self.logger, "Failed to get local counter: " .. err)
            self.logger:log(ERR, 
                "(decrease) can't get counts from the datastore : " .. err)
        end
        if local_counter == nil or local_counter <= 1 then
            counter = 0
        else
            counter = local_counter - 1
        end
        debug_log(self.logger, "Local counter decreased to: " .. counter)
    end
    
    -- Store local counter
    if counter <= 0 then
        counter = 0
        debug_log(self.logger, "Counter reached 0, deleting key")
        self.datastore:delete("plugin_badbehavior_count_" .. key_suffix)
    else
        local ok, err = self.datastore:set("plugin_badbehavior_count_" .. 
                                           key_suffix, counter, count_time)
        if not ok then
            debug_log(self.logger, "Failed to store decreased counter: " .. err)
            self.logger:log(ERR, 
                "(decrease) can't save counts to the datastore : " .. err)
            return false, err
        end
        debug_log(self.logger, "Successfully stored decreased counter: " .. counter)
    end
    
    self.logger:log(
        NOTICE,
        "decreased counter for IP "
            .. ip
            .. " ("
            .. tostring(counter)
            .. "/"
            .. tostring(threshold)
            .. ") on server "
            .. server_name
            .. " (status "
            .. status
            .. ", scope "
            .. (ban_scope or "global")
            .. ")"
    )
    return true, "success"
end

-- Increase counter using Redis
-- Uses Redis Lua script to atomically increment counter and set bans
function badbehavior:redis_increase(ip, count_time, ban_time, server_name, 
                                    ban_scope)
    debug_log(self.logger, "Redis increase for IP: " .. ip .. 
              " with ban_scope: " .. ban_scope)
    
    -- Determine key based on ban scope
    local counter_key = "plugin_bad_behavior_" .. ip
    local ban_key = "bans_ip_" .. ip
    if ban_scope == "service" then
        counter_key = "plugin_bad_behavior_" .. server_name .. "_" .. ip
        ban_key = "bans_service_" .. server_name .. "_ip_" .. ip
    end
    
    debug_log(self.logger, "Using Redis keys - counter: " .. counter_key .. 
              ", ban: " .. ban_key)

    -- Our LUA script to execute on redis
    local redis_script = [[
        local ret_incr = redis.pcall("INCR", KEYS[1])
        if type(ret_incr) == "table" and ret_incr["err"] ~= nil then
            redis.log(redis.LOG_WARNING, 
                "Bad behavior increase INCR error : " .. ret_incr["err"])
            return ret_incr
        end
        local ret_expire = redis.pcall("EXPIRE", KEYS[1], ARGV[1])
        if type(ret_expire) == "table" and ret_expire["err"] ~= nil then
            redis.log(redis.LOG_WARNING, 
                "Bad behavior increase EXPIRE error : " .. ret_expire["err"])
            return ret_expire
        end
        if ret_incr > tonumber(ARGV[2]) then
            -- For permanent bans (ban_time = 0), don't set an expiration
            if tonumber(ARGV[2]) == 0 then
                local ret_set = redis.pcall("SET", KEYS[2], "bad behavior")
                if type(ret_set) == "table" and ret_set["err"] ~= nil then
                    redis.log(redis.LOG_WARNING, 
                        "Bad behavior increase SET (permanent) error : " .. 
                        ret_set["err"])
                    return ret_set
                end
            else
                local ret_set = redis.pcall("SET", KEYS[2], "bad behavior", 
                                            "EX", ARGV[2])
                if type(ret_set) == "table" and ret_set["err"] ~= nil then
                    redis.log(redis.LOG_WARNING, 
                        "Bad behavior increase SET error : " .. ret_set["err"])
                    return ret_set
                end
            end
        end
        return ret_incr
    ]]
    
    -- Connect to server
    local ok, err = self.clusterstore:connect()
    if not ok then
        debug_log(self.logger, "Failed to connect to Redis: " .. err)
        return false, err
    end
    
    -- Execute LUA script
    local counter, err = self.clusterstore:call("eval", redis_script, 2, 
                                                 counter_key, ban_key, 
                                                 count_time, ban_time)
    if not counter then
        debug_log(self.logger, "Redis script execution failed: " .. err)
        self.clusterstore:close()
        return false, err
    end
    
    debug_log(self.logger, "Redis script executed successfully, counter: " .. counter)
    
    -- End connection
    self.clusterstore:close()
    return counter
end

-- Decrease counter using Redis
-- Uses Redis Lua script to atomically decrement counter
function badbehavior:redis_decrease(ip, count_time, server_name, ban_scope)
    debug_log(self.logger, "Redis decrease for IP: " .. ip .. 
              " with ban_scope: " .. ban_scope)
    
    -- Determine key based on ban scope
    local counter_key = "plugin_bad_behavior_" .. ip
    if ban_scope == "service" then
        counter_key = "plugin_bad_behavior_" .. server_name .. "_" .. ip
    end
    
    debug_log(self.logger, "Using Redis counter key: " .. counter_key)

    -- Our LUA script to execute on redis
    local redis_script = [[
        local ret_decr = redis.pcall("DECR", KEYS[1])
        if type(ret_decr) == "table" and ret_decr["err"] ~= nil then
            redis.log(redis.LOG_WARNING, 
                "Bad behavior decrease DECR error : " .. ret_decr["err"])
            return ret_decr
        end
        local ret_expire = redis.pcall("EXPIRE", KEYS[1], ARGV[1])
        if type(ret_expire) == "table" and ret_expire["err"] ~= nil then
            redis.log(redis.LOG_WARNING, 
                "Bad behavior decrease EXPIRE error : " .. ret_expire["err"])
            return ret_expire
        end
        if ret_decr <= 0 then
            local ret_del = redis.pcall("DEL", KEYS[1])
            if type(ret_del) == "table" and ret_del["err"] ~= nil then
                redis.log(redis.LOG_WARNING, 
                    "Bad behavior decrease DEL error : " .. ret_del["err"])
                return ret_del
            end
        end
        return ret_decr
    ]]
    
    -- Connect to server
    local ok, err = self.clusterstore:connect()
    if not ok then
        debug_log(self.logger, "Failed to connect to Redis: " .. err)
        return false, err
    end
    
    local counter, err = self.clusterstore:call("eval", redis_script, 1, 
                                                 counter_key, count_time)
    if not counter then
        debug_log(self.logger, "Redis decrease script execution failed: " .. err)
        self.clusterstore:close()
        return false, err
    end
    
    debug_log(self.logger, "Redis decrease script executed successfully, counter: " .. 
              counter)
    
    self.clusterstore:close()
    return counter
end

return badbehavior