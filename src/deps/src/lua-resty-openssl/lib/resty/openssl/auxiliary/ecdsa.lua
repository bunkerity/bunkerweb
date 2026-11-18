local ffi = require "ffi"
local ffi_new = ffi.new
local ffi_gc = ffi.gc
local ffi_str = ffi.string
local C = ffi.C

require "resty.openssl.include.ecdsa"
local bn_lib = require "resty.openssl.bn"
local format_error = require("resty.openssl.err").format_error
local ceil = math.ceil
local type = type

local _M = {}

--[[ A DER formatted ECDSA signature looks like
SEQUENCE {
  INTEGER
    4B 5F CF E8 A7 BD 6A C2 1D 25 0D F8 DE 9C EF DC
    C4 DF 33 F3 AF 2F 3D 5B 83 2C 1F BD 98 C8 61 34
  INTEGER
    7E F9 E9 60 B1 E6 7F 59 9E 2C 38 22 39 B2 C4 B1
    71 3E FA AE 24 A4 B7 D2 03 5A 60 8D F3 34 3D E8
  }

  It has ASN.1 headers on both the SEQUENCE and INTEGERs, so
  the total length is typically 70 bytes (3 headers, 2 bytes each).
  The binary form is typically 64 bytes.
]]

-- A DER ECDSA signature carries (r, s) without any width, so the raw form has
-- to be padded to the size of the curve. The caller passes the bit size of the
-- key, which both legacy and provider backed keys can report.
local function sig_size(bits)
  if type(bits) ~= "number" or bits <= 0 then
    return nil, "invalid EC group bits"
  end
  return ceil(bits / 8)
end

_M.sig_der2raw = function(der, bits)
  local psize, err = sig_size(bits)
  if not psize then
    return nil, err
  end

  local buf = ffi.new("const unsigned char*", der)
  local buf_ptr = ffi.new("const unsigned char*[1]", buf)
  local sig = C.d2i_ECDSA_SIG(nil, buf_ptr, #der)
  if sig == nil then
    return nil, format_error("failed to parse ECDSA signature: d2i_ECDSA_SIG")
  end

  ffi_gc(sig, C.ECDSA_SIG_free)

  local bn_r_ptr = ffi_new("const BIGNUM*[1]")
  local bn_s_ptr = ffi_new("const BIGNUM*[1]")

  C.ECDSA_SIG_get0(sig, bn_r_ptr, bn_s_ptr)

  if bn_r_ptr[0] == nil or bn_s_ptr[0] == nil then
    return nil, format_error("failed to get r or s from sig")
  end

  local bn_r = bn_lib.dup(bn_r_ptr[0])
  local bn_s = bn_lib.dup(bn_s_ptr[0])

  if bn_r == nil or bn_s == nil then
    return nil, format_error("failed to dup r or s")
  end

  local rbin, err = bn_r:to_binary(psize)
  if err then
    return nil, "failed to parse r to binary: " .. err
  end
  local sbin, err = bn_s:to_binary(psize)
  if err then
    return nil, "failed to parse s to binary: " .. err
  end

  return rbin .. sbin
end

_M.sig_raw2der = function(bin, bits)
  local psize, err = sig_size(bits)
  if not psize then
    return nil, err
  end

  if #bin ~= psize * 2 then
    return nil, "invalid signature length, expect " .. (psize * 2) .. " but got " .. #bin
  end

  local rbin = string.sub(bin, 1, psize)
  local sbin = string.sub(bin, psize + 1)

  local bn_r, err = bn_lib.from_binary(rbin)
  if err then
    return nil, "failed to parse r from binary: " .. err
  end
  local bn_s, err = bn_lib.from_binary(sbin)
  if err then
    return nil, "failed to parse s from binary: " .. err
  end

  local sig = C.ECDSA_SIG_new()
  if sig == nil then
    return nil, format_error("ECDSA_SIG_new")
  end

  ffi_gc(sig, C.ECDSA_SIG_free)

  local bn_r0 = C.BN_dup(bn_r.ctx)
  local bn_s0 = C.BN_dup(bn_s.ctx)
  if not bn_r0 or not bn_s0 then
    return nil, format_error("failed to BN_dup r or s")
  end

  local ok = C.ECDSA_SIG_set0(sig, bn_r0, bn_s0)
  if ok ~= 1 then
    return nil, format_error("failed to set r and s to sig")
  end

  local der_len = C.i2d_ECDSA_SIG(sig, nil)
  if der_len <= 0 then
    return nil, format_error("failed to get ECDSA signature size")
  end

  local buf = ffi_new("unsigned char[?]", der_len)
  local buf_ptr = ffi.new("unsigned char*[1]", buf)

  der_len = C.i2d_ECDSA_SIG(sig, buf_ptr)
  if der_len <= 0 then
    return nil, format_error("failed to encode ECDSA signature to DER")
  end

  return ffi_str(buf, der_len)
end

return _M
