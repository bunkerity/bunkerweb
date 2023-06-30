local ffi = require "ffi"
local C = ffi.C
local ffi_gc = ffi.gc
local ffi_str = ffi.string

require "resty.openssl.include.hmac"
require "resty.openssl.include.evp.md"
local ctypes = require "resty.openssl.auxiliary.ctypes"
local format_error = require("resty.openssl.err").format_error
local OPENSSL_10 = require("resty.openssl.version").OPENSSL_10
local OPENSSL_11_OR_LATER = require("resty.openssl.version").OPENSSL_11_OR_LATER
local OPENSSL_3X = require("resty.openssl.version").OPENSSL_3X

local _M = {}
local mt = {__index = _M}

local hmac_ctx_ptr_ct = ffi.typeof('HMAC_CTX*')

-- Note: https://www.openssl.org/docs/manmaster/man3/HMAC_Init.html
-- Replace with EVP_MAC_* functions for OpenSSL 3.0

function _M.new(key, typ)
  local ctx
  if OPENSSL_11_OR_LATER then
    ctx = C.HMAC_CTX_new()
    ffi_gc(ctx, C.HMAC_CTX_free)
  elseif OPENSSL_10 then
    ctx = ffi.new('HMAC_CTX')
    C.HMAC_CTX_init(ctx)
    ffi_gc(ctx, C.HMAC_CTX_cleanup)
  end
  if ctx == nil then
    return nil, "hmac.new: failed to create HMAC_CTX"
  end

  local algo = C.EVP_get_digestbyname(typ or 'sha1')
  if algo == nil then
    return nil, string.format("hmac.new: invalid digest type \"%s\"", typ)
  end

  local code = C.HMAC_Init_ex(ctx, key, #key, algo, nil)
  if code ~= 1 then
    return nil, format_error("hmac.new")
  end

  return setmetatable({
    ctx = ctx,
    algo = algo,
    buf = ctypes.uchar_array(OPENSSL_3X and C.EVP_MD_get_size(algo) or C.EVP_MD_size(algo)),
  }, mt), nil
end

function _M.istype(l)
  return l and l.ctx and ffi.istype(hmac_ctx_ptr_ct, l.ctx)
end

function _M:update(...)
  for _, s in ipairs({...}) do
    if C.HMAC_Update(self.ctx, s, #s) ~= 1 then
      return false, format_error("hmac:update")
    end
  end
  return true, nil
end

local result_length = ctypes.ptr_of_uint()

function _M:final(s)
  if s then
    if C.HMAC_Update(self.ctx, s, #s) ~= 1 then
      return false, format_error("hmac:final")
    end
  end

  if C.HMAC_Final(self.ctx, self.buf, result_length) ~= 1 then
    return nil, format_error("hmac:final: HMAC_Final")
  end
  return ffi_str(self.buf, result_length[0])
end

function _M:reset()
  local code = C.HMAC_Init_ex(self.ctx, nil, 0, nil, nil)
  if code ~= 1 then
    return false, format_error("hmac:reset")
  end

  return true
end

return _M
