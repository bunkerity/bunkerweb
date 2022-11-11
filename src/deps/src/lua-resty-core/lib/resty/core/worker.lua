-- Copyright (C) Yichun Zhang (agentzh)


local ffi = require "ffi"
local base = require "resty.core.base"


local C = ffi.C
local new_tab = base.new_tab
local subsystem = ngx.config.subsystem


local ngx_lua_ffi_worker_id
local ngx_lua_ffi_worker_pid
local ngx_lua_ffi_worker_count
local ngx_lua_ffi_worker_exiting


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
end


function ngx.worker.exiting()
    return ngx_lua_ffi_worker_exiting() ~= 0
end


function ngx.worker.pid()
    return ngx_lua_ffi_worker_pid()
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
