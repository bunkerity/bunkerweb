local ffi = require 'ffi'
local base = require "resty.core.base"

local C = ffi.C
local FFI_ERROR = base.FFI_ERROR
local get_request = base.get_request
local error = error
local tostring = tostring


ffi.cdef[[
int ngx_http_lua_ffi_get_phase(ngx_http_request_t *r, char **err)
]]


local errmsg = base.get_errmsg_ptr()
local context_names = {
    [0x00000001] = "set",
    [0x00000002] = "rewrite",
    [0x00000004] = "access",
    [0x00000008] = "content",
    [0x00000010] = "log",
    [0x00000020] = "header_filter",
    [0x00000040] = "body_filter",
    [0x00000080] = "timer",
    [0x00000100] = "init_worker",
    [0x00000200] = "balancer",
    [0x00000400] = "ssl_cert",
    [0x00000800] = "ssl_session_store",
    [0x00001000] = "ssl_session_fetch",
    [0x00002000] = "exit_worker",
    [0x00004000] = "ssl_client_hello",
    [0x00008000] = "server_rewrite",
    [0x00010000] = "proxy_ssl_verify",
}


function ngx.get_phase()
    local r = get_request()

    -- if we have no request object, assume we are called from the "init" phase
    if not r then
        return "init"
    end

    local context = C.ngx_http_lua_ffi_get_phase(r, errmsg)
    if context == FFI_ERROR then -- NGX_ERROR
        error(errmsg, 2)
    end

    local phase = context_names[context]
    if not phase then
        error("unknown phase: " .. tostring(context))
    end

    return phase
end


function ngx.get_raw_phase(r)
    local context = C.ngx_http_lua_ffi_get_phase(r, errmsg)
    if context == FFI_ERROR then -- NGX_ERROR
        error(errmsg, 2)
    end

    return context
end


return {
    version = base.version
}
