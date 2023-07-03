local ffi = require "ffi"
local C = ffi.C
local ffi_gc = ffi.gc

require "resty.openssl.include.ec"
local bn_lib = require "resty.openssl.bn"
local objects_lib = require "resty.openssl.objects"
local ctypes = require "resty.openssl.auxiliary.ctypes"

local version_num = require("resty.openssl.version").version_num
local format_error = require("resty.openssl.err").format_error
local BORINGSSL = require("resty.openssl.version").BORINGSSL

local _M = {}

_M.params = {"group", "public", "private", "x", "y"}

local empty_table = {}

function _M.get_parameters(ec_key_st)
  return setmetatable(empty_table, {
    __index = function(_, k)
      local group = C.EC_KEY_get0_group(ec_key_st)
      local bn

      if k == 'group' then
        local nid = C.EC_GROUP_get_curve_name(group)
        if nid == 0 then
          return nil, "ec.get_parameters: EC_GROUP_get_curve_name() failed"
        end
        return nid
      elseif k == 'public' or k == "pub_key" then
        local pub_point = C.EC_KEY_get0_public_key(ec_key_st)
        if pub_point == nil then
          return nil, format_error("ec.get_parameters: EC_KEY_get0_public_key")
        end
        local point_form = C.EC_KEY_get_conv_form(ec_key_st)
        if point_form == nil then
          return nil, format_error("ec.get_parameters: EC_KEY_get_conv_form")
        end
        if BORINGSSL then
          local sz = tonumber(C.EC_POINT_point2oct(group, pub_point, point_form, nil, 0, bn_lib.bn_ctx_tmp))
          if sz <= 0 then
            return nil, format_error("ec.get_parameters: EC_POINT_point2oct")
          end
          local buf = ctypes.uchar_array(sz)
          C.EC_POINT_point2oct(group, pub_point, point_form, buf, sz, bn_lib.bn_ctx_tmp)
          buf = ffi.string(buf, sz)
          local err
          bn, err = bn_lib.from_binary(buf)
          if bn == nil then
            return nil, "ec.get_parameters: bn_lib.from_binary: " .. err
          end
          return bn
        else
          bn = C.EC_POINT_point2bn(group, pub_point, point_form, nil, bn_lib.bn_ctx_tmp)
          if bn == nil then
            return nil, format_error("ec.get_parameters: EC_POINT_point2bn")
          end
          ffi_gc(bn, C.BN_free)
        end
      elseif k == 'private' or k == "priv_key" then
        -- get0, don't GC
        bn = C.EC_KEY_get0_private_key(ec_key_st)
      elseif k == 'x' or k == 'y' then
        local pub_point = C.EC_KEY_get0_public_key(ec_key_st)
        if pub_point == nil then
          return nil, format_error("ec.get_parameters: EC_KEY_get0_public_key")
        end
        bn = C.BN_new()
        if bn == nil then
          return nil, "ec.get_parameters: BN_new() failed"
        end
        ffi_gc(bn, C.BN_free)
        local f
        if version_num >= 0x10101000 then
          f = C.EC_POINT_get_affine_coordinates
        else
          f = C.EC_POINT_get_affine_coordinates_GFp
        end
        local code
        if k == 'x' then
          code = f(group, pub_point, bn, nil, bn_lib.bn_ctx_tmp)
        else
          code = f(group, pub_point, nil, bn, bn_lib.bn_ctx_tmp)
        end
        if code ~= 1 then
          return nil, format_error("ec.get_parameters: EC_POINT_get_affine_coordinates")
        end
      else
        return nil, "ec.get_parameters: unknown parameter \"" .. k .. "\" for EC key"
      end

      if bn == nil then
       return nil
      end
      return bn_lib.dup(bn)
    end
  }), nil
end

function _M.set_parameters(ec_key_st, opts)
  for _, k in ipairs(_M.params) do
    if k ~= "group" then
      if opts[k] and not bn_lib.istype(opts[k]) then
        return nil, "expect parameter \"" .. k .. "\" to be a bn instance"
      end
    end
  end

  local group_nid = opts["group"]
  local group
  if group_nid then
    local nid, err = objects_lib.txtnid2nid(group_nid)
    if err then
      return nil, "ec.set_parameters: cannot use parameter \"group\":" .. err
    end

    group = C.EC_GROUP_new_by_curve_name(nid)
    if group == nil then
      return nil, "ec.set_parameters: EC_GROUP_new_by_curve_name() failed"
    end
    ffi_gc(group, C.EC_GROUP_free)
    -- # define OPENSSL_EC_NAMED_CURVE     0x001
    C.EC_GROUP_set_asn1_flag(group, 1)
    C.EC_GROUP_set_point_conversion_form(group, C.POINT_CONVERSION_UNCOMPRESSED)

    if C.EC_KEY_set_group(ec_key_st, group) ~= 1 then
      return nil, format_error("ec.set_parameters: EC_KEY_set_group")
    end
  end

  local x = opts["x"]
  local y = opts["y"]
  local pub = opts["public"]
  if (x and not y) or (y and not x) then
    return nil, "ec.set_parameters: \"x\" and \"y\" parameter must be defined at same time or both undefined"
  end

  if x and y then
    if pub then
      return nil, "ec.set_parameters: cannot set \"x\" and \"y\" with \"public\" at same time to set public key"
    end
    -- double check if we have set group already
    if group == nil then
      group = C.EC_KEY_get0_group(ec_key_st)
      if group == nil then
        return nil, "ec.set_parameters: cannot set public key without setting \"group\""
      end
    end

    if C.EC_KEY_set_public_key_affine_coordinates(ec_key_st, x.ctx, y.ctx) ~= 1 then
      return nil, format_error("ec.set_parameters: EC_KEY_set_public_key_affine_coordinates")
    end
  end

  if pub then
    if group == nil then
      group = C.EC_KEY_get0_group(ec_key_st)
      if group == nil then
        return nil, "ec.set_parameters: cannot set public key without setting \"group\""
      end
    end

    local point = C.EC_POINT_bn2point(group, pub.ctx, nil, bn_lib.bn_ctx_tmp)
    if point == nil then
      return nil, format_error("ec.set_parameters: EC_POINT_bn2point")
    end
    ffi_gc(point, C.EC_POINT_free)

    if C.EC_KEY_set_public_key(ec_key_st, point) ~= 1 then
      return nil, format_error("ec.set_parameters: EC_KEY_set_public_key")
    end
  end

  local priv = opts["private"]
  if priv then
    -- openssl duplicates it inside
    if C.EC_KEY_set_private_key(ec_key_st, priv.ctx) ~= 1 then
      return nil, format_error("ec.set_parameters: EC_KEY_set_private_key")
    end
  end

end

return _M
