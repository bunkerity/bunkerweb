-- Put common type definition at the same place for convenience
-- and standarlization
local ffi = require "ffi"

--[[
    TYPE_ptr: usually used to define a pointer (to cast or something)
    char* var_name; // <- we use char_ptr

    ptr_of_TYPE: usually used to pass the pointer of an object that
    is already allocated. so that we can also set value of it as well

    int p = 2;    // ptr_of_int(); ptr_of_int[0] = 2;
    plus_one(&p); // <- we use ptr_of_int
]]

return {
    void_ptr = ffi.typeof("void *"),
    ptr_of_uint64 = ffi.typeof("uint64_t[1]"),
    ptr_of_uint = ffi.typeof("unsigned int[1]"),
    ptr_of_size_t = ffi.typeof("size_t[1]"),
    ptr_of_int = ffi.typeof("int[1]"),
    null = ffi.new("void *"), -- hack wher ngx.null is not available

    uchar_array = ffi.typeof("unsigned char[?]"),
    uchar_ptr = ffi.typeof("unsigned char*"),

    SIZE_MAX = math.pow(2, 64), -- nginx set _FILE_OFFSET_BITS to 64
}