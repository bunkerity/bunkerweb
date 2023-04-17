local ffi = require "ffi"
local C = ffi.C
local ffi_gc = ffi.gc
local ffi_cast = ffi.cast

require "resty.openssl.include.x509"
require "resty.openssl.include.x509v3"
require "resty.openssl.include.err"
local altname_lib = require "resty.openssl.x509.altname"
local stack_lib = require "resty.openssl.stack"

local _M = {}

local authority_info_access_ptr_ct = ffi.typeof("AUTHORITY_INFO_ACCESS*")

local STACK = "ACCESS_DESCRIPTION"
local new = stack_lib.new_of(STACK)
local add = stack_lib.add_of(STACK)
local dup = stack_lib.dup_of(STACK)

local aia_decode = function(ctx)
  local nid = C.OBJ_obj2nid(ctx.method)
  local gn = altname_lib.gn_decode(ctx.location)
  return { nid, unpack(gn) }
end

local mt = stack_lib.mt_of(STACK, aia_decode, _M)
local mt__pairs = mt.__pairs
mt.__pairs = function(tbl)
  local f = mt__pairs(tbl)
  return function()
    local _, e = f()
    if not e then return end
    return unpack(e)
  end
end

function _M.new()
  local ctx = new()
  if ctx == nil then
    return nil, "OPENSSL_sk_new_null() failed"
  end
  local cast = ffi_cast("AUTHORITY_INFO_ACCESS*", ctx)

  local self = setmetatable({
    ctx = ctx,
    cast = cast,
    _is_shallow_copy = false,
  }, mt)

  return self, nil
end

function _M.istype(l)
  return l and l.cast and ffi.istype(authority_info_access_ptr_ct, l.cast)
end

function _M.dup(ctx)
  if ctx == nil or not ffi.istype(authority_info_access_ptr_ct, ctx) then
    return nil, "expect a AUTHORITY_INFO_ACCESS* ctx at #1"
  end
  local dup_ctx = dup(ctx)

  return setmetatable({
    ctx = dup_ctx,
    cast = ffi_cast("AUTHORITY_INFO_ACCESS*", dup_ctx),
    -- don't let lua gc the original stack to keep its elements
    _dupped_from = ctx,
    _is_shallow_copy = true,
    _elem_refs = {},
    _elem_refs_idx = 1,
  }, mt), nil
end

function _M:add(nid, typ, value)
  -- the stack element stays with stack
  -- we shouldn't add gc handler if it's already been
  -- pushed to stack. instead, rely on the gc handler
  -- of the stack to release all memories
  local ad = C.ACCESS_DESCRIPTION_new()
  if ad == nil then
    return nil, "ACCESS_DESCRIPTION_new() failed"
  end

  -- C.ASN1_OBJECT_free(ad.method)

  local asn1 = C.OBJ_txt2obj(nid, 0)
  if asn1 == nil then
    C.ACCESS_DESCRIPTION_free(ad)
    -- clean up error occurs during OBJ_txt2*
    C.ERR_clear_error()
    return nil, "invalid NID text " .. (nid or "nil")
  end

  ad.method = asn1

  local err = altname_lib.gn_set(ad.location, typ, value)
  if err then
    C.ACCESS_DESCRIPTION_free(ad)
    return nil, err
  end

  local _, err = add(self.ctx, ad)
  if err then
    C.ACCESS_DESCRIPTION_free(ad)
    return nil, err
  end

  -- if the stack is duplicated, the gc handler is not pop_free
  -- handle the gc by ourselves
  if self._is_shallow_copy then
    ffi_gc(ad, C.ACCESS_DESCRIPTION_free)
    self._elem_refs[self._elem_refs_idx] = ad
    self._elem_refs_idx = self._elem_refs_idx + 1
  end
  return self
end

_M.all = function(stack)
  local ret = {}
  local _next = mt.__ipairs(stack)
  while true do
    local i, e = _next()
    if i then
      ret[i] = e
    else
      break
    end
  end
  return ret
end

_M.each = mt.__ipairs
_M.index = mt.__index
_M.count = mt.__len

return _M
