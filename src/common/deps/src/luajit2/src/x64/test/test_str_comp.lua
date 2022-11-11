--[[
 Given two content-idental string s1, s2, test if they end up to be the
 same string object. The purpose of this test is to make sure hash function
 do not accidently include extraneous bytes before and after the string in
 question.
]]

local ffi = require("ffi")
local C = ffi.C

ffi.cdef[[
    void free(void*);
    char* malloc(size_t);
    void *memset(void*, int, size_t);
    void *memcpy(void*, void*, size_t);
    long time(void*);
    void srandom(unsigned);
    long random(void);
]]


local function test_equal(len_min, len_max)
    -- source string is wrapped by 16-byte-junk both before and after the
    -- string
    local x = C.random()
    local l = len_min + x % (len_max - len_min);
    local buf_len = tonumber(l + 16 * 2)

    local src_buf = C.malloc(buf_len)
    for i = 0, buf_len - 1 do
        src_buf[i] = C.random() % 255
    end

    -- dest string is the clone of the source string, but it is sandwiched
    -- by different junk bytes
    local dest_buf = C.malloc(buf_len)
    C.memset(dest_buf, 0x5a, buf_len)

    local ofst = 8 + (C.random() % 8)
    C.memcpy(dest_buf + ofst, src_buf + 16, l);

    local str1 = ffi.string(src_buf + 16, l)
    local str2 = ffi.string(dest_buf + ofst, l)

    C.free(src_buf)
    C.free(dest_buf)

    if str1 ~= str2 then
        -- Oops, look like hash function mistakenly include extraneous bytes
        -- close to the string
        return 1 -- wtf
    end
end

--local lens = {1, 4, 16, 128, 1024}
local lens = {128, 1024}
local iter = 1000

for i = 1, #lens - 1 do
    for j = 1, iter do
        if test_equal(lens[i], lens[i+1]) ~= nil then
            os.exit(1)
        end
    end
end

os.exit(0)
