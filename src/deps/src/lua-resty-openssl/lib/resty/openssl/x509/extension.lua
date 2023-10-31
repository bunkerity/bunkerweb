local ffi = require "ffi"
local C = ffi.C
local ffi_gc = ffi.gc
local ffi_new = ffi.new
local ffi_cast = ffi.cast
local ffi_str = ffi.string

require "resty.openssl.include.x509"
require "resty.openssl.include.x509.extension"
require "resty.openssl.include.x509v3"
require "resty.openssl.include.bio"
require "resty.openssl.include.conf"
local asn1_macro = require("resty.openssl.include.asn1")
local objects_lib = require "resty.openssl.objects"
local stack_lib = require("resty.openssl.stack")
local bio_util = require "resty.openssl.auxiliary.bio"
local format_error = require("resty.openssl.err").format_error
local OPENSSL_3X = require("resty.openssl.version").OPENSSL_3X
local BORINGSSL = require("resty.openssl.version").BORINGSSL

local _M = {}
local mt = { __index = _M }

local x509_extension_ptr_ct = ffi.typeof("X509_EXTENSION*")

local extension_types = {
  issuer  = "resty.openssl.x509",
  subject = "resty.openssl.x509",
  request = "resty.openssl.x509.csr",
  crl     = "resty.openssl.x509.crl",
}

if OPENSSL_3X then
  extension_types["issuer_pkey"] = "resty.openssl.pkey"
end

local nconf_load
if BORINGSSL then
  nconf_load = function()
    return nil, "NCONF_load_bio not exported in BoringSSL"
  end
else
  nconf_load = function(conf, str)
    local bio = C.BIO_new_mem_buf(str, #str)
    if bio == nil then
      return format_error("BIO_new_mem_buf")
    end
    ffi_gc(bio, C.BIO_free)

    if C.NCONF_load_bio(conf, bio, nil) ~= 1 then
      return format_error("NCONF_load_bio")
    end
  end
end

function _M.new(txtnid, value, data)
  local nid, err = objects_lib.txtnid2nid(txtnid)
  if err then
    return nil, "x509.extension.new: " .. err
  end
  if type(value) ~= 'string' then
    return nil, "x509.extension.new: expect string at #2"
  end
  -- get a ptr and also zerofill the struct
  local x509_ctx_ptr = ffi_new('X509V3_CTX[1]')

  local conf = C.NCONF_new(nil)
	if conf == nil then
    return nil, format_error("NCONF_new")
  end
  ffi_gc(conf, C.NCONF_free)

  if type(data) == 'table' then
    local args = {}
    if data.db then
      if type(data.db) ~= 'string' then
        return nil, "x509.extension.new: expect data.db must be a string"
      end
      err = nconf_load(conf, data)
      if err then
        return nil, "x509.extension.new: " .. err
      end
    end

    for k, t in pairs(extension_types) do
      if data[k] then
        local lib = require(t)
        if not lib.istype(data[k]) then
          return nil, "x509.extension.new: expect data." .. k .. " to be a " .. t .. " instance"
        end
        args[k] = data[k].ctx
      end
    end
    C.X509V3_set_ctx(x509_ctx_ptr[0], args.issuer, args.subject, args.request, args.crl, 0)

    if OPENSSL_3X and args.issuer_pkey then
      if C.X509V3_set_issuer_pkey(x509_ctx_ptr[0], args.issuer_pkey) ~= 1 then
        return nil, format_error("x509.extension.new: X509V3_set_issuer_pkey")
      end
    end

  elseif type(data) == 'string' then
    err = nconf_load(conf, data)
    if err then
      return nil, "x509.extension.new: " .. err
    end
  elseif data then
    return nil, "x509.extension.new: expect nil, string a table at #3"
  end

  -- setting conf is required for some extensions to load
  -- crypto/x509/v3_conf.c:do_ext_conf "else if (method->r2i) {" branch
  C.X509V3_set_nconf(x509_ctx_ptr[0], conf)

  local ctx = C.X509V3_EXT_nconf_nid(conf, x509_ctx_ptr[0], nid, value)
  if ctx == nil then
    return nil, format_error("x509.extension.new")
  end
  ffi_gc(ctx, C.X509_EXTENSION_free)

  local self = setmetatable({
    ctx = ctx,
  }, mt)

  return self, nil
end

function _M.istype(l)
  return l and l.ctx and ffi.istype(x509_extension_ptr_ct, l.ctx)
end

function _M.dup(ctx)
  if not ffi.istype(x509_extension_ptr_ct, ctx) then
    return nil, "x509.extension.dup: expect a x509.extension ctx at #1"
  end
  local ctx = C.X509_EXTENSION_dup(ctx)
  if ctx == nil then
    return nil, "x509.extension.dup: X509_EXTENSION_dup() failed"
  end

  ffi_gc(ctx, C.X509_EXTENSION_free)

  local self = setmetatable({
    ctx = ctx,
  }, mt)

  return self, nil
end

function _M.from_der(value, txtnid, crit)
  local nid, err = objects_lib.txtnid2nid(txtnid)
  if err then
    return nil, "x509.extension.from_der: " .. err
  end
  if type(value) ~= 'string' then
    return nil, "x509.extension.from_der: expect string at #1"
  end

  local asn1 = C.ASN1_STRING_new()
  if asn1 == nil then
    return nil, format_error("x509.extension.from_der: ASN1_STRING_new")
  end
  ffi_gc(asn1, C.ASN1_STRING_free)

  if C.ASN1_STRING_set(asn1, value, #value) ~= 1 then
    return nil, format_error("x509.extension.from_der: ASN1_STRING_set")
  end

  local ctx = C.X509_EXTENSION_create_by_NID(nil, nid, crit and 1 or 0, asn1)
  if ctx == nil then
    return nil, format_error("x509.extension.from_der: X509_EXTENSION_create_by_NID")
  end
  ffi_gc(ctx, C.X509_EXTENSION_free)

  local self = setmetatable({
    ctx = ctx,
  }, mt)

  return self, nil
end

function _M:to_der()
  local asn1 = C.X509_EXTENSION_get_data(self.ctx)

  return ffi_str(asn1_macro.ASN1_STRING_get0_data(asn1))
end

function _M.from_data(any, txtnid, crit)
  local nid, err = objects_lib.txtnid2nid(txtnid)
  if err then
    return nil, "x509.extension.from_der: " .. err
  end

  if type(any) ~= "table" or type(any.ctx) ~= "cdata" then
    return nil, "x509.extension.from_data: expect a table with ctx at #1"
  elseif type(nid) ~= "number" then
    return nil, "x509.extension.from_data: expect a table at #2"
  end

  local ctx = C.X509V3_EXT_i2d(nid, crit and 1 or 0, any.ctx)
  if ctx == nil then
    return nil, format_error("x509.extension.from_data: X509V3_EXT_i2d")
  end
  ffi_gc(ctx, C.X509_EXTENSION_free)

  local self = setmetatable({
    ctx = ctx,
  }, mt)

  return self, nil
end

local NID_subject_alt_name = C.OBJ_sn2nid("subjectAltName")
assert(NID_subject_alt_name ~= 0)

function _M.to_data(extension, nid)
  if not _M.istype(extension) then
    return nil, "x509.extension.dup: expect a x509.extension ctx at #1"
  elseif type(nid) ~= "number" then
    return nil, "x509.extension.to_data: expect a table at #2"
  end

  local void_ptr = C.X509V3_EXT_d2i(extension.ctx)
  if void_ptr == nil then
    return nil, format_error("x509.extension:to_data: X509V3_EXT_d2i")
  end

  if nid == NID_subject_alt_name then
    -- Note: here we only free the stack itself not elements
    -- since there seems no way to increase ref count for a GENERAL_NAME
    -- we left the elements referenced by the new-dup'ed stack
    ffi_gc(void_ptr, stack_lib.gc_of("GENERAL_NAME"))
    local got = ffi_cast("GENERAL_NAMES*", void_ptr)
    local lib = require("resty.openssl.x509.altname")
    -- the internal ptr is returned, ie we need to copy it
    return lib.dup(got)
  end

  return nil, string.format("x509.extension:to_data: don't know how to convert to NID %d", nid)
end

function _M:get_object()
  -- retruns the internal pointer
  local asn1 = C.X509_EXTENSION_get_object(self.ctx)

  return objects_lib.obj2table(asn1)
end

function _M:get_critical()
  return C.X509_EXTENSION_get_critical(self.ctx) == 1
end

function _M:set_critical(crit)
  if C.X509_EXTENSION_set_critical(self.ctx, crit and 1 or 0) ~= 1 then
    return false, format_error("x509.extension:set_critical")
  end
  return true
end

function _M:tostring()
  local ret, err = bio_util.read_wrap(C.X509V3_EXT_print, self.ctx, 0, 0)
  if not err then
    return ret
  end
  -- fallback to ASN.1 print
  local asn1 = C.X509_EXTENSION_get_data(self.ctx)
  return bio_util.read_wrap(C.ASN1_STRING_print, asn1)
end

_M.text = _M.tostring

mt.__tostring = function(tbl)
  local txt, err = _M.text(tbl)
  if err then
    error(err)
  end
  return txt
end


return _M
