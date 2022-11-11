-- Copyright (C) Yichun Zhang (agentzh)


local base = require "resty.core.base"
base.allows_subsystem('http')


local ffi = require "ffi"
local C = ffi.C
local ffi_str = ffi.string
local get_request = base.get_request
local error = error
local errmsg = base.get_errmsg_ptr()
local get_string_buf = base.get_string_buf
local FFI_ERROR = base.FFI_ERROR


ffi.cdef[[
int ngx_http_lua_ffi_ssl_set_serialized_session(ngx_http_request_t *r,
    const unsigned char *buf, int len, char **err);

int ngx_http_lua_ffi_ssl_get_serialized_session(ngx_http_request_t *r,
    char *buf, char **err);

int ngx_http_lua_ffi_ssl_get_session_id(ngx_http_request_t *r,
    char *buf, char **err);

int ngx_http_lua_ffi_ssl_get_serialized_session_size(ngx_http_request_t *r,
    char **err);

int ngx_http_lua_ffi_ssl_get_session_id_size(ngx_http_request_t *r,
    char **err);
]]


local _M = { version = base.version }


-- return session, err
function _M.get_serialized_session()
    local r = get_request()
    if not r then
        error("no request found")
    end

    local len = C.ngx_http_lua_ffi_ssl_get_serialized_session_size(r, errmsg)

    if len < 0 then
        return nil, ffi_str(errmsg[0])
    end

    if len > 4096 then
         return nil, "session too big to serialize"
    end
    local buf = get_string_buf(len)

    local rc = C.ngx_http_lua_ffi_ssl_get_serialized_session(r, buf, errmsg)

    if rc == FFI_ERROR then
         return nil, ffi_str(errmsg[0])
    end

    return ffi_str(buf, len)
end


-- return session_id, err
function _M.get_session_id()
    local r = get_request()
    if not r then
        error("no request found")
    end

    local len = C.ngx_http_lua_ffi_ssl_get_session_id_size(r, errmsg)

    if len < 0 then
        return nil, ffi_str(errmsg[0])
    end

    local buf = get_string_buf(len)

    local rc = C.ngx_http_lua_ffi_ssl_get_session_id(r, buf, errmsg)

    if rc == FFI_ERROR then
        return nil, ffi_str(errmsg[0])
    end

    return ffi_str(buf, len)
end


-- return ok, err
function _M.set_serialized_session(sess)
    local r = get_request()
    if not r then
        error("no request found")
    end

    local rc = C.ngx_http_lua_ffi_ssl_set_serialized_session(r, sess, #sess,
                                                             errmsg)
    if rc == FFI_ERROR then
        return nil, ffi_str(errmsg[0])
    end

    return true
end


return _M
