-- Copyright (C) Yichun Zhang (agentzh)


local ffi = require 'ffi'
local base = require "resty.core.base"
require "resty.core.phase"  -- for ngx.get_phase


local C = ffi.C
local ffi_str = ffi.string
local FFI_AGAIN = base.FFI_AGAIN
local FFI_OK = base.FFI_OK
local get_request = base.get_request
local get_string_buf = base.get_string_buf
local getmetatable = getmetatable
local ngx = ngx
local ngx_phase = ngx.get_phase


local _M = {
    version = base.version
}


ffi.cdef[[
    typedef unsigned char u_char;

    void ngx_http_lua_ffi_get_setby_param(ngx_http_request_t *r, int idx,
        u_char **data, size_t *len);
    int ngx_http_lua_ffi_get_body_filter_param_eof(ngx_http_request_t *r);
    int ngx_http_lua_ffi_get_body_filter_param_body(ngx_http_request_t *r,
        u_char **data_p, size_t *len_p);
    int ngx_http_lua_ffi_copy_body_filter_param_body(ngx_http_request_t *r,
        u_char *data);
]]
local data_p = ffi.new("unsigned char*[1]")
local len_p = ffi.new("size_t[1]")


local function get_setby_param(r, idx)
    C.ngx_http_lua_ffi_get_setby_param(r, idx, data_p, len_p)
    if len_p[0] == 0 then
        return nil
    end

    return ffi_str(data_p[0], len_p[0])
end


local function get_body_filter_param(r, idx)
    if idx == 1 then
        data_p[0] = nil
        local rc = C.ngx_http_lua_ffi_get_body_filter_param_body(r, data_p,
                                                                 len_p)
        if rc == FFI_AGAIN then
            local buf = get_string_buf(len_p[0])
            assert(C.ngx_http_lua_ffi_copy_body_filter_param_body(r, buf)
                   == FFI_OK)
            return ffi_str(buf, len_p[0])
        end

        if len_p[0] == 0 then
            return ""
        end

        return ffi_str(data_p[0], len_p[0])

    elseif idx == 2 then
        local rc = C.ngx_http_lua_ffi_get_body_filter_param_eof(r)
        return rc == 1

    else
        return nil
    end
end


local function get_param(tb, idx)
    local r = get_request()
    if not r then
        error("no request found")
    end

    local phase = ngx_phase()
    if phase == "set" then
        return get_setby_param(r, idx)
    end

    if phase == "body_filter" then
        return get_body_filter_param(r, idx)
    end

    error("API disabled in the current context")
end


do
    local mt = getmetatable(ngx.arg)
    mt.__index = get_param
end


return _M
