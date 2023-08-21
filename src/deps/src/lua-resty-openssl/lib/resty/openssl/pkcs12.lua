local ffi = require "ffi"
local C = ffi.C
local ffi_gc = ffi.gc
local ffi_str = ffi.string

require "resty.openssl.include.pkcs12"
require "resty.openssl.include.bio"
local bio_util = require "resty.openssl.auxiliary.bio"
local format_error = require("resty.openssl.err").format_error
local pkey_lib = require "resty.openssl.pkey"
local x509_lib = require "resty.openssl.x509"
local stack_macro = require "resty.openssl.include.stack"
local stack_lib = require "resty.openssl.stack"
local objects_lib = require "resty.openssl.objects"
local ctx_lib = require "resty.openssl.ctx"
local OPENSSL_10 = require("resty.openssl.version").OPENSSL_10
local OPENSSL_3X = require("resty.openssl.version").OPENSSL_3X

local stack_of_x509_new = stack_lib.new_of("X509")
local stack_of_x509_add = stack_lib.add_of("X509")
local stack_of_x509_iter = stack_lib.mt_of("X509", x509_lib.dup, {}).__ipairs

local ptr_ptr_of_pkey = ffi.typeof("EVP_PKEY*[1]")
local ptr_ptr_of_x509 = ffi.typeof("X509*[1]")
local ptr_ptr_of_stack = ffi.typeof("OPENSSL_STACK*[1]")

local function decode(p12, passphrase)
  local bio = C.BIO_new_mem_buf(p12, #p12)
  if bio == nil then
    return nil, "pkcs12.decode: BIO_new_mem_buf() failed"
  end
  ffi_gc(bio, C.BIO_free)

  local p12 = C.d2i_PKCS12_bio(bio, nil)
  if p12 == nil then
    return nil, format_error("pkcs12.decode: d2i_PKCS12_bio")
  end
  ffi_gc(p12, C.PKCS12_free)

  local ppkey = ptr_ptr_of_pkey()
  local px509 = ptr_ptr_of_x509()
  local pstack = ptr_ptr_of_stack()
  local stack = stack_of_x509_new()
  if stack == nil then
    return nil, "pkcs12.decode: OPENSSL_sk_new_null() failed"
  end

  -- assign a valid OPENSSL_STACK so gc is taken care of
  pstack[0] = stack

  local code = C.PKCS12_parse(p12, passphrase or "", ppkey, px509, pstack)
  if code ~= 1 then
    return nil, format_error("pkcs12.decode: PKCS12_parse")
  end

  local cacerts
  local n = stack_macro.OPENSSL_sk_num(stack)
  if n > 0 then
    cacerts = {}
    local iter = stack_of_x509_iter({ ctx = stack })
    for i=1, n do
      local _, c = iter()
      cacerts[i] = c
    end
  end

  local friendly_name = C.X509_alias_get0(px509[0], nil)
  if friendly_name ~= nil then
    friendly_name = ffi_str(friendly_name)
  end

  return {
    key = pkey_lib.new(ppkey[0]),
    cert = x509_lib.new(px509[0]),
    friendly_name = friendly_name,
    cacerts = cacerts,
    -- store reference to the stack, so it's not GC'ed unexpectedly
    _stack = stack,
  }
end

local function encode(opts, passphrase, properties)
  if passphrase and type(passphrase) ~= "string" then
    return nil, "pkcs12.encode: expect passphrase to be a string"
  end
  local pkey = opts.key
  if not pkey_lib.istype(pkey) then
    return nil, "pkcs12.encode: expect key to be a pkey instance"
  end
  local cert = opts.cert
  if not x509_lib.istype(cert) then
    return nil, "pkcs12.encode: expect cert to be a x509 instance"
  end

  local ok, err = cert:check_private_key(pkey)
  if not ok then
    return nil, "pkcs12.encode: key doesn't match cert: " .. err
  end

  local nid_key = opts.nid_key
  if nid_key then
    nid_key, err = objects_lib.txtnid2nid(nid_key)
    if err then
      return nil, "pkcs12.encode: invalid nid_key"
    end
  end

  local nid_cert = opts.nid_cert
  if nid_cert then
    nid_cert, err = objects_lib.txtnid2nid(nid_cert)
    if err then
      return nil, "pkcs12.encode: invalid nid_cert"
    end
  end

  local x509stack
  local cacerts = opts.cacerts
  if cacerts then
    if type(cacerts) ~= "table" then
      return nil, "pkcs12.encode: expect cacerts to be a table"
    end
    if #cacerts > 0 then
      -- stack lib handles gc
      x509stack = stack_of_x509_new()
      for _, c in ipairs(cacerts) do
        if not OPENSSL_10 then
          if C.X509_up_ref(c.ctx) ~= 1 then
            return nil, "pkcs12.encode: failed to add cacerts: X509_up_ref failed"
          end
        end
        local ok, err = stack_of_x509_add(x509stack, c.ctx)
        if not ok then
          return nil, "pkcs12.encode: failed to add cacerts: " .. err
        end
      end
      if OPENSSL_10 then
        -- OpenSSL 1.0.2 doesn't have X509_up_ref
        -- shallow copy the stack, up_ref for each element
        x509stack = C.X509_chain_up_ref(x509stack)
        -- use the shallow gc
        ffi_gc(x509stack, stack_macro.OPENSSL_sk_free)
      end
    end
  end

  local p12
  if OPENSSL_3X then
    p12 = C.PKCS12_create_ex(passphrase or "", opts.friendly_name,
                              pkey.ctx, cert.ctx, x509stack,
                              nid_key or 0, nid_cert or 0,
                              opts.iter or 0, opts.mac_iter or 0, 0,
                              ctx_lib.get_libctx(), properties)
  else
    p12 = C.PKCS12_create(passphrase or "", opts.friendly_name,
                            pkey.ctx, cert.ctx, x509stack,
                            nid_key or 0, nid_cert or 0,
                            opts.iter or 0, opts.mac_iter or 0, 0)
  end
  if p12 == nil then
    return nil, format_error("pkcs12.encode: PKCS12_create")
  end
  ffi_gc(p12, C.PKCS12_free)

  return bio_util.read_wrap(C.i2d_PKCS12_bio, p12)
end

return {
  decode = decode,
  loads = decode,
  encode = encode,
  dumps = encode,
}
