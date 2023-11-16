local get_req_ssl, get_req_ssl_ctx
local get_socket_ssl, get_socket_ssl_ctx

local pok, nginx_c = pcall(require, "resty.openssl.auxiliary.nginx_c")

if pok and not os.getenv("CI_SKIP_NGINX_C") then
  get_req_ssl = nginx_c.get_req_ssl
  get_req_ssl_ctx = nginx_c.get_req_ssl_ctx
  get_socket_ssl = nginx_c.get_socket_ssl
  get_socket_ssl_ctx = nginx_c.get_socket_ssl
else
  local ffi = require "ffi"

  ffi.cdef [[
    // Nginx seems to always config _FILE_OFFSET_BITS=64, this should always be 8 byte
    typedef long long off_t;
    typedef unsigned int socklen_t; // windows uses int, same size
    typedef unsigned short in_port_t;

    typedef struct ssl_st SSL;
    typedef struct ssl_ctx_st SSL_CTX;

    typedef long (*ngx_recv_pt)(void *c, void *buf, size_t size);
    typedef long (*ngx_recv_chain_pt)(void *c, void *in,
        off_t limit);
    typedef long (*ngx_send_pt)(void *c, void *buf, size_t size);
    typedef void *(*ngx_send_chain_pt)(void *c, void *in,
        off_t limit);

    typedef struct {
      size_t             len;
      void               *data;
    } ngx_str_t;

    typedef struct {
      SSL             *connection;
      SSL_CTX         *session_ctx;
      // trimmed
    } ngx_ssl_connection_s;
  ]]

  local ngx_version = ngx.config.nginx_version
  if ngx_version == 1017008 or ngx_version == 1019003 or ngx_version == 1019009 
    or ngx_version == 1021004 then
    -- 1.17.8, 1.19.3, 1.19.9, 1.21.4
    -- https://github.com/nginx/nginx/blob/master/src/core/ngx_connection.h
    ffi.cdef [[
    typedef struct {
      ngx_str_t           src_addr;
      ngx_str_t           dst_addr;
      in_port_t           src_port;
      in_port_t           dst_port;
    } ngx_proxy_protocol_t;

    typedef struct {
      void               *data;
      void               *read;
      void               *write;

      int                 fd;

      ngx_recv_pt         recv;
      ngx_send_pt         send;
      ngx_recv_chain_pt   recv_chain;
      ngx_send_chain_pt   send_chain;

      void               *listening;

      off_t               sent;

      void               *log;

      void               *pool;

      int                 type;

      void                *sockaddr;
      socklen_t           socklen;
      ngx_str_t           addr_text;

      // https://github.com/nginx/nginx/commit/be932e81a1531a3ba032febad968fc2006c4fa48
      ngx_proxy_protocol_t  *proxy_protocol;

      ngx_ssl_connection_s  *ssl;
      // trimmed
    } ngx_connection_s;
  ]]
  else
    error("resty.openssl.auxiliary.nginx doesn't support Nginx version " .. ngx_version, 2)
  end

  ffi.cdef [[
    typedef struct {
        ngx_connection_s                     *connection;
        // trimmed
    } ngx_stream_lua_request_s;

    typedef struct {
      unsigned int                     signature;         /* "HTTP" */

      ngx_connection_s                 *connection;
      // trimmed
    } ngx_http_request_s;
  ]]

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

  local SOCKET_CTX_INDEX = 1

  local NO_C_MODULE_WARNING_MSG_SHOWN = false
  local NO_C_MODULE_WARNING_MSG = "note resty.openssl.auxiliary.nginx is using plain FFI " ..
                                  "and it's only intended to be used in development, " ..
                                  "consider using lua-resty-openssl.aux-module in production."

  local function get_ngx_ssl_from_req()
    if not NO_C_MODULE_WARNING_MSG_SHOWN then
      ngx.log(ngx.WARN, NO_C_MODULE_WARNING_MSG)
      NO_C_MODULE_WARNING_MSG_SHOWN = true
    end

    local c = get_request()
    if ngx.config.subsystem == "stream" then
      c = ffi.cast("ngx_stream_lua_request_s*", c)
    else -- http
      c = ffi.cast("ngx_http_request_s*", c)
    end

    local ngx_ssl = c.connection.ssl
    if ngx_ssl == nil then
      return nil, "c.connection.ssl is nil"
    end
    return ngx_ssl
  end

  get_req_ssl = function()
    local ssl, err = get_ngx_ssl_from_req()
    if err then
      return nil, err
    end

    return ssl.connection
  end

  get_req_ssl_ctx = function()
    local ssl, err = get_ngx_ssl_from_req()
    if err then
      return nil, err
    end

    return ssl.session_ctx
  end

  -- https://github.com/openresty/stream-lua-nginx-module/blob/master/src/ngx_stream_lua_socket_tcp.h
  ffi.cdef[[
    typedef struct ngx_http_lua_socket_tcp_upstream_s
                  ngx_http_lua_socket_tcp_upstream_t;

    typedef struct {
      ngx_connection_s                *connection;
      // trimmed
    } ngx_peer_connection_s;

    typedef
      int (*ngx_http_lua_socket_tcp_retval_handler_masked)(void *r,
      void *u, void *L);

    typedef void (*ngx_http_lua_socket_tcp_upstream_handler_pt_masked)
      (void *r, void *u);


    typedef
        int (*ngx_stream_lua_socket_tcp_retval_handler)(void *r,
            void *u, void *L);

    typedef void (*ngx_stream_lua_socket_tcp_upstream_handler_pt)
        (void *r, void *u);

    typedef struct {
      ngx_stream_lua_socket_tcp_retval_handler            read_prepare_retvals;
      ngx_stream_lua_socket_tcp_retval_handler            write_prepare_retvals;
      ngx_stream_lua_socket_tcp_upstream_handler_pt       read_event_handler;
      ngx_stream_lua_socket_tcp_upstream_handler_pt       write_event_handler;

      void                    *socket_pool;

      void                    *conf;
      void                    *cleanup;
      void                    *request;

      ngx_peer_connection_s            peer;
      // trimmed
    } ngx_stream_lua_socket_tcp_upstream_s;
  ]]

  local ngx_lua_version = ngx.config and
        ngx.config.ngx_lua_version and
        ngx.config.ngx_lua_version

  if ngx_lua_version >= 10019 and ngx_lua_version <= 10025 then
    -- https://github.com/openresty/lua-nginx-module/blob/master/src/ngx_http_lua_socket_tcp.h
    ffi.cdef[[
      typedef struct {
        ngx_http_lua_socket_tcp_retval_handler_masked          read_prepare_retvals;
        ngx_http_lua_socket_tcp_retval_handler_masked          write_prepare_retvals;
        ngx_http_lua_socket_tcp_upstream_handler_pt_masked     read_event_handler;
        ngx_http_lua_socket_tcp_upstream_handler_pt_masked     write_event_handler;

        void                            *udata_queue; // 0.10.19

        void                            *socket_pool;

        void                            *conf;
        void                            *cleanup;
        void                            *request;
        ngx_peer_connection_s            peer;
        // trimmed
      } ngx_http_lua_socket_tcp_upstream_s;
    ]]
  elseif ngx_lua_version < 10019 then
    -- the struct doesn't seem to get changed a long time since birth
    ffi.cdef[[
      typedef struct {
        ngx_http_lua_socket_tcp_retval_handler_masked          read_prepare_retvals;
        ngx_http_lua_socket_tcp_retval_handler_masked          write_prepare_retvals;
        ngx_http_lua_socket_tcp_upstream_handler_pt_masked     read_event_handler;
        ngx_http_lua_socket_tcp_upstream_handler_pt_masked     write_event_handler;

        void                            *socket_pool;

        void                            *conf;
        void                            *cleanup;
        void                            *request;
        ngx_peer_connection_s            peer;
        // trimmed
      } ngx_http_lua_socket_tcp_upstream_s;
    ]]
  else
    error("resty.openssl.auxiliary.nginx doesn't support lua-nginx-module version " .. (ngx_lua_version or "nil"), 2)
  end

  local function get_ngx_ssl_from_socket_ctx(sock)
    if not NO_C_MODULE_WARNING_MSG_SHOWN then
      ngx.log(ngx.WARN, NO_C_MODULE_WARNING_MSG)
      NO_C_MODULE_WARNING_MSG_SHOWN = true
    end

    local u = sock[SOCKET_CTX_INDEX]
    if u == nil then
      return nil, "lua_socket_tcp_upstream_t not found"
    end

    if ngx.config.subsystem == "stream" then
      u = ffi.cast("ngx_stream_lua_socket_tcp_upstream_s*", u)
    else -- http
      u = ffi.cast("ngx_http_lua_socket_tcp_upstream_s*", u)
    end

    local p = u.peer
    if p == nil then
      return nil, "u.peer is nil"
    end

    local uc = p.connection
    if uc == nil then
      return nil, "u.peer.connection is nil"
    end

    local ngx_ssl = uc.ssl
    if ngx_ssl == nil then
      return nil, "u.peer.connection.ssl is nil"
    end
    return ngx_ssl
  end

  get_socket_ssl = function(sock)
    local ssl, err = get_ngx_ssl_from_socket_ctx(sock)
    if err then
      return nil, err
    end

    return ssl.connection
  end

  get_socket_ssl_ctx = function(sock)
    local ssl, err = get_ngx_ssl_from_socket_ctx(sock)
    if err then
      return nil, err
    end

    return ssl.session_ctx
  end

end


return {
  get_req_ssl = get_req_ssl,
  get_req_ssl_ctx = get_req_ssl_ctx,
  get_socket_ssl = get_socket_ssl,
  get_socket_ssl_ctx = get_socket_ssl_ctx,
}
