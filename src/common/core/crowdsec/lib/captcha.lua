local http = require "resty.http"
local cjson = require "cjson"
local template = require "crowdsec.lib.template"
local utils = require "crowdsec.lib.utils"

local M = {_TYPE='module', _NAME='recaptcha.funcs', _VERSION='1.0-0'}

local captcha_backend_url = {}
captcha_backend_url["recaptcha"] = "https://www.recaptcha.net/recaptcha/api/siteverify"
captcha_backend_url["hcaptcha"] = "https://hcaptcha.com/siteverify"
captcha_backend_url["turnstile"] = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

local captcha_frontend_js = {}
captcha_frontend_js["recaptcha"] = "https://www.recaptcha.net/recaptcha/api.js"
captcha_frontend_js["hcaptcha"] = "https://js.hcaptcha.com/1/api.js"
captcha_frontend_js["turnstile"] = "https://challenges.cloudflare.com/turnstile/v0/api.js"

local captcha_frontend_key = {}
captcha_frontend_key["recaptcha"] = "g-recaptcha"
captcha_frontend_key["hcaptcha"] = "h-captcha"
captcha_frontend_key["turnstile"] = "cf-turnstile"

function M.New(siteKey, secretKey, TemplateFilePath, captcha_provider)
    if not captcha_backend_url[captcha_provider] then
      return nil, "unsupported captcha provider"
    end
    if type(siteKey) ~= "string" or siteKey == "" then
      return nil, "no captcha site key provided"
    end
    if type(secretKey) ~= "string" or secretKey == "" then
      return nil, "no captcha secret key provided"
    end
    if not TemplateFilePath or not utils.file_exist(TemplateFilePath) then
      return nil, "captcha template file does not exist"
    end

    local captcha_template = utils.read_file(TemplateFilePath)
    if captcha_template == nil then
        return nil, "cannot read captcha template"
    end

    local template_data = {}
    template_data["captcha_site_key"] = siteKey
    template_data["captcha_frontend_js"] = captcha_frontend_js[captcha_provider]
    template_data["captcha_frontend_key"] = captcha_frontend_key[captcha_provider]
    local ok, view = pcall(template.compile, captcha_template, template_data)
    if not ok or type(view) ~= "string" then
        return nil, "cannot compile captcha template"
    end

    -- Configuration is private to this instance, never shared module state.
    local instance = {}
    function instance.GetTemplate()
        return view
    end
    function instance.GetCaptchaBackendKey()
        return captcha_frontend_key[captcha_provider] .. "-response"
    end
    function instance.Validate(captcha_res, remote_ip)
        if type(captcha_res) ~= "string" or captcha_res == "" or type(remote_ip) ~= "string" then
            return false, "invalid captcha verification input"
        end
        local body = {
            secret   = secretKey,
            response = captcha_res,
            remoteip = remote_ip
        }

        local data = ngx.encode_args(body)
        local httpc = http.new()
        httpc:set_timeout(2000)
        local res, err = httpc:request_uri(captcha_backend_url[captcha_provider], {
            method = "POST",
            body = data,
            headers = {
                ["Content-Type"] = "application/x-www-form-urlencoded",
            },
            ssl_verify = true,
        })
        httpc:close()
        if err or not res then
            return false, "captcha provider request failed"
        end
        if res.status ~= 200 then
            return false, "captcha provider returned HTTP " .. tostring(res.status)
        end
        local decoded, result = pcall(cjson.decode, res.body)
        if not decoded or type(result) ~= "table" or type(result.success) ~= "boolean" then
            return false, "invalid captcha provider response"
        end

        return result.success, nil
    end
    return instance
end


return M
