local nkeys

do
  local pok, perr = pcall(require, "table.nkeys")
  if pok then
    nkeys = perr
  else
    nkeys = function(tbl)
      local cnt = 0
      for _ in pairs(tbl) do
          cnt = cnt + 1
      end
      return cnt
    end
  end
end

local noop = function() end

local log_warn, log_debug
local encode_base64url, decode_base64url

if ngx then
  log_warn = function(...)
    ngx.log(ngx.WARN, ...)
  end

  log_debug = function(...)
    ngx.log(ngx.DEBUG, ...)
  end

  local b64 = require("ngx.base64")
  encode_base64url = b64.encode_base64url
  decode_base64url = b64.decode_base64url

else
  log_warn = noop
  log_debug = noop

  local pok, basexx = pcall(require, "basexx")
  if pok then
    encode_base64url = basexx.to_url64
    decode_base64url = basexx.from_url64
  else
    encode_base64url = function()
      error("no base64 library is found, needs either ngx.base64 or basexx")
    end
    decode_base64url = encode_base64url
  end

end

local json
do
  local pok, perr = pcall(require, "cjson.safe")
  if pok then
    json = perr
  else
    local pok, perr = pcall(require, "dkjson")
    if pok then
      json = perr
    end
  end

  if not json then
    json = setmetatable({}, {
      __index = function()
        return function()
          error("no JSON library is found, needs either cjson or dkjson")
        end
      end,
    })
  end
end


return {
  nkeys = nkeys,
  log_warn = log_warn,
  log_debug = log_debug,
  encode_base64url = encode_base64url,
  decode_base64url = decode_base64url,
  json = json,
}