local ffi = require "ffi"
local C = ffi.C
local ffi_gc = ffi.gc

local stack_lib = require "resty.openssl.stack"
local x509_lib = require "resty.openssl.x509"
local format_error = require("resty.openssl.err").format_error

local _M = {}

local stack_ptr_ct = ffi.typeof("OPENSSL_STACK*")

local STACK = "X509"
local gc = stack_lib.gc_of(STACK)
local new = stack_lib.new_of(STACK)
local add = stack_lib.add_of(STACK)
local mt = stack_lib.mt_of(STACK, x509_lib.dup, _M)

function _M.new()
  local raw, err = new()
  if raw == nil then
    return nil, err
  end

  local self = setmetatable({
    stack_of = STACK,
    ctx = raw,
  }, mt)

  return self, nil
end

function _M.istype(l)
  return l and l.ctx and ffi.istype(stack_ptr_ct, l.ctx)
            and l.stack_of and l.stack_of == STACK
end

function _M.dup(ctx)
  if ctx == nil or not ffi.istype(stack_ptr_ct, ctx) then
    return nil, "x509.chain.dup: expect a stack ctx at #1, got " .. type(ctx)
  end
  -- sk_X509_dup plus up ref for each X509 element
  local ctx = C.X509_chain_up_ref(ctx)
  if ctx == nil then
    return nil, "x509.chain.dup: X509_chain_up_ref() failed"
  end
  ffi_gc(ctx, gc)

  return setmetatable({
    stack_of = STACK,
    ctx = ctx,
  }, mt)
end

function _M:add(x509)
  if not x509_lib.istype(x509) then
    return nil, "x509.chain:add: expect a x509 instance at #1"
  end

  local dup = C.X509_dup(x509.ctx)
  if dup == nil then
    return nil, format_error("x509.chain:add: X509_dup")
  end

  local _, err = add(self.ctx, dup)
  if err then
    C.X509_free(dup)
    return nil, err
  end

  return true
end

_M.all = stack_lib.all_func(mt)
_M.each = mt.__ipairs
_M.index = mt.__index
_M.count = mt.__len

return _M
