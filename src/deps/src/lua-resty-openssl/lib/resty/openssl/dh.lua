local ffi = require "ffi"
local C = ffi.C

require "resty.openssl.include.dh"
local bn_lib = require "resty.openssl.bn"

local format_error = require("resty.openssl.err").format_error

local _M = {}

_M.params = {"public", "private", "p", "q", "g"}

local empty_table = {}
local bn_ptrptr_ct = ffi.typeof("const BIGNUM *[1]")
function _M.get_parameters(dh_st)
  return setmetatable(empty_table, {
    __index = function(_, k)
      local ptr, ret
      ptr = bn_ptrptr_ct()

      if k == 'p' then
        C.DH_get0_pqg(dh_st, ptr, nil, nil)
      elseif k == 'q' then
        C.DH_get0_pqg(dh_st, nil, ptr, nil)
      elseif k == 'g' then
        C.DH_get0_pqg(dh_st, nil, nil, ptr)
      elseif k == 'public' then
        C.DH_get0_key(dh_st, ptr, nil)
      elseif k == 'private' then
        C.DH_get0_key(dh_st, nil, ptr)
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

function _M.set_parameters(dh_st, opts)
  local err
  local opts_bn = {}
  -- remember which parts of BNs has been added to dh_st, they should be freed
  -- by DH_free and we don't cleanup them on failure
  local cleanup_from_idx = 1
  -- dup input
  local do_set_key, do_set_pqg

  while true do -- luacheck: ignore
    for k, v in pairs(opts) do
      opts_bn[k], err = dup_bn_value(v)
      if err then
        -- luacheck: ignore
        err = "dh.set_parameters: cannot process parameter \"" .. k .. "\":" .. err
        break
      end

      if k == "private" or k == "public" then
        do_set_key = true
      elseif k == "p" or k == "q" or k == "g" then
        do_set_pqg = true
      end
    end

    local code
    if do_set_key then
      code = C.DH_set0_key(dh_st, opts_bn["public"], opts_bn["private"])
      if code == 0 then
        err = format_error("dh.set_parameters: DH_set0_key")
        break
      end
    end

    cleanup_from_idx = cleanup_from_idx + 2
    if do_set_pqg then
      code = C.DH_set0_pqg(dh_st, opts_bn["p"], opts_bn["q"], opts_bn["g"])
      if code == 0 then
        err = format_error("dh.set_parameters: DH_set0_pqg")
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
