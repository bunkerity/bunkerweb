-- Copyright (C) Yichun Zhang (agentzh)


local ffi = require "ffi"
local base = require "resty.core.base"


local C = ffi.C
local ffi_string = ffi.string
local ngx = ngx
local type = type
local error = error
local floor = math.floor
local tostring = tostring
local get_string_buf = base.get_string_buf
local get_size_ptr = base.get_size_ptr
local subsystem = ngx.config.subsystem


local ngx_lua_ffi_encode_base64
local ngx_lua_ffi_decode_base64


if subsystem == "http" then
    ffi.cdef[[
    size_t ngx_http_lua_ffi_encode_base64(const unsigned char *src,
                                          size_t len, unsigned char *dst,
                                          int no_padding);

    int ngx_http_lua_ffi_decode_base64(const unsigned char *src,
                                       size_t len, unsigned char *dst,
                                       size_t *dlen);
    ]]

    ngx_lua_ffi_encode_base64 = C.ngx_http_lua_ffi_encode_base64
    ngx_lua_ffi_decode_base64 = C.ngx_http_lua_ffi_decode_base64

elseif subsystem == "stream" then
    ffi.cdef[[
    size_t ngx_stream_lua_ffi_encode_base64(const unsigned char *src,
                                            size_t len, unsigned char *dst,
                                            int no_padding);

    int ngx_stream_lua_ffi_decode_base64(const unsigned char *src,
                                         size_t len, unsigned char *dst,
                                         size_t *dlen);
    ]]

    ngx_lua_ffi_encode_base64 = C.ngx_stream_lua_ffi_encode_base64
    ngx_lua_ffi_decode_base64 = C.ngx_stream_lua_ffi_decode_base64
end


local function base64_encoded_length(len, no_padding)
    return no_padding and floor((len * 8 + 5) / 6) or
           floor((len + 2) / 3) * 4
end


ngx.encode_base64 = function (s, no_padding)
    if type(s) ~= 'string' then
        if not s then
            s = ''
        else
            s = tostring(s)
        end
    end

    local slen = #s
    local no_padding_bool = false;
    local no_padding_int = 0;

    if no_padding then
        if no_padding ~= true then
            local typ = type(no_padding)
            error("bad no_padding: boolean expected, got " .. typ, 2)
        end

        no_padding_bool = true
        no_padding_int  = 1;
    end

    local dlen = base64_encoded_length(slen, no_padding_bool)
    local dst = get_string_buf(dlen)
    local r_dlen = ngx_lua_ffi_encode_base64(s, slen, dst, no_padding_int)
    -- if dlen ~= r_dlen then error("discrepancy in len") end
    return ffi_string(dst, r_dlen)
end


local function base64_decoded_length(len)
    return floor((len + 3) / 4) * 3
end


ngx.decode_base64 = function (s)
    if type(s) ~= 'string' then
        error("string argument only", 2)
    end
    local slen = #s
    local dlen = base64_decoded_length(slen)
    -- print("dlen: ", tonumber(dlen))
    local dst = get_string_buf(dlen)
    local pdlen = get_size_ptr()
    local ok = ngx_lua_ffi_decode_base64(s, slen, dst, pdlen)
    if ok == 0 then
        return nil
    end
    return ffi_string(dst, pdlen[0])
end


return {
    version = base.version
}
