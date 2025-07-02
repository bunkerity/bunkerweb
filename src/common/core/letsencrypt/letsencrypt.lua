local cjson = require "cjson"
local class = require "middleclass"
local plugin = require "bunkerweb.plugin"
local ssl = require "ngx.ssl"
local utils = require "bunkerweb.utils"

local letsencrypt = class("letsencrypt", plugin)

local ngx = ngx
local ERR = ngx.ERR
local NOTICE = ngx.NOTICE
local OK = ngx.OK
local HTTP_NOT_FOUND = ngx.HTTP_NOT_FOUND
local HTTP_OK = ngx.HTTP_OK
local HTTP_BAD_REQUEST = ngx.HTTP_BAD_REQUEST
local HTTP_INTERNAL_SERVER_ERROR = ngx.HTTP_INTERNAL_SERVER_ERROR
local parse_pem_cert = ssl.parse_pem_cert
local parse_pem_priv_key = ssl.parse_pem_priv_key
local ssl_server_name = ssl.server_name
local get_variable = utils.get_variable
local get_multiple_variables = utils.get_multiple_variables
local has_variable = utils.has_variable
local read_files = utils.read_files
local open = io.open
local sub = string.sub
local match = string.match
local decode = cjson.decode
local execute = os.execute
local remove = os.remove

-- Log debug messages only when LOG_LEVEL environment variable is set to 
-- "debug"
local function debug_log(logger, message)
    if os.getenv("LOG_LEVEL") == "debug" then
        logger:log(NOTICE, "[DEBUG] " .. message)
    end
end

-- Initialize the letsencrypt plugin with the given context
-- @param ctx The context object containing plugin configuration
function letsencrypt:initialize(ctx)
    -- Call parent initialize
    plugin.initialize(self, "letsencrypt", ctx)
end

-- Set the https_configured flag based on AUTO_LETS_ENCRYPT variable
-- Configures HTTPS settings for the plugin
function letsencrypt:set()
    local https_configured = self.variables["AUTO_LETS_ENCRYPT"]
    if https_configured == "yes" then
        self.ctx.bw.https_configured = "yes"
    end
    debug_log(self.logger, "Set https_configured to " .. https_configured)
    return self:ret(true, "set https_configured to " .. https_configured)
end

-- Initialize SSL certificates and load them into the datastore
-- Handles both multisite and single-site configurations, processes wildcard
-- certificates, and loads certificate data from filesystem
function letsencrypt:init()
    local ret_ok, ret_err = true, "success"
    local wildcard_servers = {}

    debug_log(self.logger, "Starting letsencrypt init phase")

    if has_variable("AUTO_LETS_ENCRYPT", "yes") then
        debug_log(self.logger, "AUTO_LETS_ENCRYPT is enabled")
        
        local multisite, err = get_variable("MULTISITE", false)
        if not multisite then
            return self:ret(false, "can't get MULTISITE variable : " .. err)
        end
        
        debug_log(self.logger, "MULTISITE mode is " .. multisite)
        
        if multisite == "yes" then
            debug_log(self.logger, "Processing multisite configuration")
            
            local vars
            vars, err = get_multiple_variables({
                "AUTO_LETS_ENCRYPT",
                "LETS_ENCRYPT_CHALLENGE",
                "LETS_ENCRYPT_DNS_PROVIDER",
                "USE_LETS_ENCRYPT_WILDCARD",
                "SERVER_NAME",
            })
            if not vars then
                return self:ret(false, 
                    "can't get required variables : " .. err)
            end
            
            local credential_items
            credential_items, err = get_multiple_variables({ 
                "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM" 
            })
            if not credential_items then
                return self:ret(false, 
                    "can't get credential items : " .. err)
            end
            
            for server_name, multisite_vars in pairs(vars) do
                debug_log(self.logger, 
                    "Processing server: " .. server_name)
                
                if multisite_vars["AUTO_LETS_ENCRYPT"] == "yes"
                    and server_name ~= "global"
                    and (
                        multisite_vars["LETS_ENCRYPT_CHALLENGE"] == "http"
                        or (
                            multisite_vars["LETS_ENCRYPT_CHALLENGE"] == "dns"
                            and multisite_vars["LETS_ENCRYPT_DNS_PROVIDER"] 
                                ~= ""
                            and credential_items[server_name]
                        )
                    )
                then
                    debug_log(self.logger, 
                        "Server " .. server_name .. " qualifies for SSL")
                    
                    local data
                    if multisite_vars["LETS_ENCRYPT_CHALLENGE"] == "dns"
                        and multisite_vars["USE_LETS_ENCRYPT_WILDCARD"] 
                            == "yes"
                    then
                        debug_log(self.logger, 
                            "Using wildcard configuration for " .. 
                            server_name)
                        
                        for part in server_name:gmatch("%S+") do
                            wildcard_servers[part] = true
                        end
                        local parts = {}
                        for part in server_name:gmatch("[^.]+") do
                            table.insert(parts, part)
                        end
                        server_name = table.concat(parts, ".", 2)
                        data = self.datastore:get("plugin_letsencrypt_" .. 
                            server_name, true)
                    else
                        for part in server_name:gmatch("%S+") do
                            wildcard_servers[part] = false
                        end
                    end
                    
                    if not data then
                        debug_log(self.logger, 
                            "Loading certificate files for " .. server_name)
                        
                        -- Load certificate
                        local check
                        check, data = read_files({
                            "/var/cache/bunkerweb/letsencrypt/etc/live/" .. 
                                server_name .. "/fullchain.pem",
                            "/var/cache/bunkerweb/letsencrypt/etc/live/" .. 
                                server_name .. "/privkey.pem",
                        })
                        if not check then
                            self.logger:log(ERR, 
                                "error while reading files : " .. data)
                            ret_ok = false
                            ret_err = "error reading files"
                        else
                            if multisite_vars["LETS_ENCRYPT_CHALLENGE"] 
                                    == "dns"
                                and multisite_vars["USE_LETS_ENCRYPT_WILDCARD"] 
                                    == "yes"
                            then
                                check, err = self:load_data(data, server_name)
                            else
                                check, err = self:load_data(data, 
                                    multisite_vars["SERVER_NAME"])
                            end
                            if not check then
                                self.logger:log(ERR, 
                                    "error while loading data : " .. err)
                                ret_ok = false
                                ret_err = "error loading data"
                            end
                        end
                    end
                end
            end
        else
            debug_log(self.logger, "Processing single-site configuration")
            
            local server_name
            server_name, err = get_variable("SERVER_NAME", false)
            if not server_name then
                return self:ret(false, 
                    "can't get SERVER_NAME variable : " .. err)
            end
            
            local use_wildcard
            use_wildcard, err = get_variable("USE_LETS_ENCRYPT_WILDCARD", 
                false)
            if not use_wildcard then
                return self:ret(false, 
                    "can't get USE_LETS_ENCRYPT_WILDCARD variable : " .. err)
            end
            
            local challenge
            challenge, err = get_variable("LETS_ENCRYPT_CHALLENGE", false)
            if not challenge then
                return self:ret(false, 
                    "can't get LETS_ENCRYPT_CHALLENGE variable : " .. err)
            end
            
            server_name = server_name:match("%S+")
            debug_log(self.logger, 
                "Processing server_name: " .. server_name)
            
            if challenge == "dns" and use_wildcard == "yes" then
                debug_log(self.logger, 
                    "Using wildcard DNS challenge for " .. server_name)
                
                for part in server_name:gmatch("%S+") do
                    wildcard_servers[part] = true
                end
                local parts = {}
                for part in server_name:gmatch("[^.]+") do
                    table.insert(parts, part)
                end
                server_name = table.concat(parts, ".", 2)
            else
                for part in server_name:gmatch("%S+") do
                    wildcard_servers[part] = false
                end
            end
            
            debug_log(self.logger, 
                "Loading certificates for " .. server_name)
            
            local check, data = read_files({
                "/var/cache/bunkerweb/letsencrypt/etc/live/" .. 
                    server_name .. "/fullchain.pem",
                "/var/cache/bunkerweb/letsencrypt/etc/live/" .. 
                    server_name .. "/privkey.pem",
            })
            if not check then
                self.logger:log(ERR, "error while reading files : " .. data)
                ret_ok = false
                ret_err = "error reading files"
            else
                check, err = self:load_data(data, server_name)
                if not check then
                    self.logger:log(ERR, "error while loading data : " .. err)
                    ret_ok = false
                    ret_err = "error loading data"
                end
            end
        end
    else
        debug_log(self.logger, "Let's Encrypt is not enabled")
        ret_err = "let's encrypt is not used"
    end

    debug_log(self.logger, "Storing wildcard servers configuration")
    
    local ok, err = self.datastore:set("plugin_letsencrypt_wildcard_servers", 
        wildcard_servers, nil, true)
    if not ok then
        return self:ret(false, 
            "error while setting wildcard servers into datastore : " .. err)
    end

    debug_log(self.logger, "Init phase completed with status: " .. 
        tostring(ret_ok))
    
    return self:ret(ret_ok, ret_err)
end

-- Handle SSL certificate selection based on SNI
-- Determines which certificate to use based on server name indication and
-- wildcard configuration
function letsencrypt:ssl_certificate()
    debug_log(self.logger, "SSL certificate phase started")
    
    local server_name, err = ssl_server_name()
    if not server_name then
        return self:ret(false, "can't get server_name : " .. err)
    end
    
    debug_log(self.logger, "Processing SSL for server: " .. server_name)
    
    local wildcard_servers, err = self.datastore:get(
        "plugin_letsencrypt_wildcard_servers", true)
    if not wildcard_servers then
        return self:ret(false, "can't get wildcard servers : " .. err)
    end
    
    if wildcard_servers[server_name] then
        debug_log(self.logger, 
            "Using wildcard certificate for " .. server_name)
        
        local parts = {}
        for part in server_name:gmatch("[^.]+") do
            table.insert(parts, part)
        end
        server_name = table.concat(parts, ".", 2)
    end
    
    local data
    data, err = self.datastore:get("plugin_letsencrypt_" .. server_name, true)
    if not data and err ~= "not found" then
        return self:ret(false, "error while getting plugin_letsencrypt_" .. 
            server_name .. " from datastore : " .. err)
    elseif data then
        debug_log(self.logger, 
            "Certificate data found for " .. server_name)
        return self:ret(true, "certificate/key data found", data)
    end
    
    debug_log(self.logger, "No certificate data found for " .. server_name)
    return self:ret(true, "let's encrypt is not used")
end

-- Load certificate and private key data into the datastore
-- Parses PEM certificate and private key files and caches them in the
-- datastore for quick retrieval
-- @param data Table containing certificate and key file contents
-- @param server_name The server name to associate with the certificate
function letsencrypt:load_data(data, server_name)
    debug_log(self.logger, "Loading certificate data for " .. server_name)
    
    -- Load certificate
    local cert_chain, err = parse_pem_cert(data[1])
    if not cert_chain then
        return false, "error while parsing pem cert : " .. err
    end
    
    -- Load key
    local priv_key
    priv_key, err = parse_pem_priv_key(data[2])
    if not priv_key then
        return false, "error while parsing pem priv key : " .. err
    end
    
    debug_log(self.logger, "Certificate and key parsed successfully")
    
    -- Cache data
    for key in server_name:gmatch("%S+") do
        debug_log(self.logger, "Caching certificate data for " .. key)
        
        local cache_key = "plugin_letsencrypt_" .. key
        local ok
        ok, err = self.datastore:set(cache_key, { cert_chain, priv_key }, 
            nil, true)
        if not ok then
            return false, "error while setting data into datastore : " .. err
        end
    end
    
    debug_log(self.logger, "Certificate data cached successfully")
    return true
end

-- Handle ACME challenge requests during certificate generation
-- Allows Let's Encrypt to access challenge files for domain validation
function letsencrypt:access()
    debug_log(self.logger, "Access phase started")
    
    if self.variables["LETS_ENCRYPT_PASSTHROUGH"] == "no"
        and sub(self.ctx.bw.uri, 1, 
            string.len("/.well-known/acme-challenge/")) == 
            "/.well-known/acme-challenge/"
    then
        debug_log(self.logger, "ACME challenge request detected")
        
        self.logger:log(NOTICE, 
            "got a visit from Let's Encrypt, let's whitelist it")
        return self:ret(true, "visit from LE", OK)
    end
    
    return self:ret(true, "success")
end

-- Handle API requests for certificate challenge management
-- Provides endpoints for creating and removing ACME challenge validation
-- tokens during the certificate issuance process
function letsencrypt:api()
    debug_log(self.logger, "API endpoint called")
    
    if not match(self.ctx.bw.uri, "^/lets%-encrypt/challenge$")
        or (self.ctx.bw.request_method ~= "POST" 
            and self.ctx.bw.request_method ~= "DELETE")
    then
        debug_log(self.logger, "API request does not match expected pattern")
        return self:ret(false, "success")
    end
    
    local acme_folder = "/var/tmp/bunkerweb/lets-encrypt/" .. 
        ".well-known/acme-challenge/"
    local ngx_req = ngx.req
    ngx_req.read_body()
    local ret, data = pcall(decode, ngx_req.get_body_data())
    if not ret then
        debug_log(self.logger, "Failed to decode JSON body")
        return self:ret(true, "json body decoding failed", HTTP_BAD_REQUEST)
    end
    
    debug_log(self.logger, "Creating ACME challenge directory: " .. 
        acme_folder)
    execute("mkdir -p " .. acme_folder)
    
    if self.ctx.bw.request_method == "POST" then
        debug_log(self.logger, "Processing POST request for token: " .. 
            data.token)
        
        local file, err = open(acme_folder .. data.token, "w+")
        if not file then
            return self:ret(true, "can't write validation token : " .. err, 
                HTTP_INTERNAL_SERVER_ERROR)
        end
        file:write(data.validation)
        file:close()
        
        debug_log(self.logger, "Validation token written successfully")
        return self:ret(true, "validation token written", HTTP_OK)
        
    elseif self.ctx.bw.request_method == "DELETE" then
        debug_log(self.logger, "Processing DELETE request for token: " .. 
            data.token)
        
        local ok, err = remove(acme_folder .. data.token)
        if not ok then
            return self:ret(true, "can't remove validation token : " .. err, 
                HTTP_INTERNAL_SERVER_ERROR)
        end
        
        debug_log(self.logger, "Validation token removed successfully")
        return self:ret(true, "validation token removed", HTTP_OK)
    end
    
    debug_log(self.logger, "Unknown request method")
    return self:ret(true, "unknown request", HTTP_NOT_FOUND)
end

return letsencrypt