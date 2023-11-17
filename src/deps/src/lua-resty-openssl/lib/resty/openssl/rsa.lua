local ffi = require "ffi"
local C = ffi.C

local bn_lib = require "resty.openssl.bn"
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
      ptr = bn_ptrptr_ct()

      if k == 'n' then
        C.RSA_get0_key(rsa_st, ptr, nil, nil)
      elseif k == 'e' then
        C.RSA_get0_key(rsa_st, nil, ptr, nil)
      elseif k == 'd' then
        C.RSA_get0_key(rsa_st, nil, nil, ptr)
      elseif k == 'p' then
        C.RSA_get0_factors(rsa_st, ptr, nil)
      elseif k == 'q' then
        C.RSA_get0_factors(rsa_st, nil, ptr)
      elseif k == 'dmp1' then
        C.RSA_get0_crt_params(rsa_st, ptr, nil, nil)
      elseif k == 'dmq1' then
        C.RSA_get0_crt_params(rsa_st, nil, ptr, nil)
      elseif k == 'iqmp' then
        C.RSA_get0_crt_params(rsa_st, nil, nil, ptr)
      else
        return nil, "rsa.get_parameters: unknown parameter \"" .. k .. "\" for RSA key"
      end

      ret = ptr[0]

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

  while true do -- luacheck: ignore
    for k, v in pairs(opts) do
      opts_bn[k], err = dup_bn_value(v)
      if err then
        -- luacheck: ignore
        err = "rsa.set_parameters: cannot process parameter \"" .. k .. "\":" .. err
        break
      end
      if k == "n" or k == "e" or k == "d" then
        do_set_key = true
      elseif k == "p" or k == "q" then
        do_set_factors = true
      elseif k == "dmp1" or k == "dmq1" or k == "iqmp" then
        do_set_crt_params = true
      end
    end

    -- "The values n and e must be non-NULL the first time this function is called on a given RSA object."
    -- thus we force to set them together
    local code
    if do_set_key then
      code = C.RSA_set0_key(rsa_st, opts_bn["n"], opts_bn["e"], opts_bn["d"])
      if code == 0 then
        err = format_error("rsa.set_parameters: RSA_set0_key")
        break
      end
    end

    cleanup_from_idx = cleanup_from_idx + 3
    if do_set_factors then
      code = C.RSA_set0_factors(rsa_st, opts_bn["p"], opts_bn["q"])
      if code == 0 then
        err = format_error("rsa.set_parameters: RSA_set0_factors")
        break
      end
    end

    cleanup_from_idx = cleanup_from_idx + 2
    if do_set_crt_params then
      code = C.RSA_set0_crt_params(rsa_st, opts_bn["dmp1"], opts_bn["dmq1"], opts_bn["iqmp"])
      if code == 0 then
        err = format_error("rsa.set_parameters: RSA_set0_crt_params")
        break
      end
    end

    return true
  end

  for i, k in pairs(_M.params) do
    if i >= cleanup_from_idx then
      C.BN_free(opts_bn[k])
    end
  end
  return false, err
end

return _M
