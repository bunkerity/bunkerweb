-- Copyright (C) Yichun Zhang (agentzh)


local ffi = require 'ffi'
local base = require "resty.core.base"


local error = error
local tonumber = tonumber
local type = type
local C = ffi.C
local ffi_new = ffi.new
local ffi_str = ffi.string
local time_val = ffi_new("long[1]")
local get_string_buf = base.get_string_buf
local ngx = ngx
local FFI_ERROR = base.FFI_ERROR
local subsystem = ngx.config.subsystem


local ngx_lua_ffi_now
local ngx_lua_ffi_time
local ngx_lua_ffi_monotonic_msec
local ngx_lua_ffi_today
local ngx_lua_ffi_localtime
local ngx_lua_ffi_utctime
local ngx_lua_ffi_update_time


if subsystem == 'http' then
    ffi.cdef[[
double ngx_http_lua_ffi_now(void);
long ngx_http_lua_ffi_time(void);
long ngx_http_lua_ffi_monotonic_msec(void);
void ngx_http_lua_ffi_today(unsigned char *buf);
void ngx_http_lua_ffi_localtime(unsigned char *buf);
void ngx_http_lua_ffi_utctime(unsigned char *buf);
void ngx_http_lua_ffi_update_time(void);
int ngx_http_lua_ffi_cookie_time(unsigned char *buf, long t);
void ngx_http_lua_ffi_http_time(unsigned char *buf, long t);
void ngx_http_lua_ffi_parse_http_time(const unsigned char *str, size_t len,
    long *time);
    ]]

    ngx_lua_ffi_now = C.ngx_http_lua_ffi_now
    ngx_lua_ffi_time = C.ngx_http_lua_ffi_time
    ngx_lua_ffi_monotonic_msec = C.ngx_http_lua_ffi_monotonic_msec
    ngx_lua_ffi_today = C.ngx_http_lua_ffi_today
    ngx_lua_ffi_localtime = C.ngx_http_lua_ffi_localtime
    ngx_lua_ffi_utctime = C.ngx_http_lua_ffi_utctime
    ngx_lua_ffi_update_time = C.ngx_http_lua_ffi_update_time

elseif subsystem == 'stream' then
    ffi.cdef[[
double ngx_stream_lua_ffi_now(void);
long ngx_stream_lua_ffi_time(void);
long ngx_stream_lua_ffi_monotonic_msec(void);
void ngx_stream_lua_ffi_today(unsigned char *buf);
void ngx_stream_lua_ffi_localtime(unsigned char *buf);
void ngx_stream_lua_ffi_utctime(unsigned char *buf);
void ngx_stream_lua_ffi_update_time(void);
    ]]

    ngx_lua_ffi_now = C.ngx_stream_lua_ffi_now
    ngx_lua_ffi_time = C.ngx_stream_lua_ffi_time
    ngx_lua_ffi_monotonic_msec = C.ngx_stream_lua_ffi_monotonic_msec
    ngx_lua_ffi_today = C.ngx_stream_lua_ffi_today
    ngx_lua_ffi_localtime = C.ngx_stream_lua_ffi_localtime
    ngx_lua_ffi_utctime = C.ngx_stream_lua_ffi_utctime
    ngx_lua_ffi_update_time = C.ngx_stream_lua_ffi_update_time
end


function ngx.now()
    local now = tonumber(ngx_lua_ffi_now())
    return now
end


function ngx.time()
    local time = tonumber(ngx_lua_ffi_time())
    return time
end


local function monotonic_msec()
    local msec = tonumber(ngx_lua_ffi_monotonic_msec())
    return msec
end


local function monotonic_time()
    local msec = tonumber(ngx_lua_ffi_monotonic_msec())
    local time = msec / 1000

    return time
end


function ngx.update_time()
    ngx_lua_ffi_update_time()
end


function ngx.today()
    -- the format of today is 2010-11-19
    local today_buf_size = 10
    local buf = get_string_buf(today_buf_size)
    ngx_lua_ffi_today(buf)
    return ffi_str(buf, today_buf_size)
end


function ngx.localtime()
    -- the format of localtime is 2010-11-19 20:56:31
    local localtime_buf_size = 19
    local buf = get_string_buf(localtime_buf_size)
    ngx_lua_ffi_localtime(buf)
    return ffi_str(buf, localtime_buf_size)
end


function ngx.utctime()
    -- the format of utctime is 2010-11-19 20:56:31
    local utctime_buf_size = 19
    local buf = get_string_buf(utctime_buf_size)
    ngx_lua_ffi_utctime(buf)
    return ffi_str(buf, utctime_buf_size)
end


if subsystem == 'http' then

function ngx.cookie_time(sec)
    if type(sec) ~= "number" then
        error("number argument only", 2)
    end

    -- the format of cookie time is Mon, 28-Sep-2038 06:00:00 GMT
    -- or Mon, 28-Sep-18 06:00:00 GMT
    local cookie_time_buf_size = 29
    local buf = get_string_buf(cookie_time_buf_size)
    local used_size = C.ngx_http_lua_ffi_cookie_time(buf, sec)
    return ffi_str(buf, used_size)
end


function ngx.http_time(sec)
    if type(sec) ~= "number" then
        error("number argument only", 2)
    end

    -- the format of http time is Mon, 28 Sep 1970 06:00:00 GMT
    local http_time_buf_size = 29
    local buf = get_string_buf(http_time_buf_size)
    C.ngx_http_lua_ffi_http_time(buf, sec)
    return ffi_str(buf, http_time_buf_size)
end


function ngx.parse_http_time(time_str)
    if type(time_str) ~= "string" then
        error("string argument only", 2)
    end

    C.ngx_http_lua_ffi_parse_http_time(time_str, #time_str, time_val)

    local res = time_val[0]
    if res == FFI_ERROR then
        return nil
    end

    local time = tonumber(res)
    return time
end

end

return {
    version = base.version,
    monotonic_msec = monotonic_msec,
    monotonic_time = monotonic_time
}
