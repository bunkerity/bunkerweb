-- Copyright (C) Yichun Zhang (agentzh)


local ffi = require "ffi"
local jit = require "jit"
local base = require "resty.core.base"
local ffi_cast = ffi.cast


local C = ffi.C
local new_tab = base.new_tab
local subsystem = ngx.config.subsystem
local get_string_buf = base.get_string_buf
local get_size_ptr = base.get_size_ptr


local ngx_lua_ffi_worker_id
local ngx_lua_ffi_worker_pid
local ngx_lua_ffi_worker_pids
local ngx_lua_ffi_worker_count
local ngx_lua_ffi_worker_exiting
local ffi_intp_type = ffi.typeof("int *")
local ffi_int_size = ffi.sizeof("int")


ngx.worker = new_tab(0, 4)


if subsystem == "http" then
    ffi.cdef[[
    int ngx_http_lua_ffi_worker_id(void);
    int ngx_http_lua_ffi_worker_pid(void);
    int ngx_http_lua_ffi_worker_count(void);
    int ngx_http_lua_ffi_worker_exiting(void);
    ]]

    ngx_lua_ffi_worker_id = C.ngx_http_lua_ffi_worker_id
    ngx_lua_ffi_worker_pid = C.ngx_http_lua_ffi_worker_pid
    ngx_lua_ffi_worker_count = C.ngx_http_lua_ffi_worker_count
    ngx_lua_ffi_worker_exiting = C.ngx_http_lua_ffi_worker_exiting
    if jit.os ~= "Windows" then
        ffi.cdef[[
        int ngx_http_lua_ffi_worker_pids(int *pids, size_t *pids_len);
        ]]

        ngx_lua_ffi_worker_pids = C.ngx_http_lua_ffi_worker_pids
    end

elseif subsystem == "stream" then
    ffi.cdef[[
    int ngx_stream_lua_ffi_worker_id(void);
    int ngx_stream_lua_ffi_worker_pid(void);
    int ngx_stream_lua_ffi_worker_count(void);
    int ngx_stream_lua_ffi_worker_exiting(void);
    ]]

    ngx_lua_ffi_worker_id = C.ngx_stream_lua_ffi_worker_id
    ngx_lua_ffi_worker_pid = C.ngx_stream_lua_ffi_worker_pid
    ngx_lua_ffi_worker_count = C.ngx_stream_lua_ffi_worker_count
    ngx_lua_ffi_worker_exiting = C.ngx_stream_lua_ffi_worker_exiting

    if jit.os ~= "Windows" then
        ffi.cdef[[
        int ngx_stream_lua_ffi_worker_pids(int *pids, size_t *pids_len);
        ]]

        ngx_lua_ffi_worker_pids = C.ngx_stream_lua_ffi_worker_pids
    end
end


function ngx.worker.exiting()
    return ngx_lua_ffi_worker_exiting() ~= 0
end


function ngx.worker.pid()
    return ngx_lua_ffi_worker_pid()
end


if jit.os ~= "Windows" then
    function ngx.worker.pids()
        if ngx.get_phase() == "init" or ngx.get_phase() == "init_worker" then
            return nil, "API disabled in the current context"
        end

        local pids = {}
        local size_ptr = get_size_ptr()
        -- the old and the new workers coexist during reloading
        local worker_cnt = ngx.worker.count() * 4
        if worker_cnt == 0 then
            return pids
        end

        size_ptr[0] = worker_cnt
        local pids_ptr = get_string_buf(worker_cnt * ffi_int_size)
        local intp_buf = ffi_cast(ffi_intp_type, pids_ptr)
        local res = ngx_lua_ffi_worker_pids(intp_buf, size_ptr)

        if res == 0 then
            for i = 1, tonumber(size_ptr[0]) do
                pids[i] = intp_buf[i-1]
            end
        end
        return pids
    end
end

function ngx.worker.id()
    local id = ngx_lua_ffi_worker_id()
    if id < 0 then
        return nil
    end

    return id
end


function ngx.worker.count()
    return ngx_lua_ffi_worker_count()
end


return {
    _VERSION = base.version
}
