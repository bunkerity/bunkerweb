local ffi = require "ffi"
local C = ffi.C
local ffi_gc = ffi.gc

require "resty.openssl.include.x509.crl"
require "resty.openssl.include.x509.revoked"
local bn_lib = require("resty.openssl.bn")
local format_error = require("resty.openssl.err").format_error

local _M = {}
local mt = { __index = _M }

local x509_revoked_ptr_ct = ffi.typeof('X509_REVOKED*')

local NID_crl_reason = C.OBJ_txt2nid("CRLReason")
assert(NID_crl_reason > 0)

--- Creates new instance of X509_REVOKED data
-- @tparam bn|number sn Serial number as number or bn instance
-- @tparam number time Revocation time
-- @tparam number reason Revocation reason
-- @treturn table instance of the module or nil
-- @treturn[opt] string Returns optional error message in case of error
function _M.new(sn, time, reason)
  --- only convert to bn if it is number
  if type(sn) == "number"then
    sn = bn_lib.new(sn)
  end
  if not bn_lib.istype(sn) then
    return nil, "x509.revoked.new: sn should be number or a bn instance"
  end

  if type(time) ~= "number" then
    return nil, "x509.revoked.new: expect a number at #2"
  end
  if type(reason) ~= "number" then
    return nil, "x509.revoked.new: expect a number at #3"
  end

  local ctx = C.X509_REVOKED_new()
  ffi_gc(ctx, C.X509_REVOKED_free)

  -- serial number
  local sn_asn1 = C.BN_to_ASN1_INTEGER(sn.ctx, nil)
  if sn_asn1 == nil then
    return nil, "x509.revoked.new: BN_to_ASN1_INTEGER() failed"
  end
  ffi_gc(sn_asn1, C.ASN1_INTEGER_free)

  if C.X509_REVOKED_set_serialNumber(ctx, sn_asn1) == 0 then
    return nil, format_error("x509.revoked.new: X509_REVOKED_set_serialNumber()")
  end

  -- time
  time = C.ASN1_TIME_set(nil, time)
  if time == nil then
    return nil, format_error("x509.revoked.new: ASN1_TIME_set()")
  end
  ffi_gc(time, C.ASN1_STRING_free)

  if C.X509_REVOKED_set_revocationDate(ctx, time) == 0 then
    return nil, format_error("x509.revoked.new: X509_REVOKED_set_revocationDate()")
  end

  -- reason
  local reason_asn1 = C.ASN1_ENUMERATED_new()
  if reason_asn1 == nil then
    return nil, "x509.revoked.new: ASN1_ENUMERATED_new() failed"
  end
  ffi_gc(reason_asn1, C.ASN1_ENUMERATED_free)

  local reason_ext = C.X509_EXTENSION_new()
  if reason_ext == nil then
    return nil, "x509.revoked.new: X509_EXTENSION_new() failed"
  end
  ffi_gc(reason_ext, C.X509_EXTENSION_free)

  if C.ASN1_ENUMERATED_set(reason_asn1, reason) == 0 then
    return nil, format_error("x509.revoked.new: ASN1_ENUMERATED_set()")
  end

  if C.X509_EXTENSION_set_data(reason_ext, reason_asn1) == 0 then
    return nil, format_error("x509.revoked.new: X509_EXTENSION_set_data()")
  end

  if C.X509_EXTENSION_set_object(reason_ext, C.OBJ_nid2obj(NID_crl_reason)) == 0 then
    return nil, format_error("x509.revoked.new: X509_EXTENSION_set_object()")
  end

  if C.X509_REVOKED_add_ext(ctx, reason_ext, 0) == 0 then
    return nil, format_error("x509.revoked.new: X509_EXTENSION_set_object()")
  end

  local self = setmetatable({
    ctx = ctx,
  }, mt)

  return self, nil
end

--- Type check
-- @tparam table Instance of revoked module
-- @treturn boolean true if instance is instance of revoked module false otherwise
function _M.istype(l)
  return l and l.ctx and ffi.istype(x509_revoked_ptr_ct, l.ctx)
end

return _M
