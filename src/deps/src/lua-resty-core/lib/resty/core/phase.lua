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
    [0x0001] = "set",
    [0x0002] = "rewrite",
    [0x0004] = "access",
    [0x0008] = "content",
    [0x0010] = "log",
    [0x0020] = "header_filter",
    [0x0040] = "body_filter",
    [0x0080] = "timer",
    [0x0100] = "init_worker",
    [0x0200] = "balancer",
    [0x0400] = "ssl_cert",
    [0x0800] = "ssl_session_store",
    [0x1000] = "ssl_session_fetch",
    [0x2000] = "exit_worker",
    [0x4000] = "ssl_client_hello",
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


return {
    version = base.version
}
