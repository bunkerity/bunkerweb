local ffi = require "ffi"
local C = ffi.C
local ffi_gc = ffi.gc

require "resty.openssl.include.x509.crl"
require "resty.openssl.include.pem"
require "resty.openssl.include.x509v3"
local asn1_lib = require("resty.openssl.asn1")
local bn_lib = require("resty.openssl.bn")
local revoked_lib = require("resty.openssl.x509.revoked")
local digest_lib = require("resty.openssl.digest")
local extension_lib = require("resty.openssl.x509.extension")
local pkey_lib = require("resty.openssl.pkey")
local bio_util = require "resty.openssl.auxiliary.bio"
local ctx_lib = require "resty.openssl.ctx"
local stack_lib = require "resty.openssl.stack"
local txtnid2nid = require("resty.openssl.objects").txtnid2nid
local find_sigid_algs = require("resty.openssl.objects").find_sigid_algs
local format_error = require("resty.openssl.err").format_error
local version = require("resty.openssl.version")
local OPENSSL_10 = version.OPENSSL_10
local OPENSSL_11_OR_LATER = version.OPENSSL_11_OR_LATER
local OPENSSL_3X = version.OPENSSL_3X
local BORINGSSL = version.BORINGSSL
local BORINGSSL_110 = version.BORINGSSL_110 -- used in boringssl-fips-20190808

local accessors = {}

accessors.set_issuer_name = C.X509_CRL_set_issuer_name
accessors.set_version = C.X509_CRL_set_version


if OPENSSL_11_OR_LATER and not BORINGSSL_110 then
  accessors.get_last_update = C.X509_CRL_get0_lastUpdate
  accessors.set_last_update = C.X509_CRL_set1_lastUpdate
  accessors.get_next_update = C.X509_CRL_get0_nextUpdate
  accessors.set_next_update = C.X509_CRL_set1_nextUpdate
  accessors.get_version = C.X509_CRL_get_version
  accessors.get_issuer_name = C.X509_CRL_get_issuer -- returns internal ptr
  accessors.get_signature_nid = C.X509_CRL_get_signature_nid
  -- BORINGSSL_110 exports X509_CRL_get_signature_nid, but just ignored for simplicity
  accessors.get_revoked = C.X509_CRL_get_REVOKED
elseif OPENSSL_10 or BORINGSSL_110 then
  accessors.get_last_update = function(crl)
    if crl == nil or crl.crl == nil then
      return nil
    end
    return crl.crl.lastUpdate
  end
  accessors.set_last_update = C.X509_CRL_set_lastUpdate
  accessors.get_next_update = function(crl)
    if crl == nil or crl.crl == nil then
      return nil
    end
    return crl.crl.nextUpdate
  end
  accessors.set_next_update = C.X509_CRL_set_nextUpdate
  accessors.get_version = function(crl)
    if crl == nil or crl.crl == nil then
      return nil
    end
    return C.ASN1_INTEGER_get(crl.crl.version)
  end
  accessors.get_issuer_name = function(crl)
    if crl == nil or crl.crl == nil then
      return nil
    end
    return crl.crl.issuer
  end
  accessors.get_signature_nid = function(crl)
    if crl == nil or crl.crl == nil or crl.crl.sig_alg == nil then
      return nil
    end
    return C.OBJ_obj2nid(crl.crl.sig_alg.algorithm)
  end
  accessors.get_revoked = function(crl)
    return crl.crl.revoked
  end
end

local function __tostring(self, fmt)
  if not fmt or fmt == 'PEM' then
    return bio_util.read_wrap(C.PEM_write_bio_X509_CRL, self.ctx)
  elseif fmt == 'DER' then
    return bio_util.read_wrap(C.i2d_X509_CRL_bio, self.ctx)
  else
    return nil, "x509.crl:tostring: can only write PEM or DER format, not " .. fmt
  end
end

local _M = {}
local mt = { __index = _M, __tostring = __tostring }

local x509_crl_ptr_ct = ffi.typeof("X509_CRL*")

function _M.new(crl, fmt, properties)
  local ctx
  if not crl then
    if OPENSSL_3X then
      ctx = C.X509_CRL_new_ex(ctx_lib.get_libctx(), properties)
    else
      ctx = C.X509_CRL_new()
    end
    if ctx == nil then
      return nil, "x509.crl.new: X509_CRL_new() failed"
    end
  elseif type(crl) == "string" then
    -- routine for load an existing csr
    local bio = C.BIO_new_mem_buf(crl, #crl)
    if bio == nil then
      return nil, format_error("x509.crl.new: BIO_new_mem_buf")
    end

    fmt = fmt or "*"
    while true do -- luacheck: ignore 512 -- loop is executed at most once
      if fmt == "PEM" or fmt == "*" then
        ctx = C.PEM_read_bio_X509_CRL(bio, nil, nil, nil)
        if ctx ~= nil then
          break
        elseif fmt == "*" then
          -- BIO_reset; #define BIO_CTRL_RESET 1
          local code = C.BIO_ctrl(bio, 1, 0, nil)
          if code ~= 1 then
              return nil, "x509.crl.new: BIO_ctrl() failed: " .. code
          end
        end
      end
      if fmt == "DER" or fmt == "*" then
        ctx = C.d2i_X509_CRL_bio(bio, nil)
      end
      break
    end
    C.BIO_free(bio)
    if ctx == nil then
      return nil, format_error("x509.crl.new")
    end
    -- clear errors occur when trying
    C.ERR_clear_error()
  else
    return nil, "x509.crl.new: expect nil or a string at #1"
  end
  ffi_gc(ctx, C.X509_CRL_free)

  local self = setmetatable({
    ctx = ctx,
  }, mt)

  return self, nil
end

function _M.istype(l)
  return l and l and l.ctx and ffi.istype(x509_crl_ptr_ct, l.ctx)
end

function _M.dup(ctx)
  if not ffi.istype(x509_crl_ptr_ct, ctx) then
    return nil, "x509.crl.dup: expect a x509.crl ctx at #1"
  end
  local ctx = C.X509_CRL_dup(ctx)
  if ctx == nil then
    return nil, "x509.crl.dup: X509_CRL_dup() failed"
  end

  ffi_gc(ctx, C.X509_CRL_free)

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

function _M:text()
  return bio_util.read_wrap(C.X509_CRL_print, self.ctx)
end

local function revoked_decode(ctx)
  if OPENSSL_10 then
    error("x509.crl:revoked_decode: not supported on OpenSSL 1.0")
  end

  local ret = {}
  local serial = C.X509_REVOKED_get0_serialNumber(ctx)
  if serial ~= nil then
    serial = C.ASN1_INTEGER_to_BN(serial, nil)
    if serial == nil then
      error("x509.crl:revoked_decode: ASN1_INTEGER_to_BN() failed")
    end
    ffi_gc(serial, C.BN_free)
    ret["serial_number"] = bn_lib.to_hex({ctx = serial})
  end

  local date = C.X509_REVOKED_get0_revocationDate(ctx)
  if date ~= nil then
    date = asn1_lib.asn1_to_unix(date)
    ret["revocation_date"] = date
  end

  return ret
end

local revoked_mt = stack_lib.mt_of("X509_REVOKED", revoked_decode, _M)

local function nil_iter() return nil end
local function revoked_iter(self)
  local stack = accessors.get_revoked(self.ctx)
  if stack == nil then
    return nil_iter
  end

  return revoked_mt.__ipairs({ctx = stack})
end

mt.__pairs = revoked_iter
mt.__ipairs = revoked_iter
mt.__index = function(self, k)
  local i = tonumber(k)
  if not i then
    return _M[k]
  end

  local stack = accessors.get_revoked(self.ctx)
  if stack == nil then
    return nil
  end

  return revoked_mt.__index({ctx = stack}, i)
end
mt.__len = function(self)
  local stack = accessors.get_revoked(self.ctx)
  if stack == nil then
    return 0
  end

  return revoked_mt.__len({ctx = stack})
end

_M.all = function(self)
  local ret = {}
  local _next = mt.__pairs(self)
  while true do
    local k, v = _next()
    if k then
      ret[k] = v
    else
      break
    end
  end
  return ret
end
_M.each = mt.__pairs
_M.index = mt.__index
_M.count = mt.__len

--- Adds revoked item to stack of revoked certificates of crl
-- @tparam table Instance of crl module
-- @tparam table Instance of revoked module
-- @treturn boolean true if revoked item was successfully added or false otherwise
-- @treturn[opt] string Returns optional error message in case of error
function _M:add_revoked(revoked)
  if not revoked_lib.istype(revoked) then
    return false, "x509.crl:add_revoked: expect a revoked instance at #1"
  end
  local ctx = C.X509_REVOKED_dup(revoked.ctx)
  if ctx == nil then
    return nil, "x509.crl:add_revoked: X509_REVOKED_dup() failed"
  end

  if C.X509_CRL_add0_revoked(self.ctx, ctx) == 0 then
     return false, format_error("x509.crl:add_revoked")
  end

  return true
end

local ptr_ptr_of_x509_revoked = ffi.typeof("X509_REVOKED*[1]")
function _M:get_by_serial(sn)
  local bn, err
  if bn_lib.istype(sn) then
    bn = sn
  elseif type(sn) == "string" then
    bn, err = bn_lib.from_hex(sn)
    if err then
      return nil, "x509.crl:find: can't decode bn: " .. err
    end
  else
    return nil, "x509.crl:find: expect a bn instance at #1"
  end

  local sn_asn1 = C.BN_to_ASN1_INTEGER(bn.ctx, nil)
  if sn_asn1 == nil then
    return nil, "x509.crl:find: BN_to_ASN1_INTEGER() failed"
  end
  ffi_gc(sn_asn1, C.ASN1_INTEGER_free)
 
  local pp = ptr_ptr_of_x509_revoked()
  local code = C.X509_CRL_get0_by_serial(self.ctx, pp, sn_asn1)
  if code == 1 then
    return revoked_decode(pp[0])
  elseif code == 2 then
    return nil, "not revoked (removeFromCRL)"
  end

  -- 0 or other
  return nil
end


-- START AUTO GENERATED CODE

-- AUTO GENERATED
function _M:sign(pkey, digest)
  if not pkey_lib.istype(pkey) then
    return false, "x509.crl:sign: expect a pkey instance at #1"
  end

  local digest_algo
  if digest then
    if not digest_lib.istype(digest) then
      return false, "x509.crl:sign: expect a digest instance at #2"
    elseif not digest.algo then
      return false, "x509.crl:sign: expect a digest instance to have algo member"
    end
    digest_algo = digest.algo
  elseif BORINGSSL then
    digest_algo = C.EVP_get_digestbyname('sha256')
  end

  -- returns size of signature if success
  if C.X509_CRL_sign(self.ctx, pkey.ctx, digest_algo) == 0 then
    return false, format_error("x509.crl:sign")
  end

  return true
end

-- AUTO GENERATED
function _M:verify(pkey)
  if not pkey_lib.istype(pkey) then
    return false, "x509.crl:verify: expect a pkey instance at #1"
  end

  local code = C.X509_CRL_verify(self.ctx, pkey.ctx)
  if code == 1 then
    return true
  elseif code == 0 then
    return false
  else -- typically -1
    return false, format_error("x509.crl:verify", code)
  end
end

-- AUTO GENERATED
local function get_extension(ctx, nid_txt, last_pos)
  last_pos = (last_pos or 0) - 1
  local nid, err = txtnid2nid(nid_txt)
  if err then
    return nil, nil, err
  end
  local pos = C.X509_CRL_get_ext_by_NID(ctx, nid, last_pos)
  if pos == -1 then
    return nil
  end
  local ctx = C.X509_CRL_get_ext(ctx, pos)
  if ctx == nil then
    return nil, nil, format_error()
  end
  return ctx, pos
end

-- AUTO GENERATED
function _M:add_extension(extension)
  if not extension_lib.istype(extension) then
    return false, "x509.crl:add_extension: expect a x509.extension instance at #1"
  end

  -- X509_CRL_add_ext returnes the stack on success, and NULL on error
  -- the X509_EXTENSION ctx is dupped internally
  if C.X509_CRL_add_ext(self.ctx, extension.ctx, -1) == nil then
    return false, format_error("x509.crl:add_extension")
  end

  return true
end

-- AUTO GENERATED
function _M:get_extension(nid_txt, last_pos)
  local ctx, pos, err = get_extension(self.ctx, nid_txt, last_pos)
  if err then
    return nil, nil, "x509.crl:get_extension: " .. err
  end
  local ext, err = extension_lib.dup(ctx)
  if err then
    return nil, nil, "x509.crl:get_extension: " .. err
  end
  return ext, pos+1
end

local X509_CRL_delete_ext
if OPENSSL_11_OR_LATER then
  X509_CRL_delete_ext = C.X509_CRL_delete_ext
elseif OPENSSL_10 then
  X509_CRL_delete_ext = function(ctx, pos)
    return C.X509v3_delete_ext(ctx.crl.extensions, pos)
  end
else
  X509_CRL_delete_ext = function(...)
    error("X509_CRL_delete_ext undefined")
  end
end

-- AUTO GENERATED
function _M:set_extension(extension, last_pos)
  if not extension_lib.istype(extension) then
    return false, "x509.crl:set_extension: expect a x509.extension instance at #1"
  end

  last_pos = (last_pos or 0) - 1

  local nid = extension:get_object().nid
  local pos = C.X509_CRL_get_ext_by_NID(self.ctx, nid, last_pos)
  -- pos may be -1, which means not found, it's fine, we will add new one instead of replace

  local removed = X509_CRL_delete_ext(self.ctx, pos)
  C.X509_EXTENSION_free(removed)

  if C.X509_CRL_add_ext(self.ctx, extension.ctx, pos) == nil then
    return false, format_error("x509.crl:set_extension")
  end

  return true
end

-- AUTO GENERATED
function _M:set_extension_critical(nid_txt, crit, last_pos)
  local ctx, _, err = get_extension(self.ctx, nid_txt, last_pos)
  if err then
    return nil, "x509.crl:set_extension_critical: " .. err
  end

  if C.X509_EXTENSION_set_critical(ctx, crit and 1 or 0) ~= 1 then
    return false, format_error("x509.crl:set_extension_critical")
  end

  return true
end

-- AUTO GENERATED
function _M:get_extension_critical(nid_txt, last_pos)
  local ctx, _, err = get_extension(self.ctx, nid_txt, last_pos)
  if err then
    return nil, "x509.crl:get_extension_critical: " .. err
  end

  return C.X509_EXTENSION_get_critical(ctx) == 1
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
    return false, "x509.crl:set_issuer_name: expect a x509.name instance at #1"
  end
  toset = toset.ctx
  if accessors.set_issuer_name(self.ctx, toset) == 0 then
    return false, format_error("x509.crl:set_issuer_name")
  end
  return true
end

-- AUTO GENERATED
function _M:get_last_update()
  local got = accessors.get_last_update(self.ctx)
  if got == nil then
    return nil
  end

  got = asn1_lib.asn1_to_unix(got)

  return got
end

-- AUTO GENERATED
function _M:set_last_update(toset)
  if type(toset) ~= "number" then
    return false, "x509.crl:set_last_update: expect a number at #1"
  end

  toset = C.ASN1_TIME_set(nil, toset)
  ffi_gc(toset, C.ASN1_STRING_free)

  if accessors.set_last_update(self.ctx, toset) == 0 then
    return false, format_error("x509.crl:set_last_update")
  end
  return true
end

-- AUTO GENERATED
function _M:get_next_update()
  local got = accessors.get_next_update(self.ctx)
  if got == nil then
    return nil
  end

  got = asn1_lib.asn1_to_unix(got)

  return got
end

-- AUTO GENERATED
function _M:set_next_update(toset)
  if type(toset) ~= "number" then
    return false, "x509.crl:set_next_update: expect a number at #1"
  end

  toset = C.ASN1_TIME_set(nil, toset)
  ffi_gc(toset, C.ASN1_STRING_free)

  if accessors.set_next_update(self.ctx, toset) == 0 then
    return false, format_error("x509.crl:set_next_update")
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
    return false, "x509.crl:set_version: expect a number at #1"
  end

  -- Note: this is defined by standards (X.509 et al) to be one less than the certificate version.
  -- So a version 3 certificate will return 2 and a version 1 certificate will return 0.
  toset = toset - 1

  if accessors.set_version(self.ctx, toset) == 0 then
    return false, format_error("x509.crl:set_version")
  end
  return true
end


-- AUTO GENERATED
function _M:get_signature_nid()
  local nid = accessors.get_signature_nid(self.ctx)
  if nid <= 0 then
    return nil, format_error("x509.crl:get_signature_nid")
  end

  return nid
end

-- AUTO GENERATED
function _M:get_signature_name()
  local nid = accessors.get_signature_nid(self.ctx)
  if nid <= 0 then
    return nil, format_error("x509.crl:get_signature_name")
  end

  return ffi.string(C.OBJ_nid2sn(nid))
end

-- AUTO GENERATED
function _M:get_signature_digest_name()
  local nid = accessors.get_signature_nid(self.ctx)
  if nid <= 0 then
    return nil, format_error("x509.crl:get_signature_digest_name")
  end

  local nid = find_sigid_algs(nid)

  return ffi.string(C.OBJ_nid2sn(nid))
end
-- END AUTO GENERATED CODE

return _M

