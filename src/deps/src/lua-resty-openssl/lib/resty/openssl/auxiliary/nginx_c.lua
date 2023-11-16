local ffi = require "ffi"
local C = ffi.C

local SOCKET_CTX_INDEX = 1
local NGX_OK = ngx.OK


local get_req_ssl, get_req_ssl_ctx
local get_socket_ssl, get_socket_ssl_ctx

local get_request
do
  local ok, exdata = pcall(require, "thread.exdata")
  if ok and exdata then
    function get_request()
      local r = exdata()
      if r ~= nil then
          return r
      end
    end

  else
    local getfenv = getfenv

    function get_request()
      return getfenv(0).__ngx_req
    end
  end
end


local stream_subsystem = false
if ngx.config.subsystem == "stream" then
  stream_subsystem = true

  ffi.cdef [[
    typedef struct ngx_stream_lua_request_s ngx_stream_lua_request_t;
    typedef struct ngx_stream_lua_socket_tcp_upstream_s ngx_stream_lua_socket_tcp_upstream_t;

    int ngx_stream_lua_resty_openssl_aux_get_request_ssl(ngx_stream_lua_request_t *r,
        void **_ssl_conn);

    int ngx_stream_lua_resty_openssl_aux_get_request_ssl_ctx(ngx_stream_lua_request_t *r,
        void **_sess);

    int ngx_stream_lua_resty_openssl_aux_get_socket_ssl(ngx_stream_lua_socket_tcp_upstream_t *u,
        void **_ssl_conn);

    int ngx_stream_lua_resty_openssl_aux_get_socket_ssl_ctx(ngx_stream_lua_socket_tcp_upstream_t *u,
        void **_sess);
  ]]

  -- sanity test
  local _ = C.ngx_stream_lua_resty_openssl_aux_get_request_ssl
else
  ffi.cdef [[
    typedef struct ngx_http_request_s ngx_http_request_t;
    typedef struct ngx_http_lua_socket_tcp_upstream_s ngx_http_lua_socket_tcp_upstream_t;

    int ngx_http_lua_resty_openssl_aux_get_request_ssl(ngx_http_request_t *r,
        void **_ssl_conn);

    int ngx_http_lua_resty_openssl_aux_get_request_ssl_ctx(ngx_http_request_t *r,
        void **_sess);

    int ngx_http_lua_resty_openssl_aux_get_socket_ssl(ngx_http_lua_socket_tcp_upstream_t *u,
        void **_ssl_conn);

    int ngx_http_lua_resty_openssl_aux_get_socket_ssl_ctx(ngx_http_lua_socket_tcp_upstream_t *u,
        void **_sess);
  ]]

  -- sanity test
  local _ = C.ngx_http_lua_resty_openssl_aux_get_request_ssl
end

local void_pp = ffi.new("void *[1]")
local ssl_type = ffi.typeof("SSL*")
local ssl_ctx_type = ffi.typeof("SSL_CTX*")

get_req_ssl = function()
  local c = get_request()

  local ret
  if stream_subsystem then
    ret = C.ngx_stream_lua_resty_openssl_aux_get_request_ssl(c, void_pp)
  else
    ret = C.ngx_http_lua_resty_openssl_aux_get_request_ssl(c, void_pp)
  end

  if ret ~= NGX_OK then
    return nil, "cannot read r->connection->ssl->connection"
  end

  return ffi.cast(ssl_type, void_pp[0])
end

get_req_ssl_ctx = function()
  local c = get_request()

  local ret
  if stream_subsystem then
    ret = C.ngx_stream_lua_resty_openssl_aux_get_request_ssl_ctx(c, void_pp)
  else
    ret = C.ngx_http_lua_resty_openssl_aux_get_request_ssl_ctx(c, void_pp)
  end

  if ret ~= NGX_OK then
    return nil, "cannot read r->connection->ssl->session_ctx"
  end

  return ffi.cast(ssl_ctx_type, void_pp[0])
end

get_socket_ssl = function(sock)
  local u = sock[SOCKET_CTX_INDEX]

  local ret
  if stream_subsystem then
    ret = C.ngx_stream_lua_resty_openssl_aux_get_socket_ssl(u, void_pp)
  else
    ret = C.ngx_http_lua_resty_openssl_aux_get_socket_ssl(u, void_pp)
  end

  if ret ~= NGX_OK then
    return nil, "cannot read u->peer.connection->ssl->connection"
  end

  return ffi.cast(ssl_type, void_pp[0])
end

get_socket_ssl_ctx = function(sock)
  local u = sock[SOCKET_CTX_INDEX]

  local ret
  if stream_subsystem then
    ret = C.ngx_stream_lua_resty_openssl_aux_get_socket_ssl_ctx(u, void_pp)
  else
    ret = C.ngx_http_lua_resty_openssl_aux_get_socket_ssl_ctx(u, void_pp)
  end

  if ret ~= NGX_OK then
    return nil, "cannot read u->peer.connection->ssl->session_ctx"
  end

  return ffi.cast(ssl_ctx_type, void_pp[0])
end

return {
  get_req_ssl = get_req_ssl,
  get_req_ssl_ctx = get_req_ssl_ctx,
  get_socket_ssl = get_socket_ssl,
  get_socket_ssl_ctx = get_socket_ssl_ctx,
}