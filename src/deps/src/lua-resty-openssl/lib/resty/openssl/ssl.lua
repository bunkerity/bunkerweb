local ffi = require "ffi"
local C = ffi.C
local ffi_str = ffi.string
local ffi_cast = ffi.cast

require "resty.openssl.include.ssl"

local nginx_aux = require("resty.openssl.auxiliary.nginx")
local x509_lib = require("resty.openssl.x509")
local chain_lib = require("resty.openssl.x509.chain")
local stack_lib = require("resty.openssl.stack")
local OPENSSL_3X = require("resty.openssl.version").OPENSSL_3X
local OPENSSL_10 = require("resty.openssl.version").OPENSSL_10
local format_error = require("resty.openssl.err").format_error

local _M = {
  SSL_VERIFY_NONE                 = 0x00,
  SSL_VERIFY_PEER                 = 0x01,
  SSL_VERIFY_FAIL_IF_NO_PEER_CERT = 0x02,
  SSL_VERIFY_CLIENT_ONCE          = 0x04,
  SSL_VERIFY_POST_HANDSHAKE       = 0x08,
}

local ops = {
  SSL_OP_NO_EXTENDED_MASTER_SECRET                = 0x00000001,
  SSL_OP_CLEANSE_PLAINTEXT                        = 0x00000002,
  SSL_OP_LEGACY_SERVER_CONNECT                    = 0x00000004,
  SSL_OP_TLSEXT_PADDING                           = 0x00000010,
  SSL_OP_SAFARI_ECDHE_ECDSA_BUG                   = 0x00000040,
  SSL_OP_IGNORE_UNEXPECTED_EOF                    = 0x00000080,
  SSL_OP_DISABLE_TLSEXT_CA_NAMES                  = 0x00000200,
  SSL_OP_ALLOW_NO_DHE_KEX                         = 0x00000400,
  SSL_OP_DONT_INSERT_EMPTY_FRAGMENTS              = 0x00000800,
  SSL_OP_NO_QUERY_MTU                             = 0x00001000,
  SSL_OP_COOKIE_EXCHANGE                          = 0x00002000,
  SSL_OP_NO_TICKET                                = 0x00004000,
  SSL_OP_CISCO_ANYCONNECT                         = 0x00008000,
  SSL_OP_NO_SESSION_RESUMPTION_ON_RENEGOTIATION   = 0x00010000,
  SSL_OP_NO_COMPRESSION                           = 0x00020000,
  SSL_OP_ALLOW_UNSAFE_LEGACY_RENEGOTIATION        = 0x00040000,
  SSL_OP_NO_ENCRYPT_THEN_MAC                      = 0x00080000,
  SSL_OP_ENABLE_MIDDLEBOX_COMPAT                  = 0x00100000,
  SSL_OP_PRIORITIZE_CHACHA                        = 0x00200000,
  SSL_OP_CIPHER_SERVER_PREFERENCE                 = 0x00400000,
  SSL_OP_TLS_ROLLBACK_BUG                         = 0x00800000,
  SSL_OP_NO_ANTI_REPLAY                           = 0x01000000,
  SSL_OP_NO_SSLv3                                 = 0x02000000,
  SSL_OP_NO_TLSv1                                 = 0x04000000,
  SSL_OP_NO_TLSv1_2                               = 0x08000000,
  SSL_OP_NO_TLSv1_1                               = 0x10000000,
  SSL_OP_NO_TLSv1_3                               = 0x20000000,
  SSL_OP_NO_DTLSv1                                = 0x04000000,
  SSL_OP_NO_DTLSv1_2                              = 0x08000000,
  SSL_OP_NO_RENEGOTIATION                         = 0x40000000,
  SSL_OP_CRYPTOPRO_TLSEXT_BUG                     = 0x80000000,
}
ops.SSL_OP_NO_SSL_MASK = ops.SSL_OP_NO_SSLv3 + ops.SSL_OP_NO_TLSv1 + ops.SSL_OP_NO_TLSv1_1
                          + ops.SSL_OP_NO_TLSv1_2 + ops.SSL_OP_NO_TLSv1_3
ops.SSL_OP_NO_DTLS_MASK = ops.SSL_OP_NO_DTLSv1 + ops.SSL_OP_NO_DTLSv1_2
for k, v in pairs(ops) do
  _M[k] = v
end

local mt = {__index = _M}

local ssl_ptr_ct = ffi.typeof('SSL*')

local stack_of_ssl_cipher_iter = function(ctx)
  return stack_lib.mt_of("SSL_CIPHER", function(x) return x end, {}, true).__ipairs({ctx = ctx})
end

function _M.from_request()
  -- don't GC this
  local ctx, err = nginx_aux.get_req_ssl()
  if err ~= nil then
    return nil, err
  end

  return setmetatable({
    ctx = ctx,
    -- the cdata is not manage by Lua, don't GC on Lua side
    _managed = false,
    -- this is the client SSL session
    _server = true,
  }, mt)
end

function _M.from_socket(socket)
  if not socket then
    return nil, "expect a ngx.socket.tcp instance at #1"
  end
  -- don't GC this
  local ctx, err = nginx_aux.get_socket_ssl(socket)
  if err ~= nil then
    return nil, err
  end

  return setmetatable({
    ctx = ctx,
    -- the cdata is not manage by Lua, don't GC on Lua side
    _managed = false,
    -- this is the client SSL session
    _server = false,
  }, mt)
end

function _M.istype(l)
  return l and l.ctx and ffi.istype(ssl_ptr_ct, l.ctx)
end

function _M:get_peer_certificate()
  local x509
  if OPENSSL_3X then
    x509 = C.SSL_get1_peer_certificate(self.ctx)
  else
    x509 = C.SSL_get_peer_certificate(self.ctx)
  end

  if x509 == nil then
    return nil
  end
  ffi.gc(x509, C.X509_free)

  local err
  -- always copy, although the ref counter of returned x509 is
  -- already increased by one.
  x509, err = x509_lib.dup(x509)
  if err then
    return nil, err
  end

  return x509
end

function _M:get_peer_cert_chain()
  local stack = C.SSL_get_peer_cert_chain(self.ctx)

  if stack == nil then
    return nil
  end

  return chain_lib.dup(stack)
end

-- TLSv1.3
function _M:set_ciphersuites(ciphers)
  if C.SSL_set_ciphersuites(self.ctx, ciphers) ~= 1 then
    return false, format_error("ssl:set_ciphers: SSL_set_ciphersuites")
  end

  return true
end

-- TLSv1.2 and lower
function _M:set_cipher_list(ciphers)
  if C.SSL_set_cipher_list(self.ctx, ciphers) ~= 1 then
    return false, format_error("ssl:set_ciphers: SSL_set_cipher_list")
  end

  return true
end

function _M:get_ciphers()
  local ciphers = C.SSL_get_ciphers(self.ctx)

  if ciphers == nil then
    return nil
  end

  local ret = {}

  for i, cipher in stack_of_ssl_cipher_iter(ciphers) do
    cipher = C.SSL_CIPHER_get_name(cipher)
    if cipher == nil then
      return nil, format_error("ssl:get_ciphers: SSL_CIPHER_get_name")
    end
    ret[i] = ffi_str(cipher)
  end

  return table.concat(ret, ":")
end

function _M:get_cipher_name()
  local cipher = C.SSL_get_current_cipher(self.ctx)

  if cipher == nil then
    return nil
  end

  cipher = C.SSL_CIPHER_get_name(cipher)
  if cipher == nil then
    return nil, format_error("ssl:get_cipher_name: SSL_CIPHER_get_name")
  end
  return ffi_str(cipher)
end

function _M:set_timeout(tm)
  local session = C.SSL_get_session(self.ctx)

  if session == nil then
    return false, format_error("ssl:set_timeout: SSL_get_session")
  end

  if C.SSL_SESSION_set_timeout(session, tm) ~= 1 then
    return false, format_error("ssl:set_timeout: SSL_SESSION_set_timeout")
  end
  return true
end

function _M:get_timeout()
  local session = C.SSL_get_session(self.ctx)

  if session == nil then
    return false, format_error("ssl:get_timeout: SSL_get_session")
  end

  return tonumber(C.SSL_SESSION_get_timeout(session))
end

local ssl_verify_default_cb = ffi_cast("verify_callback", function()
  return 1
end)

function _M:set_verify(mode, cb)
  if self._verify_cb then
    self._verify_cb:free()
  end

  if cb then
    cb = ffi_cast("verify_callback", cb)
    self._verify_cb = cb
  end

  C.SSL_set_verify(self.ctx, mode, cb or ssl_verify_default_cb)

  return true
end

function _M:free_verify_cb()
  if self._verify_cb then
    self._verify_cb:free()
    self._verify_cb = nil
  end
end

function _M:add_client_ca(x509)
  if not self._server then
    return false, "ssl:add_client_ca is only supported on server side"
  end

  if not x509_lib.istype(x509) then
    return false, "expect a x509 instance at #1"
  end

  if C.SSL_add_client_CA(self.ctx, x509.ctx) ~= 1 then
    return false, format_error("ssl:add_client_ca: SSL_add_client_CA")
  end

  return true
end

function _M:set_options(...)
  local bitmask = 0
  for _, opt in ipairs({...}) do
    bitmask = bit.bor(bitmask, opt)
  end

  if OPENSSL_10 then
    bitmask = C.SSL_ctrl(self.ctx, 32, bitmask, nil) -- SSL_CTRL_OPTIONS
  else
    bitmask = C.SSL_set_options(self.ctx, bitmask)
  end

  return tonumber(bitmask)
end

function _M:get_options(readable)
  local bitmask
  if OPENSSL_10 then
    bitmask = C.SSL_ctrl(self.ctx, 32, 0, nil) -- SSL_CTRL_OPTIONS
  else
    bitmask = C.SSL_get_options(self.ctx)
  end

  if not readable then
    return tonumber(bitmask)
  end

  local ret = {}
  for k, v in pairs(ops) do
    if bit.band(v, bitmask) > 0 then
      table.insert(ret, k)
    end
  end
  table.sort(ret)

  return ret
end

function _M:clear_options(...)
  local bitmask = 0
  for _, opt in ipairs({...}) do
    bitmask = bit.bor(bitmask, opt)
  end

  if OPENSSL_10 then
    bitmask = C.SSL_ctrl(self.ctx, 77, bitmask, nil) -- SSL_CTRL_CLEAR_OPTIONS
  else
    bitmask = C.SSL_clear_options(self.ctx, bitmask)
  end

  return tonumber(bitmask)
end

local valid_protocols = {
  ["SSLv3"] = ops.SSL_OP_NO_SSLv3,
  ["TLSv1"] = ops.SSL_OP_NO_TLSv1,
  ["TLSv1.1"] = ops.SSL_OP_NO_TLSv1_1,
  ["TLSv1.2"] = ops.SSL_OP_NO_TLSv1_2,
  ["TLSv1.3"] = ops.SSL_OP_NO_TLSv1_3,
}
local any_tlsv1 = ops.SSL_OP_NO_TLSv1_1 + ops.SSL_OP_NO_TLSv1_2 + ops.SSL_OP_NO_TLSv1_3

function _M:set_protocols(...)
  local bitmask = 0
  for _, prot in ipairs({...}) do
    local b = valid_protocols[prot]
    if not b then
      return nil, "\"" .. prot .. "\" is not a valid protocol"
    end
    bitmask = bit.bor(bitmask, b)
  end

  if bit.band(bitmask, any_tlsv1) > 0 then
    bitmask = bit.bor(bitmask, ops.SSL_OP_NO_TLSv1)
  end

  -- first disable all protocols
  if OPENSSL_10 then
    C.SSL_ctrl(self.ctx, 32, ops.SSL_OP_NO_SSL_MASK, nil) -- SSL_CTRL_OPTIONS
  else
    C.SSL_set_options(self.ctx, ops.SSL_OP_NO_SSL_MASK)
  end
  
  -- then enable selected protocols
  if OPENSSL_10 then
    return tonumber(C.SSL_clear_options(self.ctx, bitmask))
  else
    return tonumber(C.SSL_ctrl(self.ctx, 77, bitmask, nil)) -- SSL_CTRL_CLEAR_OPTIONS)
  end
end

return _M