-- Copyright (C) Yichun Zhang. All rights reserved.


local ffi = require "ffi"
local C = ffi.C

local base = require "resty.core.base"
base.allows_subsystem('http')
local FFI_BAD_CONTEXT = base.FFI_BAD_CONTEXT
local core_response = require "resty.core.response"
local set_resp_header = core_response.set_resp_header
local get_request = base.get_request

ffi.cdef[[
    int ngx_http_lua_ffi_set_resp_status_and_reason(ngx_http_request_t *r,
        int status, const char *reason, size_t reason_len);
]]


local _M = { version = base.version }


function _M.add_header(key, value)
    set_resp_header(nil, key, value, true)
end


function _M.set_status(status, reason)
    local r = get_request()

    if not r then
        error("no request found")
    end

    if type(status) ~= 'number' then
        status = tonumber(status)
    end

    local rc = C.ngx_http_lua_ffi_set_resp_status_and_reason(r, status,
                                                             reason, #reason)
    if rc == FFI_BAD_CONTEXT then
        error("API disabled in the current context", 2)
    end
end

return _M
