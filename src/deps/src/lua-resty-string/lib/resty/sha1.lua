-- Copyright (C) by Yichun Zhang (agentzh)


require "resty.sha"
local ffi = require "ffi"
local ffi_new = ffi.new
local ffi_str = ffi.string
local C = ffi.C
local setmetatable = setmetatable
--local error = error


local _M = { _VERSION = '0.16' }


local mt = { __index = _M }


ffi.cdef[[
typedef struct SHAstate_st
        {
        SHA_LONG h0,h1,h2,h3,h4;
        SHA_LONG Nl,Nh;
        SHA_LONG data[SHA_LBLOCK];
        unsigned int num;
        } SHA_CTX;

int SHA1_Init(SHA_CTX *c);
int SHA1_Update(SHA_CTX *c, const void *data, size_t len);
int SHA1_Final(unsigned char *md, SHA_CTX *c);
]]

local digest_len = 20

local buf = ffi_new("char[?]", digest_len)
local ctx_ptr_type = ffi.typeof("SHA_CTX[1]")


function _M.new(self)
    local ctx = ffi_new(ctx_ptr_type)
    if C.SHA1_Init(ctx) == 0 then
        return nil
    end

    return setmetatable({ _ctx = ctx }, mt)
end


function _M.update(self, s)
    return C.SHA1_Update(self._ctx, s, #s) == 1
end


function _M.final(self)
    if C.SHA1_Final(buf, self._ctx) == 1 then
        return ffi_str(buf, digest_len)
    end

    return nil
end


function _M.reset(self)
    return C.SHA1_Init(self._ctx) == 1
end


return _M

