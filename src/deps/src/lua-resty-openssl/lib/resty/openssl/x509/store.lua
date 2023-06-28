local ffi = require "ffi"
local C = ffi.C
local ffi_gc = ffi.gc
local ffi_str = ffi.string
local bor = bit.bor

local x509_vfy_macro = require "resty.openssl.include.x509_vfy"
local x509_lib = require "resty.openssl.x509"
local chain_lib = require "resty.openssl.x509.chain"
local crl_lib = require "resty.openssl.x509.crl"
local ctx_lib = require "resty.openssl.ctx"
local format_all_error = require("resty.openssl.err").format_all_error
local format_error = require("resty.openssl.err").format_error
local OPENSSL_11_OR_LATER = require("resty.openssl.version").OPENSSL_11_OR_LATER
local OPENSSL_3X = require("resty.openssl.version").OPENSSL_3X
local BORINGSSL = require("resty.openssl.version").BORINGSSL

local _M = {}
local mt = { __index = _M }

_M.verify_flags = x509_vfy_macro.verify_flags
local flag_crl_check = _M.verify_flags.X509_V_FLAG_CRL_CHECK

local x509_store_ptr_ct = ffi.typeof('X509_STORE*')

function _M.new()
  local ctx = C.X509_STORE_new()
  if ctx == nil then
    return nil, "x509.store.new: X509_STORE_new() failed"
  end
  ffi_gc(ctx, C.X509_STORE_free)

  local self = setmetatable({
    ctx = ctx,
    _elem_refs = {},
    _elem_refs_idx = 1,
  }, mt)

  return self, nil
end

function _M.istype(l)
  return l and l.ctx and ffi.istype(x509_store_ptr_ct, l.ctx)
end

function _M:use_default(properties)
  if x509_vfy_macro.X509_STORE_set_default_paths(self.ctx, ctx_lib.get_libctx(), properties) ~= 1 then
    return false, format_all_error("x509.store:use_default")
  end
  return true
end

function _M:add(item, skip_set_flags)
  local dup
  local err
  if x509_lib.istype(item) then
    dup = C.X509_dup(item.ctx)
    if dup == nil then
      return false, "x509.store:add: X509_dup() failed"
    end
    -- ref counter of dup is increased by 1
    if C.X509_STORE_add_cert(self.ctx, dup) ~= 1 then
      err = format_all_error("x509.store:add: X509_STORE_add_cert")
    end
    -- decrease the dup ctx ref count immediately to make leak test happy
    C.X509_free(dup)
  elseif crl_lib.istype(item) then
    dup = C.X509_CRL_dup(item.ctx)
    if dup == nil then
      return false, "x509.store:add: X509_CRL_dup() failed"
    end
    -- ref counter of dup is increased by 1
    if C.X509_STORE_add_crl(self.ctx, dup) ~= 1 then
      err = format_all_error("x509.store:add: X509_STORE_add_crl")
    end

    -- define X509_V_FLAG_CRL_CHECK                   0x4
    -- enables CRL checking for the certificate chain leaf certificate.
    -- An error occurs if a suitable CRL cannot be found.
    -- Note: this does not check for certificates in the chain.
    if not skip_set_flags and C.X509_STORE_set_flags(self.ctx, 0x4) ~= 1 then
      return false, format_error("x509.store:add: X509_STORE_set_flags")
    end
    -- decrease the dup ctx ref count immediately to make leak test happy
    C.X509_CRL_free(dup)
  else
    return false, "x509.store:add: expect an x509 or crl instance at #1"
  end

  if err then
    return false, err
  end

  -- X509_STORE doesn't have stack gc handler, we need to gc by ourselves
  self._elem_refs[self._elem_refs_idx] = dup
  self._elem_refs_idx = self._elem_refs_idx + 1

  return true
end

function _M:load_file(path, properties)
  if type(path) ~= "string" then
    return false, "x509.store:load_file: expect a string at #1"
  else
    if x509_vfy_macro.X509_STORE_load_locations(self.ctx, path, nil,
                      ctx_lib.get_libctx(), properties) ~= 1 then
      return false, format_all_error("x509.store:load_file")
    end
  end

  return true
end

function _M:load_directory(path, properties)
  if type(path) ~= "string" then
    return false, "x509.store:load_directory expect a string at #1"
  else
    if x509_vfy_macro.X509_STORE_load_locations(self.ctx, nil, path,
                      ctx_lib.get_libctx(), properties) ~= 1 then
      return false, format_all_error("x509.store:load_directory")
    end
  end

  return true
end

function _M:set_depth(depth)
  depth = depth and tonumber(depth)
  if not depth then
    return nil, "x509.store:set_depth: expect a number at #1"
  end

  if C.X509_STORE_set_depth(self.ctx, depth) ~= 1 then
    return false, format_error("x509.store:set_depth")
  end

  return true
end

function _M:set_purpose(purpose)
  if type(purpose) ~= "string" then
    return nil, "x509.store:set_purpose: expect a string at #1"
  end

  local pchar = ffi.new("char[?]", #purpose, purpose)
  local idx = C.X509_PURPOSE_get_by_sname(pchar)
  idx = tonumber(idx)

  if idx == -1 then
    return false, "invalid purpose \"" .. purpose .. "\""
  end

  local purp = C.X509_PURPOSE_get0(idx)
  local i = C.X509_PURPOSE_get_id(purp)

  if C.X509_STORE_set_purpose(self.ctx, i) ~= 1 then
    return false, format_error("x509.store:set_purpose: X509_STORE_set_purpose")
  end

  return true
end

function _M:set_flags(...)
  local flag = 0
  for _, f in ipairs({...}) do
    flag = bor(flag, f)
  end

  if C.X509_STORE_set_flags(self.ctx, flag) ~= 1 then
    return false, format_error("x509.store:set_flags: X509_STORE_set_flags")
  end

  return true
end

function _M:verify(x509, chain, return_chain, properties, verify_method, flags)
  if not x509_lib.istype(x509) then
    return nil, "x509.store:verify: expect a x509 instance at #1"
  elseif chain and not chain_lib.istype(chain) then
    return nil, "x509.store:verify: expect a x509.chain instance at #1"
  end

  local ctx
  if OPENSSL_3X then
    ctx = C.X509_STORE_CTX_new_ex(ctx_lib.get_libctx(), properties)
  else
    ctx = C.X509_STORE_CTX_new()
  end
  if ctx == nil then
    return nil, "x509.store:verify: X509_STORE_CTX_new() failed"
  end

  ffi_gc(ctx, C.X509_STORE_CTX_free)

  local chain_dup_ctx
  if chain then
    local chain_dup, err = chain_lib.dup(chain.ctx)
    if err then
      return nil, err
    end
    chain_dup_ctx = chain_dup.ctx
  end

  if C.X509_STORE_CTX_init(ctx, self.ctx, x509.ctx, chain_dup_ctx) ~= 1 then
    return nil, format_error("x509.store:verify: X509_STORE_CTX_init")
  end

  if verify_method and C.X509_STORE_CTX_set_default(ctx, verify_method) ~= 1 then
    return nil, "x509.store:verify: invalid verify_method \"" .. verify_method .. "\""
  end

  if flags then
    C.X509_STORE_CTX_set_flags(ctx, flags)
  end

  local code = C.X509_verify_cert(ctx)
  if code == 1 then -- verified
    if not return_chain then
      return true, nil
    end
    local ret_chain_ctx = x509_vfy_macro.X509_STORE_CTX_get0_chain(ctx)
    return chain_lib.dup(ret_chain_ctx)
  elseif code == 0 then -- unverified
    local vfy_code = C.X509_STORE_CTX_get_error(ctx)

    return nil, ffi_str(C.X509_verify_cert_error_string(vfy_code))
  end

  -- error
  return nil, format_error("x509.store:verify: X509_verify_cert", code)

end

function _M:check_revocation(verified_chain, properties)
  if BORINGSSL then
    return nil, "x509.store:check_revocation: this API is not supported in BoringSSL"
  end

  if not OPENSSL_11_OR_LATER then
    return nil, "x509.store:check_revocation: this API is supported from OpenSSL 1.1.0"
  end

  if not verified_chain or not chain_lib.istype(verified_chain) then
    return nil, "x509.store:check_revocation: expect a x509.chain instance at #1"
  end

  local ctx
  if OPENSSL_3X then
    ctx = C.X509_STORE_CTX_new_ex(ctx_lib.get_libctx(), properties)
  else
    ctx = C.X509_STORE_CTX_new()
  end
  if ctx == nil then
    return nil, "x509.store:check_revocation: X509_STORE_CTX_new() failed"
  end

  ffi_gc(ctx, C.X509_STORE_CTX_free)

  if C.X509_STORE_CTX_init(ctx, self.ctx, nil, nil) ~= 1 then
    return nil, format_error("x509.store:check_revocation: X509_STORE_CTX_init")
  end

  C.X509_STORE_CTX_set0_verified_chain(ctx, verified_chain.ctx)

  -- enables CRL checking for the certificate chain leaf certificate.
  -- An error occurs if a suitable CRL cannot be found.
  C.X509_STORE_CTX_set_flags(ctx, flag_crl_check)

  local check_revocation = C.X509_STORE_CTX_get_check_revocation(ctx)
  local code = check_revocation(ctx)
  if code == 1 then -- succeess
    return true, nil
  else
    local vfy_code = C.X509_STORE_CTX_get_error(ctx)
    return nil, ffi_str(C.X509_verify_cert_error_string(vfy_code))
  end
end

return _M
