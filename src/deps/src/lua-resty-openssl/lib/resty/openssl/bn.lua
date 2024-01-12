local ffi = require "ffi"
local C = ffi.C
local ffi_gc = ffi.gc
local ffi_new = ffi.new
local ffi_str = ffi.string
local floor = math.floor

require "resty.openssl.include.bn"
local crypto_macro = require("resty.openssl.include.crypto")
local ctypes = require "resty.openssl.auxiliary.ctypes"
local format_error = require("resty.openssl.err").format_error

local _M = {}
local mt = {__index = _M}

local bn_ptr_ct = ffi.typeof('BIGNUM*')
local bn_ptrptr_ct = ffi.typeof('BIGNUM*[1]')

local function set_binary(ctx, s)
  local ctx = C.BN_bin2bn(s, #s, ctx)
  if ctx == nil then
    return nil, format_error("set_binary")
  end
  return ctx
end

local function set_mpi(ctx, s)
  local ctx = C.BN_mpi2bn(s, #s, ctx)
  if ctx == nil then
    return nil, format_error("set_mpi")
  end
  return ctx
end

local function set_hex(ctx, s)
  local p = ffi_new(bn_ptrptr_ct)
  p[0] = ctx

  if C.BN_hex2bn(p, s) == 0 then
    return nil, format_error("set_hex")
  end
  return p[0]
end

local function set_dec(ctx, s)
  local p = ffi_new(bn_ptrptr_ct)
  p[0] = ctx

  if C.BN_dec2bn(p, s) == 0 then
    return nil, format_error("set_dec")
  end
  return p[0]
end

local function set_bn(ctx, s, base)
  if type(s) == 'number' then
    if C.BN_set_word(ctx, s) ~= 1 then
      return nil, format_error("set_bn")
    end
  elseif type(s) == 'string' then
    if not base or base == 10 then
      return set_dec(ctx, s)
    elseif base == 16 then
      return set_hex(ctx, s)
    elseif base == 2 then
      return set_binary(ctx, s)
    elseif base == 0 then
      ctx = set_mpi(ctx, s)
    else
      return nil, "set_bn: unsupported base: " .. base
    end
  elseif s then
    return nil, "set_bn: expect nil, a number or a string at #1"
  end

  return ctx
end

function _M.new(some, base)
  local ctx = C.BN_new()
  ffi_gc(ctx, C.BN_free)

  local ctx, err = set_bn(ctx, some, base)
  if err then
    return nil, "bn.new: " .. err
  end

  return setmetatable( { ctx = ctx }, mt), nil
end

function _M.istype(l)
  return l and l.ctx and ffi.istype(bn_ptr_ct, l.ctx)
end

function _M.dup(ctx)
  if not ffi.istype(bn_ptr_ct, ctx) then
    return nil, "bn.dup: expect a bn ctx at #1"
  end
  local ctx = C.BN_dup(ctx)
  ffi_gc(ctx, C.BN_free)

  local self = setmetatable({
    ctx = ctx,
  }, mt)

  return self
end

function _M:set(some, base)
  if not some then
    return nil, "expect a number or a string at #1"
  end

  local _, err = set_bn(self.ctx, some, base)
  if err then
    return nil, "bn:set: " .. err
  end

  return self
end

function _M:to_binary(pad)
  if pad then
    if type(pad) ~= "number" then
      return nil, "bn:to_binary: expect a number at #1"
    end
  end

  local length
  if not pad then
    length = (C.BN_num_bits(self.ctx)+7)/8
    -- align to bytes
    length = floor(length)
  else
    length = pad
  end

  local buf = ctypes.uchar_array(length)
  local sz
  if not pad then
    sz = C.BN_bn2bin(self.ctx, buf)
  else
    sz = C.BN_bn2binpad(self.ctx, buf, pad)
  end

  if sz <= 0 then
    return nil, format_error("bn:to_binary")
  end
  return ffi_str(buf, sz)
end

function _M:to_mpi(no_header)
  local length = C.BN_bn2mpi(self.ctx, nil)
  if length <= 0 then
    return nil, format_error("bn:to_mpi")
  end

  local buf = ctypes.uchar_array(length)

  local sz = C.BN_bn2mpi(self.ctx, buf)
  if sz <= 0 then
    return nil, format_error("bn:to_mpi")
  end

  local ret = ffi_str(buf, sz)

  return no_header and ret:sub(4) or ret
end

function _M:to_hex()
  local buf = C.BN_bn2hex(self.ctx)
  if buf == nil then
    return nil, format_error("bn:to_hex")
  end
  ffi_gc(buf, crypto_macro.OPENSSL_free)
  local s = ffi_str(buf)
  return s
end

function _M:to_dec()
  local buf = C.BN_bn2dec(self.ctx)
  if buf == nil then
    return nil, format_error("bn:to_dec")
  end
  ffi_gc(buf, crypto_macro.OPENSSL_free)
  local s = ffi_str(buf)
  return s
end
mt.__tostring = _M.to_dec

function _M:to_number()
  return tonumber(C.BN_get_word(self.ctx))
end
_M.tonumber = _M.to_number

local from_funcs = {
  binary = set_binary,
  mpi = set_mpi,
  hex = set_hex,
  dec = set_dec,
}

for typ, func in pairs(from_funcs) do
  local sig = "from_" .. typ
  _M[sig] = function(s)
    if type(s) ~= "string" then
      return nil, "bn." .. sig .. ": expect a string at #1"
    end

    local ctx, err = func(nil, s)
    if not ctx then
      return nil, "bn." .. sig .. ": " .. err
    end

    ffi_gc(ctx, C.BN_free)
    return setmetatable( { ctx = ctx }, mt), nil
  end
end

function _M.generate_prime(bits, safe)
  local ctx = C.BN_new()
  ffi_gc(ctx, C.BN_free)

  if C.BN_generate_prime_ex(ctx, bits, safe and 1 or 0, nil, nil, nil) == 0 then
    return nil, format_error("bn.BN_generate_prime_ex")
  end

  return setmetatable( { ctx = ctx }, mt), nil
end

-- BN_CTX is used to store temporary variable
-- we only need one per worker
local bn_ctx_tmp = C.BN_CTX_new()
assert(bn_ctx_tmp ~= nil)
ffi_gc(bn_ctx_tmp, C.BN_CTX_free)

_M.bn_ctx_tmp = bn_ctx_tmp

-- mathematics

function mt.__unm(a)
  local b = _M.dup(a.ctx)
  if b == nil then
    error("BN_dup() failed")
  end
  local sign = C.BN_is_negative(b.ctx)
  C.BN_set_negative(b.ctx, 1-sign)
  return b
end

local function check_args(op, ...)
  local args = {...}
  for i, arg in ipairs(args) do
    if type(arg) == 'number' then
      local b = C.BN_new()
      if b == nil then
        error("BN_new() failed")
      end
      ffi_gc(b, C.BN_free)
      if C.BN_set_word(b, arg) ~= 1 then
        error("BN_set_word() failed")
      end
      args[i] = b
    elseif _M.istype(arg) then
      args[i] = arg.ctx
    else
      error("cannot " .. op .. " a " .. type(arg) .. " to bignum")
    end
  end
  local ctx = C.BN_new()
  if ctx == nil then
    error("BN_new() failed")
  end
  ffi_gc(ctx, C.BN_free)
  local r = setmetatable( { ctx = ctx }, mt)
  return r, unpack(args)
end


function mt.__add(...)
  local r, a, b = check_args("add", ...)
  if C.BN_add(r.ctx, a, b) == 0 then
    error("BN_add() failed")
  end
  return r
end
_M.add = mt.__add

function mt.__sub(...)
  local r, a, b = check_args("substract", ...)
  if C.BN_sub(r.ctx, a, b) == 0 then
    error("BN_sub() failed")
  end
  return r
end
_M.sub = mt.__sub

function mt.__mul(...)
  local r, a, b = check_args("multiply", ...)
  if C.BN_mul(r.ctx, a, b, bn_ctx_tmp) == 0 then
    error("BN_mul() failed")
  end
  return r
end
_M.mul = mt.__mul

-- lua 5.3 only
function mt.__idiv(...)
  local r, a, b = check_args("divide", ...)
  if C.BN_div(r.ctx, nil, a, b, bn_ctx_tmp) == 0 then
    error("BN_div() failed")
  end
  return r
end

mt.__div = mt.__idiv
_M.idiv = mt.__idiv
_M.div = mt.__div

function mt.__mod(...)
  local r, a, b = check_args("mod", ...)
  if C.BN_div(nil, r.ctx, a, b, bn_ctx_tmp) == 0 then
    error("BN_div() failed")
  end
  return r
end
_M.mod = mt.__mod

-- __concat doesn't make sense at all?

function _M.sqr(...)
  local r, a = check_args("square", ...)
  if C.BN_sqr(r.ctx, a, bn_ctx_tmp) == 0 then
    error("BN_sqr() failed")
  end
  return r
end

function _M.gcd(...)
  local r, a, b = check_args("extract greatest common divisor", ...)
  if C.BN_gcd(r.ctx, a, b, bn_ctx_tmp) == 0 then
    error("BN_gcd() failed")
  end
  return r
end

function _M.exp(...)
  local r, a, b = check_args("power", ...)
  if C.BN_exp(r.ctx, a, b, bn_ctx_tmp) == 0 then
    error("BN_exp() failed")
  end
  return r
end
_M.pow = _M.exp

for _, op in ipairs({ "add", "sub" , "mul", "exp" }) do
  local f = "BN_mod_" .. op
  local cf = C[f]
  _M["mod_" .. op] = function(...)
    local r, a, b, m = check_args(op, ...)
    if cf(r.ctx, a, b, m, bn_ctx_tmp) == 0 then
      error(f .. " failed")
    end
    return r
  end
end

function _M.mod_sqr(...)
  local r, a, m = check_args("mod_sub", ...)
  if C.BN_mod_sqr(r.ctx, a, m, bn_ctx_tmp) == 0 then
    error("BN_mod_sqr() failed")
  end
  return r
end

local function nyi()
  error("NYI")
end

-- bit operations, lua 5.3

mt.__band = nyi
mt.__bor = nyi
mt.__bxor = nyi
mt.__bnot = nyi

function mt.__shl(a, b)
  local r, a = check_args("lshift", a)
  if C.BN_lshift(r.ctx, a, b) == 0 then
    error("BN_lshift() failed")
  end
  return r
end
_M.lshift = mt.__shl

function mt.__shr(a, b)
  local r, a = check_args("rshift", a)
  if C.BN_rshift(r.ctx, a, b) == 0 then
    error("BN_lshift() failed")
  end
  return r
end
_M.rshift = mt.__shr

-- comparaions
-- those functions are only called when the table
-- has exact same metamethods, i.e. they are all BN
-- so we don't need to check args

function mt.__eq(a, b)
  return C.BN_cmp(a.ctx, b.ctx) == 0
end

function mt.__lt(a, b)
  return C.BN_cmp(a.ctx, b.ctx) < 0
end

function mt.__le(a, b)
  return C.BN_cmp(a.ctx, b.ctx) <= 0
end

function _M:is_zero()
  return C.BN_is_zero(self.ctx) == 1
end

function _M:is_one()
  return C.BN_is_one(self.ctx) == 1
end

function _M:is_word(n)
  return C.BN_is_word(self.ctx, n) == 1
end

function _M:is_odd()
  return C.BN_is_odd(self.ctx) == 1
end

function _M:is_prime(nchecks)
  if nchecks and type(nchecks) ~= "number" then
    return nil, "bn:is_prime: expect a number at #1"
  end
  -- if nchecks is not defined, set to BN_prime_checks:
  -- select number of iterations based on the size of the number
  local code = C.BN_is_prime_ex(self.ctx, nchecks or 0, bn_ctx_tmp, nil)
  if code == -1 then
    return nil, format_error("bn.is_prime")
  end
  return code == 1
end

return _M
