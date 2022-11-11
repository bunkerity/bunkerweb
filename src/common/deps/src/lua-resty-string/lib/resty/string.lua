-- Copyright (C) by Yichun Zhang (agentzh)


local ffi = require "ffi"
local ffi_new = ffi.new
local ffi_str = ffi.string
local C = ffi.C
--local setmetatable = setmetatable
--local error = error
local tonumber = tonumber


local _M = { _VERSION = '0.14' }


ffi.cdef[[
typedef unsigned char u_char;

u_char * ngx_hex_dump(u_char *dst, const u_char *src, size_t len);

intptr_t ngx_atoi(const unsigned char *line, size_t n);
]]

local str_type = ffi.typeof("uint8_t[?]")

local BUF_MAX_LEN = 1024
local hex_buf = ffi_new(str_type, BUF_MAX_LEN)
function _M.to_hex(s)
    local len = #s
    local buf_len = len * 2
    local buf
    if buf_len <= BUF_MAX_LEN then
        buf = hex_buf
    else
        buf = ffi_new(str_type, buf_len)
    end
    C.ngx_hex_dump(buf, s, len)
    return ffi_str(buf, buf_len)
end

function _M.atoi(s)
    return tonumber(C.ngx_atoi(s, #s))
end


return _M
