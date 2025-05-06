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

M.SecretKey = ""
M.SiteKey = ""
M.Template = ""

function M.New(siteKey, secretKey, TemplateFilePath, captcha_provider)

    if siteKey == nil or siteKey == "" then
      return "no recaptcha site key provided, can't use recaptcha"
    end
    M.SiteKey = siteKey

    if secretKey == nil or secretKey == "" then
      return "no recaptcha secret key provided, can't use recaptcha"
    end

    M.SecretKey = secretKey

    if TemplateFilePath == nil then
      return "CAPTCHA_TEMPLATE_PATH variable is empty, will ban without template"
    end
    if utils.file_exist(TemplateFilePath) == false then
      return "captcha template file doesn't exist, can't use recaptcha"
    end

    local captcha_template = utils.read_file(TemplateFilePath)
    if captcha_template == nil then
        return "Template file " .. TemplateFilePath .. "not found."
    end

    M.CaptchaProvider = captcha_provider

    local template_data = {}
    template_data["captcha_site_key"] =  M.SiteKey
    template_data["captcha_frontend_js"] = captcha_frontend_js[M.CaptchaProvider]
    template_data["captcha_frontend_key"] = captcha_frontend_key[M.CaptchaProvider]
    local view = template.compile(captcha_template, template_data)
    M.Template = view

    return nil
end


function M.GetTemplate()
    return M.Template
end

function M.GetCaptchaBackendKey()
    return captcha_frontend_key[M.CaptchaProvider] .. "-response"
end

function table_to_encoded_url(args)
    local params = {}
    for k, v in pairs(args) do table.insert(params, k .. '=' .. v) end
    return table.concat(params, "&")
end

function M.Validate(captcha_res, remote_ip)
    local body = {
        secret   = M.SecretKey,
        response = captcha_res,
        remoteip = remote_ip
    }

    local data = table_to_encoded_url(body)
    local httpc = http.new()
    httpc:set_timeout(2000)
    local res, err = httpc:request_uri(captcha_backend_url[M.CaptchaProvider], {
      method = "POST",
      body = data,
      headers = {
          ["Content-Type"] = "application/x-www-form-urlencoded",
      },
    })
    httpc:close()
    if err ~= nil then
      return true, err
    end

    local result = cjson.decode(res.body)

    if result.success == false then
      for k, v in pairs(result["error-codes"]) do
        if v == "invalid-input-secret" then
          ngx.log(ngx.ERR, "reCaptcha secret key is invalid")
          return true, nil
        end
      end
    end

    return result.success, nil
end


return M
