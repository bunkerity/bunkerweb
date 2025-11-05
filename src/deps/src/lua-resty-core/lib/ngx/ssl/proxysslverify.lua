-- Copyright (C) Yichun Zhang (agentzh)


local base = require "resty.core.base"
base.allows_subsystem('http', 'stream')


local ffi = require "ffi"
local C = ffi.C
local ffi_gc = ffi.gc
local ffi_str = ffi.string
local get_request = base.get_request
local error = error
local errmsg = base.get_errmsg_ptr()

local FFI_OK = base.FFI_OK
local FFI_ERROR = base.FFI_ERROR
local subsystem = ngx.config.subsystem
local ngx_phase = ngx.get_phase

local ngx_lua_ffi_proxy_ssl_set_verify_result
local ngx_lua_ffi_proxy_ssl_get_verify_result
local ngx_lua_ffi_proxy_ssl_get_verify_cert
local ngx_lua_ffi_proxy_ssl_free_verify_cert


if subsystem == 'http' then
    ffi.cdef[[
    int ngx_http_lua_ffi_proxy_ssl_set_verify_result(ngx_http_request_t *r,
        int verify_result, char **err);

    int ngx_http_lua_ffi_proxy_ssl_get_verify_result(ngx_http_request_t *r,
        char **err);

    void *ngx_http_lua_ffi_proxy_ssl_get_verify_cert(ngx_http_request_t *r,
        char **err);

    void ngx_http_lua_ffi_proxy_ssl_free_verify_cert(void *cdata);
    ]]

    ngx_lua_ffi_proxy_ssl_set_verify_result =
        C.ngx_http_lua_ffi_proxy_ssl_set_verify_result
    ngx_lua_ffi_proxy_ssl_get_verify_result =
        C.ngx_http_lua_ffi_proxy_ssl_get_verify_result
    ngx_lua_ffi_proxy_ssl_get_verify_cert =
        C.ngx_http_lua_ffi_proxy_ssl_get_verify_cert
    ngx_lua_ffi_proxy_ssl_free_verify_cert =
        C.ngx_http_lua_ffi_proxy_ssl_free_verify_cert



elseif subsystem == 'stream' then
    ffi.cdef[[
    int ngx_stream_lua_ffi_proxy_ssl_set_verify_result(
        ngx_stream_lua_request_t *r, int verify_result, char **err);

    int ngx_stream_lua_ffi_proxy_ssl_get_verify_result(
        ngx_stream_lua_request_t *r, char **err);

    void *ngx_stream_lua_ffi_proxy_ssl_get_verify_cert(
        ngx_stream_lua_request_t *r, char **err);

    void ngx_stream_lua_ffi_proxy_ssl_free_verify_cert(void *cdata);
    ]]

    ngx_lua_ffi_proxy_ssl_set_verify_result =
        C.ngx_stream_lua_ffi_proxy_ssl_set_verify_result
    ngx_lua_ffi_proxy_ssl_get_verify_result =
        C.ngx_stream_lua_ffi_proxy_ssl_get_verify_result
    ngx_lua_ffi_proxy_ssl_get_verify_cert =
        C.ngx_stream_lua_ffi_proxy_ssl_get_verify_cert
    ngx_lua_ffi_proxy_ssl_free_verify_cert =
        C.ngx_stream_lua_ffi_proxy_ssl_free_verify_cert
end


local _M = { version = base.version }


-- return ok, err
function _M.set_verify_result(verify_result)
    local r = get_request()
    if not r then
        error("no request found")
    end

    if ngx_phase() ~= "proxy_ssl_verify" then
        error("API disabled in the current context")
    end

    local rc = ngx_lua_ffi_proxy_ssl_set_verify_result(r, verify_result, errmsg)
    if rc == FFI_OK then
        return true
    end

    return nil, ffi_str(errmsg[0])
end


-- return verify_result, err
function _M.get_verify_result()
    local r = get_request()
    if not r then
        error("no request found")
    end

    if ngx_phase() ~= "proxy_ssl_verify" then
        error("API disabled in the current context")
    end

    local rc = ngx_lua_ffi_proxy_ssl_get_verify_result(r, errmsg)
    if rc == FFI_ERROR then
        return nil, ffi_str(errmsg[0])
    end

    return rc
end


-- return cert, err
function _M.get_verify_cert()
    local r = get_request()
    if not r then
        error("no request found")
    end

    if ngx_phase() ~= "proxy_ssl_verify" then
        error("API disabled in the current context")
    end

    local cert = ngx_lua_ffi_proxy_ssl_get_verify_cert(r, errmsg)
    if cert ~= nil then
        return ffi_gc(cert, ngx_lua_ffi_proxy_ssl_free_verify_cert)
    end

    return nil, ffi_str(errmsg[0])
end


return _M
