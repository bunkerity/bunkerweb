local ffi = require "ffi"
local C = ffi.C
local ffi_gc = ffi.gc
local ffi_str = ffi.string
local ffi_cast = ffi.cast

require "resty.openssl.include.x509"
require "resty.openssl.include.x509v3"
require "resty.openssl.include.evp"
require "resty.openssl.include.objects"
local stack_macro = require("resty.openssl.include.stack")
local stack_lib = require("resty.openssl.stack")
local asn1_lib = require("resty.openssl.asn1")
local digest_lib = require("resty.openssl.digest")
local extension_lib = require("resty.openssl.x509.extension")
local pkey_lib = require("resty.openssl.pkey")
local bio_util = require "resty.openssl.auxiliary.bio"
local txtnid2nid = require("resty.openssl.objects").txtnid2nid
local find_sigid_algs = require("resty.openssl.objects").find_sigid_algs
local ctypes = require "resty.openssl.auxiliary.ctypes"
local ctx_lib = require "resty.openssl.ctx"
local format_error = require("resty.openssl.err").format_error
local version = require("resty.openssl.version")
local OPENSSL_10 = version.OPENSSL_10
local OPENSSL_11_OR_LATER = version.OPENSSL_11_OR_LATER
local OPENSSL_3X = version.OPENSSL_3X
local BORINGSSL = version.BORINGSSL
local BORINGSSL_110 = version.BORINGSSL_110 -- used in boringssl-fips-20190808

-- accessors provides an openssl version neutral interface to lua layer
-- it doesn't handle any error, expect that to be implemented in
-- _M.set_X or _M.get_X
local accessors = {}

accessors.get_pubkey = C.X509_get_pubkey -- returns new evp_pkey instance, don't need to dup
accessors.set_pubkey = C.X509_set_pubkey
accessors.set_version = C.X509_set_version
accessors.set_serial_number = C.X509_set_serialNumber
accessors.get_subject_name = C.X509_get_subject_name -- returns internal ptr, we dup it
accessors.set_subject_name = C.X509_set_subject_name
accessors.get_issuer_name = C.X509_get_issuer_name -- returns internal ptr, we dup it
accessors.set_issuer_name = C.X509_set_issuer_name
accessors.get_signature_nid = C.X509_get_signature_nid

-- generally, use get1 if we return a lua table wrapped ctx which doesn't support dup.
-- in that case, a new struct is returned from C api, and we will handle gc.
-- openssl will increment the reference count for returned ptr, and won't free it when
-- parent struct is freed.
-- otherwise, use get0, which returns an internal pointer, we don't need to free it up.
-- it will be gone together with the parent struct.

if BORINGSSL_110 then
  accessors.get_not_before = C.X509_get0_notBefore -- returns internal ptr, we convert to number
  accessors.set_not_before = C.X509_set_notBefore
  accessors.get_not_after = C.X509_get0_notAfter -- returns internal ptr, we convert to number
  accessors.set_not_after = C.X509_set_notAfter
  accessors.get_version = function(x509)
    if x509 == nil or x509.cert_info == nil or x509.cert_info.validity == nil then
      return nil
    end
    return C.ASN1_INTEGER_get(x509.cert_info.version)
  end
  accessors.get_serial_number = C.X509_get_serialNumber -- returns internal ptr, we convert to bn
elseif OPENSSL_11_OR_LATER then
  accessors.get_not_before = C.X509_get0_notBefore -- returns internal ptr, we convert to number
  accessors.set_not_before = C.X509_set1_notBefore
  accessors.get_not_after = C.X509_get0_notAfter -- returns internal ptr, we convert to number
  accessors.set_not_after = C.X509_set1_notAfter
  accessors.get_version = C.X509_get_version -- returns int
  accessors.get_serial_number = C.X509_get0_serialNumber -- returns internal ptr, we convert to bn
elseif OPENSSL_10 then
  accessors.get_not_before = function(x509)
    if x509 == nil or x509.cert_info == nil or x509.cert_info.validity == nil then
      return nil
    end
    return x509.cert_info.validity.notBefore
  end
  accessors.set_not_before = C.X509_set_notBefore
  accessors.get_not_after = function(x509)
    if x509 == nil or x509.cert_info == nil or x509.cert_info.validity == nil then
      return nil
    end
    return x509.cert_info.validity.notAfter
  end
  accessors.set_not_after = C.X509_set_notAfter
  accessors.get_version = function(x509)
    if x509 == nil or x509.cert_info == nil or x509.cert_info.validity == nil then
      return nil
    end
    return C.ASN1_INTEGER_get(x509.cert_info.version)
  end
  accessors.get_serial_number = C.X509_get_serialNumber -- returns internal ptr, we convert to bn
end

local function __tostring(self, fmt)
  if not fmt or fmt == 'PEM' then
    return bio_util.read_wrap(C.PEM_write_bio_X509, self.ctx)
  elseif fmt == 'DER' then
    return bio_util.read_wrap(C.i2d_X509_bio, self.ctx)
  else
    return nil, "x509:tostring: can only write PEM or DER format, not " .. fmt
  end
end

local _M = {}
local mt = { __index = _M, __tostring = __tostring }


local x509_ptr_ct = ffi.typeof("X509*")

-- only PEM format is supported for now
function _M.new(cert, fmt, properties)
  local ctx
  if not cert then
    -- routine for create a new cert
    if OPENSSL_3X then
      ctx = C.X509_new_ex(ctx_lib.get_libctx(), properties)
    else
      ctx = C.X509_new()
    end
    if ctx == nil then
      return nil, format_error("x509.new")
    end
    ffi_gc(ctx, C.X509_free)

    C.X509_gmtime_adj(accessors.get_not_before(ctx), 0)
    C.X509_gmtime_adj(accessors.get_not_after(ctx), 0)
  elseif type(cert) == "string" then
    -- routine for load an existing cert
    local bio = C.BIO_new_mem_buf(cert, #cert)
    if bio == nil then
      return nil, format_error("x509.new: BIO_new_mem_buf")
    end

    fmt = fmt or "*"
    while true do -- luacheck: ignore 512 -- loop is executed at most once
      if fmt == "PEM" or fmt == "*" then
        ctx = C.PEM_read_bio_X509(bio, nil, nil, nil)
        if ctx ~= nil then
          break
        elseif fmt == "*" then
          -- BIO_reset; #define BIO_CTRL_RESET 1
          local code = C.BIO_ctrl(bio, 1, 0, nil)
          if code ~= 1 then
            C.BIO_free(bio)
            return nil, "x509.new: BIO_ctrl() failed: " .. code
          end
        end
      end
      if fmt == "DER" or fmt == "*" then
        ctx = C.d2i_X509_bio(bio, nil)
      end
      break
    end
    C.BIO_free(bio)
    if ctx == nil then
      return nil, format_error("x509.new")
    end
    -- clear errors occur when trying
    C.ERR_clear_error()
    ffi_gc(ctx, C.X509_free)
  elseif type(cert) == 'cdata' then
    if ffi.istype(x509_ptr_ct, cert) then
      ctx = cert
      ffi_gc(ctx, C.X509_free)
    else
      return nil, "x509.new: expect a X509* cdata at #1"
    end
  else
    return nil, "x509.new: expect nil or a string at #1"
  end

  local self = setmetatable({
    ctx = ctx,
  }, mt)

  return self, nil
end

function _M.istype(l)
  return l and l.ctx and ffi.istype(x509_ptr_ct, l.ctx)
end

function _M.dup(ctx)
  if not ffi.istype(x509_ptr_ct, ctx) then
    return nil, "x509.dup: expect a x509 ctx at #1"
  end
  local ctx = C.X509_dup(ctx)
  if ctx == nil then
    return nil, "x509.dup: X509_dup() failed"
  end

  ffi_gc(ctx, C.X509_free)

  local self = setmetatable({
    ctx = ctx,
  }, mt)

  return self, nil
end

function _M:tostring(fmt)
  return __tostring(self, fmt)
end

function _M:to_PEM()
  return __tostring(self, "PEM")
end

function _M:set_lifetime(not_before, not_after)
  local ok, err
  if not_before then
    ok, err = self:set_not_before(not_before)
    if err then
      return ok, err
    end
  end

  if not_after then
    ok, err = self:set_not_after(not_after)
    if err then
      return ok, err
    end
  end

  return true
end

function _M:get_lifetime()
  local not_before, err = self:get_not_before()
  if not_before == nil then
    return nil, nil, err
  end
  local not_after, err = self:get_not_after()
  if not_after == nil then
    return nil, nil, err
  end

  return not_before, not_after, nil
end

-- note: index is 0 based
local OPENSSL_STRING_value_at = function(ctx, i)
  local ct = ffi_cast("OPENSSL_STRING", stack_macro.OPENSSL_sk_value(ctx, i))
  if ct == nil then
    return nil
  end
  return ffi_str(ct)
end

function _M:get_ocsp_url(return_all)
  local st = C.X509_get1_ocsp(self.ctx)

  local count = stack_macro.OPENSSL_sk_num(st)
  if count == 0 then
    return
  end

  local ret
  if return_all then
    ret = {}
    for i=0,count-1 do
      ret[i+1] = OPENSSL_STRING_value_at(st, i)
    end
  else
    ret = OPENSSL_STRING_value_at(st, 0)
  end

  C.X509_email_free(st)
  return ret
end

function _M:get_ocsp_request()

end

function _M:get_crl_url(return_all)
  local cdp, err = self:get_crl_distribution_points()
  if err then
    return nil, err
  end

  if not cdp or cdp:count() == 0 then
    return
  end

  if return_all then
    local ret = {}
    local cdp_iter = cdp:each()
    while true do
      local _, gn = cdp_iter()
      if not gn then
        break
      end
      local gn_iter = gn:each()
      while true do
        local k, v = gn_iter()
        if not k then
          break
        elseif k == "URI" then
          table.insert(ret, v)
        end
      end
    end
    return ret
  else
    local gn, err = cdp:index(1)
    if err then
      return nil, err
    end
    local iter = gn:each()
    while true do
      local k, v = iter()
      if not k then
        break
      elseif k == "URI" then
        return v
      end
    end
  end
end

local digest_length = ctypes.ptr_of_uint()
local digest_buf, digest_buf_size
local function digest(self, cfunc, typ, properties)
  -- TODO: dedup the following with resty.openssl.digest
  local ctx
  if OPENSSL_11_OR_LATER then
    ctx = C.EVP_MD_CTX_new()
    ffi_gc(ctx, C.EVP_MD_CTX_free)
  elseif OPENSSL_10 then
    ctx = C.EVP_MD_CTX_create()
    ffi_gc(ctx, C.EVP_MD_CTX_destroy)
  end
  if ctx == nil then
    return nil, "x509:digest: failed to create EVP_MD_CTX"
  end

  local algo
  if OPENSSL_3X then
    algo = C.EVP_MD_fetch(ctx_lib.get_libctx(), typ or 'sha1', properties)
  else
    algo = C.EVP_get_digestbyname(typ or 'sha1')
  end
  if algo == nil then
    return nil, string.format("x509:digest: invalid digest type \"%s\"", typ)
  end

  local md_size = OPENSSL_3X and C.EVP_MD_get_size(algo) or C.EVP_MD_size(algo)
  if not digest_buf or digest_buf_size < md_size then
    digest_buf = ctypes.uchar_array(md_size)
    digest_buf_size = md_size
  end

  if cfunc(self.ctx, algo, digest_buf, digest_length) ~= 1 then
    return nil, format_error("x509:digest")
  end

  return ffi_str(digest_buf, digest_length[0])
end

function _M:digest(typ, properties)
  return digest(self, C.X509_digest, typ, properties)
end

function _M:pubkey_digest(typ, properties)
  return digest(self, C.X509_pubkey_digest, typ, properties)
end

function _M:check_private_key(key)
  if not pkey_lib.istype(key) then
    return false, "x509:check_private_key: except a pkey instance at #1"
  end

  if not key:is_private() then
    return false, "x509:check_private_key: not a private key"
  end

  if C.X509_check_private_key(self.ctx, key.ctx) == 1 then
    return true
  end
  return false, format_error("x509:check_private_key")
end

-- START AUTO GENERATED CODE

-- AUTO GENERATED
function _M:sign(pkey, digest)
  if not pkey_lib.istype(pkey) then
    return false, "x509:sign: expect a pkey instance at #1"
  end

  local digest_algo
  if digest then
    if not digest_lib.istype(digest) then
      return false, "x509:sign: expect a digest instance at #2"
    elseif not digest.algo then
      return false, "x509:sign: expect a digest instance to have algo member"
    end
    digest_algo = digest.algo
  elseif BORINGSSL then
    digest_algo = C.EVP_get_digestbyname('sha256')
  end

  -- returns size of signature if success
  if C.X509_sign(self.ctx, pkey.ctx, digest_algo) == 0 then
    return false, format_error("x509:sign")
  end

  return true
end

-- AUTO GENERATED
function _M:verify(pkey)
  if not pkey_lib.istype(pkey) then
    return false, "x509:verify: expect a pkey instance at #1"
  end

  local code = C.X509_verify(self.ctx, pkey.ctx)
  if code == 1 then
    return true
  elseif code == 0 then
    return false
  else -- typically -1
    return false, format_error("x509:verify", code)
  end
end

-- AUTO GENERATED
local function get_extension(ctx, nid_txt, last_pos)
  last_pos = (last_pos or 0) - 1
  local nid, err = txtnid2nid(nid_txt)
  if err then
    return nil, nil, err
  end
  local pos = C.X509_get_ext_by_NID(ctx, nid, last_pos)
  if pos == -1 then
    return nil
  end
  local ctx = C.X509_get_ext(ctx, pos)
  if ctx == nil then
    return nil, nil, format_error()
  end
  return ctx, pos
end

-- AUTO GENERATED
function _M:add_extension(extension)
  if not extension_lib.istype(extension) then
    return false, "x509:add_extension: expect a x509.extension instance at #1"
  end

  -- X509_add_ext returnes the stack on success, and NULL on error
  -- the X509_EXTENSION ctx is dupped internally
  if C.X509_add_ext(self.ctx, extension.ctx, -1) == nil then
    return false, format_error("x509:add_extension")
  end

  return true
end

-- AUTO GENERATED
function _M:get_extension(nid_txt, last_pos)
  local ctx, pos, err = get_extension(self.ctx, nid_txt, last_pos)
  if err then
    return nil, nil, "x509:get_extension: " .. err
  end
  local ext, err = extension_lib.dup(ctx)
  if err then
    return nil, nil, "x509:get_extension: " .. err
  end
  return ext, pos+1
end

local X509_delete_ext
if OPENSSL_11_OR_LATER then
  X509_delete_ext = C.X509_delete_ext
elseif OPENSSL_10 then
  X509_delete_ext = function(ctx, pos)
    return C.X509v3_delete_ext(ctx.cert_info.extensions, pos)
  end
else
  X509_delete_ext = function(...)
    error("X509_delete_ext undefined")
  end
end

-- AUTO GENERATED
function _M:set_extension(extension, last_pos)
  if not extension_lib.istype(extension) then
    return false, "x509:set_extension: expect a x509.extension instance at #1"
  end

  last_pos = (last_pos or 0) - 1

  local nid = extension:get_object().nid
  local pos = C.X509_get_ext_by_NID(self.ctx, nid, last_pos)
  -- pos may be -1, which means not found, it's fine, we will add new one instead of replace

  local removed = X509_delete_ext(self.ctx, pos)
  C.X509_EXTENSION_free(removed)

  if C.X509_add_ext(self.ctx, extension.ctx, pos) == nil then
    return false, format_error("x509:set_extension")
  end

  return true
end

-- AUTO GENERATED
function _M:set_extension_critical(nid_txt, crit, last_pos)
  local ctx, _, err = get_extension(self.ctx, nid_txt, last_pos)
  if err then
    return nil, "x509:set_extension_critical: " .. err
  end

  if C.X509_EXTENSION_set_critical(ctx, crit and 1 or 0) ~= 1 then
    return false, format_error("x509:set_extension_critical")
  end

  return true
end

-- AUTO GENERATED
function _M:get_extension_critical(nid_txt, last_pos)
  local ctx, _, err = get_extension(self.ctx, nid_txt, last_pos)
  if err then
    return nil, "x509:get_extension_critical: " .. err
  end

  return C.X509_EXTENSION_get_critical(ctx) == 1
end

-- AUTO GENERATED
function _M:get_serial_number()
  local got = accessors.get_serial_number(self.ctx)
  if got == nil then
    return nil
  end

  -- returns a new BIGNUM instance
  got = C.ASN1_INTEGER_to_BN(got, nil)
  if got == nil then
    return false, format_error("x509:set: BN_to_ASN1_INTEGER")
  end
  -- bn will be duplicated thus this ctx should be freed up
  ffi_gc(got, C.BN_free)

  local lib = require("resty.openssl.bn")
  -- the internal ptr is returned, ie we need to copy it
  return lib.dup(got)
end

-- AUTO GENERATED
function _M:set_serial_number(toset)
  local lib = require("resty.openssl.bn")
  if lib.istype and not lib.istype(toset) then
    return false, "x509:set_serial_number: expect a bn instance at #1"
  end
  toset = toset.ctx

  toset = C.BN_to_ASN1_INTEGER(toset, nil)
  if toset == nil then
    return false, format_error("x509:set: BN_to_ASN1_INTEGER")
  end
  -- "A copy of the serial number is used internally
  -- so serial should be freed up after use.""
  ffi_gc(toset, C.ASN1_INTEGER_free)

  if accessors.set_serial_number(self.ctx, toset) == 0 then
    return false, format_error("x509:set_serial_number")
  end
  return true
end

-- AUTO GENERATED
function _M:get_not_before()
  local got = accessors.get_not_before(self.ctx)
  if got == nil then
    return nil
  end

  got = asn1_lib.asn1_to_unix(got)

  return got
end

-- AUTO GENERATED
function _M:set_not_before(toset)
  if type(toset) ~= "number" then
    return false, "x509:set_not_before: expect a number at #1"
  end

  toset = C.ASN1_TIME_set(nil, toset)
  ffi_gc(toset, C.ASN1_STRING_free)

  if accessors.set_not_before(self.ctx, toset) == 0 then
    return false, format_error("x509:set_not_before")
  end
  return true
end

-- AUTO GENERATED
function _M:get_not_after()
  local got = accessors.get_not_after(self.ctx)
  if got == nil then
    return nil
  end

  got = asn1_lib.asn1_to_unix(got)

  return got
end

-- AUTO GENERATED
function _M:set_not_after(toset)
  if type(toset) ~= "number" then
    return false, "x509:set_not_after: expect a number at #1"
  end

  toset = C.ASN1_TIME_set(nil, toset)
  ffi_gc(toset, C.ASN1_STRING_free)

  if accessors.set_not_after(self.ctx, toset) == 0 then
    return false, format_error("x509:set_not_after")
  end
  return true
end

-- AUTO GENERATED
function _M:get_pubkey()
  local got = accessors.get_pubkey(self.ctx)
  if got == nil then
    return nil
  end
  local lib = require("resty.openssl.pkey")
  -- returned a copied instance directly
  return lib.new(got)
end

-- AUTO GENERATED
function _M:set_pubkey(toset)
  local lib = require("resty.openssl.pkey")
  if lib.istype and not lib.istype(toset) then
    return false, "x509:set_pubkey: expect a pkey instance at #1"
  end
  toset = toset.ctx
  if accessors.set_pubkey(self.ctx, toset) == 0 then
    return false, format_error("x509:set_pubkey")
  end
  return true
end

-- AUTO GENERATED
function _M:get_subject_name()
  local got = accessors.get_subject_name(self.ctx)
  if got == nil then
    return nil
  end
  local lib = require("resty.openssl.x509.name")
  -- the internal ptr is returned, ie we need to copy it
  return lib.dup(got)
end

-- AUTO GENERATED
function _M:set_subject_name(toset)
  local lib = require("resty.openssl.x509.name")
  if lib.istype and not lib.istype(toset) then
    return false, "x509:set_subject_name: expect a x509.name instance at #1"
  end
  toset = toset.ctx
  if accessors.set_subject_name(self.ctx, toset) == 0 then
    return false, format_error("x509:set_subject_name")
  end
  return true
end

-- AUTO GENERATED
function _M:get_issuer_name()
  local got = accessors.get_issuer_name(self.ctx)
  if got == nil then
    return nil
  end
  local lib = require("resty.openssl.x509.name")
  -- the internal ptr is returned, ie we need to copy it
  return lib.dup(got)
end

-- AUTO GENERATED
function _M:set_issuer_name(toset)
  local lib = require("resty.openssl.x509.name")
  if lib.istype and not lib.istype(toset) then
    return false, "x509:set_issuer_name: expect a x509.name instance at #1"
  end
  toset = toset.ctx
  if accessors.set_issuer_name(self.ctx, toset) == 0 then
    return false, format_error("x509:set_issuer_name")
  end
  return true
end

-- AUTO GENERATED
function _M:get_version()
  local got = accessors.get_version(self.ctx)
  if got == nil then
    return nil
  end

  got = tonumber(got) + 1

  return got
end

-- AUTO GENERATED
function _M:set_version(toset)
  if type(toset) ~= "number" then
    return false, "x509:set_version: expect a number at #1"
  end

  -- Note: this is defined by standards (X.509 et al) to be one less than the certificate version.
  -- So a version 3 certificate will return 2 and a version 1 certificate will return 0.
  toset = toset - 1

  if accessors.set_version(self.ctx, toset) == 0 then
    return false, format_error("x509:set_version")
  end
  return true
end

local NID_subject_alt_name = C.OBJ_sn2nid("subjectAltName")
assert(NID_subject_alt_name ~= 0)

-- AUTO GENERATED: EXTENSIONS
function _M:get_subject_alt_name()
  local crit = ctypes.ptr_of_int()
  -- X509_get_ext_d2i returns internal pointer, always dup
  -- for now this function always returns the first found extension
  local got = C.X509_get_ext_d2i(self.ctx, NID_subject_alt_name, crit, nil)
  crit = tonumber(crit[0])
  if crit == -1 then -- not found
    return nil
  elseif crit == -2 then
    return nil, "x509:get_subject_alt_name: extension of subject_alt_name occurs more than one times, " ..
                "this is not yet implemented. Please use get_extension instead."
  elseif got == nil then
    return nil, format_error("x509:get_subject_alt_name")
  end

  -- Note: here we only free the stack itself not elements
  -- since there seems no way to increase ref count for a GENERAL_NAME
  -- we left the elements referenced by the new-dup'ed stack
  local got_ref = got
  ffi_gc(got_ref, stack_lib.gc_of("GENERAL_NAME"))
  got = ffi_cast("GENERAL_NAMES*", got_ref)
  local lib = require("resty.openssl.x509.altname")
  -- the internal ptr is returned, ie we need to copy it
  return lib.dup(got)
end

-- AUTO GENERATED: EXTENSIONS
function _M:set_subject_alt_name(toset)
  local lib = require("resty.openssl.x509.altname")
  if lib.istype and not lib.istype(toset) then
    return false, "x509:set_subject_alt_name: expect a x509.altname instance at #1"
  end
  toset = toset.ctx
  -- x509v3.h: # define X509V3_ADD_REPLACE              2L
  if C.X509_add1_ext_i2d(self.ctx, NID_subject_alt_name, toset, 0, 0x2) ~= 1 then
    return false, format_error("x509:set_subject_alt_name")
  end
  return true
end

-- AUTO GENERATED: EXTENSIONS
function _M:set_subject_alt_name_critical(crit)
  return _M.set_extension_critical(self, NID_subject_alt_name, crit)
end

-- AUTO GENERATED: EXTENSIONS
function _M:get_subject_alt_name_critical()
  return _M.get_extension_critical(self, NID_subject_alt_name)
end

local NID_issuer_alt_name = C.OBJ_sn2nid("issuerAltName")
assert(NID_issuer_alt_name ~= 0)

-- AUTO GENERATED: EXTENSIONS
function _M:get_issuer_alt_name()
  local crit = ctypes.ptr_of_int()
  -- X509_get_ext_d2i returns internal pointer, always dup
  -- for now this function always returns the first found extension
  local got = C.X509_get_ext_d2i(self.ctx, NID_issuer_alt_name, crit, nil)
  crit = tonumber(crit[0])
  if crit == -1 then -- not found
    return nil
  elseif crit == -2 then
    return nil, "x509:get_issuer_alt_name: extension of issuer_alt_name occurs more than one times, " ..
                "this is not yet implemented. Please use get_extension instead."
  elseif got == nil then
    return nil, format_error("x509:get_issuer_alt_name")
  end

  -- Note: here we only free the stack itself not elements
  -- since there seems no way to increase ref count for a GENERAL_NAME
  -- we left the elements referenced by the new-dup'ed stack
  local got_ref = got
  ffi_gc(got_ref, stack_lib.gc_of("GENERAL_NAME"))
  got = ffi_cast("GENERAL_NAMES*", got_ref)
  local lib = require("resty.openssl.x509.altname")
  -- the internal ptr is returned, ie we need to copy it
  return lib.dup(got)
end

-- AUTO GENERATED: EXTENSIONS
function _M:set_issuer_alt_name(toset)
  local lib = require("resty.openssl.x509.altname")
  if lib.istype and not lib.istype(toset) then
    return false, "x509:set_issuer_alt_name: expect a x509.altname instance at #1"
  end
  toset = toset.ctx
  -- x509v3.h: # define X509V3_ADD_REPLACE              2L
  if C.X509_add1_ext_i2d(self.ctx, NID_issuer_alt_name, toset, 0, 0x2) ~= 1 then
    return false, format_error("x509:set_issuer_alt_name")
  end
  return true
end

-- AUTO GENERATED: EXTENSIONS
function _M:set_issuer_alt_name_critical(crit)
  return _M.set_extension_critical(self, NID_issuer_alt_name, crit)
end

-- AUTO GENERATED: EXTENSIONS
function _M:get_issuer_alt_name_critical()
  return _M.get_extension_critical(self, NID_issuer_alt_name)
end

local NID_basic_constraints = C.OBJ_sn2nid("basicConstraints")
assert(NID_basic_constraints ~= 0)

-- AUTO GENERATED: EXTENSIONS
function _M:get_basic_constraints(name)
  local crit = ctypes.ptr_of_int()
  -- X509_get_ext_d2i returns internal pointer, always dup
  -- for now this function always returns the first found extension
  local got = C.X509_get_ext_d2i(self.ctx, NID_basic_constraints, crit, nil)
  crit = tonumber(crit[0])
  if crit == -1 then -- not found
    return nil
  elseif crit == -2 then
    return nil, "x509:get_basic_constraints: extension of basic_constraints occurs more than one times, " ..
                "this is not yet implemented. Please use get_extension instead."
  elseif got == nil then
    return nil, format_error("x509:get_basic_constraints")
  end

  local ctx = ffi_cast("BASIC_CONSTRAINTS*", got)

  local ca = ctx.ca == 0xFF
  local pathlen = tonumber(C.ASN1_INTEGER_get(ctx.pathlen))

  C.BASIC_CONSTRAINTS_free(ctx)

  if not name or type(name) ~= "string" then
    got = {
      ca = ca,
      pathlen = pathlen,
    }
  elseif string.lower(name) == "ca" then
    got = ca
  elseif string.lower(name) == "pathlen" then
    got = pathlen
  end

  return got
end

-- AUTO GENERATED: EXTENSIONS
function _M:set_basic_constraints(toset)
  if type(toset) ~= "table" then
    return false, "x509:set_basic_constraints: expect a table at #1"
  end

  local cfg_lower = {}
  for k, v in pairs(toset) do
    cfg_lower[string.lower(k)] = v
  end

  toset = C.BASIC_CONSTRAINTS_new()
  if toset == nil then
    return false, format_error("x509:set_BASIC_CONSTRAINTS")
  end
  ffi_gc(toset, C.BASIC_CONSTRAINTS_free)

  toset.ca = cfg_lower.ca and 0xFF or 0
  local pathlen = cfg_lower.pathlen and tonumber(cfg_lower.pathlen)
  if pathlen then
    C.ASN1_INTEGER_free(toset.pathlen)

    local asn1 = C.ASN1_STRING_type_new(pathlen)
    if asn1 == nil then
      return false, format_error("x509:set_BASIC_CONSTRAINTS: ASN1_STRING_type_new")
    end
    toset.pathlen = asn1

    local code = C.ASN1_INTEGER_set(asn1, pathlen)
    if code ~= 1 then
      return false, format_error("x509:set_BASIC_CONSTRAINTS: ASN1_INTEGER_set", code)
    end
  end

  -- x509v3.h: # define X509V3_ADD_REPLACE              2L
  if C.X509_add1_ext_i2d(self.ctx, NID_basic_constraints, toset, 0, 0x2) ~= 1 then
    return false, format_error("x509:set_basic_constraints")
  end
  return true
end

-- AUTO GENERATED: EXTENSIONS
function _M:set_basic_constraints_critical(crit)
  return _M.set_extension_critical(self, NID_basic_constraints, crit)
end

-- AUTO GENERATED: EXTENSIONS
function _M:get_basic_constraints_critical()
  return _M.get_extension_critical(self, NID_basic_constraints)
end

local NID_info_access = C.OBJ_sn2nid("authorityInfoAccess")
assert(NID_info_access ~= 0)

-- AUTO GENERATED: EXTENSIONS
function _M:get_info_access()
  local crit = ctypes.ptr_of_int()
  -- X509_get_ext_d2i returns internal pointer, always dup
  -- for now this function always returns the first found extension
  local got = C.X509_get_ext_d2i(self.ctx, NID_info_access, crit, nil)
  crit = tonumber(crit[0])
  if crit == -1 then -- not found
    return nil
  elseif crit == -2 then
    return nil, "x509:get_info_access: extension of info_access occurs more than one times, " ..
                "this is not yet implemented. Please use get_extension instead."
  elseif got == nil then
    return nil, format_error("x509:get_info_access")
  end

  -- Note: here we only free the stack itself not elements
  -- since there seems no way to increase ref count for a ACCESS_DESCRIPTION
  -- we left the elements referenced by the new-dup'ed stack
  local got_ref = got
  ffi_gc(got_ref, stack_lib.gc_of("ACCESS_DESCRIPTION"))
  got = ffi_cast("AUTHORITY_INFO_ACCESS*", got_ref)
  local lib = require("resty.openssl.x509.extension.info_access")
  -- the internal ptr is returned, ie we need to copy it
  return lib.dup(got)
end

-- AUTO GENERATED: EXTENSIONS
function _M:set_info_access(toset)
  local lib = require("resty.openssl.x509.extension.info_access")
  if lib.istype and not lib.istype(toset) then
    return false, "x509:set_info_access: expect a x509.extension.info_access instance at #1"
  end
  toset = toset.ctx
  -- x509v3.h: # define X509V3_ADD_REPLACE              2L
  if C.X509_add1_ext_i2d(self.ctx, NID_info_access, toset, 0, 0x2) ~= 1 then
    return false, format_error("x509:set_info_access")
  end
  return true
end

-- AUTO GENERATED: EXTENSIONS
function _M:set_info_access_critical(crit)
  return _M.set_extension_critical(self, NID_info_access, crit)
end

-- AUTO GENERATED: EXTENSIONS
function _M:get_info_access_critical()
  return _M.get_extension_critical(self, NID_info_access)
end

local NID_crl_distribution_points = C.OBJ_sn2nid("crlDistributionPoints")
assert(NID_crl_distribution_points ~= 0)

-- AUTO GENERATED: EXTENSIONS
function _M:get_crl_distribution_points()
  local crit = ctypes.ptr_of_int()
  -- X509_get_ext_d2i returns internal pointer, always dup
  -- for now this function always returns the first found extension
  local got = C.X509_get_ext_d2i(self.ctx, NID_crl_distribution_points, crit, nil)
  crit = tonumber(crit[0])
  if crit == -1 then -- not found
    return nil
  elseif crit == -2 then
    return nil, "x509:get_crl_distribution_points: extension of crl_distribution_points occurs more than one times, " ..
                "this is not yet implemented. Please use get_extension instead."
  elseif got == nil then
    return nil, format_error("x509:get_crl_distribution_points")
  end

  -- Note: here we only free the stack itself not elements
  -- since there seems no way to increase ref count for a DIST_POINT
  -- we left the elements referenced by the new-dup'ed stack
  local got_ref = got
  ffi_gc(got_ref, stack_lib.gc_of("DIST_POINT"))
  got = ffi_cast("OPENSSL_STACK*", got_ref)
  local lib = require("resty.openssl.x509.extension.dist_points")
  -- the internal ptr is returned, ie we need to copy it
  return lib.dup(got)
end

-- AUTO GENERATED: EXTENSIONS
function _M:set_crl_distribution_points(toset)
  local lib = require("resty.openssl.x509.extension.dist_points")
  if lib.istype and not lib.istype(toset) then
    return false, "x509:set_crl_distribution_points: expect a x509.extension.dist_points instance at #1"
  end
  toset = toset.ctx
  -- x509v3.h: # define X509V3_ADD_REPLACE              2L
  if C.X509_add1_ext_i2d(self.ctx, NID_crl_distribution_points, toset, 0, 0x2) ~= 1 then
    return false, format_error("x509:set_crl_distribution_points")
  end
  return true
end

-- AUTO GENERATED: EXTENSIONS
function _M:set_crl_distribution_points_critical(crit)
  return _M.set_extension_critical(self, NID_crl_distribution_points, crit)
end

-- AUTO GENERATED: EXTENSIONS
function _M:get_crl_distribution_points_critical()
  return _M.get_extension_critical(self, NID_crl_distribution_points)
end


-- AUTO GENERATED
function _M:get_signature_nid()
  local nid = accessors.get_signature_nid(self.ctx)
  if nid <= 0 then
    return nil, format_error("x509:get_signature_nid")
  end

  return nid
end

-- AUTO GENERATED
function _M:get_signature_name()
  local nid = accessors.get_signature_nid(self.ctx)
  if nid <= 0 then
    return nil, format_error("x509:get_signature_name")
  end

  return ffi.string(C.OBJ_nid2sn(nid))
end

-- AUTO GENERATED
function _M:get_signature_digest_name()
  local nid = accessors.get_signature_nid(self.ctx)
  if nid <= 0 then
    return nil, format_error("x509:get_signature_digest_name")
  end

  local nid = find_sigid_algs(nid)

  return ffi.string(C.OBJ_nid2sn(nid))
end
-- END AUTO GENERATED CODE

return _M
