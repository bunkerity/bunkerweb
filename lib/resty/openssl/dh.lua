local ffi = require "ffi"
local C = ffi.C

require "resty.openssl.include.dh"
local bn_lib = require "resty.openssl.bn"

local OPENSSL_10 = require("resty.openssl.version").OPENSSL_10
local OPENSSL_11_OR_LATER = require("resty.openssl.version").OPENSSL_11_OR_LATER
local format_error = require("resty.openssl.err").format_error

local _M = {}

_M.params = {"public", "private", "p", "q", "g"}

local empty_table = {}
local bn_ptrptr_ct = ffi.typeof("const BIGNUM *[1]")
function _M.get_parameters(dh_st)
  return setmetatable(empty_table, {
    __index = function(_, k)
      local ptr, ret
      if OPENSSL_11_OR_LATER then
        ptr = bn_ptrptr_ct()
      end

      if OPENSSL_11_OR_LATER then
        ptr = bn_ptrptr_ct()
      end

      if k == 'p' then
        if OPENSSL_11_OR_LATER then
          C.DH_get0_pqg(dh_st, ptr, nil, nil)
        end
      elseif k == 'q' then
        if OPENSSL_11_OR_LATER then
          C.DH_get0_pqg(dh_st, nil, ptr, nil)
        end
      elseif k == 'g' then
        if OPENSSL_11_OR_LATER then
          C.DH_get0_pqg(dh_st, nil, nil, ptr)
        end
      elseif k == 'public' then
        if OPENSSL_11_OR_LATER then
          C.DH_get0_key(dh_st, ptr, nil)
        end
        k = "pub_key"
      elseif k == 'private' then
        if OPENSSL_11_OR_LATER then
          C.DH_get0_key(dh_st, nil, ptr)
        end
        k = "priv_key"
      else
        return nil, "rsa.get_parameters: unknown parameter \"" .. k .. "\" for RSA key"
      end

      if OPENSSL_11_OR_LATER then
        ret = ptr[0]
      elseif OPENSSL_10 then
        ret = dh_st[k]
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

function _M.set_parameters(dh_st, opts)
  local err
  local opts_bn = {}
  -- remember which parts of BNs has been added to dh_st, they should be freed
  -- by DH_free and we don't cleanup them on failure
  local cleanup_from_idx = 1
  -- dup input
  local do_set_key, do_set_pqg
  for k, v in pairs(opts) do
    opts_bn[k], err = dup_bn_value(v)
    if err then
      err = "dh.set_parameters: cannot process parameter \"" .. k .. "\":" .. err
      goto cleanup_with_error
    end
    if k == "private" or k == "public" then
      do_set_key = true
    elseif k == "p" or k == "q" or k == "g" then
      do_set_pqg = true
    end
  end
  if OPENSSL_11_OR_LATER then
    local code
    if do_set_key then
      code = C.DH_set0_key(dh_st, opts_bn["public"], opts_bn["private"])
      if code == 0 then
        err = format_error("dh.set_parameters: DH_set0_key")
        goto cleanup_with_error
      end
    end
    cleanup_from_idx = cleanup_from_idx + 2
    if do_set_pqg then
      code = C.DH_set0_pqg(dh_st, opts_bn["p"], opts_bn["q"], opts_bn["g"])
      if code == 0 then
        err = format_error("dh.set_parameters: DH_set0_pqg")
        goto cleanup_with_error
      end
    end
    return true
  elseif OPENSSL_10 then
    for k, v in pairs(opts_bn) do
      if k == "public" then
        k = "pub_key"
      elseif k == "private" then
        k = "priv_key"
      end
      if dh_st[k] ~= nil then
        C.BN_free(dh_st[k])
      end
      dh_st[k]= v
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
