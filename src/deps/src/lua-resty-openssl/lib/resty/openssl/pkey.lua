local ffi = require "ffi"
local C = ffi.C
local ffi_gc = ffi.gc
local ffi_new = ffi.new
local ffi_str = ffi.string
local ffi_cast = ffi.cast
local ffi_copy = ffi.copy

local rsa_macro = require "resty.openssl.include.rsa"
local dh_macro = require "resty.openssl.include.dh"
require "resty.openssl.include.bio"
require "resty.openssl.include.pem"
require "resty.openssl.include.x509"
require "resty.openssl.include.evp.pkey"
local evp_macro = require "resty.openssl.include.evp"
local pkey_macro = require "resty.openssl.include.evp.pkey"
local bio_util = require "resty.openssl.auxiliary.bio"
local digest_lib = require "resty.openssl.digest"
local rsa_lib = require "resty.openssl.rsa"
local dh_lib = require "resty.openssl.dh"
local ec_lib = require "resty.openssl.ec"
local ecx_lib = require "resty.openssl.ecx"
local objects_lib = require "resty.openssl.objects"
local jwk_lib = require "resty.openssl.auxiliary.jwk"
local ctx_lib = require "resty.openssl.ctx"
local ctypes = require "resty.openssl.auxiliary.ctypes"
local ecdsa_util = require "resty.openssl.auxiliary.ecdsa"
local format_error = require("resty.openssl.err").format_error

local OPENSSL_11_OR_LATER = require("resty.openssl.version").OPENSSL_11_OR_LATER
local OPENSSL_111_OR_LATER = require("resty.openssl.version").OPENSSL_111_OR_LATER
local OPENSSL_3X = require("resty.openssl.version").OPENSSL_3X
local BORINGSSL = require("resty.openssl.version").BORINGSSL

local ptr_of_uint = ctypes.ptr_of_uint
local ptr_of_size_t = ctypes.ptr_of_size_t
local ptr_of_int = ctypes.ptr_of_int

local null = ctypes.null
local load_pem_args = { null, null, null }
local load_der_args = { null }

local get_pkey_key
if OPENSSL_11_OR_LATER then
  get_pkey_key = {
    [evp_macro.EVP_PKEY_RSA] = function(ctx) return C.EVP_PKEY_get0_RSA(ctx) end,
    [evp_macro.EVP_PKEY_EC] = function(ctx) return C.EVP_PKEY_get0_EC_KEY(ctx) end,
    [evp_macro.EVP_PKEY_DH]  = function(ctx) return C.EVP_PKEY_get0_DH(ctx) end
  }
else
  get_pkey_key = {
    [evp_macro.EVP_PKEY_RSA] = function(ctx) return ctx.pkey and ctx.pkey.rsa end,
    [evp_macro.EVP_PKEY_EC] = function(ctx) return ctx.pkey and ctx.pkey.ec end,
    [evp_macro.EVP_PKEY_DH]  = function(ctx) return ctx.pkey and ctx.pkey.dh end,
  }
end

local load_rsa_key_funcs

if not OPENSSL_3X then
  load_rsa_key_funcs= {
    ['PEM_read_bio_RSAPrivateKey'] = true,
    ['PEM_read_bio_RSAPublicKey'] = true,
  } -- those functions return RSA* instead of EVP_PKEY*
end

local function load_pem_der(txt, opts, funcs)
  local fmt = opts.format or '*'
  if fmt ~= 'PEM' and fmt ~= 'DER' and fmt ~= "JWK" and fmt ~= '*' then
    return nil, "expecting 'DER', 'PEM', 'JWK' or '*' as \"format\""
  end

  local typ = opts.type or '*'
  if typ ~= 'pu' and typ ~= 'pr' and typ ~= '*' then
    return nil, "expecting 'pr', 'pu' or '*' as \"type\""
  end

  if fmt == "JWK" and (typ == "pu" or type == "pr") then
    return nil, "explictly load private or public key from JWK format is not supported"
  end

  ngx.log(ngx.DEBUG, "load key using fmt: ", fmt, ", type: ", typ)

  local bio = C.BIO_new_mem_buf(txt, #txt)
  if bio == nil then
    return nil, "BIO_new_mem_buf() failed"
  end
  ffi_gc(bio, C.BIO_free)

  local ctx

  local fs = funcs[fmt][typ]
  local passphrase_cb
  for f, arg in pairs(fs) do
    -- don't need BIO when loading JWK key: we parse it in Lua land
    if f == "load_jwk" then
      local err
      ctx, err = jwk_lib[f](txt)
      if ctx == nil then
        -- if fmt is explictly set to JWK, we should return an error now
        if fmt == "JWK" then
          return nil, err
        end
        ngx.log(ngx.DEBUG, "jwk decode failed: ", err, ", continuing")
      end
    else
      -- #define BIO_CTRL_RESET 1
      local code = C.BIO_ctrl(bio, 1, 0, nil)
      if code ~= 1 then
        return nil, "BIO_ctrl() failed"
      end

      -- only pass in passphrase/passphrase_cb to PEM_* functions
      if fmt == "PEM" or (fmt == "*" and arg == load_pem_args) then
        if opts.passphrase then
          local passphrase = opts.passphrase
          if type(passphrase) ~= "string" then
            -- clear errors occur when trying
            C.ERR_clear_error()
            return nil, "passphrase must be a string"
          end
          arg = { null, nil, passphrase }
        elseif opts.passphrase_cb then
          passphrase_cb = passphrase_cb or ffi_cast("pem_password_cb", function(buf, size)
            local p = opts.passphrase_cb()
            local len = #p -- 1 byte for \0
            if len > size then
              ngx.log(ngx.WARN, "pkey:load_pem_der: passphrase truncated from ", len, " to ", size)
              len = size
            end
            ffi_copy(buf, p, len)
            return len
          end)
          arg = { null, passphrase_cb, null }
        end
      end

      ctx = C[f](bio, unpack(arg))
    end

    if ctx ~= nil then
      ngx.log(ngx.DEBUG, "pkey:load_pem_der: loaded pkey using function ", f)

      -- pkcs1 functions create a rsa rather than evp_pkey
      -- disable the checking in openssl 3.0 for sail safe
      if not OPENSSL_3X and load_rsa_key_funcs[f] then
        local rsa = ctx
        ctx = C.EVP_PKEY_new()
        if ctx == null then
          return nil, format_error("pkey:load_pem_der: EVP_PKEY_new")
        end

        if C.EVP_PKEY_assign(ctx, evp_macro.EVP_PKEY_RSA, rsa) ~= 1 then
          C.RSA_free(rsa)
          C.EVP_PKEY_free(ctx)
          return nil, "pkey:load_pem_der: EVP_PKEY_assign() failed"
        end
      end

      break
    end
  end
  if passphrase_cb ~= nil then
    passphrase_cb:free()
  end

  if ctx == nil then
    return nil, format_error()
  end
  -- clear errors occur when trying
  C.ERR_clear_error()
  return ctx, nil
end

local function generate_param(key_type, config)
  if key_type == evp_macro.EVP_PKEY_DH then
    local dh_group = config.group
    if dh_group then
      local get_group_func = dh_macro.dh_groups[dh_group]
      if not get_group_func then
        return nil, "unknown pre-defined group " .. dh_group
      end
      local ctx = get_group_func()
      if ctx == nil then
        return nil, format_error("DH_get_x")
      end
      local params = C.EVP_PKEY_new()
      if not params then
        return nil, format_error("EVP_PKEY_new")
      end
      ffi_gc(params, C.EVP_PKEY_free)
      if C.EVP_PKEY_assign(params, key_type, ctx) ~= 1 then
        return nil, format_error("EVP_PKEY_assign")
      end
      return params
    end
  end

  local pctx = C.EVP_PKEY_CTX_new_id(key_type, nil)
  if pctx == nil then
    return nil, format_error("EVP_PKEY_CTX_new_id")
  end
  ffi_gc(pctx, C.EVP_PKEY_CTX_free)

  if C.EVP_PKEY_paramgen_init(pctx) ~= 1 then
    return nil, format_error("EVP_PKEY_paramgen_init")
  end

  if key_type == evp_macro.EVP_PKEY_EC then
    local curve = config.curve or 'prime192v1'
    local nid = C.OBJ_ln2nid(curve)
    if nid == 0 then
      return nil, "unknown curve " .. curve
    end
    if pkey_macro.EVP_PKEY_CTX_set_ec_paramgen_curve_nid(pctx, nid) <= 0 then
      return nil, format_error("EVP_PKEY_CTX_ctrl: EC: curve_nid")
    end
    if not BORINGSSL then
      -- use the named-curve encoding for best backward-compatibilty
      -- and for playing well with go:crypto/x509
      -- # define OPENSSL_EC_NAMED_CURVE  0x001
      if pkey_macro.EVP_PKEY_CTX_set_ec_param_enc(pctx, 1) <= 0 then
        return nil, format_error("EVP_PKEY_CTX_ctrl: EC: param_enc")
      end
    end
  elseif key_type == evp_macro.EVP_PKEY_DH then
    local bits = config.bits
    if not config.param and not bits then
      bits = 2048
    end
    if bits and pkey_macro.EVP_PKEY_CTX_set_dh_paramgen_prime_len(pctx, bits) <= 0 then
      return nil, format_error("EVP_PKEY_CTX_ctrl: DH: bits")
    end
  end

  local ctx_ptr = ffi_new("EVP_PKEY*[1]")
  if C.EVP_PKEY_paramgen(pctx, ctx_ptr) ~= 1 then
    return nil, format_error("EVP_PKEY_paramgen")
  end

  local params = ctx_ptr[0]
  ffi_gc(params, C.EVP_PKEY_free)

  return params
end

local load_param_funcs = {
  [evp_macro.EVP_PKEY_EC] = {
    ["*"] = {
      ["*"] = {
        ['PEM_read_bio_ECPKParameters'] = load_pem_args,
        -- ['d2i_ECPKParameters_bio'] = load_der_args,
      }
    },
  },
  [evp_macro.EVP_PKEY_DH] = {
    ["*"] = {
      ["*"] = {
        ['PEM_read_bio_DHparams'] = load_pem_args,
        -- ['d2i_DHparams_bio'] = load_der_args,
      }
    },
  },
}

local function generate_key(config)
  local typ = config.type or 'RSA'
  local key_type

  if typ == "RSA" then
    key_type = evp_macro.EVP_PKEY_RSA
  elseif typ == "EC" then
    key_type = evp_macro.EVP_PKEY_EC
  elseif typ == "DH" then
    key_type = evp_macro.EVP_PKEY_DH
  elseif evp_macro.ecx_curves[typ] then
    key_type = evp_macro.ecx_curves[typ]
  else
    return nil, "unsupported type " .. typ
  end
  if key_type == 0 then
    return nil, "the linked OpenSSL library doesn't support " .. typ .. " key"
  end

  local pctx

  if key_type == evp_macro.EVP_PKEY_EC or key_type == evp_macro.EVP_PKEY_DH then
    local params, err
    if config.param then
      -- HACK
      config.type = nil
      local ctx, err = load_pem_der(config.param, config, load_param_funcs[key_type])
      if err then
        return nil, "load_pem_der: " .. err
      end
      if key_type == evp_macro.EVP_PKEY_EC then
        local ec_group = ctx
        ffi_gc(ec_group, C.EC_GROUP_free)
        ctx = C.EC_KEY_new()
        if ctx == nil then
          return nil, "EC_KEY_new() failed"
        end
        if C.EC_KEY_set_group(ctx, ec_group) ~= 1 then
          return nil, format_error("EC_KEY_set_group")
        end
      end
      params = C.EVP_PKEY_new()
      if not params then
        return nil, format_error("EVP_PKEY_new")
      end
      ffi_gc(params, C.EVP_PKEY_free)
      if C.EVP_PKEY_assign(params, key_type, ctx) ~= 1 then
        return nil, format_error("EVP_PKEY_assign")
      end
    else
      params, err = generate_param(key_type, config)
      if err then
        return nil, "generate_param: " .. err
      end
    end
    pctx = C.EVP_PKEY_CTX_new(params, nil)
    if pctx == nil then
      return nil, format_error("EVP_PKEY_CTX_new")
    end
  else
    pctx = C.EVP_PKEY_CTX_new_id(key_type, nil)
    if pctx == nil then
      return nil, format_error("EVP_PKEY_CTX_new_id")
    end
  end

  ffi_gc(pctx, C.EVP_PKEY_CTX_free)

  if C.EVP_PKEY_keygen_init(pctx) ~= 1 then
    return nil, format_error("EVP_PKEY_keygen_init")
  end
  -- RSA key parameters are set for keygen ctx not paramgen
  if key_type == evp_macro.EVP_PKEY_RSA then
    local bits = config.bits or 2048
    if bits > 4294967295 then
      return nil, "bits out of range"
    end

    if pkey_macro.EVP_PKEY_CTX_set_rsa_keygen_bits(pctx, bits) <= 0 then
      return nil, format_error("EVP_PKEY_CTX_ctrl: RSA: bits")
    end

    if config.exp then
      -- don't free exp as it's used internally in key
      local exp = C.BN_new()
      if exp == nil then
        return nil, "BN_new() failed"
      end
      C.BN_set_word(exp, config.exp)

      if pkey_macro.EVP_PKEY_CTX_set_rsa_keygen_pubexp(pctx, exp) <= 0 then
        return nil, format_error("EVP_PKEY_CTX_ctrl: RSA: exp")
      end
    end
  end
  local ctx_ptr = ffi_new("EVP_PKEY*[1]")
  -- TODO: move to use EVP_PKEY_gen after drop support for <1.1.1
  if C.EVP_PKEY_keygen(pctx, ctx_ptr) ~= 1 then
    return nil, format_error("EVP_PKEY_gen")
  end
  return ctx_ptr[0]
end

local load_key_try_funcs = {} do
  -- TODO: pkcs1 load functions are not required in openssl 3.0
  local _load_key_try_funcs = {
    PEM = {
      -- Note: make sure we always try load priv key first
      pr = {
        ['PEM_read_bio_PrivateKey'] = load_pem_args,
        -- disable in openssl3.0, PEM_read_bio_PrivateKey can read pkcs1 in 3.0
        ['PEM_read_bio_RSAPrivateKey'] = not OPENSSL_3X and load_pem_args or nil,
      },
      pu = {
        ['PEM_read_bio_PUBKEY'] = load_pem_args,
        -- disable in openssl3.0, PEM_read_bio_PrivateKey can read pkcs1 in 3.0
        ['PEM_read_bio_RSAPublicKey'] = not OPENSSL_3X and load_pem_args or nil,
      },
    },
    DER = {
      pr = { ['d2i_PrivateKey_bio'] = load_der_args, },
      pu = { ['d2i_PUBKEY_bio'] = load_der_args, },
    },
    JWK = {
      pr = { ['load_jwk'] = {}, },
    }
  }
  -- populate * funcs
  local all_funcs = {}
  local typ_funcs = {}
  for fmt, ffs in pairs(_load_key_try_funcs) do
    load_key_try_funcs[fmt] = ffs

    local funcs = {}
    for typ, fs in pairs(ffs) do
      for f, arg in pairs(fs) do
        funcs[f] = arg
        all_funcs[f] = arg
        if not typ_funcs[typ] then
          typ_funcs[typ] = {}
        end
        typ_funcs[typ] = arg
      end
    end
    load_key_try_funcs[fmt]["*"] = funcs
  end
  load_key_try_funcs["*"] = {}
  load_key_try_funcs["*"]["*"] = all_funcs
  for typ, fs in pairs(typ_funcs) do
    load_key_try_funcs[typ] = fs
  end
end

local function __tostring(self, is_priv, fmt, is_pkcs1)
  if fmt == "JWK" then
    return jwk_lib.dump_jwk(self, is_priv)
  elseif is_pkcs1 then
    if fmt ~= "PEM" or self.key_type ~= evp_macro.EVP_PKEY_RSA then
      return nil, "PKCS#1 format is only supported to encode RSA key in \"PEM\" format"
    elseif OPENSSL_3X then -- maybe possible with OSSL_ENCODER_CTX_new_for_pkey though
      return nil, "writing out RSA key in PKCS#1 format is not supported in OpenSSL 3.0"
    end
  end
  if is_priv then
    if fmt == "DER" then
      return bio_util.read_wrap(C.i2d_PrivateKey_bio, self.ctx)
    end
    -- PEM
    if is_pkcs1 then
      local rsa = get_pkey_key[evp_macro.EVP_PKEY_RSA](self.ctx)
      if rsa == nil then
        return nil, "unable to read RSA key for writing"
      end
      return bio_util.read_wrap(C.PEM_write_bio_RSAPrivateKey,
        rsa,
        nil, nil, 0, nil, nil)
    end
    return bio_util.read_wrap(C.PEM_write_bio_PrivateKey,
      self.ctx,
      nil, nil, 0, nil, nil)
  else
    if fmt == "DER" then
      return bio_util.read_wrap(C.i2d_PUBKEY_bio, self.ctx)
    end
    -- PEM
    if is_pkcs1 then
      local rsa = get_pkey_key[evp_macro.EVP_PKEY_RSA](self.ctx)
      if rsa == nil then
        return nil, "unable to read RSA key for writing"
      end
      return bio_util.read_wrap(C.PEM_write_bio_RSAPublicKey, rsa)
    end
    return bio_util.read_wrap(C.PEM_write_bio_PUBKEY, self.ctx)
  end

end

local _M = {}
local mt = { __index = _M, __tostring = __tostring }

local empty_table = {}
local evp_pkey_ptr_ct = ffi.typeof('EVP_PKEY*')

function _M.new(s, opts)
  local ctx, err
  s = s or {}
  if type(s) == 'table' then
    ctx, err = generate_key(s)
    if err then
      err = "pkey.new:generate_key: " .. err
    end
  elseif type(s) == 'string' then
    ctx, err = load_pem_der(s, opts or empty_table, load_key_try_funcs)
    if err then
      err = "pkey.new:load_key: " .. err
    end
  elseif type(s) == 'cdata' then
    if ffi.istype(evp_pkey_ptr_ct, s) then
      ctx = s
    else
      return nil, "pkey.new: expect a EVP_PKEY* cdata at #1"
    end
  else
    return nil, "pkey.new: unexpected type " .. type(s) .. " at #1"
  end

  if err then
    return nil, err
  end

  ffi_gc(ctx, C.EVP_PKEY_free)

  local key_type = OPENSSL_3X and C.EVP_PKEY_get_base_id(ctx) or C.EVP_PKEY_base_id(ctx)
  if key_type == 0 then
    return nil, "pkey.new: cannot get key_type"
  end
  local key_type_is_ecx = (key_type == evp_macro.EVP_PKEY_ED25519) or
                          (key_type == evp_macro.EVP_PKEY_X25519) or
                          (key_type == evp_macro.EVP_PKEY_ED448) or
                          (key_type == evp_macro.EVP_PKEY_X448)

  -- although OpenSSL discourages to use this size for digest/verify
  -- but this is good enough for now
  local buf_size = OPENSSL_3X and C.EVP_PKEY_get_size(ctx) or C.EVP_PKEY_size(ctx)

  local self = setmetatable({
    ctx = ctx,
    pkey_ctx = nil,
    rsa_padding = nil,
    key_type = key_type,
    key_type_is_ecx = key_type_is_ecx,
    buf = ctypes.uchar_array(buf_size),
    buf_size = buf_size,
  }, mt)

  return self, nil
end

function _M.istype(l)
  return l and l.ctx and ffi.istype(evp_pkey_ptr_ct, l.ctx)
end

function _M:get_key_type()
  return objects_lib.nid2table(self.key_type)
end

function _M:get_default_digest_type()
  if BORINGSSL then
    return nil, "BoringSSL doesn't have default digest for pkey"
  end

  local nid = ptr_of_int()
  local code = C.EVP_PKEY_get_default_digest_nid(self.ctx, nid)
  if code == -2 then
    return nil, "operation is not supported by the public key algorithm"
  elseif code <= 0 then
    return nil, format_error("get_default_digest", code)
  end

  local ret = objects_lib.nid2table(nid[0])
  ret.mandatory = code == 2
  return ret
end

function _M:get_provider_name()
  if not OPENSSL_3X then
    return false, "pkey:get_provider_name is not supported"
  end
  local p = C.EVP_PKEY_get0_provider(self.ctx)
  if p == nil then
    return nil
  end
  return ffi_str(C.OSSL_PROVIDER_get0_name(p))
end

if OPENSSL_3X then
  local param_lib = require "resty.openssl.param"
  _M.settable_params, _M.set_params, _M.gettable_params, _M.get_param = param_lib.get_params_func("EVP_PKEY", "key_type")
end

function _M:get_parameters()
  if not self.key_type_is_ecx then
    local getter = get_pkey_key[self.key_type]
    if not getter then
      return nil, "key getter not defined"
    end
    local key = getter(self.ctx)
    if key == nil then
      return nil, format_error("EVP_PKEY_get0_{key}")
    end

    if self.key_type == evp_macro.EVP_PKEY_RSA then
      return rsa_lib.get_parameters(key)
    elseif self.key_type == evp_macro.EVP_PKEY_EC then
      return ec_lib.get_parameters(key)
    elseif self.key_type == evp_macro.EVP_PKEY_DH then
      return dh_lib.get_parameters(key)
    end
  else
    return ecx_lib.get_parameters(self.ctx)
  end
end

function _M:set_parameters(opts)
  if not self.key_type_is_ecx then
    local getter = get_pkey_key[self.key_type]
    if not getter then
      return nil, "key getter not defined"
    end
    local key = getter(self.ctx)
    if key == nil then
      return nil, format_error("EVP_PKEY_get0_{key}")
    end

    if self.key_type == evp_macro.EVP_PKEY_RSA then
      return rsa_lib.set_parameters(key, opts)
    elseif self.key_type == evp_macro.EVP_PKEY_EC then
      return ec_lib.set_parameters(key, opts)
    elseif self.key_type == evp_macro.EVP_PKEY_DH then
      return dh_lib.set_parameters(key, opts)
    end
  else
    -- for ecx keys we always create a new EVP_PKEY and release the old one
    local ctx, err = ecx_lib.set_parameters(self.key_type, self.ctx, opts)
    if err then
      return false, err
    end
    self.ctx = ctx
  end
end

function _M:is_private()
  local params = self:get_parameters()
  if self.key_type == evp_macro.EVP_PKEY_RSA then
    return params.d ~= nil
  else
    return params.private ~= nil
  end
end

local ASYMMETRIC_OP_ENCRYPT = 0x1
local ASYMMETRIC_OP_DECRYPT = 0x2
local ASYMMETRIC_OP_SIGN_RAW = 0x4
local ASYMMETRIC_OP_VERIFY_RECOVER = 0x8

local function asymmetric_routine(self, s, op, padding)
  local pkey_ctx

  if self.key_type == evp_macro.EVP_PKEY_RSA then
    if padding then
      padding = tonumber(padding)
      if not padding then
        return nil, "invalid padding: " .. __tostring(padding)
      end
    else
      padding = rsa_macro.paddings.RSA_PKCS1_PADDING
    end
  end

  if self.pkey_ctx ~= nil and
      (self.key_type ~= evp_macro.EVP_PKEY_RSA or self.rsa_padding == padding) then
        pkey_ctx = self.pkey_ctx
  else
    pkey_ctx = C.EVP_PKEY_CTX_new(self.ctx, nil)
    if pkey_ctx == nil then
      return nil, format_error("pkey:asymmetric_routine EVP_PKEY_CTX_new()")
    end
    ffi_gc(pkey_ctx, C.EVP_PKEY_CTX_free)
    self.pkey_ctx = pkey_ctx
  end

  local f, fint, op_name
  if op == ASYMMETRIC_OP_ENCRYPT then
    fint = C.EVP_PKEY_encrypt_init
    f = C.EVP_PKEY_encrypt
    op_name = "encrypt"
  elseif op == ASYMMETRIC_OP_DECRYPT then
    fint = C.EVP_PKEY_decrypt_init
    f = C.EVP_PKEY_decrypt
    op_name = "decrypt"
  elseif op == ASYMMETRIC_OP_SIGN_RAW then
    fint = C.EVP_PKEY_sign_init
    f = C.EVP_PKEY_sign
    op_name = "sign"
  elseif op == ASYMMETRIC_OP_VERIFY_RECOVER then
    fint = C.EVP_PKEY_verify_recover_init
    f = C.EVP_PKEY_verify_recover
    op_name = "verify_recover"
  else
    error("bad \"op\", got " .. op, 2)
  end

  local code = fint(pkey_ctx)
  if code < 1 then
    return nil, format_error("pkey:asymmetric_routine EVP_PKEY_" .. op_name .. "_init", code)
  end

  -- EVP_PKEY_CTX_ctrl must be called after *_init
  if self.key_type == evp_macro.EVP_PKEY_RSA and padding then
    if pkey_macro.EVP_PKEY_CTX_set_rsa_padding(pkey_ctx, padding) ~= 1 then
      return nil, format_error("pkey:asymmetric_routine EVP_PKEY_CTX_set_rsa_padding")
    end
    self.rsa_padding = padding
  end

  local length = ptr_of_size_t(self.buf_size)

  if f(pkey_ctx, self.buf, length, s, #s) <= 0 then
    return nil, format_error("pkey:asymmetric_routine EVP_PKEY_" .. op_name)
  end

  return ffi_str(self.buf, length[0]), nil
end

_M.PADDINGS = rsa_macro.paddings

function _M:encrypt(s, padding)
  return asymmetric_routine(self, s, ASYMMETRIC_OP_ENCRYPT, padding)
end

function _M:decrypt(s, padding)
  return asymmetric_routine(self, s, ASYMMETRIC_OP_DECRYPT, padding)
end

function _M:sign_raw(s, padding)
  -- TODO: temporary hack before OpenSSL has proper check for existence of private key
  if self.key_type_is_ecx and not self:is_private() then
    return nil, "pkey:sign_raw: missing private key"
  end

  return asymmetric_routine(self, s, ASYMMETRIC_OP_SIGN_RAW, padding)
end

function _M:verify_recover(s, padding)
  return asymmetric_routine(self, s, ASYMMETRIC_OP_VERIFY_RECOVER, padding)
end

local evp_pkey_ctx_ptr_ptr_ct = ffi.typeof('EVP_PKEY_CTX*[1]')

local function sign_verify_prepare(self, fint, md_alg, padding, opts)
  local pkey_ctx

  if self.key_type == evp_macro.EVP_PKEY_RSA and padding then
    pkey_ctx = C.EVP_PKEY_CTX_new(self.ctx, nil)
    if pkey_ctx == nil then
      return nil, format_error("pkey:sign_verify_prepare EVP_PKEY_CTX_new()")
    end
    ffi_gc(pkey_ctx, C.EVP_PKEY_CTX_free)
  end

  local md_ctx = C.EVP_MD_CTX_new()
  if md_ctx == nil then
    return nil, "pkey:sign_verify_prepare: EVP_MD_CTX_new() failed"
  end
  ffi_gc(md_ctx, C.EVP_MD_CTX_free)

  local algo
  if md_alg then
    if OPENSSL_3X then
      algo = C.EVP_MD_fetch(ctx_lib.get_libctx(), md_alg, nil)
    else
      algo = C.EVP_get_digestbyname(md_alg)
    end
    if algo == nil then
      return nil, string.format("pkey:sign_verify_prepare: invalid digest type \"%s\"", md_alg)
    end
  end

  local ppkey_ctx = evp_pkey_ctx_ptr_ptr_ct()
  ppkey_ctx[0] = pkey_ctx
  if fint(md_ctx, ppkey_ctx, algo, nil, self.ctx) ~= 1 then
    return nil, format_error("pkey:sign_verify_prepare: Init failed")
  end

  if self.key_type == evp_macro.EVP_PKEY_RSA then
    if padding then
      if pkey_macro.EVP_PKEY_CTX_set_rsa_padding(ppkey_ctx[0], padding) ~= 1 then
        return nil, format_error("pkey:sign_verify_prepare EVP_PKEY_CTX_set_rsa_padding")
      end
    end
    if opts and opts.pss_saltlen and padding ~= rsa_macro.paddings.RSA_PKCS1_PSS_PADDING then
      if pkey_macro.EVP_PKEY_CTX_set_rsa_pss_saltlen(ppkey_ctx[0], opts.pss_saltlen) ~= 1 then
        return nil, format_error("pkey:sign_verify_prepare EVP_PKEY_CTX_set_rsa_pss_saltlen")
      end
    end
  end

  return md_ctx
end

function _M:sign(digest, md_alg, padding, opts)
  -- TODO: temporary hack before OpenSSL has proper check for existence of private key
  if self.key_type_is_ecx and not self:is_private() then
    return nil, "pkey:sign: missing private key"
  end

  local ret, err

  if digest_lib.istype(digest) then
    local length = ptr_of_uint()
    if C.EVP_SignFinal(digest.ctx, self.buf, length, self.ctx) ~= 1 then
      return nil, format_error("pkey:sign: EVP_SignFinal")
    end
    ret = ffi_str(self.buf, length[0])
  elseif type(digest) == "string" then
    if not OPENSSL_111_OR_LATER and not BORINGSSL then
      -- we can still support earilier version with *Update and *Final
      -- but we choose to not relying on the legacy interface for simplicity
      return nil, "pkey:sign: new-style sign only available in OpenSSL 1.1.1 (or BoringSSL 1.1.0) or later"
    elseif BORINGSSL and not md_alg and not self.key_type_is_ecx then
      return nil, "pkey:sign: BoringSSL doesn't provide default digest, md_alg must be specified"
    end

    local md_ctx, err = sign_verify_prepare(self, C.EVP_DigestSignInit, md_alg, padding, opts)
    if err then
      return nil, err
    end

    local length = ptr_of_size_t(self.buf_size)
    if C.EVP_DigestSign(md_ctx, self.buf, length, digest, #digest) ~= 1 then
      return nil, format_error("pkey:sign: EVP_DigestSign")
    end
    ret = ffi_str(self.buf, length[0])
  else
    return nil, "pkey:sign: expect a digest instance or a string at #1"
  end

  if self.key_type == evp_macro.EVP_PKEY_EC and opts and opts.ecdsa_use_raw then
    if not OPENSSL_11_OR_LATER then
      return nil, "pkey:sign: opts.ecdsa_use_raw is only supported on OpenSSL 1.1.0 or later"
    end

    local ec_key = get_pkey_key[evp_macro.EVP_PKEY_EC](self.ctx)

    ret, err = ecdsa_util.sig_der2raw(ret, ec_key)
    if err then
      return nil, "pkey:sign: ecdsa.sig_der2raw: " .. err
    end
  end

  return ret
end

function _M:verify(signature, digest, md_alg, padding, opts)
  if type(signature) ~= "string" then
    return nil, "pkey:verify: expect a string at #1"
  end
  local err

  if self.key_type == evp_macro.EVP_PKEY_EC and opts and opts.ecdsa_use_raw then
    if not OPENSSL_11_OR_LATER then
      return nil, "pkey:sign: opts.ecdsa_use_raw is only supported on OpenSSL 1.1.0 or later"
    end

    local ec_key = get_pkey_key[evp_macro.EVP_PKEY_EC](self.ctx)

    signature, err = ecdsa_util.sig_raw2der(signature, ec_key)
    if err then
      return nil, "pkey:sign: ecdsa.sig_raw2der: " .. err
    end
  end

  local code
  if digest_lib.istype(digest) then
    code = C.EVP_VerifyFinal(digest.ctx, signature, #signature, self.ctx)
  elseif type(digest) == "string" then
    if not OPENSSL_111_OR_LATER and not BORINGSSL then
      -- we can still support earilier version with *Update and *Final
      -- but we choose to not relying on the legacy interface for simplicity
      return nil, "pkey:verify: new-style verify only available in OpenSSL 1.1.1 (or BoringSSL 1.1.0) or later"
    elseif BORINGSSL and not md_alg and not self.key_type_is_ecx then
      return nil, "pkey:verify: BoringSSL doesn't provide default digest, md_alg must be specified"
    end

    local md_ctx, err = sign_verify_prepare(self, C.EVP_DigestVerifyInit, md_alg, padding, opts)
    if err then
      return nil, err
    end

    code = C.EVP_DigestVerify(md_ctx, signature, #signature, digest, #digest)
  else
    return nil, "pkey:verify: expect a digest instance or a string at #2"
  end

  if code == 0 then
    return false, nil
  elseif code == 1 then
    return true, nil
  end
  return false, format_error("pkey:verify")
end

function _M:derive(peerkey)
  if not self.istype(peerkey) then
    return nil, "pkey:derive: expect a pkey instance at #1"
  end
  local pctx = C.EVP_PKEY_CTX_new(self.ctx, nil)
  if pctx == nil then
    return nil, "pkey:derive: EVP_PKEY_CTX_new() failed"
  end
  ffi_gc(pctx, C.EVP_PKEY_CTX_free)
  local code = C.EVP_PKEY_derive_init(pctx)
  if code <= 0 then
    return nil, format_error("pkey:derive: EVP_PKEY_derive_init", code)
  end

  code = C.EVP_PKEY_derive_set_peer(pctx, peerkey.ctx)
  if code <= 0 then
    return nil, format_error("pkey:derive: EVP_PKEY_derive_set_peer", code)
  end

  local buflen = ptr_of_size_t()
  code = C.EVP_PKEY_derive(pctx, nil, buflen)
  if code <= 0 then
    return nil, format_error("pkey:derive: EVP_PKEY_derive check buffer size", code)
  end

  local buf = ctypes.uchar_array(buflen[0])
  code = C.EVP_PKEY_derive(pctx, buf, buflen)
  if code <= 0 then
    return nil, format_error("pkey:derive: EVP_PKEY_derive", code)
  end

  return ffi_str(buf, buflen[0])
end

local function pub_or_priv_is_pri(pub_or_priv)
  if pub_or_priv == 'private' or pub_or_priv == 'PrivateKey' then
    return true
  elseif not pub_or_priv or pub_or_priv == 'public' or pub_or_priv == 'PublicKey' then
    return false
  else
    return nil, string.format("can only export private or public key, not %s", pub_or_priv)
  end
end

function _M:tostring(pub_or_priv, fmt, pkcs1)
  local is_priv, err = pub_or_priv_is_pri(pub_or_priv)
  if err then
    return nil, "pkey:tostring: " .. err
  end
  return __tostring(self, is_priv, fmt, pkcs1)
end

function _M:to_PEM(pub_or_priv, pkcs1)
  return self:tostring(pub_or_priv, "PEM", pkcs1)
end

function _M.paramgen(config)
  local typ = config.type
  local key_type, write_func, get_ctx_func
  if typ == "EC" then
    key_type = evp_macro.EVP_PKEY_EC
    if key_type == 0 then
      return nil, "pkey.paramgen: the linked OpenSSL library doesn't support EC key"
    end
    write_func = C.PEM_write_bio_ECPKParameters
    get_ctx_func = function(ctx)
      local ctx = get_pkey_key[key_type](ctx)
      if ctx == nil then
        error(format_error("pkey.paramgen: EVP_PKEY_get0_{key}"))
      end
      return C.EC_KEY_get0_group(ctx)
    end
  elseif typ == "DH" then
    key_type = evp_macro.EVP_PKEY_DH
    if key_type == 0 then
      return nil, "pkey.paramgen: the linked OpenSSL library doesn't support DH key"
    end
    write_func = C.PEM_write_bio_DHparams
    get_ctx_func = get_pkey_key[key_type]
  else
    return nil, "pkey.paramgen: unsupported type " .. type
  end

  local params, err = generate_param(key_type, config)
  if err then
    return nil, "pkey.paramgen: generate_param: " .. err
  end

  local ctx = get_ctx_func(params)
  if ctx == nil then
    return nil, format_error("pkey.paramgen: EVP_PKEY_get0_{key}")
  end

  return bio_util.read_wrap(write_func, ctx)
end

return _M
