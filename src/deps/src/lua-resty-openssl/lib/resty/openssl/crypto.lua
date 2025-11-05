local ffi = require "ffi"
local ffi_cast = ffi.cast
local C = ffi.C
require "resty.openssl.include.crypto"

local _M = {}

function _M.memcmp(a, b, len)
  if type(len) ~= "number" or len < 1 then
    return nil, "crypto:memcmp arg 'len' must be a number > 0"
  end
  if type(a) ~= "string" and type(a) ~= "cdata" then
    return nil, "crypto:memcmp only strings and cdata types are supported"
  end

  return C.CRYPTO_memcmp(ffi_cast("void*", a), ffi_cast("void*", b), len)
end

return _M
