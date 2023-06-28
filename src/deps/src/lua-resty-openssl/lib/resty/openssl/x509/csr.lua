local ffi = require "ffi"
local C = ffi.C
local ffi_gc = ffi.gc
local ffi_cast = ffi.cast

require "resty.openssl.include.pem"
require "resty.openssl.include.x509v3"
require "resty.openssl.include.x509.csr"
require "resty.openssl.include.asn1"
local stack_macro = require "resty.openssl.include.stack"
local stack_lib = require "resty.openssl.stack"
local pkey_lib = require "resty.openssl.pkey"
local digest_lib = require("resty.openssl.digest")
local extension_lib = require("resty.openssl.x509.extension")
local extensions_lib = require("resty.openssl.x509.extensions")
local bio_util = require "resty.openssl.auxiliary.bio"
local ctypes = require "resty.openssl.auxiliary.ctypes"
local ctx_lib = require "resty.openssl.ctx"
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

accessors.set_subject_name = C.X509_REQ_set_subject_name
accessors.get_pubkey = C.X509_REQ_get_pubkey
accessors.set_pubkey = C.X509_REQ_set_pubkey
accessors.set_version = C.X509_REQ_set_version

if OPENSSL_11_OR_LATER or BORINGSSL_110 then
  accessors.get_signature_nid = C.X509_REQ_get_signature_nid
elseif OPENSSL_10 then
  accessors.get_signature_nid = function(csr)
    if csr == nil or csr.sig_alg == nil then
      return nil
    end
    return C.OBJ_obj2nid(csr.sig_alg.algorithm)
  end
end

if OPENSSL_11_OR_LATER and not BORINGSSL_110 then
  accessors.get_subject_name = C.X509_REQ_get_subject_name -- returns internal ptr
  accessors.get_version = C.X509_REQ_get_version
elseif OPENSSL_10 or BORINGSSL_110 then
  accessors.get_subject_name = function(csr)
    if csr == nil or csr.req_info == nil then
      return nil
    end
    return csr.req_info.subject
  end
  accessors.get_version = function(csr)
    if csr == nil or csr.req_info == nil then
      return nil
    end
    return C.ASN1_INTEGER_get(csr.req_info.version)
  end
end

local function __tostring(self, fmt)
  if not fmt or fmt == 'PEM' then
    return bio_util.read_wrap(C.PEM_write_bio_X509_REQ, self.ctx)
  elseif fmt == 'DER' then
    return bio_util.read_wrap(C.i2d_X509_REQ_bio, self.ctx)
  else
    return nil, "x509.csr:tostring: can only write PEM or DER format, not " .. fmt
  end
end

local _M = {}
local mt = { __index = _M, __tostring = __tostring }

local x509_req_ptr_ct = ffi.typeof("X509_REQ*")

local stack_ptr_type = ffi.typeof("struct stack_st *[1]")
local x509_extensions_gc = stack_lib.gc_of("X509_EXTENSION")

function _M.new(csr, fmt, properties)
  local ctx
  if not csr then
    if OPENSSL_3X then
      ctx = C.X509_REQ_new_ex(ctx_lib.get_libctx(), properties)
    else
      ctx = C.X509_REQ_new()
    end
    if ctx == nil then
      return nil, "x509.csr.new: X509_REQ_new() failed"
    end
  elseif type(csr) == "string" then
    -- routine for load an existing csr
    local bio = C.BIO_new_mem_buf(csr, #csr)
    if bio == nil then
      return nil, format_error("x509.csr.new: BIO_new_mem_buf")
    end

    fmt = fmt or "*"
    while true do -- luacheck: ignore 512 -- loop is executed at most once
      if fmt == "PEM" or fmt == "*" then
        ctx = C.PEM_read_bio_X509_REQ(bio, nil, nil, nil)
        if ctx ~= nil then
          break
        elseif fmt == "*" then
          -- BIO_reset; #define BIO_CTRL_RESET 1
          local code = C.BIO_ctrl(bio, 1, 0, nil)
          if code ~= 1 then
              return nil, "x509.csr.new: BIO_ctrl() failed: " .. code
          end
        end
      end
      if fmt == "DER" or fmt == "*" then
        ctx = C.d2i_X509_REQ_bio(bio, nil)
      end
      break
    end
    C.BIO_free(bio)
    if ctx == nil then
      return nil, format_error("x509.csr.new")
    end
    -- clear errors occur when trying
    C.ERR_clear_error()
  else
    return nil, "x509.csr.new: expect nil or a string at #1"
  end
  ffi_gc(ctx, C.X509_REQ_free)

  local self = setmetatable({
    ctx = ctx,
  }, mt)

  return self, nil
end

function _M.istype(l)
  return l and l and l.ctx and ffi.istype(x509_req_ptr_ct, l.ctx)
end

function _M:tostring(fmt)
  return __tostring(self, fmt)
end

function _M:to_PEM()
  return __tostring(self, "PEM")
end

function _M:check_private_key(key)
  if not pkey_lib.istype(key) then
    return false, "x509.csr:check_private_key: except a pkey instance at #1"
  end

  if not key:is_private() then
    return false, "x509.csr:check_private_key: not a private key"
  end

  if C.X509_REQ_check_private_key(self.ctx, key.ctx) == 1 then
    return true
  end
  return false, format_error("x509.csr:check_private_key")
end

--- Get all csr extensions
-- @tparam table self Instance of csr
-- @treturn Extensions object
function _M:get_extensions()
  local extensions = C.X509_REQ_get_extensions(self.ctx)
  -- GC handler is sk_X509_EXTENSION_pop_free
  ffi_gc(extensions, x509_extensions_gc)

  return extensions_lib.dup(extensions)
end

local function get_extension(ctx, nid_txt, last_pos)
  local nid, err = txtnid2nid(nid_txt)
  if err then
    return nil, nil, err
  end

  local extensions = C.X509_REQ_get_extensions(ctx)
  if extensions == nil then
    return nil, nil, format_error("csr.get_extension: X509_REQ_get_extensions")
  end
  ffi_gc(extensions, x509_extensions_gc)

  -- make 1-index array to 0-index
  last_pos = (last_pos or 0) -1
  local ext_idx = C.X509v3_get_ext_by_NID(extensions, nid, last_pos)
  if ext_idx == -1 then
    err = ("X509v3_get_ext_by_NID extension for %d not found"):format(nid)
    return nil, -1, format_error(err)
  end

  local ctx = C.X509v3_get_ext(extensions, ext_idx)
  if ctx == nil then
    return nil, nil, format_error("X509v3_get_ext")
  end

  return ctx, ext_idx, nil
end

--- Get a csr extension
-- @tparam table self Instance of csr
-- @tparam string|number Nid number or name of the extension
-- @tparam number Position to start looking for the extension; default to look from start if omitted
-- @treturn Parsed extension object or nil if not found
function _M:get_extension(nid_txt, last_pos)
  local ctx, pos, err = get_extension(self.ctx, nid_txt, last_pos)
  if err then
    return nil, nil, "x509.csr:get_extension: " .. err
  end
  local ext, err = extension_lib.dup(ctx)
  if err then
    return nil, nil, "x509.csr:get_extension: " .. err
  end
  return ext, pos+1
end

local function modify_extension(replace, ctx, nid, toset, crit)
  local extensions_ptr = stack_ptr_type()
  extensions_ptr[0] = C.X509_REQ_get_extensions(ctx)
  local need_cleanup = extensions_ptr[0] ~= nil and
  -- extensions_ptr being nil is fine: it may just because there's no extension yet
  -- https://github.com/openssl/openssl/commit/2039ac07b401932fa30a05ade80b3626e189d78a
  -- introduces a change that a empty stack instead of NULL will be returned in no extension
  -- is found. so we need to double check the number if it's not NULL.
                        stack_macro.OPENSSL_sk_num(extensions_ptr[0]) > 0

  local flag
  if replace then
    -- x509v3.h: # define X509V3_ADD_REPLACE              2L
    flag = 0x2
  else
    -- x509v3.h: # define X509V3_ADD_APPEND               1L
    flag = 0x1
  end

  local code = C.X509V3_add1_i2d(extensions_ptr, nid, toset, crit and 1 or 0, flag)
  -- when the stack is newly allocated, we want to cleanup the newly created stack as well
  -- setting the gc handler here as it's mutated in X509V3_add1_i2d if it's pointing to NULL
  ffi_gc(extensions_ptr[0], x509_extensions_gc)
  if code ~= 1 then
    return false, format_error("X509V3_add1_i2d", code)
  end

  code = C.X509_REQ_add_extensions(ctx, extensions_ptr[0])
  if code ~= 1 then
    return false, format_error("X509_REQ_add_extensions", code)
  end

  if need_cleanup then
    -- cleanup old attributes
    -- delete the first only, why?
    local attr = C.X509_REQ_delete_attr(ctx, 0)
    if attr ~= nil then
      C.X509_ATTRIBUTE_free(attr)
    end
  end

  -- mark encoded form as invalid so next time it will be re-encoded
  if OPENSSL_11_OR_LATER then
    C.i2d_re_X509_REQ_tbs(ctx, nil)
  else
    ctx.req_info.enc.modified = 1
  end

  return true
end

local function add_extension(...)
  return modify_extension(false, ...)
end

local function replace_extension(...)
  return modify_extension(true, ...)
end

function _M:add_extension(extension)
  if not extension_lib.istype(extension) then
    return false, "x509:set_extension: expect a x509.extension instance at #1"
  end

  local nid = extension:get_object().nid
  local toset = extension_lib.to_data(extension, nid)
  return add_extension(self.ctx, nid, toset.ctx, extension:get_critical())
end

function _M:set_extension(extension)
  if not extension_lib.istype(extension) then
    return false, "x509:set_extension: expect a x509.extension instance at #1"
  end

  local nid = extension:get_object().nid
  local toset = extension_lib.to_data(extension, nid)
  return replace_extension(self.ctx, nid, toset.ctx, extension:get_critical())
end

function _M:set_extension_critical(nid_txt, crit, last_pos)
  local nid, err = txtnid2nid(nid_txt)
  if err then
    return nil, "x509.csr:set_extension_critical: " .. err
  end

  local extension, _, err = get_extension(self.ctx, nid, last_pos)
  if err then
    return nil, "x509.csr:set_extension_critical: " .. err
  end

  local toset = extension_lib.to_data({
    ctx = extension
  }, nid)
  return replace_extension(self.ctx, nid, toset.ctx, crit and 1 or 0)
end

function _M:get_extension_critical(nid_txt, last_pos)
  local ctx, _, err = get_extension(self.ctx, nid_txt, last_pos)
  if err then
    return nil, "x509.csr:get_extension_critical: " .. err
  end

  return C.X509_EXTENSION_get_critical(ctx) == 1
end

-- START AUTO GENERATED CODE

-- AUTO GENERATED
function _M:sign(pkey, digest)
  if not pkey_lib.istype(pkey) then
    return false, "x509.csr:sign: expect a pkey instance at #1"
  end

  local digest_algo
  if digest then
    if not digest_lib.istype(digest) then
      return false, "x509.csr:sign: expect a digest instance at #2"
    elseif not digest.algo then
      return false, "x509.csr:sign: expect a digest instance to have algo member"
    end
    digest_algo = digest.algo
  elseif BORINGSSL then
    digest_algo = C.EVP_get_digestbyname('sha256')
  end

  -- returns size of signature if success
  if C.X509_REQ_sign(self.ctx, pkey.ctx, digest_algo) == 0 then
    return false, format_error("x509.csr:sign")
  end

  return true
end

-- AUTO GENERATED
function _M:verify(pkey)
  if not pkey_lib.istype(pkey) then
    return false, "x509.csr:verify: expect a pkey instance at #1"
  end

  local code = C.X509_REQ_verify(self.ctx, pkey.ctx)
  if code == 1 then
    return true
  elseif code == 0 then
    return false
  else -- typically -1
    return false, format_error("x509.csr:verify", code)
  end
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
    return false, "x509.csr:set_subject_name: expect a x509.name instance at #1"
  end
  toset = toset.ctx
  if accessors.set_subject_name(self.ctx, toset) == 0 then
    return false, format_error("x509.csr:set_subject_name")
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
    return false, "x509.csr:set_pubkey: expect a pkey instance at #1"
  end
  toset = toset.ctx
  if accessors.set_pubkey(self.ctx, toset) == 0 then
    return false, format_error("x509.csr:set_pubkey")
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
    return false, "x509.csr:set_version: expect a number at #1"
  end

  -- Note: this is defined by standards (X.509 et al) to be one less than the certificate version.
  -- So a version 3 certificate will return 2 and a version 1 certificate will return 0.
  toset = toset - 1

  if accessors.set_version(self.ctx, toset) == 0 then
    return false, format_error("x509.csr:set_version")
  end
  return true
end

local NID_subject_alt_name = C.OBJ_sn2nid("subjectAltName")
assert(NID_subject_alt_name ~= 0)

-- AUTO GENERATED: EXTENSIONS
function _M:get_subject_alt_name()
  local crit = ctypes.ptr_of_int()
  local extensions = C.X509_REQ_get_extensions(self.ctx)
  -- GC handler is sk_X509_EXTENSION_pop_free
  ffi_gc(extensions, x509_extensions_gc)
  local got = C.X509V3_get_d2i(extensions, NID_subject_alt_name, crit, nil)
  crit = tonumber(crit[0])
  if crit == -1 then -- not found
    return nil
  elseif crit == -2 then
    return nil, "x509.csr:get_subject_alt_name: extension of subject_alt_name occurs more than one times, " ..
                "this is not yet implemented. Please use get_extension instead."
  elseif got == nil then
    return nil, format_error("x509.csr:get_subject_alt_name")
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
    return false, "x509.csr:set_subject_alt_name: expect a x509.altname instance at #1"
  end
  toset = toset.ctx
  return replace_extension(self.ctx, NID_subject_alt_name, toset)
end

-- AUTO GENERATED: EXTENSIONS
function _M:set_subject_alt_name_critical(crit)
  return _M.set_extension_critical(self, NID_subject_alt_name, crit)
end

-- AUTO GENERATED: EXTENSIONS
function _M:get_subject_alt_name_critical()
  return _M.get_extension_critical(self, NID_subject_alt_name)
end


-- AUTO GENERATED
function _M:get_signature_nid()
  local nid = accessors.get_signature_nid(self.ctx)
  if nid <= 0 then
    return nil, format_error("x509.csr:get_signature_nid")
  end

  return nid
end

-- AUTO GENERATED
function _M:get_signature_name()
  local nid = accessors.get_signature_nid(self.ctx)
  if nid <= 0 then
    return nil, format_error("x509.csr:get_signature_name")
  end

  return ffi.string(C.OBJ_nid2sn(nid))
end

-- AUTO GENERATED
function _M:get_signature_digest_name()
  local nid = accessors.get_signature_nid(self.ctx)
  if nid <= 0 then
    return nil, format_error("x509.csr:get_signature_digest_name")
  end

  local nid = find_sigid_algs(nid)

  return ffi.string(C.OBJ_nid2sn(nid))
end
-- END AUTO GENERATED CODE

return _M

