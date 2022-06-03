-- Copyright (C) Yichun Zhang (agentzh)


local ffi = require 'ffi'
local base = require "resty.core.base"
local utils = require "resty.core.utils"


local subsystem = ngx.config.subsystem
local FFI_BAD_CONTEXT = base.FFI_BAD_CONTEXT
local FFI_DECLINED = base.FFI_DECLINED
local FFI_OK = base.FFI_OK
local new_tab = base.new_tab
local C = ffi.C
local ffi_cast = ffi.cast
local ffi_new = ffi.new
local ffi_str = ffi.string
local get_string_buf = base.get_string_buf
local get_size_ptr = base.get_size_ptr
local setmetatable = setmetatable
local lower = string.lower
local rawget = rawget
local ngx = ngx
local get_request = base.get_request
local type = type
local error = error
local tostring = tostring
local tonumber = tonumber
local str_replace_char = utils.str_replace_char


local _M = {
    version = base.version
}


local ngx_lua_ffi_req_start_time


if subsystem == "stream" then
    ffi.cdef[[
    double ngx_stream_lua_ffi_req_start_time(ngx_stream_lua_request_t *r);
    ]]

    ngx_lua_ffi_req_start_time = C.ngx_stream_lua_ffi_req_start_time

elseif subsystem == "http" then
    ffi.cdef[[
    double ngx_http_lua_ffi_req_start_time(ngx_http_request_t *r);
    ]]

    ngx_lua_ffi_req_start_time = C.ngx_http_lua_ffi_req_start_time
end


function ngx.req.start_time()
    local r = get_request()
    if not r then
        error("no request found")
    end

    return tonumber(ngx_lua_ffi_req_start_time(r))
end


if subsystem == "stream" then
    return _M
end


local errmsg = base.get_errmsg_ptr()
local ffi_str_type = ffi.typeof("ngx_http_lua_ffi_str_t*")
local ffi_str_size = ffi.sizeof("ngx_http_lua_ffi_str_t")


ffi.cdef[[
    typedef struct {
        ngx_http_lua_ffi_str_t   key;
        ngx_http_lua_ffi_str_t   value;
    } ngx_http_lua_ffi_table_elt_t;

    int ngx_http_lua_ffi_req_get_headers_count(ngx_http_request_t *r,
        int max, int *truncated);

    int ngx_http_lua_ffi_req_get_headers(ngx_http_request_t *r,
        ngx_http_lua_ffi_table_elt_t *out, int count, int raw);

    int ngx_http_lua_ffi_req_get_uri_args_count(ngx_http_request_t *r,
        int max, int *truncated);

    size_t ngx_http_lua_ffi_req_get_querystring_len(ngx_http_request_t *r);

    int ngx_http_lua_ffi_req_get_uri_args(ngx_http_request_t *r,
        unsigned char *buf, ngx_http_lua_ffi_table_elt_t *out, int count);

    int ngx_http_lua_ffi_req_get_method(ngx_http_request_t *r);

    int ngx_http_lua_ffi_req_get_method_name(ngx_http_request_t *r,
        unsigned char **name, size_t *len);

    int ngx_http_lua_ffi_req_set_method(ngx_http_request_t *r, int method);

    int ngx_http_lua_ffi_req_set_header(ngx_http_request_t *r,
        const unsigned char *key, size_t key_len, const unsigned char *value,
        size_t value_len, ngx_http_lua_ffi_str_t *mvals, size_t mvals_len,
        int override, char **errmsg);
]]


local table_elt_type = ffi.typeof("ngx_http_lua_ffi_table_elt_t*")
local table_elt_size = ffi.sizeof("ngx_http_lua_ffi_table_elt_t")
local truncated = ffi.new("int[1]")

local req_headers_mt = {
    __index = function (tb, key)
        return rawget(tb, (str_replace_char(lower(key), '_', '-')))
    end
}


function ngx.req.get_headers(max_headers, raw)
    local r = get_request()
    if not r then
        error("no request found")
    end

    if not max_headers then
        max_headers = -1
    end

    if not raw then
        raw = 0
    else
        raw = 1
    end

    local n = C.ngx_http_lua_ffi_req_get_headers_count(r, max_headers,
                                                       truncated)
    if n == FFI_BAD_CONTEXT then
        error("API disabled in the current context", 2)
    end

    if n == 0 then
        local headers = {}
        if raw == 0 then
            headers = setmetatable(headers, req_headers_mt)
        end

        return headers
    end

    local raw_buf = get_string_buf(n * table_elt_size)
    local buf = ffi_cast(table_elt_type, raw_buf)

    local rc = C.ngx_http_lua_ffi_req_get_headers(r, buf, n, raw)
    if rc == 0 then
        local headers = new_tab(0, n)
        for i = 0, n - 1 do
            local h = buf[i]

            local key = h.key
            key = ffi_str(key.data, key.len)

            local value = h.value
            value = ffi_str(value.data, value.len)

            local existing = headers[key]
            if existing then
                if type(existing) == "table" then
                    existing[#existing + 1] = value
                else
                    headers[key] = {existing, value}
                end

            else
                headers[key] = value
            end
        end

        if raw == 0 then
            headers = setmetatable(headers, req_headers_mt)
        end

        if truncated[0] ~= 0 then
            return headers, "truncated"
        end

        return headers
    end

    return nil
end


function ngx.req.get_uri_args(max_args)
    local r = get_request()
    if not r then
        error("no request found")
    end

    if not max_args then
        max_args = -1
    end

    local n = C.ngx_http_lua_ffi_req_get_uri_args_count(r, max_args, truncated)
    if n == FFI_BAD_CONTEXT then
        error("API disabled in the current context", 2)
    end

    if n == 0 then
        return {}
    end

    local args_len = C.ngx_http_lua_ffi_req_get_querystring_len(r)

    local strbuf = get_string_buf(args_len + n * table_elt_size)
    local kvbuf = ffi_cast(table_elt_type, strbuf + args_len)

    local nargs = C.ngx_http_lua_ffi_req_get_uri_args(r, strbuf, kvbuf, n)

    local args = new_tab(0, nargs)
    for i = 0, nargs - 1 do
        local arg = kvbuf[i]

        local key = arg.key
        key = ffi_str(key.data, key.len)

        local value = arg.value
        local len = value.len
        if len == -1 then
            value = true
        else
            value = ffi_str(value.data, len)
        end

        local existing = args[key]
        if existing then
            if type(existing) == "table" then
                existing[#existing + 1] = value
            else
                args[key] = {existing, value}
            end

        else
            args[key] = value
        end
    end

    if truncated[0] ~= 0 then
        return args, "truncated"
    end

    return args
end


do
    local methods = {
        [0x0002] = "GET",
        [0x0004] = "HEAD",
        [0x0008] = "POST",
        [0x0010] = "PUT",
        [0x0020] = "DELETE",
        [0x0040] = "MKCOL",
        [0x0080] = "COPY",
        [0x0100] = "MOVE",
        [0x0200] = "OPTIONS",
        [0x0400] = "PROPFIND",
        [0x0800] = "PROPPATCH",
        [0x1000] = "LOCK",
        [0x2000] = "UNLOCK",
        [0x4000] = "PATCH",
        [0x8000] = "TRACE",
    }

    local namep = ffi_new("unsigned char *[1]")

    function ngx.req.get_method()
        local r = get_request()
        if not r then
            error("no request found")
        end

        do
            local id = C.ngx_http_lua_ffi_req_get_method(r)
            if id == FFI_BAD_CONTEXT then
                error("API disabled in the current context", 2)
            end

            local method = methods[id]
            if method then
                return method
            end
        end

        local sizep = get_size_ptr()
        local rc = C.ngx_http_lua_ffi_req_get_method_name(r, namep, sizep)
        if rc ~= 0 then
            return nil
        end

        return ffi_str(namep[0], sizep[0])
    end
end  -- do


function ngx.req.set_method(method)
    local r = get_request()
    if not r then
        error("no request found")
    end

    if type(method) ~= "number" then
        error("bad method number", 2)
    end

    local rc = C.ngx_http_lua_ffi_req_set_method(r, method)
    if rc == FFI_OK then
        return
    end

    if rc == FFI_BAD_CONTEXT then
        error("API disabled in the current context", 2)
    end

    if rc == FFI_DECLINED then
        error("unsupported HTTP method: " .. method, 2)
    end

    error("unknown error: " .. rc)
end


do
    local function set_req_header(name, value, override)
        local r = get_request()
        if not r then
            error("no request found", 3)
        end

        if name == nil then
            error("bad 'name' argument: string expected, got nil", 3)
        end

        if type(name) ~= "string" then
            name = tostring(name)
        end

        local rc

        if value == nil then
            if not override then
                error("bad 'value' argument: string or table expected, got nil",
                      3)
            end

            rc = C.ngx_http_lua_ffi_req_set_header(r, name, #name, nil, 0, nil,
                                                   0, 1, errmsg)

        else
            local sval, sval_len, mvals, mvals_len, buf
            local value_type = type(value)

            if value_type == "table" then
                mvals_len = #value
                if mvals_len == 0 and not override then
                    error("bad 'value' argument: non-empty table expected", 3)
                end

                buf = get_string_buf(ffi_str_size * mvals_len)
                mvals = ffi_cast(ffi_str_type, buf)

                for i = 1, mvals_len do
                    local s = value[i]
                    if type(s) ~= "string" then
                        s = tostring(s)
                        value[i] = s
                    end

                    local str = mvals[i - 1]
                    str.data = s
                    str.len = #s
                end

                sval_len = 0

            else
                if value_type ~= "string" then
                    sval = tostring(value)
                else
                    sval = value
                end

                sval_len = #sval
                mvals_len = 0
            end

            rc = C.ngx_http_lua_ffi_req_set_header(r, name, #name, sval,
                                                   sval_len, mvals, mvals_len,
                                                   override and 1 or 0, errmsg)
        end

        if rc == FFI_OK or rc == FFI_DECLINED then
            return
        end

        if rc == FFI_BAD_CONTEXT then
            error("API disabled in the current context", 3)
        end

        -- rc == FFI_ERROR
        error(ffi_str(errmsg[0]))
    end


    _M.set_req_header = set_req_header


    function ngx.req.set_header(name, value)
        set_req_header(name, value, true) -- override
    end
end  -- do


function ngx.req.clear_header(name)
    local r = get_request()
    if not r then
        error("no request found")
    end

    if type(name) ~= "string" then
        name = tostring(name)
    end

    local rc = C.ngx_http_lua_ffi_req_set_header(r, name, #name, nil, 0, nil, 0,
                                                 1, errmsg)

    if rc == FFI_OK or rc == FFI_DECLINED then
        return
    end

    if rc == FFI_BAD_CONTEXT then
        error("API disabled in the current context", 2)
    end

    -- rc == FFI_ERROR
    error(ffi_str(errmsg[0]))
end


return _M
