local ffi = require "ffi"
local ffi_cast = ffi.cast

require "resty.openssl.include.ssl"

local ssl_type = ffi.typeof("SSL*")
local ssl_ctx_type = ffi.typeof("SSL_CTX*")

local ok, ngx_ssl = pcall(require, "ngx.ssl")
local get_req_ssl_pointer = ok and ngx_ssl.get_req_ssl_pointer
local get_req_ssl_context = ok and ngx_ssl.get_req_ssl_ctx

local socket_ok = pcall(require, "resty.core.socket")
local function has_socket_api(name)
  if not socket_ok then
    return false
  end

  -- Some lua-resty-core versions install the methods even when the C
  -- symbols are unavailable in the running Nginx binary.
  return pcall(function()
    return ffi.C["ngx_" .. ngx.config.subsystem .. "_lua_ffi_socket_tcp_" .. name]
  end)
end

local has_socket_ssl = has_socket_api("get_ssl_pointer")
local has_socket_ssl_ctx = has_socket_api("get_ssl_ctx")
local legacy

local function get_legacy()
  if not legacy then
    legacy = require "resty.openssl.auxiliary.nginx_legacy"
  end

  return legacy
end

local function get_req_ssl()
  if not get_req_ssl_pointer then
    return get_legacy().get_req_ssl()
  end

  local ssl, err = get_req_ssl_pointer()
  if ssl == nil then
    return nil, err
  end

  return ffi_cast(ssl_type, ssl)
end

local function get_req_ssl_ctx()
  if not get_req_ssl_context then
    return get_legacy().get_req_ssl_ctx()
  end

  local ctx, err = get_req_ssl_context()
  if ctx == nil then
    return nil, err
  end

  return ffi_cast(ssl_ctx_type, ctx)
end

local function get_socket_ssl(sock)
  if not has_socket_ssl or not sock.getsslpointer then
    return get_legacy().get_socket_ssl(sock)
  end

  local ssl, err = sock:getsslpointer()
  if ssl == nil then
    return nil, err
  end

  return ffi_cast(ssl_type, ssl)
end

local function get_socket_ssl_ctx(sock)
  if not has_socket_ssl_ctx or not sock.getsslctx then
    return get_legacy().get_socket_ssl_ctx(sock)
  end

  local ctx, err = sock:getsslctx()
  if ctx == nil then
    return nil, err
  end

  return ffi_cast(ssl_ctx_type, ctx)
end

return {
  get_req_ssl = get_req_ssl,
  get_req_ssl_ctx = get_req_ssl_ctx,
  get_socket_ssl = get_socket_ssl,
  get_socket_ssl_ctx = get_socket_ssl_ctx,
}
