-- Copyright (C) Yichun Zhang (agentzh)


local ffi = require "ffi"
local base = require "resty.core.base"


local C = ffi.C
local ffi_new = ffi.new
local ffi_string = ffi.string
local ngx = ngx
local type = type
local error = error
local tostring = tostring
local subsystem = ngx.config.subsystem


local ngx_lua_ffi_md5
local ngx_lua_ffi_md5_bin
local ngx_lua_ffi_sha1_bin
local ngx_lua_ffi_crc32_long
local ngx_lua_ffi_crc32_short


if subsystem == "http" then
    ffi.cdef[[
    void ngx_http_lua_ffi_md5_bin(const unsigned char *src, size_t len,
                                  unsigned char *dst);

    void ngx_http_lua_ffi_md5(const unsigned char *src, size_t len,
                              unsigned char *dst);

    int ngx_http_lua_ffi_sha1_bin(const unsigned char *src, size_t len,
                                  unsigned char *dst);

    unsigned int ngx_http_lua_ffi_crc32_long(const unsigned char *src,
                                             size_t len);

    unsigned int ngx_http_lua_ffi_crc32_short(const unsigned char *src,
                                              size_t len);
    ]]

    ngx_lua_ffi_md5 = C.ngx_http_lua_ffi_md5
    ngx_lua_ffi_md5_bin = C.ngx_http_lua_ffi_md5_bin
    ngx_lua_ffi_sha1_bin = C.ngx_http_lua_ffi_sha1_bin
    ngx_lua_ffi_crc32_short = C.ngx_http_lua_ffi_crc32_short
    ngx_lua_ffi_crc32_long = C.ngx_http_lua_ffi_crc32_long

elseif subsystem == "stream" then
    ffi.cdef[[
    void ngx_stream_lua_ffi_md5_bin(const unsigned char *src, size_t len,
                                    unsigned char *dst);

    void ngx_stream_lua_ffi_md5(const unsigned char *src, size_t len,
                                unsigned char *dst);

    int ngx_stream_lua_ffi_sha1_bin(const unsigned char *src, size_t len,
                                    unsigned char *dst);

    unsigned int ngx_stream_lua_ffi_crc32_long(const unsigned char *src,
                                               size_t len);

    unsigned int ngx_stream_lua_ffi_crc32_short(const unsigned char *src,
                                                size_t len);
    ]]

    ngx_lua_ffi_md5 = C.ngx_stream_lua_ffi_md5
    ngx_lua_ffi_md5_bin = C.ngx_stream_lua_ffi_md5_bin
    ngx_lua_ffi_sha1_bin = C.ngx_stream_lua_ffi_sha1_bin
    ngx_lua_ffi_crc32_short = C.ngx_stream_lua_ffi_crc32_short
    ngx_lua_ffi_crc32_long = C.ngx_stream_lua_ffi_crc32_long
end


local MD5_DIGEST_LEN = 16
local md5_buf = ffi_new("unsigned char[?]", MD5_DIGEST_LEN)

ngx.md5_bin = function (s)
    if type(s) ~= 'string' then
        if not s then
            s = ''
        else
            s = tostring(s)
        end
    end
    ngx_lua_ffi_md5_bin(s, #s, md5_buf)
    return ffi_string(md5_buf, MD5_DIGEST_LEN)
end


local MD5_HEX_DIGEST_LEN = MD5_DIGEST_LEN * 2
local md5_hex_buf = ffi_new("unsigned char[?]", MD5_HEX_DIGEST_LEN)

ngx.md5 = function (s)
    if type(s) ~= 'string' then
        if not s then
            s = ''
        else
            s = tostring(s)
        end
    end
    ngx_lua_ffi_md5(s, #s, md5_hex_buf)
    return ffi_string(md5_hex_buf, MD5_HEX_DIGEST_LEN)
end


local SHA_DIGEST_LEN = 20
local sha_buf = ffi_new("unsigned char[?]", SHA_DIGEST_LEN)

ngx.sha1_bin = function (s)
    if type(s) ~= 'string' then
        if not s then
            s = ''
        else
            s = tostring(s)
        end
    end
    local ok = ngx_lua_ffi_sha1_bin(s, #s, sha_buf)
    if ok == 0 then
        error("SHA-1 support missing in Nginx")
    end
    return ffi_string(sha_buf, SHA_DIGEST_LEN)
end


ngx.crc32_short = function (s)
    if type(s) ~= "string" then
        if not s then
            s = ""
        else
            s = tostring(s)
        end
    end

    return ngx_lua_ffi_crc32_short(s, #s)
end


ngx.crc32_long = function (s)
    if type(s) ~= "string" then
        if not s then
            s = ""
        else
            s = tostring(s)
        end
    end

    return ngx_lua_ffi_crc32_long(s, #s)
end


return {
    version = base.version
}
