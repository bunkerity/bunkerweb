local ffi = require "ffi"
local C = ffi.C
local ffi_gc = ffi.gc
local ffi_str = ffi.string

require "resty.openssl.include.x509.name"
require "resty.openssl.include.err"
local objects_lib = require "resty.openssl.objects"
local asn1_macro = require "resty.openssl.include.asn1"

-- local MBSTRING_FLAG = 0x1000
local MBSTRING_ASC  = 0x1001 -- (MBSTRING_FLAG|1)

local _M = {}

local x509_name_ptr_ct = ffi.typeof("X509_NAME*")

-- starts from 0
local function value_at(ctx, i)
  local entry = C.X509_NAME_get_entry(ctx, i)
  local obj = C.X509_NAME_ENTRY_get_object(entry)
  local ret = objects_lib.obj2table(obj)

  local str = C.X509_NAME_ENTRY_get_data(entry)
  if str ~= nil then
    ret.blob = ffi_str(asn1_macro.ASN1_STRING_get0_data(str))
  end

  return ret
end

local function iter(tbl)
  local i = 0
  local n = tonumber(C.X509_NAME_entry_count(tbl.ctx))
  return function()
    i = i + 1
    if i <= n then
      local obj = value_at(tbl.ctx, i-1)
      return obj.sn or obj.ln or obj.id, obj
    end
  end
end

local mt = {
  __index = _M,
  __pairs = iter,
  __len = function(tbl) return tonumber(C.X509_NAME_entry_count(tbl.ctx)) end,
}

function _M.new()
  local ctx = C.X509_NAME_new()
  if ctx == nil then
    return nil, "x509.name.new: X509_NAME_new() failed"
  end
  ffi_gc(ctx, C.X509_NAME_free)

  local self = setmetatable({
    ctx = ctx,
  }, mt)

  return self, nil
end

function _M.istype(l)
  return l and l.ctx and ffi.istype(x509_name_ptr_ct, l.ctx)
end

function _M.dup(ctx)
  if not ffi.istype(x509_name_ptr_ct, ctx) then
    return nil, "x509.name.dup: expect a x509.name ctx at #1, got " .. type(ctx)
  end
  local ctx = C.X509_NAME_dup(ctx)
  ffi_gc(ctx, C.X509_NAME_free)

  local self = setmetatable({
    ctx = ctx,
  }, mt)

  return self, nil
end

function _M:add(nid, txt)
  local asn1 = C.OBJ_txt2obj(nid, 0)
  if asn1 == nil then
    -- clean up error occurs during OBJ_txt2*
    C.ERR_clear_error()
    return nil, "x509.name:add: invalid NID text " .. (nid or "nil")
  end

  local code = C.X509_NAME_add_entry_by_OBJ(self.ctx, asn1, MBSTRING_ASC, txt, #txt, -1, 0)
  C.ASN1_OBJECT_free(asn1)

  if code ~= 1 then
    return nil, "x509.name:add: X509_NAME_add_entry_by_OBJ() failed"
  end

  return self
end

function _M:find(nid, last_pos)
  local asn1 = C.OBJ_txt2obj(nid, 0)
  if asn1 == nil then
    -- clean up error occurs during OBJ_txt2*
    C.ERR_clear_error()
    return nil, nil, "x509.name:find: invalid NID text " .. (nid or "nil")
  end
  -- make 1-index array to 0-index
  last_pos = (last_pos or 0) - 1

  local pos = C.X509_NAME_get_index_by_OBJ(self.ctx, asn1, last_pos)
  if pos == -1 then
    return nil
  end

  C.ASN1_OBJECT_free(asn1)

  return value_at(self.ctx, pos), pos+1
end

-- fallback function to iterate if LUAJIT_ENABLE_LUA52COMPAT not enabled
function _M:all()
  local ret = {}
  local _next = iter(self)
  while true do
    local k, obj = _next()
    if obj then
      ret[k] = obj
    else
      break
    end
  end
  return ret
end

function _M:each()
  return iter(self)
end

mt.__tostring = function(self)
  local values = {}
  local _next = iter(self)
  while true do
    local k, v = _next()
    if k then
      table.insert(values, k .. "=" .. v.blob)
    else
      break
    end
  end
  table.sort(values)
  return table.concat(values, "/")
end

_M.tostring = mt.__tostring

return _M
