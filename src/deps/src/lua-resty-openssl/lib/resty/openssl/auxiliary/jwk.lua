
local ffi = require "ffi"
local C = ffi.C


local evp_macro = require "resty.openssl.include.evp"
local rsa_lib = require "resty.openssl.rsa"
local ec_lib = require "resty.openssl.ec"
local ecx_lib = require "resty.openssl.ecx"
local bn_lib = require "resty.openssl.bn"
local digest_lib = require "resty.openssl.digest"
local encode_base64url = require "resty.openssl.auxiliary.compat".encode_base64url
local decode_base64url = require "resty.openssl.auxiliary.compat".decode_base64url
local param_lib = require "resty.openssl.param"
local json = require "resty.openssl.auxiliary.compat".json
local format_error = require "resty.openssl.err".format_error

local OPENSSL_3X = require("resty.openssl.version").OPENSSL_3X

local _M = {}

local rsa_jwk_params = {"n", "e", "d", "p", "q", "dp", "dq", "qi"}
local rsa_openssl_params = rsa_lib.params

local function load_jwk_rsa(tbl)
  if not tbl["n"] or not tbl["e"] then
    return nil, "at least \"n\" and \"e\" parameter is required"
  end

  local params = {}
  local err
  for i, k in ipairs(rsa_jwk_params) do
    local v = tbl[k]
    if v then
      v = decode_base64url(v)
      if not v then
        return nil, "cannot decode parameter \"" .. k .. "\" from base64 " .. tbl[k]
      end

      params[rsa_openssl_params[i]], err = bn_lib.from_binary(v)
      if err then
        return nil, "cannot use parameter \"" .. k .. "\": " .. err
      end
    end
  end

  local key = C.RSA_new()
  if key == nil then
    return nil, "RSA_new() failed"
  end

  local _, err = rsa_lib.set_parameters(key, params)
  if err ~= nil then
    C.RSA_free(key)
    return nil, err
  end

  return key
end

local ec_curves = {
  ["P-256"] = C.OBJ_ln2nid("prime256v1"),
  ["P-384"] = C.OBJ_ln2nid("secp384r1"),
  ["P-521"] = C.OBJ_ln2nid("secp521r1"),
}

local ec_curves_reverse = {}
for k, v in pairs(ec_curves) do
  ec_curves_reverse[v] = k
end

local ec_jwk_params = {"x", "y", "d"}

local function load_jwk_ec(tbl)
  local curve = tbl['crv']
  if not curve then
    return nil, "\"crv\" not defined for EC key"
  end
  if not tbl["x"] or not tbl["y"] then
    return nil, "at least \"x\" and \"y\" parameter is required"
  end
  local curve_nid = ec_curves[curve]
  if not curve_nid then
    return nil, "curve \"" .. curve .. "\" is not supported by this library"
  elseif curve_nid == 0 then
    return nil, "curve \"" .. curve .. "\" is not supported by linked OpenSSL"
  end

  local params = {}
  local err
  for _, k in ipairs(ec_jwk_params) do
    local v = tbl[k]
    if v then
      v = decode_base64url(v)
      if not v then
        return nil, "cannot decode parameter \"" .. k .. "\" from base64 " .. tbl[k]
      end

      params[k], err = bn_lib.from_binary(v)
      if err then
        return nil, "cannot use parameter \"" .. k .. "\": " .. err
      end
    end
  end

  -- map to the name we expect
  if params["d"] then
    params["private"] = params["d"]
    params["d"] = nil
  end
  params["group"] = curve_nid

  local key = C.EC_KEY_new()
  if key == nil then
    return nil, "EC_KEY_new() failed"
  end

  local _, err = ec_lib.set_parameters(key, params)
  if err ~= nil then
    C.EC_KEY_free(key)
    return nil, err
  end

  return key
end

local function load_jwk_okp(key_type, tbl)
  local params = {}
  if tbl["d"] then
    params.private = decode_base64url(tbl["d"])
  elseif tbl["x"] then
    params.public = decode_base64url(tbl["x"])
  else
    return nil, "at least \"x\" or \"d\" parameter is required"
  end
  local key, err = ecx_lib.set_parameters(key_type, nil, params)
  if err ~= nil then
    return nil, err
  end
  return key
end

local ecx_curves_reverse = {}
for k, v in pairs(evp_macro.ecx_curves) do
  ecx_curves_reverse[v] = k
end

function _M.load_jwk(txt)
  local tbl, err = json.decode(txt)
  if err then
    return nil, "error decoding JSON from JWK: " .. err
  elseif type(tbl) ~= "table" then
    return nil, "except input to be decoded as a table, got " .. type(tbl)
  end

  local key, key_free, key_type, err

  if tbl["kty"] == "RSA" then
    key_type = evp_macro.EVP_PKEY_RSA
    if key_type == 0 then
      return nil, "the linked OpenSSL library doesn't support RSA key"
    end
    key, err = load_jwk_rsa(tbl)
    key_free = C.RSA_free
  elseif tbl["kty"] == "EC" then
    key_type = evp_macro.EVP_PKEY_EC
    if key_type == 0 then
      return nil, "the linked OpenSSL library doesn't support EC key"
    end
    key, err = load_jwk_ec(tbl)
    key_free = C.EC_KEY_free
  elseif tbl["kty"] == "OKP" then
    local curve = tbl["crv"]
    key_type = evp_macro.ecx_curves[curve]
    if not key_type then
      return nil, "unknown curve \"" .. tostring(curve)
    elseif key_type == 0 then
      return nil, "the linked OpenSSL library doesn't support \"" .. curve .. "\" key"
    end
    key, err = load_jwk_okp(key_type, tbl)
    if key ~= nil then
      return key
    end
    key_free = function() end
  else
    return nil, "not yet supported jwk type \"" .. (tbl["kty"] or "nil") .. "\""
  end

  if err then
    return nil, "failed to construct " .. tbl["kty"] .. " key from JWK: " .. err
  end

  local ctx = C.EVP_PKEY_new()
  if ctx == nil then
    key_free(key)
    return nil, "EVP_PKEY_new() failed"
  end

  local code = C.EVP_PKEY_assign(ctx, key_type, key)
  if code ~= 1 then
    key_free(key)
    C.EVP_PKEY_free(ctx)
    return nil, "EVP_PKEY_assign() failed"
  end

  return ctx
end

function _M.dump_jwk(pkey, is_priv)
  local jwk
  if is_priv and not pkey:is_private() then
      return nil, "jwk.dump_jwk: could not dump public key as private key"
  end

  if pkey.key_type == evp_macro.EVP_PKEY_RSA then
    local param_keys = { "n" , "e" }
    if is_priv then
      param_keys = rsa_jwk_params
    end
    local params, err = pkey:get_parameters()
    if err then
      return nil, "jwk.dump_jwk: " .. err
    end
    jwk = {
      kty = "RSA",
    }
    for i, p in ipairs(param_keys) do
      local v = params[rsa_openssl_params[i]]:to_binary()
      jwk[p] = encode_base64url(v)
    end
  elseif pkey.key_type == evp_macro.EVP_PKEY_EC then
    local params, err = pkey:get_parameters()
    if err then
      return nil, "jwk.dump_jwk: " .. err
    end
    jwk = {
      kty = "EC",
      crv = ec_curves_reverse[params.group],
      x = encode_base64url(params.x:to_binary()),
      y = encode_base64url(params.y:to_binary()),
    }
    if is_priv then
      jwk.d = encode_base64url(params.private:to_binary())
    end
  elseif ecx_curves_reverse[pkey.key_type] then
    local params, err = pkey:get_parameters()
    if err then
      return nil, "jwk.dump_jwk: " .. err
    end
    jwk = {
      kty = "OKP",
      crv = ecx_curves_reverse[pkey.key_type],
      x = encode_base64url(params.public),
    }
    if is_priv then
      jwk.d = encode_base64url(params.private)
    end
  else
    return nil, "jwk.dump_jwk: not implemented for this key type"
  end

  local der = pkey:tostring(is_priv and "private" or "public", "DER")
  local dgst = digest_lib.new("sha256")
  local d, err = dgst:final(der)
  if err then
    return nil, "jwk.dump_jwk: failed to calculate digest for key"
  end
  jwk.kid = encode_base64url(d)

  return json.encode(jwk)
end


-- 3.x load_jwk

local settable_schema = {}

local function get_settable_schema(type, selection, properties)
  -- the pctx can't be reused after EVP_PKEY_fromdata_settable, so we create a new here
  local pctx = C.EVP_PKEY_CTX_new_from_name(nil, type, properties)
  if pctx == nil then
    return nil, "EVP_PKEY_CTX_new_from_name() failed"
  end
  ffi.gc(pctx, C.EVP_PKEY_CTX_free)

  if C.EVP_PKEY_fromdata_init(pctx) ~= 1 then
    return nil, "EVP_PKEY_fromdata_init() failed"
  end

  if settable_schema[type] then
    return settable_schema[type]
  end

  local settable = C.EVP_PKEY_fromdata_settable(pctx, selection)
  if settable == nil then
    return nil, "EVP_PKEY_fromdata_settable() failed"
  end

  local schema = {}
  param_lib.parse_params_schema(settable, schema, nil)

  settable_schema[type] = schema
  return schema
end

local ossl_params_jwk_mapping = {
  RSA = {
    n = "n",
    e = "e",
    d = "d",
    p = "rsa-factor1",
    q = "rsa-factor2",
    dp = "rsa-exponent1",
    dq = "rsa-exponent2",
    qi = "rsa-coefficient1",
  },
  EC = {
    x = "x",
    y = "y",
    d = "priv",
    crv = "group",
  },
  OKP = {
    x = "pub",
    d = "priv",
  },
}

local jwk_params_required_mapping = {
  RSA = {
    n = true,
    e = true,
  },
  EC = {
    crv = true,
    x = true,
    y = true,
  },
  OKP = {
    -- crv = true, handled earlier
    x = true,
  },
}

function _M.load_jwk_ex(txt, ptyp, properties)
  local tbl, err = json.decode(txt)
  if err then
    return nil, "jwk:load_jwk: error decoding JSON from JWK: " .. err
  elseif type(tbl) ~= "table" then
    return nil, "jwk:load_jwk: except input to be decoded as a table, got " .. type(tbl)
  elseif not tbl["kty"] then
    return nil, "jwk:load_jwk: missing \"kty\" parameter from JWK"
  end

  local kty = tbl["kty"]
  tbl["kty"] = nil
  local selection = ptyp == "pu" and evp_macro.EVP_PKEY_PUBLIC_KEY or evp_macro.EVP_PKEY_KEYPAIR

  local pkey_name = kty
  if kty == "OKP" then
    pkey_name = tbl["crv"]
    if not pkey_name then
      return nil, "jwk:load_jwk: missing \"crv\" parameter from OKP JWK"
    end
    tbl["crv"] = nil
  end

  local ctx = ffi.new("EVP_PKEY*[1]")
  local pctx = C.EVP_PKEY_CTX_new_from_name(nil, pkey_name, nil)
  if pctx == nil then
    return nil, "jwk:load_jwk: EVP_PKEY_CTX_new_from_name() failed"
  end
  ffi.gc(pctx, C.EVP_PKEY_CTX_free)

  if C.EVP_PKEY_fromdata_init(pctx) ~= 1 then
    return nil, "jwk:load_jwk: EVP_PKEY_fromdata_init() failed"
  end

  local schema, err = get_settable_schema(pkey_name, selection, properties)
  if not schema then
    return nil, "jwk:load_jwk: failed to get key schema for " .. pkey_name .. " key: " .. err
  end

  local mapping = ossl_params_jwk_mapping[kty]
  if not mapping then
    return nil, "jwk:load_jwk: not yet supported jwk type \"" .. (tbl["kty"] or "nil") .. "\""
  end
  local required = jwk_params_required_mapping[kty]

  local params_t = {}

  for kfrom, kto in pairs(mapping) do
    local v = tbl[kfrom]
    if type(v) == "string" and (selection == evp_macro.EVP_PKEY_KEYPAIR or required[kfrom]) then
      if kfrom ~= "crv" then
        v = decode_base64url(v)
        if not v then
          return nil, "jwk:load_jwk: cannot decode parameter \"" .. kfrom .. "\" from base64 " .. tbl[kfrom]
        end
        -- reverse endian expect for OKP keys
        if kty ~= "OKP" or (kfrom ~= "x" and kfrom ~= "d") then
          v = v:reverse()
        end
      end

      params_t[kto] = v
    elseif required[kfrom] then
      return nil, "jwk:load_jwk: missing required parameter \"" .. kfrom .. "\""
    end
  end

  if kty == "EC" then
    if params_t["x"] and params_t["y"] then
      params_t["pub"] = "\x04" .. params_t["x"]:reverse() .. params_t["y"]:reverse()
      params_t["x"], params_t["y"] = nil, nil
    end
  end

  local params, err = param_lib.construct(params_t, nil, schema)
  if params == nil then
    return nil, "jwk:load_jwk: failed to construct parameters for " .. kty .. " key: " .. err
  end

  if C.EVP_PKEY_fromdata(pctx, ctx, selection, params) ~= 1 then
    return nil, format_error("jwk:load_jwk: EVP_PKEY_fromdata()")
  end

  return ctx[0]
end

if OPENSSL_3X then
  _M.load_jwk = _M.load_jwk_ex
end

return _M
