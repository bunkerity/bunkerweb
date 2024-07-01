local base = require "resty.core.base"
base.allows_subsystem("http")
local debug = require "debug"
local ffi = require "ffi"


local error    = error
local assert   = assert
local tonumber = tonumber
local tostring = tostring
local type     = type
local select   = select
local registry = debug.getregistry()

local C       = ffi.C
local ffi_new = ffi.new
local ffi_str = ffi.string
local ffi_gc  = ffi.gc

local get_string_buf = base.get_string_buf
local get_size_ptr   = base.get_size_ptr
local get_request    = base.get_request

local co_yield = coroutine._yield


local option_index = {
    ["keepalive"]   = 1,
    ["reuseaddr"]   = 2,
    ["tcp-nodelay"] = 3,
    ["sndbuf"]      = 4,
    ["rcvbuf"]      = 5,
}


ffi.cdef[[
typedef struct ngx_http_lua_socket_tcp_upstream_s
    ngx_http_lua_socket_tcp_upstream_t;

int
ngx_http_lua_ffi_socket_tcp_getoption(ngx_http_lua_socket_tcp_upstream_t *u,
    int opt, int *val, unsigned char *err, size_t *errlen);

int
ngx_http_lua_ffi_socket_tcp_setoption(ngx_http_lua_socket_tcp_upstream_t *u,
    int opt, int val, unsigned char *err, size_t *errlen);

int
ngx_http_lua_ffi_socket_tcp_sslhandshake(ngx_http_request_t *r,
    ngx_http_lua_socket_tcp_upstream_t *u, void *sess,
    int enable_session_reuse, ngx_str_t *server_name, int verify,
    int ocsp_status_req, void *chain, void *pkey, char **errmsg);

int
ngx_http_lua_ffi_socket_tcp_get_sslhandshake_result(ngx_http_request_t *r,
    ngx_http_lua_socket_tcp_upstream_t *u, void **sess, char **errmsg,
    int *openssl_error_code);

void
ngx_http_lua_ffi_ssl_free_session(void *sess);
]]


local output_value_buf = ffi_new("int[1]")
local ERR_BUF_SIZE = 4096

local FFI_OK         = base.FFI_OK
local FFI_ERROR      = base.FFI_ERROR
local FFI_DONE       = base.FFI_DONE
local FFI_AGAIN      = base.FFI_AGAIN
local FFI_NO_REQ_CTX = base.FFI_NO_REQ_CTX

local SOCKET_CTX_INDEX          = 1
local SOCKET_CLIENT_CERT_INDEX  = 6
local SOCKET_CLIENT_PKEY_INDEX  = 7


local function get_tcp_socket(cosocket)
    local tcp_socket = cosocket[SOCKET_CTX_INDEX]
    if not tcp_socket then
        error("socket is never created nor connected")
    end

    return tcp_socket
end


local function getoption(cosocket, option)
    local tcp_socket = get_tcp_socket(cosocket)

    if option == nil then
        return nil, 'missing the "option" argument'
    end

    if option_index[option] == nil then
        return nil, "unsupported option " .. tostring(option)
    end

    local err = get_string_buf(ERR_BUF_SIZE)
    local errlen = get_size_ptr()
    errlen[0] = ERR_BUF_SIZE

    local rc = C.ngx_http_lua_ffi_socket_tcp_getoption(tcp_socket,
                                                       option_index[option],
                                                       output_value_buf,
                                                       err,
                                                       errlen)
    if rc ~= FFI_OK then
        return nil, ffi_str(err, errlen[0])
    end

    return tonumber(output_value_buf[0])
end


local function setoption(cosocket, option, value)
    local tcp_socket = get_tcp_socket(cosocket)

    if option == nil then
        return nil, 'missing the "option" argument'
    end

    if value == nil then
        return nil, 'missing the "value" argument'
    end

    if option_index[option] == nil then
        return nil, "unsupported option " .. tostring(option)
    end

    local err = get_string_buf(ERR_BUF_SIZE)
    local errlen = get_size_ptr()
    errlen[0] = ERR_BUF_SIZE

    local rc = C.ngx_http_lua_ffi_socket_tcp_setoption(tcp_socket,
                                                       option_index[option],
                                                       value,
                                                       err,
                                                       errlen)
    if rc ~= FFI_OK then
        return nil, ffi_str(err, errlen[0])
    end

    return true
end


local errmsg             = base.get_errmsg_ptr()
local session_ptr        = ffi_new("void *[1]")
local server_name_str    = ffi_new("ngx_str_t[1]")
local openssl_error_code = ffi_new("int[1]")


local function setclientcert(cosocket, cert, pkey)
    if not cert and not pkey then
        cosocket[SOCKET_CLIENT_CERT_INDEX] = nil
        cosocket[SOCKET_CLIENT_PKEY_INDEX] = nil
        return true
    end

    if not cert or not pkey then
        return nil,
               "client certificate must be supplied with corresponding " ..
               "private key"
    end

    if type(cert) ~= "cdata" then
        return nil, "bad cert arg: cdata expected, got " .. type(cert)
    end

    if type(pkey) ~= "cdata" then
        return nil, "bad pkey arg: cdata expected, got " .. type(pkey)
    end

    cosocket[SOCKET_CLIENT_CERT_INDEX] = cert
    cosocket[SOCKET_CLIENT_PKEY_INDEX] = pkey

    return true
end


local function sslhandshake(cosocket, reused_session, server_name, ssl_verify,
    send_status_req, ...)

    local n = select("#", ...)
    if not cosocket or n > 0 then
        error("ngx.socket sslhandshake: expecting 1 ~ 5 arguments " ..
              "(including the object), but seen " .. (cosocket and 5 + n or 0))
    end

    local r = get_request()
    if not r then
        error("no request found", 2)
    end

    session_ptr[0] = type(reused_session) == "cdata" and reused_session or nil

    if server_name then
        server_name_str[0].data = server_name
        server_name_str[0].len = #server_name

    else
        server_name_str[0].data = nil
        server_name_str[0].len = 0
    end

    local u = get_tcp_socket(cosocket)

    local rc = C.ngx_http_lua_ffi_socket_tcp_sslhandshake(r, u,
                   session_ptr[0],
                   reused_session ~= false,
                   server_name_str,
                   ssl_verify and 1 or 0,
                   send_status_req and 1 or 0,
                   cosocket[SOCKET_CLIENT_CERT_INDEX],
                   cosocket[SOCKET_CLIENT_PKEY_INDEX],
                   errmsg)

    if rc == FFI_NO_REQ_CTX then
        error("no request ctx found", 2)
    end

    while true do
        if rc == FFI_ERROR then
            if openssl_error_code[0] ~= 0 then
                return nil, openssl_error_code[0] .. ": " .. ffi_str(errmsg[0])
            end

            return nil, ffi_str(errmsg[0])
        end

        if rc == FFI_DONE then
            return reused_session
        end

        if rc == FFI_OK then
            if reused_session == false then
                return true
            end

            rc = C.ngx_http_lua_ffi_socket_tcp_get_sslhandshake_result(r, u,
                     session_ptr, errmsg, openssl_error_code)

            assert(rc == FFI_OK)

            if session_ptr[0] == nil then
                return session_ptr[0]
            end

            return ffi_gc(session_ptr[0], C.ngx_http_lua_ffi_ssl_free_session)
        end

        assert(rc == FFI_AGAIN)

        co_yield()

        rc = C.ngx_http_lua_ffi_socket_tcp_get_sslhandshake_result(r, u,
                 session_ptr, errmsg, openssl_error_code)
    end
end


do
    local method_table = registry.__tcp_cosocket_mt
    method_table.getoption = getoption
    method_table.setoption = setoption
    method_table.setclientcert = setclientcert
    method_table.sslhandshake  = sslhandshake
end


return { version = base.version }
