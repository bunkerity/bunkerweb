-- Copyright (C) Yichun Zhang (agentzh)


local base = require "resty.core.base"
base.allows_subsystem('http', 'stream')

local ffi = require 'ffi'
local errmsg = base.get_errmsg_ptr()
local FFI_ERROR = base.FFI_ERROR
local ffi_str = ffi.string
local tonumber = tonumber
local subsystem = ngx.config.subsystem

if subsystem == 'http' then
    require "resty.core.phase"  -- for ngx.get_phase
end

local ngx_phase = ngx.get_phase

local process_type_names = {
    [0 ]  = "single",
    [1 ]  = "master",
    [2 ]  = "signaller",
    [3 ]  = "worker",
    [4 ]  = "helper",
    [99]  = "privileged agent",
}


local C = ffi.C
local _M = { version = base.version }

local ngx_lua_ffi_enable_privileged_agent
local ngx_lua_ffi_get_process_type
local ngx_lua_ffi_process_signal_graceful_exit
local ngx_lua_ffi_master_pid

if subsystem == 'http' then
    ffi.cdef[[
        int ngx_http_lua_ffi_enable_privileged_agent(char **err,
            unsigned int connections);
        int ngx_http_lua_ffi_get_process_type(void);
        void ngx_http_lua_ffi_process_signal_graceful_exit(void);
        int ngx_http_lua_ffi_master_pid(void);
    ]]

    ngx_lua_ffi_enable_privileged_agent =
        C.ngx_http_lua_ffi_enable_privileged_agent
    ngx_lua_ffi_get_process_type = C.ngx_http_lua_ffi_get_process_type
    ngx_lua_ffi_process_signal_graceful_exit =
        C.ngx_http_lua_ffi_process_signal_graceful_exit
    ngx_lua_ffi_master_pid = C.ngx_http_lua_ffi_master_pid

else
    ffi.cdef[[
        int ngx_stream_lua_ffi_enable_privileged_agent(char **err,
            unsigned int connections);
        int ngx_stream_lua_ffi_get_process_type(void);
        void ngx_stream_lua_ffi_process_signal_graceful_exit(void);
        int ngx_stream_lua_ffi_master_pid(void);
    ]]

    ngx_lua_ffi_enable_privileged_agent =
        C.ngx_stream_lua_ffi_enable_privileged_agent
    ngx_lua_ffi_get_process_type = C.ngx_stream_lua_ffi_get_process_type
    ngx_lua_ffi_process_signal_graceful_exit =
        C.ngx_stream_lua_ffi_process_signal_graceful_exit
    ngx_lua_ffi_master_pid = C.ngx_stream_lua_ffi_master_pid
end


function _M.type()
    local typ = ngx_lua_ffi_get_process_type()
    return process_type_names[tonumber(typ)]
end


function _M.enable_privileged_agent(connections)
    if ngx_phase() ~= "init" then
        return nil, "API disabled in the current context"
    end

    connections = connections or 512

    if type(connections) ~= "number" or connections < 0 then
        return nil, "bad 'connections' argument: " ..
            "number expected and greater than 0"
    end

    local rc = ngx_lua_ffi_enable_privileged_agent(errmsg, connections)

    if rc == FFI_ERROR then
        return nil, ffi_str(errmsg[0])
    end

    return true
end


function _M.signal_graceful_exit()
    ngx_lua_ffi_process_signal_graceful_exit()
end


function _M.get_master_pid()
    local pid = ngx_lua_ffi_master_pid()
    if pid == FFI_ERROR then
        return nil
    end

    return tonumber(pid)
end


return _M
