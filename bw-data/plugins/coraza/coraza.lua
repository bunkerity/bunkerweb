local class		= require "middleclass"
local plugin	= require "bunkerweb.plugin"
local utils     = require "bunkerweb.utils"
local http		= require "resty.http"
local cjson     = require "cjson"
local coraza = class("coraza", plugin)

function coraza:initialize()
    -- Call parent initialize
   plugin.initialize(self, "coraza") 
end


function coraza:init_worker()
    --Send conf request
    local ret, err = self:request("conf","POST")
    if err then
        return self:ret(false,"error when sending conf request")
    end
    
    return self:ret(true,"success")
end

function coraza:init()
    return self:ret(true,"coraza init success")
end


function coraza:access()
    -- Check if needed
    if self.variables["USE_CORAZA"] ~= "yes" then
        return self:ret(true, "coraza not activated")
    end

    -- Send http request to coraza container
    local ret, msg, status = self:request("client",ngx.var.request_method)
    if not ret then
        return self:ret(false, "coraza error from request : " .. msg)
    end
    if status == 403 then
        return self:ret(true, "coraza access denied ", utils.get_deny_status())
    elseif status == 401 then
        return self:ret(true, "coraza bad request", ngx.HTTP_BAD_REQUEST)
    elseif status == 405 then
        return self:ret(true, "coraza method not allowed",  utils.get_deny_status()) -- a fix pas trouver le bon ngx
    elseif status == 500 then
        return self:ret(true, "coraza internal server error", ngx.HTTP_INTERNAL_SERVER_ERROR)
    end
    if status == 200 then
        return self:ret(true, "coraza access success" )
    end
    return self:ret(false, "coraza access error" )
    

end

function coraza:request(type,method) 
    -- set API url
    local value = self.variables["CORAZA_API"]
    if not value then
      return false, "coraza error while getting CORAZA_API setting"
    end
    self.api=value
    -- Create an http request
    local httpc, err = http.new()
    if not httpc then
      return false, "coraza can't instantiate http object : " .. err
    end
    -- Check the type of request to be sent
    if type == "client" then
        local body = nil
            if method ~= "GET" then
            ngx.req.read_body()
            body = ngx.req.get_body_data()
            if not body then
                body = ngx.req.get_body_file()
                if not body then
                return false, "coraza no body found"
                end
            end
        end
        -- Avoid duplicate ID
        math.randomseed(os.time()- os.clock() * 1000) 

        local id = utils.rand(16)

        
        local data = {
            ["X-Coraza-ID"] = id,
            ["X-Coraza-URI"] = ngx.ctx.bw.request_uri,
            ["X-Coraza-HEAD"] = ngx.req.get_headers(),
            ["X-Coraza-MET"] = method,
            ["X-Coraza-IP"] = ngx.ctx.bw.remote_addr,
            ["X-Coraza-BODY"] = body
        }
        -- Encode data
        local ok, Body = pcall(cjson.encode, data)
        if not ok then
            return false, "error while encoding json : " .. Body
        end
        -- Build request
        local res, err_http = httpc:request_uri(self.api, {
            method = "POST",
            body = Body,
            headers = {
                ["Request-type"] = "client",
                ["Content-Length"] = tostring(#Body)
            }
        })
        httpc:close()
        if not res then
            return false, "coraza error while sending request : " .. err_http
        end


        return true,"success",res.status

    elseif type == "conf" then
        -- Check user input
        local value = self.variables["CORAZA_API"]
        if not value then
            return false, "coraza error while getting CORAZA_API setting"
        end
        self.api=value
        local use_crs = self.variables["USE_OWASP_CRS"]
        if use_crs ~= "yes" and use_crs ~= "no" then
            self:ret(false, "coraza wrong assigment to 'USE_OWASP_CRS'" )
        end
        local sec_audit = self.variables["CORAZA_SEC_AUDIT_ENGINE"]
        if sec_audit ~= "On" and sec_audit ~= "Off" and sec_audit ~= "RelevantOnly" then
            self:ret(false, "coraza wrong assigment to 'CORAZA_SEC_AUDIT_ENGINE'" )
        end
        local sec_rule = self.variables["CORAZA_SEC_RULE_ENGINE"]
        if sec_rule ~= "On" and sec_rule ~= "Off" and sec_rule ~= "RelevantOnly" then
            self:ret(false, "coraza wrong assigment to 'CORAZA_SEC_RULE_ENGINE'" )
        end
        local sec_audit_log = self.variables["CORAZA_SEC_AUDIT_LOG_PARTS"]
        local str = sec_audit_log
        if not string.match(str, "^A(([B-K])(?!.*\\2))+Z$") then
            self:ret(false, "coraza wrong assigment to 'CORAZA_SEC_AUDIT_LOG_PARTS'" )
        end

        local data = {
            ["CORAZA_SEC_AUDIT_ENGINE"] = sec_audit,
            ["USE_OWASP_CRS"] = use_crs,
            ["CORAZA_SEC_RULE_ENGINE"] = sec_rule,
            ["CORAZA_SEC_AUDIT_LOG_PARTS"] = sec_audit_log,
        }
        -- Encode data
        local ok, Body = pcall(cjson.encode, data)
        if not ok then
            return false, "error while encoding json : " .. Body
        end

        -- Build request
        local res, err_http = httpc:request_uri(self.api, {
            method = "POST",
            body = Body,
            headers = {
            ["Request-type"] = "conf",
            ["Content-Length"] = tostring(#Body)
            }
        })
        
        httpc:close()
        
        if not res then
            return false, "coraza error while sending request : " .. err_http
        end

        return true,"success"

    else
        return false, "wrong type of request"
    end
   

end



return coraza

