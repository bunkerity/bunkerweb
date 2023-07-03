local ffi = require "ffi"
local C = ffi.C
local ffi_gc = ffi.gc

require "resty.openssl.include.ossl_typ"
local format_error = require("resty.openssl.err").format_error
local OPENSSL_3X = require("resty.openssl.version").OPENSSL_3X

ffi.cdef [[
  OSSL_LIB_CTX *OSSL_LIB_CTX_new(void);
  int OSSL_LIB_CTX_load_config(OSSL_LIB_CTX *ctx, const char *config_file);
  void OSSL_LIB_CTX_free(OSSL_LIB_CTX *ctx);
]]

local ossl_lib_ctx

local function new(request_context_only, conf_file)
  if not OPENSSL_3X then
    return false, "ctx is only supported from OpenSSL 3.0"
  end

  local ctx = C.OSSL_LIB_CTX_new()
  ffi_gc(ctx, C.OSSL_LIB_CTX_free)

  if conf_file and C.OSSL_LIB_CTX_load_config(ctx, conf_file) ~= 1 then
    return false, format_error("ctx.new")
  end

  if request_context_only then
    ngx.ctx.ossl_lib_ctx = ctx
  else
    ossl_lib_ctx = ctx
  end

  return true
end

local function free(request_context_only)
  if not OPENSSL_3X then
    return false, "ctx is only supported from OpenSSL 3.0"
  end

  if request_context_only then
    ngx.ctx.ossl_lib_ctx = nil
  else
    ossl_lib_ctx = nil
  end

  return true
end

local test_request

do

  local ok, exdata = pcall(require, "thread.exdata")
  if ok and exdata then
    test_request = function()
      local r = exdata()
      if r ~= nil then
          return not not r
      end
    end

  else
    local getfenv = getfenv

    function test_request()
      return not not getfenv(0).__ngx_req
    end
  end
end

return {
  new = new,
  free = free,
  get_libctx = function() return test_request() and ngx.ctx.ossl_lib_ctx or ossl_lib_ctx end,
}