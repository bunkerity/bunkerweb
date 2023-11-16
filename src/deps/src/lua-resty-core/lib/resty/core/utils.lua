-- Copyright (C) Yichun Zhang (agentzh)


local ffi = require "ffi"
local base = require "resty.core.base"


local C = ffi.C
local ffi_str = ffi.string
local ffi_copy = ffi.copy
local byte = string.byte
local str_find = string.find
local get_string_buf = base.get_string_buf
local subsystem = ngx.config.subsystem


local _M = {
    version = base.version
}


if subsystem == "http" then
    ffi.cdef[[
    void ngx_http_lua_ffi_str_replace_char(unsigned char *buf, size_t len,
        const unsigned char find, const unsigned char replace);
    ]]


    function _M.str_replace_char(str, find, replace)
        if not str_find(str, find, nil, true) then
            return str
        end

        local len = #str
        local buf = get_string_buf(len)
        ffi_copy(buf, str, len)

        C.ngx_http_lua_ffi_str_replace_char(buf, len, byte(find),
                                            byte(replace))

        return ffi_str(buf, len)
    end
end


return _M
