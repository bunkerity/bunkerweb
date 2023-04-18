local ffi = require "ffi"
local C = ffi.C
local ffi_gc = ffi.gc
local ffi_cast = ffi.cast
local ffi_str = ffi.string

require "resty.openssl.include.x509"
require "resty.openssl.include.x509v3"
local asn1_macro = require "resty.openssl.include.asn1"
local stack_lib = require "resty.openssl.stack"
local name_lib = require "resty.openssl.x509.name"
local altname_macro = require "resty.openssl.include.x509.altname"

local _M = {}

local general_names_ptr_ct = ffi.typeof("GENERAL_NAMES*")

local STACK = "GENERAL_NAME"
local new = stack_lib.new_of(STACK)
local add = stack_lib.add_of(STACK)
local dup = stack_lib.dup_of(STACK)

local types = altname_macro.types

local AF_INET = 2
local AF_INET6 = 10
if ffi.os == "OSX" then
  AF_INET6 = 30
elseif ffi.os == "BSD" then
  AF_INET6 = 28
elseif ffi.os == "Windows" then
  AF_INET6 = 23
end

ffi.cdef [[
  typedef int socklen_t;
  int inet_pton(int af, const char *restrict src, void *restrict dst);
  const char *inet_ntop(int af, const void *restrict src,
                             char *restrict dst, socklen_t size);
]]

local ip_buffer = ffi.new("unsigned char [46]") -- 46 bytes enough for both string ipv6 and binary ipv6

-- similar to GENERAL_NAME_print, but returns value instead of print
local gn_decode = function(ctx)
  local typ = ctx.type
  local k = altname_macro.literals[typ]
  local v
  if typ == types.OtherName then
    v = "OtherName:<unsupported>"
  elseif typ == types.RFC822Name then
    v = ffi_str(asn1_macro.ASN1_STRING_get0_data(ctx.d.rfc822Name))
  elseif typ == types.DNS then
    v = ffi_str(asn1_macro.ASN1_STRING_get0_data(ctx.d.dNSName))
  elseif typ == types.X400 then
    v = "X400:<unsupported>"
  elseif typ == types.DirName then
    v = name_lib.dup(ctx.d.directoryName)
  elseif typ == types.EdiParty then
    v = "EdiParty:<unsupported>"
  elseif typ == types.URI then
    v = ffi_str(asn1_macro.ASN1_STRING_get0_data(ctx.d.uniformResourceIdentifier))
  elseif typ == types.IP then
    v = asn1_macro.ASN1_STRING_get0_data(ctx.d.iPAddress)
    local l = tonumber(C.ASN1_STRING_length(ctx.d.iPAddress))
    if l ~= 4 and l ~= 16 then
      error("Unknown IP address type")
    end
    v = C.inet_ntop(l == 4 and AF_INET or AF_INET6, v, ip_buffer, 46)
    v = ffi_str(v)
  elseif typ == types.RID then
    v = "RID:<unsupported>"
  else
    error("unknown type" .. typ .. "-> " .. types.OtherName)
  end
  return { k, v }
end

-- shared with info_access
_M.gn_decode = gn_decode

local mt = stack_lib.mt_of(STACK, gn_decode, _M)
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
    return nil, "x509.altname.new: OPENSSL_sk_new_null() failed"
  end
  local cast = ffi_cast("GENERAL_NAMES*", ctx)

  local self = setmetatable({
    ctx = ctx,
    cast = cast,
    _is_shallow_copy = false,
  }, mt)

  return self, nil
end

function _M.istype(l)
  return l and l.cast and ffi.istype(general_names_ptr_ct, l.cast)
end

function _M.dup(ctx)
  if ctx == nil or not ffi.istype(general_names_ptr_ct, ctx) then
    return nil, "x509.altname.dup: expect a GENERAL_NAMES* ctx at #1"
  end

  local dup_ctx = dup(ctx)

  return setmetatable({
    cast = ffi_cast("GENERAL_NAMES*", dup_ctx),
    ctx = dup_ctx,
    -- don't let lua gc the original stack to keep its elements
    _dupped_from = ctx,
    _is_shallow_copy = true,
    _elem_refs = {},
    _elem_refs_idx = 1,
  }, mt), nil
end

local function gn_set(gn, typ, value)
  if type(typ) ~= 'string' then
    return "x509.altname:gn_set: expect a string at #1"
  end
  local typ_lower = typ:lower()
  if type(value) ~= 'string' then
    return "x509.altname:gn_set: except a string at #2"
  end

  local txt = value
  local gn_type = types[typ_lower]

  if not gn_type then
    return "x509.altname:gn_set: unknown type " .. typ
  end

  if gn_type == types.IP then
    if C.inet_pton(AF_INET, txt, ip_buffer) == 1 then
      txt = ffi_str(ip_buffer, 4)
    elseif C.inet_pton(AF_INET6, txt, ip_buffer) == 1 then
      txt = ffi_str(ip_buffer, 16)
    else
      return "x509.altname:gn_set: invalid IP address " .. txt
    end

  elseif gn_type ~= types.Email and
      gn_type ~= types.URI and
      gn_type ~= types.DNS then
    return "x509.altname:gn_set: setting type " .. typ .. " is currently not supported"
  end

  gn.type = gn_type

  local asn1_string = C.ASN1_IA5STRING_new()
  if asn1_string == nil then
    return "x509.altname:gn_set: ASN1_STRING_type_new() failed"
  end

  local code = C.ASN1_STRING_set(asn1_string, txt, #txt)
  if code ~= 1 then
    C.ASN1_STRING_free(asn1_string)
    return "x509.altname:gn_set: ASN1_STRING_set() failed: " .. code
  end
  gn.d.ia5 = asn1_string
end

-- shared with info_access
_M.gn_set = gn_set

function _M:add(typ, value)

  -- the stack element stays with stack
  -- we shouldn't add gc handler if it's already been
  -- pushed to stack. instead, rely on the gc handler
  -- of the stack to release all memories
  local gn = C.GENERAL_NAME_new()
  if gn == nil then
    return nil, "x509.altname:add: GENERAL_NAME_new() failed"
  end

  local err = gn_set(gn, typ, value)
  if err then
    C.GENERAL_NAME_free(gn)
    return nil, err
  end

  local _, err = add(self.ctx, gn)
  if err then
    C.GENERAL_NAME_free(gn)
    return nil, err
  end

  -- if the stack is duplicated, the gc handler is not pop_free
  -- handle the gc by ourselves
  if self._is_shallow_copy then
    ffi_gc(gn, C.GENERAL_NAME_free)
    self._elem_refs[self._elem_refs_idx] = gn
    self._elem_refs_idx = self._elem_refs_idx + 1
  end
  return self
end

_M.all = function(self)
  local ret = {}
  local _next = mt.__pairs(self)
  while true do
    local k, v = _next()
    if k then
      ret[k] = v
    else
      break
    end
  end
  return ret
end

_M.each = mt.__pairs
_M.index = mt.__index
_M.count = mt.__len

mt.__tostring = function(self)
  local values = {}
  local _next = mt.__pairs(self)
  while true do
    local k, v = _next()
    if k then
      table.insert(values, k .. "=" .. v)
    else
      break
    end
  end
  table.sort(values)
  return table.concat(values, "/")
end

_M.tostring = mt.__tostring

return _M
