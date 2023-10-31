
--[[
  The OpenSSL stack library. Note `safestack` is not usable here in ffi because
  those symbols are eaten after preprocessing.
  Instead, we should do a Lua land type checking by having a nested field indicating
  which type of cdata its ctx holds.
]]
local ffi = require "ffi"
local C = ffi.C
local ffi_cast = ffi.cast
local ffi_gc = ffi.gc

local stack_macro = require "resty.openssl.include.stack"
local format_error = require("resty.openssl.err").format_error

local _M = {}

local function gc_of(typ)
  local f = C[typ .. "_free"]
  return function (st)
    stack_macro.OPENSSL_sk_pop_free(st, f)
  end
end

_M.gc_of = gc_of

_M.mt_of = function(typ, convert, index_tbl, no_gc)
  if type(typ) ~= "string" then
    error("expect a string at #1")
  elseif type(convert) ~= "function" then
    error("expect a function at #2")
  end

  local typ_ptr = typ .. "*"

  -- starts from 0
  local function value_at(ctx, i)
    local elem = stack_macro.OPENSSL_sk_value(ctx, i)
    if elem == nil then
      error(format_error("OPENSSL_sk_value"))
    end
    local dup, err = convert(ffi_cast(typ_ptr, elem))
    if err then
      error(err)
    end
    return dup
  end

  local function iter(tbl)
    if not tbl then error("instance is nil") end
    local i = 0
    local n = tonumber(stack_macro.OPENSSL_sk_num(tbl.ctx))
    return function()
      i = i + 1
      if i <= n then
        return i, value_at(tbl.ctx, i-1)
      end
    end
  end

  local ret = {
    __pairs = iter,
    __ipairs = iter,
    __len = function(tbl)
      if not tbl then error("instance is nil") end
      return tonumber(stack_macro.OPENSSL_sk_num(tbl.ctx))
    end,
    __index = function(tbl, k)
      if not tbl then error("instance is nil") end
      local i = tonumber(k)
      if not i then
        return index_tbl[k]
      end
      local n = stack_macro.OPENSSL_sk_num(tbl.ctx)
      if i <= 0 or i > n then
        return nil
      end
      return value_at(tbl.ctx, i-1)
    end,
  }

  if not no_gc then
    ret.__gc = gc_of(typ)
  end
  return ret
end

_M.new_of = function(typ)
  local gc = gc_of(typ)
  return function()
    local raw = stack_macro.OPENSSL_sk_new_null()
    if raw == nil then
      return nil, "stack.new_of: OPENSSL_sk_new_null() failed"
    end
    ffi_gc(raw, gc)
    return raw
  end
end

_M.add_of = function(typ)
  local ptr = ffi.typeof(typ .. "*")
  return function(stack, ctx)
    if not stack then error("instance is nil") end
    if ctx == nil or not ffi.istype(ptr, ctx) then
      return false, "stack.add_of: expect a " .. typ .. "* at #1"
    end
    local code = stack_macro.OPENSSL_sk_push(stack, ctx)
    if code == 0 then
      return false, "stack.add_of: OPENSSL_sk_push() failed"
    end
    return true
  end
end

local stack_ptr_ct = ffi.typeof("OPENSSL_STACK*")
_M.dup_of = function(_)
  return function(ctx)
    if ctx == nil or not ffi.istype(stack_ptr_ct, ctx) then
      return nil, "stack.dup_of: expect a stack ctx at #1"
    end
    local ctx = stack_macro.OPENSSL_sk_dup(ctx)
    if ctx == nil then
      return nil, "stack.dup_of: OPENSSL_sk_dup() failed"
    end
    -- if the stack is duplicated: since we don't copy the elements
    -- then we only control gc of the stack itself here
    ffi_gc(ctx, stack_macro.OPENSSL_sk_free)
    return ctx
  end
end

-- fallback function to iterate if LUAJIT_ENABLE_LUA52COMPAT not enabled
_M.all_func = function(mt)
  return function(stack)
    if not stack then error("stack is nil") end
    local ret = {}
    local _next = mt.__pairs(stack)
    while true do
      local i, elem = _next()
      if elem then
        ret[i] = elem
      else
        break
      end
    end
    return ret
  end
end

_M.deep_copy_of = function(typ)
  local dup = C[typ .. "_dup"]
  local free = C[typ .. "_free"]

  return function(ctx)
    return stack_macro.OPENSSL_sk_deep_copy(ctx, dup, free)
  end
end

return _M