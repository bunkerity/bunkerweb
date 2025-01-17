-- Copyright (C) by Yichun Zhang (agentzh)


local ffi = require "ffi"
local ffi_new = ffi.new
local ffi_str = ffi.string
local C = ffi.C
--local setmetatable = setmetatable
--local error = error


local _M = { _VERSION = '0.16' }


ffi.cdef[[
int RAND_bytes(unsigned char *buf, int num);
int RAND_pseudo_bytes(unsigned char *buf, int num);
]]


function _M.bytes(len, strong)
    if strong == nil then
        strong = true
    end
    local buf = ffi_new("char[?]", len)
    if strong then
        if C.RAND_bytes(buf, len) == 0 then
            return nil
        end
    else
        C.RAND_pseudo_bytes(buf,len)
    end

    return ffi_str(buf, len)
end


return _M

