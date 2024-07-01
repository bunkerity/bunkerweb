-- Copyright (C) by OpenResty Inc.


local ffi = require 'ffi'
local base = require "resty.core.base"
base.allows_subsystem('http')


local C = ffi.C
local ffi_cast = ffi.cast
local ffi_new = ffi.new
local ffi_str = ffi.string
local FFI_OK = base.FFI_OK
local new_tab = base.new_tab
local get_string_buf = base.get_string_buf
local get_request = base.get_request
local setmetatable = setmetatable
local type = type
local tostring = tostring
local error = error


local _M = {
    version = base.version
}


ffi.cdef[[
typedef void * ndk_set_var_value_pt;

int ngx_http_lua_ffi_ndk_lookup_directive(const unsigned char *var_data,
    size_t var_len, ndk_set_var_value_pt *func);
int ngx_http_lua_ffi_ndk_set_var_get(ngx_http_request_t *r,
    ndk_set_var_value_pt func, const unsigned char *arg_data, size_t arg_len,
    ngx_http_lua_ffi_str_t *value);
]]


local func_p = ffi_new("void*[1]")
local ffi_str_size = ffi.sizeof("ngx_http_lua_ffi_str_t")
local ffi_str_type = ffi.typeof("ngx_http_lua_ffi_str_t*")


local function ndk_set_var_get(self, var)
    if type(var) ~= "string" then
        var = tostring(var)
    end

    if C.ngx_http_lua_ffi_ndk_lookup_directive(var, #var, func_p) ~= FFI_OK then
        error('ndk.set_var: directive "' .. var
              .. '" not found or does not use ndk_set_var_value', 2)
    end

    local func = func_p[0]

    return function (arg)
        local r = get_request()
        if not r then
            error("no request found")
        end

        if type(arg) ~= "string" then
            arg = tostring(arg)
        end

        local buf = get_string_buf(ffi_str_size)
        local value = ffi_cast(ffi_str_type, buf)
        local rc = C.ngx_http_lua_ffi_ndk_set_var_get(r, func, arg, #arg, value)
        if rc ~= FFI_OK then
            error("calling directive " .. var .. " failed with code " .. rc, 2)
        end

        return ffi_str(value.data, value.len)
    end
end


local function ndk_set_var_set()
    error("not allowed", 2)
end


if ndk then
    local mt = new_tab(0, 2)
    mt.__newindex = ndk_set_var_set
    mt.__index = ndk_set_var_get

    ndk.set_var = setmetatable(new_tab(0, 0), mt)
end


return _M
