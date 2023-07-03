local ffi = require "ffi"
local C = ffi.C
local ffi_gc = ffi.gc
local ffi_str = ffi.string

require "resty.openssl.include.evp.md"
local ctypes = require "resty.openssl.auxiliary.ctypes"
local ctx_lib = require "resty.openssl.ctx"
local format_error = require("resty.openssl.err").format_error
local OPENSSL_10 = require("resty.openssl.version").OPENSSL_10
local OPENSSL_11_OR_LATER = require("resty.openssl.version").OPENSSL_11_OR_LATER
local OPENSSL_3X = require("resty.openssl.version").OPENSSL_3X

local _M = {}
local mt = {__index = _M}

local md_ctx_ptr_ct = ffi.typeof('EVP_MD_CTX*')

function _M.new(typ, properties)
  local ctx
  if OPENSSL_11_OR_LATER then
    ctx = C.EVP_MD_CTX_new()
    ffi_gc(ctx, C.EVP_MD_CTX_free)
  elseif OPENSSL_10 then
    ctx = C.EVP_MD_CTX_create()
    ffi_gc(ctx, C.EVP_MD_CTX_destroy)
  end
  if ctx == nil then
    return nil, "digest.new: failed to create EVP_MD_CTX"
  end

  local err_new = string.format("digest.new: invalid digest type \"%s\"", typ)

  local algo
  if typ == "null" then
    algo = C.EVP_md_null()
  else
    if OPENSSL_3X then
      algo = C.EVP_MD_fetch(ctx_lib.get_libctx(), typ or 'sha1', properties)
    else
      algo = C.EVP_get_digestbyname(typ or 'sha1')
    end
    if algo == nil then
      return nil, format_error(err_new)
    end
  end

  local code = C.EVP_DigestInit_ex(ctx, algo, nil)
  if code ~= 1 then
    return nil, format_error(err_new)
  end

  return setmetatable({
    ctx = ctx,
    algo = algo,
    buf = ctypes.uchar_array(OPENSSL_3X and C.EVP_MD_get_size(algo) or C.EVP_MD_size(algo)),
  }, mt), nil
end

function _M.istype(l)
  return l and l.ctx and ffi.istype(md_ctx_ptr_ct, l.ctx)
end

function _M:get_provider_name()
  if not OPENSSL_3X then
    return false, "digest:get_provider_name is not supported"
  end
  local p = C.EVP_MD_get0_provider(self.algo)
  if p == nil then
    return nil
  end
  return ffi_str(C.OSSL_PROVIDER_get0_name(p))
end

if OPENSSL_3X then
  local param_lib = require "resty.openssl.param"
  _M.settable_params, _M.set_params, _M.gettable_params, _M.get_param = param_lib.get_params_func("EVP_MD_CTX")
end

function _M:update(...)
  for _, s in ipairs({...}) do
    if C.EVP_DigestUpdate(self.ctx, s, #s) ~= 1 then
      return false, format_error("digest:update")
    end
  end
  return true, nil
end

local result_length = ctypes.ptr_of_uint()

function _M:final(s)
  if s then
    if C.EVP_DigestUpdate(self.ctx, s, #s) ~= 1 then
      return false, format_error("digest:final")
    end
  end

  -- no return value of EVP_DigestFinal_ex
  C.EVP_DigestFinal_ex(self.ctx, self.buf, result_length)
  if result_length[0] == nil or result_length[0] <= 0 then
    return nil, format_error("digest:final: EVP_DigestFinal_ex")
  end
  return ffi_str(self.buf, result_length[0])
end


function _M:reset()
  local code = C.EVP_DigestInit_ex(self.ctx, self.algo, nil)
  if code ~= 1 then
    return false, format_error("digest:reset")
  end

  return true
end

return _M
