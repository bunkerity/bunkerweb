-- Copyright (C) by Yichun Zhang (agentzh)


local ffi = require "ffi"


local _M = { _VERSION = '0.16' }


ffi.cdef[[
typedef unsigned long SHA_LONG;
typedef unsigned long long SHA_LONG64;

enum {
    SHA_LBLOCK = 16
};
]];

return _M
