local ffi = require "ffi"
local C = ffi.C
local new_tab = table.new
local char = string.char
local concat = table.concat

require "resty.openssl.include.ssl"

local nginx_aux = require("resty.openssl.auxiliary.nginx")

local _M = {}
local mt = {__index = _M}

local ssl_ctx_ptr_ct = ffi.typeof('SSL_CTX*')

function _M.from_request()
  -- don't GC this
  local ctx, err = nginx_aux.get_req_ssl_ctx()
  if err ~= nil then
    return nil, err
  end

  return setmetatable({
    ctx = ctx,
    -- the cdata is not manage by Lua, don't GC on Lua side
    _managed = false,
    -- this is the Server SSL session
    _server = true,
  }, mt)
end

function _M.from_socket(socket)
  if not socket then
    return nil, "expect a ngx.socket.tcp instance at #1"
  end
  -- don't GC this
  local ctx, err = nginx_aux.get_socket_ssl_ctx(socket)
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
  return l and l.ctx and ffi.istype(ssl_ctx_ptr_ct, l.ctx)
end

local function encode_alpn_wire(alpns)
  local ret = new_tab(#alpns*2, 0)
  for i, alpn in ipairs(alpns) do
    ret[i*2-1] = char(#alpn)
    ret[i*2] = alpn
  end

  return concat(ret, "")
end

function _M:set_alpns(alpns)
  if not self._server then
    return nil, "ssl_ctx:set_alpns is only supported on server side"
  end

  alpns = encode_alpn_wire(alpns)

  if self._alpn_select_cb then
    self._alpn_select_cb:free()
  end

  local alpn_select_cb = ffi.cast("SSL_CTX_alpn_select_cb_func", function(_, out, outlen, client, client_len)
    local code = ffi.C.SSL_select_next_proto(
      ffi.cast("unsigned char **", out), outlen,
      alpns, #alpns,
      client, client_len)
    if code ~= 1 then -- OPENSSL_NPN_NEGOTIATED
      return 3 -- SSL_TLSEXT_ERR_NOACK
    end
    return 0 -- SSL_TLSEXT_ERR_OK
  end)

  C.SSL_CTX_set_alpn_select_cb(self.ctx, alpn_select_cb, nil)
  -- store the reference to avoid it being GC'ed
  self._alpn_select_cb = alpn_select_cb

  return true
end


return _M