-- Copyright (C) Yichun Zhang (agentzh)


local base = require "resty.core.base"
base.allows_subsystem('http', 'stream')


local ffi = require 'ffi'
local ffi_string = ffi.string
local get_string_buf = base.get_string_buf
local get_size_ptr = base.get_size_ptr
local C = ffi.C
local new_tab = base.new_tab
local ffi_new = ffi.new
local charpp = ffi_new("char *[1]")
local intp = ffi.new("int[1]")
local num_value = ffi_new("double[1]")
local get_request = base.get_request
local tonumber = tonumber
local type = type
local error = error
local subsystem = ngx.config.subsystem


local ngx_lua_ffi_errlog_set_filter_level
local ngx_lua_ffi_errlog_get_msg
local ngx_lua_ffi_errlog_get_sys_filter_level
local ngx_lua_ffi_raw_log


local _M = { version = base.version }


if subsystem == 'http' then
    ffi.cdef[[
int ngx_http_lua_ffi_errlog_set_filter_level(int level, unsigned char *err,
    size_t *errlen);
int ngx_http_lua_ffi_errlog_get_msg(char **log, int *loglevel,
    unsigned char *err, size_t *errlen, double *log_time);

int ngx_http_lua_ffi_errlog_get_sys_filter_level(ngx_http_request_t *r);

int ngx_http_lua_ffi_raw_log(ngx_http_request_t *r, int level,
    const unsigned char *s, size_t s_len);
    ]]

    ngx_lua_ffi_errlog_set_filter_level =
        C.ngx_http_lua_ffi_errlog_set_filter_level
    ngx_lua_ffi_errlog_get_msg = C.ngx_http_lua_ffi_errlog_get_msg
    ngx_lua_ffi_errlog_get_sys_filter_level =
        C.ngx_http_lua_ffi_errlog_get_sys_filter_level
    ngx_lua_ffi_raw_log = C.ngx_http_lua_ffi_raw_log

elseif subsystem == 'stream' then
    ffi.cdef[[
int ngx_stream_lua_ffi_errlog_set_filter_level(int level, unsigned char *err,
    size_t *errlen);
int ngx_stream_lua_ffi_errlog_get_msg(char **log, int *loglevel,
    unsigned char *err, size_t *errlen, double *log_time);

int ngx_stream_lua_ffi_errlog_get_sys_filter_level(ngx_stream_lua_request_t *r);

int ngx_stream_lua_ffi_raw_log(ngx_stream_lua_request_t *r, int level,
    const unsigned char *s, size_t s_len);
    ]]

    ngx_lua_ffi_errlog_set_filter_level =
        C.ngx_stream_lua_ffi_errlog_set_filter_level
    ngx_lua_ffi_errlog_get_msg = C.ngx_stream_lua_ffi_errlog_get_msg
    ngx_lua_ffi_errlog_get_sys_filter_level =
        C.ngx_stream_lua_ffi_errlog_get_sys_filter_level
    ngx_lua_ffi_raw_log = C.ngx_stream_lua_ffi_raw_log
end


local ERR_BUF_SIZE = 128
local FFI_ERROR = base.FFI_ERROR


function _M.set_filter_level(level)
    if not level then
        return nil, [[missing "level" argument]]
    end

    local err = get_string_buf(ERR_BUF_SIZE)
    local errlen = get_size_ptr()
    errlen[0] = ERR_BUF_SIZE
    local rc = ngx_lua_ffi_errlog_set_filter_level(level, err, errlen)

    if rc == FFI_ERROR then
        return nil, ffi_string(err, errlen[0])
    end

    return true
end


function _M.get_logs(max, logs)
    local err = get_string_buf(ERR_BUF_SIZE)
    local errlen = get_size_ptr()
    errlen[0] = ERR_BUF_SIZE

    local log = charpp
    local loglevel = intp
    local log_time = num_value

    max = max or 10

    if not logs then
        logs = new_tab(max * 3 + 1, 0)
    end

    local count = 0

    for i = 1, max do
        local loglen = ngx_lua_ffi_errlog_get_msg(log, loglevel, err, errlen,
                                                  log_time)
        if loglen == FFI_ERROR then
            return nil, ffi_string(err, errlen[0])
        end

        if loglen > 0 then
            logs[count + 1] = loglevel[0]
            logs[count + 2] = log_time[0]
            logs[count + 3] = ffi_string(log[0], loglen)

            count = count + 3
        end

        if loglen < 0 then  -- no error log
            logs[count + 1] = nil
            break
        end

        if i == max then    -- last one
            logs[count + 1] = nil
            break
        end
    end

    return logs
end


function _M.get_sys_filter_level()
    local r = get_request()
    return tonumber(ngx_lua_ffi_errlog_get_sys_filter_level(r))
end


function _M.raw_log(level, msg)
    if type(level) ~= "number" then
        error("bad argument #1 to 'raw_log' (must be a number)", 2)
    end

    if type(msg) ~= "string" then
        error("bad argument #2 to 'raw_log' (must be a string)", 2)
    end

    local r = get_request()

    local rc = ngx_lua_ffi_raw_log(r, level, msg, #msg)

    if rc == FFI_ERROR then
        error("bad log level", 2)
    end
end


return _M
