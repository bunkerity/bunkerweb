local ffi = require "ffi"
local C = ffi.C

local bn_lib = require "resty.openssl.bn"

local OPENSSL_10 = require("resty.openssl.version").OPENSSL_10
local OPENSSL_11_OR_LATER = require("resty.openssl.version").OPENSSL_11_OR_LATER
local format_error = require("resty.openssl.err").format_error

local _M = {}

_M.params = {"n", "e", "d", "p", "q", "dmp1", "dmq1", "iqmp"}

local empty_table = {}
local bn_ptrptr_ct = ffi.typeof("const BIGNUM *[1]")
function _M.get_parameters(rsa_st)
  -- {"n", "e", "d", "p", "q", "dmp1", "dmq1", "iqmp"}
  return setmetatable(empty_table, {
    __index = function(_, k)
      local ptr, ret
      if OPENSSL_11_OR_LATER then
        ptr = bn_ptrptr_ct()
      end

      if k == 'n' then
        if OPENSSL_11_OR_LATER then
          C.RSA_get0_key(rsa_st, ptr, nil, nil)
        end
      elseif k == 'e' then
        if OPENSSL_11_OR_LATER then
          C.RSA_get0_key(rsa_st, nil, ptr, nil)
        end
      elseif k == 'd' then
        if OPENSSL_11_OR_LATER then
          C.RSA_get0_key(rsa_st, nil, nil, ptr)
        end
      elseif k == 'p' then
        if OPENSSL_11_OR_LATER then
          C.RSA_get0_factors(rsa_st, ptr, nil)
        end
      elseif k == 'q' then
        if OPENSSL_11_OR_LATER then
          C.RSA_get0_factors(rsa_st, nil, ptr)
        end
      elseif k == 'dmp1' then
        if OPENSSL_11_OR_LATER then
          C.RSA_get0_crt_params(rsa_st, ptr, nil, nil)
        end
      elseif k == 'dmq1' then
        if OPENSSL_11_OR_LATER then
          C.RSA_get0_crt_params(rsa_st, nil, ptr, nil)
        end
      elseif k == 'iqmp' then
        if OPENSSL_11_OR_LATER then
          C.RSA_get0_crt_params(rsa_st, nil, nil, ptr)
        end
      else
        return nil, "rsa.get_parameters: unknown parameter \"" .. k .. "\" for RSA key"
      end

      if OPENSSL_11_OR_LATER then
        ret = ptr[0]
      elseif OPENSSL_10 then
        ret = rsa_st[k]
      end

      if ret == nil then
        return nil
      end
      return bn_lib.dup(ret)
    end
  }), nil
end

local function dup_bn_value(v)
  if not bn_lib.istype(v) then
    return nil, "expect value to be a bn instance"
  end
  local bn = C.BN_dup(v.ctx)
  if bn == nil then
    return nil, "BN_dup() failed"
  end
  return bn
end

function _M.set_parameters(rsa_st, opts)
  local err
  local opts_bn = {}
  -- remember which parts of BNs has been added to rsa_st, they should be freed
  -- by RSA_free and we don't cleanup them on failure
  local cleanup_from_idx = 1
  -- dup input
  local do_set_key, do_set_factors, do_set_crt_params
  for k, v in pairs(opts) do
    opts_bn[k], err = dup_bn_value(v)
    if err then
      err = "rsa.set_parameters: cannot process parameter \"" .. k .. "\":" .. err
      goto cleanup_with_error
    end
    if k == "n" or k == "e" or k == "d" then
      do_set_key = true
    elseif k == "p" or k == "q" then
      do_set_factors = true
    elseif k == "dmp1" or k == "dmq1" or k == "iqmp" then
      do_set_crt_params = true
    end
  end
  if OPENSSL_11_OR_LATER then
    -- "The values n and e must be non-NULL the first time this function is called on a given RSA object."
    -- thus we force to set them together
    local code
    if do_set_key then
      code = C.RSA_set0_key(rsa_st, opts_bn["n"], opts_bn["e"], opts_bn["d"])
      if code == 0 then
        err = format_error("rsa.set_parameters: RSA_set0_key")
        goto cleanup_with_error
      end
    end
    cleanup_from_idx = cleanup_from_idx + 3
    if do_set_factors then
      code = C.RSA_set0_factors(rsa_st, opts_bn["p"], opts_bn["q"])
      if code == 0 then
        err = format_error("rsa.set_parameters: RSA_set0_factors")
        goto cleanup_with_error
      end
    end
    cleanup_from_idx = cleanup_from_idx + 2
    if do_set_crt_params then
      code = C.RSA_set0_crt_params(rsa_st, opts_bn["dmp1"], opts_bn["dmq1"], opts_bn["iqmp"])
      if code == 0 then
        err = format_error("rsa.set_parameters: RSA_set0_crt_params")
        goto cleanup_with_error
      end
    end
    return true
  elseif OPENSSL_10 then
    for k, v in pairs(opts_bn) do
      if rsa_st[k] ~= nil then
        C.BN_free(rsa_st[k])
      end
      rsa_st[k]= v
    end
    return true
  end

::cleanup_with_error::
  for i, k in pairs(_M.params) do
    if i >= cleanup_from_idx then
      C.BN_free(opts_bn[k])
    end
  end
  return false, err
end

return _M
