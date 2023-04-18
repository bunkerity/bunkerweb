local ffi = require "ffi"
local C = ffi.C
local ffi_gc = ffi.gc
local ffi_str = ffi.string

require("resty.openssl.objects")
require("resty.openssl.include.evp.md")
-- used by legacy EVP_PKEY_derive interface
require("resty.openssl.include.evp.pkey")
local kdf_macro = require "resty.openssl.include.evp.kdf"
local ctx_lib = require "resty.openssl.ctx"
local format_error = require("resty.openssl.err").format_error
local version_num = require("resty.openssl.version").version_num
local version_text = require("resty.openssl.version").version_text
local BORINGSSL = require("resty.openssl.version").BORINGSSL
local OPENSSL_3X = require("resty.openssl.version").OPENSSL_3X
local ctypes = require "resty.openssl.auxiliary.ctypes"

--[[
https://wiki.openssl.org/index.php/EVP_Key_Derivation

OpenSSL 1.0.2 and above provides PBKDF2 by way of PKCS5_PBKDF2_HMAC and PKCS5_PBKDF2_HMAC_SHA1.
OpenSSL 1.1.0 and above additionally provides HKDF and TLS1 PRF KDF by way of EVP_PKEY_derive and Scrypt by way of EVP_PBE_scrypt
OpenSSL 1.1.1 and above additionally provides Scrypt by way of EVP_PKEY_derive.
OpenSSL 3.0 additionally provides Single Step KDF, SSH KDF, PBKDF2, Scrypt, HKDF, ANSI X9.42 KDF, ANSI X9.63 KDF and TLS1 PRF KDF by way of EVP_KDF.
From OpenSSL 3.0 the recommended way of performing key derivation is to use the EVP_KDF functions. If compatibility with OpenSSL 1.1.1 is required then a limited set of KDFs can be used via EVP_PKEY_derive.
]]

local NID_id_pbkdf2 = -1
local NID_id_scrypt = -2
local NID_tls1_prf = -3
local NID_hkdf = -4
if version_num >= 0x10002000 then
  NID_id_pbkdf2 = C.OBJ_txt2nid("PBKDF2")
  assert(NID_id_pbkdf2 > 0)
end
if version_num >= 0x10100000 and not BORINGSSL then
  NID_hkdf = C.OBJ_txt2nid("HKDF")
  assert(NID_hkdf > 0)
  NID_tls1_prf = C.OBJ_txt2nid("TLS1-PRF")
  assert(NID_tls1_prf > 0)
  -- we use EVP_PBE_scrypt to do scrypt, so this is supported >= 1.1.0
  NID_id_scrypt = C.OBJ_txt2nid("id-scrypt")
  assert(NID_id_scrypt > 0)
end

local _M = {
  HKDEF_MODE_EXTRACT_AND_EXPAND = kdf_macro.EVP_PKEY_HKDEF_MODE_EXTRACT_AND_EXPAND,
  HKDEF_MODE_EXTRACT_ONLY       = kdf_macro.EVP_PKEY_HKDEF_MODE_EXTRACT_ONLY,
  HKDEF_MODE_EXPAND_ONLY        = kdf_macro.EVP_PKEY_HKDEF_MODE_EXPAND_ONLY,

  PBKDF2   = NID_id_pbkdf2,
  SCRYPT   = NID_id_scrypt,
  TLS1_PRF = NID_tls1_prf,
  HKDF     = NID_hkdf,
}

local type_literals = {
  [NID_id_pbkdf2] = "PBKDF2",
  [NID_id_scrypt] = "scrypt",
  [NID_tls1_prf]  = "TLS-1PRF",
  [NID_hkdf]      = "HKDF",
}

local TYPE_NUMBER = 0x1
local TYPE_STRING = 0x2

local function check_options(opt, nid, field, typ, is_optional, required_only_if_nid)
  local v = opt[field]
  if not v then
    if is_optional or (required_only_if_nid and required_only_if_nid ~= nid) then
      return typ == TYPE_NUMBER and 0 or nil
    else
      return nil, "\"" .. field .. "\" must be set"
    end
  end

  if typ == TYPE_NUMBER then
    v = tonumber(v)
    if not typ then
      return nil, "except a number as \"" .. field .. "\""
    end
  elseif typ == TYPE_STRING then
    if type(v) ~= "string" then
      return nil, "except a string as \"" .. field .. "\""
    end
  else
    error("don't known how to check " .. typ, 2)
  end

  return v
end

local function check_hkdf_options(opt)
  local mode = opt.hkdf_mode
  if not mode or version_num < 0x10101000 then
    mode = _M.HKDEF_MODE_EXTRACT_AND_EXPAND
  end

  if mode == _M.HKDEF_MODE_EXTRACT_AND_EXPAND and (
    not opt.salt or not opt.hkdf_info) then
    return '""salt" and "hkdf_info" are required for EXTRACT_AND_EXPAND mode'
  elseif mode == _M.HKDEF_MODE_EXTRACT_ONLY and not opt.salt then
    return '"salt" is required for EXTRACT_ONLY mode'
  elseif mode == _M.EVP_PKEY_HKDEF_MODE_EXPAND_ONLY and not opt.hkdf_info then
    return '"hkdf_info" is required for EXPAND_ONLY mode'
  end

  return nil
end

local options_schema = {
  outlen = { TYPE_NUMBER },
  pass   = { TYPE_STRING, true },
  salt   = { TYPE_STRING, true },
  md     = { TYPE_STRING, true },
  -- pbkdf2 only
  pbkdf2_iter = { TYPE_NUMBER, true },
  -- hkdf only
  hkdf_key  = { TYPE_STRING, nil, NID_hkdf },
  hkdf_mode = { TYPE_NUMBER, true },
  hkdf_info = { TYPE_STRING, true },
  -- tls1-prf
  tls1_prf_secret = { TYPE_STRING, nil, NID_tls1_prf },
  tls1_prf_seed   = { TYPE_STRING, nil, NID_tls1_prf },
  -- scrypt only
  scrypt_maxmem = { TYPE_NUMBER, true },
  scrypt_N      = { TYPE_NUMBER, nil, NID_id_scrypt },
  scrypt_r      = { TYPE_NUMBER, nil, NID_id_scrypt },
  scrypt_p      = { TYPE_NUMBER, nil, NID_id_scrypt },
}

local outlen = ctypes.ptr_of_uint64()

function _M.derive(options)
  local typ = options.type
  if not typ then
    return nil, "kdf.derive: \"type\" must be set"
  elseif type(typ) ~= "number" then
    return nil, "kdf.derive: expect a number as \"type\""
  end

  if typ <= 0 then
    return nil, "kdf.derive: kdf type " ..  (type_literals[typ] or tostring(typ)) ..
                " not supported in " .. version_text
  end

  for k, v in pairs(options_schema) do
    local v, err = check_options(options, typ, k, unpack(v))
    if err then
      return nil, "kdf.derive: " .. err
    end
    options[k] = v
  end

  if typ == NID_hkdf then
    local err = check_hkdf_options(options)
    if err then
      return nil, "kdf.derive: " .. err
    end
  end

  local salt_len = 0
  if options.salt then
    salt_len = #options.salt
  end
  local pass_len = 0
  if options.pass then
    pass_len = #options.pass
  end

  local md
  if OPENSSL_3X then
    md = C.EVP_MD_fetch(ctx_lib.get_libctx(), options.md or 'sha1', options.properties)
  else
    md = C.EVP_get_digestbyname(options.md or 'sha1')
  end
  if md == nil then
    return nil, string.format("kdf.derive: invalid digest type \"%s\"", md)
  end

  local buf = ctypes.uchar_array(options.outlen)

  -- begin legacay low level routines
  local code
  if typ == NID_id_pbkdf2 then
    -- make openssl 1.0.2 happy
    if version_num < 0x10100000 and not options.pass then
      options.pass = ""
      pass_len = 0
    end
    -- https://www.openssl.org/docs/man1.1.0/man3/PKCS5_PBKDF2_HMAC.html
    local iter = options.pbkdf2_iter
    if iter < 1 then
      iter = 1
    end
    code = C.PKCS5_PBKDF2_HMAC(
      options.pass, pass_len,
      options.salt, salt_len, iter,
      md, options.outlen, buf
    )
  elseif typ == NID_id_scrypt then
    code = C.EVP_PBE_scrypt(
      options.pass, pass_len,
      options.salt, salt_len,
      options.scrypt_N, options.scrypt_r, options.scrypt_p, options.scrypt_maxmem,
      buf, options.outlen
    )
  elseif typ ~= NID_tls1_prf and typ ~= NID_hkdf then
    return nil, string.format("kdf.derive: unknown type %d", typ)
  end
  if code then
    if code ~= 1 then
      return nil, format_error("kdf.derive")
    else
      return ffi_str(buf, options.outlen)
    end
  end
  -- end legacay low level routines

  -- begin EVP_PKEY_derive routines
  outlen[0] = options.outlen

  local ctx = C.EVP_PKEY_CTX_new_id(typ, nil)
  if ctx == nil then
    return nil, format_error("kdf.derive: EVP_PKEY_CTX_new_id")
  end
  ffi_gc(ctx, C.EVP_PKEY_CTX_free)
  if C.EVP_PKEY_derive_init(ctx) ~= 1 then
    return nil, format_error("kdf.derive: EVP_PKEY_derive_init")
  end

  if typ == NID_tls1_prf then
    if kdf_macro.EVP_PKEY_CTX_set_tls1_prf_md(ctx, md) ~= 1 then
      return nil, format_error("kdf.derive: EVP_PKEY_CTX_set_tls1_prf_md")
    end
    if kdf_macro.EVP_PKEY_CTX_set1_tls1_prf_secret(ctx, options.tls1_prf_secret) ~= 1 then
      return nil, format_error("kdf.derive: EVP_PKEY_CTX_set1_tls1_prf_secret")
    end
    if kdf_macro.EVP_PKEY_CTX_add1_tls1_prf_seed(ctx, options.tls1_prf_seed) ~= 1 then
      return nil, format_error("kdf.derive: EVP_PKEY_CTX_add1_tls1_prf_seed")
    end
  elseif typ == NID_hkdf then
    if kdf_macro.EVP_PKEY_CTX_set_hkdf_md(ctx, md) ~= 1 then
      return nil, format_error("kdf.derive: EVP_PKEY_CTX_set_hkdf_md")
    end
    if options.salt and
      kdf_macro.EVP_PKEY_CTX_set1_hkdf_salt(ctx, options.salt) ~= 1 then
      return nil, format_error("kdf.derive: EVP_PKEY_CTX_set1_hkdf_salt")
    end
    if options.hkdf_key and
      kdf_macro.EVP_PKEY_CTX_set1_hkdf_key(ctx, options.hkdf_key) ~= 1 then
      return nil, format_error("kdf.derive: EVP_PKEY_CTX_set1_hkdf_key")
    end
    if options.hkdf_info and
      kdf_macro.EVP_PKEY_CTX_add1_hkdf_info(ctx, options.hkdf_info) ~= 1 then
      return nil, format_error("kdf.derive: EVP_PKEY_CTX_add1_hkdf_info")
    end
    if options.hkdf_mode then
      if version_num >= 0x10101000 then
        if kdf_macro.EVP_PKEY_CTX_set_hkdf_mode(ctx, options.hkdf_mode) ~= 1 then
          return nil, format_error("kdf.derive: EVP_PKEY_CTX_set_hkdf_mode")
        end
        if options.hkdf_mode == _M.HKDEF_MODE_EXTRACT_ONLY then
          local md_size = OPENSSL_3X and C.EVP_MD_get_size(md) or C.EVP_MD_size(md)
          if options.outlen ~= md_size then
            options.outlen = md_size
            ngx.log(ngx.WARN, "hkdf_mode EXTRACT_ONLY outputs fixed length of ", md_size,
                    " key, ignoring options.outlen")
          end
          outlen[0] = md_size
          buf = ctypes.uchar_array(md_size)
        end
      else
        ngx.log(ngx.WARN, "hkdf_mode is not effective in ", version_text)
      end
    end
  else
    return nil, string.format("kdf.derive: unknown type %d", typ)
  end
  code = C.EVP_PKEY_derive(ctx, buf, outlen)
  if code == -2 then
    return nil, "kdf.derive: operation is not supported by the public key algorithm"
  end
  -- end EVP_PKEY_derive routines

  return ffi_str(buf, options.outlen)
end

if not OPENSSL_3X then
  return _M
end

_M.derive_legacy = _M.derive
_M.derive = nil

-- OPENSSL 3.0 style API
local param_lib = require "resty.openssl.param"
local SIZE_MAX = ctypes.SIZE_MAX

local mt = {__index = _M}

local kdf_ctx_ptr_ct = ffi.typeof('EVP_KDF_CTX*')

function _M.new(typ, properties)
  local algo = C.EVP_KDF_fetch(ctx_lib.get_libctx(), typ, properties)
  if algo == nil then
    return nil, format_error(string.format("mac.new: invalid mac type \"%s\"", typ))
  end

  local ctx = C.EVP_KDF_CTX_new(algo)
  if ctx == nil then
    return nil, "mac.new: failed to create EVP_MAC_CTX"
  end
  ffi_gc(ctx, C.EVP_KDF_CTX_free)

  local buf
  local buf_size = tonumber(C.EVP_KDF_CTX_get_kdf_size(ctx))
  if buf_size == SIZE_MAX then -- no fixed size
    buf_size = nil
  else
    buf = ctypes.uchar_array(buf_size)
  end

  return setmetatable({
    ctx = ctx,
    algo = algo,
    buf = buf,
    buf_size = buf_size,
  }, mt), nil
end

function _M.istype(l)
  return l and l.ctx and ffi.istype(kdf_ctx_ptr_ct, l.ctx)
end

function _M:get_provider_name()
  local p = C.EVP_KDF_get0_provider(self.algo)
  if p == nil then
    return nil
  end
  return ffi_str(C.OSSL_PROVIDER_get0_name(p))
end

_M.settable_params, _M.set_params, _M.gettable_params, _M.get_param = param_lib.get_params_func("EVP_KDF_CTX")

function _M:derive(outlen, options, options_count)
  if not _M.istype(self) then
    return _M.derive_legacy(self)
  end

  if self.buf_size and outlen then
    return nil, string.format("kdf:derive: this KDF has fixed output size %d, ".. 
                              "it can't be set manually", self.buf_size)
  end

  outlen = self.buf_size or outlen
  local buf = self.buf or ctypes.uchar_array(outlen)

  if options_count then
    options_count = options_count - 1
  else
    options_count = 0
    for k, v in pairs(options) do options_count = options_count + 1 end
  end

  local param, err
  if options_count > 0 then
    local schema = self:settable_params(true) -- raw schema
    param, err = param_lib.construct(options, nil, schema)
    if err then
      return nil, "kdf:derive: " .. err
    end
  end

  if C.EVP_KDF_derive(self.ctx, buf, outlen, param) ~= 1 then
    return nil, format_error("kdf:derive")
  end

  return ffi_str(buf, outlen)
end

function _M:reset()
  C.EVP_KDF_CTX_reset(self.ctx)
  return true
end

return _M