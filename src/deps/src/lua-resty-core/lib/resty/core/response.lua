-- Copyright (C) Yichun Zhang (agentzh)


local ffi = require 'ffi'
local base = require "resty.core.base"


local C = ffi.C
local ffi_cast = ffi.cast
local ffi_str = ffi.string
local new_tab = base.new_tab
local FFI_BAD_CONTEXT = base.FFI_BAD_CONTEXT
local FFI_NO_REQ_CTX = base.FFI_NO_REQ_CTX
local FFI_DECLINED = base.FFI_DECLINED
local get_string_buf = base.get_string_buf
local setmetatable = setmetatable
local type = type
local tostring = tostring
local get_request = base.get_request
local error = error
local ngx = ngx


local _M = {
    version = base.version
}


local MAX_HEADER_VALUES = 100
local errmsg = base.get_errmsg_ptr()
local ffi_str_type = ffi.typeof("ngx_http_lua_ffi_str_t*")
local ffi_str_size = ffi.sizeof("ngx_http_lua_ffi_str_t")


ffi.cdef[[
    int ngx_http_lua_ffi_set_resp_header(ngx_http_request_t *r,
        const char *key_data, size_t key_len, int is_nil,
        const char *sval, size_t sval_len, ngx_http_lua_ffi_str_t *mvals,
        size_t mvals_len, int override, char **errmsg);

    int ngx_http_lua_ffi_get_resp_header(ngx_http_request_t *r,
        const unsigned char *key, size_t key_len,
        unsigned char *key_buf, ngx_http_lua_ffi_str_t *values,
        int max_nvalues, char **errmsg);
]]


local ngx_lua_ffi_set_resp_header

local MACOS = jit and jit.os == "OSX"

if MACOS then
    ffi.cdef[[
        typedef struct {
            ngx_http_request_t   *r;
            const char           *key_data;
            size_t                key_len;
            int                   is_nil;
            const char           *sval;
            size_t                sval_len;
            void                 *mvals;
            size_t                mvals_len;
            int                   override;
            char                **errmsg;
        } ngx_http_lua_set_resp_header_params_t;

        int ngx_http_lua_ffi_set_resp_header_macos(
            ngx_http_lua_set_resp_header_params_t *p);
    ]]

    local set_params = ffi.new("ngx_http_lua_set_resp_header_params_t")

    ngx_lua_ffi_set_resp_header = function(r, key, key_len, is_nil,
                                           sval, sval_len, mvals,
                                           mvals_len, override, err)

        set_params.r = r
        set_params.key_data = key
        set_params.key_len = key_len
        set_params.is_nil = is_nil
        set_params.sval = sval
        set_params.sval_len = sval_len
        set_params.mvals = mvals
        set_params.mvals_len = mvals_len
        set_params.override = override
        set_params.errmsg = err

        return C.ngx_http_lua_ffi_set_resp_header_macos(set_params)
    end

else
    ngx_lua_ffi_set_resp_header = function(r, key, key_len, is_nil,
                                           sval, sval_len, mvals,
                                           mvals_len, override, err)

        return C.ngx_http_lua_ffi_set_resp_header(r, key, key_len, is_nil,
                                                  sval, sval_len, mvals,
                                                  mvals_len, override, err)
    end
end


local function set_resp_header(tb, key, value, no_override)
    local r = get_request()
    if not r then
        error("no request found")
    end

    if type(key) ~= "string" then
        key = tostring(key)
    end

    local rc
    if value == nil then
        if no_override then
            error("invalid header value", 3)
        end

        rc = ngx_lua_ffi_set_resp_header(r, key, #key, true, nil, 0, nil,
                                         0, 1, errmsg)
    else
        local sval, sval_len, mvals, mvals_len, buf

        if type(value) == "table" then
            mvals_len = #value
            if mvals_len == 0 and no_override then
                return
            end

            buf = get_string_buf(ffi_str_size * mvals_len)
            mvals = ffi_cast(ffi_str_type, buf)
            for i = 1, mvals_len do
                local s = value[i]
                if type(s) ~= "string" then
                    s = tostring(s)
                    value[i] = s
                end
                local str = mvals[i - 1]
                str.data = s
                str.len = #s
            end

            sval_len = 0

        else
            if type(value) ~= "string" then
                sval = tostring(value)
            else
                sval = value
            end
            sval_len = #sval

            mvals_len = 0
        end

        local override_int = no_override and 0 or 1
        rc = ngx_lua_ffi_set_resp_header(r, key, #key, false, sval,
                                         sval_len, mvals, mvals_len,
                                         override_int, errmsg)
    end

    if rc == 0 or rc == FFI_DECLINED then
        return
    end

    if rc == FFI_NO_REQ_CTX then
        error("no request ctx found")
    end

    if rc == FFI_BAD_CONTEXT then
        error("API disabled in the current context", 2)
    end

    -- rc == FFI_ERROR
    error(ffi_str(errmsg[0]), 2)
end


_M.set_resp_header = set_resp_header


local function get_resp_header(tb, key)
    local r = get_request()
    if not r then
        error("no request found")
    end

    if type(key) ~= "string" then
        key = tostring(key)
    end

    local key_len = #key

    local key_buf = get_string_buf(key_len + ffi_str_size * MAX_HEADER_VALUES)
    local values = ffi_cast(ffi_str_type, key_buf + key_len)
    local n = C.ngx_http_lua_ffi_get_resp_header(r, key, key_len, key_buf,
                                                 values, MAX_HEADER_VALUES,
                                                 errmsg)

    -- print("retval: ", n)

    if n == FFI_BAD_CONTEXT then
        error("API disabled in the current context", 2)
    end

    if n == 0 then
        return nil
    end

    if n == 1 then
        local v = values[0]
        return ffi_str(v.data, v.len)
    end

    if n > 0 then
        local ret = new_tab(n, 0)
        for i = 1, n do
            local v = values[i - 1]
            ret[i] = ffi_str(v.data, v.len)
        end
        return ret
    end

    -- n == FFI_ERROR
    error(ffi_str(errmsg[0]), 2)
end


do
    local mt = new_tab(0, 2)
    mt.__newindex = set_resp_header
    mt.__index = get_resp_header

    ngx.header = setmetatable(new_tab(0, 0), mt)
end


return _M
